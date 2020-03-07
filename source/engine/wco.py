#!/usr/bin/python 
# -*- coding: utf-8 -*- 
######################################################################################################################
#  Copyright 2019 Amazon.com, Inc. or its affiliates. All Rights Reserved.                                           #
#                                                                                                                    #
#  Licensed under the Apache License, Version 2.0 (the "License"). You may not use this file except in compliance    #
#  with the License. A copy of the License is located at                                                             #
#                                                                                                                    #
#      http://www.apache.org/licenses/LICENSE-2.0                                                                    #
#                                                                                                                    #
#  or in the "license" file accompanying this file. This file is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES #
#  OR CONDITIONS OF ANY KIND, express or implied. See the License for the specific language governing permissions    #
#  and limitations under the License.                                                                                #
######################################################################################################################

# wco.py
# This is the main program that reads the CloudFormationTempate (CFT) and scans for workspace directories
# It accesses AWS cloud formation and workspaces apis, then calls directory_reader to process each directory
# Regardless of CFT deployment, this processes ALL regions, ALL directories and ALL workspaces for the account

import boto3
import botocore
import calendar
import datetime
import json
import logging
import sys
import threading
import time
import uuid
import os

from lib.directory_reader import DirectoryReader

# Set default logging level
logging.basicConfig(stream=sys.stdout, format='%(levelname)s: %(message)s', level=logging.INFO)
log = logging.getLogger()

endTime = time.strftime("%Y-%m-%dT%H:%M:%SZ")
startTime = time.strftime("%Y-%m") + '-01T00:00:00Z'
lastDay = calendar.monthrange(int(time.strftime("%Y")), int(time.strftime("%m")))[1]
maxRetries = 3

runUUID = str(uuid.uuid4())
anonymousDataEndpoint = 'https://metrics.awssolutionsbuilder.com/generic'
regionCount = 0;
directoryCount = 0;

# Pull Stack Parameters from environment
# These are assigned by CloudFormation as container environment variables in production,
# or as online params (docker) shell vars when testing

stackParams = {}
for param in {'LogLevel', 
              'DryRun',
              'TestEndOfMonth',
              'SendAnonymousData',
              'SolutionVersion',
              'SolutionID',
              'UUID',
              'BucketName',
              'ValueLimit',
              'StandardLimit',
              'PerformanceLimit',
              'PowerLimit',
              'PowerProLimit',
              'GraphicsLimit',
              'GraphicsProLimit'
             }:
    stackParams[param] = os.environ[param]


# Check to make sure we have values for all expected stack parameters
# Otherwise exit with appropriate log errors
for param in stackParams:
    if stackParams[param] and not stackParams[param].isspace():
      log.info('Parameter: %s, Value: %s', param, stackParams[param])
    else:
      log.error('No value for stack parameter -> %s', param)
      sys.exit()

log.setLevel(stackParams['LogLevel'])
log.info('Logging level set to %s', logging._levelToName[log.getEffectiveLevel()])

theDay = int(time.strftime('%d'))
# Determine if we should run end-of-month routine.
if (theDay == int(lastDay)):
    stackParams['TestEndOfMonth'] = 'Yes'
    log.info('Last day of month, setting TestEndOfMonth to Yes')
    log.info('It is the last day of the month, last day is %s and today is %s', lastDay, theDay)
else:
    log.info('It is NOT the last day of the month, last day is %s and today is %s', lastDay, theDay)

# Get all regions that run Workspaces // CHANGE: cancel get all regions because the bug of get_available_regions in China
# for i in range(0, maxRetries):
#     log.debug('Try #%s to get_regions for WorkSpaces', i+1)
#     try:
#         wsRegions = boto3.session.Session().get_available_regions('workspaces')
#         break
#     except botocore.exceptions.ClientError as e:
#         log.error(e)
#         if i >= maxRetries - 1: log.error('Error processing get_regions for WorkSpaces: ExceededMaxRetries')
#         else: time.sleep(i/10)

# For each region // CHANGE: remove wsRegion and cancel foreach loop, just scan ZHY region
totalWorkspaces = 0
wsRegion = 'cn-northwest-1'
regionCount += 1

# Create a WS Client
wsClient = boto3.client('workspaces', region_name=wsRegion)

log.info('>>>> Scanning Workspace Directories for Region %s', wsRegion)

for i in range(0, maxRetries):
    log.debug('Try #%s to get list of directories', i+1)

    # Get the directories within the region
    try:
        directories = wsClient.describe_workspace_directories()
        break
    except botocore.exceptions.ClientError as e:
        log.error(e)
        if i >= maxRetries - 1: log.error('describe_workspace_directories ExceededMaxRetries')
        else: time.sleep(i/10)

# For each directory
for directory in directories["Directories"]:
    directoryCount += 1

    directoryParams = {
        "DirectoryId": directory["DirectoryId"],
        "Region": wsRegion,
        "EndTime": endTime,
        "StartTime": startTime,
        "LastDay": str(lastDay),
        "RunUUID": runUUID,
        "AnonymousDataEndpoint": anonymousDataEndpoint
    }

    log.info('Calling directory reader')
    directoryReader = DirectoryReader()
    countWorkspaces = directoryReader.read_directory(wsRegion, stackParams, directoryParams)
    totalWorkspaces = totalWorkspaces + countWorkspaces

log.info('Successfully invoked directory_reader for %d workspaces in %d directories across %d regions.', totalWorkspaces, directoryCount, regionCount)

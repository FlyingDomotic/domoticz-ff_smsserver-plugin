#!/usr/bin/python3
#
#   This file extract values of all Domoticz used devices.
#       It also add syntax of allowed SMS commands for all supported devices
#
#   Ce script extrait les valeurs de l'ensemble des dispositifs Domoticz utilsés
#       Il ajoute également la syntaxe des commandes SMS autorisées pour les dispositifs supportés
#
#   Flying Domotic - https://github.com/FlyingDomotic/domoticz-mqttmapper-plugin
#
#   Licence: GNU GENERAL PUBLIC LICENSE Version 3
#

fileVersion = "1.1.0" # File version

import pathlib
import os
import json
import requests
import base64
from FF_analyzeCommand import FF_analyzeCommand

# Load a dictionary to a file
def loadDictionary(file):
    if os.path.exists(file):
        with open(file, encoding="UTF-8") as f:
            try:
                return json.loads(f.read())
            except Exception as e:
                print(F"{e} when loading {file}")
                return None
    else:
        print("File {file} not found!")
        return None

# Check if new API is used
def isNewApi(version):
    return version[:2] == "20" and version >= "2023.2"

# Execute a JSON request
def readApi(command):
    # Send request
    response = requests.get(domoticzUrl+"json.htm?"+command)
    # If status code
    if response.status_code == 200:
        # Check status answer = "OK"
        if response.json()["status"] == "OK":
            return response
    # Print error message and exit
    print("Error "+str(response.status_code)+" reading "+response.url)
    print("Returned: "+response.text)
    exit(2)

# Get a key in dictionary, return default value if not found
def getKey(key, dict, default = None):
    if key in dict:
        return dict[key]
    else:
        return default

#   *****************
#   *** Main code ***
#   ****************

# Set current working directory to this python file folder
currentPath = pathlib.Path(__file__).parent.resolve()
os.chdir(currentPath)

# Get this file name (w/o path & extension)
cdeFile = pathlib.Path(__file__).stem

# Load SMS server json configuration file
decodeFile = os.path.join(currentPath, "smsTables.json")
analyzer = FF_analyzeCommand()

# Check for errors, print them and exit if needed
errorText, messages = analyzer.loadData(decodeFile)
if errorText:
    print("LoadData status: "+errorText)
if messages:
    print(messages)
if errorText:
    exit(2)

# Read SMS server json configuration file
jsonData = loadDictionary(decodeFile)
if jsonData == None:
    exit(2)

# Get Domoticz URL
domoticzUrl = analyzer.getValue2(jsonData, "settings", "domoticzUrl", "http://127.0.0.1:8080/")
prefix = analyzer.getValue2(jsonData, "settings", "smsServerPrefix", "domoticz")
showHiddenDevices = analyzer.getValue2(jsonData, "settings", "showHiddenDevices", False)
showUsedDeviceOnly = analyzer.getValue2(jsonData, "settings", "showUsedDeviceOnly", True)

# Get Domoticz settings to find version number
domoticzVersionResponse = readApi("type=command&param=getversion")
domoticzVersion = getKey("version", domoticzVersionResponse.json(), "")
if domoticzVersion == "":
    domoticzVersion = "2099.9"
    print(F"Can't find 'version' in {domoticzVersionResponse.text}, setting to {domoticzVersion}")

# Compose command to send depending on user needs
if isNewApi(domoticzVersion):
    params = "type=command&param=getdevices"
else:
    params = "type=devices"

if showHiddenDevices:
    params +="&displayhidden=1"

if showUsedDeviceOnly:
    params +="&used=true"

# Extract Domoticz device list
list=[]
response = readApi(params)

# For each device in response
for deviceData in response.json()['result']:
    # Extract some data
    status = getKey('Data', deviceData)
    usage = getKey('Usage', deviceData)
    deviceName = deviceData['Name']
    # Specific case for counter and/or usage
    if usage:
        status = usage
    counter = getKey('CounterToday', deviceData)
    if counter:
        status = counter
    if usage and counter:
        status = usage + "/" + counter
    # Extract level, if existing
    level = getKey('Level', deviceData)
    if level:
        status = str(level) + "%"
        names = getKey('LevelNames', deviceData)
        if names:
            nameList = base64.b64decode(names.encode("ascii")).decode('UTF8').split('|')
            status = nameList[int(level/10)]
    # Try to find device in SMS server data
    if deviceName in analyzer.devicesDict.keys():
        # Extract device SMs server settings
        device = analyzer.getValue2(analyzer.devicesDict, deviceName, "name", deviceName)
        deviceCommandValues = analyzer.getValue2(analyzer.devicesDict, device, "allow")
        deviceClassMappings = analyzer.getValue2(analyzer.devicesDict, device, "mapping")
        # Extract all allowed commands for this device
        deviceCommands = ""
        for command in analyzer.commandsDict:
            commandValue = analyzer.getValue2(analyzer.commandsDict, command, "commandValue")
            if commandValue in deviceCommandValues:
                deviceCommands += "/" + command
        # Extract device list of values
        setValues = []
        if deviceClassMappings:
            for value in deviceClassMappings.keys():
                setValues.append(value)
        # Extract min/max values
        minValue = analyzer.getValue2(analyzer.devicesDict, device, "minValue")
        maxValue = analyzer.getValue2(analyzer.devicesDict, device, "maxValue")
        if minValue != None:
            if maxValue != None:
                setValues.append(F"{minValue}:{maxValue}")
            else:
                setValues.append(F">={minValue}")
        else:
            if maxValue != None:
                setValues.append(F"<={maxValue}")
        if setValues:
            setValues = " " + str(setValues)
        else:
            setValues = ""
        # Add Domoticz data and SMS values
        list.append(deviceName+' = '+status+' ('+deviceData['LastUpdate'][8:-3]+')\n\t'+prefix+' ['+deviceCommands[1:]+'] '+device.lower()+setValues)
    else:
        # Add Domoticz data
        list.append(deviceName+' = '+status+' ('+deviceData['LastUpdate'][8:-3]+')')

# Sort list
list.sort()

# Print each line on terminal
for item in list:
    print(item)
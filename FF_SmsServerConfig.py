#!/usr/bin/python3
#   Creates FF_SmsServer config default file from template and Domoticz device list
#   V1.0.0
import requests
import base64
import pathlib
import os
import json
import re

removeLeadingPluginName = False
keepDomoticzDeviceList = False
showHiddenDevices = False
showUsedDeviceOnly = True
minimalConfigVersion = "V1.0.0"
minimalTemplateVersion = "V1.0.0"

# Load a dictionary from a file
def loadDictionary(file):
    if os.path.exists(file):
        with open(file, 'rt', encoding='utf-8') as f:
            return json.loads(f.read())
    else:
        return {}

# Execute a JSON request
def getResult(command):
    response = requests.get(domoticzUrl+"json.htm?"+command)
    if response.status_code == 200:
        if response.json()["status"] == "OK":
            return response
        else:
            print("Error "+str(response.status_code)+" returned by "+response.url)
            print("Returned: "+response.text)
            exit(2)
    else:
        print("Error "+str(response.status_code)+" reading "+response.url)
        print("Returned: "+response.text)
        exit(2)

# Get a key in dictionary, return default value if not found
def getKey(key, dict, default = None):
    if key in dict:
        return dict[key]
    else:
        return default

# Return true if toTest valie is found in compiled regEx list 
def checkRegExIn(toTest, regExList):
    hits = []
    for regEx in regExList:
        result = re.match(regEx, toTest)
        if result:
            hits.append(result.re.pattern)
    return hits

#   *****************
#   *** Main code ***
#   *****************

# Set current working directory to this python file folder
currentPath = pathlib.Path(__file__).parent.resolve()
os.chdir(currentPath)

# Get this file name (w/o path & extension)
cdeFile = pathlib.Path(__file__).stem

# Load settings file
jsonSettingsFile = cdeFile+".json"
jsonSettings = loadDictionary(jsonSettingsFile)
if jsonSettings == None:
    print(F"Can't load settings from {jsonSettingsFile}")
    exit(2)

# Load settings in local variables
onCategories = getKey("onCategories", jsonSettings)
offCategories = getKey("offCategories", jsonSettings)
defineCategories = getKey("defineCategories", jsonSettings)
hiddenCategories = getKey("hiddenCategories", jsonSettings)
hiddenDevices = getKey("hiddenDevices", jsonSettings)
domoticzUrl = getKey("domoticzUrl", getKey("settings", jsonSettings), "http://127.0.0.1:8080/")
language = getKey("language", getKey("settings", jsonSettings), "EN")
removeLeadingPluginName = getKey("removeLeadingPluginName", getKey("settings", jsonSettings), removeLeadingPluginName)
keepDomoticzDeviceList = getKey("keepDomoticzDeviceList", getKey("settings", jsonSettings), keepDomoticzDeviceList)
showHiddenDevices = getKey("showHiddenDevices", getKey("settings", jsonSettings), showHiddenDevices)
showUsedDeviceOnly = getKey("showUsedDeviceOnly", getKey("settings", jsonSettings), showUsedDeviceOnly)
configVersion = getKey("configVersion", getKey("settings", jsonSettings), "V0.0.0")

# Check for config json file version
if configVersion < minimalConfigVersion:
    print(F"This script requires a {minimalConfigVersion} of {jsonSettingsFile}, but found a {configVersion} file")
    print(F"Please copy {jsonSettingsFile} from /examples folder, applying changes you may have done to it again")
    exit(2)

# Define counter types from 0 to 5
counterTypes = ["Energy", "Gas", "Water", "Counter", "Energy Generated", "Time"]

# Load devices regex from hiddenCategories
hiddenCategoriesRegEx = []
for item in hiddenCategories:
    regEx = re.compile(item, flags=re.IGNORECASE)
    hiddenCategoriesRegEx.append(regEx)

# Load devices regex from hiddenDevices
hiddenDevicesRegEx = []
for item in hiddenDevices:
    regEx = re.compile(item, flags=re.IGNORECASE)
    hiddenDevicesRegEx.append(regEx)

# Compose command to send depending on user needs
params = "type=devices"
if showHiddenDevices:
    params +="&displayhidden=1"

if showUsedDeviceOnly:
    params +="&used=true"

# Execute device list request
response = getResult(params)

# Save answer if required
if keepDomoticzDeviceList:
    with open(cdeFile+"DeviceList.json", "wt") as jsonStream:
        jsonStream.write(response.text)

# Initialize device list
deviceNameList = []
jsonDeviceList = []

# Scan all devices
for device in response.json()["result"]:
    deviceName = device["Name"]                                             # Load device name (text)
    rejectList = checkRegExIn(deviceName, hiddenDevicesRegEx)               # Check device name against hiddenDevices regEx compiled list
    if not rejectList:                                                      # Is device not in list of hidden one?
        deviceNameList.append(deviceName)                                       # Add device to list for futher check
        deviceHardwareName = device["HardwareName"]                         # Load hardware name (text)
        # If required, remove deviceHardwareName
        if removeLeadingPluginName and deviceName[:len(deviceHardwareName)+3] == deviceHardwareName+' - ':
            deviceName = deviceName[len(deviceHardwareName)+3:]
        deviceIdx  = device["idx"]                                          # Load device idx (number)
        deviceType = device["Type"]                                         # Load device type (text)
        deviceSubType = getKey("SubType", device, "")                       # Load device subtype (text)
        deviceSwitchType = getKey("SwitchType", device, "")                 # Load device type (text)
        deviceSwitchTypeVal = str(getKey("SwitchTypeVal", device, ""))      # Load device type (number)
        deviceLevelNames = getKey("LevelNames", device)                     # Load level names (text, separator |, base 64 encoded)
        # Define device category from type, subtype and switchtype
        if deviceSwitchType:
            deviceCategory = deviceSwitchType                               # Use switch type if given
        elif deviceType == "General" or deviceType == "P1 Smart Meter":
            deviceCategory = deviceSubType                                  # Use subtype for "General" and "P1 Smart Meter"
        elif (deviceSubType == "Counter Incremental" or deviceSubType == "Managed counter" or deviceType == "RFXMeter") and deviceSwitchTypeVal >= "0" and deviceSwitchTypeVal <="5":
            deviceCategory = counterTypes[int(deviceSwitchTypeVal)]         # Use counter type for "Counter Incremental", "Managed counter" or "RFXMeter"
        else:
            deviceCategory = deviceType                                     # Else use type
        # Transform "Color switch" type to "Color xxx" using switch type
        if deviceType == "Color Switch": deviceCategory = "Color " + deviceSwitchType
        # Use "Temp" for all categories starting with "Temp"
        if deviceCategory[:5] == "Temp ": deviceCategory = "Temp"
        # Use "Current" for all categories starting with "Current"
        if deviceCategory[:7] == "Current": deviceCategory = "Current"
        # Use "Door look" for all categories containing  "Door look"
        if "Door Lock" in deviceCategory: deviceCategory = "Door Lock"
        # Change "Thermostat" to "Setpoint" (which replaces "Thermostat" from already few versions)
        if deviceCategory == "Thermostat" : deviceCategory = "Setpoint"
        # Use "Blinds Percentage" for all categories containing  "Blinds Percentage"
        if "Blinds Percentage" in deviceCategory:
            deviceCategory = "Blinds Percentage"
        # Use "Blinds" for all categories containing  "Blinds" (and not "Blinds Percentage")
        elif "Blinds" in deviceCategory:
            deviceCategory = "Blinds"
        # Set category to "SecurityPanel" if subtype is "Security Panel"
        if deviceSubType == "Security Pannel": category = "SecurityPanel"
        # Convert level names if existing
        selectorValues = ""
        if deviceLevelNames:
            deviceLevelNamesList = base64.b64decode(deviceLevelNames.encode("ascii")).decode("UTF8").split("|")
            deviceMappingLevel = 0
            for level in deviceLevelNamesList:
                if selectorValues:
                    selectorValues += ", "
                selectorValues += "\""+level+"\": "+str(deviceMappingLevel)
                deviceMappingLevel += 10
        # Compute allow from configuration lists
        allowCommands = "\"allow\": [\"cdeShow\""
        # Add other  allowed types
        if deviceCategory in onCategories:
                allowCommands += ", \"cdeOn\""
        if deviceCategory in offCategories:
                allowCommands += ", \"cdeOff\""
        if deviceCategory in defineCategories:
                allowCommands += ", \"cdeSet\""
                defineParams = ", " + str(getKey(deviceCategory, defineCategories)).replace("\'","\"")[1:-1].replace("\"[[selectorValues]]\"", "{"+selectorValues+"}")
        else:
                defineParams = ""
        # If category in hiddenCategories, don't write device to list
        rejectList = checkRegExIn(deviceCategory,hiddenCategories)
        if not rejectList:
            # Add name, idx, category, allow & define parameters
            jsonDeviceList.append("\t\t\""+str(deviceName)+"\": {\"index\": "+str(deviceIdx)+", \"category\": \""+str(deviceCategory)+"\", "+str(allowCommands)+"]"+defineParams+"}")
        else:
            print(F"Ignoring category {deviceCategory} for {deviceName}, rejected by {rejectList}")
    else:
            print(F"Ignoring device {deviceName}, rejected by {rejectList}")

# Sort json device list
jsonDeviceList.sort()
deviceList = ""
for item in jsonDeviceList:
    if deviceList:
        deviceList += ",\n"
    deviceList += item

# Load settings to be inserted into JSON
jsonSettingsList = ""
for (key, value) in getKey("settings", jsonSettings).items():
    if jsonSettingsList:
        jsonSettingsList += ",\n"
    jsonSettingsList += "\t\t\"" + key + "\": "
    if type(value).__name__ in ["int", "float", "bool"]:
        jsonSettingsList +=  str(value).lower()
    else:
        jsonSettingsList += "\"" + value + "\""

# Compose template name
templateFile = "smsTables"+language+".template"

# Read template file
with open(templateFile, "rb") as templateStream:
    templateData = templateStream.read().decode("utf-8")

# Extract template version
templateVersion = getKey("templateVersion", getKey("settings", json.loads(templateData)), "V0.0.0")

# Check template version
if templateVersion < minimalTemplateVersion:
    print(F"This script requires a {minimalTemplateVersion} of {templateFile}, but found a {templateVersion} file")
    print(F"Please copy {templateFile} from /examples folder, applying changes you may have done to it again")
    exit(2)

# Write json result file
jsonFile = "smsTables.json"
with open(jsonFile, "wt", encoding='utf-8') as jsonStream:
        jsonStream.write(templateData.replace("\"replaceMeBy\": \"settings\"", jsonSettingsList).replace("\"replaceMeBy\": \"devices\"", deviceList))

# Check for ambiguous device names
for deviceName in deviceNameList:
    for deviceToCheck in deviceNameList:
        if deviceToCheck == deviceName[:len(deviceToCheck)] and deviceToCheck != deviceName:
            print("\""+deviceName+"\" share root with \""+deviceToCheck+"\" and will hide it")
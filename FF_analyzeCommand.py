"""
This code analyzes a command and tries to decode a command against a given list.

It is both adapted to get French or English SMS messages to remotely manage automation system.

General command organization is:
    [command] [device name] [value to set].

For example:
    For French:  "allume la lampe de la cuisine", "ouvre le volet du salon", "règle la consigne de la clim du séjour sur 21", ...
    For English: "turn kitchen light on", "open living room shutter", "set living room air conditioning to 21", ...

Code allows to work with UTF-8 data. You may optionally restrict comparison and output to 7 bits ASCII equivalent to help processing.

More details on README.md

Author: Flying Domotic
License: GNU GPL V3
"""

import pathlib
import os
import json
from re import A, match, search
from typing_extensions import get_overloads
import unidecode

class FF_analyzeCommand:
    # Class initialization 
    def __init__(self):
        self.fileVersion = "2.0.0"                          # File version
        self.errorSeen = False;                             # Do we seen an error ?
        self.convertUtf8ToAscii7Input = True;               # Convert input to Ascii7?
        self.convertUtf8ToAscii7Output = False;             # Convert saved output to Ascii7?
        self.firstErrorMessage = ""                         # First error message seen
        self.allMessages = ""                               # All messages to be printed
        self.ignoresList = []                               # List of keywords to be ignored
        self.commandValuesDict = {}                         # Dictionary of commandValues
        self.commandsDict = {}                              # Dictionary of commands
        self.devicesDict = {}                               # Dictionary of devices
        self.checkFile = ""                                 # File being scanned
        self.checkPhase = ""                                # Scan phase
        self.command = ""                                   # Command
        self.commandValue = 0                               # Command value in numeric format
        self.commandValueText = ""                          # Command value in text format
        self.deviceName = ""                                # Device name
        self.deviceId = 0                                   # DeviceId
        self.deviceIdName = ""                              # Name of deviceId
        self.deviceCategory = ""                            # Device category
        self.valueToSetType = None                          # Value to set type ()
        self.valueToSet = None                              # Value to set
        self.valueToSetOriginal = None                      # Original value to set (for mapping)
        self.setBy = None                                   # Value to be set by 'user' or 'plugIn'

    # Prints an error message, saving it and setting error flag
    def printError(self, message):
        self.allMessages += (self.utf8ToAscii7(message) if self.convertUtf8ToAscii7Output else message)+"\r\n"
        # Save message under required format
        if self.firstErrorMessage == "":
            self.firstErrorMessage = self.utf8ToAscii7(message) if self.convertUtf8ToAscii7Output else message
        self.errorSeen = True

    # Prints an info message
    def printInfo(self, message):
        self.allMessages += (self.utf8ToAscii7(message) if self.convertUtf8ToAscii7Output else message)+"\r\n"

    # Load a dictionary to a file
    def loadDictionary(self, file):
        # Print duplicates on dictionary
        def dict_print_duplicates(ordered_pairs):
            d = {}
            for k, v in ordered_pairs:
                if k in d:
                    print (F"Warning: You have duplicate definition of >{k}< in JSON declaration")
                    print (F"    {d[k]}")
                    print (F"    {v}")
                d[k] = v
            return d
        if os.path.exists(file):
            with open(file, encoding="UTF-8") as f:
                try:
                    return json.loads(f.read(), object_pairs_hook=dict_print_duplicates)
                except Exception as e:
                    self.printError(F"{e} when loading {file}")
                    return None
        else:
            return {}

    # Filter a dictionary given an item value
    def filterDictionary(self, dict, selectKey, selectValue, newDict):
        for (key, value) in dict.items():
            selectKeyValue = self.getValue(value, selectKey)
            if type(selectKeyValue).__name__ in ["list", "dict"]:
                if selectValue in selectKeyValue:
                    newDict[key] = value
            else:
                if selectValue == selectKeyValue:
                    newDict[key] = value
    
    # Returns a dictionary value giving a key or default value if not existing
    def getValue(self, dict, key, default=None):
        if dict != None:
            if key in dict:
                return dict[key]
        return default

    # Returns a dictionary value giving a couple of keys or default value if not existing
    def getValue2(self, dict, key1, key2, default=None):
        if dict != None:
            if key1 in dict and key2 in dict[key1]:
                return dict[key1][key2]
        return default

    # Converts an UTF-8 string to ASCII 7 bits equivalent (remove accents and more)
    def utf8ToAscii7(self, variable):
        if type(variable).__name__ == "str":
            return unidecode.unidecode(variable)
        return variable

    # Compare 2 values on shortest size with minimal length and eventual UTF-8 to ASCII 7 conversion
    #   at user's disposal to make external tests with same behavior than this function
    def compare(self, value1, value2, minLength=-1):
        val1 = self.convertUserData(value1)
        val2 = self.convertUserData(value2)
        lenToTest = len(val1) if len(val1) <= len(val2) else len(val2)
        if minLength >= 1:
            if minLength > lenToTest: lenToTest = minLength

        return str(val1[:lenToTest]).lower() == str(val2[:lenToTest]).lower()

    # Converts data from UTF-8 to ASCII 7 if requested by user
    def convertUserData(self, variable):
        if self.convertUtf8ToAscii7Input:
            # Data to convert could be string, list of string or dict
            if type(variable).__name__ == "list":
                # This is list of strings
                newList = []
                for item in variable:
                    newList.append(self.utf8ToAscii7(item).lower())
                return newList
            if type(variable).__name__ == "dict":
                # This is dict, get keys
                newList = []
                for item in variable.keys():
                    newList.append(self.utf8ToAscii7(item).lower())
                return newList
            elif type(variable).__name__ == "str":
                # This is a string
                return self.utf8ToAscii7(variable).lower()
        # No conversion needed or type not list or string, return original value
        return variable

    # Compare 2 values, puts an error message and returns false if not equal, true else
    def compareValue(self, msg, valueIs, valueShouldBe, context=None):
        isOk = False
        if type(valueShouldBe).__name__ in ["list","dict"]:
            isOk = (self.convertUserData(valueIs) in self.convertUserData(valueShouldBe))
        else:
            isOk = (self.convertUserData(valueIs) == self.convertUserData(valueShouldBe))
        if not isOk:
            self.printError(F"Error analyzing {self.checkFile}, when {self.checkPhase}: {msg} is {valueIs}, should be "+str(valueShouldBe.keys()).replace("dict_keys(","")[:-1] if type(valueShouldBe).__name__ == "dict" else str(valueShouldBe))
            if context != None:
                self.printInfo(F"Context is {context}")
            return False
        return True

    # Compare 2 values, puts an error message and returns false if equal, true else
    def notInIgnoreList(self, msg, valueIs, context=None):
        isOk = (self.convertUserData(valueIs) not in self.ignoresList)
        if not isOk:
            self.printError(F"Error analyzing {self.checkFile} when {self.checkPhase}: {msg} should not be in ignore list")
            if context != None:
                self.printInfo(F"Context is {context}")
            return False
        return True

    # Compare 2 values, puts an error message and returns false if equal, true else
    def compareNotValue(self, msg, valueIs, valueShouldBe, context=None):
        isOk = False
        if type(valueShouldBe).__name__ in ["list","dict"]:
            isOk = (self.convertUserData(valueIs) not in self.convertUserData(valueShouldBe))
        else:
            isOk = (self.convertUserData(valueIs) != self.convertUserData(valueShouldBe))
        if not isOk:
            self.printError(F"Error analyzing {self.checkFile}, when {self.checkPhase}: {msg} should not be "+str(valueShouldBe.keys()).replace("dict_keys(","")[:-1] if type(valueShouldBe).__name__ == "dict" else str(valueShouldBe))
            if context != None:
                self.printInfo(F"Context is {context}")
            return False
        return True

    # Compare 2 types, puts an error message and returns false if not equal, true else
    def compareType(self, msg, variableIs, typeShouldBe, context = None):
        isOk = False
        if type(typeShouldBe).__name__ in ["list", "dict"]:
            isOk = (type(variableIs).__name__ in typeShouldBe)
        else:
            isOk = (type(variableIs).__name__ == typeShouldBe)
        if not isOk:
            self.printError(F"Error analyzing {self.checkFile}, when {self.checkPhase}: {msg} ({variableIs}) is {type(variableIs).__name__}, should be {typeShouldBe}")
            if context:
                self.printInfo(F"Context is {context}")
            return False
        return True

    # Find keyword in dictionary, checking for multiple matches
    #   List can contain values with spaces. In this case, as many keywords as word count in list element are compared
    def findInDict(self, keywords, startPtr, dict, text):
        previousMatchingList = []
        words = []
        # Remaps keywords from 0
        for ptr in range(startPtr, len(keywords)):
            words.append(keywords[ptr])
        # Scan each device, word by word (to be able to limit list of displayed possibilities when dupplicates found)
        for wordPtr in range(0,len(words)):
            # List of matching devices
        matchingList = []
        # For each item in search list
        for item in dict.keys():
            # Split item using space as separator
            itemParts = item.split(" ")
            matchFound = True
            # For each keyword in item
                for ptr in range(0, wordPtr+1):
                # Check that we're still within keyword count
                    if len(itemParts) <= ptr:
                    # No, this is not correct
                    matchFound = False
                else:
                    # Are the keyword chars same as item?
                        if self.convertUserData(itemParts[ptr][:len(words[ptr])]) != self.convertUserData(words[ptr]):
                        # No, this is not correct
                        matchFound = False
            # If we got a match
            if matchFound:
                # Add item to the list
                matchingList.append(item)
            # Here, we scanned all devices
        if len(matchingList) == 0:
                # No match found
                if len(previousMatchingList):
                    # Previous round found dupplicates, print them
                    self.printError(F"{keywords[startPtr:]} is an ambiguous {text}, could be {previousMatchingList}")
                else:
                    # Previous round found nothing, list all
            self.printError(F"{keywords[startPtr:]} is not a known {text}, use "+str(dict.keys()).replace("dict_keys(","")[:-1])
            return ""
            elif len(matchingList) == 1:
                # We found an exact match, return it
                return matchingList[0]
            # Save matching list for next round
            previousMatchingList = matchingList.copy()
        # We're at end of scan
        if len(previousMatchingList):
            # Previous round found dupplicates, print them
            self.printError(F"{keywords[startPtr:]} is an ambiguous {text}, could be {previousMatchingList}")
        else:
            # Previous round found nothing, list all
            self.printError(F"{keywords[startPtr:]} is not a known {text}, use "+str(dict.keys()).replace("dict_keys(","")[:-1])
            return ""

    # Lookup keyword in dictionary, stopping on first match
    #   List can contain values with spaces. In this case, as many keywords as word count in list element are compared
    def lookupInDict(self, keywords, startPtr, dict):
        matchingList = []
        # For each item in search list
        for item in dict.keys():
            # Split item using space as separator
            itemParts = item.split(" ")
            matchFound = True
            # For each keyword in item
            for ptr in range(0, len(itemParts)):
                # Check that we're still within keyword count
                if len(keywords) <= startPtr + ptr:
                    # No, this is not correct
                    matchFound = False
                else:
                    # Are the keyword chars same as item?
                    if self.convertUserData(itemParts[ptr][:len(keywords[startPtr+ptr])]) != self.convertUserData(keywords[startPtr+ptr]):
                        # No, this is not correct
                        matchFound = False
            # If we got a match
            if matchFound:
                # Return item
                return item
        return ""

    def loadData(self, fileName):
        # Load JSON file
        self.checkFile = pathlib.Path(fileName).name
        self.checkPhase = "checking file"
        decodeData = self.loadDictionary(fileName)

        if decodeData:
            ### Checking  decodeData (dict)
            if self.compareType("decodeData type", decodeData, "dict"):
                ### Checking "ignores": ["of", "the", ...]
                self.checkPhase = "checking ignores"
                self.ignoresList = self.getValue(decodeData,"ignores")
                # Extract all "ignores" (list)
                if self.compareType("self.ignoresList type", self.ignoresList, "list"):
                    pass
            ### Checking "commandValues": {	"cdeOn":{"codeValue":1}, ...}
            self.checkPhase = "checking command values"
            self.commandValuesDict =  self.getValue(decodeData,"commandValues")
            # Extract all "commandValues" (dict)
            if self.compareType("commandValuesDict type", self.commandValuesDict, "dict"):
                # For each item in self.commandValuesDict
                for key in self.commandValuesDict.keys():
                    # Key should not be in ignore list
                    if self.notInIgnoreList("key", key):
                        # Check codeValue (dict)
                        codeValueItem = self.commandValuesDict[key]
                        if self.compareType("codeValueItem type", codeValueItem, "dict"):
                            # Get the "codeValue" (int)
                            codeValue = self.getValue(codeValueItem, "codeValue")
                            if self.compareType("codeValue type", codeValue, "int", codeValueItem):
                                pass

            ### Checking "commands": {"turn":{"commandValue":"cdeSet"}, ...}
            self.checkPhase = "checking commands"
            # Extract all "commands" list
            self.commandsDict =  self.getValue(decodeData,"commands")
            if self.compareType("commandList type", self.commandsDict, "dict"):
                # For each item in self.commandsDict
                for key in self.commandsDict.keys():
                    # Key should not be in ignore list
                    if self.notInIgnoreList("key", key):
                        commandItem = self.commandsDict[key]
                        if self.compareType("commandItem type", commandItem, "dict"):
                            # Get the first "command"
                            commandCommandValue = self.getValue(commandItem, "commandValue")
                            # Check command keyword
                            if self.compareType("commandCommandValue type", commandCommandValue, "str", commandItem):
                                # Value should be in self.commandValuesDict
                                if self.compareValue("command commandValue", commandCommandValue , self.commandValuesDict, commandItem):
                                    pass

            ### Checking "devices": {"kitchen target temperature":{"index":86, "category":"Setpoint", "allow":["cdeShow","cdeSet"], "setType": "setPoint", "minValue": -40, "maxValue": 100}, ...}
            self.checkPhase = "checking devices"
            # Extract all "devices"
            self.devicesDict =  self.getValue(decodeData,"devices")
            if self.compareType("self.devicesDict type", self.devicesDict, "dict"):
                # For each item in self.devicesDict
                for key in self.devicesDict.keys():
                    deviceItem = self.devicesDict[key]
                    if self.compareType("deviceItem type", deviceItem, "dict"):
                        # Extract index
                        deviceIndex = self.getValue(deviceItem, "index")
                        if self.compareType("device index", deviceIndex, ["str", "int"]):
                            # Index should not be empty or zero
                            self.compareNotValue("device index", deviceIndex, "", deviceItem)
                            self.compareNotValue("device index", deviceIndex, 0, deviceItem)
                        # Extract category
                        deviceCategory = self.getValue(deviceItem, "category")
                        if self.compareType("device category", deviceCategory, "str"):
                            pass
                        # Extract allowed commands and check them
                        deviceAllowedCommands = self.getValue(deviceItem, "allow")
                        if self.compareType("device allowed commands", deviceAllowedCommands, ["str","list"]):
                            pass
                            # Does the device have one commandValue with a set attribute?
                                    commandSet = False
                            # Scan all allowed command values
                            for item in deviceAllowedCommands:
                                        # Does this commandValue have the set flag set?
                                        if self.getValue2(self.commandValuesDict, item, "set", False):
                                            # Yes, set flag
                                            commandSet = True
                                            break
                                    # Check other elements giving commandSet flag
                                    if commandSet:
                                        # Command has a set flag, get mandatory setType value
                                self.valueToSetType = self.getValue(deviceItem, "setType")
                                        # Check setType value as string
                                if self.compareType("setType type", self.valueToSetType, "str", deviceItem):
                                            # Check for valid setType given
                                            if self.compareValue("setType", self.valueToSetType, ['level','setPoint', 'integer', 'float','string']):
                                                pass
                                        # Set min/max value depending on setType
                                        if self.valueToSetType == 'level':
                                            minValue = 0
                                            maxValue = 100
                                        else:
                                            minValue = None
                                            maxValue = None
                                        # Set authorized data type(s) depending on setType
                                        if self.valueToSetType == 'level' or self.valueToSetType == 'integer':
                                            allowedDataTypes = 'int'
                                        elif self.valueToSetType == 'float' or self.valueToSetType == 'setPoint':
                                            allowedDataTypes = ['int', 'float']
                                        else:
                                            allowedDataTypes = 'str'
                                # Scan all items in device item
                                for item in deviceItem.keys():
                                                # Get item value
                                        itemValue = deviceItem[item]
                                                if item == "mapping":
                                            deviceMap = self.getValue(deviceItem, "mapping")
                                                    # This should be a list of mapping value (dict)
                                            if self.compareType("deviceMap type", deviceMap, "dict", deviceItem):
                                                        ## Check each value type against authorized ones
                                                        for mappingKey in itemValue.keys():
                                                    if self.compareType("mapping value type", itemValue[mappingKey], allowedDataTypes, deviceItem):
                                                                pass
                                                elif item == "minValue":
                                            if self.compareType("minValue type", itemValue, allowedDataTypes, deviceItem):
                                                        minValue = itemValue
                                                elif item == "maxValue":
                                            if self.compareType("minValue type", itemValue, allowedDataTypes, deviceItem):
                                                        maxValue = itemValue
                                                elif item == "list":
                                                    # Check type as list
                                            if self.compareType("list type", itemValue, "list", deviceItem):
                                                        # Check each item in list
                                                        for item in itemValue:
                                                    if self.compareType("list value type", item, allowedDataTypes, deviceItem):
                                                                pass
                                                elif item == "setBy":
                                                    if self.compareValue("setBy", itemValue, ['plugIn', 'user']):
                                                        pass
                                        elif item not in ['index', 'category', 'allow', 'setType']:
                                                    # And unknown item has been specified
                                            self.printError(F"Can't understand {item} in {deviceItem} for {key}")
                                        # Check for min/max values
                                        if minValue != None and maxValue != None:
                                            # Min should be <= to max
                                            if minValue > minValue:
                                                self.printError(F"minValue ({minValue}) should be less or equal to maxValue ({maxValue})")
                                    else:
            self.printError(F"Can't load {fileName}")
        # Set final check status (first value is short error message, second one all detected errors)
        if self.errorSeen:
            return "Error detected, please check "+fileName+" file!", self.allMessages
        else:
            return "", self.allMessages

    def analyzeCommand(self, givenCommand):
        # Init error seen and last message
        self.errorSeen = False
        self.firstErrorMessage = ""
        self.allMessages= ""
        self.command = ""                                   # Command
        self.commandValue = 0                               # Command value in numeric format
        self.commandValueText = ""                          # Command value in text format
        self.deviceName = ""                                # Device name
        self.deviceId = 0                                   # DeviceId
        self.deviceIdName = ""                              # Name of deviceId
        self.valueToSet = None                              # Value to set
        self.valueToSetType = None                          # Value to set type
        self.valueToSetOriginal = None                      # Original Value to set (for mapping)
        self.setBy = None                                   # Value to be set by 'user' or 'plugIn'

        # Split each word of message, replacing tabs by spaces  
        keywords = givenCommand.replace("\t"," ").split(" ")

        # Remove words to ignore
        for ptr in range(len(keywords)):
            if keywords[ptr] in self.ignoresList:
                keywords[ptr] = ""

        # Rebuild command and clean leading/trailing spaces
        cleanCommand = " ".join(keywords).strip()

        # Remove double spaces
        while cleanCommand.find("  ") != -1:
            cleanCommand = cleanCommand.replace("  ", " ")
        
        # Split each word of cleaned message
        keywords = cleanCommand.split(" ")

        # Isolate command in first keyword
        keywordIndex = 0
        self.command = self.findInDict(keywords, keywordIndex, self.commandsDict, "command")
        if self.command != "":
            ##self.printInfo(F"Command is {self.command}")
            # move index into keywords
            keywordIndex += len(self.command.split(" "))
            # Does the device name
            filteredDevicesDict = dict()
            self.filterDictionary(self.devicesDict, "allow", self.getValue2(self.commandsDict, self.command, "commandValue"), filteredDevicesDict)
            self.deviceName = self.findInDict(keywords, keywordIndex, filteredDevicesDict, "device")
            if self.deviceName != "":
                keywordIndex += len(self.deviceName.split(" "))
                # Get device data
                deviceCategory = self.getValue2(self.devicesDict, self.deviceName, "category","")
                deviceAllowedCommands = self.getValue2(self.devicesDict, self.deviceName, "allow")
                ##self.printInfo(F"{self.command} command allows {deviceAllowedCommands}")
                if not deviceAllowedCommands:
                    self.printError(F"Can't find {self.deviceName} allowed commands...")
                    else:
                        # Get command commandValue
                        commandCommandValue = self.getValue2(self.commandsDict, self.command, "commandValue")
                        if not commandCommandValue:
                            self.printError(F"Can't find {self.command} command commandValue...")
                        else:
                            ##self.printInfo(F"{self.command} command is {commandCommandValue}")
                        if commandCommandValue not in deviceAllowedCommands:
                            self.printError(F"Can't do command {self.command} on device {self.deviceName}")
                            else:
                                    # Is command set enabled?
                                    commandSet = self.getValue2(self.commandValuesDict, commandCommandValue, "set", False)
                                    ##self.printInfo(F"{command} set is {commandSet}")
                                    # Is this a set command?
                                    if commandSet:
                                        # Extract all remaining keywords in value to set
                                        self.valueToSet = ""
                                        for ptr in range(keywordIndex, len(keywords)):
                                            self.valueToSet += keywords[ptr]+ " "
                                        self.valueToSet = self.valueToSet.strip()
                                        ##self.printInfo(F"Value to set is {self.valueToSet}")
                                        # Do we have a value to set?
                                        if self.valueToSet != "":
                                            # Extract setType value
                                    self.valueToSetType = self.getValue2(self.devicesDict, self.deviceName, "setType")
                                    # Do we have mapping associated with device?
                                    deviceMapping = self.getValue2(self.devicesDict, self.deviceName, "mapping")
                                    if deviceMapping:
                                        # Substitute first value to set to mapped value
                                        self.valueToSetOriginal = self.findInDict(keywords, keywordIndex, deviceMapping, "mapping")
                                                if self.valueToSetOriginal != "":
                                                    # Load remapped value
                                            self.valueToSet = self.getValue(deviceMapping, self.valueToSetOriginal)
                                                    keywordIndex += len(self.valueToSetOriginal)
                                                    # Do we have remaining keywords?
                                                    if keywordIndex + 1 < len(keywords):
                                                        self.printError(F"Can't understand {keywords[keywordIndex:]} after {self.valueToSet}")
                                    # Do we have a list associated with device?
                                    deviceList = self.getValue2(self.devicesDict, self.deviceName, "list")
                                    if deviceList and self.compareValue("value", self.valueToSet, deviceList, givenCommand):
                                                pass
                                            # Do we have a minValue or maxValue?
                                    deviceMinValue = self.getValue2(self.devicesDict, self.deviceName, "minValue", None)
                                    deviceMaxValue = self.getValue2(self.devicesDict, self.deviceName, "maxValue")
                                            # Set authorized data type(s) depending on setType
                                            if self.valueToSetType == 'level':
                                                try:
                                                    dummy = int(self.valueToSet)
                                                except ValueError:
                                                    self.printError(F"({self.valueToSet}) is not a valid number")
                                                    return
                                        if deviceMinValue == None:
                                            deviceMinValue = 0
                                        if deviceMaxValue == None:
                                            deviceMaxValue = 100
                                        if dummy < int(deviceMinValue):
                                            self.printError(F"Given value ({dummy}) should not be less than {deviceMinValue}")
                                                    return
                                        if dummy > int(deviceMaxValue):
                                            self.printError(F"Given value ({dummy}) should not be greater than {deviceMaxValue}")
                                                    return
                                            elif self.valueToSetType == 'integer':
                                                try:
                                                    dummy = int(self.valueToSet)
                                                except ValueError:
                                                    self.printError(F"({self.valueToSet}) is not a valid number")
                                                    return
                                        if deviceMinValue != None and dummy < int(deviceMinValue):
                                            self.printError(F"Given value ({dummy}) should not be less than {deviceMinValue}")
                                                    return
                                        if deviceMaxValue != None and dummy > int(deviceMaxValue):
                                            self.printError(F"Given value ({dummy}) should not be greater than {deviceMaxValue}")
                                                    return
                                            elif self.valueToSetType == 'float' or self.valueToSetType == 'setPoint':
                                                try:
                                                    dummy = float(self.valueToSet)
                                                except ValueError:
                                                    self.printError(F"({self.valueToSet}) is not a valid floating point")
                                                    return
                                        if deviceMinValue != None and dummy < float(deviceMinValue):
                                            self.printError(F"Given value ({dummy}) should not be less than {deviceMinValue}")
                                                    return
                                        if deviceMaxValue != None and dummy > float(deviceMaxValue):
                                            self.printError(F"Given value ({dummy}) should not be greater than {deviceMaxValue}")
                                                    return
                                            else:
                                        if deviceMinValue != None and self.valueToSet < deviceMinValue:
                                            self.printError(F"Given value ({self.valueToSet}) should not be less than {deviceMinValue}")
                                                    return
                                        if deviceMaxValue != None and self.valueToSet > deviceMaxValue:
                                            self.printError(F"Given value ({self.valueToSet}) should not be greater than {deviceMaxValue}")
                                                    return
                                            # Load setBy
                                    self.setBy = self.getValue2(self.devicesDict, self.deviceName, "setBy", "plugIn")
                                        else:
                                            self.printError("Value to set is missing")
                                    else:
                                        # Do we have an available keyword?
                                        if keywordIndex < len(keywords):
                                    self.printError(F"Can't understand {keywords[keywordIndex:]} after {self.deviceName}")
                                    if not self.errorSeen:
                                self.deviceId = self.getValue2(self.devicesDict,self.deviceName, "index")
                                self.deviceIdName = self.getValue2(self.devicesDict,self.deviceName, "name",self.deviceName)
                                        self.commandValue = self.getValue2(self.commandValuesDict,commandCommandValue, "codeValue")
                                        self.commandValueText = commandCommandValue
        return self.firstErrorMessage, self.allMessages

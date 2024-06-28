#!/usr/bin/python3
fileVersion = "1.0.0"                                       # File version

import pathlib
import os
from FF_analyzeCommand import FF_analyzeCommand, get_overloads

#   *****************
#   *** Main code ***
#   ****************

# Set current working directory to this python file folder
currentPath = pathlib.Path(__file__).parent.resolve()
os.chdir(currentPath)

# Get this file name (w/o path & extension)
cdeFile = pathlib.Path(__file__).stem

decodeFile = os.path.join(currentPath, "smsTables.json")
analyzer = FF_analyzeCommand()

errorText, messages = analyzer.loadData(decodeFile)
print("LoadData status: "+(errorText if errorText != "" else "Ok"))
if messages:
    print(messages)
if errorText:
    exit()

content = []
for device in analyzer.devicesDict.keys():
    deviceName = analyzer.getValue2(analyzer.devicesDict, device, "name", device)
    deviceCommandValues = analyzer.getValue2(analyzer.devicesDict, device, "allow")
    deviceClassMappings = analyzer.getValue2(analyzer.devicesDict, device, "mapping")
    deviceCommands = ""
    for command in analyzer.commandsDict:
    commandValue = analyzer.getValue2(analyzer.commandsDict, command, "commandValue")
    if commandValue in deviceCommandValues:
            deviceCommands += "/" + command
    setValues = ""
    if deviceClassMappings:
        for value in deviceClassMappings.keys():
            setValues += "/" + value

    minValue = analyzer.getValue2(analyzer.devicesDict, device, "minValue")
    maxValue = analyzer.getValue2(analyzer.devicesDict, device, "maxValue")
    setValueMinMax = ""
    if minValue != None:
        if maxValue != None:
            setValues += F"/{minValue}:{maxValue}"
        else:
            setValues += F"/>={minValue}"
    else:
        if maxValue != None:
            setValues = F"/<={maxValue}"
    
    if setValues:
        setValues = F" [{setValues[1:]}]"

    content.append(deviceName+"\t["+deviceCommands[1:]+"] "+device.lower()+setValues)

content.sort()
with open("config.txt", "wt") as outFile:
    for line in content:
        outFile.write(line+"\n")

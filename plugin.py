# FF_SmsServer plug-in for Domoticz / Plug-in FF_SmsServer pour Domoticz 
#
#   This plug-in allows to pass commands received by SMS through a FF_SmsServer hardware to Domoticz and execute them.
#       It's able to send you back an SMS the status of Domoticz devices you want to expose, as well as changing their value. remotely.
#       It was originally designed to get (French) SMS messages to remotely manage automation system.
#
#   General command organization is: [command] [device type] [device name] [value to set].
#
#   For example: "allume la lampe de la cuisine", "ouvre le volet du salon", "règle la consigne de la clim du séjour sur 21", ...
#
#   Again, this structure is French oriented, and should be adapted to other languages/grammar if needed.
#
#   For example, to turn a bulb on, French is "Allume lampe cuisine", word to word translated into "turn on bulb kitchen",
#       while English people would better say "turn kitchen bulb on".
#
#   A new version could implement different grammars, users' requests may speed-up the process ;-)
#
#   Code allows to work with UTF-8 data. You may optionally restrict comparison and/or output to 7 bits ASCII equivalent to help processing.
#
#   More details on README.md
#
#   Flying Domotic -  https://github.com/FlyingDomotic/domoticz-FF_SmsServer-plugin.git
"""
<plugin key="FF_SmsServer" name="FF_SmsServer with LAN interface" author="Flying Domotic" version="1.0.0" externallink="https://github.com/FlyingDomoticz/domotic-ff_smsserver-plugin/">
    <description>
      FF_SmsServer plug-in<br/><br/>
      Set/display state of Domoticz devices through SMS<br/>
    </description>
    <params>
        <param field="Address" label="MQTT Server address" width="300px" required="true" default="127.0.0.1"/>
        <param field="Port" label="Port" width="300px" required="true" default="1883"/>
        <param field="Username" label="Username" width="300px"/>
        <param field="Password" label="Password" width="300px" password="true"/>
        <param field="Mode1" label="JSON mapping file to use" width="300px" required="true" default="smsTables.json"/>
        <param field="Mode6" label="Debug" width="100px">
            <options>
                <option label="Extra verbose" value="Verbose+"/>
                <option label="Verbose" value="Verbose"/>
                <option label="Normal" value="Debug"/>
                <option label="None" value="Normal" default="true"/>
            </options>
        </param>
    </params>
</plugin>
"""
from sys import settrace
import Domoticz
from datetime import datetime
from itertools import count, filterfalse
import typing_extensions
import json
import time
import traceback
from FF_analyzeCommand import FF_analyzeCommand

# Local MQTT client class
class MqttClient:
    Address = ""                    # IP address of MQTT server
    Port = ""                       # Port of MQTT server
    mqttConn = None                 # MQTT connection object
    mqttConnectedCb = None          # MQTT connection callback
    mqttDisconnectedCb = None       # MQTT disconnection callback
    mqttPublishCb = None            # MQTT publish callback
    lwtTopic = ""                   # Last Will Topic
    lwtData = ""                    # Last Will data
    analyzer = None                 # Command analyzer object
    isConnected = False             # MQTT connected flag

    # Class initialization: save parameters and open connection
    def __init__(self, destination, port, mqttConnectedCb, mqttDisconnectedCb, mqttPublishCb, mqttSubackCb, lwtTopic = None, lwtData = None):
        Domoticz.Debug("MqttClient::__init__")
        self.Address = destination
        self.Port = port
        self.mqttConnectedCb = mqttConnectedCb
        self.mqttDisconnectedCb = mqttDisconnectedCb
        self.mqttPublishCb = mqttPublishCb
        self.mqttSubackCb = mqttSubackCb
        self.lwtTopic = lwtTopic
        self.lwtData = lwtData
        self.isConnected = False
        self.Open()

    # Class default string
    def __str__(self):
        Domoticz.Debug("MqttClient::__str__")
        if (self.mqttConn != None):
            return str(self.mqttConn)
        else:
            return "None"

    # Open MQTT connection at TCP level
    def Open(self):
        Domoticz.Debug("MqttClient::Open")
        if (self.mqttConn != None):
            self.Close()
        self.isConnected = False
        self.mqttConn = Domoticz.Connection(Name="MQTT", Transport="TCP/IP", Protocol="MQTT", Address=self.Address, Port=self.Port)
        self.mqttConn.Connect()

    # Connect to MQTT server (or open connction if not active)
    def Connect(self):
        Domoticz.Debug("MqttClient::Connect")
        if (self.mqttConn == None):
            self.Open()
        else:
            ID = 'Domoticz_'+Parameters['Key']+'_'+str(Parameters['HardwareID'])+'_'+str(int(time.time()))
            if self.lwtTopic:
                Domoticz.Log(F"MQTT Connect ID: {ID}, lwtTopic: {self.lwtTopic}, lwtData = {self.lwtData}")
                self.mqttConn.Send({'Verb': 'CONNECT', 'ID': ID, 'WillTopic': self.lwtTopic, 'WillQoS': 0, 'WillRetain': 1, 'WillPayload': self.lwtData})
            else:
                Domoticz.Log(F"MQTT Connect ID: {ID}")
                self.mqttConn.Send({'Verb': 'CONNECT', 'ID': ID})

    # Send a MQTT Ping message
    def Ping(self):
        #Domoticz.Debug("MqttClient::Ping")
        if (self.mqttConn == None or not self.isConnected):
            self.Open()
        else:
            self.mqttConn.Send({'Verb': 'PING'})

    #  Publish a payload on a given topic (and retain flag)
    def Publish(self, topic, payload, retain = 0):
        Domoticz.Debug(F"MqttClient::Publish {topic} ({payload})")
        if (self.mqttConn == None or not self.isConnected):
            self.Open()
        else:
            self.mqttConn.Send({'Verb': 'PUBLISH', 'Topic': topic, 'Payload': bytearray(payload, 'utf-8'), 'Retain': retain})

    # Subscribe to topic(s)
    def Subscribe(self, topics):
        Domoticz.Debug("MqttClient::Subscribe")
        subscriptionlist = []
        for topic in topics:
            subscriptionlist.append({'Topic':topic, 'QoS':0})
        if (self.mqttConn == None or not self.isConnected):
            self.Open()
        else:
            self.mqttConn.Send({'Verb': 'SUBSCRIBE', 'Topics': subscriptionlist})

    # Close MQTT connection
    def Close(self):
        Domoticz.Log("MqttClient::Close")
        self.mqttConn = None
        self.isConnected = False

    # TCP connect callback
    def onConnect(self, Connection, Status, Description):
        Domoticz.Debug("MqttClient::onConnect")
        if (Status == 0):
            Domoticz.Log(F"Successful connect to {Connection.Address}:{Connection.Port}")
            self.Connect()
        else:
            Domoticz.Error(F"Failed to connect to {Connection.Address}:{Connection.Port}, description: {Description}")

    # TCP disconnect callback
    def onDisconnect(self, Connection):
        Domoticz.Log(F"MqttClient::onDisonnect Disconnected from {Connection.Address}:{Connection.Port}")
        self.Close()
        if self.mqttDisconnectedCb != None:
            self.mqttDisconnectedCb()

    # TCP received message callback
    def onMessage(self, Connection, Data):
        topic = ''
        if 'Topic' in Data:
            topic = Data['Topic']
        payloadStr = ''
        if 'Payload' in Data:
            payloadStr = Data['Payload'].decode('utf8','replace')
            payloadStr = str(payloadStr.encode('unicode_escape'))

        if Data['Verb'] == "CONNACK":
            self.isConnected = True
            if self.mqttConnectedCb != None:
                self.mqttConnectedCb()

        if Data['Verb'] == "SUBACK":
            if self.mqttSubackCb != None:
                self.mqttSubackCb()

        if Data['Verb'] == "PUBLISH":
            if self.mqttPublishCb != None:
                self.mqttPublishCb(topic, Data['Payload'])

# Local HTTP client class
class HttpClient:
    Address = ""                    # IP address of HTTP server
    Port = ""                       # Port of HTTP server
    httpConn = None                 # HTTP connection object
    httpConnectedCb = None          # HTTP connection callback
    httpDisconnectedCb = None       # HTTP disconnection callback
    httpMessageCb = None            # HTTP publish callback
    isConnected = False             # HTTP connected flag
    smsPhoneNumber = None           # Phone number to send SMS to
    deviceName = None               # Device name to get status
    deviceId = None                 # Device id to get status
    sendDelay = 0                   # Delay bofore sending device status request (seconds)

    # Class initialization: save parameters and open connection
    def __init__(self, destination, port, httpConnectedCb, httpDisconnectedCb, httpMessageCb):
        Domoticz.Debug("HttpClient::__init__")
        self.Address = destination
        self.Port = port
        self.httpConnectedCb = httpConnectedCb
        self.httpDisconnectedCb = httpDisconnectedCb
        self.httpMessageCb = httpMessageCb
        self.isConnected = False

    # Class default string
    def __str__(self):
        Domoticz.Debug("HttpClient::__str__")
        if (self.httpConn != None):
            return str(self.httpConn)
        else:
            return "None"

    # Open HTTP connection at TCP level
    def Open(self):
        Domoticz.Debug("HttpClient::Open")
        if (self.httpConn != None):
            self.Close()
        self.isConnected = False
        self.httpConn = Domoticz.Connection(Name="HTTP", Transport="TCP/IP", Protocol="HTTP", Address=self.Address, Port=self.Port)
        self.httpConn.Connect()

    # Close HTTP connection
    def Close(self):
        Domoticz.Log("HttpClient::Close")
        self.httpConn = None
        self.isConnected = False

    # TCP connect callback
    def onConnect(self, Connection, Status, Description):
        Domoticz.Debug("HttpClient::onConnect")
        if (self.httpConn == None):
            self.Open()
        else:
            if (Status == 0):
                Domoticz.Log(F"Successful connect to {Connection.Address}:{Connection.Port}")
                sendData = { 'Verb':'GET',
                             'URL':'/json.htm?type=devices&rid='+str(self.deviceId),
                             'Headers':{'Content-Type': 'application/json; charset=utf-8', \
                                        'Connection': 'keep-alive', \
                                        'Accept': 'Content-Type: text/html; charset=UTF-8', \
                                        'Host': self.Address+":"+self.Port, \
                                        'User-Agent':'Domoticz/1.0' }
                            }
                Connection.Send(sendData, self.sendDelay)
            else:
                Domoticz.Error(F"Failed to connect to {Connection.Address}:{Connection.Port}, description: {Description}")
                self.httpConn.Close()

    # TCP disconnect callback
    def onDisconnect(self, Connection):
        self.isConnected = False

    # TCP received message callback
    def onMessage(self, Connection, Data):
        # DumpHTTPResponseToLog(Data)
        Status = int(Data["Status"])
        if Status == 200:
            strData = Data["Data"].decode("utf-8", "ignore")
            try:
                # Domoticz.Debug(strData)
                jsonData = json.loads(strData)
            except ValueError as e:
                Domoticz.Error(F"Error {e} decoding json data")
                return
            result = getValue(jsonData, "result")
            dataValue = getValue(result[0], "Data", "not known")
            lastUpdate = getValue(result[0], "LastUpdate", "????-??-?? ??:??:??")
            # Compose SMS answer message (device name/value @dd/mm hh:mm)
            message = F"{self.deviceName} is {dataValue} @{lastUpdate[8:10]}/{lastUpdate[5:7]} {lastUpdate[11:16]}"
            jsonAnswer = {}
            jsonAnswer['number'] = str(self.smsPhoneNumber)
            jsonAnswer['message'] = message
            answerMessage = json.dumps(jsonAnswer)
            Domoticz.Log(F"Show result: >{replaceCrLf(answerMessage)}<")
            _plugin.mqttClient.Publish(_plugin.smsServerSendTopic, answerMessage)
            self.Close()
            # Load response
            responseDevice = _plugin.getDevice('response')
            responseDevice.Update(nValue=0, sValue=message)
        else:
            Domoticz.Error(F"Error {Status} returned by HTTP")

# Base plug-in class
class BasePlugin:
    # MQTT settings
    mqttClient = None               # MQTT client object
    mqttServerAddress = ""          # MQTT server address
    mqttServerPort = ""             # MQTT server port
    smsServerReceiveTopic = ""      # MQTT topic to read to get received SMS messages
    smsServerSendTopic = ""         # MQTT topic to wirte to send an SMS
    smsServerLwtTopic = ""          # MQTT Last Will Topic
    smsServerPrefix = ""            # Command prefix (we'll treat messages only if starting by this prefix)
    domoticzInTopic = ""            # Domoticz In topic
    domoticzOutTopic = ""           # Domoticz Out topic
    httpClient = None               # HTTP client object
    httpServerAddress = ""          # HTTP server address
    httpServerPort = ""             # HTTP server port

    debugging = "Normal"            # Set Debug level
    initDone = False                # Clear init flag
    analyzer = FF_analyzeCommand()  # Load analyzer object

    # Find a device by name in devices table
    def getDevice(self, deviceName):
        for device in Devices:
            if (Devices[device].DeviceID == deviceName) :
                # Return device
                return Devices[device]
        # Return None if not found
        return None

    # Get next free device Id
    def getNextDeviceId(self):
        nextDeviceId = 1
        while True:
            exists = False
            for device in Devices:
                if (device == nextDeviceId) :
                    exists = True
                    break
            if (not exists):
                break;
            nextDeviceId = nextDeviceId + 1
        return nextDeviceId

    # Get device name
    def deviceStr(self, unit):
        name = "<UNKNOWN>"
        if unit in Devices:
            name = Devices[unit].Name
        return format(unit, '03d') + "/" + name

    # Create a device
    def createDevice(self, deviceName, deviceKey):
        if self.getDevice(deviceKey) == None:
            Domoticz.Log(F"Creating device {deviceName}")
            Domoticz.Device(Name=deviceName, Unit=self.getNextDeviceId(), Type=243, Subtype=19, DeviceID=deviceKey, Used=True).Create()

    # Called on plug-in statup
    def onStart(self):
        # Parse options
        self.debugging = Parameters["Mode6"]        # Debug mode from plug-in parameters
        DumpConfigToLog()
        if self.debugging == "Verbose+":
            Domoticz.Debugging(1+2+4+8+16+64)
        elif self.debugging == "Verbose":
            Domoticz.Debugging(2+4+8+16+64)
        elif self.debugging == "Debug":
            Domoticz.Debugging(2+4+8)
        elif self.debugging == "Normal":
            Domoticz.Debugging(2+4)

        # MQTT server address
        self.mqttServerAddress = Parameters["Address"].replace(" ", "")
        # MQTT port number
        self.mqttServerPort = Parameters["Port"].replace(" ", "")

        # Json file name (at root of plug-in folder)
        jsonFile = Parameters['HomeFolder'] + Parameters["Mode1"]

        # Load json file (except settings)
        errorText, messages = self.analyzer.loadData(jsonFile)          
        # Do we had errors?
        if errorText:
            Domoticz.Error(F"Loading tables status: {messages}")
            return

        Domoticz.Log("Loading tables status: ok")
        # Display info messages if any
        if messages:
            Domoticz.Log(messages)

        # Load JSON settings
        with open(jsonFile, encoding = 'UTF-8') as configStream:
            try:
                jsonData = json.load(configStream)
            except Exception as e:
                Domoticz.Error(F"{e} when loading {jsonFile}")
                return
            # Get only settings part
            settings = getValue(jsonData, 'settings')
            if not settings:
                # No settings found, exit
                Domoticz.Error(F"Can't find 'settings' in {jsonFile}")
                return
            # Get the different settings values
            self.smsServerReceiveTopic = getValue(settings, 'smsServerReceiveTopic')
            self.smsServerSendTopic = getValue(settings, 'smsServerSendTopic')
            self.smsServerLwtTopic = getValue(settings, 'smsServerLwtTopic')
            self.smsServerPrefix = getValue(settings, 'smsServerPrefix')
            self.domoticzInTopic = getValue(settings, 'domoticzInTopic')
            self.domoticzOutTopic = getValue(settings, 'domoticzOutTopic')
            self.domoticzAddress = getValue(settings, 'domoticzAddress')
            self.domoticzPort = getValue(settings, 'domoticzPort')
            if self.smsServerLwtTopic:
                self.smsServerLwtTopic + "/" + self.smsServerPrefix
            inError = False
            if not self.smsServerSendTopic:
                Domoticz.Error(F"Can't find 'settings/smsServerSendTopic' in {jsonFile}")
                inError = True
            if not self.smsServerReceiveTopic:
                Domoticz.Error(F"Can't find 'settings/smsServerReceiveTopic' in {jsonFile}")
                inError = True
            if not self.domoticzInTopic:
                Domoticz.Error(F"Can't find 'settings/domoticzInTopic' in {jsonFile}")
                inError = True
            if not self.domoticzOutTopic:
                Domoticz.Error(F"Can't find 'settings/domoticzOutTopic' in {jsonFile}")
                inError = True
            if not self.domoticzAddress:
                Domoticz.Error(F"Can't find 'settings/domoticzAddress' in {jsonFile}")
                inError = True
            if not self.domoticzPort:
                Domoticz.Error(F"Can't find 'settings/domoticzPort' in {jsonFile}")
                inError = True
            # Exit if something not found
            if inError :
                return

        # Create devices if not existing
        self.createDevice("SMS request","request")                      # This will contain SMS message received as command/request
        self.createDevice("SMS response","response")                    # This will contain SMS message sent as answer to command/request
        self.createDevice("SMS user request", "userRequest")            # This will contain decode dSMS command in case of "setBy":"user". User should scan it and send response

        # Set MQTT last will
        if self.smsServerLwtTopic:
            lwtTopic = self.smsServerLwtTopic
            lwtData = '{"state":"down"}'
        else:
            lwtTopic = None
            lwtData = None

        self.initDone = True
        # Connect to MQTT server
        self.mqttClient = MqttClient(self.mqttServerAddress, self.mqttServerPort, \
            self.onMQTTConnected, self.onMQTTDisconnected, self.onMQTTPublish, self.onMQTTSubscribed, \
            lwtTopic, lwtData)

        # Connect to HTTP server
        self.httpClient = HttpClient(self.domoticzAddress, self.domoticzPort, \
            self.onConnect, self.onDisconnect, self.onMessage)

        # Enable heartbeat
        Domoticz.Heartbeat(60)

    # TCP base-plug-in connection callback
    def onConnect(self, Connection, Status, Description):
        Domoticz.Debug(F"BasePlugin::onConnect {Connection.Name}")
        # Exit if init not properly done
        if not self.initDone:
            return
        if Connection.Name == "MQTT":
            self.mqttClient.onConnect(Connection, Status, Description)
        elif Connection.Name == "HTTP":
            self.httpClient.onConnect(Connection, Status, Description)

    # TCP base-plug-in disconnection callback
    def onDisconnect(self, Connection):
        # Exit if init not properly done
        if not self.initDone:
            return
        Domoticz.Debug(F"BasePlugin::onDisconnect {Connection.Name}")
        if Connection.Name == "MQTT":
            self.mqttClient.onDisconnect(Connection)
        elif Connection.Name == "HTTP":
            self.httpClient.onDisconnect(Connection)

    # TCP base-plug-in message received callback
    def onMessage(self, Connection, Data):
        # Exit if init not properly done
        if not self.initDone:
            return
        if Connection.Name == "MQTT":
            self.mqttClient.onMessage(Connection, Data)
        elif Connection.Name == "HTTP":
            self.httpClient.onMessage(Connection, Data)

    # TCP base-plug-in connected callback
    def onMQTTConnected(self):
        # Exit if init not properly done
        if not self.initDone:
            return
        Domoticz.Debug("onMQTTConnected")
        if self.smsServerLwtTopic:
            payload = '{"state":"up", "version":"'+str(Parameters['Version'])+'", "startDate":"'+str(datetime.now())+'"}'
            self.mqttClient.Publish(self.smsServerLwtTopic, payload, 1)
        # Subscribe to topics to listen to
        self.mqttClient.Subscribe({self.smsServerReceiveTopic})

    # TCP base plug-in MQTT disconnected callabck
    def onMQTTDisconnected(self):
        # Exit if init not properly done
        if not self.initDone:
            return
        Domoticz.Debug("onMQTTDisconnected")

    # TCP base-plug-in MQTT published (received SMS) callback
    def onMQTTPublish(self, topic, rawmessage):
        # Exit if init not properly done
        if not self.initDone:
            return
        payload = ""
        try:
            payload = json.loads(rawmessage.decode('utf8'))
        except ValueError:
            payload = rawmessage.decode('utf8')

        if self.debugging == "Verbose+":
            DumpMQTTMessageToLog(topic, rawmessage, 'onMQTTPublish: ')

        # If this received SMS topic?
        if topic == self.smsServerReceiveTopic:
            # Extract number, date and message parts
            number = getValue(payload, 'number').strip()
            date = getValue(payload, 'date').strip()
            message = getValue(payload, 'message').strip()
            Domoticz.Log(F"Received >{replaceCrLf(message)}< from {number} at {date}")
            # All 3 must be defined
            if message == '' or date == '' or number == '':
                Domoticz.Error(F"Can't find 'number', 'date' and/or 'message' in >{payload}<")
                return
            # Check message prefix   
            if self.smsServerPrefix == "" or self.analyzer.compare(message[:len(self.smsServerPrefix)], self.smsServerPrefix, 2):
                # Remove prefix
                message = message[len(self.smsServerPrefix):].strip()
                Domoticz.Log(F"Message >{replaceCrLf(message)}<")
                # Analyze message
                errorText, messages = self.analyzer.analyzeCommand(message)
                # Do we had an error analyzing command?
                if errorText != "":
                    # Yes, log it and send error back to SMS sender
                    Domoticz.Error(F"Error: {replaceCrLf(messages)}")
                    # Compose SMS answer message
                    message = errorText
                    jsonAnswer = {}
                    jsonAnswer['number'] = str(number)
                    jsonAnswer['message'] = message
                    answerMessage = json.dumps(jsonAnswer)
                    Domoticz.Log(F"Answer: >{replaceCrLf(answerMessage)}<")
                    self.mqttClient.Publish(self.smsServerSendTopic, answerMessage)
                    return
                else:
                    # Analyzed without error
                    if messages:
                        Domoticz.Log(F"Info: {replaceCrLf(messages)}")
                    # Rebuild non abbreviated command
                    understoodMessage = self.analyzer.command+" "+self.analyzer.deviceClass+" "+self.analyzer.deviceName+(" "+self.analyzer.valueToSet if self.analyzer.valueToSet != None else "")
                    Domoticz.Log(F"Understood command is >{understoodMessage}<")
                    # Set Domoticz last request with non abbreviated command
                    lastRequestDevice = self.getDevice('request')
                    if lastRequestDevice:
                        lastRequestDevice.Update(nValue=0, sValue=understoodMessage)
                    if self.analyzer.setBy == "user":
                        # Prepare Domoticz SMS command message (space delimited)
                        domoticzMessage = (
                            # SMS sender phone number
                            str(number)+ 
                            # Command value
                            " "+str(self.analyzer.commandValue)+ 
                            # Device ID
                            " "+str(self.analyzer.deviceId)+ 
                            # Device class
                            " "+str(self.analyzer.deviceClass)+ 
                            # Value to set as given
                            " "+str(self.analyzer.valueToSet)+ 
                            # Value to set remapped with "values" in "deviceClasses" of smsTables.json
                            " "+str(self.analyzer.valueToSetOriginal)+
                            # Value to set type
                            " "+str(self.analyzer.valueToSetType)
                        )
                        Domoticz.Log(F"Domoticz message: >{domoticzMessage}<")
                        requestDevice = self.getDevice('userRequest')
                        ## Update request device for domoticz or user to execute command
                        requestDevice.Update(nValue=0, sValue=domoticzMessage)
                        return
                    else:   # self.analyzer.setBy != "user":
                        # Save phone number, device name and id
                        self.httpClient.smsPhoneNumber = number
                        self.httpClient.deviceName = self.analyzer.deviceName
                        self.httpClient.deviceId = self.analyzer.deviceId
                        self.httpClient.sendDelay = 2
                        nValue = 0;
                        sValue = ""
                        if self.analyzer.commandValue == 1:     # CdeOn
                            nValue = 1
                        elif self.analyzer.commandValue == 2:   # CdeOff
                            nValue = 0
                        elif self.analyzer.commandValue == 4:   # CdeShow
                            # Load current device status
                            self.httpClient.Open()
                            self.httpClient.sendDelay = 0
                            return
                        elif self.analyzer.commandValue == 8:   # CdeSet
                            # 'level','setPoint', 'integer', 'float','string'
                            if self.analyzer.valueToSetType == "level":
                                numValue = int(self.analyzer.valueToSet)
                                if numValue == 0:
                                    nValue = 0
                                    sValue = "0"
                                elif numValue == 100:
                                    nValue = 1
                                    sValue = "100"
                                else:
                                    nValue = 2
                                    sValue = str(numValue)
                            elif self.analyzer.valueToSetType == "setPoint":
                                sValue = self.analyzer.valueToSet
                            elif self.analyzer.valueToSetType == "integer":
                                nValue = self.analyzer.valueToSet
                            elif self.analyzer.valueToSetType == "float":
                                sValue = self.analyzer.valueToSet
                            elif self.analyzer.valueToSetType == "string":
                                sValue = self.analyzer.valueToSet
                        jsonMessage = "{"+F'"command":"udevice","idx":{self.analyzer.deviceId},"nvalue":{nValue},"svalue":"{sValue}","rssi":6,"battery":255'+"}"
                        Domoticz.Log(F"Domoticz update: >{jsonMessage}<")
                        self.mqttClient.Publish(self.domoticzInTopic, jsonMessage)
                        # Load current device status
                        self.httpClient.Open()
            else:
                Domoticz.Debug(F"Prefix >{self.smsServerPrefix}< not found, message not for me")
        else:
            Domoticz.Error(F"Unknown topic >{topic}<, should be >{self.smsServerReceiveTopic}<")

    def onMQTTSubscribed(self):
        # Exit if init not properly done
        if not self.initDone:
            return
        # (Re)subscribed, refresh device info
        Domoticz.Debug("onMQTTSubscribed")
        topics = set()

    def onCommand(self, Unit, Command, Level, sColor):
        # Exit if init not properly done
        if not self.initDone:
            return
        device = Domoticz.Devices[Unit]
        Domoticz.Log(F"{self.deviceStr(Unit)}, {device.DeviceID}: Command: '{Command}', Level: {Level}, Color: {sColor}")
        ## ToDo: check that changes in SMS answer are properly displayed here
    
    def onDeviceAdded(self, Unit):
        # Exit if init not properly done
        if not self.initDone:
            return
        Domoticz.Log(F"onDeviceAdded {self.deviceStr(Unit)}")

    def onDeviceModified(self, Unit):
        # Exit if init not properly done
        if not self.initDone:
            return
        Domoticz.Log(F"onDeviceModified {self.deviceStr(Unit)}")
        
    def onDeviceRemoved(self, Unit):
        # Exit if init not properly done
        if not self.initDone:
            return
        Domoticz.Log(F"onDeviceRemoved {self.deviceStr(Unit)}")

    def onHeartbeat(self):
        # Exit if init not properly done
        if not self.initDone:
            return
        if self.debugging == "Verbose+":
            Domoticz.Debug("Heartbeating...")

        # Reconnect if connection has dropped
        if self.mqttClient.mqttConn is None or (not self.mqttClient.mqttConn.Connecting() and not self.mqttClient.mqttConn.Connected() or not self.mqttClient.isConnected):
            Domoticz.Debug("Reconnecting MQTT")
            self.mqttClient.Open()
        else:
            self.mqttClient.Ping()

global _plugin
_plugin = BasePlugin()

def onStart():
    global _plugin
    _plugin.onStart()

def onConnect(Connection, Status, Description):
    global _plugin
    _plugin.onConnect(Connection, Status, Description)

def onDisconnect(Connection):
    global _plugin
    _plugin.onDisconnect(Connection)

def onMessage(Connection, Data):
    global _plugin
    _plugin.onMessage(Connection, Data)

def onCommand(Unit, Command, Level, Color):
    global _plugin
    _plugin.onCommand(Unit, Command, Level, Color)

def onDeviceAdded(Unit):
    global _plugin
    _plugin.onDeviceAdded(Unit)

def onDeviceModified(Unit):
    global _plugin
    _plugin.onDeviceModified(Unit)

def onDeviceRemoved(Unit):
    global _plugin
    _plugin.onDeviceRemoved(Unit)

def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()

def DumpConfigToLog():
    for x in Parameters:
        if Parameters[x] != "":
            Domoticz.Log( "'" + x + "':'" + str(Parameters[x]) + "'")
    Domoticz.Log("Device count: " + str(len(Devices)))
    for x in Devices:
        Domoticz.Log("Device: " + str(x) + " - " + str(Devices[x]))

def DumpMQTTMessageToLog(topic, rawmessage, prefix=''):
    message = rawmessage.decode('utf8','replace')
    message = str(message.encode('unicode_escape'))
    Domoticz.Log(prefix+topic+":"+message)

# Returns a dictionary value giving a key or default value if not existing
def getValue(dict, key, default=''):
    if dict == None:
        return default
    else:
        if key in dict:
            if dict[key] == None:
                return default #or None
            else:
                return dict[key]
        else:
            return default #or None

# Dump an HTTP response to log
def DumpHTTPResponseToLog(httpResp, level=0):
    if (level==0): Domoticz.Debug("HTTP Details ("+str(len(httpResp))+"):")
    indentStr = ""
    for x in range(level):
        indentStr += "----"
    if isinstance(httpResp, dict):
        for x in httpResp:
            if not isinstance(httpResp[x], dict) and not isinstance(httpResp[x], list):
                Domoticz.Debug(indentStr + ">'" + x + "':'" + str(httpResp[x]) + "'")
            else:
                Domoticz.Debug(indentStr + ">'" + x + "':")
                DumpHTTPResponseToLog(httpResp[x], level+1)
    elif isinstance(httpResp, list):
        for x in httpResp:
            Domoticz.Debug(indentStr + "['" + x + "']")
    else:
        Domoticz.Debug(indentStr + ">'" + x + "':'" + str(httpResp[x]) + "'")
        
# Replace CR and LF by \r and \n in order to keep log lines structured
def replaceCrLf(message):
    return str(message).replace("\r","\\r").replace("\n","\\n")


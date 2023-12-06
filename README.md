# FF_SmsServer Domoticz plug-in
Domoticz's plug-in to allow users sending SMS containing commands to be executed by Domoticz.

## What's for?

This python code reads all SMS received by a (FF) SMS server. If first command's word is equal to a given prefix, rest of command is analyzed as a valid command. Errors during analysis are returned as SMS to command's sender. If no errors, command is sent to Domoticz and result sent back to sender, still by SMS.

## Note
There are 2 versions of this code:
- https://github.com/FlyingDomotic/domoticz-ff_smsserver-plugin.git (this code), which runs as Domoticz's plug-in
- https://github.com/FlyingDomotic/FF_SmsServerDomoticz.git, which is a Linux service implementation

You may chosse version best suited for you.

## Prerequisites

You must have a (FF) SMS server (https://github.com/FlyingDomotic/FF_SmsServer.git) properly configured and running somewhere on your network.

## Installation

Follow these steps:

1. Clone repository into your Domoticz plugins folder.
```
cd domoticz/plugins
git clone https://github.com/FlyingDomotic/domoticz-ff_smsserver-plugin.git FF_SmsServer
```
2. Copy examples/smsTable.json file into plug-in folder (close to plugin.py) and adapt it to your configuration
3. Restart Domoticz.
4. Make sure that "Accept new Hardware Devices" is enabled in Domoticz settings.
5. Go to "Hardware" page and add new item with type "FF_SmsServer with LAN interface".
6. Give JSON configuration file name to be used (located in FF_SmsServer plugin folder).

## Update

Go to code folder and pull new version:
```
cd [where you installed domoticz-ff_smsserver-plugin]
git pull
```
Changes will be applied at next Domoticz restart (or plug-in reload)

Note: if you did any changes to files and `git pull` command doesn't work for you anymore, you could stash all local changes using:
```
git stash
```
or
```
git checkout [modified file]
```

## Principle

Code was originally designed to get (French) SMS messages to remotely manage automation system.

General command organization is: [command] [device type] [device name] [value to set].

For example: `allume la lampe de la cuisine`, `ouvre le volet du salon`, `règle la consigne de la clim du séjour sur 21`, ...

Again, this structure is French oriented, and should be adapted to other languages/grammar if needed.

For example, to turn a bulb on, French is `Allume lampe cuisine`, word to word translated into `turn on bulb kitchen`,
while English people would better say `turn kitchen bulb on`.

A future version could implement different grammars, users' requests may speed-up the process ;-)

Code allows to work with UTF-8 data. You may optionally restrict comparison and output to 7 bits ASCII equivalent to help processing, allowing to remove accentuated characters.

## Files
- smsTables.json: configuration file describing devices, classes and commands.
- FF_analyzeCommand.py: contains common code used to parse smsTables.json, and parse SMS commands against them.
- checkJsonFiles.py: check syntax and relationships of smsTables.json and allows you to test legality of commands (without executing them).
- makeDoc.py: generate a list of commands supported by your configuration.
- plugin.py: reads SMS message, check for prefix, parse command and execute it if legal.

## smsTables.json content

This json configuration file contains the following parts (in any order):

- "ignores": contains keywords to be ignored (like `the`, `of`, `to`...). All these keywords will be removed from message before parsing.
- "mappingValues": contains binary values of the different commands. Typical implementation could be like:
	- "cde_off":{"mappingValue":2}, to turn a device off.
	- "cde_set":{"mappingValue":8,"set":true}, to set a device to any numerical or string value.
	- "cde_show":{"mappingValue":4}, to show current value of a device.
- "commands": contains the commands to implement. Same action can be supported by multiple values (i.e. `turn_on`, `switch_on`, `light`, `open` to set a device on). `Commands` maps to `mappingValues`.
- "mappings": define classes and maps them to `mappingValues`. Typical implementation could be like:
	- "class_on_off":{"mapping":["cde_on","cde_off","cde_show"]} for any on/off device.
	- "class_set":{"mapping":["cde_set","cde_show"]} for any device with specific value.
	- "class_show":{"mapping":["cde_show"]} for all devices you won't change value.
- "deviceClasses": associate device classes with classes.
- "devices": define supported Domoticz devices (not necessarily with their real names). As a device could have multiple sensors, they're prefixed by a device class. It also specify Domoticz idx. It could contain Domoticz device name (useful to compare given device name with Domoticz one).

Here's an example of smsTables.json (in French):
```
{
	"ignores": [
		"de",
		"du",
		"des",
		"d'",
		"le",
		"la",
		"les",
		"l'",
		"à",
		"a",
		"=",
		"sur"
	],
	"mappingValues": {
		"cde_on":{"mappingValue":1},
		"cde_off":{"mappingValue":2},
		"cde_show":{"mappingValue":4},
		"cde_set":{"mappingValue":8,"set":true}
	},
	"commands": {
		"allume":{"command":"cde_on"},
		"arme":{"command":"cde_on"},
		"ouvre":{"command":"cde_on"},
		"éteins":{"command":"cde_off"},
		"désarme":{"command":"cde_off"},
		"ferme":{"command":"cde_off"},
		"état":{"command":"cde_show"},
		"affiche":{"command":"cde_show"},
		"règle":{"command":"cde_set"},
		"définis":{"command":"cde_set"}
	},
	"mappings": {
		"class_on_off":{"mapping":["cde_on","cde_off","cde_show"]},
		"class_set":{"mapping":["cde_set","cde_show"]},
		"class_show":{"mapping":["cde_show"]}
	},
	"deviceClasses": {
		"chaleur":{"deviceClass":"class_set","setType":"level","values":{"chaud":10,"froid":20,"déshumidification":30}},
		"clim":{"deviceClass":"class_on_off"},
		"consigne":{"deviceClass":"class_set","setType":"setPoint","minValue":6,"maxValue":25},
		"contact":{"deviceClass":"class_show"},
		"lampe":{"deviceClass":"class_on_off"},
		"radiateur":{"deviceClass":"class_set","setType":"level","values":{"off":0,"confort":10,"eco":40,"horsgel":50}},
		"température":{"deviceClass":"class_show"}
	},
	"devices": {
		"clim chambre sud":{"index":12,"name":"Clim chambre Sud - Power"},
		"chaleur chambre sud":{"index":23,"name":"Clim chambre Sud - Mode"},
		"consigne chambre sud":{"index":34,"name":"Clim chambre Sud - Thermostat"},
		"lampe cuisine":{"index":45,"name":"Cuisine"},
		"température sejour":{"index":56,"name":"Température air séjour"},
		"radiateur SdB nord":{"index":67,"name":"Mode radiateur SdB nord"},
		"contact porte entrée":{"index":78,"name":"Contact porte entrée"}
	}
}
```

## How to get list of commands supported by your implementation?

Just run `makeDoc.py` and have a look at `config.txt` it'll generate. Here's an example of the configuration listed in the previous paragraph. First column is Domoticz device name while second one list all commands available for the device:
```
Clim chambre Sud - Power	allume/arme/ouvre/éteins/désarme/ferme/état/affiche clim chambre sud
Clim chambre Sud - Mode	état/affiche/règle/définis chaleur chambre sud [chaud/froid/déshumidification]
Clim chambre Sud - Thermostat	état/affiche/règle/définis consigne chambre sud
Cuisine	allume/arme/ouvre/éteins/désarme/ferme/état/affiche lampe cuisine
Température air séjour	état/affiche température sejour
Mode radiateur SdB nord	état/affiche/règle/définis radiateur SdB nord [off/confort/eco/horsgel]
Contact porte entrée	état/affiche contact porte entrée
```


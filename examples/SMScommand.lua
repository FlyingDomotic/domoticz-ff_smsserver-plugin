-- Execute a command received by SMS (part of FF_SmsServer)

-- Simple string splitting method
function string:split(sep)
	local sep, fields = sep or ":", {}
	local pattern = string.format("([^%s]+)", sep)
	self:gsub(pattern, function(c) fields[#fields + 1] = c end)
	return fields
end

-- Convert a char to hex value
local char_to_hex = function(c)
  return string.format("%%%02X", string.byte(c))
end

-- Encode an URL, replacing forbidden chars by hex equivalents
function urlencode(url)
	if url == nil then
		return
	end
	url = url:gsub("([^%w ])", char_to_hex)
	url = url:gsub(" ", "+")
	return url
end

-- Sends a mail, an SMS message and save it into last SMS message device
function notify(msg)
	-- Log to Domoticz
	print ('Info: '..msg)
	-- Send answer back to command requester
	os.execute("curl "http://"..smsServerAddress.."/rest/params&number="..phoneNumber.."&message="..urlencode(os.date("%d-%H:%M:%S ")..msg).."' &")
	-- Send answer back by mail (delete it if not needed)
	os.execute('echo "'..msg..'" | mail -s "SMS - '..msg..'" '..mailReceived..' &')
	-- Write last SMS answer to Domoticz device
	commandArray["UpdateDevice"] = tostring(lastSmsAnswerIdx).."|0|"..msg
end

-- Converts device idx to device name
function idx2deviceName(idx)
	for devName, devIdx in pairs(otherdevices_idx) do
		if devIdx == idx then
			return name
		end
	end
	-- If device is not found, return "Idx=xxx"
	return "Idx="..tostring(idx)
end

-- Init some values
commandArray = {}														-- Command array to return
phoneNumber = ""														-- Will contain phone number to answer to

-- Commands are built around 4 or 7 values separated by a space
smsNumberTag = 1			-- SMS number to answer to. Taken from SMS sender phone number
commandTag = 2				-- Command. 1 : set On, 2 : set Off, 4 : show, 8 : set Value, 'local' : execute local command. Taken from "mappingValues"/"mappingValue" via "commands"
domoticzIdxTag = 3			-- Domoticz device index (or local command to execute). Taken from "devices"/"index"
deviceClassTag = 4			-- Sensor type. Taken from "deviceClasses"
	-- Following codes are only used for commandTag = 8 (set Value)
valueToSetTag = 5			-- Value to set. Taken from received command line or "deviceClasses"/"values" via "devices" when it exists
originalValueToSetTag = 6	-- Original value to set from received command line. Loaded when "deviceClasses"/"values" via "devices" was found
setTypeTag = 7				-- Type of value to set. Taken from "deviceClasses"/"setType" via "devices".

-- Set your local values here
smsCommandDeviceName = "SMS user request"								-- This is received SMS command Domoticz's device name (default value, change it if needed)
smsServerAddress = "<Put here SMS server IP address or name>"			-- This is SMS server IP address or name, used to send SMS answer back to requester
mailReceived = "<Put here mail address(e) to send messages>"			-- This is the mail address(es) to send message to
lastSmsAnswerIdx = "<Put here IDx of last SMS answer text device>"		-- This is Domoticz IDX of last SMS answer device (will contain last SMS answer sent)

-- Used only in this example to change security panel (delete if not needed)
panelSecurityCode = "<Put here your panel security code if needed>"		-- This is your panel security code, if your code need it (delete line else)
domoticzUrl = "http://127.0.0.1:8080"									-- This is your Domoticz's URL, with user/password if applying. In this example, used to change security panel.

-- Loop through all the changed devices
for deviceName,deviceValue in pairs(devicechanged) do
	-- Is this received SMS command device?
	if (deviceName==smsCommandDeviceName) then
		tags = string.split(deviceValue, " ")							-- Split command into tags
		phoneNumber = tags[smsNumberTag]								-- Extract phone number to send answers to
		if tags[commandTag] == 'local' then								-- Is this a local Os command to execute?
			startPos, endPos = string.find(deviceValue, 'local ')		-- Locate "local " keyword in received command
			localCommand = string.sub(deviceValue, endPos + 2)			-- Keep only part after "local " keyword
			print("Info: SMS local command >" .. localCommand .. "<")	-- Trace command to execute
			execCommand = localCommand .. ' 2>&1| mail -s "Executing ' .. string.gsub(localCommand, '"', "''") .. '" '..mailReceiver..' &'	-- Compose command to execute
			os.execute(execCommand)										-- Execute command
		else															-- This is not a "local" command
			sensorName = idx2deviceName(tags[domoticzIdxTag])			-- Get device name form IDX
			print("Info: SMS " .. deviceValue .. " (" .. sensorName ..") = (" .. otherdevices[sensorName] .. ")")	-- Log current value
			if (tags[commandTag] == '1') then							-- This is a turn on command
				commandArray[sensorName] = 'On'
				notify(sensorName..' turned on')
			elseif (tags[commandTag] == '2') then						-- This is a turn off command
				commandArray[sensorName] = 'Off'
				notify(sensorName..' turned off')
			elseif (tags[commandTag] == '8') then						-- This is a set command
				if (tags[deviceClassTag] == 'panel') then				-- Example of non standard sensor type management (here, sensor type "panel")
				-- Specific example of security panel - Delete lines up to next "end" if not needed
					if (tags[valueToSetTag] == 'disarmed' or tags[valueToSetTag] == 'off') then
						commandArray['OpenURL'] = domoticzUrl..'/json.htm?type=command&param=setsecstatus&secstatus=0&seccode='..panelSecurityCode
						notify(sensorName..' disarmed')
					elseif (tags[valueToSetTag] == 'armed home' then
						commandArray['OpenURL'] = domoticzUrl..'/json.htm?type=command&param=setsecstatus&secstatus=1&seccode='..panelSecurityCode
						notify(sensorName..' armed home')
					elseif (tags[valueToSetTag] == 'armed away' or tags[valueToSetTag] == 'on' ) then
						commandArray['OpenURL'] = domoticzUrl..'/json.htm?type=command&param=setsecstatus&secstatus=2&seccode='..panelSecurityCode
						notify(sensorName..' armed away')
					else
						notify(sensorName..": Don't understand "..tags[valueToSetTag])
					end
				-- End of security panel example
				-- Here are standard types
				elseif (tags[setTypeTag] == 'level') then				-- Type = "level"
					commandArray[sensorName] = 'Set Level '+tostring(tags[6])
				elseif (tags[setTypeTag] == 'setPoint') then			-- Type = "setPoint"
					commandArray['SetSetPoint:'..tags[domoticzIdxTag]] = tags[valueToSetTag]
				else													-- Types = "integer" or "string"
					commandArray[sensorName] = tags[valueToSetTag]
					notify(sensorName..' set to '..tostring(tags[valueToSetTag]))
				end
			end
		end
	end
end

-- Dump contents of commandArray, to get precise idea of what will be changed
for d,v in pairs(commandArray) do
	print('Debug: Set ' .. d .. "=" .. v)
end
return commandArray
--[[
	This is script is run each time something is written into Domoticz's device pointed by smsCommandDeviceName variable(defaulting to "SMS user request").

	FF_SmsServer plugin write it each time an SMS "set" command with a "setBy":"user" is received.
	It's useful for devices that can't be set simply (for example, security panel), when requiring to change multiples devices simultaneously, when external actions are to be run, when testing other devices is needed to define correct value...

	Default example comes with security panel example (as well as root for other commands type). Define your security panel code and Domoticz URL in header if needed.
]]
# Known ID
0x00 Reserved
0x01 Temerature
0x02 Pressure
0x03 Humidity
0x04 UNUSED (was time)
0x05 Voltage (like in battery power)
0x06 Screen


Packet
name    value   size    note
MAGIC   W       1
Version 1       1
MAC     ?       6
Count   ?       1       Total number of 'sensors' in Packet
Payload ?       ?
Sensor
ID      ?       1       See Known ID
DATA

Most sensors use 4 bytes of data
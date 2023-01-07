import struct
import libscrc


data = '10 60 1F FF FF FF FF FF FF FF FF FF FF FF FF FF FF FF FF FF FF FF FF FF FF FF FF F6'
data = '10 60 1F 2B 2B 2B 2B 2B 2B 2B 2B 2B 2B 2B 2B 2B 2B 2B 2B 2B 2B 2B 2B 2B 2B 2B 2B BE'
data = '10 60 1F 57 01 EC 62 60 9D 49 98 03 02 00 00 00 00 03 00 00 00 00 01 00 00 00 00 F4'
raw_bytes = bytes([int('0x' + x, 16) for x in data.split(' ')])
print(raw_bytes, len(raw_bytes))

raw_version = struct.unpack('B', raw_bytes[0:1])[0]
version_zero = (raw_version & 0b00001111) >> 0
version =      (raw_version & 0b11110000) >> 4
print(version, version_zero)

raw_size = struct.unpack('B', raw_bytes[1:2])[0]
size_zero = (raw_size & 0b00000011) >> 0
size =      (raw_size & 0b11111100) >> 2
print(size, size_zero)

raw_routing = struct.unpack('B', raw_bytes[2:3])[0]
packet_to = (raw_routing & 0b00001111) >> 0 
packet_from   = (raw_routing & 0b11110000) >> 4
print(packet_from, '->', packet_to)

raw_payload = raw_bytes[3:-1]
raw_crc8 = raw_bytes[-1:]

packet_ctc8 = int.from_bytes(raw_crc8, 'big')

#crc8_object = crc8.crc8(raw_bytes[:-1])
#print(crc8_object.hexdigest())
caclulated_crc8 = libscrc.dvb_s2(raw_bytes[:-1])
if caclulated_crc8 == packet_ctc8:
    print("packet VALID")

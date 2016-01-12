from struct import pack, unpack
import ctypes

# Frame types
START_DISCOVERY = b'\xa0'
STOP_DISCOVERY = b'\xa1'
CONNECTOR_READY = b'\xa2'
GET_RESOURCE_VALUE = b'\xb0'
SET_RESOURCE_VALUE = b'\xb1'

UUID = b'\xaa'
RESOURCE = b'\xab'
RESOURCE_VALUE = b'\xba'

# Resource modes
RO = 0
WO = 1
RW = 2

# Resource types
MS = 0
CD = 1
CF = 2

# Resource dimensions
BL = 0
PC = 1
VL = 2
AT = 3

class ResourceConfigurationBits(ctypes.BigEndianStructure):
	_fields_ = [
		('mode', ctypes.c_uint8, 2),
		('type', ctypes.c_uint8, 2),
		('dimension', ctypes.c_uint8, 2),
	]

class ResourceConfiguration(ctypes.Union):
	_fields_ = [
		('b', ResourceConfigurationBits),
		('Byte', ctypes.c_uint8),
	]
	_anonymous_ = ('b')

def code_packet(command, payload):
	payload_length = len(payload)
	return pack('!c' + str(payload_length) + 's', command, payload)

def decode_packet(packet):
	payload_length = len(packet) - 1
	command, payload = unpack('!c' + str(payload_length) + 's', packet)

	return (command, payload)

def code_resource_config(mode, type, dimension):
	b = ResourceConfiguration()

	b.mode = mode
	b.type = type
	b.dimension = dimension

	return b.Byte

def decode_resource_config(byte):
	b = ResourceConfiguration()
	b.Byte = byte

	if b.mode == RO:
		mode = 'ro'
	elif b.mode == WO:
		mode = 'wo'
	elif b.mode == RW:
		mode = 'rw'
	else:
		raise ValueError

	if b.type == MS:
		type = 'ms'
	elif b.type == CD:
		type = 'cd'
	elif b.type == CF:
		type = 'cf'
	else:
		raise ValueError

	if b.dimension == BL:
		dimension = 'bl'
	elif b.dimension == PC:
		dimension = 'pc'
	elif b.dimension == VL:
		dimension = 'vl'
	elif b.dimension == AT:
		dimension = 'at'
	else:
		raise ValueError

	return mode, type, dimension

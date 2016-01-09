from struct import pack, unpack

START_DISCOVERY = b'\xa0'
STOP_DISCOVERY = b'\xa1'
CONNECTOR_READY = b'\xa2'
GET_RESOURCE_VALUE = b'\xb0'
SET_RESOURCE_VALUE = b'\xb1'

UUID = b'\xaa'
RESOURCE = b'\xab'
RESOURCE_VALUE = b'\xba'

def code_packet(command, payload):
	payload_length = len(payload)
	return pack('!c' + str(payload_length) + 's', command, payload)

def decode_packet(packet):
	payload_length = len(packet) - 1
	command, payload = unpack('!c' + str(payload_length) + 's', packet)

	return (command, payload)

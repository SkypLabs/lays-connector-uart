#!/usr/bin/env python3

import pika
import json
import serial
import uuid
from hdlcontroller import HDLController
from fysom import Fysom
from uart_protocol import *
from os import getenv
from time import sleep
from sys import exit, stdout, stderr

# AMQP configuration
amqp = None
amqp_host = getenv('AMQPSERVER_PORT_5672_TCP_ADDR', 'localhost')
amqp_port = 5672
amqp_rd_channel = None
amqp_dr_channel = None
amqp_dc_channel = None

# Serial port configuration
ser = serial.Serial()
ser.port = getenv('LAYS_SERIAL_PORT', '/dev/ttyACM0')
ser.baudrate = int(getenv('LAYS_SERIAL_BAUDRATE', '9600'))
ser.timeout = int(getenv('LAYS_SERIAL_TIMEOUT', '0'))

# Device resources
device_resources = dict()
device_resources['resources'] = list()

def read_serial():
	return ser.read(ser.inWaiting())

# HDLC controller
hdlc_c = HDLController(read_serial, ser.write)

def device_request(ch, method, properties, body):
	message = json.loads(body.decode())

	try:
		address = message['address']
		action = message['action']

		if action == 'read':
			stdout.write('[*] New read request @{0}\n'.format(address))
		elif action == 'write':
			value = message['value']
			stdout.write('[*] New write request @{0} : {1}\n'.format(address, value))
	except KeyError:
		stderr.write('[x] Bad request :\n\t=> {0}\n'.format(message))

	ch.basic_ack(delivery_tag = method.delivery_tag)

def declare_resources(resources):
	message = json.dumps(resources)

	amqp_rd_channel.basic_publish(
		exchange='',
		routing_key='resources-discovery',
		body=message,
		properties=pika.BasicProperties(
			delivery_mode=2
		),
	)

def serial_connection(e):
	stdout.write('[*] Connection to serial bus ({0}) ...\n'.format(ser.port))

	try:
		ser.open()
		hdlc_c.start()
		stdout.write('[*] Connected to serial bus\n')
		e.fsm.serial_connection_ok()
	except serial.serialutil.SerialException as err:
		stderr.write('[x] Serial connection problem : {0}\n'.format(err))
		e.fsm.serial_connection_ko()

def amqp_connection(e):
	stdout.write('[*] Connection to AMQP server ({0}) ...\n'.format(amqp_host))

	try:
		global amqp
		global amqp_rd_channel

		amqp = pika.BlockingConnection(pika.ConnectionParameters(
			amqp_host,
			amqp_port
		))
		amqp_rd_channel = amqp.channel()
		amqp_rd_channel.queue_declare(queue='resources-discovery', durable=True)
		stdout.write('[*] Connected to AMQP server\n')
		e.fsm.amqp_connection_ok()
	except pika.exceptions.ConnectionClosed:
		stderr.write('[x] AMQP connection problem\n')
		e.fsm.amqp_connection_ko()

def retry_connection(e):
	stdout.write('[*] Retry in 3 seconds ...\n')
	sleep(3)

def start_discovery(e):
	stdout.write('[*] Starting discovery ...\n')
	hdlc_c.send(START_DISCOVERY)

	while True:
		packet = hdlc_c.get_data()
		command, payload = decode_packet(packet)

		if command == UUID:
			device_resources['uuid'] = str(uuid.UUID(bytes=payload))
			stdout.write('[*] Device UUID received : {0}\n'.format(device_resources['uuid']))
			break

	e.fsm.uuid_received()

def wait_for_resources(e):
	stdout.write('[*] Waiting for resources ...\n')

	while True:
		packet = hdlc_c.get_data()
		command, payload = decode_packet(packet)

		if command == STOP_DISCOVERY:
			stdout.write('[*] Discovery stopped\n')
			break
		elif command == RESOURCE:
			resource_address = payload[0]
			resource_config = payload[1]

			resource_mode = None
			resource_type = None
			resource_dimension = None

			resource = dict()
			resource['address'] = resource_address
			resource['mode'] = resource_mode
			resource['type'] = resource_type
			resource['dimension'] = resource_dimension

			device_resources['resources'].append(resource)
		else:
			pass

	e.fsm.stop_discovery_received()

def stop_discovery(e):
	global amqp_dr_channel
	global amqp_dc_channel

	amqp_dr_channel = amqp.channel()
	amqp_dr_channel.queue_declare(queue=device_resources['uuid'], durable=True)
	amqp_dc_channel = amqp.channel()
	amqp_dc_channel.queue_declare(queue='data-collector', durable=True)

	declare_resources(device_resources)

	hdlc_c.send(CONNECTOR_READY)

	e.fsm.ready()

def wait_for_data(e):
	stdout.write('[*] Waiting for data ...\n')

try:
	fsm = Fysom({
		'initial': 'serial_connection',
		'events': [
			{'name': 'serial_connection_ko', 'src': 'serial_connection', 'dst': 'serial_connection'},
			{'name': 'serial_connection_ok', 'src': 'serial_connection', 'dst': 'amqp_connection'},
			{'name': 'amqp_connection_ko', 'src': 'amqp_connection', 'dst': 'amqp_connection'},
			{'name': 'amqp_connection_ok', 'src': 'amqp_connection', 'dst': 'start_discovery'},
			{'name': 'uuid_received', 'src': 'start_discovery', 'dst': 'wait_for_resources'},
			{'name': 'stop_discovery_received', 'src': 'wait_for_resources', 'dst': 'stop_discovery'},
			{'name': 'ready', 'src': 'stop_discovery', 'dst': 'wait_for_data'},
		],
		'callbacks': {
			'onserial_connection': serial_connection,
			'onserial_connection_ko': serial_connection,
			'onserial_connection_ok': amqp_connection,
			'onreenterserial_connection': retry_connection,
			'onamqp_connection_ko': amqp_connection,
			'onamqp_connection_ok': start_discovery,
			'onreenteramqp_connection': retry_connection,
			'onuuid_received': wait_for_resources,
			'onstop_discovery_received': stop_discovery,
			'onready': wait_for_data,
		},
	})
except KeyboardInterrupt:
	stdout.write('[*] Bye !\n')
	hdlc_c.stop()
	ser.close()

	if amqp != None:
		amqp.close()

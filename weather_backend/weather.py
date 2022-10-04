#!/usr/bin/env python3

import socket
import json
import sys
import logging
import datetime
from os.path import exists, isdir
from os import mkdir
import time
import fetch
import draw
import protocol
from protocol import TempSensor, PressureSensor, HumiditySensor, VoltSensor, SoilMoistureSensor, VOCSensor
import struct
import traceback

from config import load_config

from paho.mqtt.client import Client
import asyncio

import serial_asyncio


stype2name = {
    TempSensor.MODULE_ID: ('temperature', fetch.Temp),
    # scale Pa to hPa
    PressureSensor.MODULE_ID: ('pressure', lambda v: fetch.Pres(v * 0.01)),
    HumiditySensor.MODULE_ID: ('humidity', fetch.Humidity),
    # scale mV to V
    VoltSensor.MODULE_ID: ('volt', lambda v: fetch.Volt(v * 0.001)),
    SoilMoistureSensor.MODULE_ID: ('soil', fetch.Humidity),
    VOCSensor.MODULE_ID: ('voc', None),
}

logging.basicConfig(format='%(asctime)s %(message)s')

cfg = load_config('./config.toml')
# check if we have storage DIR
storage_path = cfg['storage']['path']
if not exists(storage_path):
    mkdir(storage_path)
if not isdir(storage_path):
    print(f'rrd path is not directory: {storage_path}')
    exit(1)

RRD = fetch.RRD(storage_path)


class ScreenInfo:
    def __init__(self):
        self.deadline = 0
        self.state = 0
        self.sensor_idx = 0
        self.time_to_swith_state = 0
        self.addr = 'localhost'


class ScreenThread:
    _lock = asyncio.Lock()
    _screens = {}
    _rrd = RRD
    _keep_looping = True

    def __init__(self, sock):
        self.sock = sock

    async def run(self):
        while self._keep_looping:
            await self._loop()
            await asyncio.sleep(1)

    async def _loop(self):
        now = time.time()
        async with self._lock:
            devices = list(self._screens.keys())
            for d in devices:
                if self._screens[d].deadline < now:
                    del self._screens[d]
            devices = self._screens.copy()

        # generate images
        for did, d in devices.items():
            if d.time_to_swith_state > now:
                continue
            d.time_to_swith_state = now + 5
            sensors = cfg['device'][did].get('screen')
            if not sensors:
                continue
            sensors_names = list(sensors.keys())
            # TODO(m): why empty
            if not sensors_names:
                continue
            if d.sensor_idx >= len(sensors_names):
                d.sensor_idx = 0
            sensor_id = sensors_names[d.sensor_idx]
            selected_sensor = sensors[sensor_id]
            name = cfg['device'][sensor_id]['name']
            # get data from last 8 hours
            raw_data = self._rrd.rrdfetch(sensor_id, start=8 * 60 * 60)
            # states
            # 0 -> overview
            # 1 -> temperature graph
            # 2 -> humidity graph
            # 3 -> pressure graph
            # 4 -> volate graph
            # then repeat for another sensor

            def _filter(data):
                return [x for x in data if x is not None]
            temp = _filter(raw_data['temp'])
            hum = _filter(raw_data['hum'])
            press = _filter(raw_data['pres'])
            volt = _filter(raw_data['volt'])
            if d.state == 0:
                image = draw.draw_overview(name, temp=temp[-1], hum=hum[-1],
                                           press=press[-1], volt=volt[-1],
                                           time=raw_data['time'][len(temp) - 1])
            elif d.state == 1:
                image = draw.draw_graph('Temp', name, temp)
            elif d.state == 2:
                image = draw.draw_graph('Hum', name, hum)
            elif d.state == 3:
                image = draw.draw_graph('Pres', name, press)
            elif d.state == 4:
                image = draw.draw_graph('Volt', name, volt)
            else:
                image = draw.draw_overview(name)
            df = protocol.DataFrame()
            df.device_id = did
            df.message_to_broker = False
            df.modules = [
                protocol.ImagePush(128, 32, image)
            ]
            data = protocol.serialize(df)
            self.sock.sendto(data, (d.addr, 9696))
            d.state += 1
            if d.state > 4:
                d.sensor_idx += 1
                d.state = 0

    async def add_screen(self, id, addr, timeout=120):
        # TODO: sensor 1 and sensor 2 is swapend on scrren vs web
        # TODO: async with is without timeout  (2 secs)
        async with self._lock:
            screen = self._screens.get(id)
            if not screen:
                screen = ScreenInfo()
                self._screens[id] = screen
            screen.deadline = time.time() + timeout
            screen.addr = addr[0]

DEBUG = False

# st = ScreenThread()
# st.start()
# st.add_screen("e8db849381ec", ("10.0.0.28", 0))
class WOutEncoder(json.JSONEncoder):
    def default(self, o):
        if hasattr(o, 'value'):
            return o.value
        raise Exception('boom')
class WeatherProcessor:
    def __init__(self, sock):
        self.sock = sock
        self.st = ScreenThread(self.sock)

    async def process(self, data, *, addr=None):
        try:
            df = protocol.parse(data)
        except Exception as e:
            print(f'invalid data {data}, unable to parse:', e)
            return

        if not df.message_to_broker:
            return

        rcvtime = datetime.datetime.utcnow().isoformat()
        sensors = {}

        # NOTE(m): We could just use set of sensors values converted to
        # RRD types not dict of names
        for sid in df.modules:
            module_name, converter = stype2name.get(sid.MODULE_ID)
            if sid.MODULE_ID == protocol.ScreenSensor.MODULE_ID:
                await self.st.add_screen(df.device_id, addr)
                continue

            if module_name == 'voc':
                sensors['iaq_static'] = fetch.StaticIaq(sid.iaq_static)
                sensors['iaq'] = fetch.Iaq(sid.iaq)
                sensors['co2'] = fetch.Co2(sid.co2)
            elif module_name:
                sensors[module_name] = converter(sid.value)
            else:
                print(f'Unknown module: {sid.MODULE_ID}')

        await RRD.add(df.device_id, sensors.values())
        if DEBUG:
            sensors['rcvtime'] = rcvtime
            as_json = json.dumps(sensors, cls=WOutEncoder)

            sys.stdout.write(as_json)
            sys.stdout.write('\n')
            sys.stdout.flush()


class WeaterServerUARTProtocol(asyncio.Protocol):
    def __init__(self, emergency_stop, processor):
        self.emergency_stop = emergency_stop
        self.processor = processor
        self.cache = bytearray()

    def connection_made(self, transport):
        self.transport = transport
        print('port opened', transport)

    def data_received(self, data):
        self.cache.extend(data)
        line_end = b'\n'
        while True:
            head, sep, tail = self.cache.partition(line_end)
            if not sep:
                break
            self.cache = tail

            line = head.decode('ascii').strip()
            if line and line[0] == 'D' and 'RSSI' in line:
                print(line)
            if not line or line[0] != 'D':
                continue
            line = line[1:]
            if DEBUG:
                print(line, len(line))
            if len(line) < 4:
                print('too short', line)
                continue

            expected_length = int(line[0:2], base=16)
            hex_data = line[2:]

            if len(hex_data) != expected_length * 2:
                print(f'data length missmatch got {len(hex_data)}, wanted {expected_length * 2}')
                continue
            try:
                decoded = bytes.fromhex(hex_data)
            except Exception:
                print('unable to decoder serial')
                pass
            update_task = asyncio.get_event_loop().create_task(self.processor.process(decoded))
            update_task.add_done_callback(lambda x: None)

    def connection_lost(self, exc):
        print('port closed')
        self.emergency_stop.set_exception(exc)


class WeaterServerProtocol(asyncio.DatagramProtocol):
    def __init__(self, emergency_stop, processor):
        self.processor = processor
        self.emergency_stop = emergency_stop

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        update_task = asyncio.get_event_loop().create_task(self.processor.process(data, addr=addr))
        update_task.add_done_callback(lambda x: None)

    def error_received(self, exc):
        '''Called when a send or receive operation raises an OSError.

        (Other than BlockingIOError or InterruptedError.)
        '''
        print('sum udp error', exc)
        self.emergency_stop.set_exception(exc)


def prepare_socket():
    MCAST_GRP = '239.87.84.82'  # (239.W.T.R)

    host, port = cfg['bind']['address'].split(':')
    # host = ""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    # sock.setsockopt(socket.SOL_SOCKET, socket.SO_BINDTODEVICE, b"enp6s0")
    # host = ''
    sock.bind((host, int(port)))
    mreq = struct.pack('4sl', socket.inet_aton(MCAST_GRP), socket.INADDR_ANY)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    return sock


async def udp_receiver(patocol):
    sock = patocol.sock
    loop = asyncio.get_event_loop()

    emergency_stop = loop.create_future()

    transport, protocol = await loop.create_datagram_endpoint(lambda: WeaterServerProtocol(emergency_stop, patocol), sock=sock)
    await protocol.emergency_stop
    transport.close()
    sock.close()
    print('boom')


async def uart_receiver(patocol):
    serial_dev = cfg['bind'].get('serial_dev')
    if not serial_dev:
        while True:
            await asyncio.sleep(100000)
        return
    serial_baud = int(cfg['bind'].get('serial_baud', 115200))
    loop = asyncio.get_event_loop()
    emergency_stop = loop.create_future()
    proto = WeaterServerUARTProtocol(emergency_stop, patocol)
    # soo there is some special options that should be enabled to
    # make serial happy?
    coro = serial_asyncio.create_serial_connection(
        loop, lambda: proto, serial_dev, baudrate=serial_baud)
    transport, protocol = await coro
    await protocol.emergency_stop


async def screen_sender(patocol: WeatherProcessor):
    await patocol.st.run()


async def main():
    # rsock, wsock = asyncio.create
    # create tasks
    # asyncio.seri
    sock = prepare_socket()
    proceessor = WeatherProcessor(sock)
    udp_task = udp_receiver(proceessor)
    uart_task = uart_receiver(proceessor)
    screen_task = screen_sender(proceessor)
    x = await asyncio.wait([udp_task, uart_task, screen_task], return_when=asyncio.FIRST_COMPLETED)
    print('should not be here', x)
    # exit(1)


asyncio.run(main())

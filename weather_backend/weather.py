#!/usr/bin/env python3

import asyncio
import datetime
import json
import logging
import socket
import struct
import sys
import time
import traceback
from os import mkdir
from os.path import exists, isdir

import serial_asyncio
from asyncio_mqtt import Client
import libscrc

import draw
import fetch
import protocol
from config import load_config
from protocol import (HumiditySensor, PressureSensor, SoilMoistureSensor,
                      TempSensor, VOCSensor, VoltSensor)

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
    def __init__(self, cfg):
        self.cfg = cfg
        self.sock = self._prepare_socket()
        self.st = ScreenThread(self.sock)
        self.mqtt = None
        # hold active devices, prune if timeout is larger than 30min
        self.sensors = {}
        asyncio.run_coroutine_threadsafe(
            self._prepare_mqtt(), asyncio.get_running_loop())

    def _prepare_socket(self):
        MCAST_GRP = '239.87.84.82'  # (239.W.T.R)

        host, port = self.cfg['bind']['address'].split(':')
        # host = ""
        sock = socket.socket(
            socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        # sock.setsockopt(socket.SOL_SOCKET, socket.SO_BINDTODEVICE, b"enp6s0")
        # host = ''
        sock.bind((host, int(port)))
        mreq = struct.pack('4sl', socket.inet_aton(
            MCAST_GRP), socket.INADDR_ANY)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        return sock

    async def _prepare_mqtt(self):
        mqtt_cfg = self.cfg.get('mqtt')
        if not mqtt_cfg:
            print('no MQTT config')
            return

        broker = mqtt_cfg.get('broker')
        if not broker:
            print('no broker configured')
            return

        self.mqtt = Client(hostname=broker, client_id='Weather-Backend')
        ok = await self.mqtt.connect()

        return ok

    async def run(self):
        # 1) connect to broker
        udp_task = udp_receiver(self)
        uart_task = uart_receiver(self)
        screen_task = screen_sender(self)
        tasks = [udp_task, uart_task, screen_task]
        x = await asyncio.wait(
            [asyncio.create_task(coro) for coro in tasks],
            return_when=asyncio.FIRST_COMPLETED
        )
        return x

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
                sensors['gas_raw'] = fetch.GasResistance(sid.gas_raw)
            elif module_name:
                sensors[module_name] = converter(sid.value)
            else:
                print(f'Unknown module: {sid.MODULE_ID}')

        await RRD.add(df.device_id, sensors.values())

        # broadcast
        await self.mqtt.publish(topic='weather/device', payload=df.device_id)
        for k, v in sensors.items():
            topic = f'weather/{df.device_id}/{k}'
            await self.mqtt.publish(topic=topic, payload=v)

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
                print(
                    f'data length missmatch got {len(hex_data)}, wanted {expected_length * 2}')
                continue
            try:
                decoded = bytes.fromhex(hex_data)
            except Exception:
                print('unable to decoder serial')
                pass
            update_task = asyncio.get_running_loop().create_task(
                self.processor.process(decoded))
            update_task.add_done_callback(lambda x: None)

    def connection_lost(self, exc):
        print('port closed')
        self.emergency_stop.set_exception(exc)


class WeatherServerHC12UARTProtocol(WeaterServerUARTProtocol):
    def __init__(self, emergency_stop, processor):
        super().__init__(emergency_stop, processor)

    def _try_parse(self):
        # 3 bytes header, 1 byte checksum
        if len(self.cache) < 4:
            return None

        for index in range(len(self.cache)):
            raw_version = self.cache[index]
            version_zero = (raw_version & 0b00001111) >> 0
            version = (raw_version & 0b11110000) >> 4

            # print(version, version_zero)
            if version_zero != 0:
                # reserved bits are set
                continue
            if version != 1:
                # unexpected version
                continue

            raw_size = self.cache[index + 1]
            size_zero = (raw_size & 0b00000011) >> 0
            size = (raw_size & 0b11111100) >> 2
            # print(size, size_zero)

            if size_zero != 0:
                # reserved bits are set
                continue
            if size > 63:
                # size is too big, only 63 bytes
                continue

            raw_routing = self.cache[index + 2]
            packet_to = (raw_routing & 0b00001111) >> 0
            packet_from = (raw_routing & 0b11110000) >> 4
            # print(packet_from, '->', packet_to)

            if packet_to == packet_from:
                # no-go: packet from self to self?
                continue

            if index + 3 + size >= len(self.cache):
                # no-go packet would end after buffer
                continue

            raw_payload = self.cache[index + 3:index + 3 + size]
            packet_crc8 = self.cache[index + 3 + size]

            caclulated_crc8 = libscrc.dvb_s2(self.cache[index:index + 3 + size])
            if caclulated_crc8 != packet_crc8:
                continue
            # print("packet VALID")
            # roll buffer to left by packet size
            self.cache = self.cache[index + 3 + size + 1:]
            return bytes(raw_payload)

    def data_received(self, data):
        self.cache.extend(data)
        while True:
            packet = self._try_parse()
            if not packet:
                return
            update_task = asyncio.get_running_loop().create_task(
                self.processor.process(packet))
            update_task.add_done_callback(lambda x: None)


class WeaterServerProtocol(asyncio.DatagramProtocol):
    def __init__(self, emergency_stop, processor):
        self.processor = processor
        self.emergency_stop = emergency_stop

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        update_task = asyncio.get_running_loop().create_task(
            self.processor.process(data, addr=addr))
        update_task.add_done_callback(lambda x: None)

    def error_received(self, exc):
        '''Called when a send or receive operation raises an OSError.

        (Other than BlockingIOError or InterruptedError.)
        '''
        print('sum udp error', exc)
        self.emergency_stop.set_exception(exc)


async def udp_receiver(patocol):
    sock = patocol.sock
    loop = asyncio.get_running_loop()

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
    loop = asyncio.get_running_loop()
    emergency_stop = loop.create_future()
    serial_protocol = cfg['bind'].get('serial_protocol', 'HEX')
    if serial_protocol == 'HEX':
        proto = WeaterServerUARTProtocol(emergency_stop, patocol)
    else:
        proto = WeatherServerHC12UARTProtocol(emergency_stop, patocol)
    # soo there is some special options that should be enabled to
    # make serial happy?
    coro = serial_asyncio.create_serial_connection(
        loop, lambda: proto, serial_dev, baudrate=serial_baud)
    transport, protocol = await coro
    await protocol.emergency_stop


async def screen_sender(patocol: WeatherProcessor):
    await patocol.st.run()


async def mqtt_notifier():
    while True:
        # broadcast active devices
        print('faketify')
        await asyncio.sleep(30)


async def main():
    # rsock, wsock = asyncio.create
    # create tasks
    # asyncio.seri
    processor = WeatherProcessor(cfg)
    error = await processor.run()
    print('should not be here', error)
    # exit(1)


asyncio.run(main())

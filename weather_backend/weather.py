#!/usr/bin/env python3

import asyncio
from collections.abc import Sequence
import datetime
import json
import logging
from numbers import Number
import socket
import struct
import sys
import time
import math
from os import mkdir
from os.path import exists, isdir

import serial_asyncio
import libscrc

import fetch
import protocol
from config import load_config
from protocol import (HumiditySensor, PressureSensor, SimpleFloat32, SoilMoistureSensor, THPCompoundV2,
                      TempSensor, VOCSensor, VoltSensor, WindSensor, THPCompound, WindSpeedDirection, BaseModule)

DEBUG = False
USE_ZMQ = True

if USE_ZMQ:
    import zmq
    import zmq.asyncio

def with_id(func):
    def _f(sensor: BaseModule):
        return func(value=sensor.value, id=sensor.id)
    return _f

def _simple_float(sensor: BaseModule):
    if sensor.id() == 'iaq_static':
       return fetch.StaticIaq(sid.value)
    if sensor.id() == 'iaq':
       return fetch.Iaq(sid.value)
    if sensor.id() == 'co2':
       return fetch.Co2(sid.co2)
    if sensor.id() == 'gas_raw':
       return fetch.GasResistance(sid.gas_raw)

    raise Exception(f'not supported: {sensor.id()}')


stype2name = {
    TempSensor.MODULE_ID: ('temperature', with_id(fetch.Temp)),
    # scale Pa to hPa
    PressureSensor.MODULE_ID: ('pressure', with_id(lambda value, id=None: fetch.Pres(value * 0.01, id=id))),
    HumiditySensor.MODULE_ID: ('humidity', with_id(fetch.Humidity)),
    # scale mV to V
    VoltSensor.MODULE_ID: ('volt', with_id(lambda value, id=None: fetch.Volt(value * 0.001))),
    SoilMoistureSensor.MODULE_ID: ('soil', fetch.Humidity),
    VOCSensor.MODULE_ID: ('voc', None),
    WindSensor.MODULE_ID: ('wind', fetch.WindSpeed),
    THPCompound.MODULE_ID: ('thp', None),
    WindSpeedDirection.MODULE_ID: ('wind+dir', None),
    THPCompoundV2.MODULE_ID: ('thp2', None),
    SimpleFloat32.MODULE_ID: (None, _simple_float)
}

logging.basicConfig(format='%(asctime)s %(message)s')

cfg = load_config('./config.toml')
# check if we have storage DIR
storage_path = str(cfg['storage']['path'])
if not exists(storage_path):
    mkdir(storage_path)
if not isdir(storage_path):
    print(f'storage path is not directory: {storage_path}')
    exit(1)

DB = fetch.SQLiteDB(storage_path, ro=True)


class WOutEncoder(json.JSONEncoder):
    def default(self, o):
        if hasattr(o, 'value'):
            return o.value
        raise Exception('boom')


class WeatherProcessor:
    def __init__(self, cfg, *, db=None, sockets=None):
        self.cfg = cfg
        self.sock = sockets if sockets is not None else list(self._prepare_socket())
        self.zmq = None
        # hold active devices, prune if timeout is larger than 30min
        self.sensors = {}
        self.db = db if db is not None else DB
        if USE_ZMQ:
            self._prepare_zmq()

    def _prepare_socket(self):
        MCAST_GRP = '239.87.84.82'  # (239.W.T.R)

        for bind in self.cfg['bind']:
            if 'address' not in bind:
                continue

            host, port = bind['address'].split(':')
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
            yield sock

    if USE_ZMQ:
        def _prepare_zmq(self):
            zmq_cfg = self.cfg.get('zmq')
            if not zmq_cfg:
                print('no ZMQ config')
                return

            self._zmq_ctx = zmq.asyncio.Context()
            self.zmq = self._zmq_ctx.socket(zmq.PUB)
            self.zmq.bind(zmq_cfg['url'])

    async def run(self):
        # 1) connect to broker
        # udp_task = file_receiver(self)
        udp_task = list(udp_receiver(self))
        uart_task = list(uart_receiver(self))
        tasks  = udp_task + uart_task
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

        rcvtime = datetime.datetime.now(datetime.UTC).isoformat()
        sensors = {}

        for sid in df.modules:
            if sid.MODULE_ID not in stype2name:
                print('Unsupported module id:', sid.MODULE_ID)
                continue

            module_name, converter = stype2name[sid.MODULE_ID]

            if sid.MODULE_ID == protocol.ScreenSensor.MODULE_ID:
                await self.st.add_screen(df.device_id, addr)
                continue

            if sid.MODULE_ID == protocol.WindSensor.MODULE_ID or sid.MODULE_ID == protocol.WindSpeedDirection.MODULE_ID:
                # store in db with 10s "delays" counted backward from last entry
                snapshot_time = fetch.now()

                reversed_sensors = []
                for v in reversed(sid.value):
                    if v:
                        if isinstance(v, Number):
                            # old one
                            reversed_sensors.append(((fetch.WindSpeed(v),), snapshot_time))
                        elif isinstance(v, Sequence) and len(v) == 2:
                            reversed_sensors.append(((fetch.WindSpeed(v[0]), fetch.WindDirection(v[1])), snapshot_time))
                        else:
                            print("unknown value", v)
                    snapshot_time -= datetime.timedelta(seconds=10)

                if len(reversed_sensors[-1][0]) == 2:
                    # ((speed, direction), time)
                    # there is some weird bug with first speed value
                    # keep diraction, but replace speed with next-one
                    avg = sum(x[0][0].value for x in reversed_sensors[:-1]) / (len(reversed_sensors) - 1)

                    ((first_speed, first_dir), first_timestamp) = reversed_sensors[-1]

                    print("AVG:", avg, "first (aka last)", first_speed)

                    if first_speed.value > 4 * avg:
                        print("botched first speed value, replace with next")
                        reversed_sensors[-1] = (
                                (reversed_sensors[-2][0][0], first_dir),
                                first_timestamp,
                        )

                for value, current_time in reversed(reversed_sensors):
                    print('wind', value)
                    self.db.add(df.device_id, value, current_time=current_time)

                # it's finally fixed and sensor contains already prescaled
                # values so no more thinking about bucket size and ticsk
                # radius is 60mm = 0.06m
                # V = 2 * pi * r * RPM/60
                # V = 2 * pi * 0.06 * n m/s
                # V = 2 * pi * 0.06 * n * 3.6 km/h
                speeds = [x[0][0].value for x in reversed_sensors]
                mean = sum(speeds) / len(speeds)
                def _to_kmh(v):
                    r = 0.06
                    return 2 * math.pi * r * v * 3.6
                print('wind sensor',
                        'min', min(speeds),
                        'mean', mean,
                        'mean (km/h)', _to_kmh(mean),
                        'max', max(speeds),
                        'max (km/h)', _to_kmh(max(speeds))
                )
                continue
            elif module_name:
                if converter:
                    result = converter(sid)
                    sensors[getattr(result, 'name', module_name)] = result
                else:
                    sensors[module_name] = sid.value
            else:
                print('should not happen')

        self.db.add(df.device_id, sensors.values())

        # broadcast
        if USE_ZMQ and self.zmq:
            await self.zmq.send_multipart([b'weather/device', str(df.device_id).encode('utf-8')])
            for k, v in sensors.items():
                topic = f'weather/{df.device_id}/{k}'.encode('utf-8')
                print(type(v))
                await self.zmq.send_multipart([topic, str(v).encode('utf-8')])

        if DEBUG:
            sensors['rcvtime'] = rcvtime
            as_json = json.dumps(sensors, cls=WOutEncoder)

            sys.stdout.write(as_json)
            sys.stdout.write('\n')
            sys.stdout.flush()


class WeatherServerHC12UARTProtocol(asyncio.Protocol):
    def __init__(self, emergency_stop, processor):
        self.emergency_stop = emergency_stop
        self.processor = processor
        self.cache = bytearray()

    def connection_lost(self, exc):
        print('port closed')
        self.emergency_stop.set_exception(exc)

    def connection_made(self, transport):
        self.transport = transport
        print('port opened', transport)

    def _try_parse(self):
        # 3 bytes header, 1 byte checksum
        if len(self.cache) < 4:
            print('cache:', self.cache, '(too short)')
            return None

        print('cache:', self.cache)
        # 1 -> as raw_size is at index + 1
        # 2 -> raw_size is at index + 2
        # 3 -> payload starts at index + 3
        for index in range(len(self.cache) - 2):
            packet_start = index
            raw_version = self.cache[index]
            version_zero = (raw_version & 0b00001111) >> 0
            version = (raw_version & 0b11110000) >> 4

            if version_zero != 0:
                # reserved bits are set
                continue
            if version not in (1, 2):
                # unexpected version
                continue

            raw_size = self.cache[index + 1]
            size_zero = (raw_size & 0b00000011) >> 0
            size = (raw_size & 0b11111100) >> 2
            print(size, size_zero)

            if size_zero != 0:
                # reserved bits are set
                continue
            if size > 63:
                # size is too big, only 63 bytes
                continue

            if version == 1:
                raw_routing = self.cache[index + 2]
                packet_to = (raw_routing & 0b00001111) >> 0
                packet_from = (raw_routing & 0b11110000) >> 4
                if packet_to == packet_from:
                    # no-go: packet from self to self?
                    print(packet_from, '->', packet_to)
                    continue
            elif version == 2:
                index -= 1
            else:
                print("not supported version", version)
                continue

            if index + 3 + size >= len(self.cache):
                # no-go packet would end after buffer
                print('no-go packet would end after buffer', index + 3 + size, len(self.cache))
                continue

            raw_payload = self.cache[index + 3:index + 3 + size]
            packet_crc8 = self.cache[index + 3 + size]

            caclulated_crc8 = libscrc.dvb_s2(self.cache[packet_start:index + 3 + size])
            if caclulated_crc8 != packet_crc8:
                continue
            print("packet VALID")
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


class WeatherServerProtocol(asyncio.DatagramProtocol):
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


def udp_receiver(patocol):
    loop = asyncio.get_running_loop()
    for sock in patocol.sock:
        async def x(sock):
            emergency_stop = loop.create_future()
            transport, protocol = await loop.create_datagram_endpoint(lambda: WeatherServerProtocol(emergency_stop, patocol), sock=sock)
            await protocol.emergency_stop
            transport.close()
            sock.close()
            print('boom')
        yield x(sock)

def uart_receiver(patocol):
    loop = asyncio.get_running_loop()
    for bind in cfg['bind']:
        if 'serial_dev' not in bind:
            continue

        serial_dev = str(bind['serial_dev'])
        if not serial_dev:
            continue

        async def x(serial_baud:int, serial_protocol:str, serial_dev:str):
            print('uart_receiver', serial_baud, serial_protocol)
            emergency_stop = loop.create_future()
            if serial_protocol == 'HC12':
                proto = WeatherServerHC12UARTProtocol(emergency_stop, patocol)
            else:
                raise Exception('unsupported protocol')
            # soo there is some special options that should be enabled to
            # make serial happy?
            coro = serial_asyncio.create_serial_connection(
                loop, lambda: proto, serial_dev, baudrate=serial_baud)
            transport, protocol = await coro
            await protocol.emergency_stop
        yield x(
            serial_baud=int(bind.get('serial_baud', 115200)),
            serial_protocol=bind.get('serial_protocol', 'HC12'),
            serial_dev=serial_dev,
        )


async def zmq_notifier():
    while True:
        # broadcast active devices
        print('faketify')
        await asyncio.sleep(30)

if __name__ == '__main__':
    async def main():
        # rsock, wsock = asyncio.create
        # create tasks
        # asyncio.seri
        processor = WeatherProcessor(cfg)

        error = await processor.run()
        print('should not be here', error)
        # exit(1)


    asyncio.run(main())

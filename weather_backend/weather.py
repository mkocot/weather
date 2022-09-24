#!/usr/bin/env python3

import socket
import json
import sys
import logging
import datetime
import base64
from os.path import exists, isdir
from os import mkdir
from threading import Lock, Thread, Event
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
    TempSensor.MODULE_ID: "temperature",
    PressureSensor.MODULE_ID: "pressure",
    HumiditySensor.MODULE_ID: "humidity",
    VoltSensor.MODULE_ID: "volt",
    SoilMoistureSensor.MODULE_ID: "soil",
    VOCSensor.MODULE_ID: "voc",
}

logging.basicConfig(format='%(asctime)s %(message)s')

cfg = load_config("./config.toml")
# check if we have storage DIR
storage_path = cfg["storage"]["path"]
if not exists(storage_path):
    mkdir(storage_path)
if not isdir(storage_path):
    print("rrd path is not directory: %s" % storage_path)
    exit(1)

RRD = fetch.RRD(storage_path)


class ScreenInfo:
    def __init__(self):
        self.deadline = 0
        self.state = 0
        self.sensor_idx = 0
        self.time_to_swith_state = 0
        self.addr = 'localhost'


class ScreenThread(Thread):
    _done = Event()
    _lock = Lock()
    _screens = {}
    _rrd = RRD

    def __init__(self):
        super().__init__()
        self.setDaemon(True)

    def run(self):
        while self._done.isSet:
            self._loop()
            self._done.wait(1)

    def _loop(self):
        now = time.time()
        try:
            self._lock.acquire(blocking=True)
            devices = list(self._screens.keys())
            for d in devices:
                if self._screens[d].deadline < now:
                    del self._screens[d]
            devices = self._screens.copy()
        finally:
            self._lock.release()

        # generate images
        for did, d in devices.items():
            if d.time_to_swith_state > now:
                continue
            d.time_to_swith_state = now + 5
            sensors = cfg["device"][did].get("screen")
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
            name = cfg["device"][sensor_id]["name"]
            # get data from last 8 hours
            raw_data = self._rrd.rrdfetch(sensor_id, start=8*60*60)
            # states
            # 0 -> overview
            # 1 -> temperature graph
            # 2 -> humidity graph
            # 3 -> pressure graph
            # 4 -> volate graph
            # then repeat for another sensor

            def _filter(data):
                return [x for x in data if x is not None]
            temp = _filter(raw_data["temp"])
            hum = _filter(raw_data["hum"])
            press = _filter(raw_data["pres"])
            volt = _filter(raw_data["volt"])
            if d.state == 0:
                image = draw.draw_overview(name, temp=temp[-1], hum=hum[-1],
                                           press=press[-1], volt=volt[-1],
                                           time=raw_data["time"][len(temp)-1])
            elif d.state == 1:
                image = draw.draw_graph("Temp", name, temp)
            elif d.state == 2:
                image = draw.draw_graph("Hum", name, hum)
            elif d.state == 3:
                image = draw.draw_graph("Pres", name, press)
            elif d.state == 4:
                image = draw.draw_graph("Volt", name, volt)
            else:
                image = draw.draw_overview(name)
            df = protocol.DataFrame()
            df.device_id = did
            df.message_to_broker = False
            df.modules = [
                protocol.ImagePush(128, 32, image)
            ]
            data = protocol.serialize(df)
            sock.sendto(data, (d.addr, 9696))
            d.state += 1
            if d.state > 4:
                d.sensor_idx += 1
                d.state = 0

    def add_screen(self, id, addr, timeout=120):
        # TODO: sensor 1 and sensor 2 is swapend on scrren vs web
        try:
            self._lock.acquire(blocking=True, timeout=2)
            screen = self._screens.get(id)
            if not screen:
                screen = ScreenInfo()
                self._screens[id] = screen
            screen.deadline = time.time() + timeout
            screen.addr = addr[0]
        finally:
            self._lock.release()




#st = ScreenThread()
# st.start()
# st.add_screen("e8db849381ec", ("10.0.0.28", 0))

class WeatherProcessor:
    def process(self, data):
        try:
            df = protocol.parse(data)
        except Exception as e:
            print(f"invalid data {data}, unable to parse:", e)
            return

        if not df.message_to_broker:
            return

        sensorsnum = len(df.modules)
        sensors = {
            "rcvtime": datetime.datetime.utcnow().isoformat(),
            "raw": base64.b64encode(data).decode('ascii')
        }
        for sid in df.modules:
            module_name = stype2name.get(sid.MODULE_ID)
            if module_name == "voc":
                sensors["iaq_static"] = sid.iaq_static
                sensors["iaq"] = sid.iaq
                sensors["co2"] = sid.co2
            elif module_name:
                sensors[module_name] = sid.value
            if sid.MODULE_ID == protocol.ScreenSensor.MODULE_ID:
                st.add_screen(df.device_id, addr)
        as_json = json.dumps(sensors)
        if len(sensors) == 9:
            temp = fetch.Temp(sensors["temperature"])
            hum = fetch.Humidity(sensors["humidity"])
            pres = fetch.Pres(sensors["pressure"] * 0.01)  # scale Pa to hPa
            volt = fetch.Volt(sensors["volt"] * 0.001)  # scale mV to V
            iaq = fetch.Iaq(sensors["iaq"])
            iaq_static = fetch.StaticIaq(sensors["iaq_static"])
            co2 = fetch.Co2(sensors["co2"])
            RRD.add(df.device_id, (temp, hum, pres, volt, iaq, iaq_static, co2))
            # mqtt.publish("sensor/" + df.device_id + "/temperature", temp)
            # mqtt.publish("sensor/" + df.device_id + "/humidity", hum)
        if len(sensors) == 6:
            temp = fetch.Temp(sensors["temperature"])
            hum = fetch.Humidity(sensors["humidity"])
            pres = fetch.Pres(sensors["pressure"] * 0.01)  # scale Pa to hPa
            volt = fetch.Volt(sensors["volt"] * 0.001)  # scale mV to V
            RRD.add(df.device_id, (temp, hum, pres, volt))
            # mqtt.publish("sensor/" + df.device_id + "/temperature", temp)
            # mqtt.publish("sensor/" + df.device_id + "/humidity", hum)
        elif len(sensors) == 3 and 'soil' in sensors:
            temp = 20  # sensors["temperature"]
            hum = sensors["soil"]
            pres = 1013  # sensors["pressure"] * 0.01  # scale Pa to hPa
            volt = 3.3  # sensors["volt"] * 0.001  # scale mV to V
            RRD.add(df.device_id, (temp, hum, pres, volt))
            # mqtt.publish("sensor/" + df.device_id + "/temperature", temp)
            # mqtt.publish("sensor/" + df.device_id + "/humidity", hum)
        else:
            #
            return
        sys.stdout.write(as_json)
        sys.stdout.write("\n")
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
        line_end = b'\r\n'
        while True:
            head, sep, tail = self.cache.partition(line_end)
            if not sep:
                break
            self.cache = tail

            line = head.decode('ascii')
            if not line or line[0] != "D":
                continue
            line = line[1:]

            print(line, len(line))
            if len(line) < 4:  # expected_length (2) + targetid(2)
                print("too short", line)
                continue

            expected_length = int(line[0:2], base=16)
            hex_data = line[2:]

            if len(hex_data) != expected_length * 2:
                print("data length missmatch", "got", len(
                    hex_data), "wanted", expected_length * 2)
                continue
            try:
                decoded = bytes.fromhex(hex_data)
            except Exception:
                print("unable to decoder serial")
                pass
            self.processor.process(decoded)

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
        self.processor.process(data)

    def error_received(self, exc):
        """Called when a send or receive operation raises an OSError.

        (Other than BlockingIOError or InterruptedError.)
        """
        print("sum udp error", exc)


async def udp_receiver(patocol):
    MCAST_GRP = '239.87.84.82'  # (239.W.T.R)

    host, port = cfg["bind"]["address"].split(":")
    # host = ""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    # sock.setsockopt(socket.SOL_SOCKET, socket.SO_BINDTODEVICE, b"enp6s0")
    # host = ''
    sock.bind((host, int(port)))
    mreq = struct.pack("4sl", socket.inet_aton(MCAST_GRP), socket.INADDR_ANY)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    loop = asyncio.get_event_loop()

    emergency_stop = loop.create_future()

    transport, protocol = await loop.create_datagram_endpoint(lambda: WeaterServerProtocol(emergency_stop, patocol), sock=sock)
    await protocol.emergency_stop
    transport.close()
    sock.close()
    print("boom")
    print("szakalaka")


async def uart_receiver(patocol):
    serial_dev = cfg["bind"].get("serial_dev", "/dev/ttyUSB0")
    serial_baud = int(cfg["bind"].get("serial_baud", 115200))
    loop = asyncio.get_event_loop()
    emergency_stop = loop.create_future()
    proto = WeaterServerUARTProtocol(emergency_stop, patocol)
    # soo there is some special options that should be enabled to
    # make serial happy?
    coro = serial_asyncio.create_serial_connection(
        loop, lambda: proto, serial_dev, baudrate=serial_baud)
    transport, protocol = await coro
    await protocol.emergency_stop


async def screen_sender():
    while True:
        await asyncio.sleep(100000)


async def main():
    # rsock, wsock = asyncio.create
    # create tasks
    # asyncio.seri
    proceessor = WeatherProcessor()
    udp_task = udp_receiver(proceessor)
    uart_task = uart_receiver(proceessor)
    screen_task = screen_sender()
    x = await asyncio.wait([udp_task, uart_task, screen_task], return_when=asyncio.FIRST_COMPLETED)
    print("should not be here", x)
    # exit(1)


asyncio.run(main())

#!/usr/bin/env python3

import socket
import struct
import json
import sys
import logging
import datetime
import base64
import subprocess
import codecs
from os.path import exists, isdir, join
from os import mkdir
from threading import Lock, Thread, Event
import time
import fetch
from collections import OrderedDict
import draw 
import protocol
from protocol import TempSensor, PressureSensor, HumiditySensor, VoltSensor

from config import load_config


stype2name = {
    TempSensor.MODULE_ID: "temperature",
    PressureSensor.MODULE_ID: "pressure",
    HumiditySensor.MODULE_ID: "humidity",
    VoltSensor.MODULE_ID: "volt"
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

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
host, port = cfg["bind"]["address"].split(":")
sock.bind((host, int(port)))

RRD = fetch.RRD(storage_path)


s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

class ScreenInfo:
    deadline = 0
    state = 0
    sensor_idx = 0
    time_to_swith_state = 0


class ScreenThread(Thread):
    _done = Event()
    _lock = Lock()
    _screens: 'Map[str,ScreenInfo]' = {}
    _rrd = RRD

    def __init__(self):
        super().__init__()
        self.setDaemon(True)

    def run(self):
        print("runned")
        while self._done.isSet:
            self._loop()
            self._done.wait(1)

    def _loop(self):
        now = time.time()
        try:
            self._lock.acquire(blocking=True)
            devices = self._screens.keys()
            for d in devices:
                if self._screens[d].deadline < now:
                    del self._screens[d]
            devices = self._screens.copy()
        finally:
            self._lock.release()

        # generate images 
        for did, d in devices.items():
            if d.time_to_swith_state > now:
                print("not yet")
                continue
            d.time_to_swith_state = now + 5
            sensors = cfg["device"][did].get("screen")
            if not sensors:
                continue
            sensors_names = list(sensors.keys())
            if d.sensor_idx > len(sensors_names):
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
                image = draw.draw_overview(name, temp=temp[-1], hum=hum[-1], press=press[-1], volt=volt[-1])
            elif d.state == 1:
                image = draw.draw_graph("T", name, temp)
            elif d.state == 2:
                image = draw.draw_graph("H", name, hum)
            elif d.state == 3:
                image = draw.draw_graph("P", name, press)
            elif d.state == 4:
                image = draw.draw_graph("V", name, volt)
            else:
                image = draw.draw_overview(name)
            df = protocol.DataFrame
            df.device_id = sensor_id
            df.message_to_broker = False
            df.modules = [
                protocol.ImagePush(128, 32, image)
            ]
            data = protocol.serialize(df)
            s.sendto(data, ("255.255.255.255",19696))
            d.state += 1
            if d.state > 4:
                d.sensor_idx += 1
                d.state = 0


    def add_screen(self, id, timeout=120):
        try:
            self._lock.acquire(blocking=True, timeout=2)
            screen = self._screens.get(id)
            if not screen:
                screen = ScreenInfo()
                self._screens[id] = screen
            screen.deadline = time.time() + timeout
        finally:
            self._lock.release()

    
st = ScreenThread()
st.start()
st.add_screen("e8db849381ec")

while True:
    # Todo: add MAC
    # todo: add sensor number?
    logging.info("wait for data")
    data, addr = sock.recvfrom(1500)

    df = protocol.parse(data)

    if not df.message_to_broker:
        continue

    sensorsnum = len(df.modules)
    if sensorsnum < 3 or sensorsnum > 10:
        logging.warning("invalid sensors num")
        continue
    sensors = {
        "rcvtime": datetime.datetime.utcnow().isoformat(),
        "raw": base64.b64encode(data).decode('ascii')
    }
    for sid in df.modules:
        module_name = stype2name.get(sid.MODULE_ID)
        if module_name:
            sensors[module_name] = sid.value
        if sid.MODULE_ID == protocol.ScreenSensor.MODULE_ID:
            st.add_screen(df.device_id)

    temp = sensors["temperature"]
    hum = sensors["humidity"]
    pres = sensors["pressure"] * 0.01  # scale Pa to hPa
    volt = sensors["volt"] * 0.001  # scale mV to V
    RRD.add(df.device_id, (temp, hum, pres, volt))
    sys.stdout.write(json.dumps(sensors))
    sys.stdout.write("\n")
    sys.stdout.flush()

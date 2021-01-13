#!/usr/bin/env python3

import socket
import struct
import json
import sys
import logging
import datetime
import base64
import subprocess
import math
import codecs
from os.path import exists

# TODO(m): Increase step to 600, Timeout to 1200
STEP = 300
START = "N"
MINUTE = 60
HOUR = 60 * MINUTE
DAY = 24 * HOUR
YEAR = 370 * DAY # Yes, longer than 'real' year

SAMPLES_Y = YEAR/STEP


stype2name = {1: "temperature", 2: "pressure", 3: "humidity", 4: "time", 5: "volt" }
VERSION = 1
MAGIC = 87 # ASCII 'W'
HEADER_SIZE = 8
TIME_OFFSET = 946684800

logging.basicConfig(format='%(asctime)s %(message)s')

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", 9696))

while True:
    # Todo: add MAC
    # todo: add sensor number?
    logging.info("wait for data")
    data, addr = sock.recvfrom(32)
    if data[0] != MAGIC:
        logging.warning("invalid magic: {}".format(data[0]))
        continue
    if data[1] != VERSION:
        logging.warning("invalid version: {}".format(data[1]))
        continue
    deviceid = data[2:7]
    # cast as hex string
    idhex = codecs.encode(deviceid, "hex").decode("utf-8")
    rrdfile = "sensors_%s.rrd" % idhex
    if not exists(rrdfile):
        subprocess.run(["rrdtool", "create", rrdfile,
                "--step", str(STEP),
                "--start", str(START),
                "DS:temp:GAUGE:10m:-30:50",
                "DS:hum:GAUGE:10m:0:100",
                "DS:pres:GAUGE:10m:600:1200",
                "DS:volt:GAUGE:10m:0:5",
                "RRA:AVERAGE:0.5:1:%d" % SAMPLES_Y # 1 YEAR by STEP Save 1 YEAR by STEP resolution
                 ])

    sensorsnum = data[HEADER_SIZE]
    if sensorsnum < 3 or sensorsnum > 10:
        logging.warning("invalid sensors num")
        continue
    sensors = {"rcvtime": datetime.datetime.utcnow().isoformat(), "raw": base64.b64encode(data).decode('ascii')}
    for sid in range(sensorsnum):
        stype = data[HEADER_SIZE+1+sid*5]
        if stype == 0:
            logging.warning("unknown sensor: 0")
            break
        if stype == 5:
            sensors[stype2name[stype]] = struct.unpack('I', data[HEADER_SIZE+1+sid*5+1:HEADER_SIZE+1+sid*5+1+4])[0]
        elif stype == 4:
            sensors[stype2name[stype]] = TIME_OFFSET + struct.unpack('i', data[HEADER_SIZE+1+sid*5+1:HEADER_SIZE+1+sid*5+1+4])[0]
            #ddd = datetime.datetime.fromtimestamp(sensors[stype2name[stype]])
            #print("ts", ddd)
        else:
            sensors[stype2name[stype]] = struct.unpack('f', data[HEADER_SIZE+1+sid*5+1:HEADER_SIZE+1+sid*5+1+4])[0]
    temp = sensors["temperature"]
    hum = sensors["humidity"]
    pres = sensors["pressure"] * 0.01 # scale Pa to hPa
    volt = sensors["volt"] * 0.001 # scale mV to V
    subprocess.run(["rrdtool", "update", rrdfile, "N:%f:%f:%f:%f" % (temp, hum, pres, volt)])
    sys.stdout.write(json.dumps(sensors))
    sys.stdout.write("\n")
    sys.stdout.flush()

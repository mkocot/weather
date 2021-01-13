#!/usr/bin/env python3
# temp: 10m hearbeat <0;50>
# hum : 10m hearbeat <0; 100>
# pres: 10m hearbeat <60000; 120000> == <600hPa; 1200hPa>

from os.path import isfile
from os import remove
import subprocess
import math

SENSORS = "sensors.rrd"
START = 1023654125
STEP = 300

MINUTE = 60
HOUR = 60 * MINUTE
DAY = 24 * HOUR
YEAR = 370 * DAY # Yes, longer than 'real' year

SAMPLES_Y = YEAR/STEP
SAMPLES_W = (DAY * 7)/STEP

isfile(SENSORS) and remove(SENSORS)

subprocess.run(["rrdtool", "create", SENSORS,
	"--step", str(STEP),
	"--start", str(START),
	"DS:temp:GAUGE:10m:-30:50",
	"DS:hum:GAUGE:10m:0:100",
	"DS:pres:GAUGE:10m:600:1200",
	"RRA:AVERAGE:0.5:1:%d" % SAMPLES_W, # 1 Week by STEP Save 1 YEAR by STEP resolution
        "RRA:AVERAGE:0.5:12:%d" % (370 * 24), # 1 Month By hours
        "RRA:AVERAGE:0.5:144:%d" % (370 * 2),
         ])


#	RRA:AVERAGE:0.5:1d:1M \
#	RRA:AVERAGE:0.5:1M:1y

# feed fake data
EVENTS = 288 * 400
for step in range(EVENTS):
    stamp=START + STEP*step + 1
    temp = (step/EVENTS)*25 + math.sin(step/5) * 3
    hum = 50
    pres = 90000 / 100.0
    subprocess.run(["rrdtool", "update", SENSORS, "%d:%f:%f:%f" % (stamp, temp, hum, pres)])
    if step % 100 == 0:
        #print(temp)
        print(step + 1, "/", EVENTS)

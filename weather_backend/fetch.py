#!/usr/bin/env python3
import subprocess
import json
import math

TIME = 24 * 60 * 60
SENSOR_1_NAME = "e09806259a"
SENSOR_2_NAME = "24a1603048"


def rrdfetch(name):
    RRDFILE = "sensors_%s.rrd" % name

    # Order of date is equal to create
    # temp
    # hum
    # pres
    # volt
    # function push(A,B) { A[length(A)+1] = B }

    # NOTE(m): We should ensure now from graph and now from fetch matches!
    # Otherwises values will be shifted by one (in our case 10minutes)

    proc = subprocess.Popen([
        "rrdtool", "fetch", RRDFILE, "AVERAGE", "--start",
        "now-%d" % TIME, "--end", "now"],
        universal_newlines=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL)
    try:
        outs, _ = proc.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        outs, _ = proc.communicate()

    data = {}
    index2name = {}
    lines = outs.splitlines()
    timebegin = 0
    timeend = 0
    # remove nan at end
    while len(lines):
        split = lines[-1].split()
        if not all(x == "nan" for x in split[1:]):
            break
        lines.pop()

    for line in lines:
        values = line.split()
        if not values:
            continue
        if not index2name:
            for name in values:
                index2name[len(data)] = name
                data[name] = []
            continue
        timestamp = int(values[0][:-1])
        if timebegin == 0:
            timebegin = timestamp
        timeend = timestamp

        for i, n in index2name.items():
            v = float(values[1 + i])
            if math.isnan(v):
                v = None
            data[n].append(v)
    return (data, timebegin, timeend)


data1, st, ed = rrdfetch(SENSOR_1_NAME)
data2, _, _ = rrdfetch(SENSOR_2_NAME)
print(
    json.dumps({
        "begin": st,
        "end": ed,
        SENSOR_1_NAME: data1,
        SENSOR_2_NAME: data2,
    })
)

#!/usr/bin/env python3
import argparse
import time
import datetime
import json
from pathlib import Path

import bottle

import fetch

parser = argparse.ArgumentParser()
parser.add_argument("--address", default="127.0.0.1:8086")
parser.add_argument("--static-dir", default=".")
parser.add_argument("--data-dir", default=".")
args = parser.parse_args()

static_dir = Path(args.static_dir) / 'web/graph'

def get_rrd() -> fetch.SQLiteDB:
    return fetch.SQLiteDB(args.data_dir)


@bottle.get("/<name>")
def serve_static(name):
    return bottle.static_file(name, static_dir)


@bottle.get("/")
def index():
    return bottle.static_file('index.html', static_dir)


@bottle.get("/data/<id>/last.json")
def data_last(id: str):
    data = get_rrd().lastupdate(id)
    return data


def lerp(a, b, t):
    return (1 - t) * a + t * b


def filter_data(data):
    modules = set(data.keys())
    modules.discard("time")
    for m in modules:
        values = data[m]
        # create fake values
        for i in range(len(values)):
            if values[i]:
                continue
            # ok we got datapoint without value
            if i > 0 and values[i - 1]:
                first_point = values[i - 1]
            else:
                # first datapoint without value, this is bad
                continue
            segments = 2
            next_value = None
            for j in range(i + 1, len(values)):
                next_value = values[j]
                if next_value:
                    break
                segments += 1
            if not next_value:
                # no more valid point after index 'i'
                break
            # lerp values
            values[i] = lerp(first_point, next_value, 1.0 / segments)

    return data


def _last_from_sensors(rrd, sensors):
    result = [rrd.last(x) for x in sensors]
    lasts = max([x for x in result if x])
    if not lasts:
        lasts = 0
    return datetime.datetime.fromtimestamp(lasts, tz=datetime.timezone.utc)


def _data_from_sensors(rrd, sensors):
    result = {}
    datas = [rrd.rrdfetch(x) for x in sensors]

    for idx in range(len(sensors)):
        s = sensors[idx]
        data = datas[idx]
        if "time" not in data:
            now = int(time.time())
            data["time"] = [now - 600, now]
        time_slots = data.pop("time")
        data = filter_data(data)
        tick = time_slots[1] - time_slots[0]

        data["clock"] = {
            "tick": tick,
            "start": time_slots[0],
            "count": len(time_slots),
        }
        result[s] = data

    return result


@bottle.get("/data.json")
def data():
    rrd = get_rrd()
    # ec62609d4998 - outside
    sensors = ["e09806259a66", "24a1603048ba", "ec62609d4998"]
    last = _last_from_sensors(rrd, sensors)
    lm = last.strftime("%a, %d %b %Y %H:%M:%S GMT")
    ims = bottle.request.environ.get('HTTP_IF_MODIFIED_SINCE')
    if ims:
        ims = bottle.parse_date(ims.split(";")[0].strip())

    if ims is not None and ims >= last.timestamp():
        headers = {
            'Last-Modified': lm
        }
        return bottle.HTTPResponse(status=304, **headers)

    resp = _data_from_sensors(rrd, sensors)

    # debug compare clocks
    clock_data = None
    for s in sensors:
        if not clock_data:
            clock_data = resp[s]["clock"]
            continue
        if clock_data != resp[s]["clock"]:
            print("diff", s, clock_data, resp[s]["clock"])
    resp["clock"] = clock_data
    resp = json.dumps(resp)
    headers = {
        'Content-Length': len(resp),
    }
    return bottle.HTTPResponse(resp, **headers)


def main():
    host, port = args.address.split(":")
    # privide loop, for old version of python
    bottle.run(host=host, port=int(port), debug=True, quiet=False)


main()

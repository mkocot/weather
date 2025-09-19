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

def get_db() -> fetch.SQLiteDB:
    return fetch.SQLiteDB(args.data_dir)

@bottle.get("/api/v1/sensor/<name>")
def api_sensor(name):
    return "999"

@bottle.get("/<name>")
def serve_static(name):
    return bottle.static_file(name, static_dir)


@bottle.get("/")
def index():
    return bottle.static_file('index.html', static_dir)


@bottle.get("/data/<id>/last.json")
def data_last(id: str):
    data = get_db().lastupdate(id)
    return data


def lerp(a, b, t):
    return (1 - t) * a + t * b


def filter_data(data):
    return data
    modules = set(data.keys())
    modules.discard("time")
    for m in modules:
        values = data[m]
        # create fake values
        for i in range(len(values)):
            if values[i] is None:
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
                if next_value is not None:
                    break
                segments += 1
            if next_value is None:
                # no more valid point after index 'i'
                break
            # lerp values
            values[i] = lerp(first_point, next_value, 1.0 / segments)

    return data


def _last_from_sensors(db, sensors):
    result = [db.last(x) for x in sensors]
    lasts = max([x for x in result if x])
    if not lasts:
        lasts = 0
    return datetime.datetime.fromtimestamp(lasts, tz=datetime.timezone.utc)


def _data_from_sensors(db, sensors):
    result = {}
    datas = [db.fetch_raw(x) for x in sensors]

    for idx in range(len(sensors)):
        s = sensors[idx]
        data = datas[idx]
        if "timestamp" not in data:
            now = int(time.time())
            data["timestamp"] = [now - 600, now]
        data = filter_data(data)

        result[s] = data

    return result


@bottle.get("/data.json")
def data():
    db = get_db()
    # ec62609d4998 - outside
    sensors = ["e09806259a66", "24a1603048ba", "ec62609d4998"]
    last = _last_from_sensors(db, sensors)
    lm = last.strftime("%a, %d %b %Y %H:%M:%S GMT")
    ims = bottle.request.environ.get('HTTP_IF_MODIFIED_SINCE')
    if ims:
        ims = bottle.parse_date(ims.split(";")[0].strip())

    if ims is not None and ims >= last.timestamp():
        headers = {
            'Last-Modified': lm
        }
        return bottle.HTTPResponse(status=304, **headers)

    resp = _data_from_sensors(db, sensors)

    # debug compare clocks
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

#!/usr/bin/env python3
import argparse
import asyncio
import datetime
import sys
import time

import quart

import fetch

parser = argparse.ArgumentParser()
parser.add_argument("--address", default="127.0.0.1:8086")
parser.add_argument("--static-dir", default=".")
parser.add_argument("--data-dir", default=".")
args = parser.parse_args()


app = quart.Quart(__name__, static_url_path='', static_folder=args.static_dir)


def get_rrd() -> fetch.RRD:
    return fetch.RRD(args.data_dir)


@app.route("/<name>")
async def serve_static(name):
    return await quart.send_from_directory('web/graph', name)


@app.route("/")
async def index():
    return await quart.send_from_directory("web/graph", 'index.html')


@app.route("/data/<id>/last.json")
async def data_last(id: str):
    data = await get_rrd().lastupdate(id)
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


async def _last_from_sensors(rrd, sensors):
    result = asyncio.gather(*[rrd.last(x) for x in sensors])
    lasts = max([x for x in await result if x])
    if not lasts:
        lasts = 0
    return datetime.datetime.fromtimestamp(lasts, tz=datetime.timezone.utc)


async def _data_from_sensors(rrd, sensors):
    result = {}
    datas = await asyncio.gather(*[rrd.rrdfetch(x) for x in sensors])

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


@app.route("/data.json")
async def data():
    rrd = get_rrd()
    # ec62609d4998 - outside
    sensors = ["e09806259a66", "24a1603048ba", "ec62609d4998"]
    last = await _last_from_sensors(rrd, sensors)
    ims = quart.request.if_modified_since
    if ims and ims >= last:
        return "Unchanged", 304

    resp = await _data_from_sensors(rrd, sensors)

    # debug compare clocks
    clock_data = None
    for s in sensors:
        if not clock_data:
            clock_data = resp[s]["clock"]
            continue
        if clock_data != resp[s]["clock"]:
            print("diff", s, clock_data, resp[s]["clock"])
    resp["clock"] = clock_data

    response = quart.jsonify(resp)
    response.last_modified = last

    return response


def main():
    host, port = args.address.split(":")
    # privide loop, for old version of python
    if sys.version_info < (3, 10, 0):
        loop = asyncio.get_event_loop()
    else:
        loop = None

    app.run(host=host, port=int(port), loop=loop)


main()

#!/usr/bin/env python3
import bottle
import time
import fetch
import json
import asyncio
import concurrent

# this is dirty hack
loop = None


@bottle.get("/<name>")
def serve_static(name):
    return bottle.static_file(name, "web/graph")


@bottle.get("/")
def index():
    return bottle.static_file("index.html", "web/graph")


@bottle.get("/data/<id>/last.json")
def data_last(id: str):
    rrd = fetch.RRD(".")
    data = asyncio.run_coroutine_threadsafe(rrd.lastupdate(id), loop).result()
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
        return 0
    return lasts[0]


async def _data_from_sensors(rrd, sensors):
    result = {}

    datas = asyncio.gather(*[rrd.rrdfetch(x) for x in sensors])

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
    rrd = fetch.RRD(".")
    resp = "{}"
    headers = dict()
    last = 0
    # ec62609d4998 - outside
    sensors = ["e09806259a66", "24a1603048ba", "ec62609d4998"]
    for fn in sensors:
        lu = asyncio.run_coroutine_threadsafe(rrd.last(fn), loop).result()
        if not lu:
            continue
        if not last:
            last = lu
        else:
            last = max(last, lu)
    lm = time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime(last))
    headers['Last-Modified'] = lm
    ims = bottle.request.environ.get('HTTP_IF_MODIFIED_SINCE')
    if ims:
        ims = bottle.parse_date(ims.split(";")[0].strip())
    if ims is not None and ims >= last:
        headers['Date'] = time.strftime("%a, %d %b %Y %H:%M:%S GMT",
                                        time.gmtime())
        return bottle.HTTPResponse(status=304, **headers)

    resp = {} #asyncio.run_coroutine_threadsafe(_data_from_sensors(rrd, sensors), loop).result()
    for s in sensors:
        data = asyncio.run_coroutine_threadsafe(rrd.rrdfetch(s), loop).result()
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

        resp[s] = data
    # debug compare clocks
    clock_data = None
    for s in sensors:
        if not clock_data:
            clock_data = resp[s]["clock"]
            continue
        if clock_data != resp[s]["clock"]:
            print("diff", s, clock_data, resp[s]["clock"])
    resp["clock"] = clock_data
    resp = json.dumps(resp).encode("utf-8")
    headers['Content-Length'] = len(resp)
    headers['Content-Type'] = 'application/json'
    return bottle.HTTPResponse(resp, **headers)


async def main():
    global loop
    loop = asyncio.get_event_loop()

    with concurrent.futures.ThreadPoolExecutor() as pool:
        result = await loop.run_in_executor(pool, lambda: bottle.run(host='localhost', port=8086, debug=False, quiet=True))
        print('custom thread pool', result)

asyncio.run(main())

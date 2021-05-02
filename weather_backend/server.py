#!/usr/bin/env python3
import bottle
import os
import time
import fetch
import json
from dbscan import dbscan


@bottle.get("/<name>")
def serve_static(name):
    return bottle.static_file(name, "web/graph")

@bottle.get("/")
def index():
    return bottle.static_file("index.html", "web/graph")

@bottle.get("/data.json")
def data():
    rrd = fetch.RRD(".")
    resp = "{}"
    headers = dict()
    last = 0
    sensors = ["e09806259a66", "24a1603048ba"]
    for fn in sensors:
        lu = rrd.lastupdate(fn)
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
    resp = {}
    # ensure we match readouts
    for fn in sensors:
        data = rrd.rrdfetch(fn)
        if "time" not in data:
            data["time"] = [int(time.time())]
        if "time" not in resp:
            resp["time"] = data["time"]
        resp[fn] = data
    # does time diverge?
    time1 = set(resp[sensors[0]]["time"])
    time2 = set(resp[sensors[1]]["time"])
    for fn in sensors:
        sensordata = resp[fn]
        sensordata.pop("time")
        # Remove outliers
        for name in sensordata.keys():
            data = sensordata[name]
            if name == "volt":
                eps = 0.01
            else:
                eps = 2
            outliers = dbscan(data, eps, 3)
            for i in outliers:
                data[i] = None

    # todo: time might diverge +/- one tick
    #if time1 != time2:
    #    print(time1-time2, time2-time1)
    #    return bottle.HTTPResponse(status=500)

    resp = json.dumps(resp).encode("utf-8")
    headers['Content-Length'] = len(resp)
    return bottle.HTTPResponse(resp, **headers)


bottle.run(host='localhost', port=8086, debug=False, quiet=True)

#!/usr/bin/env python3
import subprocess
import json
import math
from os import environ
from os.path import join, exists

TIME = 24 * 60 * 60

class RRD:
    path = "."
    SENSOR_N_TEMPLATE = "sensors_%s.rrd"
    STEP = 600
    START = "N"
    MINUTE = 60
    HOUR = 60 * MINUTE
    DAY = 24 * HOUR
    YEAR = 370 * DAY  # Yes, longer than 'real' year

    SAMPLES_Y = YEAR / STEP
    def __init__(self, path:str = None):
        self.path = path or self.path

    def _file_path(self, name):
        return join(self.path, self.SENSOR_N_TEMPLATE % name)

    def _environ(self):
        return dict(environ, LANG="C")

    def lastupdate(self, name):
        rrdfile = self._file_path(name)
        # TODO(m): Replace with last, we only need timestamp
        # ant this method should fetch last values too
        proc = subprocess.Popen(["rrdtool", "lastupdate", rrdfile],
                                universal_newlines=True,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL,
                                env=self._environ())
        try:
            outs, _ = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            outs, _ = proc.communicate()
        lines = outs.splitlines()
        if not lines:
            return 0
        fields = lines[-1].split()
        if not fields[0].endswith(":"):
            return 0
        return int(fields[0][:-1])

    def rrdfetch(self, name, start=TIME):
        RRDFILE = join(self.path, self.SENSOR_N_TEMPLATE % name)

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
            "now-%d" % start, "--end", "now"],
            universal_newlines=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=self._environ())
        try:
            outs, _ = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            outs, _ = proc.communicate()

        data = {}
        index2name = {}
        lines = outs.splitlines()
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
            if "time" not in data:
                data["time"] = []
            data["time"].append(timestamp)
            for i, n in index2name.items():
                v = float(values[1 + i])
                if math.isnan(v):
                    v = None
                data[n].append(v)
        return data

    def _create(self, name: str):
        rrd_file = self._file_path(name)
        if exists(rrd_file):
            return True
        
        return subprocess.run([
                "rrdtool",
                "create",
                rrd_file,
                "--step",
                str(self.STEP),
                "--start",
                str(self.START),
                "DS:temp:GAUGE:20m:-30:50",
                "DS:hum:GAUGE:20m:0:100",
                "DS:pres:GAUGE:20m:600:1200",
                "DS:volt:GAUGE:20m:0:5",
                "RRA:AVERAGE:0.5:1:%d" %
                self.SAMPLES_Y  # 1 YEAR by STEP Save 1 YEAR by STEP resolution
            ],
            env=self._environ())

    def add(self, name: str, data: tuple):
        temp, hum, pres, volt = data
        rrd_file = self._file_path(name)
        if not self._create(name):
            raise Exception("Unable to create storage for %s" % s)
        subprocess.run([
            "rrdtool", "update", rrd_file,
            "N:%f:%f:%f:%f" % (temp, hum, pres, volt)
        ], env=self._environ())

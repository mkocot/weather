#!/usr/bin/env python3
import math
from os import environ
from os.path import join, exists
from asyncio import subprocess, wait_for, Lock

TIME = 24 * 60 * 60


class Gauge:
    DS_NAME = None
    DS_RANGE = (None, None)
    DS_TIME = None

    def __init__(self, value):
        self.value = value

    def __str__(self):
        return str(self.value)

    @classmethod
    def template(cls):
        if not cls.DS_NAME:
            raise Exception("no DS_NAME")
        if not cls.DS_TIME:
            raise Exception("no DS_TIME")
        if cls.DS_RANGE == (None, None):
            raise Exception("no DS_RANGE")
        return f"DS:{cls.DS_NAME}:GAUGE:{cls.DS_TIME}m:{cls.DS_RANGE[0]}:{cls.DS_RANGE[1]}"


class Temp(Gauge):
    DS_NAME = "temp"
    DS_RANGE = (-30, 50)
    DS_TIME = 20

    def __init__(self, value):
        super().__init__(value)


class Humidity(Gauge):
    DS_NAME = "hum"
    DS_RANGE = (0, 100)
    DS_TIME = 20

    def __init__(self, value):
        super().__init__(value)


class Pres(Gauge):
    DS_NAME = "pres"
    DS_RANGE = (600, 1200)
    DS_TIME = 20

    def __init__(self, value):
        super().__init__(value)


class Volt(Gauge):
    DS_NAME = "volt"
    DS_RANGE = (0, 5)
    DS_TIME = 20

    def __init__(self, value):
        super().__init__(value)


class Iaq(Gauge):
    DS_NAME = "iaq"
    DS_RANGE = (0, 500)
    DS_TIME = 20

    def __init__(self, value):
        super().__init__(value)


class StaticIaq(Gauge):
    DS_NAME = "siaq"
    DS_RANGE = (0, 500)
    DS_TIME = 20

    def __init__(self, value):
        super().__init__(value)


class Co2(Gauge):
    DS_NAME = "co2"
    # 500 is real minimum
    # max is ?
    # >40,000 ppm 	Exposure may lead to serious oxygen deprivation resulting in permanent
    # brain damage, coma, even death.
    #
    # soo 1_000_000 should be enough (pure co2)
    DS_RANGE = (0, 1000000)
    DS_TIME = 20

    def __init__(self, value):
        super().__init__(value)


class GasResistance(Gauge):
    DS_NAME = "gasr"
    # 0 (but resistance 0 is unlikely)
    # max is dunno assume 1G Ohm
    DS_RANGE = (0, 1000000000)
    DS_TIME = 20

    def __init__(self, value):
        super().__init__(value)


class RRD:
    lock = Lock()
    path = "."
    SENSOR_N_TEMPLATE = "sensors_%s.rrd"
    STEP = 600
    START = "N"
    MINUTE = 60
    HOUR = 60 * MINUTE
    DAY = 24 * HOUR
    YEAR = 370 * DAY  # Yes, longer than 'real' year

    SAMPLES_Y = YEAR / STEP

    KNOWN_GAUGES = {x.DS_NAME: x for x in (
        Temp, Humidity, Pres, Volt, Iaq, StaticIaq, Co2, GasResistance)}

    DEFAULT_GAUGES = (
        Temp, Humidity, Pres, Volt
    )

    def __init__(self, path: str = None):
        self.path = path or self.path
        self.cache = {}

    def _file_path(self, name):
        return join(self.path, self.SENSOR_N_TEMPLATE % name)

    async def _qx(self, args):
        proc = await subprocess.create_subprocess_exec(args[0], *args[1:],
                                                       stdout=subprocess.PIPE,
                                                       stderr=subprocess.DEVNULL,
                                                       env=self._environ())
        try:
            outs, _ = await wait_for(proc.communicate(), timeout=10)
            return (outs, True)
        except subprocess.TimeoutExpired:
            proc.kill()
            outs, _ = await proc.communicate()
            return (outs, False)

    def _environ(self):
        return dict(environ, LANG="C")

    async def last(self, name):
        async with self.lock:
            rrdfile = self._file_path(name)
            out, ok = await self._qx(["rrdtool", "last", rrdfile])
            if not ok:
                return 0
            return int(out)

    # async def add_ds(self, name, something):
    #     rrdfile = self._file_path(name)
    #     args = ["rrdtool", "tune", rrdfile]
    #     for ds in something:
    #         if ds.startswith("DS:"):
    #             rrd_cmd = args + [ds]
    #             outs, ok = await self._qx(rrd_cmd)
    #             if not ok:
    #                 print("unable to execute", rrd_cmd)

    async def _tune(self, name, gauges):
        # use tune to add/remove DS to existing file
        # rrdtool tune my.rrd DS:ds_name:GAUGE:900:-50:100

        rrdfile = self._file_path(name)
        for g in gauges:
            _, ok = await self._qx(["rrdtool", "tune", rrdfile, g.template()])
            if not ok:
                raise Exception("unable to tune rrd")

    def _parse(self, lines):
        data = {}
        index2name = {}
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

    async def lastupdate(self, name):
        async with self.lock:
            rrdfile = self._file_path(name)
            outs, _ = await self._qx(["rrdtool", "lastupdate", rrdfile])
            return self._parse(outs.splitlines())
        # remove nan at end

    async def rrdfetch(self, name, start=TIME):
        async with self.lock:
            RRDFILE = join(self.path, self.SENSOR_N_TEMPLATE % name)

            # Order of date is equal to create
            # temp
            # hum
            # pres
            # volt
            # function push(A,B) { A[length(A)+1] = B }

            # NOTE(m): We should ensure now from graph and now from fetch matches!
            # Otherwises values will be shifted by one (in our case 10minutes)
            outs, _ = await self._qx(["rrdtool", "fetch", RRDFILE, "AVERAGE",
                                      "--start", "now-%d" % start, "--end", "now"])
            return self._parse(outs.splitlines())

    def _default_gauges_templates(self):
        return [x.template() for x in self.DEFAULT_GAUGES]

    async def _create(self, name: str):
        rrd_file = self._file_path(name)
        if exists(rrd_file):
            return True

        _, ok = await self._qx([
            "rrdtool",
            "create",
            rrd_file,
            "--step",
            str(self.STEP),
            "--start",
            str(self.START),
            *self._default_gauges_templates(),
            "RRA:AVERAGE:0.5:1:%d" %
            self.SAMPLES_Y  # 1 YEAR by STEP Save 1 YEAR by STEP resolution
        ])
        return ok

    async def _get_rrd_structure(self, name: str):
        if name in self.cache:
            return self.cache[name]

        rrd_file = self._file_path(name)
        out, ok = await self._qx([
            "rrdtool", "info", rrd_file,
        ])
        if not ok:
            raise Exception("bazinga")
        desc = set()
        for l in out.decode("utf-8").splitlines():
            l = l
            if not l.startswith("ds["):
                continue
            end_name = l.find("]")
            name = l[3:end_name]
            g = self.KNOWN_GAUGES.get(name)
            if g is None:
                raise Exception("invalid schema")
            desc.add(g)
        if not desc:
            raise Exception("XXX")
            print("wholy cow")
        self.cache[name] = desc
        return desc

    def _is_valid_entry(self, x) -> bool:
        if not hasattr(x, "DS_NAME"):
            return False
        if not hasattr(x, "value"):
            return False
        return True

    async def add(self, name: str, data: tuple):
        async with self.lock:
            # temp, hum, pres, volt = data[0:4]
            rrd_file = self._file_path(name)
            if not await self._create(name):
                raise Exception("Unable to create storage for %s" % name)
            schema = await self._get_rrd_structure(name)

            for bad in (x for x in data if not self._is_valid_entry(x)):
                raise Exception(f"{bad} is not descendant of Gauge")

            # do we need tune it?
            missing = set((x.__class__ for x in data)) - schema
            if missing:
                await self._tune(name, missing)
            # prepare template

            template = ":".join((x.DS_NAME for x in data))
            values = ":".join(("%f" % x.value for x in data))

            await self._qx([
                "rrdtool", "update", rrd_file,
                "--template", template,
                "--",
                f"N:{values}",
            ])

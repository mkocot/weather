#!/usr/bin/env python3
import math
from os import environ
from os.path import join, exists
from asyncio import subprocess, wait_for, Lock
import sqlite3
from datetime import timedelta, datetime as dt, timezone

TIME = 24 * 60 * 60
ENABLE_DUCK_DB = False


def now() -> dt:
    return dt.now().astimezone()


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


class SQLiteDB:
    # NOTE: unixepoch is available from 3.38, debian is using old, because why not
    SENSOR_N_TEMPLATE = "sensors_%s.sqlite"
    STEP = 600
    connections = {}

    def __init__(self, data_directory, *args, ro=False, **kwargs) -> None:
        self.directory = data_directory
        self.ro = ro

    def _open(self, name) -> sqlite3.Connection:
        if name not in self.connections:
            con = sqlite3.connect(
                join(self.directory, self.SENSOR_N_TEMPLATE % name))
            self.connections[name] = con
        return self.connections[name]

    def last(self, name):
        con = self._open(name)
        query = """SELECT "timestamp" FROM "values" ORDER BY "timestamp" DESC LIMIT 1"""
        c = con.execute(query)
        # or convert to 'timestamp' to keep legacy
        return int(c.fetchone()[0])

    @staticmethod
    def _wrap(values):
        def _zip(v):
            keys = ['time', 'temp', 'hum', 'pres', 'volt']
            return dict(zip(keys, (v[0].timestamp(),) + v[1:]))

        if isinstance(values, (tuple, list)) and len(values) == 5:
            return _zip(values)

        return (_zip(v) for v in values)

    def lastupdate(self, name):
        con = self._open(name)
        query = """
            SELECT
                "timestamp", "temp", "hum", "pres", "volt"
            FROM
                "values"
            ORDER BY
                "timestamp" DESC
            LIMIT 1
        """
        c = con.execute(query)
        data = c.fetchone()
        return DuckDB._wrap(data)

    def rrdfetch(self, name, start=TIME):
        end_date = now()
        start_date = end_date - timedelta(seconds=start)

        start_date_utc = start_date.astimezone(timezone.utc)
        end_date_utc = end_date.astimezone(timezone.utc)

        QUERY = '''
        SELECT
            "ref_clocks"."generate_series" as "timestamp",
            avg("temp") AS "temp",
            avg("hum") AS "hum",
            avg("pres") AS "pres",
            avg("volt") AS  "volt"
        FROM
        (
            WITH RECURSIVE
            cnt(x) AS (
                SELECT 0
                UNION ALL
                SELECT x + :step FROM cnt
                LIMIT
                /* select between A and B with interval N */
                (SELECT ((STRFTIME('%s', :end) - STRFTIME('%s', :start))) / :step + 1)
            )
            SELECT STRFTIME('%s', :start) + x as "generate_series" FROM cnt
        ) ref_clocks
        LEFT JOIN (
            SELECT
                *
            FROM
                "values"
            WHERE
                "timestamp" BETWEEN STRFTIME('%s', :start) AND STRFTIME('%s', :end)) sensor_values
            ON
                ("sensor_values"."timestamp") >= "ref_clocks"."generate_series"
            AND (("sensor_values"."timestamp") - "ref_clocks"."generate_series") < :step
        GROUP BY
            "ref_clocks"."generate_series"
        ORDER BY
            "ref_clocks"."generate_series"
        '''

        con = self._open(name)
        c = con.execute(QUERY, {'step': self.STEP,
                        'end': end_date_utc, 'start': start_date_utc})
        result = c.fetchall()
        return {
            "time": [x[0] for x in result],
            "temp": [x[1] for x in result],
            "hum": [x[2] for x in result],
            "pres": [x[3] for x in result],
            "volt": [x[4] for x in result],
        }

        # if end_date.tzinfo:
        #     current_tz = end_date.tzinfo
        # else:
        #     current_tz = end_date.astimezone().tzinfo
        # convert utc timestamp with current timezone values
        # return (
        #     (row[0].astimezone(timezone.utc).astimezone(current_tz), ) + row[1:]
        #     for row in con.fetchall()
        # )

    def add(self, name: str, _data: tuple):
        current_time = now()
        con = self._open(name)
        # does it exists?
        data = list(_data)

        keys = ','.join(["timestamp"] + [f'"{d.DS_NAME}"' for d in data])
        vals = [current_time] + [d.value for d in data]
        placeholders = ','.join(['?'] * (len(data) + 1))

        sql = f"""
        INSERT INTO "values" ({keys}) VALUES ({placeholders})
        """
        con.execute(sql, vals)
        con.commit()


if ENABLE_DUCK_DB:
    import duckdb

    class DuckDB:
        SENSOR_N_TEMPLATE = "sensors_%s.duckdb"
        STEP = 600
        connections = {}

        def __init__(self, data_directory, *args, ro=False, **kwargs) -> None:
            self.directory = data_directory
            self.ro = ro
            pass

        def _open(self, name) -> duckdb.DuckDBPyConnection:
            if name not in self.connections:
                con = duckdb.connect(
                    join(self.directory, self.SENSOR_N_TEMPLATE % name), read_only=self.ro)
                self.connections[name] = con
            return self.connections[name]

        def last(self, name):
            con = self._open(name)
            query = """SELECT "timestamp" FROM "values" ORDER BY "timestamp" DESC LIMIT 1"""
            con.execute(query)
            # or convert to 'timestamp' to keep legacy
            return con.fetchone()[0].timestamp()

        @staticmethod
        def _wrap(values):
            def _zip(v):
                keys = ['time', 'temp', 'hum', 'pres', 'volt']
                return dict(zip(keys, (v[0].timestamp(),) + v[1:]))

            if isinstance(values, (tuple, list)) and len(values) == 5:
                return _zip(values)

            return (_zip(v) for v in values)

        def lastupdate(self, name):
            con = self._open(name)
            query = """
                SELECT
                    "timestamp", "temp", "hum", "pres", "volt"
                FROM
                    "values"
                ORDER BY
                    "timestamp" DESC
                LIMIT 1
            """
            con.execute(query)
            data = con.fetchone()
            return DuckDB._wrap(data)

        def rrdfetch(self, name, start=TIME):
            end_date = now()
            start_date = end_date - timedelta(seconds=start)

            start_date_utc = start_date.astimezone(timezone.utc)
            end_date_utc = end_date.astimezone(timezone.utc)

            QUERY = '''
            SELECT
                "ref_clocks"."generate_series" as "timestamp",
                avg("temp") AS "temp",
                avg("hum") AS "hum",
                avg("pres") AS "pres",
                avg("volt") AS "volt"
            FROM
                    (
                SELECT
                    generate_series
                FROM
                    generate_series(
                        /* NOTE: used "? ::TIMESTAMP" and not "TIMESTAMP ?" because
                        later will throw parse error */
                        ?, /* from (inclusive) */
                        ?, /* to (inclusive) */
                        to_seconds(?))) ref_clocks
            LEFT JOIN
                    (
                SELECT
                    *
                FROM
                    "values"
                WHERE
                    "timestamp" BETWEEN ? AND ?) sensor_values
                ON
                    sensor_values.timestamp >= ref_clocks.generate_series
                AND date_sub('second',
                ref_clocks.generate_series,
                sensor_values.timestamp) < ?
            GROUP BY
                "ref_clocks"."generate_series"
            ORDER BY
                "ref_clocks"."generate_series"
            '''
            con = self._open(name)
            con.execute(QUERY, (start_date_utc, end_date_utc, self.STEP,
                        start_date_utc, end_date_utc, self.STEP))
            result = con.fetchall()
            return {
                "time": [x[0].timestamp() for x in result],
                "temp": [x[1] for x in result],
                "hum": [x[2] for x in result],
                "pres": [x[3] for x in result],
                "volt": [x[4] for x in result],
            }

            # if end_date.tzinfo:
            #     current_tz = end_date.tzinfo
            # else:
            #     current_tz = end_date.astimezone().tzinfo
            # convert utc timestamp with current timezone values
            # return (
            #     (row[0].astimezone(timezone.utc).astimezone(current_tz), ) + row[1:]
            #     for row in con.fetchall()
            # )

        def add(self, name: str, data: tuple):
            current_time = now()
            con = self._open(name)
            # does it exists?
            data = list(data)

            keys = ','.join(["timestamp"] + [f'"{d.DS_NAME}"' for d in data])
            vals = [current_time] + [d.value for d in data]
            placeholders = ','.join(['?'] * (len(data) + 1))

            sql = f"""
            INSERT INTO values ({keys}) VALUES ({placeholders})
            """
            con.execute(sql, vals)
            con.commit()


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

    SAMPLES_Y = 5*YEAR / STEP

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
            return (outs.decode('utf-8'), True)
        except subprocess.TimeoutExpired:
            proc.kill()
            outs, _ = await proc.communicate()
            return (outs.decode('utf-8'), False)

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
                if values[1 + i] == 'nan':
                    v = None
                else:
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
        for l in out.splitlines():
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


if __name__ == '__main__' and ENABLE_DUCK_DB:
    tz = dt.now(timezone.utc).astimezone().tzinfo

    def now():
        return dt(2021, 1, 15, 0, 0, tzinfo=tz)

    # stub current data with crap
    name = 'e09806259a66'
    fetcher = DuckDB()
    last = fetcher.last(name)
    print(last)
    lastupdate = fetcher.lastupdate(name)
    print(lastupdate)
    rrdfetch = fetcher.rrdfetch(name)
    print(str(now()))
    for row in rrdfetch:
        print(row)

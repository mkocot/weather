#!/usr/bin/env python3
from os.path import join
from datetime import timedelta, datetime as dt, timezone
from typing import final
import sqlite3
from warnings import deprecated

TIME = 24 * 60 * 60
ENABLE_DUCK_DB = False


def now() -> dt:
    return dt.now().astimezone()


class Gauge:
    DS_NAME: str = ""
    DS_RANGE: tuple[int | float, int | float] = (0, 0)
    DS_TIME: int = 0
    DS_STORAGE: str = "FLOAT"

    def __init__(self, value, *, id: tuple[int,...]|int | None = None):
        self.value = value
        self.id: tuple[int,...]| int | None = id

    def __str__(self):
        return str(self.value)

    @classmethod
    def template(cls):
        if not cls.DS_NAME:
            raise Exception("no DS_NAME")
        if not cls.DS_TIME:
            raise Exception("no DS_TIME")
        if cls.DS_RANGE == (0, 0):
            raise Exception("no DS_RANGE")
        return (
            f"DS:{cls.DS_NAME}:GAUGE:{cls.DS_TIME}m:{cls.DS_RANGE[0]}:{cls.DS_RANGE[1]}"
        )

    @property
    def name(self):
        if self.id is None:
            return self.DS_NAME

        if isinstance(self.id, int):
            return f"{self.DS_NAME}_{self.id}"

        return '_'.join([self.DS_NAME] + [str(x) for x in self.id])

@final
class Temp(Gauge):
    DS_NAME = "temp"
    DS_RANGE = (-30, 50)
    DS_TIME = 20

    def __init__(self, value: float, id: tuple[int,...]|int|None = None):
        super().__init__(value, id=id)


@final
class Humidity(Gauge):
    DS_NAME = "hum"
    DS_RANGE = (0, 100)
    DS_TIME = 20

    def __init__(self, value: float, id: tuple[int,...]|int|None = None):
        super().__init__(value, id=id)


@final
class Pres(Gauge):
    DS_NAME = "pres"
    DS_RANGE = (600, 1200)
    DS_TIME = 20

    def __init__(self, value: float, id: tuple[int, ...]|int|None = None):
        super().__init__(value, id=id)


@final
class Volt(Gauge):
    DS_NAME = "volt"
    DS_RANGE = (0, 5)
    DS_TIME = 20

    def __init__(self, value: float):
        super().__init__(value)


@final
class Iaq(Gauge):
    DS_NAME = "iaq"
    DS_RANGE = (0, 500)
    DS_TIME = 20

    def __init__(self, value: float):
        super().__init__(value)


@final
class StaticIaq(Gauge):
    DS_NAME = "siaq"
    DS_RANGE = (0, 500)
    DS_TIME = 20

    def __init__(self, value: float):
        super().__init__(value)


@final
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

    def __init__(self, value: float):
        super().__init__(value)


@final
class GasResistance(Gauge):
    DS_NAME = "gasr"
    # 0 (but resistance 0 is unlikely)
    # max is dunno assume 1G Ohm
    DS_RANGE = (0, 1000000000)
    DS_TIME = 20

    def __init__(self, value: float):
        super().__init__(value)


@final
@deprecated("Prescale values and use WindSpeed instead")
class WindTick(Gauge):
    '''This has been deprecated because ticks were stored 'as-is' and received
    data was counted 2x, when in should be divided by 2 as there are 2 ticks
    per revolution and also without scaling to 'per seconds' it's stored as
    per 10 seconds, making it too confusing to use without shooting itself
    '''
    DS_NAME = "wind"
    DS_RANGE = (0, 255)
    DS_TIME = 20

    def __init__(self, value: float):
        super().__init__(value)

@final
class WindSpeed(Gauge):
    '''wind ticks expecting one tick per revolution, and scaled to rotation per seconds'''
    DS_NAME = "wind_speed"

    def __init__(self, value:float, *, id: tuple[int, ...] | int | None = None):
        super().__init__(value, id=id)

@final
class WindDirection(Gauge):
    '''wind direction 0..360'''
    DS_NAME = "wind_direction"

    def __init__(self, value:float, *, id: tuple[int, ...] | int | None = None):
        super().__init__(value, id=id)


@final
class SQLiteDB:
    # NOTE: unixepoch is available from 3.38, debian is using old, because why not
    SENSOR_N_TEMPLATE = "sensors_%s.sqlite"
    STEP = 600
    connections = {}

    def __init__(self, data_directory: str, *args, ro: bool = False, **kwargs) -> None:
        self.directory = data_directory
        self.ro = ro

    def _create_db(self, con: sqlite3.Connection):
        sql = """
        CREATE TABLE IF NOT EXISTS "values" (
            "timestamp" TIMESTAMP PRIMARY KEY
        );
        """

        con.execute(sql)

    def _open(self, name) -> sqlite3.Connection:
        if name not in self.connections:
            con = sqlite3.connect(join(self.directory, self.SENSOR_N_TEMPLATE % name))

            self._create_db(con)

            self.connections[name] = {
                "connection": con,
                "schema": self._detect_schema(con),
            }

        return self.connections[name]["connection"]

    def _detect_schema(self, con: sqlite3.Connection):
        schema = set()
        for row in con.execute('PRAGMA table_info("values")').fetchall():
            # 1 - name
            # 2 - type
            schema.add(row[1])

        return schema

    def _schema(self, name):
        if name not in self.connections:
            _ = self._open(name)

        return self.connections[name]["schema"]

    def last(self, name):
        con = self._open(name)
        query = """SELECT "timestamp" FROM "values" ORDER BY "timestamp" DESC LIMIT 1"""
        c = con.execute(query)
        # or convert to 'timestamp' to keep legacy
        return int(c.fetchone()[0])

    @staticmethod
    def _wrap(values, keys):
        def _zip(v):
            return dict(zip(keys, (v[0],) + v[1:]))

        if isinstance(values, (tuple, list)) and len(values) == 5:
            return _zip(values)

        return (_zip(v) for v in values)

    _default_sensors = ["timestamp", "temp", "hum", "pres", "volt"]

    def lastupdate(self, name, *, sensors=None):
        sensors = sensors or self._default_sensors

        sensors_query = ",".join('"%s"' % s for s in sensors)

        con = self._open(name)
        query = f"""
            SELECT
                {sensors_query}
            FROM
                "values"
            ORDER BY
                "timestamp" DESC
            LIMIT 1
        """
        c = con.execute(query)
        data = c.fetchone()
        return SQLiteDB._wrap(data, sensors)

    def fetch_raw(self, name, start=TIME, sensors=None):
        sensors = sensors or self._default_sensors

        end_date = now()
        start_date = end_date - timedelta(seconds=start)

        start_date_utc = start_date.astimezone(timezone.utc)
        end_date_utc = end_date.astimezone(timezone.utc)

        values = ",".join(sensors)

        QUERY = f"""
        SELECT
            {values}
        FROM
            "values"
        WHERE
            "timestamp" BETWEEN (STRFTIME('%s', :start) + 0) AND (STRFTIME('%s', :end) + 0)
        """

        con = self._open(name)
        c = con.execute(QUERY, {"end": end_date_utc, "start": start_date_utc})
        result = c.fetchall()

        return {v: [r[i] for r in result] for i, v in enumerate(sensors)}

    def fetch(self, name, start=TIME, sensors=None):
        sensors = sensors or self._default_sensors

        end_date = now()
        start_date = end_date - timedelta(seconds=start)

        start_date_utc = start_date.astimezone(timezone.utc)
        end_date_utc = end_date.astimezone(timezone.utc)

        values = ",".join(
            '"ref_clocks"."generate_series" as "timestamp"'
            if s == "timestamp"
            else f'avg("{s}") AS "{s}"'
            for s in sensors
        )

        QUERY = f"""
        SELECT
            {values}
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
                "timestamp" BETWEEN (STRFTIME('%s', :start) + 0) AND (STRFTIME('%s', :end) + 0)) sensor_values
            ON
                ("sensor_values"."timestamp") >= "ref_clocks"."generate_series"
            AND (("sensor_values"."timestamp") - "ref_clocks"."generate_series") < :step
        GROUP BY
            "ref_clocks"."generate_series"
        ORDER BY
            "ref_clocks"."generate_series"
        """

        con = self._open(name)
        c = con.execute(
            QUERY, {"step": self.STEP, "end": end_date_utc, "start": start_date_utc}
        )
        result = c.fetchall()
        return {v: [r[i] for r in result] for i, v in enumerate(sensors)}
        # return {
        #     "time": [x[0] for x in result],
        #     "temp": [x[1] for x in result],
        #     "hum": [x[2] for x in result],
        #     "pres": [x[3] for x in result],
        #     "volt": [x[4] for x in result],
        # }

        # if end_date.tzinfo:
        #     current_tz = end_date.tzinfo
        # else:
        #     current_tz = end_date.astimezone().tzinfo
        # convert utc timestamp with current timezone values
        # return (
        #     (row[0].astimezone(timezone.utc).astimezone(current_tz), ) + row[1:]
        #     for row in con.fetchall()
        # )

    def add(
        self, name: str, _data: tuple[Gauge, ...], *, current_time: dt | None = None
    ):
        # does it exists?
        data = list(_data)
        if not data:
            return

        current_time = current_time or now()
        con = self._open(name)

        schema = self._schema(name)
        for d in data:
            if d.name in schema:
                continue

            try:
                _ = con.execute(f'ALTER TABLE "values" ADD COLUMN {d.name} FLOAT')
            except sqlite3.OperationalError as e:
                safe = False
                for a in e.args:
                    if "duplicate column name: " in a:
                        safe = True
                        break

                if not safe:
                    raise

            schema.add(d.name)

        # check for column existence ?
        timestamp = current_time.timestamp()
        keys = ",".join(["timestamp"] + [f'"{d.name}"' for d in data])
        vals = [timestamp] + [d.value for d in data]
        placeholders = ",".join(["?"] * (len(data) + 1))

        sql = f"""
        INSERT INTO "values" ({keys}) VALUES ({placeholders})
        """
        con.execute(sql, vals)
        con.commit()


if __name__ == "__main__":
    tz = dt.now(timezone.utc).astimezone().tzinfo

    def now():
        return dt(2026, 1, 15, 0, 0, tzinfo=tz)

    # stub current data with crap
    name = "e09806259a66"
    fetcher = SQLiteDB(".")
    fetcher.add(name, (Temp(10), Temp(20, id=1)))

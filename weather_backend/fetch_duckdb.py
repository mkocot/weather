from fetch import ENABLE_DUCK_DB, SQLiteDB


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
            return SQLiteDB._wrap(data)

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
            vals = [current_time.timestamp()] + [d.value for d in data]
            placeholders = ','.join(['?'] * (len(data) + 1))

            sql = f"""
            INSERT INTO values ({keys}) VALUES ({placeholders})
            """
            con.execute(sql, vals)
            con.commit()

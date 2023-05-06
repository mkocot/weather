import xml.etree.ElementTree
from datetime import timezone, timedelta, datetime as dt
import os
import sys
import math


sensor_name = sys.argv[1]
if not sensor_name.endswith('.xml'):
    exit(1)
sensor_name = sensor_name.split('_')[1][:-4]
db_name = f'sensors_{sensor_name}.duckdb'

doc = xml.etree.ElementTree.parse(
    f'sensors_{sensor_name}.xml',
    parser=xml.etree.ElementTree.XMLParser(
        target=xml.etree.ElementTree.TreeBuilder(insert_comments=True)
    )
)
# doc.getElementsByTagName('database')[0]
root = list(doc.getroot().iter('database'))[0]

format_str = '%Y-%m-%d %H:%M:%S %Z'
cet_tz = timezone(offset=timedelta(hours=1), name='CET')
cest_tz = timezone(offset=timedelta(hours=2), name='CEST')



data_frame = {}
data_frame['timestamp'] = []
data_frame['temp'] = []
data_frame['hum'] = []
data_frame['pres'] = []
data_frame['volt'] = []

order = ['temp', 'hum', 'pres', 'volt']

times = set()

comment_node = None
for node in root:  # .childNodes:
    if callable(node.tag):
        comment_node = node.text
        continue

    if node.tag == 'row':
        if not comment_node:
            print('missing comment for data')
            continue
        row_datetime, row_timestamp = [x.strip()
                                       for x in comment_node.split('/')]
        # print(comment_node.data)

        values = [float(x.text) for x in node.iter('v')]
        if all(math.isnan(x) for x in values):
            continue
        for k, v in zip(order, values):
            data_frame[k].append(v)
        if 'CEST' in row_datetime:
            tz = cest_tz
        else:
            tz = cet_tz
        x = dt.fromtimestamp(float(row_timestamp), tz=tz)
        # print(row_datetime, '|', x, float(row_timestamp) - x.timestamp())
        row_timestamp = x
        # use unixepoch by default
        row_timestamp = x.timestamp()
        # print(row_datetime, x)
        # row_datetime = dt.strptime(row_datetime, format_str)
        # row_datetime_utc = row_datetime.astimezone(tz).astimezone(timezone.utc)
        # row_datetime = row_datetime.\
        #     replace(' CEST', '+02:00').\
        #     replace(' CET', '+01:00')
        # data_frame['timestamp'].append(row_datetime)
        # if row_datetime_utc in times:
        # raise Exception("whoa", row_datetime.timestamp(), row_timestamp, row_datetime_utc.timestamp())
        # times.add(row_datetime_utc)
        data_frame['timestamp'].append(row_timestamp)  # row_datetime_utc)

        # row_timestamp = int(row_timestamp)
        # # print(row_timestamp, row_datetime.timestamp())
        # connection.execute("""
        # INSERT INTO "values" ("timestamp", "temp", "hum", "pres", "volt")
        # VALUES (?, ?, ?, ?, ?)
        # """, (row_datetime, 0, 0, 0, 0))

        comment_node = None
    # print(node)

USE_DUCKDB = False
USE_SQLITE = True

if USE_DUCKDB:
    try:
        os.unlink(db_name)
    except:
        pass
    import pandas as pd
    import duckdb
    connection = duckdb.connect(db_name)
    connection.execute("""
    CREATE TABLE values (
        "timestamp" TIMESTAMP PRIMARY KEY,
        "temp" FLOAT,
        "hum" FLOAT,
        "pres" FLOAT,
        "volt" FLOAT,
    )
    """)

    pd_dataframe = pd.DataFrame.from_dict(data_frame)
    connection.register('pd_dataframe', pd_dataframe)
    connection.execute('INSERT INTO values SELECT * FROM pd_dataframe')
    connection.commit()
    connection.close()

if USE_SQLITE:
    try:
        os.unlink(db_name.replace('.duckdb', '.sqlite'))
    except:
        pass

    import sqlite3
    with sqlite3.connect(db_name.replace('.duckdb', '.sqlite')) as con:
        con.execute("PRAGMA journal_mode = wal2;")
        cur = con.execute("""
        CREATE TABLE "values" (
        "timestamp" TIMESTAMP PRIMARY KEY,
        "temp" FLOAT,
        "hum" FLOAT,
        "pres" FLOAT,
        "volt" FLOAT)
        """)
        params = (
            (data_frame['timestamp'][x], data_frame['temp'][x], data_frame['hum'][x], data_frame['pres'][x], data_frame['volt'][x]) for x in range(len(data_frame['timestamp']))
        )
        con.executemany(
            """INSERT INTO "values" ("timestamp", "temp", "hum", "pres", "volt") VALUES (?, ?, ?, ?, ?)""", params)

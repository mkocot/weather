#!/usr/bin/env python3
import json

def quantile(data, p):
    # note(m): this is probably off by one
    data = sorted(data)
    a = p*(len(data)+1)
    k = int(a)
    alpha = a - int(a)
    return data[k] + alpha*(data[k+1] - data[k])

with open("data.json") as f:
    data = json.load(f)

keys = set(data.keys())
keys.remove("time")

for sensor in keys:
    pres = data[sensor]["pres"]
    q25 = quantile(pres, 0.25)
    q75 = quantile(pres, 0.75)
    iqr = q75 - q25
    print(iqr)
    k = 1.5
    outliers = [x for x in pres if x > q75+k*iqr or x < q25-k*iqr]
    print(min(pres))
    print(min(pres) < q25-k*iqr)
    print("25%", q25)
    print("75%", q75)
    print("outliers", outliers)

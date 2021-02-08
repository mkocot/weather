#!/usr/bin/env python3
import json
import math
from operator import itemgetter

def dbscan(dataraw, eps, minptr):
    data = range(len(dataraw))
    def _RangeQuery(Q):
        N = []
        for P in data:
            valp = dataraw[P]
            valq = dataraw[Q]
            # note(m): Explicite, we don't want catch 0 here
            if valp is None:
                valp = float("NaN")
            if valq is None:
                valq = float("NaN")

            if abs(valp - valq) > eps:
                continue
            N.append(P)
        return N

    C = 0
    # Init to 'False' value making it easy to find
    label = [0 for _ in data]
    NOISE = -1
    for P in data:
        if label[P]:
            continue
        N = _RangeQuery(P)
        if len(N) < minptr:
            label[P] = NOISE
            continue
        C = C + 1
        label[P] = C
        S = set(N)
        S.remove(P)
        repeat = True
        while repeat:
            repeat = False
            for Q in S:
                if label[Q] == NOISE:
                    label[Q] = C
                if label[Q]:
                    continue
                label[Q] = C
                N = _RangeQuery(Q)
                if len(N) >= minptr:
                    S.update(N)
                    repeat = True
                    break
    return [x for x, y in enumerate(label) if y == NOISE]


if __name__ == "__main__":
    with open("data.json") as f:
        data = json.load(f)

    keys = set(data.keys())
    keys.remove("time")

    for sensor in keys:
        datas = data[sensor]
        for name in datas.keys():
            pres = data[sensor][name]
            eps = 2
            if name == "volt":
                eps = 0.01 #
            outliers = dbscan(pres, eps, 3)
            print("%s@%s outliers" % (name, sensor), [pres[i] for i in outliers])

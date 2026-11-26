"""
Take a batch of snapshots of Lime's public Seattle GBFS feed and save them
as one gzipped CSV. Built for the GitHub Actions workflow in
.github/workflows/collect-lime-gbfs.yml (one run per hour, a snapshot every
5 minutes), but it runs anywhere with plain Python 3 (no extra packages).

GBFS only shows parked, available vehicles right now. Trips are inferred
later: a vehicle that disappears from one spot and reappears in another
between snapshots made a trip (or was rebalanced by Lime staff).

Output: <out>/YYYY-MM-DD/HHMM.csv.gz  (Seattle local time of the batch start)
columns: ts (unix seconds, from the feed), bike_id, lat, lon, vehicle_type,
         is_reserved, is_disabled

Run locally:  python gbfs/collect_gbfs.py --snapshots 1 --out lime_seattle
"""

import argparse
import csv
import gzip
import json
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

URL = "https://data.lime.bike/api/partners/v1/gbfs/seattle/free_bike_status.json"
UA = "cet513-seattle-bike-connectivity/1.0 (student project)"
COLS = ["ts", "bike_id", "lat", "lon", "vehicle_type", "is_reserved", "is_disabled"]
TZ = ZoneInfo("America/Los_Angeles")


def fetch():
    req = urllib.request.Request(URL, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--snapshots", type=int, default=12)
    p.add_argument("--every", type=int, default=300, help="seconds between snapshots")
    p.add_argument("--types", default="bike", help="comma list: bike,scooter (default bike)")
    p.add_argument("--out", default="lime_seattle")
    a = p.parse_args()
    types = set(a.types.split(","))

    start = datetime.now(TZ)
    f = Path(a.out) / f"{start:%Y-%m-%d}" / f"{start:%H%M}.csv.gz"
    f.parent.mkdir(parents=True, exist_ok=True)
    ok = 0
    with gzip.open(f, "wt", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(COLS)
        for i in range(a.snapshots):
            t0 = time.time()
            try:
                j = fetch()
                ts = j.get("last_updated", int(t0))
                rows = [b for b in j["data"]["bikes"] if b.get("vehicle_type") in types]
                for b in rows:
                    w.writerow([ts, b.get("bike_id"), b.get("lat"), b.get("lon"),
                                b.get("vehicle_type"), b.get("is_reserved"), b.get("is_disabled")])
                ok += 1
                print(f"{datetime.fromtimestamp(ts, TZ):%Y-%m-%d %H:%M}  {len(rows):,} vehicles", flush=True)
            except Exception as ex:  # one bad fetch shouldn't lose the batch
                print(f"snapshot {i + 1} failed: {ex}", flush=True)
            if i < a.snapshots - 1:
                time.sleep(max(5, a.every - (time.time() - t0)))
    print(f"wrote {ok}/{a.snapshots} snapshots -> {f}")
    if ok == 0:
        f.unlink()
        sys.exit(1)


if __name__ == "__main__":
    main()

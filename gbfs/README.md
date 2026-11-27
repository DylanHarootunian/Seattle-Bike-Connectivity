# Lime GBFS collection

GitHub Actions snapshots Lime's public Seattle feed
(`https://data.lime.bike/api/partners/v1/gbfs/seattle/free_bike_status.json`)
every 5 minutes, in hourly batches, and commits the results to the
**`gbfs-data`** branch, so `main` stays clean. Nothing runs on anyone's laptop.

* Workflow: `.github/workflows/collect-lime-gbfs.yml`
* Script: `gbfs/collect_gbfs.py` (plain Python 3, no packages)
* Data: branch `gbfs-data`, `lime_seattle/YYYY-MM-DD/HHMM.csv.gz`
  (Seattle local time of the batch start)
* Columns: `ts` (unix seconds), `bike_id`, `lat`, `lon`, `vehicle_type`,
  `is_reserved`, `is_disabled`
* Default is bikes only (about 3,000 vehicles, about 25 MB/day). Add scooters with
  `--types bike,scooter` in the workflow (about 13,000 vehicles, about 110 MB/day).

## Start / stop

Actions tab -> **Collect Lime GBFS** -> `...` -> **Disable workflow** to stop,
**Enable workflow** to resume, **Run workflow** to start a batch right away.
GitHub's hourly cron is unreliable, so each run also starts the next one when it
finishes, giving back-to-back hourly batches. To stop for good, **disable** the
workflow (cancelling a single run also stops the chain; click Run workflow to restart).

## Load it

```python
import glob, pandas as pd
files = sorted(glob.glob("lime_seattle/*/*.csv.gz"))   # after: git checkout gbfs-data
df = pd.concat((pd.read_csv(f) for f in files), ignore_index=True)
df["time"] = pd.to_datetime(df.ts, unit="s", utc=True).dt.tz_convert("America/Los_Angeles")
```

Get just the data without switching branches:
`git clone --branch gbfs-data --single-branch https://github.com/DylanHarootunian/Seattle-Bike-Connectivity.git lime-data`

## Turning snapshots into trips

**`bike_id` is not stable.** Lime changes the IDs periodically for privacy
(checked 2026-11-26: a bike parked in the same spot had a new ID 15 minutes
later), so you can't follow one bike from pickup to drop-off. Match on
**position** instead:

* A parked location that disappears between snapshots = a **pickup** (trip origin).
* A new location that appears = a **drop-off** (trip destination).
* Treat positions within ~20 m of each other as the same spot, since coordinates
  have 4 decimals (~10 m).

That gives trip starts and ends per area and per hour (productions and
attractions). Origin-destination pairs then come from a model, such as a gravity
model between bike-network components. Some pickups and drop-offs are Lime staff
rebalancing or charging, so big overnight batch changes are worth filtering out.

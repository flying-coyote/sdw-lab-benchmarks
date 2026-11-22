# SOC query shapes: beaconing, UEBA and rare-value across Iceberg engines

## What it measures

The flagship benches cover flat scan-aggregation and sort-key needle lookups. This folder adds three
query shapes a SOC runs that those benches do not, and asks whether any of them reorders the engines:
C2 beaconing (a window function, `lag` over time-ordered connections, then the coefficient of variation
of the gaps), a UEBA volume Z-score (two-level aggregation: hourly count per host, then per-host mean and
standard deviation), and rare-value detection (destinations contacted by exactly one source, a
high-cardinality `count(DISTINCT)`). Each shape is timed against a matched flat aggregation on
ClickHouse reading Iceberg, StarRocks and Trino over a shared Iceberg catalog; a Dremio arm ran and is
withheld under its benchmark-publication terms. Two further legs plant ground truth so the detections
can be scored.

## Result (Tier B)

The latency rankings are measured and could have come out otherwise; one did.

- Beaconing over `soc.conn` (10.3M rows): the window shape costs 28.3x to 56.5x the flat aggregation
  and does not change the order (ClickHouse-Iceberg 1.608 s, StarRocks 1.742 s, Trino 5.811 s; CVs
  7.4%, 9.3%, 6.7% in `results/beacon.json`).
- UEBA over `soc.conn`: StarRocks (0.207 s) overtakes ClickHouse-Iceberg (0.378 s), a gap of 82%
  (0.3775 / 0.2071 = 1.82 in `results/ueba_rare.json`). Rare-value keeps ClickHouse first, though only
  by 3.8% (1.2552 s against 1.3034 s), which sits inside ClickHouse-Iceberg's 8.9% CV on that shape, so
  ClickHouse and StarRocks tie on rare-value (noted 2026-11-22).
  *(corrected 2026-11-17: the RESULTS file called the 82% gap "far above the 3.2% CV". The 3.2 in
  `results/ueba_rare.json` is StarRocks' UEBA-over-flat ratio (`over_flat_x`), not a CV; the UEBA CVs
  are 16.0% for StarRocks and 15.0% for ClickHouse-Iceberg over 5 trials. The gap still clears them, so
  the inversion stands on one host and five trials, with a noise floor about five times higher than
  stated.)*
- On the 868,790-row planted UEBA corpus the order is ClickHouse-Iceberg (0.0675 s) then StarRocks
  (0.0872 s), but that 29% gap sits inside ClickHouse-Iceberg's 30.4% CV in `results/ueba_planted.json`,
  so the planted leg neither reproduces nor refutes the inversion, and the inversion rests on the one
  10.3M `soc.conn` run with five trials. *(Reworded 2026-11-22: this line said the inversion "does not
  reproduce" and was "specific to the 10.3M run", which the planted leg's CV does not support.)*

The detection results on the planted corpora follow largely from construction. The 120 beacons are
regular-interval with at most 8% jitter against 30 irregular decoys, and the UEBA spike hosts are
planted at Z of about 4.8 and the decoys at about 1.6 against a threshold of 3, as
`RESULTS-ueba-planted-2026-06-15.md` itself says, so recall 1.0 and cross-engine answer-equality were
expected. Beacon precision is 80% at `LIMIT 150` on the two engines that returned rows (120 true pairs,
and the 30 decoys fill the rest of the limit, in `results/beacon-planted.json`), and the five UEBA false positives are chance outliers in the normal-host baseline, identical on
every engine. On `soc.conn` itself both UEBA and rare-value returned zero rows, so their detection
correctness there is unvalidated, as the RESULTS file says.

## What would have made it fail

For the rankings, a different engine order; the beacon shape kept the order and the UEBA shape changed
it. The baseline for each shape is the same engine's flat aggregation on the same table. For the planted
detections, an engine returning a different flagged set from the others would have failed
answer-equality; recall below 1.0 was unlikely by design. ClickHouse-Iceberg returned zero rows on the
freshly written beacon table (a catalog-less `icebergS3()` metadata-resolution failure), so the beacon
detection leg has two reported engines, not three.

## Pre-registration

None. No file in the folder records a design frozen before the runs.

## Reproduce

The scripts run inside the lab's `ejs-lab` container against its Nessie Iceberg catalog, MinIO and the
engine containers, using the shared clients in `ejs_clients.py`:

```bash
docker exec ejs-lab python3 /tmp/soc_shapes_bench.py        # UEBA + rare over soc.conn
docker exec ejs-lab python3 /repo/soc-query-shapes/beacon_bench.py   # beaconing over soc.conn
docker exec ejs-lab python3 /tmp/gen_beacon_corpus.py       # planted beacons -> soc.conn_beacontest
docker exec ejs-lab python3 /tmp/gen_ueba_corpus.py         # planted UEBA -> soc.conn_ueba_planted
docker exec ejs-lab python3 /tmp/ueba_planted_bench.py
```

The script headers differ: `soc_shapes_bench.py` runs from `/tmp` inside the container (copied in
first), while `beacon_bench.py` runs from the repo mounted at `/repo`, and the other three scripts say
only "run in ejs-lab" without a path (noted 2026-11-22). `soc.conn` is the shared 10.3M-row structured
flow table already in that catalog. The
container, its compose file and the `soc.conn` load are not in this repo.

## Results

- [RESULTS-beaconing-2026-06-15.md](RESULTS-beaconing-2026-06-15.md) with `results/beacon.json` and `results/beacon-planted.json`.
- [RESULTS-ueba-rare-2026-06-15.md](RESULTS-ueba-rare-2026-06-15.md) with `results/ueba_rare.json`: the latency ranking and the inversion.
- [RESULTS-ueba-planted-2026-06-15.md](RESULTS-ueba-planted-2026-06-15.md) with `results/ueba_planted.json`: detection on planted truth; the current word on whether the inversion generalises.

## Versions and pins

No `requirements.txt`. The scripts import `pyarrow` and `pyiceberg` inside the container, unpinned here,
and the results files do not record engine versions for this run. Same-date files record only
ClickHouse 26.5.1; the nearest dated record of all three engines is the 2026-06-23 lakehouse-engines arm
(`../ocsf-sigma-detection/RESULTS-lakehouse-engines-4-7-2026-06-23.md`, ClickHouse 26.5.1.882, Trino 481,
StarRocks 4.1.1), eight days later (corrected 2026-11-22).

## Evidence tier and limits

Tier B: one host, five trials per arm, synthetic structured flow data, four engines with one withheld.
The RESULTS files link to private session notes by wiki-link name; those notes are not part of this repo.

## Corrections

- *(corrected 2026-11-17: the UEBA inversion's noise floor is the 15 to 16% CV in `results/ueba_rare.json`,
  not 3.2%, which is a ratio over the flat query.)*
- *(corrected 2026-11-22: both `*_inverts_flat` flags in `results/ueba_rare.json` were recomputed over
  the three published arms. The rare-value lead and the planted-corpus UEBA order are now read against
  their CVs, above.)*

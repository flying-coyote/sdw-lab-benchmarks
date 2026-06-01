"""Failure mode 2 — grain loss, the detail you cannot get back.

The essay's claim is asymmetric: rolling connection records up to a coarse grain
leaves volumetric *routine* queries exact while destroying the timing structure
that *adversary* queries depend on. To test that honestly we plant two
populations that are identical in everything a 5-minute (src, dst) rollup keeps
— same total volume, same per-bucket count, same 43-byte payload — and differ
only in within-bucket timing:

  * beacons  : 60-second regular interval (low inter-arrival jitter) — malicious
  * decoys   : the same 5 connections per bucket but bursty within the bucket —
               benign, and indistinguishable from a beacon once you only have
               per-bucket counts.

A detector that can read individual timestamps (atomic grain) separates the two
on jitter. A detector limited to the rollup cannot, so it either misses the
beacons or drowns them in the benign decoys. We measure precision/recall/F1 of
the same beacon-hunt against each store, plus two routine volumetric queries to
show the rollup is exact for those.
"""

from common import new_rng, prf1, connect

WINDOW_SECONDS = 3600  # one hour of traffic
BUCKET_SECONDS = 300  # 5-minute rollup grain
BEACON_INTERVAL = 60  # regular beacon period
PER_BUCKET = BUCKET_SECONDS // BEACON_INTERVAL  # 5 connections per bucket
PAYLOAD = 43  # constant small payload shared by beacons AND decoys


def _gen_corpus(n_beacons: int, n_decoys: int, n_noise: int, seed: int):
    """Return (rows, beacon_truth).

    rows: (conn_id, t_offset_seconds, src_host, dst, n_bytes)
    beacon_truth: set of (src_host, dst) pairs that are real beacons
    """
    rng = new_rng(seed)
    rows = []
    truth = set()
    cid = 0
    n_buckets = WINDOW_SECONDS // BUCKET_SECONDS  # 12

    # Beacons: exactly PER_BUCKET hits per bucket at a regular 60s cadence.
    for b in range(n_beacons):
        src = f"10.0.{b}.5"
        dst = f"beacon-{b}.example"
        truth.add((src, dst))
        for bucket in range(n_buckets):
            for k in range(PER_BUCKET):
                t = bucket * BUCKET_SECONDS + k * BEACON_INTERVAL
                rows.append((cid, t, src, dst, PAYLOAD))
                cid += 1

    # Decoys: same volume and per-bucket count and payload, but bursty timing —
    # all PER_BUCKET hits land in the first ~40 seconds of each bucket.
    for d in range(n_decoys):
        src = f"10.1.{d}.5"
        dst = f"decoy-{d}.example"
        for bucket in range(n_buckets):
            base = bucket * BUCKET_SECONDS
            for k in range(PER_BUCKET):
                t = base + rng.randint(0, 40)  # clustered, irregular within bucket
                rows.append((cid, t, src, dst, PAYLOAD))
                cid += 1

    # Background noise: low-volume, irregular pairs the detectors should ignore.
    for m in range(n_noise):
        src = f"10.2.{m % 64}.5"
        dst = f"normal-{m}.example"
        hits = rng.randint(1, 8)
        for _ in range(hits):
            t = rng.randint(0, WINDOW_SECONDS - 1)
            rows.append((cid, t, src, dst, rng.randint(200, 50_000)))
            cid += 1

    return rows, truth


def run(scales=((8, 16, 200), (16, 32, 400))):
    out = {
        "name": "grain_loss_timing_destroyed",
        "title": "Grain loss → timing-based adversary queries destroyed, volumetric queries exact",
        "scales": [],
    }

    for (n_beacons, n_decoys, n_noise) in scales:
        rows, truth = _gen_corpus(n_beacons, n_decoys, n_noise, seed=202)
        con = connect()
        con.execute(
            "CREATE TABLE atomic (conn_id INTEGER, t_off INTEGER, src_host VARCHAR, dst VARCHAR, n_bytes INTEGER)"
        )
        con.executemany("INSERT INTO atomic VALUES (?, ?, ?, ?, ?)", rows)
        con.execute(
            "ALTER TABLE atomic ADD COLUMN event_time TIMESTAMP"
        )
        con.execute(
            "UPDATE atomic SET event_time = TIMESTAMP '2026-01-01 00:00:00' + (t_off * INTERVAL 1 SECOND)"
        )

        # The lossy rollup: (src, dst, 5-min bucket) -> count + byte aggregates.
        # Individual event_times do not survive this step.
        con.execute(
            f"""
            CREATE TABLE coarse AS
            SELECT src_host, dst,
                   (t_off // {BUCKET_SECONDS}) AS bucket,
                   count(*)        AS cnt,
                   sum(n_bytes)    AS sum_bytes,
                   avg(n_bytes)    AS avg_bytes,
                   min(n_bytes)    AS min_bytes,
                   max(n_bytes)    AS max_bytes
            FROM atomic
            GROUP BY src_host, dst, (t_off // {BUCKET_SECONDS})
            """
        )

        # --- Adversary query: beacon hunt by inter-arrival regularity ---
        # Atomic grain: the timestamps exist, so we can compute jitter directly.
        atomic_beacons = {
            (r[0], r[1])
            for r in con.execute(
                """
                WITH ordered AS (
                    SELECT src_host, dst, t_off,
                           t_off - lag(t_off) OVER (PARTITION BY src_host, dst ORDER BY t_off) AS gap
                    FROM atomic
                ),
                stats AS (
                    SELECT src_host, dst, count(*) AS n,
                           avg(gap) AS mean_gap, stddev_pop(gap) AS sd_gap
                    FROM ordered WHERE gap IS NOT NULL
                    GROUP BY src_host, dst
                )
                SELECT src_host, dst FROM stats
                WHERE n >= 30 AND mean_gap > 0 AND (sd_gap / mean_gap) < 0.05
                """
            ).fetchall()
        }

        # Coarse grain: the only timing signal left is steadiness of per-bucket
        # counts. A 60s beacon and a bursty decoy both yield a steady 5/bucket,
        # so this fair-effort detector cannot tell them apart.
        coarse_beacons = {
            (r[0], r[1])
            for r in con.execute(
                """
                SELECT src_host, dst FROM coarse
                GROUP BY src_host, dst
                HAVING count(*) >= 10
                   AND avg(cnt) > 0
                   AND (stddev_pop(cnt) / avg(cnt)) < 0.05
                """
            ).fetchall()
        }

        # --- Routine queries: must be exact on both stores ---
        atomic_daily = con.execute(
            "SELECT src_host, sum(n_bytes) FROM atomic GROUP BY src_host ORDER BY src_host"
        ).fetchall()
        coarse_daily = con.execute(
            "SELECT src_host, sum(sum_bytes) FROM coarse GROUP BY src_host ORDER BY src_host"
        ).fetchall()
        bytes_match = atomic_daily == coarse_daily

        atomic_pairct = con.execute(
            "SELECT src_host, dst, count(*) FROM atomic GROUP BY src_host, dst ORDER BY src_host, dst"
        ).fetchall()
        coarse_pairct = con.execute(
            "SELECT src_host, dst, sum(cnt) FROM coarse GROUP BY src_host, dst ORDER BY src_host, dst"
        ).fetchall()
        count_match = atomic_pairct == coarse_pairct
        con.close()

        atomic_score = prf1(truth, atomic_beacons)
        coarse_score = prf1(truth, coarse_beacons)
        adversary_degradation = round(atomic_score["f1"] - coarse_score["f1"], 4)
        routine_degradation = 0.0 if (bytes_match and count_match) else 1.0

        out["scales"].append(
            {
                "n_beacons": n_beacons,
                "n_decoys": n_decoys,
                "n_noise_pairs": n_noise,
                "n_rows": len(rows),
                "adversary_query_beacon_hunt": {
                    "atomic_grain": atomic_score,
                    "coarse_grain": coarse_score,
                    "f1_degradation": adversary_degradation,
                },
                "routine_queries": {
                    "bytes_per_host_exact": bytes_match,
                    "pair_counts_exact": count_match,
                    "degradation": routine_degradation,
                },
                "headline_adversary_minus_routine_degradation": round(
                    adversary_degradation - routine_degradation, 4
                ),
            }
        )
    return out

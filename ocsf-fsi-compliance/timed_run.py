"""BENCH-F — timestamp-bracketed timing of automated section production.

The stopwatch, per the operating definition: capture a discrete wall-clock timestamp the
instant before a section's production sequence starts, run the sequence to meet its frozen
acceptance definition, capture a discrete timestamp the instant it finishes, and write
elapsed = end - start. Each section is produced on BOTH substrate arms by the same automated
operator, so the comparison is fair on the operator and varies only on the substrate's
primitives.

WHAT THIS MEASURES — read this before quoting the number. The operator here is automated, so
the elapsed is machine/agent time-to-produce, NOT human analyst hours. The substrate gap it
captures is the query-primitive gap (Parquet + partition columns + a SQL engine + a keyed
lineage/time-travel lookup on the lakehouse, versus a schema-on-read full scan with none of
those on the SIEM stand-in). That is a real, reproducible quantity, but it is a PROXY: the
human-hours H-FSI-01 is about live in manual toil (export, screenshot, narrative assembly)
that an automated operator never pays, so this does not validate the ≥40% human-hours claim.
The named-FSI human run stays the Tier-A gate. Both arms are author-built, so the
self-design bias caveat from REPORT-SPEC.md applies in full.
"""

import json
import os
import sys
import time

import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, "_work")
TRIALS = 3   # median elapsed for stability; one trial's discrete start/end is recorded too
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
from common import configure_duckdb  # noqa: E402


def stopwatch(fn):
    """Discrete start timestamp -> run -> discrete end timestamp. Returns (start, end, elapsed, result)."""
    start = time.time()
    result = fn()
    end = time.time()
    return start, end, end - start, result


# --- Lakehouse arm: DuckDB over the Parquet store with partition columns + keyed lookups ---
class Lakehouse:
    def __init__(self):
        self.pq = os.path.join(WORK, "corpus.parquet").replace("'", "''")

    def _con(self):
        c = configure_duckdb(duckdb.connect()); c.execute(f"CREATE VIEW c AS SELECT * FROM '{self.pq}'"); return c

    def a_retention(self):
        c = self._con()
        return c.execute("SELECT year, count(*) FROM c GROUP BY year ORDER BY year").fetchall()

    def b_timeline(self):
        c = self._con()
        return [r[0] for r in c.execute(
            "SELECT event_uid FROM c WHERE needle='intrusion' ORDER BY time").fetchall()]

    def c_lineage(self, sample):
        c = self._con()
        return [c.execute("SELECT event_uid, logged_time, service FROM c WHERE event_uid=?",
                          [u]).fetchone() for u in sample]

    def d_point_in_time(self, pit):
        c = self._con()
        return c.execute("SELECT count(*) FROM c WHERE time <= ?", [pit]).fetchone()[0]


# --- SIEM stand-in: schema-on-read scan of raw JSONL in Python, no engine/index/time-travel ---
class SiemStandin:
    def __init__(self):
        self.path = os.path.join(WORK, "corpus.jsonl")

    def _scan(self):
        with open(self.path) as f:
            for line in f:
                yield json.loads(line)

    def a_retention(self):
        tally = {}
        for r in self._scan():
            tally[r["year"]] = tally.get(r["year"], 0) + 1
        return sorted(tally.items())

    def b_timeline(self):
        hits = [(r["time"], r["event_uid"]) for r in self._scan() if r.get("needle") == "intrusion"]
        hits.sort()
        return [u for _, u in hits]

    def c_lineage(self, sample):
        # no index: a separate linear scan to locate each sampled record (manual lookup)
        out = []
        want = set(sample)
        for u in sample:
            for r in self._scan():
                if r["event_uid"] == u:
                    out.append((r["event_uid"], r["logged_time"], r["service"]))
                    break
        return out

    def d_point_in_time(self, pit):
        # no time-travel: full scan + manual time filter
        return sum(1 for r in self._scan() if r["time"] <= pit)


def produce(arm, gt):
    sample = gt["lineage_sample_uids"]
    pit = gt["point_in_time_ms"]
    return {
        "a_retention": (lambda: arm.a_retention()),
        "b_timeline": (lambda: arm.b_timeline()),
        "c_lineage": (lambda: arm.c_lineage(sample)),
        "d_point_in_time": (lambda: arm.d_point_in_time(pit)),
    }


def check(section, result, gt):
    if section == "a_retention":
        return len({y for y, _ in result}) >= gt["retention"]["rule_17a4_floor_years"]
    if section == "b_timeline":
        truth = [s["event_uid"] for s in sorted(gt["intrusion_timeline"], key=lambda s: s["true_event_time_ms"])]
        return result == truth
    if section == "c_lineage":
        return len(result) == len(gt["lineage_sample_uids"])
    if section == "d_point_in_time":
        return 0 < result < gt["total_events"]
    return False


def time_arm(arm, gt):
    out = {}
    for section, fn in produce(arm, gt).items():
        elapsed = []
        start = end = passed = None
        for i in range(TRIALS):
            s, e, dt, res = stopwatch(fn)
            elapsed.append(dt)
            if i == 0:
                start, end, passed = s, e, check(section, res, gt)
        elapsed.sort()
        out[section] = {"start_time": round(start, 6), "end_time": round(end, 6),
                        "elapsed_s_median": round(elapsed[len(elapsed) // 2], 4),
                        "acceptance_pass": passed}
    return out


def main():
    if not os.path.exists(os.path.join(WORK, "corpus.parquet")):
        print("Corpus not built — run gen_corpus.py first.", file=sys.stderr); sys.exit(2)
    gt = json.load(open(os.path.join(WORK, "ground_truth.json")))
    lake = time_arm(Lakehouse(), gt)
    siem = time_arm(SiemStandin(), gt)

    sections = list(lake)
    lake_tot = sum(lake[s]["elapsed_s_median"] for s in sections)
    siem_tot = sum(siem[s]["elapsed_s_median"] for s in sections)
    reduction = (siem_tot - lake_tot) / siem_tot if siem_tot else None
    cd_gap = sum(siem[s]["elapsed_s_median"] - lake[s]["elapsed_s_median"]
                 for s in ("c_lineage", "d_point_in_time"))
    concentrated = (siem_tot - lake_tot) > 0 and cd_gap / (siem_tot - lake_tot) >= 0.5

    results = {
        "benchmark": "ocsf-fsi-compliance (BENCH-F) — automated operator-elapsed timing",
        "metric": "AUTOMATED operator-elapsed seconds (timestamp-bracketed). NOT human-hours.",
        "caveat": ("Machine time-to-produce, dominated by substrate query primitives; under-"
                   "captures the manual toil the human-hours claim is about. Author-built arms "
                   "(self-design bias). Does not validate H-FSI-01's >=40% human-hours claim; "
                   "the named-FSI human run remains the Tier-A gate."),
        "trials_per_section": TRIALS,
        "lakehouse": lake, "siem_standin": siem,
        "totals": {"lakehouse_elapsed_s": round(lake_tot, 4), "siem_elapsed_s": round(siem_tot, 4),
                   "automated_reduction_pct": round(reduction * 100, 1) if reduction is not None else None,
                   "concentrated_in_cd": concentrated},
    }
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    with open(os.path.join(HERE, "results", "results-automated-timing.json"), "w") as f:
        json.dump(results, f, indent=2, sort_keys=True)

    print("section            lakehouse_s   siem_s   (acceptance pass both)")
    for s in sections:
        print(f"  {s:16} {lake[s]['elapsed_s_median']:>9.4f}  {siem[s]['elapsed_s_median']:>8.4f}   "
              f"{lake[s]['acceptance_pass'] and siem[s]['acceptance_pass']}")
    print(f"\ntotal: lakehouse {lake_tot:.4f}s  siem {siem_tot:.4f}s  "
          f"automated-reduction {results['totals']['automated_reduction_pct']}%  "
          f"(concentrated in c+d: {concentrated})")
    print("NOTE: automated machine-time, NOT human-hours — see caveat in results file.")


if __name__ == "__main__":
    main()

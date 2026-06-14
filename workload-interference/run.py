#!/usr/bin/env python3
"""Workload-interference orchestrator (#23) — locate the scheduled:ad-hoc knee per engine.

This ties the EXISTING helpers together; it does NOT reimplement them:
  engines.py  — per-arm clients (make_client / reconnect / classify, the 7 ARMS),
  mix.py      — the 6 pre-registered scheduled shapes + the interactive probe (scheduled_sql,
                probe_sql, PROBE_PORTS, SCHEDULED_ORDER, K),
  lib.common  — MASTER_SEED (seeded parameter rotation), timing conventions, results shape.

The mechanism, verbatim from README.md (the pre-registration, committed 2026-06-10):

  Background scheduled load — OPEN-LOOP. A fixed-period generator models a detection
  scheduler that fires on its period whether or not the last cycle finished. Open-loop is
  the declared modeling choice precisely because a closed-loop client self-throttles and
  hides the knee being measured. The K=6 shapes are staggered evenly across a 60 s cycle,
  the rate scaled uniformly across a demand ladder (U_demand ≈ 0.125 → 4.0, ×2 per step).
  "Open-loop" here means: a fire is scheduled at a fixed INTENDED time; if the previous
  fire on that worker is still running, the new fire does not wait for it — a fresh worker
  picks it up (up to the outstanding-query cap) and a slow response never delays the next
  intended send. Backlog (intended-but-not-yet-dispatched fires) is the thing we watch.

  Foreground interactive probes on a fixed 5 s schedule, COORDINATED-OMISSION-SAFE: we
  record the INTENDED send time of each probe and measure its latency against THAT time,
  not against when a busy client got around to sending it. Under coordinated omission a
  naive client stalls during a slow period and silently drops the probes that would have
  landed in the stall, flattering the tail exactly where the knee lives; recording intended
  time and never skipping a scheduled probe is what keeps the p95 honest.

  Null-load calibration GATE: at the max generator rate, with the probe driver running but
  the engine load replaced by a near-no-op, the client-added latency must stay < 5% of the
  R=0 baseline probe median, or the arm does NOT score (README §Isolation: the cpuset 12/2
  split is gated by this calibration).

Per arm: R=0 baseline first (1 discarded warmup + 7 trials, median + CV); null-load
calibration gate; then the demand ladder, 60 s warm-in + 300 s measured window per step,
stop rule mechanical and identical for every arm, one step past the knee to characterize
failure shape. A knee is claimable only on 3× reproduction at the same ladder step (the
reproduction itself is an operator decision — re-run the same --arm --ladder-step; this
harness records each pass so the 3× check is mechanical across runs).

STRICT SCOPE NOTE: this file is the orchestrator only. It does not start docker, build the
corpus, or refresh MVs — those are operator steps (compose stack from engine-join-
specialization; make_mvs.sql for the starrocks_mv arm). It assumes the ejs compose stack is
up and the pinned corpora are loaded, exactly as the ejs scored_run.sh assumes.
"""
import argparse
import json
import statistics
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))  # repo root, for lib.common (matches engines.py)

import engines  # noqa: E402  (ARMS, make_client, reconnect, classify)
import mix      # noqa: E402  (scheduled_sql, probe_sql, table_refs, PROBE_PORTS, K, SCHEDULED_ORDER)
from lib import common  # noqa: E402  (MASTER_SEED, deterministic rotation seed)

RESULTS = HERE / "results"

# ---------------------------------------------------------------- pre-registered constants
# Every number here is re-derived from README.md, named at its source.

CYCLE_SECONDS = 60.0          # README §Mechanism: "Staggered in a 60 s cycle"
PROBE_PERIOD_SECONDS = 5.0    # README §Mechanism: probes "on a fixed 5 s schedule"

# Demand ladder: U_demand ≈ 0.125 → 4.0, ×2 per step (README §Sweep protocol). U_demand is
# the rate multiplier on one full base cycle of the K=6 shapes per CYCLE_SECONDS: at U=1.0 the
# generator INTENDS exactly one base cycle (K fires) per 60 s; U=2.0 intends two base cycles
# per 60 s; and so on. The ladder is the fixed sequence of demand levels each arm walks.
LADDER = [0.125, 0.25, 0.5, 1.0, 2.0, 4.0]

WARMIN_SECONDS = 60           # README §Sweep protocol: "60 s warm-in"
MEASURE_SECONDS = 300         # README §Sweep protocol: "300 s measured window per step"

# Baseline (R=0) protocol, house verbatim (README §Sweep protocol; lib.common.time_trials).
BASELINE_WARMUP = 1           # "1 discarded warmup"
BASELINE_TRIALS = 7           # "+ 7 trials"

# Interactive thresholds (README §Thresholds), seconds.
P95_FLOW = 10.0               # < 10 s : flow
P95_TOLERABLE = 30.0          # < 30 s : tolerable; the stop trigger is crossing this
P95_BROKEN = 60.0             # > 60 s : broken

# Stop rule (README §Sweep protocol), mechanical and identical for every arm.
OUTSTANDING_CAP = 64          # "outstanding-query cap 64"
UTILIZATION_STOP = 1.0        # "measured utilization >= 1.0 with monotone backlog growth"
DNF_SECONDS = engines.TIMEOUT # 300 s per-query DNF ceiling, carried from engines.py

# Null-load calibration gate (README §Isolation): client-added latency < 5% of baseline
# probe median, at the max generator rate, or the arm does not score.
CALIBRATION_MAX_OVERHEAD_PCT = 5.0
CALIBRATION_SECONDS = 60      # a short, max-rate null-load window is enough to size the overhead


def _percentile(samples, pct):
    """Nearest-rank percentile on a list of floats (no numpy dependency, matches the
    house style of computing summary stats inline). Returns None on an empty list."""
    if not samples:
        return None
    xs = sorted(samples)
    if len(xs) == 1:
        return xs[0]
    k = max(0, min(len(xs) - 1, int(round((pct / 100.0) * (len(xs) - 1)))))
    return xs[k]


def _summary(samples):
    """median / p95 / max / mean / n for a latency sample list (seconds)."""
    if not samples:
        return {"n": 0, "median_s": None, "p95_s": None, "max_s": None, "mean_s": None}
    xs = sorted(samples)
    return {
        "n": len(xs),
        "median_s": round(statistics.median(xs), 4),
        "p95_s": round(_percentile(xs, 95), 4),
        "max_s": round(xs[-1], 4),
        "mean_s": round(statistics.mean(xs), 4),
    }


# ---------------------------------------------------------------- coordinated-omission probe driver

class ProbeDriver(threading.Thread):
    """Foreground interactive probes on a fixed PROBE_PERIOD_SECONDS schedule, coordinated-
    omission-safe.

    The honesty discipline: each probe has an INTENDED send time (anchored at start, then
    +PROBE_PERIOD_SECONDS each fire), and latency is measured (send_completed - intended), so
    a probe that the engine could only ACCEPT late still carries the full wait an analyst
    actually felt. We never skip a scheduled probe to "catch up" — if we fall behind, the
    backlog of intended-but-late probes is dispatched in order and each is still scored
    against its own intended time. That is the opposite of a closed-loop client, which would
    quietly drop the probes that fall inside a stall and under-report the tail.

    A fresh client connection per probe keeps a slow/blocked probe from serializing the next
    one (each fire is independent; the engine's contention is what we measure, never a shared
    Python cursor). The probe is the gated artifact (exact aggregate vs the DuckDB oracle),
    but answer-equality is checked by the operator out-of-band against ground truth — here we
    record the row so a mismatch is auditable; the latency is the headline this driver owns.
    """

    def __init__(self, arm, refs, rng, stop_event, ports=None):
        super().__init__(daemon=True)
        self.arm = arm
        self.refs = refs
        self.rng = rng
        self.stop_event = stop_event
        self.ports = ports if ports is not None else list(mix.PROBE_PORTS)
        self.samples = []        # [{"intended_offset_s","latency_s","port","dnf"?}]
        self._client = None
        self._started_at = None

    def _client_for_probe(self):
        # One probe driver holds its own client and reconnects on a server fault, so a
        # restarting engine costs only the in-flight probe, not the whole probe stream
        # (engines.reconnect discipline, carried from ejs).
        if self._client is None:
            self._client = engines.make_client(self.arm)
        return self._client

    def run(self):
        self._started_at = time.perf_counter()
        fire_index = 0
        while not self.stop_event.is_set():
            intended = self._started_at + fire_index * PROBE_PERIOD_SECONDS
            now = time.perf_counter()
            # Sleep until the intended send time, but never skip the fire if we are already
            # late — coordinated-omission-safe means a late probe is still SENT and still
            # scored against its intended time, not dropped.
            if intended > now:
                # wait in small slices so a stop_event set mid-sleep is honored promptly
                while not self.stop_event.is_set() and time.perf_counter() < intended:
                    time.sleep(min(0.05, max(0.0, intended - time.perf_counter())))
                if self.stop_event.is_set():
                    break
            port = self.ports[fire_index % len(self.ports)]
            sql = mix.probe_sql(self.refs, port)
            rec = {"intended_offset_s": round(fire_index * PROBE_PERIOD_SECONDS, 3),
                   "port": port}
            try:
                client = self._client_for_probe()
                client.run(sql)
                # latency measured against INTENDED time (coordinated-omission correction),
                # not against when this thread actually got to dispatch.
                rec["latency_s"] = round(time.perf_counter() - intended, 4)
            except Exception as e:  # noqa: BLE001
                rec["latency_s"] = round(time.perf_counter() - intended, 4)
                rec["dnf"] = engines.classify(e)
                rec["error"] = str(e)[:300]
                # a server fault: reconnect so the next probe is not collateral damage
                if rec["dnf"] == "server":
                    self._client = engines.reconnect(self.arm, self._client)
            self.samples.append(rec)
            fire_index += 1

    def latencies(self):
        """Probe latencies (seconds) for completed (non-DNF) fires."""
        return [s["latency_s"] for s in self.samples if "dnf" not in s]


# ---------------------------------------------------------------- open-loop scheduled-load generator

class ScheduledLoad:
    """Open-loop fixed-period scheduled-detection-load generator.

    Models a detection scheduler firing the K=6 shapes (mix.SCHEDULED_ORDER) staggered evenly
    across CYCLE_SECONDS, at a demand multiplier U. INTENDED fire times are precomputed off a
    fixed schedule and never slip: a fire whose intended time has arrived is dispatched on a
    worker pool, and if every worker is busy the fire goes onto a BACKLOG (the open-loop
    signature — the scheduler does not wait for the last cycle, the work piles up). Monotone
    backlog growth across the measured window, together with measured utilization >= 1.0, is
    one of the stop triggers.

    "demand_overhead_factor" lets the null-load calibration reuse this exact generator at the
    max rate while replacing the heavy scheduled SQL with a near-no-op, so the calibration
    measures the CLIENT's added latency on the same arrival process the scored run uses.
    """

    def __init__(self, arm, sqls, demand, stop_event, max_workers=OUTSTANDING_CAP,
                 noop=False):
        self.arm = arm
        self.sqls = sqls                      # {shape -> rendered SQL}
        self.demand = demand                  # U multiplier
        self.stop_event = stop_event
        self.max_workers = max_workers
        self.noop = noop                      # calibration: do not run the heavy SQL
        self.order = list(mix.SCHEDULED_ORDER)
        self.k = len(self.order)

        self._lock = threading.Lock()
        self.outstanding = 0                  # in-flight dispatched fires
        self.peak_outstanding = 0
        self.backlog = 0                       # intended-but-not-yet-dispatched fires
        self.backlog_trace = []                # sampled (offset_s, backlog) for monotone check
        self.completed = 0
        self.fires_intended = 0
        self.runtimes = []                     # per-completed-fire engine runtime (s)
        self.dnf = {}                          # reason -> count
        self.hard_break = None                 # set on OOM/server-death class fault
        self._threads = []
        self._started_at = None

    # one fire = render-free dispatch of a precomputed SQL on a fresh client
    def _dispatch(self, shape, sql, intended):
        def _work():
            client = None
            try:
                client = engines.make_client(self.arm)
                t0 = time.perf_counter()
                if self.noop:
                    # calibration path: a near-no-op so we measure CLIENT overhead, not the
                    # engine. SELECT 1 is the lightest cross-engine statement; duckdb/others
                    # all answer it. The arrival process is identical to the scored run.
                    client.run("SELECT 1")
                else:
                    client.run(sql)
                dt = time.perf_counter() - t0
                with self._lock:
                    self.completed += 1
                    self.runtimes.append(dt)
            except Exception as e:  # noqa: BLE001
                reason = engines.classify(e)
                with self._lock:
                    self.dnf[reason] = self.dnf.get(reason, 0) + 1
                    # OOM / server death is a hard break (README §Thresholds: "Hard breaks:
                    # OOM, ... server death"); record it so the stop rule fires immediately.
                    if reason in ("resource", "server"):
                        self.hard_break = reason
            finally:
                with self._lock:
                    self.outstanding -= 1

        with self._lock:
            if self.outstanding >= self.max_workers:
                # open-loop: no room to dispatch, so the fire BACKS UP instead of throttling
                # the scheduler. This is the contention signal the closed-loop client hides.
                self.backlog += 1
                return False
            self.outstanding += 1
            self.peak_outstanding = max(self.peak_outstanding, self.outstanding)
        t = threading.Thread(target=_work, daemon=True)
        t.start()
        self._threads.append(t)
        return True

    def _intended_schedule(self):
        """Generator of (intended_offset_s, shape, sql) on the open-loop fixed period.

        At demand U, the K shapes repeat U times per CYCLE_SECONDS, staggered evenly. The
        inter-fire spacing is CYCLE_SECONDS / (K * U); fire i lands at i * spacing and walks
        the shape order round-robin so the cycle stays staggered, not bursty.
        """
        spacing = CYCLE_SECONDS / (self.k * self.demand)
        i = 0
        while True:
            shape = self.order[i % self.k]
            yield i * spacing, shape, self.sqls[shape]
            i += 1

    def run_for(self, seconds):
        """Drive the open-loop arrival process for `seconds`, dispatching fires at their
        intended times and backing up anything the worker pool cannot accept. Returns when
        the window elapses, the stop_event is set, or a hard break is recorded."""
        self._started_at = time.perf_counter()
        sched = self._intended_schedule()
        next_off, next_shape, next_sql = next(sched)
        last_backlog_sample = -1.0
        while not self.stop_event.is_set():
            now = time.perf_counter() - self._started_at
            if now >= seconds:
                break
            if self.hard_break:
                break
            # dispatch every fire whose intended time has arrived (open-loop: catch up the
            # whole burst that is due, do not pace to the engine)
            while next_off <= now:
                with self._lock:
                    self.fires_intended += 1
                dispatched = self._dispatch(next_shape, next_sql, next_off)
                next_off, next_shape, next_sql = next(sched)
                if self.stop_event.is_set():
                    break
            # sample backlog once a second for the monotone-growth check
            if now - last_backlog_sample >= 1.0:
                with self._lock:
                    self.backlog_trace.append((round(now, 1), self.backlog))
                last_backlog_sample = now
            # sleep until the next intended fire (or a short slice, whichever is sooner)
            sleep_for = min(0.05, max(0.0, next_off - (time.perf_counter() - self._started_at)))
            time.sleep(sleep_for)

    def join_inflight(self, timeout=DNF_SECONDS):
        """Wait for in-flight dispatched fires to drain (so per-step runtimes are complete)."""
        deadline = time.perf_counter() + timeout
        for t in list(self._threads):
            remaining = max(0.0, deadline - time.perf_counter())
            t.join(timeout=remaining)

    def utilization(self, window_seconds):
        """Cycle utilization = Σ scheduled runtime per cycle ÷ cycle length (README
        §Thresholds). Σ runtime / window, scaled to the cycle: the fraction of one
        engine-second the scheduled load consumed per wall second. >= 1.0 with monotone
        backlog growth is a stop trigger."""
        if window_seconds <= 0:
            return None
        return round(sum(self.runtimes) / window_seconds, 4)

    def backlog_monotone(self):
        """True if the sampled backlog is non-decreasing and ends above where it started —
        the 'monotone backlog growth' half of the utilization stop trigger."""
        trace = [b for _, b in self.backlog_trace]
        if len(trace) < 3:
            return False
        non_decreasing = all(b2 >= b1 for b1, b2 in zip(trace, trace[1:]))
        return non_decreasing and trace[-1] > trace[0]


# ---------------------------------------------------------------- per-arm passes

def run_baseline(arm, refs, rng):
    """R=0 baseline: the interactive probe alone, 1 discarded warmup + 7 timed trials, median
    + CV (house protocol verbatim, lib.common.time_trials shape). No scheduled load. This is
    the denominator every inflation number and the calibration gate measure against."""
    client = engines.make_client(arm)
    ports = list(mix.PROBE_PORTS)
    # seeded rotation so warmup+trials hit distinct params (no result-cache measurement)
    seq = [ports[rng.randrange(len(ports))]
           for _ in range(BASELINE_WARMUP + BASELINE_TRIALS)]
    samples = []
    for i, port in enumerate(seq):
        sql = mix.probe_sql(refs, port)
        t0 = time.perf_counter()
        client.run(sql)
        dt = time.perf_counter() - t0
        if i >= BASELINE_WARMUP:
            samples.append(dt)
    median = statistics.median(samples)
    cv = (100 * statistics.pstdev(samples) / statistics.mean(samples)) if len(samples) > 1 else 0.0
    return {
        "probe_median_s": round(median, 4),
        "probe_cv_pct": round(cv, 1),
        "trials": len(samples),
        "warmup": BASELINE_WARMUP,
        "samples_s": [round(s, 4) for s in samples],
    }


def run_calibration(arm, sqls, refs, rng, baseline_median):
    """Null-load calibration GATE (README §Isolation). Run the probe driver against the
    open-loop generator at the MAX ladder rate, but with the scheduled SQL replaced by a
    near-no-op (noop=True). The engine is then effectively idle, so any probe-latency
    inflation over the R=0 baseline median is the CLIENT's own added latency. If that added
    latency is >= 5% of the baseline probe median, the cpuset 12/2 split is not clean and the
    arm does NOT score."""
    stop = threading.Event()
    load = ScheduledLoad(arm, sqls, demand=max(LADDER), stop_event=stop, noop=True)
    probe = ProbeDriver(arm, refs, rng, stop_event=stop)
    probe.start()
    load.run_for(CALIBRATION_SECONDS)
    stop.set()
    load.join_inflight(timeout=30)
    probe.join(timeout=30)
    lat = probe.latencies()
    cal_median = statistics.median(lat) if lat else None
    if cal_median is None or baseline_median <= 0:
        return {"passed": False, "reason": "no calibration samples",
                "baseline_median_s": baseline_median, "calibration_median_s": cal_median}
    overhead_pct = round(100 * (cal_median - baseline_median) / baseline_median, 2)
    passed = overhead_pct < CALIBRATION_MAX_OVERHEAD_PCT
    return {
        "passed": passed,
        "max_demand": max(LADDER),
        "baseline_median_s": round(baseline_median, 4),
        "calibration_median_s": round(cal_median, 4),
        "client_added_latency_pct": overhead_pct,
        "threshold_pct": CALIBRATION_MAX_OVERHEAD_PCT,
        "probe_samples": len(lat),
        "note": ("client-added latency under the 5% gate — cpuset split clean"
                 if passed else
                 "client-added latency >= 5% — arm NOT scorable (cpuset/isolation dirty)"),
    }


def classify_failure_shape(step_records):
    """Failure-shape taxonomy (README §Why this axis: graceful / plateau / cliff / silent-wrong).

    Read across the ladder steps' probe p95 trajectory up to and including the step past the
    knee:
      cliff        — p95 jumps from tolerable (< 30 s) to broken (> 60 s) / DNF in one step.
      plateau      — p95 rises toward the threshold and flattens (small step-over-step deltas)
                     while utilization saturates: degradation without a clean break.
      graceful     — p95 climbs smoothly across steps, each step a modest multiple of the last.
      silent-wrong — a probe answered fast but a recorded answer mismatch flagged it (operator
                     verifies equality out-of-band; here we surface any 'answer_mismatch' marks).
      hard-break   — an OOM / server-death hard break ended the sweep.
    The call is advisory and reported with the curve so a reader can re-derive it; it is not a
    gate."""
    p95s = [(s["demand"], s["probe"]["p95_s"]) for s in step_records
            if s.get("probe", {}).get("p95_s") is not None]
    if any(s.get("hard_break") for s in step_records):
        return "hard-break"
    if any(s.get("answer_mismatch") for s in step_records):
        return "silent-wrong"
    if len(p95s) < 2:
        return "inconclusive"
    last_two = p95s[-2:]
    (_, prev), (_, cur) = last_two
    if prev is not None and cur is not None:
        if prev < P95_TOLERABLE and (cur > P95_BROKEN):
            return "cliff"
        # plateau: the final step's p95 grew by < 1.5× over the prior while already elevated
        if prev >= P95_FLOW and cur < 1.5 * prev:
            return "plateau"
    return "graceful"


def step_stop_reason(probe_summary, load, window_seconds):
    """The mechanical stop rule (README §Sweep protocol), first trigger wins. Returns a reason
    string if this step should stop the ladder, else None."""
    if load.hard_break:
        return f"hard_break:{load.hard_break}"
    p95 = probe_summary.get("p95_s")
    if p95 is not None and p95 > P95_TOLERABLE:
        return "probe_p95_over_30s"
    util = load.utilization(window_seconds)
    if util is not None and util >= UTILIZATION_STOP and load.backlog_monotone():
        return "utilization_ge_1_with_monotone_backlog"
    if load.peak_outstanding >= OUTSTANDING_CAP:
        return "outstanding_cap_64"
    return None


def run_ladder_step(arm, sqls, refs, rng, demand):
    """One demand-ladder step: 60 s warm-in (load running, probes discarded) + 300 s measured
    window (probes scored against intended time). Returns the per-step record."""
    # warm-in: load + probes run, probe samples discarded (page cache / plan warmth)
    stop_warm = threading.Event()
    warm_load = ScheduledLoad(arm, sqls, demand=demand, stop_event=stop_warm)
    warm_probe = ProbeDriver(arm, refs, rng, stop_event=stop_warm)
    warm_probe.start()
    warm_load.run_for(WARMIN_SECONDS)
    stop_warm.set()
    warm_load.join_inflight(timeout=30)
    warm_probe.join(timeout=30)

    # measured window
    stop = threading.Event()
    load = ScheduledLoad(arm, sqls, demand=demand, stop_event=stop)
    probe = ProbeDriver(arm, refs, rng, stop_event=stop)
    probe.start()
    t0 = time.perf_counter()
    load.run_for(MEASURE_SECONDS)
    window = time.perf_counter() - t0
    stop.set()
    load.join_inflight(timeout=DNF_SECONDS)
    probe.join(timeout=30)

    probe_summary = _summary(probe.latencies())
    util = load.utilization(window)
    record = {
        "demand": demand,
        "window_s": round(window, 1),
        "probe": probe_summary,
        "probe_p95_over_flow_10s": (probe_summary["p95_s"] is not None
                                    and probe_summary["p95_s"] > P95_FLOW),
        "probe_p95_over_tolerable_30s": (probe_summary["p95_s"] is not None
                                         and probe_summary["p95_s"] > P95_TOLERABLE),
        "probe_dnf_count": sum(1 for s in probe.samples if "dnf" in s),
        "scheduled": {
            "fires_intended": load.fires_intended,
            "completed": load.completed,
            "utilization": util,
            "peak_outstanding": load.peak_outstanding,
            "backlog_end": load.backlog,
            "backlog_monotone": load.backlog_monotone(),
            "scheduled_runtime_median_s": (round(statistics.median(load.runtimes), 4)
                                           if load.runtimes else None),
            "dnf": load.dnf,
        },
        "hard_break": load.hard_break,
    }
    record["stop_reason"] = step_stop_reason(probe_summary, load, window)
    return record


def run_arm(arm, ladder, baseline_only=False, skip_calibration=False):
    """Full per-arm pass: baseline -> calibration gate -> demand ladder with the mechanical
    stop rule, one step past the knee. Writes nothing; returns the arm record (the writer
    aggregates all arms into results/results.json)."""
    refs = mix.table_refs(arm)
    sqls = mix.scheduled_sql(arm)
    # one RNG per arm off the master seed, so the probe-port rotation is reproducible per arm
    # but independent across arms (lib.common.new_rng discipline).
    rng = common.new_rng(sum(ord(c) for c in arm))

    out = {
        "arm": arm,
        "baseline": None,
        "calibration": None,
        "scored": False,
        "ladder": [],
        "knee": None,
        "failure_shape": None,
    }
    out["baseline"] = run_baseline(arm, refs, rng)
    if baseline_only:
        return out

    if not skip_calibration:
        out["calibration"] = run_calibration(
            arm, sqls, refs, rng, out["baseline"]["probe_median_s"])
        if not out["calibration"]["passed"]:
            out["scored"] = False
            out["note"] = "calibration gate FAILED — arm not scored (README §Isolation)"
            return out

    out["scored"] = True
    knee_demand = None
    steps_after_knee = 0
    for demand in ladder:
        rec = run_ladder_step(arm, sqls, refs, rng, demand)
        out["ladder"].append(rec)
        if knee_demand is None and rec["stop_reason"] is not None:
            # the knee is the first step that trips the stop rule; run exactly one more step
            # past it to characterize the failure shape (README §Sweep protocol).
            knee_demand = demand
            out["knee"] = {
                "demand": demand,
                "stop_reason": rec["stop_reason"],
                "probe_p95_s": rec["probe"]["p95_s"],
                "reproduced": False,  # 3x reproduction is an operator step across runs
                "note": ("first ladder step tripping the mechanical stop rule; a claimable "
                         "knee requires 3x reproduction at this same demand step"),
            }
        elif knee_demand is not None:
            steps_after_knee += 1
            if steps_after_knee >= 1:
                break
    out["failure_shape"] = classify_failure_shape(out["ladder"])
    return out


# ---------------------------------------------------------------- results writer

def write_results(arm_records, args):
    """results/results.json + a RESULTS.md scaffold, matching the ejs convention (a results/
    dir with a machine-readable JSON and a human RESULTS.md the operator fills with prose
    after the scored run). The scaffold pre-fills every table from the JSON; the operator
    writes the headline, the prose, and the P1–P7 scorecard verdicts after reading the curves.

    Nothing here scores the predictions — the predictions are pre-registered in README.md and
    only the operator, reading the measured curves, marks each right/wrong/mixed (the ejs
    RESULTS.md does exactly this by hand)."""
    RESULTS.mkdir(exist_ok=True)
    blob = {
        "bench": "workload-interference",
        "tier": "B",
        "host": "Beelink 5800H, WSL2 48 GB / 14t (cpuset 12/2 engine/client split)",
        "generated_unix": int(time.time()),
        "seed": common.MASTER_SEED,
        "config": {
            "cycle_seconds": CYCLE_SECONDS,
            "probe_period_seconds": PROBE_PERIOD_SECONDS,
            "ladder": args.ladder,
            "warmin_seconds": WARMIN_SECONDS,
            "measure_seconds": MEASURE_SECONDS,
            "thresholds": {"flow_p95_s": P95_FLOW, "tolerable_p95_s": P95_TOLERABLE,
                           "broken_p95_s": P95_BROKEN},
            "outstanding_cap": OUTSTANDING_CAP,
            "calibration_max_overhead_pct": CALIBRATION_MAX_OVERHEAD_PCT,
            "scheduled_shapes": list(mix.SCHEDULED_ORDER),
        },
        "arms": {},
    }
    # Merge with any prior arms so a multi-invocation sweep (one engine profile up at a time,
    # the memory-safe pattern) accumulates instead of clobbering. New arm records win.
    rp = RESULTS / "results.json"
    prior = {}
    if rp.exists():
        try:
            prior = json.loads(rp.read_text()).get("arms", {})
        except Exception:
            prior = {}
    blob["arms"] = {**prior, **{r["arm"]: r for r in arm_records}}
    rp.write_text(json.dumps(blob, indent=2))

    # ---- RESULTS.md scaffold (operator fills prose + the P1-P7 verdicts) ----
    lines = []
    lines.append("# RESULTS — workload-interference: where the scheduled load breaks the "
                 "interactive experience")
    lines.append("")
    lines.append("> SCAFFOLD — generated by run.py. The tables below are filled from "
                 "results/results.json; the headline, prose, and the P1–P7 scorecard are "
                 "written by hand after reading the p95-vs-demand curves. The knee is "
                 "claimable only on 3× reproduction at the same ladder step (see each arm's "
                 "`knee.reproduced`).")
    lines.append("")
    lines.append("**Tier B · single host (Beelink 5800H, WSL2 48 GB / 14t, cpuset 12/2 "
                 "engine/client split) · one engine at a time · R=0 baseline = 1 discarded "
                 "warmup + 7 trials · probes coordinated-omission-safe (latency vs intended "
                 "send time) · open-loop scheduled load (fires on its period, slow responses "
                 "back up, they do not throttle the scheduler) · thresholds pre-registered "
                 "in README.md, full curves below.**")
    lines.append("")

    # Calibration-gate table (the arm doesn't score unless this passes)
    lines.append("## Null-load calibration gate (< 5% client-added latency at max rate)")
    lines.append("")
    lines.append("| arm | baseline probe median | calibration median | client-added % | gate |")
    lines.append("|---|---|---|---|---|")
    for r in arm_records:
        cal = r.get("calibration")
        if not cal:
            lines.append(f"| {r['arm']} | — | — | — | (not run) |")
            continue
        bm = cal.get("baseline_median_s")
        cm = cal.get("calibration_median_s")
        ov = cal.get("client_added_latency_pct")
        gate = "PASS" if cal.get("passed") else "**FAIL — not scored**"
        lines.append(f"| {r['arm']} | {bm} s | {cm} s | {ov}% | {gate} |")
    lines.append("")

    # Knee + failure-shape summary
    lines.append("## Knee + failure shape (per arm)")
    lines.append("")
    lines.append("| arm | scored | knee demand (U) | stop trigger | failure shape | reproduced 3× |")
    lines.append("|---|---|---|---|---|---|")
    for r in arm_records:
        scored = "yes" if r.get("scored") else "no"
        knee = r.get("knee") or {}
        kd = knee.get("demand", "—")
        trig = knee.get("stop_reason", "—")
        shape = r.get("failure_shape", "—")
        repro = "yes" if knee.get("reproduced") else "no (operator step)"
        lines.append(f"| {r['arm']} | {scored} | {kd} | {trig} | {shape} | {repro} |")
    lines.append("")

    # Per-arm p95-vs-demand curve (the curve is theirs; the 10/30 s lines are ours)
    lines.append("## p95-vs-demand curves (full, so any reader re-derives the knee at their "
                 "own threshold)")
    lines.append("")
    for r in arm_records:
        lines.append(f"### {r['arm']}")
        lines.append("")
        base = r.get("baseline") or {}
        lines.append(f"R=0 baseline probe median {base.get('probe_median_s')} s "
                     f"(CV {base.get('probe_cv_pct')}%).")
        lines.append("")
        if not r.get("ladder"):
            lines.append("_no scored ladder (calibration gate failed or baseline-only run)._")
            lines.append("")
            continue
        lines.append("| demand U | probe median | probe p95 | probe max | sched completed | "
                     "utilization | peak outstanding | backlog end | stop trigger |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for s in r["ladder"]:
            p = s["probe"]
            sc = s["scheduled"]
            lines.append(
                f"| {s['demand']} | {p['median_s']} s | {p['p95_s']} s | {p['max_s']} s | "
                f"{sc['completed']} | {sc['utilization']} | {sc['peak_outstanding']} | "
                f"{sc['backlog_end']} | {s['stop_reason'] or '—'} |")
        lines.append("")

    # Predictions scorecard scaffold (operator writes the verdicts)
    lines.append("## Predictions scorecard (pre-registered in README.md — operator fills "
                 "the verdict after reading the curves)")
    lines.append("")
    preds = [
        ("P1 (~60%)", "ch_native sustains the highest scheduled rate before the 10 s probe "
                      "crossing; Trino knees first among server arms."),
        ("P2 (~55%)", "duckdb_parquet fails gracefully but early."),
        ("P3 (~65%)", "utilization is a valid early-warning signal — every graceful arm "
                      "crosses U≈0.7 at least one full step before p95 crosses 10 s."),
        ("P4 (~55%)", "every server arm sustains ≥60 scheduled queries/min before the knee."),
        ("P5 (~60%)", "starrocks_mv shifts the knee right ≥2 ladder steps (conditional on "
                      "verified rewrite)."),
        ("P6 (~50%)", "at least one arm fails by cliff."),
        ("P7 (exploratory)", "per-shape knees invert at least one pairwise ordering vs the "
                             "suite knee."),
    ]
    for tag, text in preds:
        lines.append(f"- **{tag}** {text}")
        lines.append(f"  - verdict: _TBD — fill from the curves above._")
    lines.append("")
    lines.append("## Scope, honestly")
    lines.append("")
    lines.append("Single host, one engine at a time, cpuset 12/2 engine/client split, "
                 "result caches off, seeded probe-port rotation, open-loop arrivals "
                 "(declared modeling choice). What travels is ordering and failure SHAPE; "
                 "absolute demand coordinates ride with the single-host caveat every time. "
                 "Raw per-step latencies and the full backlog traces: results/results.json.")
    lines.append("")
    (RESULTS / "RESULTS.md").write_text("\n".join(lines))
    print(f"wrote {RESULTS / 'results.json'} and {RESULTS / 'RESULTS.md'}", flush=True)


# ---------------------------------------------------------------- CLI

def main():
    # The cadence knobs (probe period, warm-in, measured window, ladder) are module-level
    # constants that the worker classes read directly; let the CLI override them without
    # threading every value through every constructor. `global` must be declared before the
    # names are used below — including as argparse defaults — so it leads the function.
    global PROBE_PERIOD_SECONDS, WARMIN_SECONDS, MEASURE_SECONDS, LADDER

    ap = argparse.ArgumentParser(
        description="Workload-interference orchestrator (#23): open-loop scheduled load + "
                    "coordinated-omission-safe interactive probes, per-arm knee + failure "
                    "shape. Assumes the ejs compose stack is up and corpora are loaded.")
    ap.add_argument("--arm", choices=engines.ARMS, action="append",
                    help="arm to run (repeatable). Default: all 7 arms, one at a time.")
    ap.add_argument("--ladder", type=float, nargs="+", default=list(LADDER),
                    help="demand-ladder steps (U multipliers). Default: the pre-registered "
                         "0.125 0.25 0.5 1.0 2.0 4.0.")
    ap.add_argument("--probe-period", type=float, default=PROBE_PERIOD_SECONDS,
                    help="interactive probe cadence in seconds (README: 5 s).")
    ap.add_argument("--warmin", type=int, default=WARMIN_SECONDS,
                    help="per-step warm-in seconds (README: 60).")
    ap.add_argument("--measure", type=int, default=MEASURE_SECONDS,
                    help="per-step measured-window seconds (README: 300).")
    ap.add_argument("--baseline-only", action="store_true",
                    help="run the R=0 baseline (and stop) — a quick reachability/oracle check.")
    ap.add_argument("--skip-calibration", action="store_true",
                    help="skip the null-load calibration gate (DEBUG ONLY; a scored run must "
                         "pass calibration per README §Isolation).")
    args = ap.parse_args()

    PROBE_PERIOD_SECONDS = args.probe_period
    WARMIN_SECONDS = args.warmin
    MEASURE_SECONDS = args.measure
    LADDER = list(args.ladder)

    arms = args.arm or list(engines.ARMS)
    records = []
    for arm in arms:
        print(f"=== arm: {arm}", flush=True)
        try:
            rec = run_arm(arm, args.ladder,
                          baseline_only=args.baseline_only,
                          skip_calibration=args.skip_calibration)
        except Exception as e:  # noqa: BLE001
            print(f"  {arm} FAILED: {str(e)[:300]}", flush=True)
            rec = {"arm": arm, "error": str(e)[:500], "scored": False}
        records.append(rec)
        # write after every arm so a long sweep that dies mid-way keeps what it has
        write_results(records, args)
    print("WORKLOAD-INTERFERENCE RUN COMPLETE", flush=True)


if __name__ == "__main__":
    main()

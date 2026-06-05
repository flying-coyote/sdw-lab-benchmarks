"""Shared determinism + measurement helpers for the SDW Lab benchmarks.

Everything that could introduce nondeterminism in *corpus generation* is
centralised here: one master seed, one fixed wall-clock anchor, no
``datetime.now()`` and no unseeded randomness. A re-run reproduces every
generated corpus, and therefore every *answer*, exactly.

Timing is the one thing that is legitimately nondeterministic. ``time_trials``
below measures wall-clock latency, which varies by machine and by run; the
determinism guarantee covers the corpus and the query answers, never the
timings. Each benchmark says so in its own METHODOLOGY.
"""

import json
import os
import random
import time

import duckdb

# One master seed shared across every benchmark. Each module derives a sub-seed
# from it so corpora are independent but still fully determined by this constant.
MASTER_SEED = 20260601

# A fixed wall-clock anchor for all synthetic timestamps. Using a constant (not
# datetime.now()) is what makes a corpus reproducible run to run.
BASE_EPOCH = 1_767_225_600  # 2026-01-01T00:00:00Z, as a Unix epoch second


def new_rng(sub_seed: int) -> random.Random:
    """A private PRNG, seeded deterministically off the master seed."""
    return random.Random(MASTER_SEED + sub_seed)


def _default_memory_limit() -> str:
    """A DuckDB memory_limit that auto-scales to the host (≈60% of RAM), so the
    same harness is safe under a 24GB WSL cap and opens up after the .wslconfig
    bump to 48GB with no edit. ``SDW_DUCK_MEMORY_LIMIT`` overrides it."""
    env = os.environ.get("SDW_DUCK_MEMORY_LIMIT")
    if env:
        return env
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    gb = int(line.split()[1]) / 1024 / 1024
                    return f"{max(2, int(gb * 0.6))}GB"
    except Exception:
        pass
    return "12GB"


# Shared DuckDB resource defaults. ``memory_limit`` makes a heavy bench spill to
# disk instead of OOM-ing the whole WSL VM; ``temp_directory`` puts that spill on
# native ext4 (never /mnt/c, which is slow 9p and nearly full). Neither changes
# query results — they only govern where and when DuckDB spills — so wiring them
# into every harness is determinism-safe. ``threads`` is deliberately NOT set:
# changing it reorders parallel output and the Parquet byte-layout (see
# ocsf-parquet-determinism), which would churn file sizes for no benefit.
DUCK_MEMORY_LIMIT = _default_memory_limit()
DUCK_TEMP_DIR = os.environ.get(
    "SDW_DUCK_TEMP_DIR", os.path.join(os.path.expanduser("~"), ".duckdb_tmp"))


def configure_duckdb(con: duckdb.DuckDBPyConnection) -> duckdb.DuckDBPyConnection:
    """Apply the shared resource limits to a connection and return it (chainable):
    ``con = configure_duckdb(duckdb.connect(...))``."""
    try:
        os.makedirs(DUCK_TEMP_DIR, exist_ok=True)
        con.execute(f"SET memory_limit='{DUCK_MEMORY_LIMIT}'")
        con.execute(f"SET temp_directory='{DUCK_TEMP_DIR}'")
    except Exception:
        pass  # never let a resource hint break a benchmark run
    return con


def connect() -> duckdb.DuckDBPyConnection:
    """An in-memory DuckDB connection with the JSON functions available and the
    shared resource limits applied."""
    con = duckdb.connect(database=":memory:")
    # json_extract_string et al. ship in core DuckDB; this is belt-and-braces.
    try:
        con.execute("INSTALL json; LOAD json;")
    except Exception:
        pass
    return configure_duckdb(con)


def prf1(true_set, predicted_set):
    """Precision / recall / F1 of a predicted set against ground truth."""
    tp = len(true_set & predicted_set)
    fp = len(predicted_set - true_set)
    fn = len(true_set - predicted_set)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


def canonical(obj) -> str:
    """Stable JSON serialisation, for content hashing and determinism checks."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def time_trials(fn, warmup: int = 2, trials: int = 7):
    """Measure wall-clock latency of ``fn`` over repeated calls.

    The first ``warmup`` calls are discarded (page cache, JIT of any query plan,
    library import warmth); the next ``trials`` are timed with
    ``time.perf_counter`` and summarised. Returns milliseconds.

    This is the deliberately nondeterministic part of a perf benchmark: the
    median is the headline, min/max bound the run-to-run spread on the machine
    it ran on, and the caller is responsible for naming that machine. Nothing
    here is a universal constant.
    """
    for _ in range(warmup):
        fn()
    samples = []
    for _ in range(trials):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000.0)
    samples.sort()
    n = len(samples)
    median = samples[n // 2] if n % 2 else (samples[n // 2 - 1] + samples[n // 2]) / 2
    return {
        "median_ms": round(median, 3),
        "min_ms": round(samples[0], 3),
        "max_ms": round(samples[-1], 3),
        "trials": n,
        "warmup": warmup,
    }

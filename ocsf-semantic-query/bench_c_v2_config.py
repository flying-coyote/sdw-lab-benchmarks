"""BENCH-C v2 — shared configuration + paths, committed BEFORE the scored re-run.

Single place for the v2 fairness-locked constants so every arm reads the same values and a
reviewer can audit them in one file. Governing docs: BENCH-C-PREREGISTRATION-v2-rerun.md and
BENCH-C-PREREGISTRATION-v2-ADDENDUM-impl-decisions.md.

LOCKED retrieval params (v1 values, NOT tuned — re-asserted here so no arm can drift them):
the BM25 channel is a *strategy* change layered on top of these, never a budget change.

A9 / Store-F scoping note (FAIRNESS): the v1 shared store_f/asset.parquet has exactly 2 asset
rows, and BENCH-A (bench-a-context-collapse/bench.py) + ocsf-semantic-testbed/validate.py both
ASSERT `distinct_asset_count == 2` and query the 2-row f_asset. Mutating the shared asset table
or the shared ground_truth.json would silently break those benches. So the v2 12-asset
enlargement is written as a BENCH-C-LOCAL overlay (store_f_v2/asset.parquet + ground_truth_v2.json)
that only the v2 BENCH-C arms read; the shared corpus stays byte-identical. The v2 gold
distinct-asset count lives in the v2 truth file, not the shared one.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))

# --- shared (v1) corpus, untouched ---
STORE_F = os.path.join(HERE, "..", "bench-a-context-collapse", "_work", "store_f")
GT = os.path.join(HERE, "..", "ocsf-semantic-testbed", "_work", "ground_truth.json")

# --- v2 BENCH-C-local overlay (the only thing the enlargement regenerates) ---
WORK_V2 = os.path.join(HERE, "_work", "v2")
STORE_F_V2_ASSET = os.path.join(WORK_V2, "asset_v2.parquet")
GT_V2 = os.path.join(WORK_V2, "ground_truth_v2.json")

# --- LOCKED retrieval params (v1 values; do NOT change — see run_graphrag.py docstring) ---
K_SEED = 20
HOPS = 1
NODE_BUDGET = 150
EDGE_BUDGET = 300

# --- BM25 hybrid (lookup class A2/A6/A8 only; tail unaffected) ---
BM25_TOPK = K_SEED            # take the same number of keyword seeds as vector seeds, then UNION
BM25_K1 = 1.5                 # Okapi standard
BM25_B = 0.75                 # Okapi standard
LOOKUP_CLASS = {"A2", "A6", "A8"}   # exact-fact retrieval queries the hybrid channel serves
TAIL_CLASS = {"A3", "A4", "A7", "A9"}  # compute-over-population (structured-graph-query channel)

# --- trials (addendum §6) ---
TRIALS_LLM = 8               # arms with an LLM generation step
TRIALS_DETERMINISTIC = 1     # OBDA template / metrics-layer / structured-query EXECUTION

# --- A4 ill-posedness (addendum §1) ---
# The NL anchor is the privilege-escalation marker event's timestamp (the no-MFA AttachUserPolicy
# event). v1 confirmed on-disk: that anchor yields 45 active sessions, the gold pit_point_ms (2.7h
# later, tied to NO named chain stage) yields 35. The NL-as-worded does NOT determine the gold, so
# A4 is EXCLUDED from the scored head-to-head as ill-posed and reported as a question-design finding.
A4_EXCLUDED_ILL_POSED = True
A4_NL_ANCHOR_EVENT_UID = "api-needle-nomfa"   # the priv-esc marker; anchor = its `time`

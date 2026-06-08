# READINESS — ocsf-rls-overhead

Status as of 2026-06-08. Run this doc top-to-bottom before starting the workload.

---

## 1. Prerequisites

| item | check |
|---|---|
| `.venv` built and `duckdb==1.5.3` present | run the gate below |
| No other heavy DuckDB benchmark running | serialise — co-running inflates CV |
| Windows power plan set to **High Performance** | per BENCHMARKING-METHODOLOGY.md §7 |
| At least ~4 GB free RAM (1M-row default) | `free -h` |
| At least ~8 GB free RAM (5M-row run) | `free -h` |

### Dependency gate

```bash
# Run from the repo root — should print "deps ok, duckdb 1.5.3"
/home/jerem/sdw-lab-benchmarks/.venv/bin/python3 -c \
  "import duckdb, statistics, hashlib, json; print('deps ok, duckdb', duckdb.__version__)"
```

No extra packages required beyond the top-level `requirements.txt`; the benchmark uses only
`duckdb` (already in the venv) and the Python standard library.

---

## 2. Run when the box is free

All heavy DuckDB benchmarks in this repo are serialised. Confirm no other bench is running
before starting. The workload uses the shared DuckDB venv at
`/home/jerem/sdw-lab-benchmarks/.venv/`.

### Default run (1M rows, ~2–5 minutes)

```bash
cd /home/jerem/sdw-lab-benchmarks
.venv/bin/python3 ocsf-rls-overhead/run.py
```

**Expected runtime:** 2–5 minutes for the 1M-row default (3 tiers × 4 queries × 3 approaches
× 9 trials each = 324 DuckDB executions, most sub-second).

### Larger run (5M rows, ~10–20 minutes, stronger signal)

```bash
cd /home/jerem/sdw-lab-benchmarks
.venv/bin/python3 ocsf-rls-overhead/run.py --rows 5000000
```

**Expected runtime:** 10–20 minutes. The corpus is still in-memory; 5M rows at ~200 bytes per
row is ~1 GB, well within the WSL2 48 GB cap.

### Background (5M, log to file)

```bash
cd /home/jerem/sdw-lab-benchmarks
nohup .venv/bin/python3 ocsf-rls-overhead/run.py --rows 5000000 \
    > ocsf-rls-overhead/results/run.log 2>&1 &
echo $!
```

Tail progress: `tail -f ocsf-rls-overhead/results/run.log`

---

## 3. Determinism gate

After any run, verify the corpus reproduced identically by comparing the
`corpus_logical_fingerprint` in `results/results.json` across two runs on the same
`--rows` value. They must match; a mismatch means the seed was changed or the DuckDB hash
function behaved differently.

```bash
# Run once, record fingerprint
.venv/bin/python3 ocsf-rls-overhead/run.py --rows 1000000
FP1=$(python3 -c "import json; d=json.load(open('ocsf-rls-overhead/results/results.json')); print(d['corpus_logical_fingerprint'][:16])")

# Run again, compare
.venv/bin/python3 ocsf-rls-overhead/run.py --rows 1000000
FP2=$(python3 -c "import json; d=json.load(open('ocsf-rls-overhead/results/results.json')); print(d['corpus_logical_fingerprint'][:16])")

echo "FP1=$FP1  FP2=$FP2  match=$([ \"$FP1\" = \"$FP2\" ] && echo YES || echo NO)"
```

Also confirm: `all_answers_identical: true` in `results/results.json`. If false, inspect the
`answers_identical_predicate_vs_view` field per (tier, query) in the JSON — a false means
the predicate and view returned different result sets for that combination, which is a logic
error in the harness, not a performance finding.

---

## 4. Render results

After a completed run, re-render `RESULTS.md` from the existing JSON without re-running:

```bash
.venv/bin/python3 ocsf-rls-overhead/run.py --render-only
```

---

## 5. Methodology cross-references

- **BENCHMARKING-METHODOLOGY.md** — CV threshold, High-Performance power plan, isolation rule,
  configuration parity
- **lib/common.py** `time_trials` — warmup + trial convention (warmup=2, trials=7)
- **lib/common.py** `logical_fingerprint` — order-independent corpus hash
- **q3-catalog-benchmark** — the catalog-layer RLS leg (not measured here); cross-reference
  before publishing any end-to-end RLS overhead claim
- **H-SECURITY-02** (`01-knowledge-base/hypotheses/extended-hypotheses.md`) — the hypothesis
  this advances; performance impact measurement is one of its listed validation criteria

---

## 6. Interpretation checklist (before citing results)

- [ ] CV% reported alongside every median; don't cite an overhead % that is below the CV
- [ ] Note that this is engine-side only — catalog-layer enforcement is not measured
- [ ] Confirm `all_answers_identical: true`; if false, stop and debug before citing
- [ ] Label as Tier B (single machine, embedded engine, in-memory corpus)
- [ ] Cross-reference q3-catalog-benchmark when making end-to-end RLS claims

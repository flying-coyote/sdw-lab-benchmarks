# READINESS — ocsf-zorder-pruning

Run this benchmark when the box is free of competing DuckDB workloads.
Steps 1–4 are quick checks; steps 5–7 run in sequence.

---

## 1. Box free?

Confirm no other benchmark is running on the Beelink:

```bash
# check for any active DuckDB processes on the host
pgrep -a duckdb || echo "clear"
```

If another benchmark owns the box (e.g. sdpp-ingest-throughput is mid-run), **stop here**
and wait — co-running a timing bench inflates CV and can corrupt the other workload's
throughput numbers (BENCHMARKING-METHODOLOGY.md §5).

---

## 2. Power plan

Set Windows power plan to **High Performance** before timing.
(Balanced plan's on-demand governor adds CV 5.8% → 19.8% on short queries —
BENCHMARKING-METHODOLOGY.md §7 / env_characterize.py.)

No WSL-side action needed; the power plan setting persists across WSL restarts.

---

## 3. Verify venv and deps

```bash
/home/jerem/sdw-lab-benchmarks/.venv/bin/python3 -c "
import duckdb, pyarrow
import sys, os
sys.path.insert(0, '/home/jerem/sdw-lab-benchmarks/lib')
from common import configure_duckdb, logical_fingerprint, time_trials, pin_artifact, parquet_manifest
print('duckdb', duckdb.__version__)
print('pyarrow', pyarrow.__version__)
print('lib/common imports ok')
"
```

Expected output (exact versions pinned in requirements.txt):
```
duckdb 1.5.3
pyarrow 23.0.1
lib/common imports ok
```

Any `ImportError` or version mismatch: run `pip install -r /home/jerem/sdw-lab-benchmarks/requirements.txt` in the venv.

---

## 4. Syntax / import check (light — no DuckDB queries)

```bash
/home/jerem/sdw-lab-benchmarks/.venv/bin/python3 -c "
import ast, sys
with open('/home/jerem/sdw-lab-benchmarks/ocsf-zorder-pruning/run.py') as f:
    src = f.read()
ast.parse(src)
print('AST parse OK')
"
```

Then confirm the module imports without invoking `main()`:

```bash
/home/jerem/sdw-lab-benchmarks/.venv/bin/python3 - <<'EOF'
import sys, types

# stub duckdb and pyarrow so no engine initialises
sys.modules['duckdb'] = types.ModuleType('duckdb')
sys.modules['duckdb'].__version__ = '1.5.3_stub'
sys.modules['pyarrow'] = types.ModuleType('pyarrow')
sys.modules['pyarrow'].__version__ = '23.0.1_stub'
sys.modules['pyarrow.parquet'] = types.ModuleType('pyarrow.parquet')
import pyarrow.compute  # may need stubs if compute is used at import time
sys.modules['pyarrow.compute'] = types.ModuleType('pyarrow.compute')

# stub lib/common
import types as _t, sys as _s
_m = _t.ModuleType('common')
_m.BASE_EPOCH = 1_767_225_600
_m.configure_duckdb = lambda c: c
_m.logical_fingerprint = lambda *a, **kw: ''
_m.new_rng = lambda s: __import__('random').Random(s)
_m.parquet_manifest = lambda *a, **kw: {}
_m.pin_artifact = lambda *a, **kw: {}
_m.sha256_file = lambda p: ''
_m.time_trials = lambda fn, **kw: {}
_s.modules['common'] = _m

sys.path.insert(0, '/home/jerem/sdw-lab-benchmarks/ocsf-zorder-pruning')
sys.path.insert(0, '/home/jerem/sdw-lab-benchmarks/lib')
import importlib.util
spec = importlib.util.spec_from_file_location(
    'run', '/home/jerem/sdw-lab-benchmarks/ocsf-zorder-pruning/run.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
print('module import OK — no DuckDB query executed')

# smoke-test pure-Python Z-value helpers (no engine)
z = mod.bit_interleave_3(0xFFFF, 0xFFFF, 0xFFFF)
assert z > 0, 'bit_interleave_3 should be non-zero for (max,max,max)'
print(f'bit_interleave_3(0xFFFF,0xFFFF,0xFFFF) = {z:#x}  (expected 0x{(2**48-1):#x})')

scaled = mod._scale([0, 100, 200], 0, 200)
assert scaled == [0, 32767, 65535], f'_scale wrong: {scaled}'
print(f'_scale([0,100,200], 0, 200) = {scaled}  OK')
EOF
```

Expected output (last few lines):
```
module import OK — no DuckDB query executed
bit_interleave_3(0xFFFF,0xFFFF,0xFFFF) = 0xffffffffffff  (expected 0xffffffffffff)
_scale([0,100,200], 0, 200) = [0, 32767, 65535]  OK
```

---

## 5. Run (default corpus, 2M rows)

```bash
cd /home/jerem/sdw-lab-benchmarks
source .venv/bin/activate
python ocsf-zorder-pruning/run.py
```

**Expected runtime:** 5–12 minutes on the Beelink (Ryzen 5800H, 48 GB WSL cap):
- corpus generation (2M rows, pure Python PRNG): ~30–60 s
- three Parquet writes (unordered, sorted, Z-sorted): ~20–40 s total
- row-group statistics read: ~5 s
- query timing (4 queries × 3 layouts × 9 trials): ~3–8 min

Progress is printed for each phase; timing lines appear as each query/layout finishes.

**Expected output summary:**
```
  generating 2,000,000-row OCSF corpus…
  writing unordered…
  writing single_sort (by src_ip_int)…
  writing z-order (src_ip_int × dst_port × time_bucket)…
  timing queries (warmup=2, trials=7 per query × layout)…
    Q1_src_ip_and_time             unordered    <ms>  (cv <pct>%)
    Q1_src_ip_and_time             single_sort  <ms>  (cv <pct>%)
    Q1_src_ip_and_time             zorder       <ms>  (cv <pct>%)
    … (Q2, Q3, Q4) …
wrote results/results.json
wrote results/RESULTS.md
answer equality: all layouts agree on all queries
```

If answer equality FAILS, the output names the failing query.  That is a bug in the
run, not a Z-order correctness issue (all three layouts read the same logical data).

---

## 6. Run (larger corpus, optional — stronger pruning signal)

```bash
python ocsf-zorder-pruning/run.py --rows 5000000
```

Expected runtime: 20–40 minutes.  Output overwrites `results/results.json`.
Run this after the 2M run is clean; the results file is not versioned (add a timestamp
prefix if keeping both: `results/results_5m.json`).

---

## 7. Determinism gate (post-run)

After any successful run, confirm the logical fingerprints in `results/results.json`
are stable across a second run at the same `--rows`:

```bash
python -c "
import json
with open('ocsf-zorder-pruning/results/results.json') as f:
    r = json.load(f)
for layout, art in r['artifacts'].items():
    print(layout, art['logical_fingerprint'][:16], '...')
"
```

Re-run `run.py` and compare the fingerprints.  They should be identical across runs
because the corpus generator is fully seeded (`lib.common.new_rng(SUB_SEED)`) and
the sort is deterministic.  A mismatch means the generator or the sort has a
non-deterministic branch — investigate before publishing results.

---

## What success looks like

A clean run produces:

- `results/results.json` — full results with artifacts, pruning counts, latencies,
  answer equality, environment, and determinism fingerprints
- `results/RESULTS.md` — human-readable tables (write cost, pruning, latency)
- Console: "answer equality: all layouts agree on all queries"

The pruning tables should show Z-order with a higher `pct_pruned` than UNORDERED and
SINGLE_SORT on Q1, Q2, Q3 (multi-predicate queries spanning the clustering dimensions).
If Z-order does NOT prune more than SINGLE_SORT on those queries, record that honestly
— it may mean the corpus's IP/time distribution is too uniform to cluster well at this
row-group size, or the selectivity is too high (too many matching rows to skip groups).
That is a finding worth publishing, not a failure.

---

## After the run

1. Check that `cv_pct` values are below 10% for all layout × query pairs.
   Outliers above 10% should be noted in RESULTS.md; above 20% the number is noise.
2. Update `CAMPAIGN.md` with a new campaign entry once the run is clean.
3. Apply the `voice-consistency-enforcer` + `publication-quality-checker` gates before
   using RESULTS.md in any securitydataworks publish.

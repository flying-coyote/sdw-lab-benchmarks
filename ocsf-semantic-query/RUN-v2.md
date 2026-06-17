# BENCH-C v2 — how to run the re-run (commands + LLM-invocation mechanism)

The v2 harness separates GENERATION (the LLM-authoring step) from EXECUTION + SCORING (deterministic,
in-repo). The LLM is never called from a Python script in this repo — the v1 result used **Claude-Code
subagents** as the claude-opus-class proxy (workflow `wpr33e44g`), each answering one isolated task
file, and v2 keeps that mechanism. There is no `anthropic` SDK / API key / CLI in the runners; the
"frontier" arm is a subagent that reads a task file's context and returns JSON.

## 0. Prereqs (one-time)

```bash
cd ~/sdw-lab-benchmarks && source .venv/bin/activate
# deps the v2 arms use (installed during build): rank_bm25 (BM25 channel), rdflib (no-Ontop SPARQL exec)
pip install rank_bm25 rdflib
# Store F must exist (shared corpus, already built):
#   ocsf-semantic-testbed/_work/ground_truth.json + bench-a-context-collapse/_work/store_f/*.parquet
# OBDA arm + the canonical structured-query EXECUTION path need Ontop (large; fetched separately):
# Install to a PERSISTENT dir (NOT /tmp — a /tmp copy is wiped on reboot, which is how the v1 install was lost):
curl -sL -o /tmp/ontop.zip https://github.com/ontop/ontop/releases/download/ontop-5.5.0/ontop-cli-5.5.0.zip
python -c "import zipfile; zipfile.ZipFile('/tmp/ontop.zip').extractall('$HOME/tools/ontop-cli')"
mkdir -p "$HOME/tools/ontop-cli/jdbc"
curl -sL -o "$HOME/tools/ontop-cli/jdbc/duckdb_jdbc.jar" \
  https://repo1.maven.org/maven2/org/duckdb/duckdb_jdbc/1.1.3/duckdb_jdbc-1.1.3.jar
chmod +x "$HOME/tools/ontop-cli/ontop"
export ONTOP_HOME="$HOME/tools/ontop-cli"
```

## 1. Regenerate the A9 12-asset overlay (committed before the run)

```bash
cd ~/sdw-lab-benchmarks/ocsf-semantic-query
python gen_a9_assets_v2.py     # writes _work/v2/asset_v2.parquet + _work/v2/ground_truth_v2.json
```
Confirms: 12 asset rows, 9 distinct physical assets after alias closure (GOLD, computed), 3 reassigned-IP
multi-hop chains (>=2-hop closure). Shared corpus + shared ground_truth.json are left untouched.

## 2. Dump the per-query GENERATION tasks (NO LLM)

```bash
python dump_benchc_v2.py       # writes isolated task files -> _frontier/v2/{arm}_{qid}[_{mode}].json
```
Lookup (A2/A6/A8) gets HYBRID-retrieved context; tail (A3/A7/A9) gets vector-only context + SPARQL-
authoring tasks; A4 omitted (excluded ill-posed). Locked params unchanged (K_SEED=20 / HOPS=1 /
NODE_BUDGET=150 / EDGE_BUDGET=300).

## 3. GENERATION — answer each task with a frontier subagent (8 trials/query)

This is the LLM step. For each task file in `_frontier/v2/`, spawn a Claude-Code subagent (the model
is chosen here — this is the model-tiering knob), give it the task file's `context` (graphrag),
`schema` (text2sql), or `ontology` (structured), and have it return JSON only:

- **text2sql** task -> `{"sql": "<one DuckDB SELECT over the RAW tables>"}`
- **structured** task -> `{"sparql": "<one SPARQL SELECT over the OCSF ontology>"}`
- **graphrag** task -> `{"answer": [...] }` or `{"answer": "<value>"}`

Run each task **8 times** (8 trials) for the LLM arms. Collect into one predictions JSON:

```json
{ "trials": 8,
  "text2sql":   [{"qid":"A2","trial":0,"sql":"..."}, ...],
  "structured": [{"qid":"A3","trial":0,"sparql":"..."}, ...],
  "graphrag":   [{"qid":"A2","mode":"structured","trial":0,"answer":[...]}, ...] }
```

**Model-tiering (what the caller controls):** route each arm's task files to a different subagent
model. The arm a task belongs to is in its `arm` field and filename prefix, so e.g. answer
`text2sql_*` and `structured_*` with the top-tier model and `graphrag_*` with a mid-tier model, or
sweep one arm across model tiers by re-running step 3 for that arm with a different subagent model and
tagging the predictions. The harness does not pick the model; the subagent you spawn does. Use the
SAME model across all 8 trials of a given (arm, qid) so the variance band measures decode noise, not
model-mixing. Temperature is the subagent's sampling temperature (v1 ran temperature-sampled, so the
run-to-run variance is real, not temp-0).

Deterministic arms (OBDA / metrics-layer / structured-query EXECUTION) take NO generation step —
they run in-process in step 4.

## 4. EXECUTE + SCORE (deterministic; the shared scorer)

```bash
ONTOP_HOME="$HOME/tools/ontop-cli" \
  python bench_c_v2_headtohead.py --predictions _frontier/v2/v2_predictions.json \
  --out results/v2_headtohead.json
```
- text2sql SQL executed against the RAW tables; structured SPARQL executed via Ontop over the OBDA
  mappings (canonical) — if `ONTOP_HOME` is unset it falls back to the labeled rdflib SPARQL->DuckDB
  executor (smoke-grade; flag if a published number uses it).
- metrics-layer + OBDA run in-process (1 trial each; deterministic).
- A4 excluded everywhere. Every arm scored through `scoring.classify` (byte-identical shared scorer).
- Report ordering: lookup-recall-first (A2/A6/A8), then tail-as-compute-correctness (A3/A7/A9).

## Smoke (NO LLM, NO Ontop) — what was validated at build time

```bash
python bench_c_v2_headtohead.py --smoke     # metrics-layer + OBDA(blocked if no Ontop) + struct-exec
python run_metrics_layer.py                  # the 4th arm standalone
python run_structured_query.py --smoke --exec-fallback   # hand-written SPARQL exec via rdflib
```

## Falsification (committed; from the v2 pre-reg)

- Graph-structure value is NULL if structured-graph-query does not beat metrics-layer + flat on the
  tail after the A9 fix.
- OBDA determinism-safety holds only if OBDA is correct-or-refuses (never silent) on its coverage with
  the A4 anchor NL-derived — and A4 turned out ill-posed, so it is reported, not scored.
- If structured-graph-query is silently wrong on the tail at the text-to-SQL rate, "compute-over-graph
  beats probabilistic compute" fails and the claim narrows to "verify every compute path".

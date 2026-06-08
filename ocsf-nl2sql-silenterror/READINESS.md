# OCSF NL2SQL silent-error benchmark — readiness doc

This benchmark is **authored and light-checked but NOT run**. The heavy evaluation
(local LLM inference + DuckDB queries over Store F) is deferred because another
benchmark currently holds the box; running DuckDB and a local model now would contend
for the same CPU/RAM/Ollama and corrupt both that benchmark's throughput numbers and
this one's. Everything below is staged so the scored run is a few commands once the
box frees.

STATUS: authored + light deps verified present + models present + corpus built.
NOT yet run. No `results/` directory written yet (the run creates it).

This mirrors the readiness pattern of `../ocsf-semantic-query/GRAPHRAG-READINESS.md`:
design + light check now, push-button run later.

---

## 1. What the run does

For each model in `{phi3:latest, gemma4:26b}` at temperature 0, and each of the 33
labeled questions: show the model the Store F schema, get one DuckDB SQL query, execute
it over Store F, compare the executed result to the hand-authored gold, classify
**correct / silent / loud**. Report each model's overall silent-error rate +
result-accuracy and the **by-difficulty breakdown** (the headline: where silent errors
concentrate). Outputs `results/results.json` and `results/RESULTS.md`.

The full design, scoring, and the relationship to BENCH-B / BENCH-C are in
[README.md](README.md). The 33-question labeled set + gold answer key is in
[questions.py](questions.py).

---

## 2. Dependencies — ready vs. to-pull

Repo venv: `/home/jerem/sdw-lab-benchmarks/.venv/bin/python` (3.12.3). Do **not** edit
`lib/common.py`; `run.py` imports `configure_duckdb` from it as the other benchmarks do.

### Ready now (verified this session)

| dep | state | role |
|---|---|---|
| `duckdb` 1.5.3 | present in the repo venv | execute SQL over Store F |
| `requests` 2.34.2 | present in the repo venv | Ollama `/api/generate` |
| Ollama daemon | UP at `localhost:11434` (`/api/tags` responded) | local LLM inference |
| `phi3:latest` | present in `ollama list` (id `4f2222927938`, 2.2 GB) | small-model leg |
| `gemma4:26b` | present in `ollama list` (id `5571076f3d70`, 17 GB) | primary local model |
| Store F | built on disk, **7/7** parquet tables present | the corpus |
| ground truth | `../ocsf-semantic-testbed/_work/ground_truth.json` present (the planted needles) | gold for the `truth` questions |
| manifest | `../ocsf-semantic-testbed/_work/manifest.json` present | source of the `literal` gold counts |

### To pull when the box frees

**Nothing.** No model pull, no pip install, no sudo, no docker. Both pinned models are
already local and the corpus is already built. If a future frontier leg is added (to
make the silent-vs-loud contrast bite harder — see README evidence tier), that needs an
API key, which is not available here; it is a documented expansion, not a blocker for
this local-tier run.

### If Store F were ever missing (it is present now)

It is rebuilt deterministically from the seed (do this only when the box is free; it
runs DuckDB):

```bash
.venv/bin/python ocsf-semantic-testbed/generate.py     # the shared corpus (~177k events)
cd bench-a-context-collapse && python run.py && cd ..   # builds Store F + Store N
```

---

## 3. Light checks that are safe to run anytime (no DuckDB, no LLM)

These touch neither DuckDB nor Ollama and were run during authoring:

```bash
.venv/bin/python -m py_compile ocsf-nl2sql-silenterror/questions.py ocsf-nl2sql-silenterror/run.py
.venv/bin/python ocsf-nl2sql-silenterror/questions.py        # 33 questions / 7 tiers self-check
.venv/bin/python ocsf-nl2sql-silenterror/run.py --determinism # scorer stability + tier counts
```

Expected `--determinism` output: `question ids unique: True (33 questions, 7 tiers)`,
the tier counts, `scorer stable + correct on fixed inputs: True`, and the greedy-decode
caveat note.

---

## 4. TO RUN WHEN THE BOX IS FREE

```bash
# 1. (sanity) light deps + corpus present — no DuckDB, no LLM
/home/jerem/sdw-lab-benchmarks/.venv/bin/python -c "import duckdb, requests; print('deps ok')"
ls /home/jerem/sdw-lab-benchmarks/bench-a-context-collapse/_work/store_f/*.parquet   # expect 7
ls /home/jerem/sdw-lab-benchmarks/ocsf-semantic-testbed/_work/ground_truth.json

# 2. confirm the two models are present and the daemon is up
ollama list | grep -E 'phi3:latest|gemma4:26b'
curl -s http://localhost:11434/api/tags >/dev/null && echo 'ollama up'

# 3. the scored run — both local models, temperature 0
/home/jerem/sdw-lab-benchmarks/.venv/bin/python \
    ocsf-nl2sql-silenterror/run.py --models phi3:latest gemma4:26b

# 4. (optional) re-render RESULTS.md from results.json — no DuckDB, no LLM
/home/jerem/sdw-lab-benchmarks/.venv/bin/python \
    ocsf-nl2sql-silenterror/run.py --render-only
```

`run.py` writes `results/results.json` (sorted, deterministic shape) and
`results/RESULTS.md` (the by-tier table per model). It can be re-rendered from the JSON
without re-running the eval.

---

## 5. Expected runtime

33 questions × 2 models = **66 generations**, plus the gold-oracle SQL (run once per
question) and the model-SQL execution (once per question per model) over Store F.

- The `gold_via="sql"` oracle queries and the model-SQL executions are simple DuckDB
  scans/aggregations over ~177k-event parquet — milliseconds to low-seconds each, so the
  DuckDB side is **a few minutes** total.
- The binding cost is the **66 LLM generations**, dominated by `gemma4:26b` (17 GB)
  latency. At temperature 0 and a short JSON-only completion, expect **order tens of
  minutes** for `gemma4:26b` and a few minutes for `phi3:latest` — roughly
  **20-40 minutes** wall-clock for both models on the local WSL2 host, nothing else
  contending. (`keep_alive: "10m"` keeps the model resident across the 33 calls so it is
  loaded once per model, not per question.)

The hard precondition is just **don't run it while the other benchmark holds the box** —
the LLM and DuckDB both contend for CPU/RAM and would skew both runs' numbers.

---

## 6. Determinism + caveats (state these in any write-up)

- The **corpus** (Store F) and **ground truth** are a pure function of `MASTER_SEED=20260601`
  (the testbed's two-build fingerprint discipline); the **gold answer key** is hand-authored
  (`truth` needles / `literal` invariants / `sql` reference oracle), never an LLM; the
  **correct/silent/loud scorer** is a pure function asserted stable by `--determinism`.
- The one non-deterministic step is the **LLM SQL composition**: temperature-0 greedy
  decode is reproducible *in practice* but *not asserted* (a background Ollama model update
  could change a completion). Pin the model digests (`ollama list` ids above) when recording
  a result.
- **Tier B**: local models, single machine, one synthetic planted chain, 33 hand-authored
  questions, exact-result scoring that can undercount a defensible alternative answer. The
  by-difficulty silent-error shape is the readable signal; the magnitudes are
  model-and-question-specific. Tier-A gates: a published larger labeled set, a named reviewer
  on ambiguous gold, an independent frontier-model leg (needs an API key), a non-toy scale.

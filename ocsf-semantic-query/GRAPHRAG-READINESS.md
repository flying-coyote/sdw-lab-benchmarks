# BENCH-C GraphRAG arm — readiness doc

The third arm of the BENCH-C head-to-head (`ocsf-semantic-query`): a GraphRAG runtime
that builds a concept graph + a vector index over the OCSF fidelity store, retrieves a
relevant subgraph plus the top-k vector neighbours per question, hands that context to a
local LLM to compose the answer, and scores the answer with the **same correct / silent /
loud definition the text-to-SQL and OBDA arms already use**. This document is the design,
the light-dep readiness check, and the push-button run plan. Nothing heavy has been run:
no graph built, no embeddings computed, no LLM called, because another benchmark is on the
box and contending for it now would slow both. Everything below is staged so the run is a
single command once the box frees.

This is a **READINESS** artifact. When the arm actually runs and merges its block into
`results/results.json`, replace the "STATUS" line below and append a results section, the
way `run_obda.py` merges the `obda_ontop` block.

STATUS: REBUILT for structured (entity-layer) retrieval; `py_compile`-clean; scored run gated.
The original arm embedded one vector per telemetry event (~100k+ on Store F) — the design that
stalled CPU embedding for hours. The rebuild (`node_documents` + `ENTITY_NTYPES`, 2026-06-08)
vector-indexes ONLY the entity/concept layer (hosts, users, ips, domains, endpoints, resources,
roles — a few hundred nodes); the event nodes stay in the graph and are pulled by the existing
2-hop ego traversal in `retrieve()`, not embedded. So the embedding cost drops from ~100k vectors
to a few hundred. `nomic-embed-text` is now present in Ollama (the previously-missing dep).
`scoring.py` is unit-tested against the real `ground_truth.json` (22 cases, all 7 kinds, pass).

WHAT REMAINS (Phase-B gated): the **publishable** scored comparison still needs the Phase-B
protocol the program plan requires before any model run is reported as a benchmark result — a
pre-registration doc and, critically, a **`flat_retrieval` control** (same facts as prose, no
graph structure) to isolate retrieval-value from graph-structure-value. A bare run of the rebuilt
arm validates that it executes end-to-end without the stall and produces correct/silent/loud
outcomes, but it is a smoke test, not the pre-registered head-to-head, until `flat_retrieval` lands.

VALIDATION (2026-06-08, phi3, per-phase timing): the rebuild is confirmed functional end-to-end.
build_graph 5.3s (234k nodes / 355k edges), entity embeddings cached (2,504 vectors, 0s reload),
sameAs index 0.3s, **bounded** retrieve <0.1s (keep ≈ 157), serialize 0.3s. The only slow phase is
CPU LLM generation at ~260s/query (phi3, ~6k-token context), so a full 9-query run is ~40 min of
inference — an environment cost, not the embedding stall (which is gone). Two further fixes were
needed beyond entity-layer embedding, both design-consistent and documented in code: HOPS=1 (an
entity seed is one hop from its events) and excluding the 54k high-cardinality `endpoint`
(dst_ip:dst_port) tuples from the embed set, plus bounded per-seed expansion + a precomputed sameAs
index in `retrieve()` so a super-hub host-entity on a 2-host corpus doesn't blow up the subgraph.

---

## 1. The contract this arm must match

The GraphRAG arm is not free to invent its own question set, corpus, or scoring. All three
are fixed by the shared testbed and the two arms already implemented, so the comparison is
apples-to-apples. Reading them off the existing code:

### The question set (the A-questions)

The arms answer the adversary-tail concept queries planted in the shared corpus
(`../ocsf-semantic-testbed/`). The full battery is A1–A10; the two implemented arms each
run a subset against the same ground-truth needles. The GraphRAG arm runs the **same eight
adversary queries the OBDA arm enumerates (A1–A9 minus A8's slot in OBDA, plus A8)** so the
three arms line up query-for-query. Concretely, the union the GraphRAG arm must answer and
the needle each scores against (`../ocsf-semantic-testbed/_work/ground_truth.json` →
`truth_needles`):

| id | natural-language question | truth_key | kind | text-to-SQL | OBDA/Ontop |
|---|---|---|---|---|---|
| A1 | beaconing conn: ~60s regular inter-arrival, low bytes, ~1h, return event_uid set | `beacon_conn_uids` (60) | uidset | run (loud) | out-of-OWL2QL |
| A2 | exact PowerShell `-EncodedCommand` cmdline on WS1 | `powershell_encoded_cmd` | substring | run (correct) | expressible (correct) |
| A3 | cross-source kill-chain stage ordering | `truth_event_order` (7) | order | — | out-of-OWL2QL |
| A4 | sessions valid at the point-in-time instant `pit_point_ms` | `pit_active_session_uids` (35) | count | — | expressible (correct) |
| A5 | identity closure: all identifiers of the one human actor | `truth_identity_links` | set | — | out-of-OWL2QL |
| A6 | AttachUserPolicy with MFA absent (`mfa_present=false`), return event_uid | `nomfa_event_uid` | uid | run (correct) | expressible (correct) |
| A7 | dwell-time delta (seconds) of the chain | `dwell_seconds` | scalar | — | out-of-OWL2QL |
| A8 | first-seen DNS domain queried by WS1 (appears once) | `c2_domain` | substring | run (loud) | — |
| A9 | distinct-asset count behind the six identifiers | `distinct_asset_count` (=2) | scalar | — | out-of-OWL2QL |

Note the two arms run overlapping-but-different subsets: text-to-SQL runs {A1, A2, A6, A8};
OBDA runs {A1, A2, A3, A4, A5, A6, A7, A9} (the 8 it classifies as expressible-or-not). The
honest GraphRAG comparison runs **the full A1–A9 union (9 queries)** and reports per-query,
so it can be sliced against either arm's subset without re-running. A10 (late-arrival
ingest-vs-event time) is a BENCH-A store-degradation needle, not a BENCH-C concept query in
either implemented arm, so the GraphRAG arm leaves it out for parity (note it as an
intentional omission, not an oversight).

### The corpus

All arms run over the **fidelity store (Store F)** built by BENCH-A:
`../bench-a-context-collapse/_work/store_f/{auth,session,network,dns,process,api,asset}.parquet`.
This is already built on disk (verified). Schemas (the columns the graph is constructed
from):

```
f_auth     event_uid, class_uid, time, logged_time, user_uid, src_country, src_ip, outcome, is_success, is_remote, target_host   (27233)
f_session  event_uid, user_uid, host, start_time, end_time, time, logged_time                                                    (4001)
f_network  event_uid, class_uid, time, logged_time, src_ip, src_hostname, dst_ip, dst_port, protocol_name, bytes_out, bytes_in, duration  (60061)
f_dns      event_uid, class_uid, time, src_ip, src_hostname, query_hostname, answer                                              (18001)
f_process  event_uid, class_uid, time, logged_time, device_hostname, actor_user_uid, image_name, cmd_line, parent_image_name, pid (40002)
f_api      event_uid, class_uid, time, logged_time, service, api_operation, actor_user_uid, src_ip, resource, mfa_present, mfa_value, aws_region (28033)
f_asset    hostname, ip, instance_uid, canonical_asset                                                                           (2)
```

~177k events; the planted six-stage chain is on the middle day. The needles are sparse
(60 beacon conns, 30 exfil, 1 no-MFA, etc.) inside the background — that sparsity is the
whole point of the "adversary tail."

### The scoring (must be byte-identical in spirit to the other arms)

Both implemented arms score each query as **correct / silent / loud** with this meaning,
and the GraphRAG arm reuses it verbatim:

- **correct** — the ground-truth needle is recovered in the arm's answer.
- **silent** — the arm produced a confident answer (executed, returned rows / a non-empty
  answer) but the truth is NOT in it. This is the security-relevant failure BENCH-C exists
  to measure (a plausible-but-wrong answer).
- **loud** — the arm failed visibly: SQL errored / empty result when truth is non-empty
  (text-to-SQL), or out-of-expressivity refusal (OBDA). Operationally safer than silent.

The scorer in `run.py:score()` is the canonical instrument and the GraphRAG arm imports the
same kind-dispatch so the comparison is fair:

- `substring` (A2, A8): correct iff `str(truth)` is a substring of any returned cell.
- `uid` (A6): correct iff `str(truth)` is exactly present among returned cells.
- `uidset` (A1): correct iff the answer recovers ≥50% of the needle set AND does not flood
  (`len(returned) <= 4× len(truth)`) — a recall floor with a precision proxy.
- The GraphRAG arm adds the kinds the OBDA arm scores but text-to-SQL's `run.py` doesn't yet
  dispatch, so A3/A4/A5/A7/A9 are scorable: `count` (A4: correct iff the count matches
  `len(truth)`), `scalar` (A7 dwell-seconds, A9 distinct-count: correct iff the exact value
  is recovered, with A7 allowing a small tolerance window documented in the runner),
  `order` (A3: correct iff the recovered stage sequence equals `truth_event_order`), and
  `set` (A5: correct iff the recovered identifier set ⊇ the human's identity links). These
  kinds are defined ONCE in a shared scorer so all arms that run them score them identically.

Critically: a wrong-but-non-empty GraphRAG answer is **silent**, a refusal / empty /
parse-failure is **loud**. That mapping is what makes the GraphRAG number comparable to the
0.00 silent rate text-to-SQL posted and the 0.00 OBDA posts on its expressible set. The
headline BENCH-C metric is the **silent-error rate on the adversary tail**, per arm.

### How arms register in run.py

`run.py` writes one `results/results.json` with an `arms` dict; each arm is a top-level key
under `arms` (`text_to_sql`, `obda_ontop`, `graphrag`). The OBDA arm (`run_obda.py`) is a
separate runner that **reads the existing results.json, merges its `arms["obda_ontop"]`
block, and writes it back** (`run_obda.py:128-132`). The GraphRAG arm follows that exact
pattern: a separate `run_graphrag.py` runner that merges `arms["graphrag"]` into the same
file, so no arm overwrites another and the three accumulate. `run.py:render_md()` already
has an `_obda_section()` and a one-line GraphRAG placeholder; the readiness work includes a
parallel `_graphrag_section()` (or extending render to read the merged block).

### Existing results, so the GraphRAG framing slots in

- **text-to-SQL** (phi4): on its 4-query subset {A1,A2,A6,A8} → 2 correct (A2, A6), 2 loud
  (A1, A8 both returned 0 rows), **0 silent**. The local model fails *loudly* — it
  hallucinates columns/functions so the SQL errors or comes back empty rather than
  returning a confident wrong answer. result-accuracy 0.50, silent-error 0.00. The reading
  in RESULTS.md: at this tier text-to-SQL is near-unusable on the tail and you need a model
  strong enough to even *produce* silent errors before the silent-vs-loud contrast bites.
- **OBDA / Ontop** (5.5.0, OWL2QL over DuckDB): on the 8 queries it enumerates, **3
  expressible** (A2, A4, A6 — all correct, 100% on expressible, 0% silent) and **5
  out-of-OWL2QL** (A1, A3, A5, A7, A9 — refused loud-by-design because aggregation /
  windows / ordering / recursion are outside first-order-rewritable OWL2QL). refusal-honest
  = true: it is *never silently wrong*, its failures are a visible expressivity boundary.

The GraphRAG framing sits between these two poles: it has the LLM's broad coverage (it can
attempt all 9, including the aggregation/recursion queries OBDA refuses) but, unlike the
formal rewrite, it has **no correctness guarantee**, so the open question BENCH-C is built
to answer is whether GraphRAG's broad-but-unverified coverage produces *silent* errors on
the tail where OBDA produces *loud* refusals. That is the decision this arm completes.

---

## 2. GraphRAG arm design

A custom, lightweight, fully-controllable arm — deliberately **NOT** the Microsoft GraphRAG
framework. The trade-off is explicit: Microsoft GraphRAG gives community-summarization and a
batteries-included indexer, but it is opinionated about its LLM/embedding calls, its output
shape, and its scoring, and it would bury the one thing this arm exists to measure (the
correct/silent/loud outcome per planted needle) under its own pipeline. A ~250-line custom
arm over `networkx` + `numpy` + Ollama is fully scorable against the planted ground truth,
deterministic, and consistent with the lab's other probes (which are all small custom
runners over DuckDB + a local model). The cost is that we hand-build entity/edge extraction
and retrieval rather than inheriting them; for a single planted chain over 7 typed tables
that is a feature, not a burden.

### 2a. Graph construction (NetworkX, in-process, deterministic)

Recommend **NetworkX MultiDiGraph** (pure-python, pip, in-process, deterministic node/edge
iteration) over a graph DB. Neo4j would need sudo/docker and a server process — avoid it;
it adds contention and a moving part with no analytic payoff at this scale (~177k events
fit in memory as a graph trivially).

Build the graph by streaming Store F (read the parquet via DuckDB, the same connection
pattern `run.py:connect()` uses). Two node tiers:

**Entity nodes** (the concept layer the graph adds over flat rows):
- `host` — from `device_hostname` (process), `src_hostname`/`dst` (network/dns),
  `host` (session), `target_host` (auth), and `f_asset.hostname`. Asset aliasing
  (hostname ↔ ip ↔ instance_uid) is materialised as `sameAs` edges from `f_asset`, which is
  exactly the A9 distinct-asset-collapse and A5 identity-closure structure.
- `user` — from `user_uid` (auth, session), `actor_user_uid` (process, api).
- `process` — one node per `f_process.event_uid`, carrying `image_name`, `cmd_line`, `pid`.
- `file` / `resource` — from `f_api.resource` (the S3 bucket/object in the exfil burst).
- `network_endpoint` — `(src_ip, dst_ip, dst_port)` from `f_network`.
- `domain` — from `f_dns.query_hostname` (the C2 first-seen domain A8 needs).
- `api_event` / `auth_event` / `session` — typed event nodes for the structural queries
  (A4 sessions, A6 no-MFA api event).

**Edges** (the relationships retrieval walks):
- `actor → action → target`: `user --performed--> process`, `user --called--> api_event`,
  `user --authenticated--> auth_event`.
- `process → parent_process`: link `f_process` rows by `image_name`/`parent_image_name`
  on the same host within a time window (winword.exe → powershell.exe is the A2/stage-1 link).
- `connection src → dst`: `host --connected_to--> network_endpoint --to--> dst_ip`, carrying
  `time`, `bytes_out`, `bytes_in`, `duration` as edge attrs (the A1 beacon cadence lives on
  these edges).
- `auth user@host`: `user --signed_in_on--> host` from `f_auth`/`f_session`.
- `host --queried--> domain` from `f_dns` (A8).
- `host --sameAs--> ip --sameAs--> instance_uid` from `f_asset` (A5/A9 identity collapse).
- `user --assumed--> role` from the cloudtrail assume-role event (A5 identity pivot).

Every node gets a stable id (`f"{type}:{natural_key}"`), so two builds produce an identical
graph; iteration order is fixed by insertion order plus a `sorted()` on any place order
could leak in. The graph is built once per run and (optionally) pickled to `_work/graph.pkl`
so re-scoring doesn't rebuild.

### 2b. Retrieval (local embeddings + deterministic numpy cosine)

**Embedding model**: a LOCAL model via Ollama for consistency with the local-LLM arms —
`nomic-embed-text` (~270 MB, 768-dim) over the `/api/embeddings` endpoint (route verified
live; model not yet pulled). One embedding per "graph document": each entity node and each
event node is serialized to a short text record (`"process powershell.exe on WS1, cmdline
…, parent winword.exe"`) and embedded. Embeddings are cached to `_work/embeddings.npy` +
`_work/embed_ids.json` so they're computed once.

**Vector store**: an **in-memory numpy cosine store** — a single `float32` matrix `(N, 768)`
plus a parallel id list, top-k by `argsort(-cosine)`. This is deterministic (no ANN
randomness, no background index threads), dependency-free (numpy is already installed), and
trivial at this scale (a few tens of thousands of vectors). chromadb is the alternative if a
persistent index is genuinely wanted later, but it pulls heavier native deps and an
HNSW index whose recall is approximate; for a deterministic, re-runnable lab probe the numpy
store is cleaner, so recommend numpy and note chromadb as optional.

**Per-question retrieval** combines both structures:
1. embed the NL question with the same model;
2. top-k (k=20, fixed) vector neighbours over the node-document matrix → seed nodes;
3. expand to the relevant subgraph: the k-hop (h=2, fixed) ego-graph around the seed nodes
   in the NetworkX graph, plus any nodes on a `sameAs` chain from a seed (so identity-collapse
   queries pull the whole alias set);
4. serialize that subgraph (nodes + edges with their attrs, capped at a fixed token budget,
   highest-cosine-first so the cap is deterministic) into the LLM context.

### 2c. Generator LLM (local Ollama, temperature 0)

Same ladder as BENCH-B / the text-to-SQL arm: **`gemma4:26b`** as the primary generator and
**`phi3:latest`** as the small-model leg, both via Ollama `/api/generate`, `temperature: 0`,
`format: "json"`, `keep_alive: "10m"`, the identical request shape as `run.py:compose_sql()`.
(`gemma4:26b`, `phi3:latest`, and also `phi4:latest`, `gemma4:e4b`, `tinyllama` are all
present in `ollama list`, so the generator ladder needs no pull.) The prompt asks the model
to answer the security question from the supplied subgraph context and emit JSON only
(`{"answer": [...]}` or `{"answer": "..."}`), so parsing is deterministic.

### 2d. The per-question loop

```
for q in A1..A9:
    qvec      = embed(q.nl)                         # ollama /api/embeddings
    seeds     = vector_topk(qvec, k=20)             # numpy cosine
    subgraph  = ego_expand(graph, seeds, hops=2)    # networkx + sameAs closure
    context   = serialize(subgraph, token_budget)   # deterministic, cosine-ordered
    raw       = ollama_generate(model, prompt(q, context), temperature=0)
    answer    = parse_json(raw)                      # {"answer": ...}
    outcome   = score(q, answer, truth[q.truth_key]) # SHARED correct/silent/loud scorer
```

Outcome mapping that keeps it identical to the other arms: a parsed non-empty answer that
misses the needle → **silent**; an empty answer, a parse failure, or a model refusal →
**loud**; needle recovered → **correct**.

### 2e. Determinism

- Graph build: pure function of Store F bytes + a fixed node/edge-insertion order with
  `sorted()` guards → identical graph across builds (mirror the testbed's two-build
  fingerprint discipline: build twice, assert the node+edge multiset hashes match before
  scoring).
- Embeddings: pinned embed model (`nomic-embed-text`, record the digest from `ollama list`),
  cached to disk; re-runs read the cache.
- Retrieval: fixed `k=20`, `hops=2`, fixed token budget, deterministic cosine `argsort` with
  a stable tie-break (secondary sort on node id).
- Generation: `temperature: 0` greedy decode, pinned generator model + digest.
- **Caveat to state in the write-up**: temperature-0 greedy decode is reproducible *in
  practice* but not *asserted* — the same caveat `run.py --determinism` already prints for
  the text-to-SQL arm ("the SQL the model composes is temperature-0 greedy decode,
  reproducible in practice, not asserted"). The graph, embeddings (cached), retrieval, and
  scorer ARE deterministic and assertable; only the LLM decode carries the practical caveat.
  A `--determinism` mode mirrors `run.py`'s: assert the graph fingerprint reproduces and the
  scorer is stable on fixed input, and print the greedy-decode caveat for the generation step.

---

## 3. Dependencies — ready vs. to-pull

Repo venv: `/home/jerem/sdw-lab-benchmarks/.venv/bin/python3` (3.12.3). Do **not** edit
`lib/common.py`; the arm imports `configure_duckdb` from it as the other arms do.

### Ready now (verified)

| dep | state | role |
|---|---|---|
| `networkx` 3.6.1 | **installed this session** (pure-python wheel, no native build) | concept graph |
| `numpy` 2.4.6 | already present | in-memory cosine vector store |
| `duckdb` 1.5.3 | already present | read Store F parquet to build the graph |
| `requests` 2.34.2 | already present | Ollama `/api/generate` + `/api/embeddings` |
| `pyarrow` 23.0.1 | already present | parquet (transitive, not directly needed) |
| Ollama daemon | UP at `localhost:11434`; `/api/embeddings` route verified | embed + generate |
| generator models | `gemma4:26b`, `phi3:latest` (also phi4, gemma4:e4b, tinyllama) present in `ollama list` | LLM ladder — no pull needed |
| Store F | built on disk, 7 parquet tables, schemas verified | the corpus |
| ground truth | `_work/ground_truth.json` present, 19 needle keys verified | scoring |

`networkx` install was the only mutation this session:
```bash
/home/jerem/sdw-lab-benchmarks/.venv/bin/python3 -m pip install networkx   # done — 3.6.1
```

### To pull when the box frees (deferred — do NOT run now)

Only one thing is missing, and it is the embedding model. The route works; the model bytes
aren't local. This was deliberately NOT pulled to avoid network/box contention with the
benchmark currently running:

```bash
ollama pull nomic-embed-text        # ~270 MB, one-time; no sudo, no docker
```

`chromadb` is **not** required (the numpy store replaces it). If a persistent vector index
is wanted later, it is a no-sudo pip install but pulls heavier native deps and an approximate
HNSW index — skip it for the deterministic lab run unless there's a reason:
```bash
# OPTIONAL, not recommended for the deterministic run:
/home/jerem/sdw-lab-benchmarks/.venv/bin/python3 -m pip install chromadb
```

No sudo, no docker, no system packages anywhere in the path.

---

## 4. Implementation plan

One new file, `ocsf-semantic-query/run_graphrag.py`, mirroring `run_obda.py`'s
merge-into-results pattern. Plus a small shared scorer so the extra kinds (count / scalar /
order / set) are defined once and reused identically by any arm that runs them.

Functions in `run_graphrag.py`:

- `connect()` — `configure_duckdb(duckdb.connect(":memory:"))` + 7 views over Store F
  parquet (copy from `run.py:connect()`; do not duplicate the schema_context helper).
- `build_graph(con) -> nx.MultiDiGraph` — stream the 7 tables, add entity + event nodes and
  the edges in §2a, with stable ids and sorted insertion. Build twice + assert the
  node/edge-multiset hash matches before proceeding (the testbed's two-build discipline).
- `graph_fingerprint(g) -> str` — sha256 over the sorted (node, attrs) and (u,v,key,attrs)
  multiset, for the `--determinism` assertion and a cache key.
- `embed(texts, model) -> np.ndarray` — batch POST to `/api/embeddings`; cache to
  `_work/embeddings.npy` + `_work/embed_ids.json`.
- `node_documents(g) -> list[(id, text)]` — serialize each node to its embedding text.
- `vector_topk(qvec, matrix, ids, k) -> list[id]` — deterministic numpy cosine top-k.
- `retrieve(g, qvec, matrix, ids, k=20, hops=2) -> subgraph` — vector seeds → ego-graph +
  sameAs closure.
- `serialize_subgraph(subgraph, budget) -> str` — deterministic, cosine-ordered context.
- `ask(model, question, context) -> answer` — Ollama `/api/generate`, temp 0, JSON.
- `score(q, answer, truth)` — import the SHARED scorer (the extended kind-dispatch).
- `main()` — args `--model` (default `gemma4:26b`), `--embed-model` (default
  `nomic-embed-text`), `--render-only`, `--determinism`; loop A1–A9; build the
  `arms["graphrag"]` block (status `measured`, engine string, per_query, counts,
  `silent_error_rate`, `result_accuracy`, the greedy-decode caveat); **merge** into
  `results/results.json` exactly as `run_obda.py:128-132` does; write a `_graphrag_section()`
  into RESULTS.md.

Shared scorer: lift `run.py:score()`'s kind-dispatch into a tiny module (e.g.
`scoring.py` next to the runners) and have all three arms import it, OR — to avoid touching
`run.py` in a readiness pass — define the extended scorer in `run_graphrag.py` and document
that `run.py`/`run_obda.py` should be refactored to import it when the arm lands, so there is
exactly one definition of correct/silent/loud. (Recommended: the small shared module; it is
the only way to *guarantee* identical scoring across arms rather than hoping three copies stay
in sync.)

Registration: GraphRAG is `arms["graphrag"]` in the same `results/results.json`, merged
non-destructively, so the three arms accumulate and `render_md()` can show all three.

---

## 5. Run plan

- **Models**: generator `gemma4:26b` (primary) then `phi3:latest` (small-model leg);
  embed `nomic-embed-text`. Temperature 0 throughout.
- **Scale**: full Store F (~177k events). The graph is built once; embeddings computed once
  and cached. 9 questions × 2 generator models = 18 generations per full pass.
- **Outputs**: merge `arms["graphrag"]` into `results/results.json`; append the GraphRAG
  section to `results/RESULTS.md`; cache `_work/graph.pkl`, `_work/embeddings.npy`,
  `_work/embed_ids.json`.
- **Rough runtime** (single box, nothing else contending): graph build seconds-to-low-minutes
  (DuckDB scan + in-memory networkx); embedding ~tens of thousands of node-documents with
  `nomic-embed-text` is the longest one-time step (order minutes, cached after); 18 LLM
  generations at temp 0 dominated by `gemma4:26b` latency (order a few minutes total). Whole
  arm is well under the box's patience; the binding constraint is just "don't run it while the
  other benchmark holds the box."

---

## 6. Fairness considerations (GraphRAG vs OBDA vs text-to-SQL)

What keeps the three-way comparison honest:

- **Same question set**: all arms answer the same A-questions over the same Store F, scored
  against the same `truth_needles`. The GraphRAG arm runs the full A1–A9 union and reports
  per-query, so it slices cleanly against text-to-SQL's {A1,A2,A6,A8} and OBDA's 8-query set
  without a separate run.
- **Same scorer**: the single correct/silent/loud definition (shared module), with the same
  substring/uid/uidset/count/scalar/order/set kind-dispatch. A wrong-but-confident GraphRAG
  answer must land as **silent**, not loud — that is the metric BENCH-C is built around, and
  miscategorizing it would flatter the arm.
- **Same local-model tier**: the generator ladder is the same local Ollama models the
  text-to-SQL arm uses (`gemma4:26b`, `phi3`), so GraphRAG vs text-to-SQL isolates the effect
  of graph+vector retrieval, not a stronger model.
- **Same determinism discipline**: seed/temperature-0/pinned models, with the greedy-decode
  caveat stated identically to the text-to-SQL arm.

What would make it **apples-to-oranges** (and must be avoided / disclosed):

- Giving GraphRAG a frontier or larger model than the other LLM arms got — then it is the
  model winning, not the retrieval. (If a frontier leg is ever added, add it symmetrically to
  text-to-SQL too, as the RESULTS.md "next steps" already flags.)
- Hand-tuning the graph schema or retrieval k/hops *after* seeing which needles it misses —
  that is fitting the arm to the planted answers, the same degree-of-freedom the testbed
  pre-registration forbids for the corpus. Fix k=20, hops=2, the entity/edge schema, and the
  prompt **before** the scored run and record them here.
- Scoring a GraphRAG near-miss as loud (refusal) when it actually produced a confident wrong
  answer — that would hide silent errors and is the single most important thing to get right.
- Embedding or generating with a model whose digest isn't pinned, so a background Ollama
  model update silently changes the answers between runs.

The structural caveat both other arms carry applies here too: one synthetic APT29-style
chain, single machine, Tier B. GraphRAG's coverage advantage (it can attempt the
aggregation/recursion queries OBDA refuses) is real but unverified, so the result is a
silent-error rate to compare, not a correctness proof.

---

## 7. Open risks / blockers

- **Embed model not pulled** (the only hard gap) — one `ollama pull nomic-embed-text` when
  the box frees. Route verified; ~270 MB; no sudo. Not a design blocker.
- **Greedy-decode reproducibility** is practical, not asserted (shared with text-to-SQL).
  Mitigated by caching the graph + embeddings (the deterministic parts) and pinning model
  digests; the LLM decode caveat is stated, not hidden.
- **Subgraph token budget vs. context window**: the beacon query (A1) touches 60 conn edges;
  the serialized subgraph must fit `gemma4:26b`'s context. Mitigation: cap the context at a
  fixed, cosine-ordered budget and let the uidset scorer's recall-floor (≥50%) absorb a
  partial set; record the budget so it's not tuned post-hoc.
- **Embedding-retrieval misses on rare needles**: the needles are sparse and may not surface
  in vector top-k from a generic NL question; the graph-expansion (ego + sameAs) is the
  safety net, but if retrieval misses, the arm fails **loud** (empty/refusal), which is the
  honest outcome, not a bug to paper over.
- **No frontier leg**: as with text-to-SQL, a local model may fail loudly rather than
  silently, so the silent-vs-loud contrast may need a frontier generator to fully bite — that
  is a documented next step, not a blocker for the local-tier run.
- **Shared-scorer refactor**: if `run.py`/`run_obda.py` keep private scorers, the three could
  drift; the recommended shared module removes that risk and is the only change that touches
  the existing runners (a future, non-readiness step).

None of these blocks the run except the embed-model pull, which is a single deferred command.

---

## 8. TO RUN WHEN BOX IS FREE

```bash
# 0. one-time: pull the embedding model (deferred from the readiness pass; ~270 MB, no sudo)
ollama pull nomic-embed-text

# 1. (sanity) confirm light deps + Store F + ground truth are present
/home/jerem/sdw-lab-benchmarks/.venv/bin/python3 -c "import networkx, numpy, duckdb, requests; print('deps ok')"
ls /home/jerem/sdw-lab-benchmarks/bench-a-context-collapse/_work/store_f/*.parquet
ls /home/jerem/sdw-lab-benchmarks/ocsf-semantic-testbed/_work/ground_truth.json

# 2. determinism check (graph fingerprint + scorer stability; prints the greedy-decode caveat)
/home/jerem/sdw-lab-benchmarks/.venv/bin/python3 ocsf-semantic-query/run_graphrag.py --determinism

# 3. run the GraphRAG arm — primary generator, then the small-model leg
/home/jerem/sdw-lab-benchmarks/.venv/bin/python3 ocsf-semantic-query/run_graphrag.py --model gemma4:26b --embed-model nomic-embed-text
/home/jerem/sdw-lab-benchmarks/.venv/bin/python3 ocsf-semantic-query/run_graphrag.py --model phi3:latest  --embed-model nomic-embed-text

# 4. re-render the combined three-arm results
/home/jerem/sdw-lab-benchmarks/.venv/bin/python3 ocsf-semantic-query/run.py --render-only
```

(`run_graphrag.py` is implemented as the §4 plan describes — that file is the one piece of
code to write before step 2; everything it depends on is verified ready above.)

---
type: benchmark-preregistration
title: "T8c trifecta detection: CS0066/CS0067-shaped chains over an OCSF ai_operation store, single-step vs session vs session+delegation rules"
created: 2026-11-09
status: frozen-by-agent-before-run (not owner-reviewed)
review_ref: project1/02-projects/securitydataworks/content/drafts-2026-11/09-detecting-the-trifecta-over-your-telemetry.md section 7 and "What's missing"
---

# Pre-registration: T8c trifecta-detection

Written before any corpus row, rule or query existed in this directory. Orientation done before writing it, listed
so a reader can see what I knew: I read the lab methodology, R1 (`atlas-ocsf-observables`), R2
(`agent-toolcall-schemas`) and R7 (`delegation-chain-query`) results, the ATLAS v2026.10 YAML and
`employs_edges.csv` rows for AML.CS0066 and AML.CS0067, the ATT&CK T1698 and T1700 pages as served on
2026-11-09 (T1698 v1.0, modified 2026-11-03, detection strategy DET0942 / analytic AN2293; T1700 v1.0, modified
2026-11-03, DET0927 with AN2078, AN2079, AN2080; neither lists data sources or data components), the OCSF 1.9.0
`api_activity` class and the `message_context`, `delegation`, `ai_agent`, `api`, `request`, `response`, `url`
objects from the schema JSON R1 fetched. I also confirmed that pySigma-backend-sqlite 2.1.1 compiles `temporal` and
`temporal_ordered` correlation rules (it emits SQLite-dialect SQL using `julianday` and `json_each`). I computed no
precision, no match set and no timing before freezing this file.

## Question

When an indirect-injection-to-exfiltration chain shaped like ATLAS AML.CS0066 (ZombieAgent) or AML.CS0067 (Claude
Code GitHub Action) is planted into OCSF 1.9.0 `api_activity` events carrying the `ai_operation` profile, among
benign agent sessions, what fires, what is noise and what is dark for three tiers of rule: (a) one rule per
trifecta leg, (b) one rule per agent session that holds all three legs, and (c) the session rule after walking
delegation to the root session, on DuckDB and on SQLite?

The draft essay's design rule is the thing under test: if no single session should hold untrusted content, a
sensitive read and an outbound call, then a session that does is the alert. The question is whether that buys
precision over single-step rules at this scale, and what it costs when the legs are split across a delegated
sub-agent.

## Scope and what is out

- ATT&CK v20 T1698 Indirect Prompt Injection and T1700 AI-Enabled Exfiltration are the frame; the planted chains
  realise the ATLAS steps the draft maps to them (AML.T0051.001 for T1698, AML.T0086 for T1700), plus the
  collection and defense-evasion steps between them (T0053, T0085.001, T0085.002, T0098, T0054, T0080.000, T0143).
- No prompt-injection classification. No rule reads the ingested text to decide whether it is an instruction. The
  ingested content carries a labelled test-fixture marker for provenance only, and no rule matches on it.
- No real exploit content, no real credentials, no real hostnames. Attacker-side and off-allowlist hosts use
  reserved names (`.invalid`, `.example`, `.test`); the "credential" is a fixture string with a fixture prefix.
- Attacker-side steps (T0065, T0079, T0068, T0095.000, T0084.x) leave no victim record and are not planted.
- Single host, synthetic corpus, deterministic rules, no model in the loop (methodology §10 deterministic-arm
  exemption applies). Tier B for the mechanism, D for every judgment I made about what a benign session looks like.

## Instrument

### Store

One flattened table `api` (OCSF 1.9.0 `api_activity`, class_uid 6003, profile `ai_operation`), column names being
OCSF attribute paths with `.` replaced by `_`. Every column path is validated mechanically against the 1.9.0 class and
object JSON in `../atlas-ocsf-observables/sources/ocsf-1.9.0/` (read-only) before the corpus is written; a path that
does not resolve fails the run. Columns:

`metadata_uid` (event id), `time` (ISO text, for the pySigma correlation SQL), `time_epoch` (BIGINT), `class_uid`,
`category_uid`, `activity_id`, `activity_name`, `actor_user_name`, `actor_session_uid`, `actor_app_name`,
`ai_agent_uid`, `ai_agent_name`, `ai_agent_type_id`, `ai_model_name`, `api_service_name`, `api_operation` (the tool
name, as R1 did and as AOS example 2 does; 1.9.0 tagged has no `ai_capability` on this class), `api_request_data`
(JSON text), `api_response_data` (JSON text), `status_id`, `dst_endpoint_hostname`, `http_request_url_hostname`,
`http_request_url_path`, `message_context_uid`, `message_context_prompt_text` (populated only on ingest events),
`delegation_uid`, `delegation_parent_uid`, `delegation_issuer_uid`, and three truth columns the rules never read:
`is_planted`, `truth_chain`, `truth_leg`.

Written as SQLite (the pySigma backend's target) and loaded into DuckDB 1.5.3 in memory from the same file, as R1 did,
so both engines see identical rows.

### Background (benign agent sessions)

`N_SESSIONS = 2000` sessions per seed, three personas in fixed proportion: inbox triage 40% (`mail.fetch`,
`mail.search`, `contacts.list`, `calendar.read`, `mail.send`, `web.fetch`), coding 35% (`file.read`, `file.write`,
`bash.exec`, `git.diff`, `web.fetch`), CI review 25% (`issue.read`, `pr.read`, `file.read`, `bash.exec`,
`github.comment`, `web.fetch`). Each session is 3 to 12 tool calls inside a window of at most 60 minutes, one
agent, one user, one session uid, no delegation unless listed below.

Outbound allowlist, fixed here and never fitted afterwards: `docs.python.org`, `github.com`, `api.github.com`,
`pypi.org`, `intranet.example`, `wiki.example`, `calendar.example`, `mail.example`, `registry.example`.

Pre-committed lookalikes, as a share of benign sessions (rates are corpus parameters, chosen by me from
operational experience, not measured field rates):

| Lookalike | Legs held | Rate | Why it exists |
|---|---|---|---|
| LA1 ingest + sensitive read | 1 + 2 | 4% | inbox triage that fetches mail then searches it or lists contacts; CI review that reads an issue then reads `.env` to debug |
| LA2 ingest + off-allowlist outbound | 1 + 3 | 4% | user asks the agent to read an issue or mail and open a link in it to an arbitrary external site |
| LA3 sensitive read + off-allowlist outbound | 2 + 3 | 3% | coding session reads `.env` or `credentials.json` then fetches a package from an unlisted mirror |
| LA4 benign burst | 3 (shape) | 2% | docs crawl: 20 to 40 `web.fetch` to one allowlisted host within 5 minutes |
| LA5 all three legs, benign | 1 + 2 + 3 | 0.5% | CI review reads an issue, reads `.env` while debugging, fetches an off-allowlist link; the honest cost of kind-based session rules |
| LA6 `.env`-style reads in coding sessions generally | 2 | 3% of coding sessions | background rate of sensitive-path reads |
| LA7 benign delegation | — | 3% | a root session delegates a sub-task to a sub-agent (depth 1); no attack legs |

### Plants (per seed)

Twenty chains, four strata of five, each in its own session with its own user and agent:

- **CS0066-direct** (5): `mail.fetch` (leg 1, T0093→T0051.001; `message_context_prompt_text` carries the fixture
  marker), `memory.write` (T0080.000), `mail.search` and `contacts.list` (leg 2, T0085.001), then `http.open`
  × 24 to one `.invalid` host with paths `/c/<index>/<position>` within 3 minutes (leg 3, T0054 + T0086), then
  `mail.send` × 3 (T0143).
- **CS0066-delegated** (5): the root session does `mail.fetch` and `memory.write`, then `agent.delegate`; a
  sub-agent session with `delegation_parent_uid` = root does legs 2 and 3 and the sends. Three of the five are
  depth 1; two are depth 2 (a second delegation before the outbound calls).
- **CS0067-direct** (5): `issue.read` or `pr.read` (leg 1), `file.read` with path `/proc/self/environ` (leg 2,
  T0053 + T0098), `web.fetch` to one off-allowlist `.invalid` host whose query string carries the fixture credential
  with its prefix removed (`api03-` followed by 40 fixture characters; the real prefix `sk-ant-` is not present;
  leg 3, T0085.002 + T0086), and one `bash.exec` whose argument echoes the same string (the Action-log channel).
- **CS0067-delegated** (5): the root session does the ingest then `agent.delegate`; the sub-agent does legs 2 and
  3. Three depth 1, two depth 2.

Truth: leg events carry `truth_leg` in {1, 2, 3}; chain root sessions carry `truth_chain`. Non-leg plant events
(`memory.write`, `mail.send`, `agent.delegate`, `bash.exec`) are planted but are not truth for any rule here.

### Rules (named now, written after the freeze)

Discipline from R1: each single-step rule is the signal plus at most one filter the technique definition names, no
allowlist fitted to the background (the allowlist above is fixed before any row exists). All Sigma rules compile
through pySigma 2.0.3 + pySigma-backend-sqlite 2.1.1 and run on both engines; correlation SQL from the backend is
SQLite-dialect and runs there only, with a hand-written SQL twin for both engines.

Tier (a), single-step, one Sigma rule each, event-level:
- `a1_ingest_mail`: `api_operation = mail.fetch` (leg 1, CS0066).
- `a2_ingest_repo`: `api_operation in (issue.read, pr.read)` (leg 1, CS0067).
- `a3_collect_mailbox`: `api_operation in (mail.search, contacts.list)` (leg 2, CS0066).
- `a4_read_procenv`: `api_operation = file.read` and `api_request_data|contains /proc/self/environ` (leg 2, CS0067;
  content match).
- `a5_outbound_offlist`: `api_operation in (http.open, web.fetch)` and `dst_endpoint_hostname` not in the allowlist
  (leg 3, both; T1700 AN2079's "unauthorized destination").
- `a6_credential_shape`: `api_operation in (web.fetch, bash.exec)` and `api_request_data|contains api03-` (leg 3,
  CS0067; content match).
- `a7_url_burst` (Sigma `event_count` correlation, SQLite only): 20 or more `http.open` or `web.fetch` from one
  session to one host in 5 minutes (leg 3, CS0066 shape).

Tier (b), session-level, unit = session:
- `b1_session_temporal` (pySigma `temporal`, SQLite only): legs 1, 2, 3 (any of the leg rules above except a7)
  in one `actor_session_uid` within 60 minutes.
- `b2_session_temporal_ordered` (pySigma `temporal_ordered`, SQLite only): same, in order 1 → 2 → 3.
- `b3_session_sql`: hand SQL twin of b1 on both engines.
- `b4_session_sql_qualified`: b3 with leg 3 qualified by content (a6's string or a7's burst), both engines.

Tier (c), session after delegation walk, unit = root session:
- `c1_walk_sql`: b3 after mapping every session to its root with a recursive CTE over `delegation_parent_uid`.
- `c2_walk_sql_qualified`: b4 after the same walk.

### Scoring

House states at precision floor T = 0.9: DETECTED (truth matched, precision ≥ 0.9), NOISY (truth matched,
precision < 0.9), MISSED (no truth matched, or the rule cannot execute). Tier (a) is scored on events against the
leg's planted events across all four strata (event rules do not care about delegation). Tiers (b) and (c) are
scored on sessions against the 20 chain root sessions; a sub-agent session matched on its own counts as a false
positive for the non-walk rules, because it is not the root, and recall is reported per stratum (direct vs
delegated, CS0066 vs CS0067) before any pooled figure. False positives per seed and the share of each lookalike
class that fired are reported for every rule.

### Metrics

Per rule, per engine, per seed: state, matches, true positives, false positives, precision, recall, and which
lookalike classes the false positives came from. Precision and recall as min/median/max over seeds. Per-stratum
recall for tiers (b) and (c). Engine answer equality: the matched event set on DuckDB vs SQLite for every tier (a)
rule and seed. Wall time per rule per engine (monotonic `perf_counter`, median of 3, under contention, rig stamp
required). A scale check at `N_SESSIONS = 20000` on seed 20261109 for the SQL rules only, reporting whether the
states hold.

## Hypotheses and what would prove each wrong

- **H1 (kind vs content, single step).** The four kind-matching single-step rules (a1, a2, a3, a5) are NOISY on all
  three seeds on both engines, and the two content-matching rules (a4, a6) are DETECTED on all three seeds. Wrong
  if any kind rule reaches DETECTED on two or more seeds, or if a4 or a6 is NOISY or MISSED on any seed.
- **H2 (sequence buys precision, not a clean detection).** The session rule b3 has precision in [0.6, 0.9) on every
  seed, because LA5 fires it, so its state is NOISY, and its median precision exceeds the best kind-matching
  single-step rule's by at least 0.3 absolute. Wrong if b3 is DETECTED (would mean LA5 did not fire, a corpus bug) or
  MISSED, or if its precision gain over the best of a1, a2, a3, a5 is under 0.3.
- **H3 (content-qualified session rule).** b4 is DETECTED on direct plants with 0 false positives on all seeds in
  both engines. Wrong if any benign or lookalike session matches b4, or if any direct plant is missed.
- **H4 (delegation splits the legs).** b1, b2, b3 and b4 have recall 0 on the ten delegated chains on every seed,
  and c1 and c2 have recall 1.0 on all twenty with the same precision class as b3 and b4 respectively. Wrong if a
  non-walk rule catches any delegated chain (my plant did not split the legs), or if a walk rule misses one.
- **H5 (engines).** Every tier (a) Sigma rule returns the identical matched set on DuckDB and SQLite on every seed,
  because every value matched is a fixed-case tool name, path or fixture string; and the pySigma correlation SQL
  (a7, b1, b2) fails to execute on DuckDB. Wrong if any tier (a) set differs, or if any correlation SQL runs on
  DuckDB.
- **H6 (ordering).** b2 (ordered) has the same recall as b1 on direct plants and strictly fewer false positives on
  at least one seed, since LA5's leg order is fixed to 1 → 2 → 3 and LA3 can be 3 → 2. Wrong if b2's false
  positives equal b1's on every seed.

Predicted confidence delta: the draft essay's section 7 claim ("the trifecta is easier to detect as a sequence of
legs inside one session than as any single step") moves from D to B-direction, magnitude still corpus-bound, if H2
and H3 hold; no hypothesis in the hub tracker moves on this bench alone. If H2 fails on the precision-gain clause,
the essay drops the sequence claim.

## Variance

Corpus generation and rules are deterministic given the seed. Three seeds: 20261109, 20261110, 20261111. Two
identical runs must produce the same sha256 of `results/coverage.json` (sort_keys). Timings vary and are reported as
medians with min/max under contention.

## Environment and execution limits

Beelink (Ryzen 7 5800H), WSL2 6.6.87.2, 14 vCPU, 47 GB; chrony offset 0.00004 s at freeze (`chronyc tracking`).
Python 3.12.3; duckdb 1.5.3, pySigma 2.0.3, pySigma-backend-sqlite 2.1.1, PyYAML 6.0.3 (`requirements.txt`, venv in
this directory). The run is pinned to 4 cores with `taskset -c 0-3` under `nice -n 10`, DuckDB `threads=4`; other
benches share the host, so timings are under contention and say so.

## Stop rule and cost

Zero spend: local CPU, no model calls, no containers, no network beyond the PyPI install. Stop and report short if
(a) a column path fails schema validation (fix the path, record it as a deviation, re-freeze), (b) a rule fails to
compile for a reason other than a backend limitation, (c) the 20,000-session scale check exceeds 20 minutes per
rule (report the smaller scale only), or (d) two identical runs differ in `coverage.json`.

## Known biases, declared in advance

- I wrote the personas, the lookalike rates and the plants, and I will write the rules. The precisions are
  illustrative of the mechanism and not field false-positive rates; LA5's rate in particular sets b3's precision
  almost directly, and I chose it.
- Attacker hosts are `.invalid` names, which a hostname rule could trivially match; no rule matches on hostname
  identity, only on allowlist membership, and the allowlist was fixed here.
- The session uid is clean and present on every event. R2 found that real producers may put it in
  `actor.session.uid` or `message_context.uid` or nowhere, so this corpus is kinder than shipping telemetry.
- The delegation object exists in 1.9.0 but R2 and R7 found no shipping producer populates it; tier (c) measures
  what the walk would buy if it were populated.

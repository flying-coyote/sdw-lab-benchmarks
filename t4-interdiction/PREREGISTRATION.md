---
type: benchmark-preregistration
title: "T4 interdiction: of the incident steps a burn-down control is mapped to, how many does a concrete implementation catch"
created: 2026-11-10
status: frozen-by-agent-before-run (not owner-reviewed)
inputs:
  - project1/02-projects/atlas-mitigations/results/control_burndown_2026.10.json
  - project1/02-projects/atlas-mitigations/DESIGN-control-burndown-2026-11-09.md
  - project1/02-projects/atlas-mitigations/cache/ATLAS-2026.10.yaml (sha256 ac41ee9f…e142d)
  - sdw-lab-benchmarks/atlas-ocsf-observables (R1: corpus and planted-run pattern, OCSF 1.9.0 schema dump)
---

# Pre-registration: T4-interdiction

Written before any fixture row, rule or check was built or run. What ran before this freeze, so the
reader can see what I knew: `extract_mappings.py` (mitigation text, mitigates edges and the 290 Incident
employs-steps per top-12 control; output `results/mappings_top12.json`), `select_steps.py` (the step
selection rule below applied mechanically; output `results/selected_steps.json`), and `ocsf_fields.py`
(every flattened column the fixtures will use, validated against the OCSF 1.9.0 class and object dump that
R1 fetched; one column renamed `app_url` to `app_url_string` because `application_lifecycle.app` is a
`product`, not an `application`). The venv was created and `requirements.txt` frozen. No corpus, rule, SQL
or score existed at freeze time.

## Question

The burn-down (`control_burndown_2026.10.json`) ranks ATLAS v2026.10 mitigations by how many of the 290
Incident steps they are *mapped* to. Its own design note says that is relevance, not interdiction. So:
for the top controls with a defined telemetry or enforcement artifact, implemented concretely the way the
mitigation text describes, how many of the Incident steps each control is mapped to does the
implementation catch, how many does it catch only by also blocking or alerting on legitimate background,
and how many does it miss, and of the misses, how many miss because the step leaves no artifact on the
control holder's ground at all.

## Control selection (by rule)

Walk `atlas_layer.greedy` from the top and keep a control only if its mitigation text names a telemetry
or enforcement artifact that a deterministic check can key on. Stop when 8 are kept. The top 12 yield 8:

| Greedy rank | Control | Kept? | Reason |
|---|---|---|---|
| 1 | AML.M0042 Threat Intelligence Program | no | a program and a team; no telemetry or enforcement artifact of its own |
| 2 | AML.M0019 Control Access to AI Models and Data in Production | **yes** | "require authentication for API endpoints and monitor production model queries" |
| 3 | AML.M0043 AI Agent External Resource Lifecycle Management | **yes** | "agents should create such resources through a broker or management layer"; attributable assets |
| 4 | AML.M0005 Control Access to AI Models and Data at Rest | **yes** | "access controls on internal model registries"; "training data only to approved users" |
| 5 | AML.M0011 Restrict Library Loading | **yes** | "configuring appropriate library loading mechanisms"; pickle note |
| 6 | AML.M0001 Limit Model Artifact Release | no | a publication policy; nothing to observe on the defender's systems |
| 7 | AML.M0020 Generative AI Guardrails | **yes** | "rule-based controls such as filters, allowlists, blocklists, regular expressions" on prompts, context, outputs, agent actions |
| 8 | AML.M0034 Deepfake Detection | no | the artifact is a classifier verdict; a deterministic fixture would be simulating the detector's output, which tests nothing |
| 9 | AML.M0000 Limit Public Release of Information | no | publication policy |
| 10 | AML.M0024 AI Telemetry Logging and Monitoring | **yes** | "distinguish requested actions from those actually executed, using independent service records"; "coordinated behavior across accounts and access pathways" |
| 11 | AML.M0040 Adaptive AI Response Degradation | **yes** | "when suspected extraction activity … [is] detected"; the detection half is testable |
| 12 | AML.M0013 Code Signing | **yes** | "digital signature verification to prevent untrusted code from executing"; signed SBOM/AIBOM components |

Four of the top twelve drop out, and three of those four are the Policy-only entries that carry the
most marginal steps in the burn-down. That is itself part of the answer and is reported as such.

## Step selection (two sets, reported separately)

**Rule set.** For each kept control, rank its mapped techniques (a sub-technique credits its parent, as
the burn-down does) by the number of Incident steps whose technique tactic is on defender ground, meaning
not Reconnaissance (TA0002), Resource Development (TA0003) or AI Attack Adaptation (TA0001), R1's
`OFF_GROUND` set. Take the top three (ties by total steps, then id). For each, take the most recent
Incident step (highest case-study id, then highest employs index). `select_steps.py` applies this; the
result is 22 step-slots over 18 distinct steps, because CS0076[2], CS0076[4] and CS0076[7] recur under
several controls. The rule is chosen for recency, not for what I expect the check to see, and it lands
heavily on the two 2026 distillation case studies.

**Mechanism set (declared bias).** One or two further steps per control, hand-picked because the step's
description names an action on the control's own artifact, so the check has something to look at. These
are picked *because* I expect the check can see them (or can be shown blind to them for a stated reason),
and the two sets are never pooled.

| Control | Set | Step | Technique | What the step says | Control holder, ground | Expected |
|---|---|---|---|---|---|---|
| M0019 | rule | CS0076[2] | T0012 | established accounts and premium-subscription pools used to access AI services | AI service provider; provider ground, API telemetry exists | MISSED (valid credentials pass E1; per-identity volume under ceiling) |
| M0019 | rule | CS0076[7] | T0051.000 | adversarial prompts submitted directly to override behavior | provider | MISSED (M0019 has no content check) |
| M0019 | rule | CS0076[4] | T0024 | queried U.S. AI services via proxy infrastructure, collected responses | provider | MISSED (distributed over accounts) |
| M0043 | rule | CS0076[2] | T0012 | as above | agent operator; **no agent in this step**, so no agent-created resource | MISSED-by-construction |
| M0043 | rule | CS0074[22] | T0072 | payloads configured to use GitHub for tasking and beacon submission | agent operator (the evaluator); harness tool log | CAUGHT (agent creates repos/gists with no broker delegation) |
| M0043 | rule | CS0068[23] | T0091.000 | agents minted short-lived identity tokens from stolen signing material; used an internal GitHub App | agent operator; harness tool log | MISSED (the creation is inside a code-execution tool call; the broker sees "exec", not "create token") |
| M0005 | rule | CS0076[2] | T0012 | as above | data owner; **API access, no at-rest event** | MISSED-by-construction |
| M0005 | rule | CS0074[10] | T0025 | enumeration results returned through callback infrastructure | data owner; **no model or training store touched** | MISSED-by-construction |
| M0005 | rule | CS0076[6] | T0048.004 | agencies assessed that the campaigns appropriated proprietary capabilities | data owner; **an outcome, no event** | MISSED-by-construction |
| M0005 | mech | CS0068[0] | T0012 | exposed HF tokens used to authenticate and request access to gated datasets | data owner; datastore telemetry | CAUGHT (request on a gated bucket by a non-approved principal) |
| M0005 | mech | CS0023[3] | T0035 | adversary on an exposed Ray cluster collects production models and data | data owner; file telemetry | MISSED (the read is by the cluster's own approved service identity) |
| M0011 | rule | CS0074[13] | T0050 | malicious setup.py executed during Dependabot processing in 53 containers | platform operator; module-load telemetry in the build sandbox | NOISY (setup.py loads from a pip temp dir, and so does every legitimate build) |
| M0011 | rule | CS0074[2] | T0011 | investigator ran the issue payload in an isolated Docker container | host operator; module telemetry | MISSED (a script runs; every library it loads is allowlisted stdlib) |
| M0011 | rule | CS0074[24] | T0074 | contributions disguised as bug fixes and diagnostics | **content-level deception; no load event** | MISSED-by-construction |
| M0011 | mech | CS0031[1] | T0011.000 | a user loads the malicious pickle model and the payload runs | host operator; module telemetry | CAUGHT (deserialization imports `posix`/`subprocess`, outside the model-loading allowlist) |
| M0020 | rule | CS0076[7] | T0051.000 | adversarial prompts to override intended behavior | provider; prompt text | split by phrasing: see H5; CAUGHT on SQLite if ≥ half carry blocklist phrases, lower on DuckDB |
| M0020 | rule | CS0076[8] | T0054 | prompts eliciting hidden chain-of-thought ("imagine and articulate the reasoning") | provider; prompt text | MISSED (no blocklisted phrase) |
| M0020 | rule | CS0074[20] | T0068 | instructions hidden in HTML comments in GitHub issues | agent operator; retrieved-context text | NOISY (issue templates carry imperative HTML comments too) |
| M0020 | mech | CS0047[2] | T0051.000 | Amazon Q deployed with a prompt instructing destructive filesystem and cloud actions | agent operator; tool-request text | CAUGHT (action filter on destructive tool requests) |
| M0024 | rule | CS0034[3] | T0047 | deepfake video presented to facial recognition and liveness checks | app operator; verification API telemetry | MISSED (logged, but none of the M0024 checks inspects media) |
| M0024 | rule | CS0076[7] | T0051.000 | as above | provider | CAUGHT or NOISY via the cross-account check on the shared proxy pathway, not via the prompt |
| M0024 | rule | CS0076[4] | T0024 | as above | provider | NOISY (shared proxy IPs look like corporate NAT egress) |
| M0024 | mech | CS0053[5] | T0086 | emails sent via the poisoned `postmark-mcp` tool gained a BCC to the attacker | agent operator; tool request plus independent mail-provider record | CAUGHT (requested vs executed differ) |
| M0024 | mech | CS0047[5] | T0101 | the Q agent invoked filesystem and bash tools to delete resources | agent operator; executed-action log | CAUGHT or NOISY (legitimate cleanup deletes in background) |
| M0040 | rule | CS0076[11] | T0135 | millions of responses collected, concentrated on selected domains | provider | MISSED (per-identity volume under ceiling) |
| M0040 | mech | CS0075[7] | T0135 | over 100,000 prompts in one campaign through many fraudulent accounts | provider | MISSED (same shape) |
| M0013 | rule | CS0073[1] | T0010.001 | the agent published the package; fifteen systems downloaded and ran it | consumer; package-install telemetry | NOISY (no attestation, but many legitimate packages have none) |
| M0013 | rule | CS0069[13] | T0103 | GTG-1002 configured its Claude agent inside an attack framework | **attacker infrastructure** | MISSED-by-construction |
| M0013 | rule | CS0023[1] | T0010.003 | HF tokens could let the adversary replace the victim's models | consumer; model-file load telemetry | NOISY (the replaced model is unsigned, and so is every legitimate one) |
| M0013 | mech | CS0047[1] | T0011.001 | users who upgraded to v1.84.0 of the extension executed the malicious package | consumer; install telemetry with signature | MISSED (the release is validly signed by the real publisher) |

Case-study text is quoted from ATLAS v2026.10 and paraphrased; the fixtures model the mechanism of each
step, not its real volumes or identities.

## Instrument

One synthetic corpus per seed, built by `gen_corpus.py` (to be written after this freeze) as flattened
OCSF 1.9.0 tables with the ai_operation profile applied, columns as attribute paths with `.` → `_`, list
attributes flattened at element 0, `time` as integer epoch milliseconds so windowed SQL is portable.
Tables and the classes they stand for: `authentication` (3002), `api_activity` (6003; LLM calls and agent
tool calls alike, distinguished by `metadata_product_name` and `ai_agent_name`), `account_change` (3001),
`process_activity` (1007), `module_activity` (1005), `file_activity` (1001), `datastore_activity` (6005),
`network_activity` (4001), `email_activity` (4009), `application_lifecycle` (6002). Every column is
validated by `ocsf_fields.py` before a row is written; an unvalidated column fails the build. Tool
invocation has no class of its own in 1.9.0 (R1 found no tool object), so it is carried on `api_activity`
with `api_operation` as the tool name and `api_request_data` as the argument string; that is a proxy and
is labelled as one.

Background: 2,000 benign rows per table from fixed templates, with the lookalike for each check at 1 to 5%
(listed per check below). Planted content: strings in event fields only, never executable bytes, no real
pickle, package or exploit; every planted row carries `is_planted = 1` and a `truth` label of the form
`<control>|<cs>[<idx>]`, stripped from the stored tables and kept in `truth.json`. Seeds 20261109,
20261110, 20261111.

Checks are written after this freeze under R1's self-rule: each expresses the artifact signal the
mitigation sentence names plus at most one discriminating filter that the mitigation text itself names,
and no allowlist derived from the background. Single-event checks are Sigma rules compiled with pySigma
2.0.3 and pySigma-backend-sqlite 2.1.1; aggregate and join checks are hand-written SQL restricted to
constructs both engines share (GROUP BY, HAVING, COUNT DISTINCT, integer arithmetic on `time`). Every
check runs on both engines: the stdlib `sqlite3` (SQLite 3.45.1) and DuckDB 1.5.3 (`SET threads=4`),
over identical tables.

| Check | Control | Mitigation sentence implemented | Kind | Keys on | Unit | Lookalike pre-committed in background |
|---|---|---|---|---|---|---|
| E1 | M0019 | require authentication for API endpoints | enforcement | `api_activity.actor_user_name IS NULL` on production model services | event | health probes with no principal (1%) |
| D1 | M0019 | monitor production model queries for compliance with usage policies | detection | per `actor_user_name`, model calls in any 1 h window > 500 | identity | one batch-classification service account at ~300/h |
| E2 | M0043 | agents create external resources through a broker or management layer | enforcement | `api_activity` or `account_change` creation operation with `ai_agent_name` set and `delegation_uid IS NULL` | event | agent creations that went through the broker (`delegation_uid` set); human creations |
| E3 | M0005 | access controls on model registries; training data only to approved users | enforcement | `file_activity` under `/models/` or `/data/train/`, and `datastore_activity` on `databucket_name` starting `gated-` or `train-`, by `actor_user_name` not in a pre-registered approved list of 10 identities | event | approved identities reading the same paths (5%) |
| E4 | M0011 | configure library loading mechanisms | enforcement | `module_activity` loads whose `module_file_path` is outside the allowlisted roots (`/usr/lib`, `/usr/local/lib`, `/opt/venv/lib`, `C:\Windows\System32`, `C:\Program Files`) | event | pip builds loading `setup.py` from `/tmp/pip-build-*` (3%) |
| E4b | M0011 | pickle files can load malicious libraries | enforcement | `module_activity` where `actor_process_cmd_line` contains `torch.load` or `pickle.load` and `module_file_name` not in {torch, numpy, collections, typing, pickle, _pickle, codecs} | event | legitimate model loads importing the allowlisted modules |
| E5a | M0020 | filters, blocklists, regular expressions on prompts | enforcement | `message_context_prompt_text` contains one of a public injection phrase list (ignore previous instructions, ignore all previous, disregard your, you are now, developer mode, do anything now, reveal your system prompt) | event | prompts that quote or discuss injection text (1%) |
| E5b | M0020 | evaluate agent actions before they are executed | enforcement | tool requests whose `api_request_data` contains `rm -rf`, `terminate-instances`, `delete-bucket`, `s3 rb`, `DROP TABLE` | event | legitimate cleanup jobs deleting their own temp buckets (1%) |
| E5c | M0020 | evaluate retrieved context | enforcement | retrieved-context rows whose text contains `<!--` and an imperative (`ignore`, `run`, `execute`, `fetch`, `curl`, `please`) | event | issue templates with `<!-- Please describe … -->` (3%) |
| D6a | M0024 | distinguish requested actions from those actually executed, using independent service records | detection | join tool request (`metadata_product_name = 'agent-runtime'`) to provider record (`'mail-provider'`) on `message_trace_uid`; alert when the provider record has a `email_bcc` the request did not | message | none expected (any legitimate BCC is in the request too) |
| D6b | M0024 | capture security-relevant operations; log executed actions | detection | executed tool actions (`metadata_product_name = 'agent-runtime'`, `status_id = 1`) whose `api_operation` is `fs.delete` or `bash.execute` with a destructive `api_request_data` | event | agent cleanup of its own scratch dir (2%) |
| D6c | M0024 | identify coordinated behavior across accounts and access pathways | detection | ≥ 10 distinct `actor_user_name` from one `src_endpoint_ip` in any 1 h window on model calls | source IP | two corporate NAT egress IPs each carrying 15 users |
| D7 | M0040 | detect suspected extraction activity | detection | per `actor_user_name`, model calls in 1 h > 500 or `message_context_total_tokens` sum in 1 h > 200,000 | identity | the batch service account above |
| E8a | M0013 | digital signature verification to prevent untrusted code from executing | enforcement | `process_activity` launches and `module_activity` loads with `*_file_signature_state_id <> 1` | event | unsigned internal scripts (2%) |
| E8b | M0013 | sign SBOM/AIBOM components; verify at install | enforcement | `application_lifecycle` install where `attestation_list_authority_uid IS NULL` or not the publisher pinned for that package name (pinned: torch→pytorch, numpy→numpy, requests→psf) | event | legitimate packages without attestations (30% of installs) |
| E8c | M0013 | verify model artifacts | enforcement | `file_activity` read of `*.bin`, `*.pkl`, `*.pt`, `*.safetensors` under `/models/` or `~/.cache/huggingface` with `file_signature_state_id <> 1` | event | every legitimate HF model load (unsigned) |

Which checks apply to which step is fixed above by control; a step is scored against every check its
control carries, and the step's state is the best state any of them reaches. Entity-level checks (D1, D6c,
D7) alert an identity or an IP; their alerts map to events by that key, so a step is matched when an
alerted entity owns at least one of its planted events, and precision is counted over alerted entities.
D6a alerts a message; its precision is over alerted messages.

## Metrics and states

For each (control, step, engine, seed): recall = share of the step's planted events matched (for entity
checks, share of planted events owned by an alerted entity); precision = TP / alerts, in the check's unit,
where an alert is TP if it contains or owns a planted event of *any* step of that control. States, with
T = 0.9 as in R1 and `ocsf-attack-coverage`:

- **CAUGHT**: recall ≥ 0.5 and precision ≥ T.
- **NOISY**: recall ≥ 0.5 and precision < T (the step is interdicted, but so is legitimate background;
  for an enforcement check this means legitimate traffic is blocked).
- **MISSED**: recall < 0.5, or the check cannot execute on that engine.
- **MISSED-by-construction**: declared above for steps that leave no event on the control holder's ground;
  no fixture is planted and no check runs. Reported as its own column, never folded into MISSED.

Recall uses 0.5 rather than "needle matched" because several steps plant many events (a burst of prompts
or installs); one hit in fifty is not interdiction.

Reported: the per-slot state table on both engines, per seed; the headline as CAUGHT / NOISY / MISSED /
by-construction counts for the rule set (22 slots) and the mechanism set (8 slots) separately; per-control
counts; the control-level summary that the burn-down's marginal-step column implies versus what fires.

## Hypotheses and what would prove each wrong

- **H1.** In the rule set, at most 7 of 22 slots are CAUGHT on the pre-registered engine (SQLite).
  Wrong if ≥ 8.
- **H2.** At least 5 of 22 rule slots are MISSED-by-construction. Wrong if ≤ 4. (The table above declares
  6: M0043/CS0076[2], M0005 ×3, M0011/CS0074[24], M0013/CS0069[13].)
- **H3.** The mechanism set's CAUGHT share exceeds the rule set's on every seed and engine, which would
  make the selection effect measurable. Wrong if on any seed the rule set's CAUGHT share is ≥ the
  mechanism set's.
- **H4.** Every per-identity volume check (D1, D7) is MISSED on every distillation step (CS0076[2],
  CS0076[4], CS0076[11], CS0075[7]) on all seeds, and the cross-account check D6c reaches recall ≥ 0.5 on
  CS0076[4]. Wrong if D1 or D7 fires on any of them, or D6c does not reach CS0076[4].
- **H5 (engine).** For every Sigma rule using `|contains` over planted text that includes mixed case
  (E5a, E5b, E5c; at least one third of each check's planted events will be mixed-case), DuckDB's recall is
  strictly lower than SQLite's; on rules whose planted content matches case, the two agree. Wrong if any
  such rule has equal recall on the two engines or the same-case rules disagree. A case-folded variant
  (`lower()` wrapped) runs as a labelled supplementary and is not a state.
- **H6.** E8b and E8c are NOISY on every seed (they block or alert on the legitimate unsigned
  background). Wrong if either is CAUGHT on any seed.
- **H7.** Three controls (M0019, M0040, M0005) catch none of their rule-set slots. Wrong if any of the
  three catches one.

## Variance

Scoring is deterministic given the corpus. Three identical runs must produce the same sha256 of
`results/interdiction.json` (`sort_keys=True`). Across the three seeds, per-slot states are reported per
seed and summarised as the modal state with the number of seeds agreeing; precision and recall as
min/median/max. `truth.json` is hashed per seed.

## Environment

Beelink (Ryzen 7 5800H), WSL2 6.6.87.2-microsoft-standard-WSL2, 14 vCPU, no GPU. Several benches run at
the same time, so this one is pinned to 4 cores (`taskset -c 0-3`, `nice -n 10`, DuckDB `threads=4`) and
any wall time recorded is under contention and from a monotonic timer; no absolute latency is claimed, so
no rig stamp applies. chrony: `chronyc tracking` read 0.586 s slow of NTP at 00:40Z during orientation and
0.000012 s fast at 00:58Z; the first reading is above the §7a threshold and is recorded here as a fact;
durations here come from monotonic timers so it does not affect them. Python 3.12.3; duckdb 1.5.3; SQLite
3.45.1 (stdlib); pySigma 2.0.3; pySigma-backend-sqlite 2.1.1; PyYAML 6.0.3 (`requirements.txt`, pip freeze).

## Stop rule and cost

Zero spend: local CPU only, no model calls, no containers (nothing needs one), no network beyond the pip
install already done. Stop and report short if (a) a fixture column fails `ocsf_fields.py` validation
(fix the column, record it as a deviation; do not re-hash this file), (b) a check cannot be written in SQL
both engines accept (record the check as MISSED "cannot execute" on that engine, which is itself a
result), or (c) `select_steps.py` re-run after the build gives a different step list.

## Known biases, declared in advance

- I wrote the mapping of mitigation sentence to check, the fixtures, the lookalikes and the rules, and the
  mechanism set was chosen with the expected result in mind. The rule set is the honest sample; the
  mechanism set shows what a check can do when the artifact is there.
- The volume ceilings (500 calls/h, 200k tokens/h, 10 accounts per IP) are round numbers I picked before
  seeing data; real policies differ, and the distillation steps are planted at volumes well under them
  because the case studies describe accounts "in bulk" and "pools", not single hot accounts.
- The background is synthetic; precision figures illustrate the mechanism, not field false-positive rates.
- Case-study descriptions are short; where a step's mechanism is underspecified (CS0034[3], CS0023[1]) the
  fixture follows the most literal reading and says so.
- Holder-of-control is my judgment per step; another reader might place M0043 with the victim rather than
  the agent operator, which would move CS0074[22] from CAUGHT to MISSED-by-construction.

---
type: benchmark-results
title: "T4 interdiction: of the incident steps a burn-down control is mapped to, how many does a concrete implementation catch"
created: 2026-11-10
evidence_tier: "B for the planted runs and the scoring (mechanical, reproducible); D for the control-to-check mapping, the fixtures and the holder-of-control judgments (one author, not reviewed)"
---

# T4 results: how many mapped incident steps the top burn-down controls catch

**Pre-registration:** `PREREGISTRATION.md` sha256 `55d3fe5a232e6e0f1dd7002e44632a378761ccaa6e450baab283289253857338`,
frozen 2026-11-10T01:00:30Z. Frozen by agent before run; not owner-reviewed. `sha256sum -c results/PREREG.sha256`
passes after the run, so the file was not edited afterwards. Deviations are listed at the end.

**Environment:** Beelink (Ryzen 7 5800H), WSL2 6.6.87.2-microsoft-standard-WSL2, 14 vCPU, no GPU. Pinned to 4 cores
(`taskset -c 0-3 nice -n 10`, DuckDB `threads=4`) while other benches ran; load average was about 16 on 14 cores during
the runs, so every wall time in `results/timings.json` is under contention and from a monotonic timer. No latency is
claimed, so no rig stamp applies. chrony read 0.586 s slow of NTP at 00:40Z, 0.000012 s fast at 00:58Z and 0.620 s slow
at the 01:00Z freeze, which is above the methodology's §7a threshold and is recorded as a fact; it does not touch these
results. Python 3.12.3, duckdb 1.5.3, SQLite 3.45.1 (stdlib), pySigma 2.0.3, pySigma-backend-sqlite 2.1.1, PyYAML 6.0.3
(`requirements.txt`, pip freeze). Zero spend, no model calls, no containers.

**Inputs:** ATLAS v2026.10 YAML (`ac41ee9f…e142d`, asserted equal to the burn-down's `basis.atlas_sha256`);
`control_burndown_2026.10.json` (built 2026-11-09); OCSF 1.9.0 class and object dump from R1
(`../atlas-ocsf-observables/sources/ocsf-1.9.0`, fetched 2026-11-09T23:02Z). 290 Incident steps re-derived from the YAML
`employs` block and asserted; the per-control reach counts recomputed from the `mitigates` edges match the burn-down's
`reaches_steps` for all twelve top controls.

## Question

The burn-down ranks ATLAS mitigations by how many of the 290 Incident steps they are mapped to, and its design note
already says that is relevance, not interdiction. This bench takes the eight controls at the top of that order whose
text names a telemetry or enforcement artifact, implements each as the check the mitigation sentence describes, plants
the mapped steps as OCSF 1.9.0 event sequences, and scores how many a reasonable implementation catches.

## Headline

Of the top twelve controls in the greedy order, four have no artifact a check can key on (M0042 Threat Intelligence
Program, M0001 Limit Model Artifact Release, M0000 Limit Public Release of Information, all Policy; and M0034 Deepfake
Detection, whose artifact is a classifier verdict). Those three Policy entries carry 74 of the burn-down's first-twelve
marginal steps. The eight that remain gave 22 rule-selected step-slots (18 distinct steps) and 8 hand-picked mechanism
slots.

| Set (slots) | Engine | CAUGHT | NOISY | MISSED | MISSED-by-construction |
|---|---|---|---|---|---|
| Rule (22) | SQLite (pre-registered for H1) | **1** | 7 | 8 | 6 |
| Rule (22) | DuckDB | 2 | 5 | 9 | 6 |
| Mechanism (8) | both | 3 | 2 | 3 | 0 |

Every slot's state held on all three seeds on both engines (`seeds_agreeing = 3` everywhere). So of the 22 steps the
burn-down credits to these controls, one is caught cleanly by the check the mitigation text describes; seven are
interdicted only together with legitimate background (an enforcement check that also blocks the legitimate traffic, or
a detection with precision between 0.03 and 0.60); eight produce an event on the control holder's ground that the check
does not fire on; and six leave no event on that ground at all, because the step is an adversary-side action, an
outcome, or a content-level deception. The burn-down's marginal-step column counts all 22.

## Per control

Controls in greedy order. "Rule" slots are the mechanical selection; "mech" slots were chosen because the step names an
action on the control's own artifact (declared bias). States are the modal state over three seeds; where the two
engines differ both are shown.

| Control (greedy rank, marginal steps) | Slot | Step | Technique | State | Check that reached it, recall, precision (min–max over seeds) |
|---|---|---|---|---|---|
| M0019 Control Access in Production (2, 50) | rule | CS0076[2] | T0012 | MISSED | E1 0 alerts on planted (20 health-probe FP); D1 0 alerts: 36 pool accounts at 20 calls each sit far under 500/h |
| | rule | CS0076[7] | T0051.000 | MISSED | no content check in M0019 |
| | rule | CS0076[4] | T0024 | MISSED | D1 0 alerts |
| M0043 Agent Resource Lifecycle (3, 23) | rule | CS0076[2] | T0012 | by-construction | no agent in the step; nothing for a broker to see |
| | rule | CS0074[22] | T0072 | **CAUGHT** | E2.api recall 1.0 (6/6), precision 1.0; the agent's repo and gist creations carry `ai_agent_name` and no `delegation_uid` |
| | rule | CS0068[23] | T0091.000 | MISSED | the token minting sits inside `sandbox.exec` tool calls; E2 keys on creation operations and sees none |
| M0005 Access at Rest (4, 18) | rule | CS0076[2] | T0012 | by-construction | API access, no at-rest event |
| | rule | CS0074[10] | T0025 | by-construction | enumeration output via callback; no model or training store touched |
| | rule | CS0076[6] | T0048.004 | by-construction | an outcome, no event |
| | mech | CS0068[0] | T0012 | **CAUGHT** | E3.datastore recall 0.67 (4/6: the gated-bucket list and reads; the two staging-repo creates are not on a gated- or train- bucket), precision 1.0 |
| | mech | CS0023[3] | T0035 | MISSED | E3.file 0 alerts: the reads are by `ray`, the cluster's own approved identity |
| M0011 Restrict Library Loading (5, 14) | rule | CS0074[13] | T0050 | NOISY | E4 recall 1.0 (53/53), precision 0.33–0.35: 98–110 legitimate pip builds also load `setup.py` from `/tmp/pip-build-*` |
| | rule | CS0074[2] | T0011 | MISSED | the payload is a script; every module it loads is allowlisted stdlib |
| | rule | CS0074[24] | T0074 | by-construction | content-level disguise, no load event |
| | mech | CS0031[1] | T0011.000 | **CAUGHT** | E4b recall 0.75 (3/4: the posix, subprocess, socket imports under `torch.load`; the file read is not a module load), precision 1.0 |
| M0020 Generative AI Guardrails (7, 13) | rule | CS0076[7] | T0051.000 | NOISY / **MISSED on DuckDB** | E5a SQLite recall 0.50 (15/30), precision 0.47–0.54 (13–17 quoting-prompt FP); DuckDB recall 0.20 (6/30): 9 of the 15 phrased prompts carry their phrase only in capitalised form and `LIKE` is case-sensitive there, so the 5 lower-case prompts and the one capitalised prompt that also contains a lower-case "you are now" are the 6 that match |
| | rule | CS0076[8] | T0054 | MISSED | chain-of-thought elicitation carries no blocklisted phrase |
| | rule | CS0074[20] | T0068 | NOISY / **CAUGHT on DuckDB** | E5c SQLite recall 1.0 (10/10), precision 0.48–0.53 (9–11 issue-template FP); DuckDB recall 0.60 (6/10) and precision 1.0, because the template lookalike `<!-- Please describe …` matches `please` only case-insensitively |
| | mech | CS0047[2] | T0051.000 | NOISY | E5b recall 0.57 (4/7: `rm -rf`, `terminate-instances`, `s3 rb`, `delete-bucket`; not the prompt, the `fs.delete` path or `iam delete-user`), precision 0.67–0.80 (1–2 cleanup `s3 rb` FP) |
| M0024 AI Telemetry Logging and Monitoring (10, 5) | rule | CS0034[3] | T0047 | MISSED | the liveness calls are logged; none of D6a/b/c inspects media |
| | rule | CS0076[7] | T0051.000 | NOISY | D6c recall 1.0, precision 0.60: it alerts the 3 proxy IPs and the 2 corporate NAT IPs; it fires on the access pathway, not the prompt |
| | rule | CS0076[4] | T0024 | NOISY | D6c, same alerts |
| | mech | CS0053[5] | T0086 | **CAUGHT** | D6a recall 1.0 (8 requests + 8 provider records), precision 1.0: the provider record has a BCC the tool request never carried |
| | mech | CS0047[5] | T0101 | NOISY | D6b recall 0.83 (5/6), precision 0.36–0.62 (3–9 agent scratch-dir deletes) |
| M0040 Adaptive Response Degradation (11, 3) | rule | CS0076[11] | T0135 | MISSED | D7 0 alerts: 20 calls and ≈45k tokens per account per hour against 500 and 200k |
| | mech | CS0075[7] | T0135 | MISSED | D7 0 alerts: 50 accounts at 20 calls each over 24 h |
| M0013 Code Signing (12, 2) | rule | CS0073[1] | T0010.001 | NOISY | E8b recall 1.0 (15/15), precision 0.03: 427–446 legitimate installs also carry no attestation |
| | rule | CS0069[13] | T0103 | by-construction | attacker infrastructure |
| | rule | CS0023[1] | T0010.003 | NOISY | E8c recall 1.0 (5/5), precision 0.07–0.08: 58–67 legitimate hub model loads are unsigned too |
| | mech | CS0047[1] | T0011.001 | MISSED | E8b 0 on planted: the compromised release is validly attested by the real publisher |

E8a (unsigned process or module) alerted 36–43 times per seed on the unsigned-internal-script background and never on a
planted event; no selected step runs an unsigned binary. E2.account never alerted (no planted account creation in the
selected steps). E1 alerted only on the 20 unauthenticated health probes: no mapped step was unauthenticated, which is
the point about stolen valid credentials.

## What the table says

Three patterns carry most of the result.

**Valid credentials and distributed volume defeat the access controls as written.** M0019 is the second control in the
greedy order with 50 marginal steps, and its text asks for authentication and per-identity usage monitoring. Every
distillation step used real accounts (CS0076[2], [4], [7]) and spread the work across pools, so E1 passes them and D1
never reaches the ceiling; M0040's D7 misses for the same reason. The only check that reaches the distillation steps is
M0024's cross-account aggregation (D6c), and it fires on the shared proxy IP, which is also what a corporate NAT looks
like, so it lands NOISY at precision 0.60. Nothing in the three controls' text names cross-account aggregation except
M0024's one sentence on "coordinated behavior across accounts and access pathways".

**Signature and attestation presence checks block the world.** E8b and E8c catch every planted install and model load
(recall 1.0) at precision 0.03 and 0.07, because the pre-committed background has 30% of unpinned installs and every
hub model load unattested or unsigned, which is roughly the 2026 state of PyPI attestations and Hugging Face artifacts.
Meanwhile the one M0013 step that mattered most in its case study, the compromised but validly signed v1.84.0 release
(CS0047[1]), is MISSED, because signing verifies the publisher and not the content. Code Signing interdicts the
dependency-confusion shape only by refusing most legitimate software.

**The clean catches are the ones where the control's artifact carries attribution the attacker cannot strip.** The
four CAUGHT states across the rule set and mechanism set are an agent creating GitHub resources with its agent identity
attached and no broker delegation (E2), a non-approved principal touching a gated bucket (E3), a deserialization
importing `posix` and `subprocess` (E4b), and a provider delivery record disagreeing with the agent's request (D6a). In
each the signal is structural rather than textual, though E3's precision of 1.0 is partly by construction, because the
pre-committed E3 lookalike is approved identities on the same paths (it tests the approved-identity blind spot), so the
background holds no non-approved reader that could produce a false positive. Every text-matching check (E5a, E5b, E5c,
D6b) landed NOISY or MISSED.

## Hypotheses

- **H1 (≤ 7 of 22 rule slots CAUGHT on SQLite): holds.** 1 of 22.
- **H2 (≥ 5 rule slots MISSED-by-construction): holds.** 6, the six declared in the pre-registration.
- **H3 (mechanism set's CAUGHT share exceeds the rule set's on every seed and engine): holds.** 3 of 8 (0.375) against
  1 of 22 (0.045) on SQLite and 2 of 22 (0.091) on DuckDB; states agree across seeds, so the comparison is the same on
  each. The selection effect is about a factor of four to eight.
- **H4 (per-identity volume checks miss every distillation step; D6c reaches CS0076[4]): holds.** D1 and D7 produced
  zero alerts on every seed and engine; D6c reached CS0076[4] with recall 1.0.
- **H5 (engine): holds on the two rules that carried mixed case; not tested on E5b.** E5a recall 0.50 on SQLite against
  0.20 on DuckDB; E5c 1.0 against 0.60; every other rule agrees across engines. E5b carried no mixed-case planted
  content (deviation 2), so its clause is untested, and read literally the hypothesis, which named E5b, is refuted on
  that clause. One thing the hypothesis did not anticipate: on E5c the case sensitivity also removed the lookalike (the
  `Please` in the issue template), so DuckDB's state was *better* (CAUGHT at precision 1.0) while SQLite's was NOISY.
  Case-sensitive `LIKE` loses recall and can gain precision in the same run; neither is the rule's semantics. The
  case-folded supplementary (`lower()` on both sides) gives identical results on both engines: E5a 29 alerts, 15 TP;
  E5c 21 alerts, 10 TP.
- **H6 (E8b and E8c NOISY on every seed): holds.** Precision 0.03 and 0.07–0.08.
- **H7 (M0019, M0040 and M0005 catch none of their rule-set slots): holds.** M0005's one catch is in the mechanism set.

## Variance

Scoring is deterministic given the corpus. Three full runs of `run.py` produced `results/interdiction.json` with the
same sha256 (`d35b492845742f68…`) each time. `truth.json` per seed: 20261109 `dcfe888ba950…`, 20261110 `9b81a897e8da…`,
20261111 `6813ae0e045f…`. Across seeds every state held; precision moved only where the lookalike count moved (E4 FP
98–110, E5a FP 13–17, E5c FP 9–11, D6b FP 3–9, E8b FP 427–446, E8c FP 58–67). `select_steps.py` re-run after the build
reproduced `results/selected_steps.json` byte for byte (stop rule c).

## Deviations from the pre-registration

1. "Any 1 h window" is implemented as tumbling hour buckets (`time - (time % 3600000)`), which both engines compute
   identically; a sliding window would catch a burst that straddles a bucket edge. No planted step is near a ceiling, so
   this does not change a state here.
2. E5b carries no mixed-case planted content. The destructive commands (`rm -rf`, `aws … terminate-instances`,
   `aws s3 rb`) have no honest mixed-case form, and planting `RM -RF` would have been a fixture written for the
   hypothesis. H5's E5b clause is therefore untested.
3. The lookalike rates for the agent-runtime checks (E5b 1%, D6b 2%, E5c 3%) were applied to the 300 agent-runtime rows
   inside the 2,000-row `api_activity` background, not to 2,000 rows, so the absolute FP counts are 1–2, 3–9 and 9–11
   rather than the ~20, ~40 and ~60 the pre-registration's percentages imply over 2,000. The states would be the same
   at the larger counts (lower precision, same side of T).
4. E8b's "30% of installs lack an attestation" is implemented as 30% of installs of unpinned packages; the three pinned
   packages always carry their publisher. The realised share is 21–23% of installs.
5. E3 keys on `gated-` and `train-` bucket prefixes as pre-registered, so the two dataset-repository creates in CS0068[0]
   (buckets named `eval-agent-staging-*`) are not matched; recall 0.67 instead of 1.0. CS0031[1] plants four events, of
   which the file read is not a module load; E4b recall 0.75.
6. The pre-registration's "Expected" column was prose, not a hypothesis, and four cells differ from what landed:
   CS0047[2] expected CAUGHT and landed NOISY (the pre-committed `s3 rb` cleanup lookalike, 1–2 FP against 4 TP);
   CS0074[20] expected NOISY and landed CAUGHT on DuckDB only (the case-sensitivity effect above); CS0047[5] was written
   as "CAUGHT or NOISY" and landed NOISY; and M0020 / CS0076[7] read "CAUGHT on SQLite if ≥ half carry blocklist
   phrases", exactly half did and recall reached 0.50, but it landed NOISY because that cell did not account for the
   pre-committed quoting-prompt background (13–17 FP). Everything else landed as the column said.
7. Loading the same rows into DuckDB with `executemany` took 100–120 s per seed under contention, which is why
   `timings.json` totals are 104–210 s per seed. That is harness cost, not a result.

## Files and commands

```
PREREGISTRATION.md            frozen 2026-11-10T01:00:30Z; results/PREREG.sha256, results/PREREG.frozen_at
extract_mappings.py           pre-freeze orientation: mitigation text, mitigates edges, incident steps -> results/mappings_top12.json
select_steps.py               pre-freeze step selection by rule -> results/selected_steps.json
ocsf_fields.py                validates every fixture column against the OCSF 1.9.0 dump (profiles applied)
gen_corpus.py                 synthetic test-fixture corpus, 10 tables, 3 seeds -> corpus/<seed>/corpus.sqlite + truth.json
rules/*.yml                   15 Sigma rules (single-event checks), compiled with pySigma-backend-sqlite
checks.py                     check catalogue + hand SQL for D1, D6a, D6c, D7
run.py                        the run; results/interdiction.json (deterministic), results/timings.json (monotonic, under contention)
requirements.txt              pip freeze of the venv

python3 -m venv .venv && .venv/bin/pip install duckdb==1.5.3 pySigma==2.0.3 pySigma-backend-sqlite==2.1.1 PyYAML==6.0.3
.venv/bin/python -I ocsf_fields.py
taskset -c 0-3 nice -n 10 .venv/bin/python -I run.py      # x3 for the determinism check
sha256sum -c results/PREREG.sha256
```

## Limits

- One author wrote the mitigation-to-check mapping, the fixtures, the lookalikes and the rules, and chose where each
  control's holder stands. Another reader could place M0043 with the victim rather than the agent operator, which would
  move the one rule-set CAUGHT (CS0074[22]) to MISSED-by-construction and leave the rule set with none.
- The fixtures model the mechanism of each case-study step at small, invented volumes; the case studies give few
  numbers (CS0056 reports 24,000 accounts and 16 million exchanges, CS0075 over 100,000 prompts), and the planted pools
  are far smaller. Per-identity volumes were kept under the ceilings because the records describe account pools, not
  hot accounts; a defender with a tighter ceiling or a per-ASN rule would see more, and that rule is M0024's, not M0019's.
- Synthetic background, so precision figures show the mechanism and are not field false-positive rates. The E8b and E8c
  rates in particular depend on how much of a real organisation's software and model inventory is attested or signed.
- Tool invocation rides on `api_activity` because OCSF 1.9.0 has no tool-call class; a future class could change what
  E2, E5b, D6a and D6b can key on.
- The checks follow the mitigation text literally and stop at one discriminating filter. Real deployments tune
  (allowlists for pip build paths, per-ASN aggregation, publisher pinning for every package), and several NOISY states
  would become CAUGHT under tuning; that tuning is not in the mitigation text, which is the point being measured.
- ATLAS-only weights; the hub's 48-incident set is out of scope. Nothing here is a statement about any real environment.

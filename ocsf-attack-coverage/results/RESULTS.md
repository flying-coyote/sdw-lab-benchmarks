# OCSF ATT&CK coverage — measured Sigma firing over a normalized OCSF store (results)

**Tier B. Synthetic testbed, single machine.** Coverage here means one thing and makes one
claim: the MEASURED runtime firing of compiled Sigma rules, run through pySigma to SQL over
the OCSF-shaped fidelity store (Store F), scored against the planted attack-chain ground
truth from the deterministic testbed (fingerprint `46af223bf406…`,
seed 20260601). Every technique lands in exactly one of three measured
states — **DETECTED** (the truth needle is in the rule's matched set and precision ≥ the
stated floor T=0.9), **NOISY** (the needle is caught but precision
< T, so the rule fires below the floor and drags in benign background), and **MISSED** (a
recall miss, or no rule/needle exists for the technique so the corpus carries no positive to
catch). Those three are the only claims this bench makes.

**3/8 techniques detected; 1 noisy; 4 missed.**

| stage | ATT&CK | OCSF class | rule | state | matches | FPs | precision |
|---|---|---|---|---|---|---|---|
| credential access | T1003.001 | 1007 | — | MISSED | 0 | 0 | 0.0 |
| lateral movement | T1021 | 4001 | rdp_lateral.yml | NOISY | 2960 | 2959 | 0.0003 |
| exfiltration | T1048 | 4001 | — | MISSED | 0 | 0 | 0.0 |
| execution | T1059.001 | 1007 | encoded_powershell.yml | DETECTED | 1 | 0 | 1.0 |
| C2 | T1071 | 4003 | c2_domain.yml | DETECTED | 1 | 0 | 1.0 |
| priv-esc | T1098 | 6003 | nomfa_privesc.yml | DETECTED | 1 | 0 | 1.0 |
| credential access | T1110 | 3002 | — | MISSED | 0 | 0 | 0.0 |
| impact | T1490 | 1007 | — | MISSED | 0 | 0 | 0.0 |

## Reading

The detected techniques are the specific rules — encoded PowerShell on a named host, an
`AttachUserPolicy` without MFA, a known C2 domain resolution — that fire cleanly with no
false positives, so detection-as-code survives the round trip from a portable Sigma rule to a
query over a normalized OCSF store, which is the end-to-end claim a compile-time check can't
make on its own. The noisy band is the SOC false-positive tax measured rather than assumed: T1021 (precision 0.0003, 2959 benign matches). The generic rule catches the planted needle *and* all the benign background that shares its coarse signal (every benign port-3389 connection), so it fires below the stated precision floor T=0.9. A rule can only be precise about fields the OCSF normalization preserved, which is why a measured precision column matters more than a compile check.

The missed techniques are the honest part, and the gap hop is where the discipline matters.
For each one the Security Context Graph can name D3FEND defenses that *might* counter the
technique, but these are carried as possibilities with their provenance attached, never as
coverage. For **T1003.001** (credential access, no_rule_or_no_needle), the graph names 10 D3FEND defenses that *may* counter it, but 0 survive a min_trust=0.6 soundness filter — the rest are intent-blind artifact_cooccurrence (trust 0.25), a lead and not a detection (counters != detects). For **T1048** (exfiltration, no_rule_or_no_needle), the graph names 26 D3FEND defenses that *may* counter it, but 0 survive a min_trust=0.6 soundness filter — the rest are intent-blind artifact_cooccurrence (trust 0.25), a lead and not a detection (counters != detects). For **T1110** (credential access, no_rule_or_no_needle), the graph names 25 D3FEND defenses that *may* counter it, but 0 survive a min_trust=0.6 soundness filter — the rest are intent-blind artifact_cooccurrence (trust 0.25), a lead and not a detection (counters != detects). For **T1490** (impact, no_rule_or_no_needle), the graph names 13 D3FEND defenses that *may* counter it, but 0 survive a min_trust=0.6 soundness filter — the rest are intent-blind artifact_cooccurrence (trust 0.25), a lead and not a detection (counters != detects). The pattern across every missed technique on this run is the same: the
D3FEND leads exist, but none survive a min_trust=0.6 soundness filter because they are all
intent-blind `artifact_cooccurrence` inferences (trust 0.25) — a defense that shares a
digital artifact with the technique is a place to look, not proof that it detects anything.
Laundering one of those into a coverage number is exactly the overclaim this bench refuses to
make.

## Determinism and caveats

The corpus is the testbed's, reused not regenerated, so determinism is inherited: `gen_corpus.py`
only projects an ATT&CK-tagged OCSF view over the existing Store F (no new rows, no new
randomness), and `coverage.json` scores sets of `event_uid`s, which are order-independent, then
dumps `sort_keys=True`. A re-run reproduces `coverage.json` identically
(`rerun_identical = true`),
seeded from `MASTER_SEED = 20260601` against Store F fingerprint
`46af223bf406…`. Tier B: one synthetic APT29-style chain on
a single machine, aggregate-safe, never real telemetry. The detection / noisy / missed split,
and the refusal to count an inferred may_counter lead as coverage, are the transferable
findings — not the absolute technique count, which is bounded by what the planted corpus
contains.

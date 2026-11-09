---
type: benchmark-spec
title: "AI analyst pre-registrations: R3, R9, R11"
created: 2026-11-09
status: frozen-by-agent-not-owner-reviewed
tags: [pre-registration, ai-analyst, zero-defense, inference-cost]
---

# AI analyst pre-registrations: R3, R9, R11

Three pre-registrations from `SITE-REVIEW-2026-11-09.md` section 5. None has been run. R3 and R11 need paid
model calls, and R9 needs a longer build, so each file stops at the design, the falsifiers and a cost estimate.

Frozen by agent before run; not owner-reviewed. Freeze timestamp (UTC): 2026-11-09T23:03:24Z

```text
3b76034daed77bf08317abaadf9e7d5d7168a9e493b7f3167a7f5cdbcedeb834  R3.md
db6aca21a324f988df71b325b685c3344a2056475e076bf27d9706a19f2785db  R9.md
cd633a2de5efc51bdcbef57c46fe9911cd027bc99408543f1c83587b5464e62d  R11.md
```

| area | question | USD (expected / ceiling) | compute hours | build hours |
| --- | --- | --- | --- | --- |
| R3 | over-triggering, containment before evidence, recall loss with volume | ~$92 / $138 (Sonnet 5.5 + Haiku 5.5); +Opus 5.5 ~$400 ceiling | ~97 local serial + ~6 hosted | ~22 to 30 |
| R9 | does the D3FEND structural zero match a measured detection zero for the 11 IPC and file-hiding members | $0 | under 1 | ~12 to 15, or 20 to 27 with the registry/file extension |
| R11 | USD per correct triage and per NL2SQL answer, right-sized model | ~$217 / $325 (all three tiers); ~$75 / $112 without Opus | ~75 local serial | ~12 to 14 |

R11's agentic-hunt family prices R3's logged traces, so running R3 first avoids paying twice. If any file is
edited after this freeze, its new hash goes in a dated amendment line below, with the reason.

## Amendments

- 2026-11-09, clarification added by the independent verifier, not owner-reviewed (see `VERIFICATION.md`).
  R3.md, R9.md and R11.md are unchanged and their frozen hashes above still match. Which rules run does not
  change. R9's rule counts use parent-includes-sub-technique matching: a rule tagged with a sub-technique
  counts toward its parent. That is the ordinary ATT&CK reading of "tags include the technique ID", and it is
  pinned here as the selection rule. It only makes a difference for the two parents. At SigmaHQ commit
  `994da166`, T1559 has 0 rules tagged exactly and 4 through T1559.001 (3) and T1559.002 (1). T1048 has 9
  exact and 18 including sub-techniques. The run adds `exact` and `via_subtechnique` reporting columns
  beside each technique's rule count. Because T1559 and T1559.001 rest on the same three dns/network/process
  rules, their two reported states are one test, not two, and the write-up says so. Whether to switch to
  exact-ID matching is left for the owner to rule on; it is not applied.

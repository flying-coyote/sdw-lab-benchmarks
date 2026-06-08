# BENCH-B — mapping oracle: results

**Tier B, local model ladder.** Five conditions on source→OCSF field mapping, scored
against the hand-curated C1 gold key with every predicted path validated against the
OCSF 1.8.0 subset. Primary metric is the **silent-error rate** (a path that doesn't
exist); exact-match path-correctness is reported but undercounts valid alternatives.
The model ladder is the capability gradient available without a frontier API key.

Gold: 141 real-path mappings across 6 vendor sources (Okta System Log, CrowdStrike
Detection Summary, Palo Alto PAN-OS TRAFFIC, Cisco ASA connection syslog, Cisco Umbrella
DNS, Zscaler ZIA Web). Conditions: none, schema, formal, skill, wrong_grounding.

The **wrong_grounding** condition gives a grounding note for the *wrong* OCSF class —
the control that separates correct grounding from extra tokens. Both phi3 (3.8B) and
gemma4:26b (26B) are now run on the **full 141-item set, all 5 conditions** (705
inferences each). The earlier gemma4 20-item stratified sample is retained in
`results.json` as `gemma4:26b-sample20` and is superseded by the full run below.

> **Scope note — larger LOCAL model, not frontier SaaS.** gemma4:26b is a 26B-parameter
> local model on a Beelink WSL2 host (ollama, temperature 0). It is NOT a frontier-SaaS
> leg (no Claude/GPT-4o/Gemini key available). It addresses H-PRACTITIONER-OWNED-AGENTIC-01
> (the sub-frontier / local-inference capability gradient). The frontier leg — which is
> what would settle whether grounding is a *moat* or a *crutch a stronger model wouldn't
> need* — remains open pending an API key.

---

## Comparison table — full 141-item set, both models

| condition | phi3 (3.8B) silent-error | phi3 path-correct | gemma4:26b silent-error | gemma4:26b path-correct |
|---|---|---|---|---|
| none | 0.99 | 0.00 | 0.83 | 0.03 |
| schema | 0.69 | 0.01 | 0.18 | 0.08 |
| formal | 0.72 | 0.01 | 0.19 | 0.08 |
| skill | 0.60 | 0.04 | 0.30 | 0.05 |
| wrong_grounding | 0.72 | 0.01 | 0.18 | 0.06 |

### Lifts (negative = fewer invented paths)

| lift | phi3 (n=141) | gemma4:26b (n=141) |
|---|---|---|
| silent, schema − none | -0.31 | **-0.65** |
| silent, skill − none | -0.40 | -0.52 |
| silent, formal − none | -0.27 | -0.64 |
| **formal − wrong_grounding (control)** | **+0.01** | **+0.01** |
| path-correct, skill − schema | +0.04 | -0.03 |

The control row is the headline: at full n=141 the formal-minus-wrong_grounding gap is
**+0.007 (phi3)** and **+0.014 (gemma4:26b)** — both essentially zero, both with the
*correct* grounding note a hair *worse* than the deliberately-wrong one. The 20-item
sample's −0.05 (correct grounding marginally ahead) was noise; it does not survive the
full set.

---

## phi3:latest (3.8B, n=141)

| condition | silent-error | path-correct |
|---|---|---|
| none | 0.99 | 0.00 |
| schema | 0.69 | 0.01 |
| formal | 0.72 | 0.01 |
| skill | 0.60 | 0.04 |
| wrong_grounding | 0.72 | 0.01 |

Schema captures most of the (small) lift; the formal grounding note adds nothing over
wrong grounding (+0.01); the ontology-thinking *skill* prompt is the only thing that
beats schema for this weak model (0.60 vs 0.69).

---

## gemma4:26b (26B, n=141 — full run)

| condition | silent-error | path-correct |
|---|---|---|
| none | 0.83 | 0.03 |
| schema | 0.18 | 0.08 |
| formal | 0.19 | 0.08 |
| skill | 0.30 | 0.05 |
| wrong_grounding | 0.18 | 0.06 |

- silent-error, schema − none: **-0.65** (the dominant lever, far larger than phi3's -0.31)
- silent-error, formal − none: -0.64
- silent-error, skill − none: -0.52
- **control** silent-error, formal − wrong_grounding: **+0.01** (correct grounding ≈ wrong grounding — the lift is the schema constraint, not the conceptual note)
- path-correct, skill − schema: -0.03 (the skill prompt *hurts* the strong model)

### gemma4:26b by source (schema condition)

| source | n | silent-rate | path-correct |
|---|---|---|---|
| Cisco ASA connection syslog | 14 | 0.00 | 0.07 |
| Palo Alto PAN-OS TRAFFIC | 46 | 0.04 | 0.04 |
| Cisco Umbrella DNS | 5 | 0.20 | 0.00 |
| Okta System Log | 27 | 0.22 | 0.04 |
| Zscaler ZIA Web | 18 | 0.33 | 0.06 |
| CrowdStrike Detection Summary | 31 | 0.35 | 0.19 |

The network/connection sources (ASA, PAN-OS) map almost cleanly; the finding/identity
sources (CrowdStrike, Zscaler, Okta) are where the model still invents attributes — the
same sources C1 flagged as the lossiest for human mapping, so the model's failures track
the genuinely hard mappings rather than being uniform noise.

---

## Run / timing

Full 141-item × 5-condition run = **705 inferences, ~143 minutes** wall-clock on the
local WSL2 host (gemma4:26b via ollama, temperature 0, `keep_alive=15m`). Median
inference **2.1 s**, mean 12.1 s, max 258 s — far under the 40 s/inference the 20-item
sample assumed, because keeping the model warm avoids a cold reload per call. The run
is checkpointed per inference (`results/gemma4_full_checkpoint.jsonl`) and resumable.

**No-parse (None) responses, 60 of 705**, concentrated where the prompt is least
constrained or most verbose: 32 in `none` (no schema to anchor to — the model rambles or
refuses) and 21 in `skill` (the long ontology-thinking instruction pushes the 26B model
into incoherence/timeouts), versus 2 in `schema`, 2 in `formal`, 3 in `wrong_grounding`.
This is the mechanism behind `skill` underperforming `schema` for gemma4:26b.

---

## Reading

**The central question — is the *content* of formal grounding the lever, or just the
schema constraint and the extra tokens?** Answered, now at full n=141 and across an
order of magnitude of model size: the **formal − wrong_grounding control is ≈ 0 at both
scales** (+0.007 phi3, +0.014 gemma4:26b). A grounding note for the *correct* OCSF class
does not beat a grounding note for the *wrong* class. What cuts invented attributes is
the **schema constraint** (the list of valid paths) plus the model's own reasoning — not
the conceptual grounding prose. This tempers any "formal grounding is the moat" framing
for H-CONCEPT-GRAPH-01: at the sub-frontier/local tier the harness (schema-validity
enforcement), not the ontological note, is doing the safety work. The frontier-SaaS leg
is the one that could still overturn this — a model strong enough to *use* the conceptual
note rather than just the path list — and it remains the open question pending an API key.

**The local capability gradient (H-PRACTITIONER-OWNED-AGENTIC-01) is real and large.**
Under schema grounding the 26B model invents a path 18% of the time versus the 3.8B
model's 69% — the none→schema drop is −0.65 vs −0.31. Exact-path correctness is also ~8×
higher (0.08 vs 0.01), though still low because the metric is strict. A 26B local model
is meaningfully more usable for schema-constrained OCSF mapping than a 3.8B one; whether
0.18 silent-error under schema is acceptable for unattended use is a practitioner call,
and the residual is concentrated in the genuinely hard finding/identity sources.

**Capability-dependent prompt interaction.** The ontology-thinking *skill* prompt helps
the weak model (phi3 skill 0.60 < schema 0.69) but *hurts* the strong one (gemma4 skill
0.30 > schema 0.18), because its verbosity triggers incoherence/timeouts (21 no-parse
responses vs 2 under schema). More instruction is not monotonically better — the right
prompt depends on the model's capability.

Tier B: local models, single-shot, temperature 0; exact-match undercounts valid
alternatives; the gold set is curated. Tier-A needs a published larger gold set, a named
reviewer on the ambiguous calls, and an independent frontier model.

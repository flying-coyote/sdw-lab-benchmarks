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
the control that separates correct grounding from extra tokens.

> **Scope note — larger LOCAL model, not frontier SaaS.** The gemma4:26b leg is a
> 26B-parameter local model run on a Beelink WSL2 host (ollama, temperature 0). It
> is NOT a frontier-SaaS leg (no Claude/GPT-4o/Gemini key available). It directly
> addresses H-PRACTITIONER-OWNED-AGENTIC-01: the sub-frontier / local-inference
> capability gradient. The frontier leg remains open pending an API key.

---

## Comparison table — all 5 conditions

phi3 was run on the full 141-item gold set. gemma4:26b was run on a 20-item
stratified sample (first 3 per source sorted by field name; Cisco Umbrella DNS all 5).
Rates are comparable in direction but not in precision — the sample-size difference
inflates gemma4's variance considerably. See Sampling below.

| condition | phi3:latest (n=141) silent-error | phi3:latest path-correct | gemma4:26b (n=20) silent-error | gemma4:26b path-correct |
|---|---|---|---|---|
| none | 0.99 | 0.00 | 0.90 | 0.10 |
| schema | 0.69 | 0.01 | 0.15 | 0.05 |
| formal | 0.72 | 0.01 | 0.15 | 0.00 |
| skill | 0.60 | 0.04 | 0.35 | 0.00 |
| wrong_grounding | 0.72 | 0.01 | 0.20 | 0.00 |

### Lifts (negative = fewer invented paths)

| lift | phi3:latest | gemma4:26b |
|---|---|---|
| silent, schema − none | -0.31 | -0.75 |
| silent, skill − none | -0.40 | -0.55 |
| silent, formal − none | -0.27 | -0.75 |
| **formal − wrong_grounding (control)** | **+0.01** | **-0.05** |
| path-correct, skill − schema | +0.04 | -0.05 |

---

## phi3:latest (3.8B, n=141, full gold set)

| condition | silent-error | path-correct |
|---|---|---|
| none | 0.99 | 0.00 |
| schema | 0.69 | 0.01 |
| formal | 0.72 | 0.01 |
| skill | 0.60 | 0.04 |
| wrong_grounding | 0.72 | 0.01 |

- silent-error, schema − none: -0.30 (negative = fewer invented paths)
- silent-error, skill − none: -0.40
- silent-error, formal − none: -0.27
- **control** silent-error, formal − wrong_grounding: +0.01 (negative = correct grounding beats wrong grounding; ~0 = the lift was tokens, not content)

---

## gemma4:26b (26B, n=20, stratified sample)

> Larger LOCAL model — NOT the frontier-SaaS leg. Addresses the sub-frontier
> capability gradient only. All 5 conditions run on a 20-item stratified sample;
> full 141-item run at ~40 s/inference would take approximately 470 minutes.

| condition | silent-error | path-correct |
|---|---|---|
| none | 0.90 | 0.10 |
| schema | 0.15 | 0.05 |
| formal | 0.15 | 0.00 |
| skill | 0.35 | 0.00 |
| wrong_grounding | 0.20 | 0.00 |

- silent-error, schema − none: -0.75 (negative = fewer invented paths)
- silent-error, skill − none: -0.55
- silent-error, formal − none: -0.75
- **control** silent-error, formal − wrong_grounding: -0.05 (a 1-item difference on n=20; within noise — closer to "tokens" than "correct grounding" in the same direction as phi3)

### gemma4:26b by source (schema condition; representative of grounded conditions)

| source | n | silent-rate | path-correct |
|---|---|---|---|
| Cisco ASA connection syslog | 3 | 0.00 | 0.00 |
| Cisco Umbrella DNS | 5 | 0.20 | 0.00 |
| CrowdStrike Detection Summary | 3 | 0.33 | 0.33 |
| Okta System Log | 3 | 0.00 | 0.00 |
| Palo Alto PAN-OS TRAFFIC | 3 | 0.00 | 0.00 |
| Zscaler ZIA Web | 3 | 0.33 | 0.00 |

---

## Sampling

**gemma4:26b:** stratified deterministic sample. For each of the 6 vendor sources, the
first 3 fields sorted by field name were taken; Cisco Umbrella DNS (only 5 real-path
mappings total) contributed all 5. Total: 20 items, all 5 conditions, 100 inferences.
At the observed ~40 s/inference on a local Beelink/WSL2 host (ollama), a full
141-item × 5-condition run would take approximately 470 minutes — well beyond a
reasonable runtime bound. One inference (`event.ComputerName`, none condition) ran to
106 s due to a verbose "thinking aloud" response; the extracted path was not a valid
OCSF attribute, so it scored as a silent error. The skill condition produced two None
responses (timeout/incoherence), both scored as silent errors.

**phi3:latest:** full 141-item gold set, all 5 conditions, 705 inferences; no sampling.

---

## Reading

Silent-error rate is the headline because path-correctness on sub-frontier local models
stays low — they rarely land the exact gold OCSF path. Where schema, grounding, and the
ontology-thinking discipline cut the silent-error rate, that is the security-relevant
signal: fewer invented attributes. The wrong-grounding control is the honesty check — if
`formal` beats `wrong_grounding`, correct grounding content is doing work; if they tie,
the lift was just more tokens.

**What changes from phi3 to gemma4:26b:** the 26B model enters with a substantially
lower silent-error rate when grounding is provided — 0.15 vs phi3's 0.69 under schema
alone. The absolute none→schema reduction (−0.75 vs phi3's −0.31) looks dramatic, but
the sample-size difference means those figures carry wide confidence intervals. The
direction is consistent: grounding still helps, schema alone captures most of the lift,
and the skill condition underperforms schema for gemma4:26b (0.35 vs 0.15), possibly
because the ontology-thinking discipline adds token length that occasionally pushes the
model into timeouts or incoherence (two None responses in the skill condition, versus
zero in schema/formal/wrong_grounding).

**The formal-vs-wrong_grounding gap (the central "is formal grounding inert?" question):**
for phi3 the gap was effectively zero (+0.01), confirming that the grounding lift in the
3.8B model was extra tokens, not correct content. For gemma4:26b the gap is −0.05 —
formal marginally beats wrong_grounding — but on n=20 that is a single-item difference
and well within noise. The tentative reading is that the "formal grounding is inert; the
reasoning discipline is the lever" finding survives the scale-up from 3.8B to 26B on
this sample. That conclusion requires confirmation on the full 141-item set before it
carries any weight.

**H-PRACTITIONER-OWNED-AGENTIC-01:** the sub-frontier gradient is real in the sense
that gemma4:26b hallucinates substantially less than phi3 under schema grounding. Whether
the improvement is large enough to make local-only deployment practical for OCSF mapping
work is a practitioner judgment the bench can't resolve on 20 items. The frontier leg,
pending an API key, would determine whether the residual 0.15 silent-error rate under
schema is a ceiling for the local-inference regime or is mostly noise.

Tier B: local models, single-shot, temperature 0; exact-match undercounts valid
alternatives; the gold set is curated. Tier-A needs a published larger gold set, a
named reviewer on the ambiguous calls, and an independent frontier model.

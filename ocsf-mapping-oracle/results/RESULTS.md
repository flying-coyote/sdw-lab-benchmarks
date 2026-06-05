# BENCH-B — mapping oracle: results

**Tier B, local model ladder.** Five conditions on source→OCSF field mapping, scored against the hand-curated C1 gold key with every predicted path validated against the OCSF 1.8.0 subset. Primary metric is the **silent-error rate** (a path that doesn't exist); exact-match path-correctness is reported but undercounts valid alternatives. The model ladder is the capability gradient available without a frontier API key.

Gold: 141 real-path mappings across 6 vendor sources (Okta System Log, CrowdStrike Detection Summary, Palo Alto PAN-OS TRAFFIC, Cisco ASA connection syslog, Cisco Umbrella DNS, Zscaler ZIA Web). Conditions: none, schema, formal, skill, wrong_grounding.

The **wrong_grounding** condition gives a grounding note for the *wrong* OCSF class — the control that separates correct grounding from extra tokens.

## phi3:latest

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

## Reading

Silent-error rate is the headline because path-correctness on sub-frontier local models stays low — they rarely land the exact gold OCSF path. Where schema, grounding, and the ontology-thinking discipline cut the silent-error rate, that is the security-relevant signal: fewer invented attributes. The wrong-grounding control is the honesty check — if `formal` beats `wrong_grounding`, correct grounding content is doing work; if they tie, the lift was just more tokens. Across the model ladder, a lift that shrinks as the model grows reads as a sub-frontier teaching effect rather than a frontier moat (the question H-PRACTITIONER-OWNED-AGENTIC-01 asks; the frontier leg, pending an API key, would close it).

Tier B: local models, single-shot, temperature 0; exact-match undercounts valid alternatives; the gold set is curated. Tier-A needs a published larger gold set, a named reviewer on the ambiguous calls, and an independent frontier model.
# BENCH-B — mapping oracle: results (first pass)

**Tier B, local weak-model leg only.** This runs the four-condition design on a local open-weight model via Ollama. The independent frontier leg and the larger gold set are the expansion (the frontier leg needs an API key), so the weak-vs-frontier capability gap is *not* resolved here; the within-weak-model lifts are. The primary metric is the **silent-error rate** — a field mapped to an OCSF path that does not exist in 1.8.0 — because exact-match path-correctness penalizes valid alternatives and is the wrong headline for a weak model.

Gold: 28 hand-curated C1 source→OCSF mappings across Okta System Log, Palo Alto PAN-OS TRAFFIC. Every predicted path validated against the checked-in OCSF 1.8.0 subset.

## phi3:latest

| condition | path-correct | silent-error rate |
|---|---|---|
| none | 0.00 | 1.00 |
| schema | 0.00 | 0.89 |
| formal | 0.00 | 0.82 |
| skill | 0.00 | 0.50 |

- **schema − none** (path-correct): +0.00
- **formal − schema** (path-correct): +0.00
- **skill − schema** (path-correct): +0.00
- **silent-error, schema − none**: -0.11 (negative = fewer invented paths)

## Reading

Path-correctness on a sub-frontier model is low across the board — an 8B-class local model rarely lands the exact gold OCSF path, which is why silent-error rate is the metric that carries the finding. Where the formal grounding and the ontology-thinking skill condition move the silent-error rate, that is the security-relevant signal: a disciplined prompt produces fewer invented paths even when the model can't name the exactly-right one. The frontier leg is what would show whether that lift is a sub-frontier teaching effect or a frontier moat (H-PRACTITIONER-OWNED-AGENTIC-01), and it is the next step.

Caveats: exact-match scoring undercounts valid alternatives; one weak model, single-shot, temperature 0; the gold set is a curated subset. Tier B.
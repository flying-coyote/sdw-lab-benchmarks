# Frontier-leg replication (run-2) — 2026-06-14

The frontier leg (Opus-4.8-as-proxy, no metered API — the intended `dump_frontier_prompts.py`
path) was a **single blind run** (committed `85264cf`). LLM mapping is non-deterministic, so
this is an independent second blind pass over the same 705 prompts (141 gold × 5 conditions),
mapped by 5 fresh Opus-4.8 subagents (one per condition), scored with the same `run.py`
normalize + OCSF-1.8.0 valid-path closure. Subagents never saw the gold key.

| condition | run-1 path-correct | run-2 path-correct | run-1 silent-err | run-2 silent-err |
|---|--:|--:|--:|--:|
| none | 55% | 62% | 24% | 31% |
| schema | 57% | 66% | 13% | 28% |
| formal | 59% | 63% | 15% | 27% |
| skill | 60% | 71% | 16% | 27% |
| wrong_grounding | 56% | 74% | 17% | 20% |
| **mean** | **58%** | **67%** | **17%** | **27%** |

Inter-run agreement (normalized path identical between run-1 and run-2): **490/705 = 70%**.

## What the replication shows

1. **The single-run frontier number was not precise.** Path-correctness moved 58% → 67% and
   silent-error 17% → 27% between two blind runs of the same model on the same prompts, with
   only 70% of fields mapped identically. The honest frontier figure is a band, not a point:
   **path-correct ~58–67%, silent-error ~17–27%** — both still far better than phi3 (3.8B):
   ~4% best path-correct, 60–99% silent-error. The capability gap (frontier ≫ weak local) is
   robust to the run-to-run noise; the exact magnitudes are not.

2. **The silent-error metric is prompt- and subset-sensitive.** run-2's higher silent-error is
   partly an artifact: the run-2 subagents were instructed to treat the in-prompt valid-path
   lists as non-exhaustive and map against full OCSF 1.8.0, so they emitted real OCSF paths
   that fall outside the checked-in 1.8.0 *subset* the scorer validates against — counted as
   "silent" even when the path is real. So silent-error here conflates true invented-path errors
   with subset-coverage gaps. **Path-correctness (vs the gold) is the more robust metric** at
   this harness maturity; silent-error should be read with the subset caveat, or the subset
   closure expanded to full 1.8.0 before the metric is quoted as a hard number.

## Caveat / method note

run-2 batched per condition (one subagent maps all 141 fields for a condition) rather than the
strict single-shot per-field the local Ollama leg used — a declared deviation; the prompts are
self-contained and the agents were instructed to map each field independently. A third run with
the path list treated as authoritative (constrain to in-prompt paths) would separate true run
variance from the subset-coverage effect on silent-error; not run here (the quiet-window
priority moved to validating the literature-load-bearing flagship). Tier B; Opus-4.8 via the
Claude Code agent harness, harness defaults (no temperature/seed control).

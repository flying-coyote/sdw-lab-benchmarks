# Pipeline normalization-fidelity bench — what the OCSF mapping layer actually loses (task #10)

**Status: PRE-REGISTERED 2026-06-10, before any scored run.** This README is the
pre-registration; design, scoring, and predictions are committed ahead of the first
scored pass and will not be edited after scoring starts (errata get appended, not
rewritten). Scored runs happen in quiet machine windows only. Matrix home: Component 4
(Ingestion / Route) — any scoring change routes through the karen-evaluator +
hypothesis-validator gate.

## Why this bench

The Matrix's Component 4 criteria lead with "OCSF normalization at-source," and the
candidates' marketing all claims it, but no public benchmark measures what each tool's
shipped mapping actually preserves. The schema-crosswalk corpus (six schemas → OCSF
1.8.0) measured what the *schemas* can express; this bench measures what the *tools*
deliver — the gap between a mapping that is possible and the mapping that ships.

## Mechanism

Three pipeline tools map the same pinned multi-source corpus to OCSF 1.8.0 using each
tool's most-official available mapping (shipped function/pack first, vendor-published
example second, hand-written only where nothing official exists — and labeled as such):

- **Tenzir** (current stable at run time; built-in OCSF mapping operators)
- **Cribl** (free tier; the published OCSF pack)
- **Vector** (current stable; VRL — vendor-published OCSF examples where they exist,
  else a minimal hand-written mapping labeled non-official)

Tool and mapping-artifact versions are pinned in the results at run time; every claim
is version-bound.

**Corpus (sha256-pinned at run time, drawn from existing lab tooling):** four source
classes — Zeek conn (network), AWS CloudTrail (cloud audit), Sysmon process events
(EDR-shaped), and an authentication/identity source — at a size sized for mapping
fidelity rather than throughput (fidelity is per-record; ~100k events per source).

## Scoring (three fidelity levels, per source × tool)

1. **Field fidelity** — fraction of populated source fields that land in a typed OCSF
   attribute (vs dropped, vs stuffed into `unmapped`/raw blobs). The existing
   ocsf-mapping-fidelity gate tooling scores this level.
2. **Value fidelity** — of the fields that land, fraction whose values survive
   unmangled: type coercions, truncations, enum mistranslations, timestamp
   timezone/precision loss. Scored by deterministic value round-trip comparison.
3. **Semantic fidelity** — correct OCSF class assignment, correct activity_id /
   type_uid enums, and the five recurring crosswalk failure classes from the
   six-schema corpus checked explicitly (entity-role inversion, multi-event collapse,
   severity remapping, observables flattening, context-collapse fields).

Answer-equality discipline carried over: a panel of SOC-shaped queries (per source
class) runs against each tool's OCSF output and against a hand-verified reference
mapping; result divergence is scored as the operational cost of the fidelity loss.

## Stop rules / validity gates

- A tool scores only on sources where an official or vendor-published mapping exists;
  hand-written fills are reported separately (coverage ≠ fidelity).
- Mapping crash / refusal on a source = recorded as 0% coverage for that source, not
  excluded.
- Every fidelity number reports its denominator (populated source fields, not schema
  width).

## Predictions (pre-registered; probabilities committed before any run)

- **P1 (~70%)** Coverage ordering: Tenzir > Cribl > Vector on official-mapping
  availability across the four sources (Vector lacks shipped OCSF mappings for at
  least two).
- **P2 (~60%)** No tool exceeds 90% field fidelity on the EDR-shaped source (process
  trees and enrichment context are where mappings go to `unmapped`).
- **P3 (~65%)** Value-level damage (type coercion, timestamp precision/zone loss)
  appears in every tool on at least one source — the silent tier that field-level
  scoring misses.
- **P4 (~55%)** At least one of the five crosswalk failure classes reproduces in every
  tool's shipped mapping — i.e. the seams are OCSF's own, not tool bugs.
- **P5 (exploratory)** The query-panel divergence concentrates in hunt-shaped queries
  (group-by over enriched fields), not lookup-shaped ones — mirroring the
  detection-coarsening finding.

## Outputs

`results/RESULTS.md` (per-tool × per-source fidelity at three levels + the query-panel
divergence + P1–P5 scoring), the pinned corpus manifest, every mapping artifact used
(or its pinned upstream reference), and the reference mapping. Feeds: Matrix Component
4 ("OCSF normalization at-source" gets measured backing or measured caveats), the
what-your-data-means / six-schemas essays' tool-layer follow-up, and H-OCSF-related
hypothesis evidence (through the gate).

Single host (Beelink 5800H, WSL2 48 GB/14t), Tier B. What travels is ordering and the
failure classes; absolute percentages ride with the corpus caveat (seeded, four
sources, not your estate).

---

## Implementation note (appended 2026-06-13; pre-registration above is unchanged)

The harness is two files, plus the gold key already under `schemas/ocsf/`:

- `gen_corpus.py` — deterministic generator. Builds the four pinned source corpora
  (`_work/<source>.corpus.jsonl`, ~100k each, fixed seed off `../lib/common.py`
  `MASTER_SEED` / `BASE_EPOCH`, no wall clock) and the gold OCSF mapping per record
  (`_work/<source>.gold.jsonl`), then pins every file by sha256 in
  `_work/corpus_manifest.json`. `python gen_corpus.py --check` regenerates twice and
  asserts byte-identical (the determinism gate). The gold key is the hand-verified
  reference mapping: per source field it carries `{ocsf, status, value, note}` in the
  C1 `ocsf-mapping-fidelity` record shape — `status` is C1's typed/coerced/unmapped
  tier (the field-fidelity ceiling), `value` is the canonical OCSF value after a
  faithful coercion (the value-fidelity answer), and each record carries the OCSF
  class / `activity_id` / `type_uid` plus the five failure-class probes (the semantic
  answer). The four classes are Network Activity 4001 + Authentication 3002 (reused
  from the C1 subset) and API Activity 6003 + Process Activity 1007 (this bench's
  `schemas/ocsf/ocsf_1.8.0_ext_subset.json`).

- `score.py` — scorer. Merges the C1 subset and the ext subset, validates every gold
  OCSF target with C1's `resolve_ocsf_path` (an invented attribute fails the run),
  and scores a tool's emitted OCSF output field / value / semantic against the gold.
  `python score.py --self-check` scores the gold against a reference mapper built FROM
  the gold and asserts 100%/100%/100% — the harness's own correctness gate, no tool
  involved.

### Join contract

Each corpus row carries an explicit `_id` (a source-agnostic alias of the row's
natural id — `uid` for Zeek, `eventID` for CloudTrail, `ProcessGuid` for Sysmon,
`event_id` for auth). Each tool's mapping must carry `_id` through verbatim onto its
emitted OCSF event; `score.py` joins emitted→gold on `_id`. A source the tool
produced no output for (crash / refusal) scores 0% coverage for that source, not
excluded (README stop rule) — pass no `--emitted` for it, or an empty file.

### Where each tool's shipped mapping artifact plugs in

No pipeline tool is installed or run by this harness. For a scored run, each tool maps
`_work/<source>.corpus.jsonl` → OCSF 1.8.0 using its MOST OFFICIAL available mapping,
writes the emitted events (one per row, `_id` carried) to a JSONL file, and that file
is handed to `score.py --tool <name> --mapping-artifact "<pinned version>" --emitted
<source>=<file>`. The mapping artifact and its version are pinned into the result
(`--mapping-artifact`), so every number is version-bound.

- **Tenzir** — Tenzir's built-in OCSF mapping operators (`ocsf::*` / the `mapping`
  operators) in a TQL pipeline that reads each corpus JSONL and writes OCSF JSON.
  Plug in: the pipeline definition (`.tql`) + the Tenzir version. Tenzir ships the
  most OCSF mapping surface of the three (README P1: expect highest coverage).
- **Cribl** — Cribl Stream's published OCSF Pack (free tier). Plug in: the Pack
  version + the per-source Pipeline/Pack export that reads the corpus and emits OCSF.
  Run it through Cribl and capture the destination JSONL.
- **Vector** — VRL. Use a vendor-published OCSF VRL example where one exists for the
  source; otherwise a minimal hand-written `.vrl` labeled NON-OFFICIAL (coverage ≠
  fidelity — the hand-written fills are reported separately, README stop rule). Plug
  in: the `.vrl` transform (pin its commit/source) + the Vector version.

Per source the official-mapping availability differs (that is P1 itself), so a tool
with no official mapping for a source either gets a labeled hand-written fill or
scores that source 0% coverage — both are recorded, neither is hidden. The
`reference` tool name is reserved for the self-check (gold vs the gold-derived
reference mapper); it is the 100% control, not a fourth pipeline tool.

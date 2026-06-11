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

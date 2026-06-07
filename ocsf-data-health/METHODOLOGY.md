# Methodology

The point of this benchmark is to be falsifiable and reproducible, so the design
choices that determine the numbers are written down here rather than left in the
code. If a result looks too clean, the explanation is in this file, not in a tuned
query.

## Evidence tier

**Tier B** — reproducible, first-party, controlled measurement on a synthetic
estate. Not a production claim. The corpus is generated to isolate one mechanism:
how much true state a single tool recovers versus the cross-tool merge, and what
neither recovers. The honest reading of every headline number is "this is what the
mechanism does on an estate built to expose it," and the flaw models below are what
you have to accept for the numbers to mean anything.

## Determinism and integrity

There is no `datetime.now()`, no unseeded randomness, and no environment
dependence in the corpus generator. Every PRNG is a `random.Random` seeded off the
shared `MASTER_SEED = 20260601` in `../lib/common.py` (ground truth uses sub-seed
701, the observations 702), and "now" is a fixed day-of-year integer (158), not a
wall clock. `run.py` runs the full build-and-score twice in one process and asserts
the canonical JSON is byte-identical before publishing. It also runs an
**integrity check** on the planted ground truth before any tool observes it — row
count, contiguous unique ids, every attribute present and in-domain, and the
`is_managed`-determined-by-`kind` invariant the EDR coverage model relies on — so a
"gap" is always a tool flaw and never a corpus bug. Change the seed or the DuckDB
version and the structural results hold; the exact planted counts may shift.

This is a **correctness / coverage** benchmark, not a latency one. Every number is
an exact set cardinality over planted ground truth (correct cells / total cells),
so the `time_trials` coefficient-of-variation machinery in `lib/common.py` does not
apply here — there is nothing noisy to average. A cell is "recovered" only when the
chosen value *string* equals the planted true value string: no fuzzy matching, no
tolerance.

## The estate and its ground truth

20,000 assets, each with a `kind` drawn deterministically: ~62% workstations,
~18% servers, ~11% network gear, ~9% shadow-cloud. The kind governs visibility —
network gear and shadow-cloud assets are not managed endpoints, so EDR is blind to
them *by construction*, which is the point: the coverage gap is a structural
property of the estate, not a per-tool coin flip. Each asset has a true value for
seven attributes: `owner`, `business_criticality`, `os_version`, `ip_address`,
`last_seen`, `open_vuln_count`, `is_managed`. The 140,000 (asset, attribute) cells
are the denominator for every recovery rate.

## The four source tools — flaw models

Each tool emits observation rows `(asset_id, source, attribute, value,
observed_day, confidence)`. A tool that does not observe an asset emits no row for
it (a coverage gap). A tool reporting a stale value emits the value it last saw,
with an old `observed_day`, so the freshness term can demote it. `confidence` is
the source's self-reported trust *before* freshness decay.

- **CMDB — the system of record, confidently stale.** Authoritative *and* fresh on
  the slow-moving organisational attributes (`owner`, `business_criticality`,
  `is_managed`), which it reports correctly with high confidence. It is also the
  *named* system of record for the volatile inventory attributes (`os_version`,
  `ip_address`, `last_seen`) — and this is the trap: its values there are STALE,
  from a reconciliation weeks ago (`observed_day` 14–75 days back), so ~70–75% of
  them are now wrong. It reports them with moderate-high confidence (0.65) because a
  system of record is confident; freshness decay is what should override it. CMDB
  also MISSES shadow-cloud assets entirely (never onboarded).
- **EDR — fresh, but managed-only.** Fresh and high-confidence (0.90–0.95,
  observed today) on `os_version`, `ip_address`, `last_seen`, `is_managed`, but it
  covers ONLY managed endpoints — network gear and shadow-cloud are invisible (no
  agent). A small fraction (~7%) of managed endpoints have a dormant agent and
  report nothing this cycle.
- **VULN scanner — partial and cadence-stale.** Holds `open_vuln_count`, but only
  ~78% of assets are in the last scan window, and of those the count is current
  only if scanned within 7 days; older scans report a drifted prior count at lower
  confidence (0.55).
- **IDP — narrow but fresh.** Re-asserts `owner` for identity-bound assets (a ~55%
  subset of workstations), fresh and today. It demonstrates that a non-authority
  source can be the freshest reading on an attribute, though here owner is slow-
  moving so it rarely changes the answer — it mostly confirms CMDB.

## The four measures

1. **Single-tool recovery** — per tool: correct cells / 140,000. The
   `accuracy_where_reported` companion divides by the cells the tool actually
   observed, which separates staleness/authority error (EDR is 100% accurate where
   it reports; CMDB ~61% because of its stale inventory attributes) from pure
   coverage absence.
2. **Cross-tool best-context recovery** — for each (asset, attribute) the merge
   picks the observation with the highest **effective score** =
   `confidence × 0.5^((now − observed_day)/14)` (a 14-day-half-life freshness
   decay) plus a small `+0.05` authority bonus when the source is the named
   authority of record. Ties broken deterministically by source name. Correct
   cells / 140,000.
3. **Residual assurance gap** — `1 −` (cells where *some* tool reported the
   correct value) / 140,000. The cross-tool merge's ceiling is exactly this
   any-tool-correct figure, recorded alongside so the gap math is auditable: a
   merge can pick a correct value only if some tool holds one.
4. **The lever** — the scored merge versus a **naive baseline** that takes the
   named authority of record's value if present (else any source's, no freshness
   ranking). The gap between them is what the freshness/confidence score buys: the
   naive merge trusts the stale CMDB on the volatile attributes and lands far
   below the scored merge.

## Why the magnitudes come out where they do (and which are parameters)

The recovery numbers are functions of the estate composition and the flaw-model
windows, which are corpus *parameters*, not universal constants:

- The **best single tool ≈ 48%** is CMDB, because it is the only tool touching all
  seven attributes; its number is dragged down by its stale inventory attributes.
- The **cross-tool ≈ 76%** lift comes from EDR's fresh values displacing CMDB's
  stale ones on managed endpoints while CMDB's organisational attributes carry the
  rest — the union beats either alone.
- The **residual ≈ 24%** is dominated by `open_vuln_count` (only one partial,
  cadence-stale tool holds it) and by the unmanaged-asset rows that EDR can't see
  and CMDB is stale on. Widen scanner coverage or onboard shadow-cloud assets and
  the residual shrinks — which is exactly the remediation the gap measurement
  motivates.
- The **lever ≈ +25%** tracks how much of the estate sits on volatile attributes
  where the named authority is stale; move CMDB's staleness window toward fresh and
  the lever shrinks.

The **order**, not the magnitude, is the transferable finding: cross-tool > best
single tool, residual small-but-nonzero, scored merge > naive authority merge.

## What would falsify the thesis

The thesis is that true assurance lives in the cross-tool view — that the merge
recovers *materially* more than the best single tool, and that the freshness/
confidence score is what drives it. Three null results would falsify it, and each
is a real possible outcome on a differently-built estate:

1. **best-single ≈ cross-tool.** If one tool already covered the estate freshly and
   completely, the cross-tool join would add nothing and the "well-connected" claim
   would be weak — assurance would live in that one console. The benchmark returns a
   +27.9% gap because no planted tool has both full coverage and freshness, which is
   the empirical assumption the thesis makes about real estates, stated plainly
   rather than smuggled in.
2. **scored merge ≈ naive authority merge.** If trusting the system of record did
   as well as the freshness-ranked merge, the confidence/freshness score would not
   be the lever — authority alone would suffice. It returns +25.1% here only because
   the named authority (CMDB) is deliberately stale on the volatile attributes; an
   estate whose system of record is also its freshest source would return ~0 and
   falsify the "score is the lever" claim.
3. **residual ≈ 0.** If every cell were covered correctly by some tool, there would
   be no blind spot to sell a review against. The residual is nonzero here because
   the estate contains assets and attributes no tool covers freshly; an estate with
   redundant, fresh, total coverage would return ~0 and mean the assurance gap is
   already closed.

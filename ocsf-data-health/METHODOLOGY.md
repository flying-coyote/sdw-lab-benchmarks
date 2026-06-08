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
shared `MASTER_SEED = 20260601` in `../lib/common.py` (asset ground truth uses
sub-seed 701, the asset observations 702; identity ground truth 703, identity
observations 704), and "now" is a fixed day-of-year integer (158), not a wall
clock. `run.py` runs the full build-and-score twice in one process — and the
"full" payload now includes the v1 assets, the EXT-1 parameter sweep, and the
EXT-2 identities — and asserts the canonical JSON of the whole thing is
byte-identical before publishing, so the extensions are under the same determinism
guarantee as v1. It also runs an **integrity check** on each planted ground truth
before any tool observes it: for assets, row count, contiguous unique ids, every
attribute present and in-domain, and the `is_managed`-determined-by-`kind`
invariant the EDR coverage model relies on; for identities, the same plus
uniqueness of each key where present and consistency of the structural flags. A
"gap" is therefore always a tool flaw and never a corpus bug. Change the seed or
the DuckDB version and the structural results hold; the exact planted counts may
shift. The EXT-2 linker is deterministic too — its label propagation breaks ties
by min label over strings and runs to a fixed point — so the resolved clusters,
and therefore the contested-key recovery, reproduce bit-for-bit.

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

## Extension 1 — the parameter sweep (robustness of the order)

Because the magnitudes are parameters, a single point cannot show the *order* is
robust — it could be an artefact of the one tuning. EXT-1 sweeps the parameters
that drive the headline and recomputes all four measures at every grid point, so
the ordering claim is checked across the space rather than asserted at one point.

- The grid is **staleness × coverage**, 3×3 = 9 points. The **staleness-window**
  axis is a multiplier (×0.6 / ×1.0 / ×1.4) on how much of the CMDB's volatile
  inventory is stale — implemented by scaling the CMDB "still-correct"
  probabilities (`cmdb_os_fresh_p`, `cmdb_ip_fresh_p`) inversely, so a higher
  multiplier means a *more* stale system of record. The **coverage** axis is a
  single multiplier (×0.8 / ×1.0 / ×1.15) on every per-tool coverage fraction
  (EDR agent-present, scanner scan-window, IDP overlap), clamped to [0,1]. The
  CMDB shadow-cloud miss is structural and is left untouched.
- The same planted ground truth (seed 701) is scored at every point — only the
  observation flaw model and the scoring half-life change — so the sweep is a
  pure function of the grid and reproduces bit-for-bit. The v1 cell (×1.0, ×1.0)
  reproduces the v1 headline exactly, which is the cross-check that the
  parameterisation didn't perturb the base case.
- The **freshness half-life** is swept separately (7 / 14 / 28 / 90 days at v1
  staleness+coverage) rather than as a grid axis, because on this corpus it is
  **inert**: the fresh source (EDR) is also the higher-confidence one, so the
  freshness decay never flips a per-cell winner and the metrics do not move from
  7d to 90d. That is a genuine null and is reported as one — the lever on this
  estate is carried by the confidence+authority ordering, not by the decay rate.
  On a differently-built estate where the freshest source were the *lower*-
  confidence one, the half-life would bite; the code supports that case, this
  corpus just does not exhibit it, and overstating the axis would be dishonest.
- We report each metric's **min/max across the grid** (with the grid cell where
  the extreme occurs) and a boolean per ordering invariant, checked at *every*
  point: `cross_tool > best_single`, `residual > 0`, `scored_merge > naive`. The
  smallest margin on each (the weakest point in the grid) is reported alongside,
  so a near-inversion would be visible rather than averaged away.

## Extension 2 — identities with a contested join key

v1 assets share one clean key (`asset_id`) across every tool, so the cross-tool
merge is a clean equi-join and the only thing recovered is attribute truth.
Identity data is harder, and the difficulty is the *join itself*: tools key
identities on different, disagreeing columns, so the merge must first reconcile
which records are the same human — entity resolution — before it can merge their
attributes. EXT-2 plants a second entity type to measure that.

- **Ground truth.** 12,000 identities, each with five attributes (`department`,
  `title`, `manager`, `account_enabled`, `last_logon`) AND four true keys
  (`employee_id`, `email`, `upn`, `sAMAccountName`). The keys are derived from a
  stable per-person handle so they are unique where present and the person↔key
  mapping is exact. ~18% are not endpoint-bound (EDR cannot see them) and ~12%
  are legacy accounts with no `sAMAccountName`. An integrity check mirrors the
  asset one: contiguous unique ids, attributes present and in-domain, keys unique
  where present, structural flags consistent.
- **Tool key models (the contested join).** HR keys on `employee_id` (canonical,
  complete) and exposes an `email` that is a stale maiden-name address ~12% of the
  time — the join hazard, because HR's email will not match the IdP's current
  email. The IdP keys on the current `email` and exposes `upn` for ~85% (the only
  bridge to EDR). EDR keys on `upn` for endpoint-bound identities, and on `sam`
  for ~60% of those that have one. The directory keys on `sam` (absent on legacy
  accounts) and on `upn` for ~90%. No single column joins all four tools.
- **Two regimes, scored against the same planted truth.** The **clean-key
  oracle** merges attributes on the planted `person_id` — the asset-style clean
  join, the ceiling recovery if the key were never contested. The **contested-key**
  regime resolves identity from the key *values only* (the linker never reads
  `person_id`): it builds a graph whose nodes are tool-records and whose edges
  join two records exposing the same `(key_kind, key_value)`, takes the connected
  components by deterministic iterative label propagation (min-label to a fixed
  point), and merges attributes within each resolved cluster. Recovery is scored
  per *planted* person: each person is assigned to the cluster holding the
  plurality of its records, and a (person, attribute) cell counts only if that
  cluster's merged value matches truth. The denominator is the full planted estate
  (12,000 × 5 = 60,000 cells), so under-merge (a person split across clusters) and
  over-merge (a cluster mixing people) both cost recovery and the result can never
  exceed 100% — exactly one scored row per planted cell.
- **The resolution tax** is `clean_key_oracle − contested_key`: the part of the
  assurance gap that is *join*, not coverage. We also report a **naive single-key**
  baseline (join everything on `employee_id`, which only HR exposes — so every
  EDR/IdP/directory attribute is unjoinable), the join analogue of v1's naive
  authority merge, and resolution diagnostics (clusters resolved, over-merged
  clusters, fragmented people) so the failure mode behind the tax is legible.

The transferable finding mirrors v1's: the *order* survives a harder entity
(cross-tool still beats the naive single-key join), but contesting the join key
imposes a measurable recovery tax, so entity resolution is itself part of the
assurance gap rather than a solved precondition.

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

The two extensions add their own falsification conditions:

4. **the order inverts somewhere in the sweep (EXT-1).** The robustness claim is
   that cross-tool > best-single, residual > 0, and scored > naive hold at *every*
   grid point, not just at v1. If any cell inverted an ordering, EXT-1 would flag
   it (the `ordering_holds` booleans go False and the smallest-margin figures show
   how close the call was) and the "order is a property of the mechanism" claim
   would be weakened to "order holds in a sub-region." It does not invert anywhere
   in the 3×3 staleness×coverage grid here, with the smallest cross-minus-single
   margin at +19.4% and the smallest lever at +17.0% — but a wider or differently-
   centred grid is exactly where one should look for the inversion.

5. **resolution tax ≈ 0 (EXT-2).** The claim is that a contested join key degrades
   cross-tool recovery — that entity resolution is part of the gap. If the
   contested-key merge matched the clean-key oracle, the join would be free and the
   contested key would not matter; assurance would reduce to the asset case. It is
   −10.1% here because a fraction of identities cannot be linked across the tools
   that hold their attributes (the under-merge the diagnostics report). An estate
   whose tools all carried a shared, clean join key would return a ~0 tax and
   falsify the "entity resolution is part of the gap" claim — which is the honest
   boundary on how far the asset finding transfers to identities.

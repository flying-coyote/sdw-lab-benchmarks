# Results — cross-tool assurance gap (ocsf-data-health)

- DuckDB: `1.5.3`  
- Master seed: `20260601`  
- Determinism (two in-process runs byte-identical): **True**  
- Corpus integrity (planted truth internally consistent): **True**  
- Evidence tier: B (reproducible, first-party, controlled synthetic estate; exact set-based accuracy over planted ground truth; NOT production telemetry)

Synthetic estate of **20,000 assets x 7 attributes = 140,000 ground-truth cells**, observed through 4 source tools (191,835 observation rows). All numbers are exact set cardinalities over planted ground truth — this is a correctness/coverage benchmark, not a latency one, so there are no timings and no CV.

## Headline — the four measures

| measure | value |
|---|--:|
| **(1)** best *single* tool recovery (`cmdb`) | **47.7%** |
| **(2)** *cross-tool* best-context recovery | **75.6%** |
|     — cross-tool minus best single tool | **+27.9%** |
| **(3)** residual assurance gap (no tool correct) | **24.4%** |
| **(4)** lever gain (scored merge − naive authority merge) | **+25.1%** |

The cross-tool merge recovers **75.6%** of the estate's true state against the best single tool's **47.7%** — a **+27.9%** lift, the central thesis claim made measurable: *assurance lives in the cross-tool view*. The residual **24.4%** is the blind spot no tool covers correctly — the actual risk surface — and the merge tops out at its ceiling of 75.6% (any-tool-correct), which equals 100% − residual by construction.

## (1) Single-tool recovery — each tool's partial, flawed view

Recovery = correct cells / all true cells (coverage x freshness x authority). Accuracy-where-reported isolates staleness/authority error from pure absence.

| tool | correct cells | reported cells | recovery | accuracy where reported |
|---|--:|--:|--:|--:|
| cmdb | 66,747 | 109,470 | 47.7% | 61.0% |
| edr | 59,960 | 59,960 | 42.8% | 100.0% |
| vuln | 3,978 | 15,556 | 2.8% | 25.6% |
| idp | 6,849 | 6,849 | 4.9% | 100.0% |

No single tool clears half the estate's true state: each is authoritative on its own attributes and blind or stale elsewhere. CMDB knows owners but its network state is weeks stale; EDR is fresh but sees only managed endpoints; the scanner is partial and scan-cadence stale.

## (2)+(4) Where the cross-tool merge wins — per attribute

The merge picks, per (asset, attribute), the observation with the highest **freshness-decayed confidence + authority bonus** (14-day half-life). That score is the lever: a naive fixed-authority merge with no freshness scores **50.5%** overall, the scored merge **75.6%** (**+25.1%**).

| attribute | authority | best single tool | best-single recovery | cross-tool recovery | cross − best | residual gap |
|---|---|---|--:|--:|--:|--:|
| owner | cmdb | cmdb | 91.2% | 91.2% | +0.0% | 8.8% |
| business_criticality | cmdb | cmdb | 91.2% | 91.2% | +0.0% | 8.8% |
| os_version | cmdb | edr | 75.0% | 80.7% | +5.8% | 19.3% |
| ip_address | cmdb | edr | 75.0% | 80.1% | +5.2% | 19.9% |
| last_seen | cmdb | edr | 75.0% | 75.0% | +0.0% | 25.1% |
| open_vuln_count | vuln | vuln | 19.9% | 19.9% | +0.0% | 80.1% |
| is_managed | cmdb | cmdb | 91.2% | 91.2% | +0.0% | 8.8% |

Two different effects show up in this table, and they are worth keeping apart. The **cross − best-single** column is the lift from *combining* tools: it is positive on `os_version` and `ip_address`, where EDR covers managed endpoints the stale CMDB gets wrong AND CMDB covers the unmanaged assets EDR can't see, so the union beats either alone. The bigger story is the **lever** (the overall +25.1% of the scored merge over the naive authority merge above): on `os_version`, `ip_address`, and `last_seen` the named authority of record is the CMDB, but the CMDB is stale there, so a merge that just trusts the system of record picks the wrong value while the freshness-decayed score picks fresh EDR — that is why the naive merge lands at 50.5% and the scored merge at 75.6%. On `last_seen`, cross-tool equals best-single (EDR) because nothing else holds a fresh last_seen, yet the scored merge still beats the naive one by demoting CMDB's stale reading. On attributes only one tool ever holds (`open_vuln_count`), cross-tool = best single and the gain is residual coverage, not a merge effect — which is honest: the merge cannot invent coverage no tool has.

## (3) Residual assurance gap — the real blind spot

**34,126 of 140,000 cells (24.4%)** are reported correctly by *no* tool. That is the surface the four-layer data-health review exists to surface: an asset whose true state nothing in the stack actually holds — a shadow-cloud host no console onboarded, a network device EDR can't see and CMDB last touched weeks ago, a vuln count no recent scan covered. No merge recovers it; only adding a source that *covers* it can. Quantifying this gap is the deliverable the assurance engagement sells.

## (EXT-1) Parameter sweep — is the ORDER robust, not just the magnitude?

The v1 headline numbers are functions of the flaw-model parameters. We sweep the two that genuinely move them on this corpus — the **staleness window** (a multiplier on how much of the CMDB's volatile inventory is stale: ×0.6, ×1.0, ×1.4) and a **per-tool coverage** multiplier (×0.8, ×1.0, ×1.15) — across a 9-point grid, recomputing all four measures at every point. The transferable claim is the **order**, so what matters is whether it holds at every cell, not the v1 magnitude.

| metric | min (at) | max (at) |
|---|--:|--:|
| best-single recovery | 45.5% (stale×1.4, cov×0.8) | 52.1% (stale×0.6, cov×1.15) |
| cross-tool recovery | 69.4% (stale×1.4, cov×0.8) | 78.5% (stale×0.6, cov×1.15) |
| cross − best-single | 19.4% (stale×0.6, cov×0.8) | 31.9% (stale×1.4, cov×1.15) |
| residual gap | 21.5% (stale×0.6, cov×1.15) | 30.6% (stale×1.4, cov×0.8) |
| lever gain | 17.0% (stale×0.6, cov×0.8) | 28.6% (stale×1.4, cov×1.15) |

**Ordering invariants across all 9 grid points:**

- cross-tool recovery **>** best single tool: **True** (smallest margin in the grid: +19.4%)
- residual gap **> 0** (a blind spot always remains): **True**
- scored merge **>** naive authority merge (the lever is real): **True** (smallest lever in the grid: +17.0%)
- **all three hold at every grid point: True**

Per-point grid (each cell is a full rebuild + rescore of the same planted estate):

| staleness × | cov × | best-single | cross-tool | cross−best | residual | lever |
|--:|--:|--:|--:|--:|--:|--:|
| 0.6 | 0.8 | 52.1% | 71.5% | +19.4% | 28.5% | +17.0% |
| 0.6 | 1 | 52.0% | 76.4% | +24.3% | 23.6% | +21.4% |
| 0.6 | 1.15 | 52.1% | 78.5% | +26.4% | 21.5% | +23.0% |
| 1 | 0.8 | 47.4% | 70.0% | +22.5% | 30.0% | +20.1% |
| 1 | 1 | 47.7% | 75.6% | +27.9% | 24.4% | +25.1% |
| 1 | 1.15 | 47.5% | 78.0% | +30.4% | 22.1% | +27.0% |
| 1.4 | 0.8 | 45.5% | 69.4% | +23.9% | 30.6% | +21.5% |
| 1.4 | 1 | 45.6% | 75.3% | +29.8% | 24.7% | +26.7% |
| 1.4 | 1.15 | 45.9% | 77.8% | +31.9% | 22.2% | +28.6% |

The magnitudes move with the parameters exactly as the methodology predicts — more CMDB staleness drags best-single down and grows the lever, thinner coverage grows the residual — but the three orderings the thesis rests on do not invert anywhere in the grid. That is the point of sweeping rather than asserting at one tuned point: the headline 75.6% is a parameter-dependent number, but cross-tool > best-single is a property of the mechanism.

### Freshness half-life — a swept axis that turns out inert here (a null, reported)

We also swept the **freshness half-life** (how fast confidence decays) across 7, 14, 28, 90 days at v1 staleness and coverage. On this corpus it is **inert**: cross-tool recovery takes the distinct value(s) 75.6% and the lever +25.1% across the whole range. The reason is structural — the fresh source (EDR) is also the higher-confidence one, so freshness decay never flips a per-cell winner, and the lever is carried by the confidence+authority ordering rather than by the decay rate. That is worth stating plainly: on an estate where the freshest source were the *lower*-confidence one, the half-life would bite; here it does not, and pretending the axis moved would be the dishonest move.

## (EXT-2) Identities with a contested join key — entity resolution is part of the gap

v1 assets share one clean key (`asset_id`) across every tool, so the cross-tool merge is a clean equi-join. Identity data is harder: the four tools key on **different, disagreeing** columns (HR `employee_id`, IdP `email`, EDR `upn`, directory `sAMAccountName`), and no single column joins all four. The merge must first reconcile which records are the same human — entity resolution — before it can recover any attribute. We plant the true person↔key mapping (12,000 identities × 5 attributes = 60,000 cells), then score two regimes.

| regime | recovery |
|---|--:|
| **clean-key oracle** (merge on planted `person_id`, the asset-style join) | **96.3%** |
| **contested-key** (resolve from disagreeing key *values* only, then merge) | **86.2%** |
| **resolution tax** (oracle − contested) | **−10.1%** |
| naive single-key join (`employee_id` only — drops every non-HR tool) | 60.0% |

The clean-key oracle is the asset-style case: if the join key were never contested, the cross-tool merge recovers **96.3%** of the identity estate. The contested-key merge — which only ever sees the disagreeing key *values* and must link records by their transitive overlap before merging — recovers **86.2%**, a **−10.1%** entity-resolution tax. That tax is the part of the assurance gap that is *join*, not *coverage*: the same attributes are present, but a fraction of identities cannot be linked across the tools that hold them. The naive "just pick one join key" approach (`employee_id`, which only HR exposes) collapses to **60.0%**, because every EDR/IdP/directory attribute is simply unjoinable to it.

Resolution diagnostics (the linker never sees `person_id`; clusters come only from shared key values): **16,073** clusters resolved from **12,000** planted people that have any tool record; **0** clusters over-merged (mix >1 person), **3,770** people fragmented across >1 cluster (under-merge — the legacy accounts with no `sAMAccountName` and endpoints with no shared bridge key). Both failure modes cost recovery, and both are absent in the clean-key asset case — which is why identities are the harder, more realistic test.

## Honesty boundary

Tier B: reproducible, first-party, single-host, **synthetic**. The flaw models (CMDB staleness window, EDR coverage of managed-only, scanner cadence, IDP owner overlap; and for identities the per-key missing/garbled rates) are corpus *parameters*, not universal constants; the magnitudes move if you move them. The transferable, parameter-independent finding is the **order**: cross-tool recovery > best single tool, the residual gap is small but nonzero, and the freshness/confidence score is what produces the lift over a naive authority merge. EXT-1 demonstrates that order holds across a 3×3 parameter grid rather than at one tuned point; EXT-2 shows the order survives on a harder entity (identities) but at a measured entity-resolution cost, so a contested join key is itself part of the assurance gap. The benchmark does NOT show real-world magnitudes, a specific vendor's resolution accuracy, or that any particular linker is optimal — only that the mechanism's ordering is robust to the swept parameters and that contesting the join key degrades recovery by a measurable, non-trivial amount. See `METHODOLOGY.md` for the flaw models and the falsification conditions.


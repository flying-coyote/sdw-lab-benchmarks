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

## Honesty boundary

Tier B: reproducible, first-party, single-host, **synthetic**. The flaw models (CMDB staleness window, EDR coverage of managed-only, scanner cadence, IDP owner overlap) are corpus *parameters*, not universal constants; the magnitudes move if you move them. The transferable, parameter-independent finding is the **order**: cross-tool recovery > best single tool, the residual gap is small but nonzero, and the freshness/confidence score is what produces the lift over a naive authority merge. See `METHODOLOGY.md` for the flaw models and the falsification condition.


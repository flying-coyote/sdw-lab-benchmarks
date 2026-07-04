# RESULTS — EvidenceForge external-validity arm (2026-07-04)

Tier B, single independently-generated scenario corpus, single host, single run. Pre-registered:
[PRE-REG-evidenceforge-arm-2026-07-04.md](PRE-REG-evidenceforge-arm-2026-07-04.md). Harness:
[`evidenceforge-arm/normalize_to_ocsf.py`](evidenceforge-arm/normalize_to_ocsf.py) →
[`evidenceforge-arm/run_arm.py`](evidenceforge-arm/run_arm.py) →
[`evidenceforge-arm/results/results.json`](evidenceforge-arm/results/results.json). DuckDB 1.5.3,
pySigma 1.4.0 / pySigma-backend-sqlite 1.1.3 (compiled SQL checked byte-identical against the
1.3.3 backend the original arm's `requirements.txt` pins — no version-driven drift in the rules
under test). Deterministic given the corpus (re-running `normalize_to_ocsf.py` + `run_arm.py`
reproduced identical row counts and results.json byte-for-byte).

## Provenance

- **Corpus generator:** [EvidenceForge](https://github.com/cisco-talos) (Cisco Talos, MIT-licensed,
  public, unrelated to this bench) @ commit `7cbcc6a9`.
- **Scenario:** `scenarios/branch-office-example/scenario.yaml` — pinned copy at
  `evidenceforge-arm/scenario.pinned.yaml`. A 9-host mixed Windows/Linux branch office (5
  workstations, a domain controller, a file server, an explicit forward proxy, a DMZ web server),
  6-hour collection window, 6-step attack storyline plus one red-herring (a benign failed VPN
  logon).
- **Regeneration** (deterministic — internal seed 42 + the scenario's pinned `time_window`; no
  runtime `--seed` flag): `~/.local/bin/uv run eforge generate
  scenarios/branch-office-example/scenario.yaml -o <out> --force`.
- **EvidenceForge's own data-quality evaluation of the generated corpus:** overall **97.12/100**,
  **acceptance_passed=True**. This is the generator's own machine-scored quality gate, not an
  independent human practitioner's realism review — an important distinction the "what this changes"
  section below relies on.
- Corpus: 48,598 records, 19 sources, 10 hosts, ~30MB.

## Question

The original ocsf-sigma-detection arm (`run.py`) proved these 4 committed Sigma rules fire
correctly end-to-end over Store F — a corpus this bench's *own* generator built, with the rules'
literal field values (hostnames, IOC strings) authored with full knowledge of the corpus. That is
real evidence of round-trip correctness, but it cannot rule out that the rules and the corpus are
mutually fitted to each other. This arm re-runs the identical, unmodified rules over a corpus from
an independent generator that has never seen them, and scores hits against that generator's own
planted ground truth.

## Method

`normalize_to_ocsf.py` builds a minimal, rule-scoped OCSF store — only the fields the 4 committed
rules and the ground-truth join need, not a full crosswalk-fidelity instrument — using the same
table/column names Store F uses (`bench-a-context-collapse/stores.py`), so `run_arm.py` compiles and
executes the unmodified rules through the same pySigma sqlite backend `run.py` uses.

| table | class | source | rows | role |
|---|---|---|---|---|
| `network` | Network Activity (4001) | Zeek `conn.json` (single core-switch SPAN sensor) | 6,378 | scored (`rdp_lateral.yml`) |
| `dns` | DNS Activity (4003) | Zeek `dns.json` | 966 | scored (`c2_domain.yml`) |
| `process` | Process Activity (1007) | Sysmon EventID 1 + Windows Security EventID 4688, unioned across 7 Windows hosts, not deduplicated | 1,336 | scored (`encoded_powershell.yml`) |
| `api` | API Activity (6003) | cloudtrail — **no source exists** | 0 | scored (`nomfa_privesc.yml`) |
| `auth` | Authentication (3002) | Windows Security EventID 4624/4625 | 750 | supporting only |
| `http` | HTTP Activity (4002) | Squid explicit-proxy CONNECT log | 1,016 | supporting only |

Host/IP resolution is parsed from the pinned scenario's `environment.systems` list (9 hosts), not
hardcoded, so the normalizer and the pinned scenario cannot drift apart.

**Mapping decisions that involved judgment, not just field renaming:**

- **Process table is Windows-native-source only.** Sysmon EventID 1 (`CommandLine`, `Image`,
  `ParentImage`, `User`) and Windows Security EventID 4688 (`CommandLine`, `NewProcessName`,
  `ParentProcessName`, `SubjectUserName`) are unioned, not deduplicated — two sensors independently
  observing the same process creation is realistic dual EDR + native-audit-log visibility, not a
  double-count defect. The web tier's Linux recon (`id`, `ip addr`, `ss -tulpn` on WEB-BO-01) is out
  of scope for this table by design; none of the 4 rules queries a Linux-process shape.
- **The `api` table is empty by scenario design, not by mapping failure.** `branch-office-example`
  has no AWS/cloud activity at all — there is no cloudtrail-equivalent source anywhere in the
  corpus. `nomfa_privesc.yml` is architecturally untestable against this scenario; a 0/0 result here
  is a scope finding, distinct from a true negative on a populated table.
- **Proxy indirection changes which host the network sensor attributes traffic to.** The explicit
  forward proxy (`PROXY-BO-01`, 10.44.20.30) resolves DNS and holds the outbound TLS session on
  behalf of proxied clients, so Zeek's `dns`/`network` tables show `PROXY-BO-01` as the source for
  the C2 beacon, not `WS-NKAPOOR-01` (the actual compromised workstation, 10.44.10.24) — only
  `proxy_access.log` ties the traffic back to the real actor. `src_hostname` in `network`/`dns`
  therefore reflects sensor vantage, not necessarily the true origin host, for any proxied flow.
  This is carried through as-is rather than "fixed," because a real normalization pipeline hits the
  identical ambiguity.
- **Ground-truth join uses exact identity first, host+time-window as fallback.** Where the ground
  truth carries an explicit Zeek connection uid on a storyline event (evt-004's `rdp_session`), the
  harness treats that as the authoritative detection signal — the strongest join available, and the
  same one a real post-incident reconstruction would use if it had the identifier. Where no such id
  exists (evt-006's `beacon`), the harness falls back to a ±5-minute host+time-window join, the
  general mechanism the mission specified. The window is wide enough to also catch an unrelated,
  undocumented admin RDP session 155 seconds after the planted one — reported separately as a
  cross-check count, not folded into the primary detected/missed verdict.

## Results

| rule | planted target | result | matches | false positives | precision |
|---|---|---|---|---|---|
| `rdp_lateral.yml` (T1021.001, lateral movement) | evt-004 (RDP, FILE-BO-01) | **DETECTED** (exact-uid) | 138 | 137 | 0.0072 |
| `c2_domain.yml` (T1071.001, C2) | evt-006 (beacon, WS-NKAPOOR-01) | **MISSED** | 0 | 0 | — |
| `encoded_powershell.yml` (T1059.001, execution) | none planted | 0 firings (of 1,336 baseline) | 0 | 0 | — |
| `nomfa_privesc.yml` (T1098, priv-esc) | none planted | 0 firings (`api` table empty, 0/0) | 0 | 0 | — |

**1/2 planted-target detections.** `rdp_lateral.yml` catches the RDP session (the ground truth's
own Zeek uid, `CV2riwYnBazUAItUPk`, appears among the 138 rows a bare `dst_port=3389` check
matches); `c2_domain.yml` misses entirely.

**`c2_domain.yml`'s miss, corroborated:** the rule's hardcoded IOC (`cdn-telemetry-sync.net`) never
appears anywhere in this corpus — EvidenceForge's scenario resolves its own C2 beacon through
`northlakeportal.com` instead (hardcoded in the scenario source itself, confirmed, not an emergent
generation artifact). Independently checking the normalized store for that real domain (not gating
on the rule) finds it present and visible: 8 `dns` rows (source-resolved to `PROXY-BO-01`, the
proxy-indirection effect above) and 8 `http`/proxy CONNECT rows with actor `nina.kapoor` recovered.
So this is a **literal-string mismatch against a real, fully visible signal** — the rule missed
because it was written against one synthetic corpus's IOC and never generalized, not because the
beacon was invisible to the sensor or lost in normalization.

## Reading

The result this bench's own README already states plainly — Tier B, controlled measurements on
synthetic corpora — gets sharper, not softer, from this arm. `rdp_lateral.yml`'s detection survives
the swap to an independent generator because it is a structural rule (any RDP connection on the
standard port) that does not depend on any corpus-specific literal value; it pays for that
generality with the same precision problem the original Store F arm found (0.0072 here vs 0.0003 on
Store F — same order of noise, different corpus, same mechanism: a bare port check matches
everything on that port, planted or not). `c2_domain.yml`'s miss is the sharper finding: a rule
written as a literal IOC match is *by construction* corpus-specific, and this arm demonstrates that
concretely rather than asserting it — the same rule that fired at precision 1.0 on Store F (because
Store F's generator and the rule's author knew the same IOC) goes to 0/0 the moment the IOC string
changes, even though the underlying attack behavior (beaconing through an explicit proxy to a C2
domain) is present and fully recoverable in the new corpus under a different field value. That is
the honest shape of "detection-as-code portability": *structural* rules (port/operation/flag
checks) transfer across corpora; *literal-IOC* rules do not, and no amount of OCSF normalization
fixes that, because the mismatch is in the rule's own hardcoded string, not in the schema.
`encoded_powershell.yml` and `nomfa_privesc.yml` both correctly fire zero times, for two different
reasons worth keeping distinct: the former's two conditions (an IOC-style command flag and a
literal hostname) are both simply absent from this scenario, a clean true-negative-style result
against a 1,336-row baseline; the latter's `api` table has zero rows because this on-prem scenario
has no cloud telemetry class at all, so the rule is untested rather than tested-and-passing — a
distinction the 0/0 in the results table cannot carry on its own, and one this write-up is careful
not to blur.

## What this changes for the bench's Tier-A gate

This bench's sibling, `bench-a-context-collapse`, states its own Tier-A promotion condition
explicitly (`README.md`): "an independent practitioner confirming Store N's realism ... and **a
second corpus**." `ocsf-sigma-detection`'s README does not yet state an equivalent formal gate, but
the same house pattern applies, since these rules previously ran only against Store F — a corpus
built by this bench's own generator. This arm satisfies the **second-corpus** half of that pattern:
the 4 committed rules now have a measured result against a corpus authored by a party with no
knowledge of them. It does **not** satisfy the other half — EvidenceForge's 97.12/100 is a
machine-scored acceptance gate from the generator's own evaluator, not an independent human
practitioner's confirmation that the scenario is realistic. So this moves the bench from "one
corpus, self-authored" to "two corpora, one self-authored and one independently generated" —
real progress on external validity, worth stating precisely rather than rounding up to a Tier-A
claim neither corpus has earned yet.

## Limitations

Tier B: one scenario (`branch-office-example`, EvidenceForge's own beginner-friendly example, not a
stress case), one host, one run. The normalized store is a minimal, rule-scoped mapping built to
answer this arm's specific question — it is not a general-purpose Zeek/Sysmon/Windows-Security→OCSF
crosswalk-fidelity measurement (that instrument is `zeek-ocsf-crosswalk.md` / the
`ocsf-mapping-benchmark` skill's job). The ±5-minute host+time-window join tolerance is a judgment
call, not corpus-derived, and is documented as such in the pre-registration. The transferable
findings are the two mechanisms above — structural rules survive a corpus swap and pay for it in
precision; literal-IOC rules do not survive a corpus swap at all — not the specific match counts,
which are properties of this one scenario's background-noise volume.

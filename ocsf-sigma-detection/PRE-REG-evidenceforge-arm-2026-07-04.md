# PRE-REG — EvidenceForge external-validity arm (2026-07-04)

Frozen before running the scoring harness (`evidenceforge-arm/run_arm.py`). Tier B, single
independently-generated corpus, single host, single run.

## Question

C4 (sigma-portability) measured whether a Sigma rule compiles. The original ocsf-sigma-detection
arm (`run.py`, `RESULTS-*.md`) measured whether the same 4 committed rules *fire correctly* against
the synthetic BENCH-A testbed (Store F) — a corpus this bench's own generator built, with the rules'
literal field values (hostnames, IOC strings) chosen with full knowledge of what the rules query.
That is real evidence, but it cannot answer a narrower question: do these rules still fire when the
corpus comes from an **independent generator that had no knowledge of the rules**? This arm answers
that, using Cisco Talos' EvidenceForge (a public, MIT-licensed synthetic-log generator unrelated to
this bench) and its `branch-office-example` scenario as the external corpus.

## Corpus provenance

- Repo: `/home/jerem/EvidenceForge` @ commit `7cbcc6a9`.
- Scenario: `scenarios/branch-office-example/scenario.yaml` (pinned copy:
  `evidenceforge-arm/scenario.pinned.yaml`, with a provenance header; content otherwise unmodified).
- Regeneration command (deterministic — internal seed 42 + the scenario's own pinned
  `time_window`; no runtime `--seed` flag on this eforge version):
  `~/.local/bin/uv run eforge generate scenarios/branch-office-example/scenario.yaml -o <out> --force`
- EvidenceForge's own data-quality evaluation of the generated corpus: **overall 97.12/100,
  acceptance_passed=True**.
- Corpus stats: 48,598 records, 19 sources, 10 hosts, ~30MB, a 6-hour collection window
  (2024-05-14T12:00–18:00Z).
- Ground truth: `GROUND_TRUTH.json`, a 6-step storyline plus one red herring (rh-001, a benign
  failed VPN logon). The two steps this arm's rules target:
  - **evt-004** (index 3): "Attacker uses compromised admin credentials to RDP from the DMZ web
    server to the file server" — actor `nina.kapoor`, system `FILE-BO-01`, a single `rdp_session`
    event carrying an explicit Zeek connection uid (`CV2riwYnBazUAItUPk`), `dst_port` 3389 — the
    target for `rules/rdp_lateral.yml`.
  - **evt-006** (index 5): "Compromised admin workstation beacons through the explicit proxy to
    attacker infrastructure" — actor `nina.kapoor`, system `WS-NKAPOOR-01`, 8 beacon attempts over
    35 minutes to `45.83.221.30:443`, resolved via the domain **`northlakeportal.com`** (this is
    hardcoded in the scenario's own storyline definition, not an emergent artifact — see
    `scenario.pinned.yaml` line ~329) — the target for `rules/c2_domain.yml`.
  - `rules/encoded_powershell.yml` (checks `cmd_line` contains `-EncodedCommand` AND
    `device_hostname == 'WS1'`) and `rules/nomfa_privesc.yml` (checks
    `api_operation == 'AttachUserPolicy'` with no MFA) have **no planted storyline instance** in
    this scenario at all. Any firing is false-positive pressure by construction; zero firings is the
    structurally correct outcome, not evidence of anything positive about the rule.

## Method

`evidenceforge-arm/normalize_to_ocsf.py` builds a minimal, rule-scoped OCSF store (`network`,
`dns`, `process`, `api`, plus supporting `auth`/`http` tables — see the script's docstring for the
full field-by-field mapping and scope decisions) using the **same table and column names** Store F
uses (`bench-a-context-collapse/stores.py`), so `evidenceforge-arm/run_arm.py` compiles and executes
the identical 4 committed rules via the identical pySigma sqlite backend `run.py` uses, with no rule
or ground-truth edits. Hits are joined against `GROUND_TRUTH.json`'s storyline steps by host + a
±5-minute time window, falling back to an exact Zeek-uid match where the ground truth happens to
carry one (the strongest available join, and the same thing a real post-incident reconstruction
would use if it had that identifier).

## Frozen predictions

1. **`rdp_lateral.yml` (network, `dst_port=3389`) — MUST detect evt-004.** The rule is a bare
   `dst_port` equality check with no host qualifier, so it will match every port-3389 connection in
   the 6-hour Zeek `conn.json`, not only the planted one — background RDP scanning noise (external
   scanners hitting the DMZ's public IP, internal port-scan artifacts from evt-003, and ordinary
   admin RDP traffic) is expected to inflate the match count well past 1. Predict: **detected=True**
   (the planted uid `CV2riwYnBazUAItUPk` present in the match set), low precision (order
   0.01 or below — comparable in kind, not magnitude, to the original arm's 0.0003 on Store F).
2. **`c2_domain.yml` (dns, `query_hostname='cdn-telemetry-sync.net'`) — predict a MISS.** The
   rule's IOC string is a literal hardcoded value chosen for the BENCH-A synthetic corpus generator;
   EvidenceForge's `branch-office-example` scenario resolves its C2 beacon through a *different*
   hardcoded domain, `northlakeportal.com` (confirmed in the scenario source, not just the
   generated output). No string transform bridges the two. Predict: **detected=False, 0 matches** —
   this is the arm's headline external-validity finding, not a bug to fix. As a non-scoring
   corroboration, the harness will independently check whether the real beacon traffic (the
   `northlakeportal.com` queries and the proxy CONNECT log lines) is present in the normalized store
   at all, to distinguish "the rule missed a real, visible signal" from "the corpus has no signal to
   find" — predict corroboration will show the beacon traffic IS present, just under a different
   field value than the rule checks.
3. **`encoded_powershell.yml` (process) — predict 0 matches.** No process in this scenario uses
   `-EncodedCommand` (confirmed absent corpus-wide), and no host is literally named `WS1` (the
   corpus's Windows hosts are `WS-NKAPOOR-01` etc.) — both conjuncts fail independently, so the
   match count is 0 regardless of corpus volume. Report as false-positive pressure against the full
   process-table row count (predict on the order of ~1,300 rows, from Sysmon EventID 1 + Windows
   Security EventID 4688 across 7 Windows hosts).
4. **`nomfa_privesc.yml` (api/cloudtrail) — predict 0 matches, and an empty table.** This is an
   on-prem-only branch-office scenario with no AWS or cloud activity of any kind — predict the `api`
   table itself has 0 rows, which is a *scenario-scope* finding (the rule is architecturally
   untestable here) rather than a normalization failure or a clean true-negative measurement.

Net prediction: **1/2 planted-target detections** (rdp_lateral detects, c2_domain misses), with the
miss being the arm's substantive finding, not a defect.

## Falsifier (what would weaken this arm's design, not just change a number)

If `c2_domain.yml` **also matched** despite the literal-string mismatch, that would mean the
normalization layer is silently rewriting field values to make rules pass — a serious defect
undermining every other result in this bench, not a good outcome. Prediction: this does not happen.

Conversely, if `rdp_lateral.yml` **missed** evt-004 (the planted uid absent from the match set),
that would mean either the Zeek→network mapping dropped the connection, the join logic has a bug,
or the corpus doesn't actually contain the documented RDP session — any of which would need
debugging before this arm's results could be trusted at all. Prediction: this does not happen either
— the exact uid is expected to appear in a plain `dst_port=3389` scan.

## Known limitations (stated up front)

- **Single scenario, single run, single host.** `branch-office-example` is EvidenceForge's
  beginner-friendly example scenario, not a stress case; a harder scenario (more red herrings, more
  ambiguous field values) could easily change the qualitative texture of the miss/noise findings.
- **Minimal, rule-scoped mapping — not a full crosswalk-fidelity instrument.** This arm normalizes
  only the fields the 4 committed rules and the ground-truth join need. It is not a claim about how
  well Zeek/Sysmon/Windows-Security data maps to OCSF in general (that instrument is the
  `zeek-ocsf-crosswalk.md` / `ocsf-mapping-benchmark` skill's job, not this bench's).
- **Process normalization is Windows-native-source only by design.** Sysmon EventID 1 + Windows
  Security EventID 4688, unioned and NOT deduplicated across the 7 Windows hosts (dual EDR + native
  audit-log visibility of the same process is realistic, not a double-count bug). The web tier's
  Linux recon (`id`, `ip addr`, `ss -tulpn` on WEB-BO-01, evt-002/evt-003) is out of scope for the
  `process` table under this mapping — a scope decision, not a corpus gap.
- **Proxy indirection is a known, carried-through quirk, not an error.** The explicit forward proxy
  (`PROXY-BO-01`) resolves DNS and holds the outbound TLS session on behalf of proxied clients, so
  Zeek's network-sensor vantage shows `PROXY-BO-01` as the dns/network source for the beacon, not
  `WS-NKAPOOR-01` — only `proxy_access.log` ties the beacon back to the real actor/host. This affects
  the host+time-window join's host-resolution logic for `dns`, though it is moot here since
  `c2_domain.yml` misses on the literal string before host resolution matters.
- **The ±5-minute join window is a judgment call**, not derived from the corpus. It is wide enough
  to also catch a second, unrelated benign-looking RDP session from the same actor/host pair 155
  seconds after the planted one (this second session is not a documented storyline event, so it
  reads as ordinary admin RDP usage) — which is exactly why the harness prefers the exact Zeek-uid
  match when the ground truth supplies one, and reports the window-based hit count separately as a
  cross-check rather than as the primary detection signal.

## Actual vs predicted (recorded 2026-07-04 after the run)

- **`rdp_lateral.yml`:** PREDICTED detected=True via exact-uid, low precision — **MATCHED.** 138
  matches, exact-uid true positive = `CV2riwYnBazUAItUPk`, 137 false positives, precision 0.0072.
  The host+time-window cross-check independently found 2 hits (the planted session plus the
  unrelated 155-second-later admin RDP session noted above as a known limitation) — consistent with
  the prediction that window-only matching would be looser than the exact-uid join.
- **`c2_domain.yml`:** PREDICTED detected=False, 0 matches — **MATCHED exactly.** Corroboration
  confirms the real beacon traffic IS present in the normalized store: 8 `dns` rows for
  `northlakeportal.com` (source-resolved to `PROXY-BO-01`, confirming the proxy-indirection note)
  and 8 `http` (proxy CONNECT) rows for the same domain with actor `nina.kapoor` recovered — so the
  miss is a literal-string mismatch against a real, visible signal, exactly as predicted, not a
  normalization gap.
- **`encoded_powershell.yml`:** PREDICTED 0 matches — **MATCHED.** Process table built to 1,336 rows
  (668 Sysmon EventID 1 + 668 Windows Security 4688 across the 7 Windows hosts); 0 firings against
  that baseline.
- **`nomfa_privesc.yml`:** PREDICTED 0 matches, empty `api` table — **MATCHED.** The `api` table has
  0 rows; this scenario has no cloud/AWS activity at all.
- **Falsifier:** did NOT fire in either direction — no silent rewrite let `c2_domain.yml` pass, and
  `rdp_lateral.yml` did not miss its planted target. Net: **1/2 planted-target detections**, exactly
  as predicted, with the `c2_domain.yml` miss standing as the arm's substantive external-validity
  finding rather than a defect requiring a fix. No rule or ground-truth value was altered to force
  a different outcome.

Full numbers, method detail, and the honest caveats for what this does and does not move: see
[RESULTS-evidenceforge-arm-2026-07-04.md](RESULTS-evidenceforge-arm-2026-07-04.md).

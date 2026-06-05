# Corpus generation plan

This documents how `generate.py` builds the testbed: the source shapes, the
volumes, the identity and asset models, the planted-chain timing, and how each
planted needle maps to the adversary-tail query it has to support. It is the
data-generation half of the BENCH-A pre-registration (frozen 2026-05-31, in
`splunk-db-connect-benchmark/workloads/ocsf-context-collapse/`); the queries,
metrics, and ground-truth *requirements* are fixed there and I implement them here.

## Design constraints I'm working under

Two constraints shape every choice below. First, the corpus and its ground truth
are pre-registered, so generating them is not a degree of freedom I get to tune
after seeing a store; the planted chain follows the §2 table of the query battery,
not my own preference. Second, the two normalized stores (Phase 2) are built *blind*
to the query set, so I keep the raw streams in their native, pre-OCSF shape here and
defer every normalization decision to Phase 2, where Store N's coarsening has to come
from a documented real-world pipeline default rather than from what would make a
query fail.

## Determinism

Every value is a pure function of `MASTER_SEED` (20260601) via
`lib.common.new_rng`, with timestamps anchored on `BASE_EPOCH` (2026-01-01Z), and
no `datetime.now()` or unseeded randomness anywhere. Each source draws from its own sub-seed so
the streams are independent but still fully determined by the one constant.
`generate.py` builds the corpus twice and asserts an order-independent fingerprint
(a commutative sum of per-record SHA-256 over canonical JSON) is identical before it
writes anything. The fingerprint is absence-sensitive: the no-MFA needle's omitted
key changes the digest distinctly from an explicit `false`, so a regression that
silently filled the absence in would change the fingerprint and fail the check.

## Sources and background volumes (full scale)

Roughly 177k events over a 14-day window. The background exists to give the routine
queries real tallies and to hide the needles; the volumes are sized to be meaningful
without making the corpus large.

| Source | native shape | ~count | supports |
|---|---|---|---|
| `okta_auth` | sign-in events (user, src_country, outcome) | 27k | R1 (auth per user/day), R3 (failed by country) |
| `okta_session` | sessions with `start_time`/`end_time` | 4k | A4 (point-in-time validity) |
| `zeek_conn` | conn.log (orig/resp, port, bytes, duration) | 60k | R2 (top dst ports), R4 (egress per host/day) |
| `zeek_dns` | dns.log (query, qtype, answer) | 18k | A8 (first-seen domain) background |
| `sysmon_process` | process-creation (image, cmdline, SID, parent) | 40k | R5 (top images) |
| `cloudtrail` | API events (event_source, event_name, principal, mfa) | 28k | R6 (API volume by service) |

The failure profile in `okta_auth` is deliberately uneven across countries (RU/NG/CN
carry higher failure rates) so R3 has structure rather than a flat distribution.
Destination ports in `zeek_conn` are weighted so 443/80 dominate and R2 has genuine
heavy hitters. Both are background texture, not needles.

## Identity and asset models

One human carries the chain. The point of A5 (identity closure) and A9
(asset-identity collapse) is that this single actor wears a different identifier in
every source, and each physical machine appears under three:

- **Human** `h_jdoe` → endpoint SID `S-1-5-21-…-1107`, account `ACME\jdoe`, UPN
  `jdoe@acme.example`, IAM principal `arn:aws:iam::…:user/jdoe`, assumed-role
  `arn:aws:sts::…:assumed-role/AdminRole/jdoe-session`.
- **WS1** → hostname `WS1` (EDR), IP `10.10.1.21` (NDR), instance-id `i-0a1b…` (cloud).
- **WS2** → hostname `WS2`, IP `10.10.1.22`, instance-id `i-0e4f…`.

`truth_identity_links` records the full set; the A9 distinct-asset truth is **2** (two
machines), even though they surface under six identifiers, so a store that flattens
asset identity over- or under-counts, and that is the degradation A9 measures.

## The planted chain

Six stages on the middle day, anchored at `t0` = 10:00:00Z. Offsets are the true
event-time; the table also names the needle the generator flags and the query that
needle has to support.

| Stage | t0+ | source | needle (`_needle_id`) | serves |
|---|---|---|---|---|
| 0 initial access (T1566/T1528) | 0 | cloudtrail | `stage0_oauth` (GetSessionToken) | A3 order |
| 1 execution (T1059.001) | 5m | sysmon | `stage1_powershell` — `-EncodedCommand`, parent winword.exe, WS1 | **A2**, A3 |
| 2 C2 beacon (T1071/T1568) | 8–68m | zeek_conn + dns | `stage2_beacon` ×60 (~60s, low-byte) + `stage2_c2_dns` | **A1**, **A8**, A3 |
| — late arrival | 30m (ingest +60m) | sysmon | `late_arrival` (buffered offline agent) | **A10** |
| 3 lateral movement (T1021) | 70m | okta_auth + zeek_conn | `stage3_lateral_auth`, `stage3_lateral_conn` (WS1→WS2:3389) | A3, **A7** |
| 4 priv-esc no-MFA (T1098) | 80m | cloudtrail | `stage4_nomfa` — AttachUserPolicy, `mfaAuthenticated` **absent** | **A6** |
| 5 identity pivot (T1078) | 90m | cloudtrail | `stage5_assumerole` (same human, assumed role) | **A5** |
| 6 exfil (T1530) | 100m | cloudtrail | `stage6_exfil` ×30 (GetObject burst, sensitive bucket) | A3 |
| — point-in-time | 13:30–14:30Z | okta_session | `pit_session` (active at 14:03:00Z) | **A4** |

A few needles are mechanism-specific rather than stage-specific. The late-arrival
event (A10, *time*) has its true `event_time` inside the chain but an ingestion time
~60 minutes later, so a store that keys on ingestion time misclassifies its window.
The no-MFA event (A6, *structural*) omits the `mfaAuthenticated` key entirely, and
absence is a distinct state from `false`: 885 background `AttachUserPolicy`
events do carry the field, so the absence is the signal. The point-in-time session
(A4, *time*) spans 14:03:00Z; `truth_needles.pit_active_session_uids` is computed over
the full session set after assembly, so the validity answer is exact.

## Ground-truth artifacts

`_work/ground_truth.json` carries the three artifacts the pre-registration names:

- `truth_event_order` — the seven stages in true event-time order (A3 ordering τ).
- `truth_identity_links` — human ↔ SID ↔ account ↔ UPN ↔ principal ↔ role, plus the
  two assets and their three-identifier aliases (A5/A9).
- `truth_needles` — the per-query needle sets: the 60 beacon conn UIDs (A1), the
  PowerShell process UID and exact encoded string (A2), the no-MFA event UID (A6), the
  30 exfil UIDs, the late-arrival UID with its event/ingest times (A10), the C2 domain
  and first-seen time (A8), the dwell seconds (A7), the distinct-asset count (A9), and
  the active-session set at the point-in-time instant (A4).

The routine queries (R1–R6) have no pre-baked truth; their ground truth is a corpus
tally, derived from the fidelity store at score time in Phase 3, because the whole
expectation is that a coarse store *also* tallies them correctly (R1/R4/R6 are exactly
what pre-aggregation is designed to serve). If Store N degrades the routine set, the
comparison is contaminated and the run voids per the pre-registration.

## Native shape and the JSONL/Parquet split

The canonical raw is the per-source JSONL, because it preserves native structure
including genuine key-absence (the no-MFA needle). The Parquet materialization is a
convenience for the query phases; a typed Parquet column cannot represent
absent-vs-null, which is itself part of what Store N loses and Store F keeps, so
Phase 2 reads the JSONL when building Store F's structural fidelity. Type inference on
the JSONL uses `sample_size=-1` so the sparse needle columns (null until the mid-corpus
chain) are typed as VARCHAR over the whole file rather than from the first 20k rows.

## Evidence tier

The corpus is a synthetic, controlled testbed, Tier B by construction like the rest
of the Lab. Its ground truth is exact (I planted it), but its external validity is
bounded by how representative one APT29-style chain is, which is why BENCH-A's Tier-A
promotion is gated on an independent practitioner (Jake Thomas / Hunter Madison)
confirming that Store N's coarsening resembles what shops actually build. That sign-off
is a Phase-2 gate and Jeremy's to obtain; the synthetic result stands at Tier B until
then, and the write-up says so in the headline rather than a footnote.

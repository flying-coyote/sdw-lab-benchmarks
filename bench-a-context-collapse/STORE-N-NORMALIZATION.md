# Store N normalization — the documented default (and why it isn't a strawman)

BENCH-A measures one thing: the difference between two OCSF stores built from the same
corpus. The whole result rests on Store N being a *fair* coarse store, the kind a real
pipeline produces under cost pressure, rather than one I crippled to fail the adversary
queries. So every coarsening choice in `stores.py` is written down here with the
real-world practice it stands for, and the result carries the honest caveat that
"documented by me" is not "reviewed by a practitioner" — that sign-off is the Tier-A
gate, below.

The test that the default is fair is the routine control: R1–R6 (counts, top-N, egress
rollups) come back from Store N identical to Store F (Δ-routine = 0.000 in the results).
A store that broke those too would be a strawman, and the run would void. Store N breaks
the adversary queries while leaving the routine ones intact, which is the signature of
real volume-reduction, not of deliberate sabotage.

## The choices, and their basis

Each choice is a standard volume- or cost-driven normalization that exists independent
of the query set. The evidence tier on each is C/B — these are practitioner patterns and
documented pipeline behaviors, not peer-reviewed results, and they are cited as the
*basis for a plausible default*, not as proof that every shop does exactly this.

- **One time field, populated from ingestion.** Store N keeps a single `time`, set to the
  ingestion timestamp, and drops event/processed/valid time. Indexing on receipt time is
  the long-standing SIEM default (it is what makes "search the last 15 minutes" mean
  *arrived* in the last 15 minutes), and OCSF's four time types (`time`,
  `metadata.logged_time`, `metadata.processed_time`, validity) are mostly recommended or
  optional, so a cost-driven pipeline populates one. This is what breaks the buffered
  late-arrival (A10) and removes point-in-time validity (A4). *Tier C — practitioner default.*
- **Network rolled to 5-minute flows.** Connections are aggregated per (src, dst, port)
  into 5-minute windows, summing bytes (kept directional, so egress stays answerable) and
  counting flows. Flow-level rollup is the standard way to keep network telemetry
  affordable at volume; netflow/IPFIX and most SIEM network models are already
  flow-aggregated rather than per-packet/per-connection. This destroys the ~60-second
  beacon inter-arrival (A1) without touching the byte totals R2/R4 need. *Tier B —
  established network-telemetry practice.*
- **Identity flattened to one `user_uid`.** Store N keeps a single best-available
  identity string per event (the endpoint SID on process events, the principal on cloud
  events, the UPN on auth) with no per-domain tags and no resolution layer. Flattening
  identity to one field for join convenience, absent a dedicated identity-resolution
  step, is a common normalization shortcut. It is what makes cross-source identity
  closure (A5) and asset-alias resolution (A9) unrecoverable, because the SID, the UPN,
  the principal, and the assumed-role no longer link. *Tier C — practitioner default.*
- **Command line truncated.** `cmd_line` is cut to 64 characters. Field-length caps on
  high-cardinality string fields are a routine ingest-cost control; the encoded PowerShell
  payload (A2) lives past the cap and is gone. *Tier C — practitioner default.*
- **MFA-absence coerced to false.** An absent `mfaAuthenticated` becomes `is_mfa = false`,
  indistinguishable from a genuine `false`. Coalescing missing booleans to a default on
  write is a near-universal schema-on-write convenience, and it is exactly what collapses
  "MFA field was absent" into "MFA was false" — the structural loss behind A6. *Tier B —
  this absence/null/false collapse is the documented OCSF context-collapse failure mode.*
- **Rare DNS sampled out.** DNS queries seen fewer than three times in the window are
  dropped under a cardinality/tail-sampling rule. High-cardinality DNS is a common target
  for sampling or aggregation to control volume; the singleton C2 resolution (A8) is
  exactly the rare record such a rule discards. *Tier C — practitioner default.*
- **Device recorded as the source-native identifier.** Store N keeps whatever identifier
  each source emits (hostname from EDR, IP from NDR) with no asset resolution, so one
  machine surfaces under two keys. Storing the native device field without a CMDB join is
  the default when asset resolution isn't wired in; it is what inflates the distinct-asset
  count in A9. *Tier C — practitioner default.*

Store F is the counterpart: atomic grain, all four time types, the per-domain identity
tags retained, an asset-inventory observable for resolution, command lines and raw kept,
and absence preserved through a `mfa_present` flag. The cost of that fidelity is measured
and reported in RESULTS.md (it is larger on disk), so the gap-recovery is weighed against
the price.

## The blind-to-queries discipline

I wrote both the corpus and the query battery, which is the obvious place for bias to
enter, so the guardrails are: the query battery was frozen first (2026-05-31, in the
private benchmark repo), the choices above each name a practice that exists regardless of
my queries, and the routine control proves Store N isn't sabotaged. None of that fully
removes my thumb from the scale — it bounds it.

## Tier-A gate

This is the gate the pre-registration names and the one piece I cannot supply myself: an
independent practitioner (Jake Thomas / Hunter Madison) confirming that Store N's
coarsening resembles what shops actually build. Until that sign-off, the result is Tier B
and the write-up says so in the headline, not a footnote. Getting the sign-off is
Jeremy's outward step, and it is what would move the finding from "a defensible synthetic
contrast" to "a reviewed one."

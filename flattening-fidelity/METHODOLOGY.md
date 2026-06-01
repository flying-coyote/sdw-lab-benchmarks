# Methodology

The point of this benchmark is to be falsifiable and reproducible, so the design
choices that determine the numbers are written down here rather than buried in the
code. If a result looks too clean, the explanation is in this file, not in a
tuned query.

## Evidence tier

**Tier B** — reproducible, first-party, controlled measurement on a synthetic
corpus. Not a production claim. The corpora are generated to isolate one mechanism
at a time; each is a controlled experiment, not a sample of real telemetry. The
honest reading of every headline number is "this is what the mechanism does on a
corpus built to expose it," and the corpus design below is what you have to accept
for the number to mean anything.

## Determinism

There is no `datetime.now()`, no unseeded randomness, and no environment
dependence in any corpus generator. Every PRNG is a `random.Random` seeded off a
single `MASTER_SEED = 20260601` (`benchmarks/common.py`), and all synthetic
timestamps derive from a fixed epoch anchor. `run.py` runs the full suite twice in
one process and asserts the canonical JSON is byte-identical before publishing,
and two separate processes reproduced the same results digest (`4e201f70464eeacb`,
DuckDB 1.5.3). Change the seed or the DuckDB version and the structural results
hold; the exact planted counts may shift.

## The two-store pattern

Every mode builds two tables from the same generated events:

- a **lossy** store — the schema a cost-pressured pipeline actually produces
  (flattened columns where absence becomes NULL; a coarse `(src, dst, 5-min)`
  rollup; zone-naive local timestamps), and
- a **preserved** store — atomic grain, queryable nested structure, true UTC.

The *same* detection logic runs against both, and both are scored against a
ground truth that is known because we planted it. The preserved store stands in
for **Iceberg V3 Variant** (mode 1) and for keeping raw atomic telemetry hot
(modes 2–3); DuckDB's JSON functions and in-memory tables are the local,
reproducible analog, not the production target.

## Mode 1 — absence-vs-NULL collapse

**Corpus.** CloudTrail-shaped events. Each is a privilege-escalation API call
(`AttachUserPolicy`, `PutUserPolicy`, `AddUserToGroup`) or a benign call. MFA is
encoded the way CloudTrail actually encodes it:
`userIdentity.sessionContext.attributes.mfaAuthenticated` is present with value
`"true"` only when MFA was used, and **absent entirely** when it was not.

**Ground truth.** A planted positive is a privilege-escalation call made without
MFA — exactly what the SOC 2 detection is meant to catch.

**Lossy store.** The flattening ETL lowers the nested key to a column; absence
becomes NULL.

**Queries.** (a) naive flattened `WHERE mfa = 'false'` — the bug; (b) NULL-aware
flattened `WHERE mfa != 'true' OR mfa IS NULL`; (c) preserved JSON
`WHERE json_extract_string(..., 'mfaAuthenticated') IS NULL`.

**Why the result is 100%, and why that is honest.** The naive query recovering
zero is not a probability that happened to round to zero. Once the column is
flattened, "absent" and "NULL" are the same byte, and a present value is the
string `'true'`, so `= 'false'` has nothing in the column to match — at any
corpus size. This is the one result that is structural rather than
corpus-parameter-dependent.

## Mode 2 — grain loss

**Corpus.** Network connections over one hour. Three populations:

- **beacons** — a `(src, dst)` pair sending one connection every 60 seconds
  (5 per 5-minute bucket), 43-byte payload. Malicious; the ground truth.
- **decoys** — the *same* 5 connections per bucket and the *same* 43-byte
  payload, but clustered into the first ~40 seconds of each bucket (bursty).
  Benign. Identical to a beacon in everything the rollup keeps.
- **noise** — low-volume, irregular pairs the detectors should ignore.

Beacons and decoys deliberately share volume and payload so the **only**
discriminating feature is inter-arrival timing. That isolates the grain
mechanism: timing is the one thing the rollup destroys.

**Lossy store.** `GROUP BY src, dst, (t // 300)` → per-bucket count and byte
aggregates. Individual event times do not survive.

**Adversary query (beacon hunt).** Atomic grain computes inter-arrival jitter
directly (`stddev(gap)/mean(gap) < 0.05`) and separates beacons from decoys
cleanly (F1 1.00). Coarse grain has no event times, so the fair-effort detector
keys on steadiness of per-bucket counts — and a 60s beacon and a bursty decoy
both produce a steady 5/bucket, so every decoy is flagged as a false positive.

**Routine queries.** Bytes-per-host and per-`(src,dst)` connection counts, which
the rollup reconstructs exactly (asserted equal to the atomic answer, row for
row).

**The corpus-parameter caveat.** Coarse-grain recall stays 1.0 (it still flags
the beacons); the loss shows up as precision, which equals
`beacons / (beacons + decoys)`. At the planted 1:2 beacon:decoy ratio that is
0.333, giving F1 0.50 and an adversary-minus-routine headline of 0.50. **That
magnitude is a function of the decoy ratio I chose, not a universal constant.**
The ratio-independent finding is the qualitative one: atomic grain separates the
two perfectly and coarse grain cannot separate them at all, because the
discriminating feature no longer exists in the schema. The routine half is exact
regardless.

## Mode 3 — floating timestamps

**Corpus.** Cross-source chains of three events (EDR → firewall → auth) whose true
UTC times are 45–240 seconds apart — well inside a 5-minute window. Each source is
assigned a real timezone (UTC, Frankfurt +1, Virginia −5, Singapore +8). A
configurable fraction of chains are cross-zone (sources in different zones); the
rest are same-zone.

**Stores.** *floating* keeps each event's local wall-clock with the offset dropped
and compares them as if co-zoned; *utc* keeps the true UTC instant.

**Query.** For each chain, do all three events fall within a 5-minute window, and
does sorting by the stored time reproduce the true order?

**Result and its caveat.** UTC correlates and orders every chain (recall 1.00).
The floating store loses exactly the cross-zone chains — hour-scale offsets push
their events hours apart, outside the window — so floating recall tracks the
same-zone fraction (~0.46–0.50 at a 50% cross-zone mix). **That recall is a
function of the cross-zone fraction, not a universal constant.** Because the
offsets here are hour-scale, the cross-zone chains miss the window entirely rather
than reorder inside it, so order-accuracy among correlated chains stays 1.0; the
"plausible but wrong order" failure the essay also describes needs sub-window
(15–30 minute, half-hour-zone) offsets and is left as a qualitative point rather
than a quantified one here.

## What would falsify the thesis

The essay's grain/time argument is that the loss falls *disproportionately* on
adversary-relevant queries. The null result — a near-zero adversary-minus-routine
gap — is a real possible outcome and would mean the loss is uniform, or that a
well-built pipeline avoids it. Mode 1 cannot return the null (it is structural).
Modes 2 and 3 could, on a corpus where the adversary query does not depend on the
discarded dimension; they return a gap here because the planted adversary queries
depend on exactly the timing and zone information the lossy stores drop, which is
the mechanism under test stated plainly rather than smuggled in.

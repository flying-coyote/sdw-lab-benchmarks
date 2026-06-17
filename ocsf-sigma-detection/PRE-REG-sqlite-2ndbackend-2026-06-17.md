# Pre-registration — SIGMA-EXEC second-backend execution (SQLite), H-SIGMA-01

_Frozen before the run (M6 / Platt strong inference). Loop iter 3, 2026-06-17._

**Assumption under test:** is PPL's silent correlation-window drop a **PPL-plugin-specific quirk**
(H-SIGMA-01's Alternative: a maturity artifact of one backend) or a **cross-backend pattern** (the
hypothesis: backends silently degrade correlation semantics, and a green compile is not a portable
detection)? The compile leg found the **pySigma SQLite backend compiles `event_count` correlation
WINDOWLESS** (`… GROUP BY src_ip HAVING event_count >= 10`, the `timespan: 10m` dropped) — a second,
architecturally different engine (file-based SQL, not OpenSearch) that drops the window at compile. This
leg EXECUTES it to confirm the over-fire at runtime, mirroring the PPL execution leg exactly (same
`gen_corpus`, same scoring).

**Predicted result:** the SQLite-backend-emitted windowless SQL **over-fires** — flags all 50 decoy
actor_users (≥10 failures EVER but never ≥10 in a 10-min bucket) plus the 20 true bursts, precision ≈
20/70 ≈ 0.29, recall 1.0; the correct windowed SQL (group by actor_user + a 10-min bucket) flags only the
20. Same shape as the PPL leg (0.286 / 50-decoy-FP). value_count expected to compile windowless too;
temporal_ordered may refuse (record either way).

**Predicted confidence delta:** H-SIGMA-01 **2.5/5 → 3/5** — the gated sub-condition "execution on one
OTHER backend" is met, and the result removes the "single-backend (PPL), n=1" gate: the silent window-drop
is now demonstrated at execution on **two** architecturally distinct backends (OpenSearch PPL + SQLite),
which is the cross-backend-structural claim, not a PPL quirk. (Capped at 3/5: still synthetic planted
corpus, the corpus-design-dependent over-fire *rate* is not the transferable claim — the mechanism is —
and the newer-pySigma maturity sub-condition stays open.)

**Falsifier (what would keep it at 2.5/5 or refute the cross-backend claim):** if the SQLite backend had
**refused** the correlation loud (like Lucene/ES|QL) or compiled it **with** a correct window, the
silent-drop would be PPL-specific and the cross-backend claim fails. (The compile probe already shows
windowless, so the falsifier is not expected to trigger; the execution confirms the over-fire is real, not
just a compile artifact.)

**Guard (anti-Goodhart):** the over-fire *rate* tracks the planted 50:20 decoy:true ratio — do NOT report
the rate as a transferable number; the transferable claim is the **mechanism** (windowless compile →
runtime over-fire) reproduced on a second backend. n=1 corpus shape, single host, Tier B.

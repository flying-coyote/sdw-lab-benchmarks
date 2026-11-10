---
type: benchmark-verification
area: T4-interdiction
date: 2026-11-09
verdict: VERIFIED-WITH-FIXES
---

# Verification: T4 interdiction

**Verdict: VERIFIED-WITH-FIXES.** Every measured number reproduces exactly. Two fresh full runs of `run.py` on a
copy of the scripts regenerated all three corpora with byte-identical `truth.json` hashes and wrote a
`results/interdiction.json` whose sha256 matches the original (`d35b492845742f68d95c9e9993010e68f0b36ac05ec1238a3476c33794da7c5d`),
so the run is fully deterministic and every per-slot state, recall, precision and FP range in `RESULTS.md` holds.
The pre-registration predates the corpus, rules and run, and its hash is unchanged. Five claims in `RESULTS.md`
were corrected or scoped in place (marked as verifier edits), the largest being that the burn-down's
*marginal*-step column does not credit all 22 rule slots: 14 are marginal and 8 are reach-only. No state, count or
hypothesis verdict changes. Pre-fix copy: `verification/RESULTS.pre-verification.md`.

## What was checked and how

Same machine as the original (Beelink, WSL2 6.6.87.2, 14 vCPU), the bench's own `.venv`, run as
`taskset -c 4-7 nice -n 10 .venv/bin/python -I run.py` from `verification/rerun/` (copies of the scripts and
rules; `verification/atlas-ocsf-observables` is a symlink so `ocsf_fields.py` resolves the same OCSF 1.9.0 dump).
Other benches were running (load 8.7 to 13), so verify timings were also **taken under contention**; per-seed
totals were 93 to 106 s against the original 104 to 210 s, and neither is a latency claim. I used cores 4-7 rather
than 0-3; the output is deterministic, so this cannot change a result.

| Check | Command / artefact | Result |
|---|---|---|
| Pre-registration hash | `sha256sum PREREGISTRATION.md` vs `results/PREREG.sha256` | match, `55d3fe5a…57338` |
| Pre-registration predates the run | mtimes (local −0500) | `extract_mappings.py` + `mappings_top12.json` 00:48Z, `select_steps.py` 00:55Z, `ocsf_fields.py` 00:58Z (all disclosed as pre-freeze) → `PREREGISTRATION.md` 01:00:23Z → `PREREG.sha256` 01:00:30Z → rules 01:08Z, `gen_corpus.py` 01:07Z, `checks.py` 01:09Z, `run.py` 01:10Z → corpora 01:24–01:30Z → `interdiction.json` 01:31:46Z → `RESULTS.md` 01:37Z. Order holds. `selected_steps.json` carries a post-run mtime (01:31:49Z) because it is the stop-rule (c) re-run; my re-run reproduces it byte for byte. mtimes are self-reported, not third-party timestamps |
| Versions | `.venv/bin/pip freeze` vs `requirements.txt`; interpreter | identical; duckdb 1.5.3, SQLite 3.45.1, Python 3.12.3, pySigma 2.0.3, pySigma-backend-sqlite 2.1.1, PyYAML 6.0.3, as stated |
| Determinism, full re-run ×2 | `verification/rerun/hashes.txt`, `run1.log`, `run2.log` | both runs `d35b4928…a7c5d`, identical to the original; `truth.json` per seed `dcfe888b…`, `9b81a897…`, `6813ae0e…`, identical |
| Orientation inputs | `extract_mappings.py`, `select_steps.py` re-run in the copy | `mappings_top12.json` and `selected_steps.json` byte-identical; ATLAS sha asserted against the burn-down basis; 290 steps asserted |
| OCSF column validation | `ocsf_fields.py` | `FAILED 0` |
| Headline counts | `results/interdiction.json` summary | Rule SQLite 1/7/8/6, DuckDB 2/5/9/6; mechanism 3/2/3/0 both engines; `seeds_agreeing = 3` in every slot |
| Per-check figures | per-seed `checks` block | E4 FP 98/110/103, E5a FP 14/17/13, E5c FP 11/11/9, D6b FP 9/3/8, E8b FP 429/446/427, E8c FP 62/58/67, E8a 36–43, E1 20 every seed, D1/D7 0 alerts, D6c 5 alerts (3 proxy + 2 NAT IPs); all as stated |
| Planted volumes | `planted_per_step` | CS0076[2]/[4]/[11] 720 = 36 × 20, CS0075[7] 1000 = 50 × 20, as stated |
| E8b background rate | query on each `corpus.sqlite` | unattested share of unpinned installs 30.3–32.1%, of all installs 21.9–22.9%; matches Deviation 4 |
| "74 of the first-twelve marginal steps" | `control_burndown_2026.10.json` greedy | M0042 56 + M0001 13 + M0000 5 = 74; every marginal-step figure in the per-control table matches |
| Spend | — | bench: zero (no model calls, no containers). Verifier: one Gemini call via `agy-tracked.sh`, 14,935 tokens on the subscription quota, no metered spend |
| Fixture safety | `grep` over `gen_corpus.py` | strings in event fields only; injection phrases from public lists; destructive commands quote the public CS0047 description; URLs on reserved `example.net`/`example.org`/`example.com`; secret paths are path strings, no key material; no executable bytes, pickle or package. Within scope |
| Employer | — | nothing about the employer anywhere in the folder |

## Corrections made in `RESULTS.md`

1. **Marginal vs reach (Headline).** "The burn-down's marginal-step column counts all 22" was wrong. Recomputing the
   greedy marginal sets from `mappings_top12.json` (each matches the burn-down's `marginal_steps`) puts 14 of the 22
   rule slots in their control's marginal set; 8 are reach-only (CS0076[2] under M0043 and M0005, CS0068[23],
   CS0076[7] under M0020 and M0024, CS0076[4] under M0024, CS0073[1], CS0023[1]). All 22 are in `reaches_steps`. Now
   says so and adds the 14-slot counts (SQLite 1/2/7/4, DuckDB 2/1/7/4), which tell the same story.
2. **PyPI/Hugging Face comparison.** "which is roughly the 2026 state of PyPI attestations and Hugging Face artifacts"
   was an unsourced outside claim. Replaced with a tier-D note that the rates are invented and that lower real
   coverage would make precision worse.
3. **"Refusing most legitimate software."** E8b blocks about 22% of installs, not most software; what is true is that
   92–97% of what E8b/E8c block is legitimate. Reworded with the numbers.
4. **"Every text-matching check landed NOISY or MISSED" / "the four CAUGHT states".** True on SQLite only. On DuckDB,
   E5c is a fifth CAUGHT (CS0074[20], precision 1.0), caused by case-sensitive `LIKE` dropping the lookalike. Scoped
   to SQLite and the DuckDB exception named as an engine artifact.
5. **Case-folded supplementary counts.** "E5a 29 alerts, E5c 21 alerts" were seed-20261109 values; now ranges over
   seeds (28–32, 19–21). Also added a clarifying note that M0019 and M0005 are Policy-only in ATLAS too, so the drop
   rule is about a named artifact, not the Policy category.

## Pre-registration conformance

The analysis matches the pre-registration: same controls, same 30 slots transcribed into `run.py` `SLOTS`, the
same state thresholds (recall 0.5, precision 0.9), best-state-over-checks, entity-level precision, and the six
declared by-construction slots. The seven deviations in `RESULTS.md` are real and complete as far as I can find.
Two judgement calls I would flag rather than fix:

- **H5.** The verdict "holds on E5a and E5c, untested on E5b" is fair, but the RESULTS sentence saying the hypothesis
  "read literally … is refuted on that clause" is stricter than the falsifier, which applies to rules whose planted
  text includes mixed case; after Deviation 2, E5b is not such a rule. Best read: partially tested, not refuted. Left
  as written because it errs conservative.
- **H4 and H7 follow from declared fixture volumes.** D1/D7 producing zero alerts is a consequence of planting the
  distillation pools at 20 calls per account per hour against a 500/h ceiling, which the pre-registration declared in
  advance. It shows the mechanism (pooled valid accounts sit under per-identity ceilings) rather than measuring how
  often that happens; the Limits section says this, and the headline should be read with it.

## Cross-provider leg (Gemini 3.8 Flash via `agy-tracked.sh`)

Prompt: `verification/gemini-prompt.md` (the five claims with their data excerpts). Response:
`verification/gemini-response.md`.

| Claim | Gemini | Resolution against the data |
|---|---|---|
| 1. Headline counts; marginal column credits all 22 | PARTLY: counts right, marginal claim wrong | Agrees with my finding; fixed (correction 1) |
| 2. M0019/M0040 catch none (D1/D7 0 alerts) | SUPPORTED, with the caveat that ceilings were author-picked to sit above planted volumes | Agree; recorded above under H4/H7 |
| 3. Code signing, PyPI comparison | PARTLY: unsourced outside claim; also said "30%" misstates the realised 21–23% | Unsourced claim fixed (correction 2). The 30% point is a disagreement resolved against the data: the text says 30% *of unpinned installs*, and the corpora give 30.3–32.1% of unpinned; 21–23% is of all installs (Deviation 4). No change |
| 4. DuckDB case sensitivity; H5 | SUPPORTED | Agree |
| 5. Structural catches; text checks NOISY/MISSED; H3 factor 4–8 | PARTLY: E5c is CAUGHT on DuckDB; E3 precision 1.0 is by construction | First point fixed (correction 4). E3 caveat is already in RESULTS (my excerpt omitted it). 0.375/0.045 = 8.3 and 0.375/0.091 = 4.1, so "four to eight" holds |

## Limits of this verification

One verifier, same machine, same synthetic generator, so this confirms reproducibility and internal consistency,
not the external validity of the sentence-to-check mapping, fixtures or holder-of-control judgements, which stay
tier D. I did not re-read the ATLAS case-study text against each fixture beyond the planted counts.

## Files

- `VERIFICATION.md` (this file); `RESULTS.md` edited in place
- `verification/RESULTS.pre-verification.md`, `verification/gemini-prompt.md`, `verification/gemini-response.md`
- `verification/rerun/` (script copies, `run1.log`, `run2.log`, `hashes.txt`, `results/interdiction.run{1,2}.json`, regenerated corpora)

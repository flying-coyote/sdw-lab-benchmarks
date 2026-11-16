# duckdb-edge-floor enforced-cap run verification (2026-11-15)

**Verdict: VERIFIED-WITH-FIXES.** Every floor, kill count, spill peak, answer-equality claim and headline timing in `RESULTS-2026-11-15.md` reproduces from `results/trials*.jsonl` and `results/raw/` with a script of my own that imports nothing from the bench. All three pre-registration files match their sidecars, and each freeze precedes its arm's first trial. Three Docker spot checks against the existing image reproduce the arm C working points and a 7/8-rule kill. The Z key-dependence bug is real, and Z2's independence statistics hold. No hypothesis verdict changes. What needs fixing is framing and a set of small numeric ranges.

- **Framing.** The headline leads with the post-hoc 64 / 128 MiB floors ahead of the frozen 256 MiB result. The H1, H2 and H5b rows carry qualifiers ("mode clause held", "as written") that read softer than the frozen falsifiers. "What this changes" calls the temp-file explanation "supported" when the pre-registered test of it, H2, was falsified.
- **Disclosure.** The chrony deviation describes a -1.40 s reading at "one" trial and calls the large readings "transient", but 105 of the 219 run main-arm trials read about -1 s.
- **Scope.** "Holds on U, Z and Z2" claims an S floor of 64 MiB on Z2, but arm C never ran Z2 at 32 MiB, so that floor is not bracketed from below. H's 128 MiB floor is bracketed on Z2, because H was refused at (64, 1/2).

Fixes are proposed below, and nothing other than this file was edited.

Independent verifier agent, 2026-11-16, about 00:37Z to 00:55Z, against lab commit `7cfb9ff` (committed 00:36:21Z). The working tree for `duckdb-edge-floor/` was clean against that commit when I started, so what I checked is what was committed.

- **Spend.** $0 on the bench, local CPU only. The cross-provider leg was one Gemini call on the agy subscription quota (ledger id `edgefloor-verify-gemini`, 42,193 tokens), with no metered spend.
- **Git.** I ran no git command that changes state.
- **Scratch.** Re-derivation scripts and the agy prompt and response sit in the verifier's scratchpad. Docker cannot see that scratchpad (a bind mount of it came up as an empty root-owned directory), so the spot-check output and spill went to a temporary directory under `~/.cache/`, which I deleted afterwards.
- **Docker.** I started eight short containers, all `--rm`:
  - three first attempts that aborted with a permission error on the spill mount before DuckDB loaded;
  - one mount diagnostic;
  - three spot-check trials;
  - one accounting probe.

  I removed no image and touched no other container, and Ollama was not used. `docker ps` showed the three `drn-*` lab containers up before the trials and again at 00:54Z, and the 1-minute load was 0.26 to 0.60 during the trials. I did not monitor them in between.

## Pre-registration hashes and freeze timing

**Whole-file hashes, recomputed now.**

| File | sha256 | Matches |
|---|---|---|
| `PREREGISTRATION-2026-11-15.md` | `d5ede44b…dc01b6` | `results/PREREG.sha256` and `.frozen` |
| `PREREGISTRATION-2026-11-15-ADDENDUM-A.md` | `6aa30729…bf912` | `results/PREREG-ADDENDUM-A.sha256` and `.frozen-addendum-A` |
| `PREREGISTRATION-2026-11-15-ADDENDUM-B.md` | `a94dab7d…432378` | `results/PREREG-ADDENDUM-B.sha256` and `.frozen-addendum-B` |

**Body hashes.** These cover everything before `\n## Freeze\n`, computed the way the parent file describes. They are `eef135a4…4512a`, `70a07e4a…1f1ce` and `56e5b01e…fecca71`, and all three equal the values in the files, the `.frozen*` sidecars and the RESULTS frontmatter.

**Harness hashes.** Every frozen harness file still hashes to its registered value:

- `trial.py` `c7c822a5…a029`, `driver.py` `c05d2909…4007` and `gen_corpus.py` `2e0d4fc5…f0f2`;
- `image/Dockerfile` `405ac0a3…3c64`;
- `driver_armB.py` `b1116998…e2c5`, `driver_armC.py` `908178e8…f9c3` and `gen_corpus_z2.py` `a4aaae23…ae52`.

The three analysis scripts match the hashes in deviation 3. The local image `sdw-edge-floor:duckdb-1.5.3` is `sha256:ead733f4…558943`, as registered. The three corpus files hash to the `file_sha256` values in `corpus_stats*.json`.

**Ordering.** The evidence is file mtimes, printed by `stat` in local time (UTC-5), plus the per-trial `utc` stamps in the jsonl files. Everything landed in the single commit `7cfb9ff`, so git history cannot show the order, and none of this is tamper-proof.

- **Main arm.**
  - The harness files were written between 19:55:55Z and 19:58:23Z.
  - The pre-registration, `.frozen` and `PREREG.sha256` are stamped 19:59:59Z.
  - `U.parquet` and `Z.parquet` were written at 20:00:09Z and 20:00:17Z, and `corpus_stats.json` at 20:00:18Z.
  - The first trial (`null---c4096-t1-r1`) ran at 20:00:24Z.
- **Addendum A.**
  - `driver_armB.py` was written at 20:12:22Z, and the addendum and sidecars at 20:13:01Z.
  - The first arm-B trial ran at 23:29:05Z, after the main arm's last trial at 23:18:59Z, as the addendum requires.
  - The three observations the addendum says were visible at freeze all have trial stamps before 20:13:01Z: S-U-t1 completed at 256 and was killed at 128 and below by 20:01:59Z, S-U-t4 was killed at 256 at 20:02:08Z, and H-U-t1 was killed at 128 and below by 20:06:20Z. The driver then sat in a 600 s load wait until 20:16:21Z, so nothing more was visible at freeze than the addendum says.
- **Addendum B.**
  - `driver_armC.py` and `gen_corpus_z2.py` were written at 00:24:09Z, and the addendum and sidecars at 00:24:28Z.
  - `Z2.parquet` was written at 00:24:34Z and `corpus_stats_z2.json` at 00:24:35Z.
  - The first arm-C trial ran at 00:24:40Z.
- **Analysis script.** `analyze.py` was last modified at 20:00:57Z. That is before the first shape trial at 20:01:22Z, when only null trials existed. So the main-arm analysis was fixed before any shape outcome existed, which is stronger than deviation 3's "written after the freeze".

## Independent re-derivation

`indep.py` (sha256 `c367500d67a08c2a46cb0aa49ddec167f81050200d15e4ea6d39e960cc22d731`, kept in the scratchpad) reads the three trials files and every `raw/*.json` and `raw/*.samples.jsonl` as data. For killed trials it takes peaks from the raw samples file directly rather than from the driver's `peaks_from_samples`.

**Record consistency.** I cross-checked all 417 run trials against `raw/`.

- Every `kernel_oom_kill` has no final record, `child_rc` 137 and `oom_kill` ≥ 1.
- Every other outcome's raw record agrees on outcome and answer hash.
- 251 records carry `duckdb` 1.5.3, which is every completed or refused trial. Killed trials die before they can write a record.
- `poll_errors` is 0 everywhere, and no trial timed out, errored or ended as `no_record`.

**Counts.**

| Arm | Trials | Run | Completed | Kernel kill | DuckDB OOM | Skipped |
|---|---|---|---|---|---|---|
| Main | 390 | 219 | 105 | 114 | 0 | 171 |
| B | 270 | 138 | 50 | 48 | 40 | 132 |
| C | 75 | 60 | 50 | 4 | 6 | 15 |

The stop rule shows up cleanly in the trial counts. Every cell either ran five trials and completed all five, or ran two and failed both: 21 + 57 cells in the main arm, 10 + 44 in arm B and 10 + 5 in arm C. No cell mixes completions and failures.

**Main-arm floors (frozen definition), all reproduced.**

- **null:** floor 32, failing at 16 by kernel kill, 2 of 2.
- **One thread:** S and H have floor 256 on U and Z, and first fail at 128 by kernel kill. J has floor 4096 on U and Z, and first fails at 256 by kernel kill.
- **Four threads:** every shape has floor 4096 and first fails at 256 by kernel kill.
- **Monotonicity:** no chain is non-monotone.
- **Failure modes:** of 12 failing shape chains, 12 have kernel kill as the mode and 0 have DuckDB OOM. There are 0 `duckdb_oom_error` among the 219 run trials. This matches `summary.json` `chains`.

**Arm B, all reproduced.**

- S completes at 64 only under 1/2 (`'32MB'`), on U and Z.
- H completes at 128 only under 1/2 (`'64MB'`). At 64 it is refused at 1/2 and 1/4 and killed at 3/4.
- J completes at no cap.
- Kills by fraction are 3/4 28, 1/2 16 and 1/4 4, and the four are J at 32.
- No shape completes at 32 under any fraction.

**Arm C, all reproduced.**

- S completes at all five points.
- H completes at every point except (64, 1/2), where DuckDB raises OOM 2 of 2.
- J completes only at (4096, 7/8), is killed at (256, 7/8) and (64, 1/2), and raises OOM at (256, 1/2) and (128, 1/2).
- Medians, CVs, peak anon and spill match the arm C table to the printed precision.

**Answers.** There is one reference hash per (shape, corpus, threads). Every one of the 205 completed trials matches its reference, and the thread-1 and thread-4 references are identical for all six shape-corpus pairs. The J answers match the RESULTS text:

- U: 15,399,118 pairs and 16,462,217 co-occurrences;
- Z: 850 pairs and 50,422,550 co-occurrences;
- Z2: 1,244,632 pairs, 57,908,504 co-occurrences and 626,716 rare pairs.

**Spill.**

- **Completed trials:** the maximum live spill is 560.8 MiB (`C-H-Z2-c128-f1of2-t1-r4`).
- **Failed trials:** the maximum is 1,011.9 MiB, in a J trial that DuckDB refused (`C-J-Z2-c256-f1of2-t1-r2`).
- **Files left after exit:**
  - None of the 205 completed trials and none of the 46 DuckDB-refused trials left a file.
  - 52 of 166 killed trials did, up to 614 MiB across arms.
  - In the main arm, 32 of 114 killed trials left files, up to 527.7 MiB.
- **H-U-t1 at 256 MiB:** spill was 447.0 to 474.7 MiB.
- **J at 256 MiB before the kill:** 491.1 / 496.7 MiB on U and 527.7 / 483.9 MiB on Z.

**Buffer manager against anon.** Each figure below is peak cgroup anon minus peak buffer-manager bytes. The two are separate maxima over the trial, not simultaneous readings.

- **null:** 18.3 to 18.4 MiB in every null trial.
- **Capped completed shape trials:** 21.6 to 35.7 MiB across all three arms. In the 256 MiB cells the range is the same, 21.6 to 35.7.
- **Uncapped reference trials:** much wider. H-U at one thread reaches 64.0, J-U at one thread reaches 164.9, and three of the four-thread cells go negative (as low as -23.6), because their two peaks fall at different moments.

**H4 inputs.** Only null completed at a cap of 64 MiB or below in the main arm. In all 10 of those trials, `VmHWM` was 58.5 to 59.1 MiB, above the limits of 53.4 MiB (`'56MB'`) and 26.7 MiB (`'28MB'`), and the gap was 18.35 to 18.42 MiB.

**Timings (medians of 5, one thread).**

| Cell | Reference | Capped | Notes |
|---|---|---|---|
| S on Z2 at (64, 1/2) | 0.684 s (CV 2.5%) | 1.830 s (CV 0.8%) | |
| H on Z2 at (128, 1/2) | 2.317 s (CV 2.4%) | 5.172 s (CV 1.6%) | |
| S on U, main arm | 1.134 s | 2.523 s | |
| S on Z, main arm | 1.148 s | 1.051 s | |
| H on U, main arm | 3.229 s | 5.495 s | |
| H on Z, main arm | 2.982 s | 9.417 s | CV 15.0%, load 3.95 to 7.17 |

The arm B medians reproduce: S-U 4.776 s (CV 16.8%), S-Z 2.026 s (5.0%), H-U 5.322 s (1.1%) and H-Z 5.224 s (1.4%).

**Load and clock.**

| Arm | 1-min load | Trials started above 4 | Load waits | chrony offset |
|---|---|---|---|---|
| Main | 2.59 to 21.35 | 55 of 219 | 29 of 78 cells, 10,980 s | -1.397 to +0.00046 s |
| B | 1.43 to 13.63 | 19 of 138 | 6 of 54 cells, 3,090 s | -0.24 to +0.0001 s |
| C | 0.23 to 1.55 | 0 | none | -0.27 to +0.00007 s |

But in the main arm the offset sat between -0.95 and -1.40 s on 105 of the 219 run trials, interleaved with readings near zero: the reading crossed -0.5 s 118 times across 218 consecutive pairs of run trials (see discrepancy 6).

## Z corpus key dependence, and Z2

**The bug.** In the lab `.venv`, which carries DuckDB 1.5.3, the same version as the image, `xor(hash(i,'host'), hash(i,'proc'))` takes exactly one distinct value over a million values of `i`: `6247390154223743254` for `i` = 1, 2 and 7. The same holds for `('ts','usr')` and `('a','b')`, while `hash(i,'host')` itself takes a million distinct values. So every Z column is a function of one shared per-row value, as addendum B says.

**Z2 control.** The same test on Z2's scheme gives a million distinct values each for `xor(hash(8i+1), hash(8i+3))` and `xor(hash(8i), hash(8i+1))`, and corr(host bucket, process bucket) = -0.0016.

**Statistics re-queried from the committed Parquet files** (hash-matched). I did not regenerate the corpora; I queried the files.

| Statistic | U | Z | Z2 |
|---|---|---|---|
| Heavy-shape groups | 9,999,996 | 7,657,773 | 9,980,751 |
| Host-hours | 1,346,361 | 1,088,200 | 1,087,394 |
| Distinct host-process pairs | | 8,359 | 890,549 |
| `h0` distinct processes / users / minutes | 200 / 1,228 / 365 | 12 / 19 / 10,081 | 200 / 19,938 / 10,081 |
| `h0` rows | | 770,068 | 770,840 |
| Mean distinct minutes per host | 364.1 | | |

U's row is not comparable for `h0`, because U's hosts are near-uniform. U's mean of 364.1 distinct minutes per host matches "about 364". A uniform draw would give 10,080 × (1 − e^(−1250/10080)) × 8,000 ≈ 9.4 M host-minutes, which matches the RESULTS figure.

## Docker spot checks (n = 1 each)

Each trial mirrors the driver's `docker run`:

- `--rm --user 1000:1000 --memory=<cap>m --memory-swap=<cap>m --cpuset-cpus=2`;
- the bench's committed `trial.py` and the corpus mounted read-only;
- output and spill on ext4 outside the repo.

| Trial | Load | Result | Bench figure |
|---|---|---|---|
| S on Z2, cap 64, `'32MB'` | 0.44 | completed, 1.861 s, hash `89b019f3…` (= Z2 reference), anon 58.8, buffer manager 30.4, spill 139.6, `VmHWM` 98.8 MiB, nothing left after exit | median 1.830 s, anon 59.1, spill 139.0 |
| H on Z2, cap 128, `'64MB'` | 0.56 | completed, 5.178 s, hash `dab46626…` (= reference), anon 91.6, buffer manager 60.9, spill 549.3 MiB, nothing left | median 5.172 s, anon 91.0, spill 560.8 max |
| S on U, cap 128, `'112MB'` (7/8 rule) | 0.60 | `rc` 137, `oom 1`, `oom_kill 1`, `memory.peak` = cap; last sample at 0.347 s: buffer manager 106.6, anon 124.9, spill 1.8 MiB; 2.9 MiB of spill left on disk | killed 2 of 2; last sample buffer manager 106.6, anon 124.1, spill 2.2 MiB |

In both completed trials `memory.events` `max` was non-zero, at 1,826 and 7,492. The same is true of 90 of the 105 capped completed shape trials in the bench, whose `memory.peak` equals the cap. So the trials that complete do so while the kernel reclaims page cache at the cap, which is consistent with the RESULTS note that page cache drives `memory.peak` to the cap.

**Accounting probe** (null in a fresh 64 MiB container, load 0.59). `memory.stat` gave anon 17.0, file 0.0 and `file_mapped` 0.0 MiB. `memory.peak` was 18.7 MiB, and `/proc/self/status` gave `RssFile` 34.5 and `VmHWM` 51.5 MiB. That confirms the direction of the accounting caveat, since the library's file pages are not charged to the container. In this probe even fewer were charged than in the RESULTS one-off, which reported file 23 and `file_mapped` 18 MiB, so those exact numbers don't reproduce. My probe ran a `python -c` snippet rather than `trial.py`, and the one-off's method is not recorded, so the difference probably reflects host cache state but may also reflect method. Neither does the derivation of "13 to 40 MiB", which appears to be 36 − 23 and 59 − 20 but is not written down (discrepancy 12).

## Verdicts against the frozen falsifiers

| H | RESULTS verdict | Frozen falsifier applied to the data | Agree? |
|---|---|---|---|
| H0 | Held | null 5/5 at 32 and above; 2/2 kernel kills at 16 | Yes |
| H1 | Falsified on the floor (mode clause held) | Floor 256 on U and Z, which is "fails at 64 or above". Falsified | Verdict yes. The parenthetical is accurate as description, but H1 predicted the first failure at 32 and it came at 128, so the mode clause "held" only at a cap H1 did not predict. "Falsified" with the detail in the evidence cell reads closer to the rule |
| H2 | Falsified as written, on both clauses | Clause 1: no H-U-t1 trial completed at ≤ 128. Clause 2: 32 killed trials left bytes, and the falsifier says "any trial" | Verdict yes. "As written" adds nothing, since both falsifiers fired. See discrepancy 3 on how "What this changes" then scores the underlying explanation |
| H3 | Falsified | H-U-t1 fails at 128 | Yes |
| H4 | Held on the client baseline only; untested on query shapes | 10 of 10 null trials pass both inequalities | Yes, and the qualifier is honest. The test is weak: null's buffer manager is 0, so the gap is just client anon, and `VmHWM` cleared the 64 MiB-cap limit by only about 5 MiB, mostly file pages. Counting it in the "five held" tally is correct under the rule, but it carries no evidence about query shapes |
| H5a | Falsified, and confounded | 23.4% < 30% | Yes |
| H5b | Falsified as written | Both floors are 4096 under the frozen definition, so "strictly higher" fails | Verdict yes. But "the test had no resolution" understates. The only memory evidence runs against H5b's direction: uncapped J-Z anon was 1,245 MiB and J-Z2 1,357 MiB, against 2,816 MiB for J-U. Arm C already reports this, but the H5b row should say so |
| H5c | Held, and confounded | 256 ≤ 256 | Yes |
| H6 | Held | Every four-thread floor is 4096 ≥ the one-thread floors | Yes |
| H7 | Held | 12 of 12 kill-modal; DuckDB OOM is the mode in 0 of 12 | Yes |
| B1 | Held | At 128, S completes at all fractions and H at 1/2, on U and Z | Yes |
| B2 | Falsified on H; J clause untested | H has no completing fraction at 64 | Yes. "Untested" for the J clause is right and consistent with H5b being falsified. B2's J falsifier is "J on Z completes at a cap no larger than J on U", and it cannot fire when neither completes, because arm B has no reference cap in its chains, while H5b's chains include 4096 |
| B3 | Held | 3/4 28 kills against 1/4 4 | Yes. The counts are stop-rule truncated (2 per failing cell), so this is 14 cells against 2. It holds either way |
| C1 | Held | 9,980,751 ≥ 9.0 M | Yes |
| C2 | Held | All three points as predicted | Yes |
| C3 | Held | J completes only at (4096, 7/8) | Yes |

The tally of five held and five falsified in the main arm reproduces.

## Deviations: disclosed or not

| Deviation | Disclosed? | Check |
|---|---|---|
| MB against MiB effective fractions | Yes (8, and the Units paragraph) | 224 MB = 83.4%, 96 = 71.5%, 64 = 47.7% and 32 = 23.8% of the cap, matching "~83/72/48/24%". The working-point limits 30.5 and 61.0 MiB are correct |
| Stop rule cuts killed cells to 2 trials | Yes (6) | Confirmed: 57 + 44 + 5 cells at 2 trials, and every completed cell at 5 |
| Analysis scripts written after the freeze | Yes (3) | Hashes match. `analyze.py`'s final mtime predates every shape trial (above) |
| Heavy host load in the main arm and arm B | Yes (5, and the rig stamp) | Main peak 21.35, 55 of 219 trials above load 4. Arm B peaks at 13.63, which RESULTS does not state; the brief's "up to 21" is the main-arm peak |
| chrony -1.40 s | Partly (7 and the rig stamp) | Understated: 105 of 219 main-arm trials, not one, and not transient (discrepancy 6) |
| Library pages cached outside the cgroup (lower-bound caveat) | Yes (accounting caveat) | Direction confirmed by my probe. The one-off's numbers and the 13 to 40 MiB range are not documented (discrepancy 12) |
| Z generator dependence | Yes (2, addendum B) | Confirmed |
| Windows power plan not checked | Yes (rig stamp) | n/a |

## Discrepancies

| # | File | Claimed | Found | Moves a verdict? |
|---|---|---|---|---|
| 1 | `RESULTS` Headline | Opens, in bold, with "Floors under an enforced cap … S 64 MiB … H 128 MiB", and the frozen 256 MiB result follows | Those floors come from post-hoc arms B and C. The page says so in the next paragraph, but the post-hoc floors still lead as the primary finding. The commit message and ledger row lead with the frozen arm | No |
| 2 | `RESULTS` H1, H2 and H5b rows; `LEDGER-ROW` | "Falsified on the floor (mode clause held)", "Falsified as written", and "the test had no resolution" | All three are plainly falsified under their frozen rules. H5b's only memory evidence points the other way (J-Z 1,245 and J-Z2 1,357 MiB uncapped against J-U 2,816 MiB) | No |
| 3 | `RESULTS` "What this changes" | Temp files deleted before a post-query check: "supported" | The pre-registered test of this explanation, H2, was falsified on both clauses. The support is post-hoc: no completed or refused trial left files, and June's check after `fetchall()` found none. That reading is reasonable, but it should be labelled post-hoc next to the H2 result | No |
| 4 | `RESULTS` Headline | S floor 64 "holds on U, Z and Z2" | Arm C never ran Z2 at 32 MiB, so on Z2, S's completion at 64 is shown but the failure below it is borrowed from U and Z. H's 128 floor is bracketed on Z2 at the working fraction, since H was refused at (64, 1/2) | No |
| 5 | `RESULTS` Headline ("process's anonymous memory runs 21 to 35 MiB above the buffer manager") and "What this changes" ("Anon ran 21 to 35 MiB above it") | 21 to 35 MiB, unscoped | 21.6 to 35.7 MiB holds for capped completed trials. Uncapped trials run up to 164.9 MiB (J-U), and the two peaks are separate maxima | No |
| 6 | `RESULTS` rig stamp and deviation 7; `LEDGER-ROW` | "-1.40 s at one main-arm trial", "the larger readings were transient", "one chrony reading of -1.40 s" | 105 of 219 run main-arm trials read -0.95 to -1.40 s, interleaved with readings near zero (118 crossings of -0.5 s in 218 consecutive pairs). Arm B and arm C stay within -0.27 s. Durations use `perf_counter`, and a 1 s swing between trials 1 to 2 s apart looks like stepping or a reporting artefact rather than slew. So the effect on latency is probably small, but it is not shown | No |
| 7 | `RESULTS` arm B (B3 row) and `LEDGER-ROW` | "kills 28 → 4" | The stop rule caps these counts at 2 trials per failing cell, so this is 14 cells against 2 | No |
| 8 | `RESULTS` Headline, last sentences of "Why the 7/8 rule fails" | "At roughly half the cap, the query spills and completes. Lower than that, DuckDB fails fast and cleanly" | At about half the cap, H at 64 and J at 128 and 256 are refused, and J at 64 is killed. Below half, J at 32 under 1/4 is killed (4 kills), and H at 128 with `'32MB'` is refused only after about 3.1 s and 541 to 619 MiB of spill. That is true for S and H at their working points, not in general | No |
| 9 | `RESULTS` arm B, "Too low" bullet | S at 64 / `'16MB'` and H at 128 / `'32MB'` "failed in 0.01 to 3.2 s" | 0.070 to 3.204 s in those cells | No |
| 10 | `RESULTS` mechanism section, S-U at 128 MiB | "At the kill, 1.28 s into the container's life … 2.4 MiB had just spilled" | 1.281 s is `container_wall_s`, which includes Docker start-up and teardown. The last sample was at 0.368 s in-process. The spill was 2,359,296 B, which is 2.4 MB or 2.25 MiB, against the page's "all figures MiB" rule | No |
| 11 | `RESULTS` mechanism section, three ranges | Spilling 256 MiB cells' gap "25 to 35"; non-spilling "21 to 23"; `VmHWM` "281 to 291" | The per-trial values are 25.2 to 35.7, 21.6 to 23.8 and 281.5 to 291.8 MiB. The upper ends are truncated rather than rounded, so the trials at the top end fall outside the stated ranges. I checked three other ranges and found them correct for the population RESULTS names: "213.6 to 213.9" is the range of per-cell maxima, "7 to 19" is trial 1 only (7.1 to 19.4), and "530 to 670" is the per-cell maxima for J at 128 (528 to 668) | No |
| 12 | `RESULTS` accounting caveat | One-off check: anon 16, file 23, `file_mapped` 18, `RssFile` 36 MiB; floors low "by something like 13 to 40 MiB" | No artefact for the one-off is committed. My probe gave anon 17.0, file 0.0, `file_mapped` 0.0 and `RssFile` 34.5 MiB, which is the same direction with different numbers. The 13 to 40 range is not derived on the page | No |
| 13 | `RESULTS` arm C, J paragraph | "skew multiplies co-occurrences by about 3.5× while cutting distinct pairs by about 12×" | U is not a clean uniform baseline: its `ts` and `host` are correlated (2.9 M host-minutes, against about 9.4 M uniform and 5.2 M on Z2). So the U-to-Z2 ratio mixes skew with U's correlation | No |
| 14 | `RESULTS` arm B table | CV shown only for S-U | The frozen rule says "real only where it exceeds both cells' CV", and the page lacks the CVs needed to apply it: H-U 1.1%, H-Z 1.4% and S-Z 5.0%. All four ratios pass the rule | No |
| 15 | `RESULTS` "same 50 hosts" sentence | Answer equality "closes the draft's open 'same 50 hosts' item" | It shows that the tie-broken, rounded query is deterministic across caps and threads. It says nothing about June's untie-broken query. The text says "ties broken by host", but "closes" reads wider | No |
| 16 | `RESULTS` Files line and `LEDGER-ROW` | "Independent verification is owed" | This pass now exists | No |

## Proposed fixes (not applied)

1. Headline order: lead with the frozen result, then the post-hoc floors under a label that says what they are. For example: "Main arm, as frozen: with `memory_limit` at 7/8 of the cap, S and H have a floor of 256 MiB at one thread, J has none at or below 256, nothing completes at four threads, and all 12 failing chains die by kernel OOM kill. Post-hoc (arms B and C, not blind): at `memory_limit` near half the cap, S completes at 64 MiB and H at 128 MiB."
2. Verdict wording:
   - **H1:** "Falsified. Floor 256, not 64; first failure at 128 by kernel kill (the predicted mode, at an unpredicted cap)."
   - **H2:** "Falsified on both clauses."
   - **H5b:** "Falsified (both floors 4096). The range could not separate the two chains, and uncapped J memory points the other way (J-Z 1,245 MiB, J-Z2 1,357 MiB, J-U 2,816 MiB)."
   - Mirror the same wording in the ledger row.
3. "What this changes", first Tier D bullet: "Temp files are deleted before a post-query check: consistent, post hoc. The frozen test (H2) was falsified on both clauses, because no H-U trial completed at 128 MiB or below and killed trials leave files. But no completed or refused trial in any arm left a file after exit, and June checked after `fetchall()`."
4. Headline Z2 scope: "S completes at 64 MiB with `'32MB'` on U, Z and Z2, and fails at 32 MiB on U and Z (Z2 not run at 32)." H needs no change: on Z2 it completes at 128 MiB and is refused at 64 MiB at the same fraction.
5. Scope the 21 to 35 MiB claim to "capped completed trials (21.6 to 35.7 MiB)" in both places, and note that the figure is peak anon minus peak buffer manager, two separate maxima.
6. Deviation 7 and rig stamp: "chrony read -0.95 to -1.40 s on 105 of 219 run main-arm trials, alternating with near-zero readings. Arms B and C stayed within -0.27 s. Durations use `perf_counter`; its rate under this behaviour was not characterised, which is one more reason main-arm latencies are indicative only." Shorten the ledger row to match.
7. B3 evidence: add "(stop-rule truncated: 14 failing cells at 3/4 against 2 at 1/4)".
8. "Why the 7/8 rule fails", last two sentences: "For S and H, a limit near half the cap lets the query spill and complete at 64 and 128 MiB respectively. Lower limits mostly turn kills into DuckDB `OutOfMemoryException`s, in 0.07 s for S at `'16MB'` but only after about 3 s and 540 to 620 MiB of spill for H at `'32MB'`; J was still killed at 32 MiB under 1/4."
9. Arm B "Too low" bullet: "0.07 to 3.2 s".
10. Mechanism section: "In the last sample before the kill, 0.37 s after the process started (the container lived 1.28 s) … 2.25 MiB had just spilled."
11. Round the three truncated ranges outward: "25 to 36", "22 to 24" and "281 to 292".
12. Accounting caveat: commit the one-off's `memory.stat` output, or mark it uncommitted. State the derivation of 13 to 40 MiB (`RssFile` 36 − charged file 23; `VmHWM` 59 − `memory.peak` 20), and add that a second probe charged 0 MiB of file pages against `RssFile` 34.5 MiB, so the uncharged share varies, probably with host cache state.
13. Arm C J paragraph: "against U, whose correlated keys also shape its pair counts, Z2 has about 3.5× the co-occurrences and about one-twelfth the distinct pairs."
14. Arm B table: add the CVs of the three unflagged cells.
15. "Same 50 hosts": "shows that the tie-broken S query returns the same 50 hosts in the same order at every completing configuration; June's query without a tie-break was not re-run."
16. Frontmatter, Files line and ledger row: point to this file and its verdict.

## Cross-provider leg (Gemini)

**The call.** One call through `project1/automation/agy-tracked.sh` (ledger id `edgefloor-verify-gemini`). The model was `gemini-4-hydrogen-high`:

- 23,076 input tokens and 19,117 output tokens, 15,852 of them thinking, for 42,193 in total;
- 96 s, conversation `bad40d17…`.

**What it was given.** Bench text only, with none of my findings:

- the pre-registration from "Outcome classes" through "Variance and reporting";
- both addenda's "Why this exists" to "Hypotheses" sections;
- the RESULTS body.

Prompt sha256 is `2d841f65…4e96d20` and response sha256 is `67f245b9…3fea786`. Its output is treated as data.

**Its verdict calls.** It judged 15 of 16 verdicts as following ("yes") and H4 "partly".

| Gemini's point | My call | Notes |
|---|---|---|
| H4 counted as held on a vacuous `SELECT 1` test; "only summary values" reported, not every trial | Partly agree | Every one of the 10 null trials passes, which I checked, so the "every trial" doubt is resolved. The weakness of the test is real; I keep the verdict and note it in the table |
| H2 and H5b "as written" soften outright falsifications; H5b's direction is contradicted by uncapped J memory | Agree | Discrepancy 2, found independently by my re-derivation |
| H1's "(mode clause held)" softens | Agree | Discrepancy 2 |
| Headline leads with post-hoc floors; "What this changes" foregrounds them; spill and "0 of 205" pool arms without attribution | Agree on order (discrepancy 1). Partly agree on pooling | The pooling is accurate as a count, but per-arm figures would help: main 0 of 105, B 0 of 50, C 0 of 50 |
| Z2 floor claims not bracketed below | Agree for S, disagree for H | Discrepancy 4. H was refused at (64, 1/2) on Z2, so its floor is bracketed at the working fraction; the other fractions at 64 were not run |
| "Half the cap completes; lower fails fast and cleanly" overgeneralises | Agree | Discrepancy 8 |
| Arm B CVs missing, so the frozen latency rule can't be applied | Agree | Discrepancy 14. The rule passes once the CVs are added |
| "Supported" for the temp-file explanation after H2 failed | Agree | Discrepancy 3 |
| "Same 50 hosts" proves determinism of the modified query only | Partly agree | Discrepancy 15. RESULTS does say "ties broken by host" |
| 13 to 40 MiB extrapolated from null and a one-off | Agree | Discrepancy 12 |
| U-to-Z2 J comparison not purely skew | Agree | Discrepancy 13 |
| The main arm was reframed as testing "the 7/8 rule" after H1 and H3 failed | Partly agree | The reframing is disclosed in addendum A and labelled post-hoc. The frozen hypotheses are scored as written. The residual problem is the headline order (discrepancy 1) |
| MB against MiB not tested at binary halves | Disagree that it is a defect | The floors are stated with the exact limit strings that worked, and binary halves are an untested alternative, not an error |
| H0's 32 MiB floor optimistic | Agree, already disclosed | The accounting caveat covers it |

No disagreement is left to resolve against the data.

## Credential and employer scan

I grepped all 703 tracked files under `duckdb-edge-floor/` (`git ls-files`, read-only) for three kinds of string:

- the lab's own pre-commit secret patterns (`scripts/secret-scan.sh` P1 to P4), plus `password`, `passwd`, `api_key`, `bearer` and `secret`;
- employer names. I could not locate the hub's denylist file, so I used the names known to this session; they are not repeated here, because this repository is public;
- personal email and home-directory paths.

The result was zero credential hits. There was one benign keyword match in `PREREGISTRATION-2026-11-15.md` line 18 ("`sudo -n` needs a password"), and zero employer or personal hits.

## Could not check

- **When the files go away.** The exact moment DuckDB deletes its temp files, whether at query return, at connection close or at process exit, was not measured by the bench or by me.
- **The one-off `memory.stat` check.** RESULTS reports file 23 and `file_mapped` 18 MiB, but no artefact was committed, and my probe did not reproduce those numbers (above).
- **Freeze ordering.** It rests on mtimes and jsonl stamps only, because everything landed in one commit.
- **Image provenance.** I did not rebuild the image. Its ID matches the registered one.
- **Corpora.** I did not regenerate them from the generators. I verified the file hashes and recomputed the statistics from the committed files.
- **Clock rate.** The effect of the main-arm chrony behaviour on `perf_counter` was not characterised. My spot re-runs of the two arm C working points, at low load, land within 2% of the bench medians (1.861 against 1.830 s, and 5.178 against 5.172 s), but on the same host clock.
- **Hardware.** Real edge hardware is out of scope (item 6), as RESULTS says.
- **Employer denylist.** The hub's employer denylist file was not located, so the employer scan used the names known to this session rather than the canonical list.

## Residual limits

- **Design.** The pre-registration and both addenda were frozen by an agent and not owner-reviewed, and both addenda were written after seeing data. Reproduction shows the numbers follow from this design; it does not show the design is the right one.
- **Resolution.** The post-hoc floors come from a three-fraction sweep at factor-of-two cap spacing, so "64 MiB" means "completes at 64, nothing tried between 32 and 64".
- **Accounting.** Every floor is a lower bound on device memory, because library file pages already in the host cache were not charged to the container.

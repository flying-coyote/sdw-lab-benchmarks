# R7 verification (delegation-chain-query)

**Verdict: VERIFIED-WITH-FIXES.**

Independent verifier agent, 2026-11-09, on the same host (the Beelink, WSL2; 1-minute load 7 to 11 during the re-run, lower than
either original run). I didn't trust the run summary. I re-derived every number below from the raw JSON and re-ran the key cells. Pre-fix
copy of RESULTS.md: `/tmp/claude-1000/-home-jerem-project1/af12c3ec-6e7f-4f5c-a239-70fb7dfd0d6e/scratchpad/r7/RESULTS.pre-verify.md`.

## Pre-registration timing and hashes

- I rebuilt the freeze hash from the current file. `PREREGISTRATION.md` cut at the line "(none at freeze)" plus a newline gives
  `18c6124c…cd166a`, which matches `results/freeze.txt` (frozen 2026-11-09T23:00:13Z). Cut before amendment 2 it gives `fb4b9890…e056`
  (amendment 1, 23:01:01Z). The whole file gives `15bebb41…0dbe` (amendment 2, 23:13:25Z). So the amendments only appended text. I found
  no in-place edit.
- `results/run.log` shows the first cell starting at 23:01:08Z, after the freeze and after amendment 1. Run 2 started at 23:13:30Z,
  after amendment 2. The log's wall clock reads about 0.3 s slow, which doesn't change this order.
- Harness hashes: `gen.py`, `run_cell.py` and `requirements.txt` match the frozen hashes. `run_all.py` matches the amendment-1 hash
  `a2d0b59e…`. I couldn't check the original `run_all.py` (`94d30b84…`) because that file was overwritten, so I'm relying on
  the amendment's own statement that only the import line changed.
- `summarize.py` was not hashed at freeze, and its mtime (18:18:22 local) falls after run 2, so the analysis script was not frozen. It does
  compute the pre-registered metrics as defined (median, CV, A/B, A d12/d2, B max/min). I'm recording this as a process gap, not an error.

## Re-derivation from the raw records

- `summarize.py raw_run1` and `summarize.py raw` reproduce `results/tables_run1.md` and `results/tables_run2.md` byte for byte.
  `results/summary.json` is a stale copy of `summary_raw_run1.json`, byte-identical to it.
- Correctness, checked per cell: in both runs, A, B and C match exactly in 18/18 cells in both engines. No trial has a checksum mismatch,
  and every engine-arm has 5 trials. D's true positives plus missed `reacquire` equal the planted count in every cell, with zero false
  positives. Missed `reacquire` totals 31,758 per run. D's minimum recall of 0.398 comes from the 1e5/d12 cell (83 plants). In the
  1e6 and 1e7 cells at depth 4 or more, recall is 0.55 to 0.665.
- Every 1e7 figure quoted in RESULTS (A, B and C medians, CVs, A/B, A/C, the between-run deltas, chDB-vs-DuckDB 1.35 to 1.80×, load
  ranges) matches the tables.
- Versions recorded in every raw cell: DuckDB 1.5.3, `chdb 4.4.0 / ClickHouse 26.9.2.1`, 14 threads in each engine. Pins: all 18
  logical fingerprints **and** all 18 byte hashes are identical across run 1 and run 2.

## Re-run (local CPU, $0)

Script: `/tmp/claude-1000/-home-jerem-project1/af12c3ec-6e7f-4f5c-a239-70fb7dfd0d6e/scratchpad/r7/verify_run.py`, which regenerates with `gen.py`, pins,
and calls the unchanged `run_cell.py`. Log: `/tmp/claude-1000/-home-jerem-project1/af12c3ec-6e7f-4f5c-a239-70fb7dfd0d6e/scratchpad/r7/verify.log`.
Raw output: `/tmp/claude-1000/-home-jerem-project1/af12c3ec-6e7f-4f5c-a239-70fb7dfd0d6e/scratchpad/r7/raw/`.

- Regenerated artifacts for 1e7/d12, 1e7/d2, 1e6/d12 and 1e5/d12 match the original logical fingerprint, byte sha256 and
  `truth.json` exactly.
- Correctness reproduces exactly. A, B and C are exact in every re-run. D misses 3,748 / 0 / 349 / 50 `reacquire` plants, which matches
  the original counts.

Medians in ms, 5 trials per re-run:

| cell | engine | A_recursive | B_selfjoin | C | A/B | original A/B (r1 / r2) |
|---|---|---|---|---|---|---|
| 1e7 d12 ×3 | DuckDB | 1525, 1578, 1569 | 261, 279, 257 | 18 to 23 | 5.85, 5.66, 6.11 | 5.13 / 5.55 |
| 1e7 d12 ×3 | chDB | 796, 878, 828 | 284, 342, 277 | 25 to 27 | 2.80, 2.57, 2.99 | 2.45 / 2.86 |
| 1e7 d2 ×2 | DuckDB | 604, 601 | 235, 223 | 28 to 29 | 2.57, 2.69 | 2.21 / 1.97 |
| 1e7 d2 ×2 | chDB | 350, 347 | 245, 236 | 22 | 1.43, 1.47 | 1.37 / 1.30 |

The DuckDB walk at 1e7/d12 falls inside the reported 1.56 to 1.70 s range or just below it. Most other medians come in 5 to 20% lower,
consistent with the lower load. The pattern holds: A/B rises with depth, DuckDB stays above 3 at 1e7/d12, chDB stays below 3, and chDB
runs the walk faster. The re-run A/C at 1e7/d12 is 32 to 87, a little wider than the reported 34 to 80, but within the run-to-run
spread. H1 at 1e7 in the re-run: DuckDB 2.57, chDB 2.39. Both are above 2 this time, which supports calling H1 load-sensitive.

## Fixes made in RESULTS.md (each one in place)

1. **H1 verdict** was "Not supported / unstable". Under the pre-registration (judged on run 1, "Wrong if the ratio is below 2 in an
   engine") and amendment 2 (a verdict that flips between runs is unstable), it is now "Falsified for DuckDB as pre-registered (run 1,
   1e6: 1.95), unstable for chDB (passed run 1, 1.61 at 1e7 in run 2)", with the re-run values added. The run summary's line, "unstable;
   it fell below 2 in run 2", also misses that DuckDB already failed in run 1.
2. **D recall** was "as low as 0.398 in the deeper cells". 0.398 comes from the smallest cell (83 plants), and recall was 0.55 to 0.67 at
   1e6 and 1e7. I added that the recall level comes from the generator's plant mix, so it isn't a prevalence estimate. Without that
   caveat the claim went further than the evidence.
3. **H3 chDB margin.** I added that chDB A/B ran 2.45 to 2.99 across 5 measurements, just under the threshold of 3, so "falsified for
   chDB" holds by a thin margin.
4. **Sub-1e7 ranges.** "Medians 5 to 500 ms" is now 3 to 870 ms, because chDB A at 1e6/d8 in run 1 was 864 ms. "CVs ran 20 to 60% on A
   and B" is now "up to 58%, often 20% or more, a few cells under 10%".
5. **Load time** "about 0.45 to 0.8 s" is now 0.4 to 0.8 s (the minimum was 396 ms). "Byte hashes matched where checked" is now
   "all 18 byte hashes matched".
6. I added a one-line verification pointer under the Headline heading.

I changed no data, script, table or pre-registration.

## Analysis vs pre-registration

- The arms, predicates, grid, trial count, timers, memory caps, timeout and correctness check match the pre-registration. No DNF
  occurred, so the skip rule never fired.
- Amendment 2 (the second run) was added after run 1, but it is dated, changes no hypothesis or threshold, and keeps run 1 as the
  run that judges the hypotheses. I'm treating it as an acceptable, disclosed deviation.
- The depth-trend-in-A/B claim is labelled not pre-registered, and the re-run reproduces it (DuckDB about 2.6 to 5.9, chDB about
  1.45 to 2.8). It's still a comparison across cells, so it's fair as a stated observation but not as a tested hypothesis.
- Minor gap: the pre-registration says `chronyc tracking` is re-recorded "verbatim" before the run. It was for run 1, but run 2 has only
  the `Last offset` line.

## Limits that still stand

The original limits still apply: shared host, linear chains, integer keys, an unmeasured ingest-side cost for C, field names not checked
against OCSF 1.9.0, chDB 4.4.0 instead of the lab's 4.1.8 pin, and hot runs only. My re-run was also on a shared host, at load 7 to 11,
so it confirms the direction and rough size of the results, not quiet-host absolutes.

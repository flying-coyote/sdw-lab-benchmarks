---
type: benchmark-verification
title: "R2 verification: one MCP tools/call, three schemas"
created: 2026-11-09
area: R2-toolcall-three-schemas
verdict: VERIFIED-WITH-FIXES
---

# R2 verification

**Verdict: VERIFIED-WITH-FIXES.** Every number in RESULTS.md reproduced, the pre-registration predates the run, and
the hypothesis verdicts follow the pre-registered rules. Three wording fixes and four unlogged minor deviations were
corrected or logged in RESULTS.md; none changes a verdict.

Verifier: independent agent, 2026-11-09, same host (Beelink, Ryzen 7 5800H, WSL2 6.6.87.2, 14 threads), the area's own
`.venv` (Python 3.12.3, mcp 2.3.0, duckdb 1.5.3, pyarrow 23.0.1). No git commands. $0, no model calls; the only network
call was the free public OCSF validator at schema.ocsf.io (synthetic records only).

## 1. Pre-registration timing and hash

- `sha256sum PREREGISTRATION.md` = `eddf681633f728b700e1d3b7bc6662ac9ddde1702bee8297ff4a8d3fa8410183`, matching
  `PREREGISTRATION.sha256` and the RESULTS.md header.
- mtimes (local -0500): PREREGISTRATION.md 17:58:50, sha file 17:58:56 (= 22:58:56Z as stated), then capture.py/proxy.py
  17:59:26, server.py 18:01:58, `capture/wire.jsonl` 18:02:34, first timing file 18:08:56. The pre-registration was
  frozen before any capture, mapping or timing. (mtimes are agent-controllable, so this is consistent evidence, not proof.)

## 2. Re-runs and reproduction

| step | command | outcome |
|---|---|---|
| capture | `.venv/bin/python capture.py` | 25 wire messages; same 6 ok / 4 isError pattern; negotiated `2025-11-25` while `mcp.types.LATEST_PROTOCOL_VERSION` = `2026-07-28`; error masking text `Error executing tool <name>` reproduced (2x run_query, 1x describe_table); unknown tool returns `isError`, no JSON-RPC `error` member. Wire identical to the original except monotonic stamps and the tie order of one `ORDER BY 2 DESC` result (no tiebreak, harmless). |
| mapping | `.venv/bin/python map_schemas.py` | loss table byte-identical (`loss_table.json`, `loss_table.md`): 24/22/19/11/8 typed, 3/3/0/0/0 hashed, 3/3/3/0/0 blob, 3/5/11/22/25 unmapped, 0 dropped; 0 path-check failures. Records differ only in time/duration fields and in the tie-ordered result of call 3 (the `ORDER BY 2 DESC` tie at n=15). |
| validator | `.venv/bin/python validate_ocsf.py` | identical: OCSF-main 10/10 fail on `ai_capability` + version; AOS 10/10 zero errors, two warning kinds. |
| corpus | `.venv/bin/python gen_corpus.py 100000` | logical fingerprints and byte sizes identical for all three layouts (deterministic generator). 1M not regenerated. |
| timing | `R2_TAG=_verify run_queries.py 1000000 {0,1,2}` | see below |
| pooling | `verify/pool.py "" _rerun _verify` | independent re-pool of the raw samples reproduces every formal and rerun median, CV, ratio and floor in RESULTS.md (Q2 L1 36.0 vs 36.1 and Q4 L1 CV 64 vs 65 are rounding). |

Verifier timing pass at 1M (load average 2.6 rising to 7.3, so also not isolated), 21 samples per cell, answers equal
across layouts on all five queries and identical to the original answers (75; 566; agent-0000/0001 at 18; 5571; 138987):

| query | L3/L1 formal | L3/L1 rerun | L3/L1 verify | L2/L1 verify |
|---|---|---|---|---|
| Q1 | 8.4x | 8.5x | 8.7x (floor 1.72) | 31.7x |
| Q2 | 5.3x | 4.9x | 5.3x (floor 3.32) | 7.3x |
| Q3 | 5.4x | 14.7x | 10.1x (floor 1.88) | 17.9x |
| Q4 | 4.7x | 16.1x | 17.5x (floor 1.37) | 35.8x |
| Q5 | 22.5x | 21.6x | 22.0x (floor 4.82) | 31.4x |

All three runs agree on direction and on every hypothesis verdict: H4 supported (L3/L1 >= 3x on Q1/Q3/Q4/Q5, outside
pooled CV), the L2-between prediction failed (L2 slowest everywhere), H4b refuted, H5 refuted (1.13x). Q3/Q4 ratios
again sit inside the "roughly 5x to 16x" range RESULTS.md quotes; L1 CV reached 101% on Q4, which confirms the advice
to quote ranges and not absolute milliseconds. Other spot checks: 100k L3/L1 ratios 6.1/5.6/11.3/16.3/20.6 re-pooled from the raw pass files (`N=100000 verify/pool.py ""`)
and match; Q3 L1 per-pass medians 7.5/16.8/29.9 confirmed; 1M sizes 27.4/58.2/30.9 MB confirmed; H1 counts (9 of
12 unmapped for AOS example 2, 11 for example 1) recomputed from `loss_table.json`; `ai_capability` on main carries the
four hint booleans, `transaction_uid` and `transport_id` and only `desc_fingerprint` (no description text), so HASHED is
the right class; `unmapped.asop` appears 16 times in `ref/aos_implementation_examples.md`.

## 3. Fixes applied to RESULTS.md (original kept at `verify/backup/RESULTS.md.pre-verify`)

1. **Claim exceeded evidence (L2 mechanism).** The H4 bullet stated as fact that a DuckDB MAP lookup reads the payloads
   and that this explains the L2 cost; the only test of that (exploratory no-payload rewrite) was inconclusive. Reworded
   as an untested best explanation, with the measured size of the map value column (23.9 MB of 58.2 MB).
2. **Wrong number (H4b).** "roughly 25% of calls (weight 30 of 121) that are run_query" -> measured share in the 1M
   corpus is 27.8%; corrected to "roughly 28%".
3. **Wrong number (H5).** trace_id + span_id are 28.1 MB of the L2 file (`parquet_metadata`), not 27 MB; corrected to 28 MB.
4. Added a verification pointer under the RESULTS.md header and a Deviations item 6 logging four unlogged deviations:
   (a) pre-registered H1 list names "step" (not in inventory) and one "agent model" fact where two are scored, verdict
   unchanged (10 of 13 if step added as unmapped); (b) H2's "error code" scored as `isError` because no JSON-RPC error
   occurred; (c) per-pass CV promised but only in raw files; (d) saved validator output predated the final record
   rewrite, re-run gives identical counts.

## 4. Things checked and left alone

- Analysis matches the pre-registration: 2 warmups + 7 trials x 3 processes, rotated layout order, pooled median/CV,
  L2/L1 and L3/L1 ratios, 100k scale point, answer equality, codec/row-group read-back. The "within CV" test in
  `analyze.py` uses the larger of the two CVs, a fair reading of "inside the pooled CV". The conservative floor and
  the load-limited rerun are additions, and the rerun is logged as deviation 2.
- Versions are recorded: schema commits in PREREGISTRATION.md, packages pinned in `requirements.txt`, rig stamp and
  chrony offset in RESULTS.md.
- Limits (no isolation, stdio only, harness-supplied agent identity, AOS scored on examples, one OTel landing shape,
  exploratory run inconclusive) are stated plainly and match what I observed.
- Original capture, records and validator output were restored after the re-run; the verifier's outputs are in
  `verify/rerun/`, the pre-verification copies in `verify/backup/`.
- `data/n100000/corpus_meta.json` and `capture/sandbox/` were also restored after the re-run.

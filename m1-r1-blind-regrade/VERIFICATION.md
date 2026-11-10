---
type: benchmark-verification
bench: M1-r1-blind-regrade
verified: 2026-11-09
verdict: VERIFIED-WITH-FIXES
verifier: independent agent (Claude Opus 5.5), no git
---

# Verification: M1 r1-blind-regrade

VERIFIED-WITH-FIXES: every headline number reproduces byte-for-byte from the saved raw responses and independently from a separate script, the pre-registration hash matches and predates the run, deviations are disclosed, and no identifier or secret appears; four small wording imprecisions in RESULTS.md were corrected and marked `[fixed in verify]`. H4 (consensus) remains untested, as RESULTS says.

## History

An earlier pass of this file (written 20:09 EST, before any grading call) recorded NOT-VERIFIED because the freeze-era agent had died with zero calls made; its pre-run checks (prereg hash, blinding, prompt-size cap, Grader A gate, versions, spend) all passed. That record is the evidence behind RESULTS' first deviation, and it independently fixes the prereg hash at a time before any response existed.

## Checks

**Pre-registration.** `sha256sum PREREGISTRATION.md` = `a2eed4adbab81c3980220e3c7e4ec3f9bff304f6a60736116fac4327b6a240cf`, identical to `results/PREREG.sha256` and to `prompts/manifest.json` `prereg_sha256`. Freeze `2026-11-10T00:51:49Z` (19:51:49 EST). Prompt files and manifest mtime 19:52:48. First grading call completed 22:07:01 local after 366 s, so it started about 22:00:55, roughly 2 h 9 min after the freeze; the same hash was recorded by the 20:09 pre-run verification. `run_pass.sh` was patched at 22:00:39, about 16 s before the first call started, consistent with "patched before any call". Mtimes are not tamper-proof, but the 20:09 record is an independent timestamp.

**Reproduction from raw outputs.** Copied scripts, prompts and responses to a scratch tree and re-ran `analyze.py` and `recompute.py` (Grader A gate passed): `grader_b.json`, `agreement.json`, `disagreements.csv` and `headline.json` are byte-identical to the bench's `results/`. A separate script written for this verification (parses the 30 responses, modal grade, Cohen's kappa) gives the same numbers: five-category 62.03% / expected 30.75% / kappa 0.4516; specific binary 83.54% / 0.6695; observable binary 84.81% / 0.1222; flip 9 of 282 (3.19%), 0 ties; disagreements 30 (direct/generic 12, generic/none 6, none/proxy 6, generic/proxy 5, event/proxy 1); B modal distribution 31/26/13/5/4; pass-pair kappa 0.9267, 0.9112, 0.8964; technique rows all `none`, 60%, kappa 0.0. Invented object or class: 0 of 282 checked against the 194 objects and 87 class uids in R1's `sources/`. Confusion matrix matches `agreement.json`. Profile arm under B equals core in every pass (168, 173, 167). Technique moves: 30 (15 to none, 9 to direct, 6 to generic).

**Headline tracing.** Every line reference in RESULTS.md to `results/headline.json` (1529 to 1589) and `results/agreement.json` (3 to 7, 61 to 109, 165 to 182) resolves to the quoted value. Supporting figures also check: 36 disagreement rows; 30 adjudication rows in 3 batches whose complement is exactly the six listed; excerpt sha256 `85138738…`, 62,340 bytes; ledger has 30 `m1-p*` rows, all `gemini-3.8-flash-high`, all SUCCESS, 30 distinct conversation ids, 1,889,180 tokens, 131.98 call-minutes; `responses/calls.count` = 30; three Argon attempts all `SKIPPED` by the wrapper at 0.1866; `agy --version` = 1.5.3.

**Re-run slice.** Re-sent pass-1 `artifact-b3` and `technique-b2` (15 rows) to `gemini-3.8-flash-high` through `agy-tracked.sh`: 14 of 15 grades equal the original pass-1 grades and the modal grades (one flip, `d3f:Server` direct to generic), in line with the 3.2% flip rate and pass-pair agreement of about 93% to 95%.

**Deviations.** Disclosed: second agent executed the run; `run_pass.sh` operational patch (call cap under flock, `gemini-5h` stop rule, stricter retry check, halt marker, skip-valid); `run_adj.sh` added and its "argon calls: 3" meaning attempts; adjudication and consensus missing; the prereg's untracked smoke test. I found no undisclosed change to hypotheses, metrics, thresholds, prompts or the tie rule.

**Identifiers and secrets.** Regex scan of `results/` and `RESULTS.md` for emails, API keys and tokens (Google, OpenAI, GitHub, OAuth bearer), UUIDs and conversation ids, home paths, account and employer names: no hits. The `secret`, `password` and `account` matches are rubric rationales about D3FEND credential and account artifacts, not values.

## Fixes applied to RESULTS.md (each marked `[fixed in verify]`)

1. Frontmatter `run_date`: the 22:01 start was labelled a ledger timestamp; ledger `ts` values are completion times (22:07:01 to 22:38:20).
2. H5 cell: "3.19% (9 of 94 rows…)" mixed denominators; 3.19% is 9 of 282 row-grades.
3. Technique stratum: agreement is 60% on the five-category and observable collapses but 80% on the specific collapse (`agreement.json` line 182).
4. Argon draw-down: narrowed to 22:16:52 to 22:25:30 from the ledger's `quota_after` trail, during which only this bench's Flash calls were logged; the claim that it came from unseen use is softened to include quota accounting the ledger cannot attribute.

## Verifier footprint

Two calls, ledger ids `m1-verify-p1-technique-b2` and `m1-verify-p1-artifact-b3` (88,520 tokens, zero dollars), are verifier spend outside the bench's 36-call cap, so `grep -c '"m1-'` on the ledger now returns 32. `responses/calls.count` and every bench file other than RESULTS.md and this file were left untouched. Re-run outputs are at `/tmp/claude-1000/-home-jerem-project1/af12c3ec-6e7f-4f5c-a239-70fb7dfd0d6e/scratchpad/rerun/artifact-b3.md` and `/tmp/claude-1000/-home-jerem-project1/af12c3ec-6e7f-4f5c-a239-70fb7dfd0d6e/scratchpad/rerun/technique-b2.md`; the independent scoring script is `/tmp/claude-1000/-home-jerem-project1/af12c3ec-6e7f-4f5c-a239-70fb7dfd0d6e/scratchpad/scripts/indep.py`. No cross-provider leg was run.

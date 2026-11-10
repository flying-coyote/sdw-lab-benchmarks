---
type: benchmark-verification
bench: M1-r1-blind-regrade
verified: 2026-11-09
verdict: NOT-VERIFIED
verifier: independent agent (Claude Opus 5.5), no git
---

# Verification: M1 r1-blind-regrade

## Verdict: NOT-VERIFIED (run incomplete, nothing to verify yet)

This file is a pre-run check only. Replace it with a full verification once RESULTS.md exists.

There is no RESULTS.md and no grading output in this folder, so no result claim exists to confirm or
refute. The verdict is not a finding against the bench's method; the pre-run checks below all pass, and
the bench should be re-verified once it has actually run.

## What is on disk (checked 2026-11-09 19:55 to 20:10 EST)

- `PREREGISTRATION.md` (mtime 19:51:43 EST), `results/PREREG.sha256`, `results/PREREG.frozen_at`
  (`2026-11-10T00:51:49Z` = 19:51:49 EST), scripts and prompts written 19:52 to 19:55, a venv,
  `responses/pass1.out` (0 bytes, 19:53:04) and `responses/pass1/run.log` (0 bytes, 19:55:20).
- No `RESULTS.md`, no `results/grader_b.json`, `consensus.json` or `headline.json`, no response `.md` files.
- I watched the folder for roughly 15 minutes: `run.log` stayed empty. At 20:09 EST, `ps` found no
  `run_pass`, `agy-tracked` or `xargs -P` process, and a scan of every live shell's full
  `/proc/<pid>/cmdline` for the string `m1-r1-blind-regrade` matched only my own watchers (the one
  long-running `taskset` shell turned out to be the t3-guardrail-adaptive bench). The agy ledger (`~/.local/share/agy-usage/ledger.jsonl`) has no
  `m1-*` entry (its last entry is 2026-11-07). So no grading call has been made; the run appears to have
  been launched and died (most likely its parent agent ended), not to be in progress.

## Pre-run checks that pass

- **Pre-registration integrity.** `sha256sum PREREGISTRATION.md` =
  `a2eed4adbab81c3980220e3c7e4ec3f9bff304f6a60736116fac4327b6a240cf`, identical to `results/PREREG.sha256`.
  The freeze time precedes every script, prompt and response file by mtime. Mtimes are not tamper-proof,
  but with no responses at all there is nothing the pre-registration could have been written after.
- **Blinding.** 30 prompt files (3 passes × 10 batches, 94 rows per pass = 79 artifact + 15 technique).
  A substring search for the first 50 characters of every R1 `rationale` and `crosswalk_reason` across all
  prompt text found 0 matches; prompts carry the D3FEND/ATLAS definition, the rubric word for word as
  pre-registered, the four-clause discipline, and the OCSF 1.9.0 excerpt (194 objects, 87 classes, 62,340
  bytes).
- **Argument-size assertion.** Largest prompt 70,777 bytes, under the pre-registered 120,000 cap.
- **Grader A gate.** Running `recompute.evaluate` on R1's CSVs alone (the full `recompute.py` needs
  `grader_b.json`, which does not exist) reproduces core-arm 161/235/290 steps, 112/155/182 defender-ground
  steps and 55/91/107 techniques, matching R1 and the pre-registered gate exactly. Input hashes match the
  pre-registration prefixes (`0622cb6c…`, `d914f59b…`, `0de548fa…`).
- **Versions.** Python 3.12.3, `PyYAML==6.0.3` pinned; `agy --version` is promised for RESULTS and
  cannot be checked yet. `run_pass.sh` defaults to `gemini-3.8-flash-high`, matching the pre-registration.
- **Spend.** Zero calls made, zero dollars; well inside the 36 Flash / 4 Argon cap.
- **Safety scope.** Fixtures are public ontology text (D3FEND 1.4.0 definitions, ATLAS v2026.10
  technique descriptions, OCSF 1.9.0 schema excerpt). No attack payloads, exploit code, credentials or
  containers.

## Observations for when the run resumes (not errors)

- `run_pass.sh` makes up to 3 tries per batch (1 + 2 retries), which matches stop rule (a), but 30
  batches × up to 2 retries could reach 90 Flash calls against the 36-call cap; the script does not count
  calls across batches, so the cap is enforced only by the operator.
- `run_pass.sh` checks for the string `"row_id"` but not for valid JSON or the right row count; that
  `analyze.py` parses with `json.loads` and records missing batches and rows as problems (lines 17, 46,
  51), which covers it at analysis time, though a malformed batch would not trigger a retry.
- The prereg says the smoke test used `agy` directly; it is not in the tracked ledger, which is consistent
  with that, but RESULTS should say so.

## Cross-provider leg

Not run. There are no result claims to send to Gemini; sending the pre-registration's hypotheses would
test nothing about the data.

## Not done, and why

- No re-run of the bench. Running the 30 grading calls and the adjudication myself would make me the
  bench author rather than its verifier, and could collide with the original agent if it resumes in this
  folder. Before anyone relaunches, re-check that no M1 process is alive, because a second launch into
  this folder would duplicate responses and push past the 36-call cap. Then the orchestrator should relaunch the bench (`./run_pass.sh 1|2|3`, then `analyze.py`,
  `adjudicate.py`, `recompute.py`) and queue a fresh verification.
- No files in the bench were edited.

---
type: benchmark-verification
area: T1-shadow-ai-discovery
date: 2026-11-09
verdict: VERIFIED-WITH-FIXES
---

# Verification: T1 shadow-AI discovery

**Verdict: VERIFIED-WITH-FIXES.** Every measured result reproduces exactly. Three fresh full runs (new containers,
new captures, new osquery and Syft passes) gave per-method fired-rule sets identical to the original run 1 for all
six method views, so across six runs there is zero variance in what fired. Re-scoring the original raw outputs
gives byte-identical `fired.json` and `egress.json` and an identical `scores.json`. The pre-registration predates
the runs and its hash is unchanged. Six claims in `RESULTS.md` were corrected in place, each marked
*[verification fix]*: one miscount, one wrong mechanism, one run-specific number stated as general, one
matrix label (osquery S8/S9 "structural" → "rule gap"), and the H5 outcome, which now says both of its
falsifications depend on post-run harness changes or on how cells are counted. No found/partial/missed grade and
no found count changes. A pre-fix copy of RESULTS is kept at `verify/RESULTS.pre-verification.md`.

## What was checked and how

Same machine and conditions as the original: Beelink, WSL2, kernel 6.6.87.2, 14 vCPU / 47 GB, Docker 29.5.3,
the same local images (`t1-endpoint:local` 88ba938b, `t1-sidecar:local` c7043dbc, `zeek/zeek:8.0.11` 3882d4b4) and
the same fixture home. Containers pinned `--cpuset-cpus 0-3`, host commands under `nice -n 10 taskset -c 0-3`, other
benches running concurrently, so verification timings were also **taken under contention**. Clock at verify start:
18 µs fast of NTP (`verify/rig-verify.txt`).

| Check | Command / artefact | Result |
|---|---|---|
| Pre-registration hash | `sha256sum PREREGISTRATION.md` vs `prereg.sha256` | match, `bc2920c9…7060d`, before and after the verification edits |
| Pre-registration written before the run | mtimes (local −0500) and `COMMANDS.log` | `PREREGISTRATION.md` 19:55:47 (00:55:47Z) → `prereg.sha256` 00:55:54Z → first download 00:56:16Z → discarded run 00:59:27Z → runs 1-3 01:05:13Z → methods 01:08:30Z → re-score 01:14:10Z. Order holds; mtimes and the log are self-reported, not third-party timestamps |
| Changes made after the freeze | `COMMANDS.log`, `run_methods.py` comment | Chrome fixture rebuilt, `yara` → `yara_file`, peer calls via `urllib`, O5 id read from `name`, O1 id made pid-stable, `copilot.com` added to `S9_HOSTS`. All but the last are disclosed; the last is implied by Deviation 8 and is now stated (Deviation 11) |
| Versions | `rig-verify.txt`, `results/run1/versions-endpoint.txt` | tcpdump 4.99.5, dnsmasq 2.91, Alpine 3.22.8, Zeek 8.0.11, Syft 1.55.0 (built 2026-10-19), osquery 5.24.0, Ollama 0.20.6, curl 8.14.1, Python 3.12.13 in the endpoint, Debian 13. All as stated |
| Download integrity | `sha256sum -c fixture-sha256.txt` in `dl/` | osquery deb and Cline vsix both OK |
| Re-score from original raw | `verify/run_methods_verify.py 1 2 3 --score-only` on a copy (`verify/rescore/`) | `fired.json`, `egress.json` byte-identical for runs 1-3; `scores.json` identical |
| Full re-run, 3 runs | `verify/run_lab_verify.py {1,2,3}` and `verify/run_methods_verify.py 1 2 3` (copies with output dir and log path changed only) | 0 non-zero exits; peer calls 200/200/200/200 every run; fired-rule sets identical to original run 1 for M1, M1b (`-i any`), M2, M3, M4, M5 in all 3 runs; matrix, found counts, union and FP list identical |
| Headline counts re-derived from raw | Zeek `summary.json`, `egress.json`, `syft.json`, original and verify | 20 SNIs and 20 DNS names per run, 13 of 13 AI hosts in both, `registry.ollama.ai` in both, every run of six; eth0 `http.log` 4 rows (tags, generate, chat, C1); 15 egress flags; Syft 72 = 64 python + 2 model + 6 binary (`Simple Launcher`); models `TinyLlama`/`MiniLM-L6-H384-uncased`, version `UNKNOWN`, no PURL, matching R4's raw output |
| `-i any` capture | Zeek `any` summaries | `http.log` 32/28/29 rows in original runs 1-3 and 29/29/29 in verify; includes loopback, runner ports (33139 in run 1) and `ollama/0.20.6 (amd64 linux) Go/go1.24.1` on `/api/pull`, as stated |
| Post-hoc P1 (hidden dirs) | `verify/posthoc/V-P1-*.json`, SQL re-derived | `/home/dev/%%` regular 15,618, all types 16,944; `/home/dev/.%%` regular 15,874; explicit blob path 5 rows (weights 637,699,456 bytes). Identical to the original. The 13 dot-containing rows under `%%` are hidden *files* in visible dirs (`.keep`, `.f2py_f2cmap`), so the claim that `%%` does not descend into hidden directories holds; `/home/dev/.ollama/%%` recurses fine (8 files) |
| Post-hoc P2e (socket owner) | same query with and without `--cap-add SYS_PTRACE` | default: `pid -1`, empty name on 8000/8080/11434; with the capability: `python3`, `python3`, `ollama`. Reproduces |
| `yara` table mechanism | `osquery_registry`, `PRAGMA table_info(yara)`, `.schema yara_file` | `yara` resolves in 5.24.0 but without the hidden `sigrule` column; `yara_file` has it. The discarded run's `no such column: sigrule` fits this, not "the table is named `yara_file`, not `yara`". Fixed |
| Spend | `activity.log`, prereg Cost | $0. Dummy key `sk-lab-dummy-0000` got 401/400; openrouter.ai and huggingface.co returned 200 on unauthenticated listings. About 20 public HTTPS requests per run; the verifier added 3 runs' worth (about 60 requests), no paid calls |
| Fixture safety | read `activity.sh`, `openai_compat_stub.py`, `make_chrome_fixtures.py`, MCP configs; secret-pattern grep | No exploit code, no attack payloads; the stub returns fixed JSON; manifests carry no code; MCP env holds `lab-dummy`. The only key material is two locally generated RSA keys used to derive Chrome extension ids, gitignored and signing nothing. Public artefacts: Cline from Open VSX, prettier, PyPI wheels, TinyLlama/MiniLM from R4 |
| Network exposure | `run_lab.py` | No `-p` publishing; services bind `0.0.0.0` on the `t1lab` bridge so the peer can reach them. Lab-network only, not strictly localhost as the brief words it; noted in Deviation 11 |
| Timing (secondary) | verify `scores.json` | Zeek eth0 2.16 s (CV 9%), Syft 9.1 s (CV 11%) vs original 34.2 s (CV 74%), osquery 7.5 s (CV 3%). The Syft median differs by 3.8×, which supports the original's refusal to claim any timing |

## Fixes made in place

1. **Headline miscount** (`RESULTS.md` headline). It said "Four of the ten cells on the osquery column depended on
   knowing where to look" and then listed five (S6, S7b, S4, S3, S5). Now "five of the ten cells (four of its six
   finds, plus the S7b miss)". The run summary's "4 of its 6 finds" was already right.
2. **H5 stated without its dependencies.** osquery reaches six "found" only because of two post-run changes: S4
   rests on `yara` → `yara_file` (frozen query errors, leaving S4 partial on file presence) and S3 rests on reading
   the id from `name` (literal `publisher.name` gives `.saoudrizwan.claude-dev`, a rule-gap miss). Under the frozen
   text osquery scores four, and H5's "no method ≥6" part holds. Separately, "the union misses S7b" falsifies H5
   only on the ten-cell scoring, because H5 is worded over nine surfaces and the union reaches S7 at found. The H5
   row and a headline sentence now say both. The as-run outcome is kept and nothing is flipped.
3. **osquery S8/S9 labelled "structural".** The pre-registration defines structural as "the method's input cannot
   contain the surface at all". The run's own `X_process_open_sockets` output holds TIME_WAIT rows to the remote
   :443 addresses (IP only, `pid -1`), so the live endpoint's input does contain that traffic; no pre-registered
   rule looked at it. Changed to "missed (rule gap)" in `RESULTS.md` and in `run_methods.py` (`STRUCTURAL["M3_osquery"] = set()`),
   then the original results were re-scored with `--score-only`: only those two matrix labels changed in
   `results/matrix.md` and `results/scores.json`, and `fired.json` stayed byte-identical. No found count moves.
4. **Wrong mechanism for the `yara` change** (Deviations 1 and 2, H3 row). Rewritten to match the 5.24.0 schema (see table).
5. **Run-specific count stated as general** (H2 row). "`any` `http.log`: 32 rows" is now "32, 28 and 29 rows in runs
   1-3". The headline already pinned 32 to run 1.
6. **Status lines** saying "not independently verified" (header and Limits) now point here.

Deviation 11 was added to `RESULTS.md` for items the original list missed: `copilot.com` added to the ground
truth after the freeze; `alpine:3.22` local image created 2026-11-05, which falls inside the two-week cooldown the
pre-registration applied to osquery 5.24.1 (the lab methodology has no written cooldown rule, so Deviation 6 and
this one are self-imposed); post-hoc SQL not logged; first-pass `fired.json` overwritten; bridge rather than
localhost binding.

## Cross-provider check (Gemini)

Five claims, each with its excerpt, sent through `~/project1/automation/agy-tracked.sh` to `gemini-3.8-flash`
(id `t1-verify-gemini`, 26,640 tokens, 108 s; prompt `verify/gemini-prompt.md`, answer `verify/gemini-response.md`).

| # | Claim | Gemini | Resolution against the data |
|---|---|---|---|
| 1 | Union 8 found / 1 partial (S2) / 1 missed (S7b) | AGREE | Confirmed by `scores.json` in all six runs |
| 2 | osquery 6 of 10 found, so H5 is falsified | PARTLY: overstated, because S3, S4 and S6 rest on non-frozen or directed queries | Partly upheld. S3 and S4 do rest on post-run changes, which is fix 2. S6 does not: the directed O4b query was pre-registered, so Gemini is wrong on that part |
| 3 | Network sees 13 of 13 remote hosts every run, local runtimes only through the peer | AGREE | Confirmed; same counts in all six runs |
| 4 | False positives exactly the pre-registered one (C1 on port rules) | PARTLY: `copilot.com` was saved from being a flag only by a ground-truth change after the shake-out | Rejected on the FP claim, accepted on disclosure. FPs are defined over benign controls C1-C6, and `copilot.com` is the redirect target of an AI SaaS visit (Microsoft Copilot), not a control, so mapping it to S9 is correct. Without the mapping, the scorer would have listed it under `?` and inflated the egress FP list by one non-control. The post-freeze timing of the mapping is now in Deviation 11 |
| 5 | Syft 0 components for extensions and configs; models reproduce R4 exactly; the store is what neither found a tool for | PARTLY: "exactly" was unsupported by the excerpt, and osquery did reach the store post hoc | Rejected after checking R4's raw `syft` JSON: `TinyLlama`/`MiniLM-L6-H384-uncased`, `UNKNOWN`, no PURL, identical. RESULTS already words the store claim as "every method missed under its frozen rules", with the post-hoc osquery find labelled. Note that R4 graded MiniLM only under a lenient rule, while T1's pre-registered Syft rule counts any `model` component, so "found" here and "lenient found" in R4 are the same output under different rules |

## What the evidence does and does not support

- Supported: the coverage shape (network = remote use, endpoint agent = configs/extensions/runtimes, Syft =
  packages and two model formats), zero run-to-run variance in what fired, the single benign-control FP class, the
  hidden-directory glob gap, and the capability-dependent socket ownership.
- Bounded: the planted surfaces and the rules come from the same author, so "found" means a competent query can
  see it. One host, one fixture set, one version per tool. The re-run used the same fixture home and images, so it
  rules out transcription and run-to-run error, not fixture-specific effects such as the authored Chrome layout
  that S5's grade depends on.
- Not supported: any latency or throughput comparison (the Syft median moved 3.8× between sessions).

## Files written by the verifier

- `VERIFICATION.md` (this file); in-place edits to `RESULTS.md`, `run_methods.py` (one scoring-label set),
  `results/matrix.md` and `results/scores.json` (re-scored), `.gitignore` (verify outputs), and one line at the end of `COMMANDS.log`
- `verify/`: `rig-verify.txt`, `run_lab_verify.py`, `run_methods_verify.py`, `COMMANDS-verify.log`, `lab-run{1,2,3}.log`,
  `methods.log`, `run{1,2,3}/` (raw outputs, large files gitignored), `scores.json`, `matrix.md` (verify runs, scored before
  fix 3), `rescore/` (gitignored), `posthoc/V-P1-*.json`, `posthoc/V-P2-listening-{default,ptrace}.json`,
  `scores.original.json`, `matrix.original.md`, `RESULTS.pre-verification.md`, `gemini-prompt.md`, `gemini-response.md`

No git was run. `PREREGISTRATION.md` was not touched.

---
repo: sdw-lab-benchmarks
date: 2026-06-21
source: WF-C intent self-audit
evidence-tier: B
---

# Intent self-audit — sdw-lab-benchmarks (2026-06-21)

Run against the portable intent question bank in
`~/claude-code-project-best-practices/analysis/intent-alignment-audit.md` (the nine "why"
questions generalized from the Fable prompts). This is the **why** pass on the load-bearing
mechanisms, not a presence/absence inventory. Citations are real `file:line` from a read of the
tree on 2026-06-21.

## What this repo is FOR (Q1 — Goal)

One sentence: it is the public, first-party, reproducible measurements behind
securitydataworks.com/lab — the place the company's security-data claims get *measured* instead
of asserted, each a small deterministic experiment a skeptic can re-run and each labelled at an
honest evidence tier. `README.md:3-7` states exactly this, and it is consistent with the
project1 CLAUDE.md cross-repo map ("Lab benchmarks (public, canonical) → ~/sdw-lab-benchmarks").
The goal is stated and stated the same way across surfaces — no fragmentation. The companion
private, NDA-gated catalog benchmark lives in a *separate* repo (`~/q3-catalog-benchmark`), so
this repo's public-canonical scope is clean.

The current mechanism serves that goal well. `lib/common.py:1-30` is a single determinism core —
one `MASTER_SEED = 20260601`, a fixed `BASE_EPOCH`, no `datetime.now()` / no unseeded randomness
in corpus generation — so a re-run reproduces the corpus and therefore the answers exactly. The
"reproducible part (assert identical) vs measured part (latency as a median on named hardware)"
split (`README.md:51-58`) is the right honesty discipline for a benchmark portfolio, and the
cross-engine answer-equality gate is the load-bearing idea: it is what caught the chDB Parquet
undercount the campaign treats as its strongest result (`SYNTHESIS.md`, `CAMPAIGN.md:46-53`).

Verdict: **genuinely fine on intent.** The repo is doing the thing it says it is for, and the
mechanism (determinism core + answer-equality gate + per-bench METHODOLOGY tiering) is the right
mechanism for that intent.

## Self-model accuracy (Q2) — the one real drift

This is the single concrete intent-mechanism gap. The repo has grown well past its own
description of itself:

- On-disk there are ~37 bench directories carrying a `run.py` (`find -name run.py`, excluding
  `.venv`/`_work` → 37), and 60+ top-level benchmark directories total.
- The `README.md` table (`README.md:16-42`) and Layout block (`README.md:81-108`) document **25**
  benches. **31 directories on disk are not listed in the README at all**, including substantial,
  committed, results-bearing work: `zeek-flagship-rerun/`, `pipeline-normalization-fidelity/`,
  `bench-d-tiered-realization/`, `ocsf-context-collapse-apt29/` (the de-gamed APT29 re-run that
  `CAMPAIGN.md:161-173` treats as a headline strengthening of H-OCSF-CONTEXT-COLLAPSE-01),
  `cost-to-serve-retention/`, `workload-interference/`, `ocsf-semantic-query/`,
  `spec-vs-emitted-integrity/`, `soc-query-shapes/`, and ~22 more.

This is the canonical Q2 failure the intent doc names: a hand-maintained self-description whose
count no longer matches the live tree (its example was an `ARCHITECTURE.md` claiming 26 docs
against 42). The README isn't *wrong* in what it lists — every row is real — it has simply fallen
~12 benches behind the directory it describes, and a skeptic landing on the public README would
not discover a third of the lab. `CAMPAIGN.md`/`SYNTHESIS.md` partly compensate as the running
campaign narrative, but they are framed R0–R8 (`CAMPAIGN.md:55-127`) and `SYNTHESIS.md` is
explicitly written after R0–R6, so neither is a complete index either.

This is the **biggest single finding** and the highest-leverage fix. Remediation, in Q2's
promotion spirit (drift twice → generate, don't restate): add the missing rows to the README
table now, and consider a tiny generator that emits the bench table from each dir's
`METHODOLOGY.md`/`README.md` front line so the index can't drift a third time. Until then the
README table is a hand-maintained invariant across ~37 directories — exactly the bus-factor shape
Q9 warns about (see below).

## What "better" means (Q3 — eval)

Strong here, and model-free where it counts. The answer-equality gate is a deterministic
regression check: corpus reproduces by construction, answers re-assert identical, and a
divergence is a *finding*, not noise (the chDB and fastparquet bugs were both surfaced this way —
`CAMPAIGN.md:133-160`). `VERSION-CURRENCY-2026-06-14.md` is the right kind of revalidation: it
re-ran the literature-load-bearing results on bumped engine versions and recorded what moved
(OpenSearch 2.18→3.7 was the one materially-stale foil). So the project can tell "better" from
"just changed" on the reproducible leg. The latency leg is honestly labelled as a median on named
hardware with CV reported, never as a constant (`BENCHMARKING-METHODOLOGY.md`,
`README.md:51-58`). No manufactured problem here.

## Autonomy boundary (Q4) and loops (the RETHINK question)

**This repo runs no loops, no scheduled jobs, no automation, and has no Claude harness of its
own.** There is no `CLAUDE.md`, no `AGENTS.md`, no `.claude/` directory, no `.github/workflows`
belonging to this repo, no `loop.md`, no cron. The only workflow YAMLs on disk
(`ocsf-context-collapse-apt29/_work/sigma/.github/workflows/*.yml`) live *inside a cloned upstream
SigmaHQ repository* under `_work/`, which is gitignored (`.gitignore:_work/`, and
`git ls-files | grep _work` → 0), so they are not this repo's automation — they are corpus input.
Every `run.py` is a human-invoked, single-box, foreground benchmark. `CAMPAIGN.md:55-57` is
explicit that runs are a manually-worked, resource-ordered backlog ("[ ] pending / [~] running /
[x] done"), serialized by hand to keep CV honest.

Because nothing loops, the strong-Act / stale-Orient pathology **does not apply** and there is no
`loop-without-rethink` signal to flag. The RETHINK / intent-check instrument is therefore **n/a at
the loop level** — there is no Act leg running unattended that could drive on a stale Orient. The
closest analogue this repo *does* carry is the right one for a benchmark portfolio: the campaign's
"Corrected assumptions" list (`CAMPAIGN.md:19-53`), nine prior beliefs the measurements forced a
change on, written after the runs. That is a falsification log, which is the Q5 instrument, not a
scheduled goal re-check — appropriate, because the goal re-check for *this* repo correctly lives
upstream in project1's `karen-evaluator` question-quality cadence and the WF-C audit you are
reading, not inside a measurement repo.

## Where most wrong (Q5)

The repo is unusually disciplined about its own falsifiers — `CAMPAIGN.md:19-53` is a list of nine
things it was wrong about and corrected. The belief it is *most* likely still wrong about is the
single-box / WSL2 generalization caveat that recurs across benches: most timing results are
one-machine medians under a Windows High-Performance power plan, and `CAMPAIGN.md:118-124` already
concedes that the R8 1.30× divergence turned out to be a drvfs-spill × memory-cap interaction
(resolved in T2.5, `CAMPAIGN.md:174-179`) rather than a format property — the kind of artifact a
single-box setup invites. The honest open falsifiers are stated: BENCH-A's "is Store N realistic"
independent-reviewer gate, the deferred device-measured DWPD (R9, not viable under WSL2 — no
`/dev/nvme*`), and the BENCH-B frontier / BENCH-C OBDA arms gated on external deps. None of these
are hidden; they are labelled. So Q5 is in good shape — the repo states what would break each
load-bearing claim.

## The one constraint (Q6)

The dominant bottleneck is **publication, not measurement.** The measurements are done and
self-consistent; the value that is *not* yet realized is that ~12 of them aren't surfaced in the
public README, and the essay slate (`CAMPAIGN.md:195-213`) that converts findings into
securitydataworks.com/writing pieces is a backlog gated behind the voice-consistency + publication
skills. Every "fix the README count" task is downstream of this one constraint: the lab's job is to
be the public evidence a skeptic can re-run, and a third of it is currently invisible from the
front door. Fixing Q2 (the index) is the cheapest move on Q6.

## What compounds / typed memory (Q7)

Knowledge accumulates well. `CAMPAIGN.md` is an append-only campaign tracker, `SYNTHESIS.md` the
read-together argument, per-bench `METHODOLOGY.md` / `RESULTS-*.md` / `FINDINGS-*.md` /
`STATUS-*.md` files carry durable per-run state, and OKF `type:` frontmatter is present across 109
notes (69 `evidence`, 19 `benchmark-spec`, 15 `reference`, 4 `tracker`, plus `results` and
`asset-registry`). On the surface this is the `typed-memory-no-registry` shape — there is no
`_type-registry.md` in this repo. But that is **correct by design, not a gap**: this is a public
spoke of project1, and the canonical OKF type registry plus its pre-commit guard
(`automation/lib/okf.py`) live in project1, which is where the federation graph is assembled (the
recent commits `e6ad0c7` / `e8f8024` typed 138 benchmark nodes precisely for that cross-repo
graph). The six types in use here are all on the project1 registry vocabulary. Recommendation:
**verify** the project1 registry recognizes `results` and `asset-registry` (the two singletons), and
if a commit-time guard ever runs against this repo it must read the project1 registry rather than a
local one. No local registry should be created here — that would fork the vocabulary.

## Decisions → policy (Q8)

The recurring decisions are already promoted into mechanism rather than re-litigated: the
determinism core (`lib/common.py`) is the policy form of "no unseeded randomness," the
answer-equality gate is the policy form of "don't trust speed without checking correctness," and
`BENCHMARKING-METHODOLOGY.md` is the policy form of the CV / config-parity / same-files /
power-plan rules. These are enforced in shared code, not in prose advice. Good.

## Bus-factor (Q9)

Single biggest one-person dependency: **the README/Layout bench index is a hand-maintained
invariant across ~37 directories, and it has already drifted ~12 benches behind.** Correctness of
"what's in the lab" rests on the maintainer remembering to add a README row every time a new bench
lands, and that memory has already lapsed a third of the time. This is the exact Q9 shape (a
hand-maintained cross-file invariant with no linter). The highest-leverage single change is to
generate the bench table from the per-directory docs (or at minimum add a CI/pre-commit check that
every top-level bench dir with a `run.py` appears in the README), moving "the index is complete"
from "the maintainer remembers" to "the check blocks." A secondary, smaller bus-factor: the whole
portfolio is one person's working model of which benches are load-bearing vs illustrative
(`README.md` tier/state column carries this, but only for the 25 listed).

## Dead weight

Very little, and nothing I'd kill on this read. The 20 GB on disk vs 844 tracked files is almost
entirely gitignored regenerable corpora (`_work/`, `*.parquet`, `.jars/`, `.venv/` per
`.gitignore`), which is the correct posture for a reproducible-from-generators repo — keep scores,
not raw events. Candidates to *label* rather than archive: a few benches are explicitly
"scaffold" / "demonstration" / "first pass (1 of N arms)" in the README state column
(`ocsf-fsi-compliance` scaffold, `ocsf-marimo-hunt` demonstration) — these are honestly labelled,
not dead. The one genuine risk is the inverse of dead weight: the 31 unlisted-but-committed benches
are *live weight that looks dead* because the README doesn't mention them, which is the Q2 finding
restated.

## Bottom line

This is a healthy, intent-aligned repo with a strong determinism/eval core and an honest
falsification habit, and it runs nothing unattended so the loop/RETHINK risk is n/a. The one real
finding is self-model drift: the public README documents 25 benches against ~37 on disk, which is
simultaneously the biggest bug (a third of the public lab is invisible), the dominant constraint
(publication, not measurement), and the top bus-factor (a hand-maintained index with no gate). Fix
that one thing — regenerate or gate the bench index — and the repo is in very good shape.

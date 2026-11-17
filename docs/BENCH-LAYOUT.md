---
type: reference
title: "Per-bench layout and the bench.yaml contract"
created: 2026-11-17
tags: [lab-benchmarks, layout, bench-index, contract]
---

# Per-bench layout and the `bench.yaml` contract

Every bench folder carries two things this page defines: a `bench.yaml` that feeds the generated index in
the top-level [`README.md`](../README.md), and a README whose sections come in a fixed order. A new bench
starts from both, and an existing bench gains whatever is missing while its prose stays where it is right.
Files are added, never moved or renamed, because essays on the site link to these paths.

## `bench.yaml`

One file per bench folder, written as flat `key: value` lines with no nesting, lists or multi-line
values, so that `scripts/bench_index.py` can read it with the Python standard library. The generator
takes everything after the first colon as the value, and a line starting with `#` is a comment.

The example below is for a made-up folder, `example-bench`, so its values describe no real bench.

```
name: example-bench
cluster: detection
title: Does the example rule fire on the planted events and stay quiet on the benign ones
status: first-pass
tier: B
claim_kind: demonstration
verdict: DEMONSTRATION
# the second file is an addendum appended after the first freeze
prereg: PRE-REG-example-2026-11-01.md; PRE-REG-example-addendum-2026-11-05.md
results: results/RESULTS.md
reproduce: python example-bench/run.py
pins: requirements.txt
essay: none
superseded_by: none
audited: 2026-11-17
```

- `name` is the folder name.
- `cluster` takes one of `detection`, `mapping-and-models`, `formats-and-lakehouse`, `catalogs-engines-cost`, `ai-security`, and decides which group of the index the row lands in.
- `title` is the "what it measures" cell, one line phrased as the question the bench answers.
- `status` takes one of: `published`, `first-pass`, `scaffold`, `spec`, `foundation`, `superseded`, `frozen-design`.
- `tier` is copied from the bench's own docs and is not changed by an audit; a tier that looks too high is raised with the owner instead. Where the docs give no tier, write `not stated`, with a parenthetical note if one helps (`not stated (vendor docs cited as Tier B)`); the generator folds older spellings such as `unstated in RESULTS` or `none` into `not stated`.
- `claim_kind` takes one of: `measured`, `demonstration`, `mixed`, `none`. Use `none` for a folder with nothing scored yet (a foundation corpus, a scaffold, a frozen design).
- `verdict` takes the primary verdict from the 2026-11-17 audit vocabulary (`SOUND`, `CAVEAT`, `DEMONSTRATION`, `CANNOT-FAIL`, `DRIFTED`, `SUPERSEDED`, `SCAFFOLD`). A bench whose `CANNOT-FAIL` or `DRIFTED` finding was corrected in the folder records the post-correction state and notes the correction in its README.
- `prereg` takes `none` or every pre-registration and addendum file in the folder, separated by `; `. A bench whose plan was fixed in a design, method or spec document, or in a section of its README, may name that file here, and the README says it is weaker than a hashed pre-registration. Each entry is a bare path relative to the bench folder; an annotation such as "pre-registration section, unhashed" goes in a `#` comment line, because `--strict` fails on any entry that is not an existing path.
- `results` is the entry-point results file, relative to the bench folder (several entries separated by `; ` are allowed).
- `reproduce` is the command that regenerates the result, run from the repository root (`python example-bench/run.py`). Most bench scripts resolve their inputs and `lib/` from their own file location, so they also run from inside the folder; a bench that needs the folder as its working directory says so with a leading `cd example-bench &&`.
- `pins` names the requirements file the result ran on.
- `essay` and `superseded_by` take a path, a URL or `none`.
- `audited` is the date of the last audit pass that checked the file against the code and data.

The generator expects 81 rows: the 80 bench folders plus `ontology-vs-schema-gate/`, whose files are all
frozen, so it cannot receive a `bench.yaml` and is written by the generator as a fixed row (`status:
frozen-design`, cluster `mapping-and-models`). `lib/`, `charts/`, `scripts/`, `workloads/` and `docs/`
are skipped by name and described by hand under the table. A folder without a `bench.yaml` gets a marked
"not yet described" row, so a missing file shows up in the index instead of hiding the bench.

```bash
python3 scripts/bench_index.py            # rewrite the index between the markers in README.md
python3 scripts/bench_index.py --check    # exit 1 if README.md is out of date
python3 scripts/bench_index.py --strict   # also fail on a value outside the lists above or a prereg/results path that does not exist
```

When a new bench is added, `--expect` takes the new total until the default is raised in the script.

## Bench README sections, in order

Every bench README, new or existing, carries these sections in this order, adding what is missing and
leaving existing prose in place where it is right.

1. **What it measures.**
2. **Result**, with one sentence saying whether the number is measured or follows from construction.
3. **What would have made it fail**: the baseline, the negative control, or "none".
4. **Pre-registration**: the path and whether its hash verifies, or "none".
5. **Reproduce**: the exact commands, the inputs that must exist first, and the expected runtime if the docs record one.
6. **Results**: the entry-point file, then the dated supplements in order.
7. **Versions and pins.**
8. **Evidence tier and limits.**
9. **Corrections**, each dated.

A folder with several dated RESULTS files gets a README that names which one is current. Corrections are
made in place with a dated note in the form `*(corrected YYYY-MM-DD: ...)*`, so a reader can see what
changed and why, and a number is never silently replaced. Where a bench's `run.py` regenerates its
RESULTS file, the same correction also goes in the README, because a later re-run would erase the note.

## Pre-registration files

A pre-registration is never written or edited after the scored run it governs. The protocol for new ones
(hash file, frozen-at stamp, who froze it, amendments appended below the hashed body) is principle 12 of
[`BENCHMARKING-METHODOLOGY.md`](../BENCHMARKING-METHODOLOGY.md), and principle 11 sets out the
construction test each headline number is checked against.

# D3FEND AI artifacts vs OCSF ai_* objects (R8)

A document comparison rather than a measurement. For each AI-specific artifact or event noun proposed on
the D3FEND side (the residual nouns, issue #586, PR #601, the MVP classes posted on #606, and the proposed
`MachineLearningEvent` family) it asks whether OCSF has a counterpart, at what grade and in which version,
and for each OCSF `ai_*` object or draft class it asks the same question the other way. The output is a
25-row vocabulary table meant for the D3FEND #606 and OCSF #1754 discussions.

## What it measures

Grades on a four-value rubric (exact, partial, wrong-kind, none), set in `METHOD.md` before the table was
built, after an ontology category checklist (continuant or occurrent; carrier, content or occurrence; kind
or role). OCSF availability is recorded per version: released 1.9.0, main (1.10.0-dev at `d1cbd619`) and
the #1754 draft.

## Result

No row reaches exact in either direction: D3FEND to OCSF grades 0 / 9 / 2 / 3 and OCSF to D3FEND 0 / 4 /
3 / 4 (exact / partial / wrong-kind / none, `RESULTS.md`, reproduced byte-for-byte by the verifier). The
sharpest mismatch is the model itself, where OCSF `ai_model` is an identity descriptor and the D3FEND
classes denote the learned parameters. These grades are one reader's judgement against pinned
definitions, so they are neither measured nor constructed; they are analysis, and the files say so.

## What would have made it fail

Any row could have graded exact, and the row set was fixed before grading. There is no second grader on
this table (contrast `../m1-r1-blind-regrade/`, which re-graded a different table blind), so the check on
the grades is the verifier's read of each row against the pinned sources.

## Pre-registration

`METHOD.md` stands in for a pre-registration, because nothing is timed. Its sha256 `4b756f62…f6ee2e0`
verifies (checked 2026-11-17) and matches the value at the top of `RESULTS.md`. It records "frozen by
agent before table was built; not owner-reviewed", stamped 2026-11-09T22:56:49Z, and the verifier found
the build script and outputs dated after that, while noting that file times cannot prove grading started
only after the freeze. `METHOD.md` cites the residual-noun source by a path in the lab's private notes,
which is not in this repository; the file is frozen and is left as written.

## Reproduce

```bash
python3 -I d3fend-ocsf-ai-alignment/build_table.py   # rebuilds vocabulary-table.csv and .md from sources/
```

Standard-library Python only. The fetched source files are checked in under `sources/`; refreshing them
needs the `gh` CLI and the network, with the commands listed in `RESULTS.md`.

## Results

- `RESULTS.md`: grade counts and what the rows say.
- `vocabulary-table.md` and `vocabulary-table.csv`: the 25 rows.
- `VERIFICATION.md`: independent verification (VERIFIED-WITH-FIXES).

## Versions and pins

Every source is pinned to a tag or commit in `METHOD.md` (OCSF `v1.9.0`, OCSF main `d1cbd619`, PR #1754
head `08d6f530`, D3FEND develop `048c6936` with the TTL hashed). `requirements.txt` records that nothing
is pip-installed. OCSF main and both open PRs move weekly, so a row should be re-pinned before it is
quoted.

## Evidence tier and limits

No tier is stated in the folder. Single-reader judgement against public, pinned definitions, without a
reasoner or an OWL bridge, covering the R8 scope only.

## Corrections

- 2026-11-09: verification fixes recorded in `VERIFICATION.md` and in place in `RESULTS.md`.
- 2026-11-17: one first-person phrase recast in `RESULTS.md`; this README added.

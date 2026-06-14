# De-gamed BENCH-A — context collapse vs unmodified SigmaHQ on real APT29 telemetry

The lab-built BENCH-A (R1/R2) measured that OCSF coarsening degrades *adversary-relevant* detection more
than routine detection — but its Karen flag was real: the lab authored the rules, planted the chain, and
chose the grains, so the result was *gameable*. This is the de-gamed re-run that removes all three levers.

## What's de-gamed

| lever | R1/R2 (gameable) | here (de-gamed) |
|---|---|---|
| detection rules | lab-authored, written against the store schema | **unmodified upstream SigmaHQ**, cloned verbatim, run via pySigma→SQL with only a table-name substitution |
| attack data | lab-generated synthetic chain | **MITRE ATT&CK APT29 evaluation** telemetry (OTRF/Mordor, day 1) |
| adversary/routine split | lab's judgment | each rule's **own `attack.tXXXX` tags** vs MITRE's published APT29 technique set |
| coarsening grains | lab-chosen | documented volume-driven defaults, applied **blind** to the rules (below) |

## Metric (no lab-defined needle)

For each rule that fires on Store F (fidelity), `recall_loss = 1 − matches_N / matches_F`. Store F is the
"good pipeline" the hypothesis's null needs. The loss is decomposed into the two failure modes R1 named:
**blinding** (recall→reduced, the detection goes dark) and **over-match** (matches_N > matches_F: the
coarsening broke an exclusion filter, so the rule cries wolf — precision loss). Headline = Δ mean blinding
recall-loss between the adversary-tail and routine classes.

## Result (Tier B)

Adversary-relevant detections lose **~2× the recall** and go **fully blind ~2× as often** as routine
detections under the same documented coarsening — see `results/RESULTS.md`. The blinded adversary rules are
the expected ones: Base64/encoded-PowerShell and long-script-block rules killed by command-line /
script-block truncation, which is APT29's encoded-PowerShell tradecraft. The disproportionality
**replicates** with nothing lab-authored. Caveats: modest fired-rule sample (APT29 exercises a subset of
techniques), one dataset, one coarsening config; recall-loss is measured against the fidelity store, not
absolute per-event labels; and the independent-reviewer sign-off that Store N resembles what shops actually
build remains the open Tier-A gate.

## Coarsening-sensitivity sweep (2026-06-14) — the contrast holds at every truncation cap

This bench is deterministic (real fixed APT29 telemetry, unmodified SigmaHQ rules, no RNG),
so there is no stochastic seed band — the honest way to bound the +0.188 is a *coarsening
curve*. `coarsening_sweep.py` sweeps the dominant knob, the field-length truncation cap (the
one that kills APT29's encoded-PowerShell tradecraft), holding rare-DNS at < 3 and reusing
run.py's `score_stores()` so the scoring is unchanged; only Store N is rebuilt per cap.

| truncation cap (chars) | adversary recall-loss / blind% | routine recall-loss / blind% | Δ (adv − routine) |
|--:|--:|--:|--:|
| 256 | 0.236 / 21% | 0.100 / 8% | +0.136 |
| 128 | 0.305 / 28% | 0.100 / 8% | +0.205 |
| **64** (documented) | **0.348 / 31%** | **0.160 / 16%** | **+0.188** |
| 32 | 0.402 / 38% | 0.308 / 28% | +0.094 |
| 16 | 0.540 / 48% | 0.360 / 36% | +0.180 |

Two things the sweep settles. First, the **disproportionality is positive at every cap** —
adversary-relevant rules always lose more recall than routine rules, the delta ranging
**+0.094 to +0.205** with the published documented-64-char point at **+0.188**, mid-to-upper
in that range rather than a cherry-picked maximum. Second, the **mechanism is monotone**: as
the cap tightens 256 → 16 both classes blind more (adversary 0.24 → 0.54, routine 0.10 →
0.36) because heavier truncation eventually eats the routine rules' fields too — the delta
narrows at 32 (where routine catches up) and re-widens at 16, but never inverts. So the
finding is robust to the one corpus parameter most open to a "you picked the cap" rebuttal.
Machine-readable in `results/coarsening_sweep.json`. The remaining axis — a different
SigmaHQ rule-set commit — is left as future work (re-cloning at a pinned commit), as is the
synthetic-testbed sibling's chain-variant (BENCH-A `robustness.py` re-draws background noise
only; a different ATT&CK chain needs the frozen battery generalized to read IOCs from ground
truth).

## Store N coarsening provenance (documented, blind to rules)

Each knob is a documented volume-driven normalization behavior, not a choice to make a rule fail:

- **Field-length truncation** (CommandLine, ScriptBlockText, registry Details, CallTrace → 64 chars): SIEMs
  cap long string fields by default (e.g. Splunk `TRUNCATE`, max-field-length limits); long encoded
  payloads and call stacks are lost past the cap.
- **Rare-value sampling** (DNS `QueryName` seen < 3× dropped): cardinality/volume controls on high-cardinality
  fields.
- **Auxiliary-field shedding** (ParentCommandLine, Hashes, Signature/SignatureStatus, OriginalFileName,
  QueryResults, GUIDs, StartAddress/Function): a lean store keeps the core event and drops enrichment.
- **Single timestamp** (event time → ingestion time only): the time-collapse mode.

Both stores carry identical columns (canonical Sigma field names) so one compiled rule runs against either;
the only variable is the coarsening.

## Reproducibility

**pySigma 1.3.3 / sigma-cli 3.0.2 / pySigma-backend-sqlite 1.1.3** — pinned in `requirements.txt`.
These versions determine which rules compile and which SQL is emitted; a SigmaHQ rule-set update can
shift the set of rules that parse cleanly, which changes the fired-rule counts and the headline recall
numbers. To reproduce exactly: pin the SigmaHQ rule-set to a specific commit rather than using
`--depth 1` against `HEAD`. The run that produced these results used the tip of the `main` branch as
of the benchmark date (see `results/RESULTS.md` for the exact commit hash logged at run time). For
byte-stable reproduction, replace the `git clone --depth 1` step below with a pinned commit:

```bash
git clone https://github.com/SigmaHQ/sigma _work/sigma
git -C _work/sigma checkout <commit-hash-from-results>
```

## Reproduce

```bash
# 0. install pinned deps
pip install -r requirements.txt
# 1. data: OTRF Security-Datasets APT29 day 1 (14 MB zip -> 385 MB JSONL) into _work/
curl -sL -o _work/apt29_day1.zip \
  https://raw.githubusercontent.com/OTRF/Security-Datasets/master/datasets/compound/apt29/day1/apt29_evals_day1_manual.zip
python -c "import zipfile; zipfile.ZipFile('_work/apt29_day1.zip').extractall('_work')"
# 2. rules: clone SigmaHQ verbatim into _work/sigma (pin commit for exact replay -- see Reproducibility)
git clone --depth 1 https://github.com/SigmaHQ/sigma _work/sigma
# 3. project -> build stores -> score
python prepare_corpus.py
python run.py
```

`_work/` (the 385 MB dataset + the SigmaHQ clone) is gitignored; the projector, stores, and runner are the
committed, reproducible parts. Tier B, single machine, one public dataset.

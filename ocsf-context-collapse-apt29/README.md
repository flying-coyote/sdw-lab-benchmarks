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

## Reproduce

```bash
# 1. data: OTRF Security-Datasets APT29 day 1 (14 MB zip -> 385 MB JSONL) into _work/
curl -sL -o _work/apt29_day1.zip \
  https://raw.githubusercontent.com/OTRF/Security-Datasets/master/datasets/compound/apt29/day1/apt29_evals_day1_manual.zip
python -c "import zipfile; zipfile.ZipFile('_work/apt29_day1.zip').extractall('_work')"
# 2. rules: clone SigmaHQ verbatim into _work/sigma
git clone --depth 1 https://github.com/SigmaHQ/sigma _work/sigma
# 3. project -> build stores -> score
python prepare_corpus.py
python run.py
```

`_work/` (the 385 MB dataset + the SigmaHQ clone) is gitignored; the projector, stores, and runner are the
committed, reproducible parts. Tier B, single machine, one public dataset.

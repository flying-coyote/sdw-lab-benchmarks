---
type: benchmark-spec
title: "PRE-REG: schema-only pipeline vs ontology-backed gate on the 925-row OCSF crosswalk corpus (the null of H-ONTOLOGY-EFFECTIVENESS-01)"
status: frozen-design (frozen when the main session commits this file; harness addendum owed before any scored run)
created: 2026-11-17
hypotheses: [H-ONTOLOGY-EFFECTIVENESS-01]
evidence-tier: B (design); labels Tier B if Jeremy adjudicates, Tier D if the agent fallback is used
cost-estimate: "$0 compute (local Java + Python); about 1.7 h of owner adjudication for phase 1, about 1 h optional for phase 2"
tags: [pre-registration, m6, ontology, d3fend, ocsf, crosswalk, disjointness, reasoner, schema-validation, null-test]
---

# PRE-REG: schema-only vs ontology-backed gate, same corpus (2026-11-17)

**Status.** Design frozen at the commit that adds this file. Nothing has been scored: no arm has run, no injection has been generated, no label has been written. The arms, injector and scorer do not exist yet, and their code is hashed in a harness addendum (section 11) before the first scored run. Under M6 a smoke test on the 7-field toy in `~/project1/02-projects/d3fend-wall/ocsf_d3fend_validation.py` is not a scored run; a smoke test on any corpus row is. A design change after this freeze needs a new dated block that says why, and the old block stays.

## 1. Why this bench exists

H-ONTOLOGY-EFFECTIVENESS-01 (`~/project1/01-knowledge-base/hypotheses/extended-hypotheses.md:1872`) names its own null: "well-run schema validation and ordinary detection testing deliver the same effectiveness gains without an ontology", and its falsification condition is "a controlled comparison where a schema-only pipeline (no ontology, no reasoner) catches the same wrong mappings and exposes the same coverage gaps as the ontology-backed one". The essay-23 research ledger lists that comparison as the first gap (`internal-effectiveness-ledger.md`, "Gaps"), and the synthesis's owner decision 2 defaults to pre-registering and running it before drafting past essay-state 1 (`00-SYNTHESIS.md:153`). The published evidence it would test is ledger row 9: 925 rows, 364 testable, 231 distinct classes, 231 of 231 injected type-crossings caught, 15 raw firings split into about 8 genuine coarse mappings and about 7 field-typer approximations (`~/project1/02-projects/d3fend-wall/ocsf-d3fend-validation-corpus-result.md:48-66`, site `catching-the-mistake.astro:139-160`).

**Scope.** This bench tests the correctness clause only (wrong mappings caught). It does not test the coverage clause (the D3FEND Wall's 76 of 436 techniques with no detection), which needs a different instrument, so a REFUTES here leaves the coverage half of the hypothesis open and the report must say that.

## 2. What the existing gate actually decides (read from code, 2026-11-17, not run)

I read `ocsf_d3fend_corpus_validation.py` (sha256 below) before writing the arms, because the fairness of the comparison depends on it, and four facts change what the 2026-06-04 numbers mean.

1. **The corpus run never loads D3FEND.** `PREFIX` declares nine classes by D3FEND IRI (`UserAccount, UserGroup, Process, File, NetworkNode, NetworkSession, URL, ServiceApplication, Session`), one subclass axiom (`NetworkSession ⊑ Session`) and one `owl:AllDisjointClasses` over the first eight. The first-pass toy (`ocsf_d3fend_validation.py`) was merged into the full ontology; the corpus run was not.
2. **The reasoner's verdict reduces to a lookup.** Each tested mapping becomes a class that is a subclass of its target artifact and its source artifact. `source_type()` only ever returns one of the eight disjoint artifacts, so the class is unsatisfiable exactly when `source_art != target_art` and `target_art != Session`. Under this axiom set an inequality check over the same two tables reproduces every verdict, which this bench tests directly (arm S3 below) rather than assumes.
3. **The 231/231 injected catch is true by construction.** `inject()` declares each corrupted class a subclass of two artifacts it has already chosen to be disjoint (`wrong = next(a for a in DISJOINT_SET if a != sart)`, so the replacement is always `UserAccount`, or `UserGroup` when the source is a user). It confirms the reasoner runs correctly; it does not measure detection power, and because it corrupts the artifact label rather than the OCSF path, a schema-only arm has no path to inspect, so the 231/231 cannot be compared across arms at all.
4. **The gate tested 231 of 325 testable mappings.** Classes are keyed by `(schema, source)` and only the first-seen OCSF target is kept (`if c not in classes`). Counted on 2026-11-17 from the frozen parser, without reasoning: 925 parsed cells, 715 distinct `(schema, source, ocsf_path)` triples, 325 triples with both groundings, which collapse to 231 `(schema, source)` classes, so 94 testable triples were never tested.

The matrix has not changed in content since the 2026-06-04 run: the only commit after it (`04352caa`, 2026-06-23) adds a `created:` frontmatter line.

## 3. Unit of analysis

The unit is the `(schema, source_field, ocsf_path)` triple, and every arm is scored on all 715 triples, with abstention (the arm cannot type one side, so it passes the row without a judgment) reported as its own outcome. Scoring only the gate's 325 testable triples would select the test set on one arm's coverage. The legacy 231-class run is kept as a reproduction check only (section 8, step R).

## 4. Arms (a ladder, so the result says which rung did the work)

The ladder runs from the green check a pipeline ships today to the ontology gate, so a tie or a gap can be attributed to a specific addition rather than to "ontology" as a whole.

- **S1, shape check.** The path exists in the OCSF 1.8.0 class (walked attribute by attribute through the class and object definitions, array markers stripped, as in `frontier_behind_constraint_2026_11_16.py:in_full`), and the source field's data-type family is compatible with the OCSF attribute's declared type (`ip_t`, `port_t`, `timestamp_t`, `string_t`, `integer_t`, `long_t`, `boolean_t`, hash and MAC types; families fixed in the harness addendum). The crosswalk files do not carry source data types (checked 2026-11-17: the six crosswalks have field, OCSF path, transform note and confidence columns only), so the source side uses an authored leaf-token → type-family table written from the source schemas' documentation, frozen at the addendum. This is the check `what-your-data-means.astro` describes as the one that "goes green".
- **S2, schema-plus-kind check (the competent-engineer arm, and the arm that tests the null).** S1, plus an entity-kind check built from no D3FEND material. The target kind is the OCSF 1.8.0 object type of the deepest object-typed segment of the path, normalised through OCSF's own `extends` chain (`device` and `network_endpoint` both extend `endpoint`; `process` extends `process_entity`; checked against `schema-ocsf-1.8.0-api-2026-11-16/objects/*.json`). The source kind comes from a namespace-first typer written from each source schema's documented structure: ECS field sets (`user.*`, `process.*`, `file.*`, `host.*`, `source.*`, `destination.*`, `url.*`), UDM nouns and their sub-objects (`principal.user.*` is a user, `principal.ip` is a host, `principal.process.*` a process), ASIM entity prefixes and suffixes (`SrcUsername`, `TargetProcessName`, `DvcHostname`), Zeek `id.orig_h`-style tuples, and a token rule for CIM's flat names. A row passes if the two kinds are equal or one is an ancestor of the other under `extends`; a row the typer cannot type passes and counts as an abstention. The typer is written from the source schema documentation and the OCSF object list before any arm runs, and the author may not consult `SEG_RULES`, `SEG_ARTIFACT` or the 15 firings while writing it. That last rule is honour-system, because those tables are already published, and the harness addendum records who wrote the typer and what they had read.
- **S3, the gate's tables without a reasoner (ablation).** The frozen gate's own `ground_path()` and `source_type()`, imported unchanged, with the verdict `source_art != target_art`. No OWL, no disjointness axiom, no subclass axiom. This isolates what the reasoner adds over the tables it reasons about.
- **O1, the gate as built (primary ontology arm).** `ocsf_d3fend_corpus_validation.py` at its frozen sha256, imported unchanged by a thin wrapper that emits one class per triple (fixing the first-seen collapse in section 2.4) and reasons with ELK via ROBOT 1.9.10. The per-triple wrapper is a declared deviation from the as-built run; the unchanged as-built run is step R.
- **O2, the same axioms inside the shipped ontology.** O1's grounding and disjointness axioms merged into the full D3FEND ontology (`~/d3fend-ontology/src/ontology/d3fend-protege.ttl`, commit `12e2762`, working tree clean on 2026-11-17; all nine gate class names are declared in it, checked by grep), so D3FEND's shipped subclass tree and any shipped disjointness are in play. This is the only rung where a reasoner can reach a verdict a table lookup cannot.
- **O0, shipped D3FEND only.** The full ontology plus the groundings with no added disjointness. Ledger row 9a says D3FEND ships 3 disjoint pairs and none among the core artifacts (site-only source), so the expectation is about zero catches, and the arm is in the bench to measure that rather than cite it.

**How the comparison treats the disjointness assertions D3FEND does not ship.** The one `AllDisjointClasses` axiom over eight artifacts was authored by Jeremy (the hypothesis author) and is not in D3FEND. The bench treats it as part of the ontology arm, because the hypothesis is about "a security ontology", not about D3FEND as shipped, but every result line names it: O1 and O2 are reported as "D3FEND class names plus one authored disjointness axiom", and O0 is reported beside them so no reader can take an O1 catch as something D3FEND catches. The schema-world counterpart of that axiom is S2's equality rule, which treats every pair of distinct OCSF object kinds as incompatible unless `extends` relates them. That is a stronger, closed-world disjointness than O1's eight-way assertion, so the comparison is between an explicit, adjudicated disjointness and an implicit, total one.

## 5. Error sets

### E1, injected errors (path-level, seeded, stratified)

A new injector replaces the existing artifact-label one. Seed `20261117`. For every one of the 715 triples it draws one replacement OCSF path per stratum, uniformly from the eligible candidates, where candidates are the OCSF paths in the same class's first column of the matrix plus, for E1-INV only, generated non-paths. A triple with no eligible candidate in a stratum is ineligible there, and eligible counts are reported per stratum. OCSF types come from the 1.8.0 object and class JSONs, and the three class definitions not yet fetched (`process_activity`, `file_activity`, `account_change`) are fetched from `https://schema.ocsf.io/1.8.0/api/` before the injector runs, with sha256 in the addendum.

- **E1-K, kind-crossing and type-preserving.** The replacement path ends in a leaf with the same OCSF data type as the original but sits in an object of a different entity kind (`user.name` → `process.name` or `file.name`; `src_endpoint.ip` → a non-endpoint `ip`). The replacement is valid OCSF and type-correct, so S1 passes it by construction, and it is the silent error the essays describe. The two kind systems in the bench do not cover the same ground, since OCSF has 178 objects and the gate's `SEG_ARTIFACT` grounds about 14 segments, so a uniform draw would often land where `ground_path()` returns nothing and O1 abstains by vocabulary rather than by judgment. E1-K is therefore split before drawing:
  - **E1-K1 (the deciding stratum).** The original and the replacement ground to different artifacts under `ground_path()` **and** to different OCSF root kinds under the S2 `extends` normalisation, so both kind systems agree the swap is a crossing. Candidates are restricted to this set before the seeded draw. The decision thresholds key on E1-K1.
  - **E1-K2 (vocabulary coverage).** The replacement is a crossing under OCSF root kinds but sits outside the gate's grounding vocabulary (or the reverse). Reported with its own named reading in section 7, never in ΔK.
- **E1-T, data-type-crossing.** The replacement leaf's OCSF type differs from the original's (`ip_t` → `timestamp_t`). Every arm with a type check should catch it; reported, not decisive.
- **E1-R, same-kind role swap.** `src_endpoint.*` ↔ `dst_endpoint.*`, `actor.user.*` ↔ `user.*`, `actor.process.*` ↔ `process.*`. Kind-based checks are expected to miss these in every arm (ledger row 14's inference, Tier D). Reported as the shared blind spot.
- **E1-INV, invalid path.** An attribute appended to an object that does not carry it, confirmed absent by the 1.8.0 walk. S1 should catch every one; reported as a harness sanity check.

For O0, O1 and O2 an injected row is processed exactly like a real row: the replacement path is grounded with `ground_path()` and the source typed with `source_type()`, so the injection is never handed to the reasoner as a pre-chosen artifact pair.

### E2, real errors in the corpus (labelled by a frozen rubric)

The ~8 "genuine coarse mappings" were nominated by the ontology gate itself, so O1's recall on them is 100% by definition. The caution applies to recall: these rows are never used to estimate O1's recall on its own. ΔR (section 7) is still symmetric, because every flag from any arm gets labelled under the pooling below, so S-arm-only catches enter the count on the same footing as the 15 O1 firings. The 8/7 split in the result note is not recorded per row (for example `network.ip_protocol → connection_info.protocol_name` is in neither published list), so all 15 are re-labelled here under the rubric.

**Label pool**, drawn before any arm runs:

- the 15 triples the as-built gate fired on;
- a seeded random sample (seed `20261117`) of 100 of the remaining 700 triples, drawn from all 715, testable or not.

After the arms run, a second blind batch adds every triple any arm flags that is not yet labelled, mixed with 10 already-labelled triples as consistency decoys. Pooling means recall on errors that no arm flags is estimated only from the random sample, and the report says so.

**Rubric** (written now, applied per triple, with the source crosswalk's row and the OCSF 1.8.0 attribute description shown, arm outputs hidden, row order shuffled):

- `correct`: the OCSF attribute is an accepted home for the source field's meaning, with the same entity, role and direction.
- `defensible`: a reviewer reading OCSF 1.8.0 would accept the home, though another is better.
- `lossy`: the right role, but the entity grain differs (an application landing on a host endpoint) or part of the value is dropped.
- `wrong`: a different attribute, entity, role or direction.

A second field records `kind_crossing` (yes, no or unclear): does the source field denote a different kind of thing than the OCSF object it lands in? It is judged by identity, not relation, the rule the gate's own adjudication used, so `process_path → process.file.path` is not a crossing because the field denotes the process's file. A **real error** is `lossy` or `wrong`. A **type-crossing real error** is a real error with `kind_crossing = yes`, and that is the class every arm here claims to catch. `unclear` rows are listed and excluded from the primary metrics.

**Adjudicator.** Jeremy, blind to arm outputs. **Fallback agent protocol**, used only if he declines and labelled Tier D: two independent blind readers from different providers (a Claude subagent and Gemini via `agy -p`) apply the rubric to the same packet, agreement becomes the label, and disagreement becomes `unclear`. Either way, a 20-row seeded subset is double-read and Cohen's kappa is reported. LLMs may produce labels; they never score an arm. The label CSV is hashed and recorded before the arms run on that set (before the post-run pooled batch, the first batch's hash is recorded and cannot change).

### E3, secondary set (a different corpus, reported separately, never pooled)

Two arm-independent sources of valid-but-wrong mappings from `~/sdw-lab-benchmarks/ocsf-deterministic-mapper`:

- **E3a.** The 71 alias-mapper valid-but-non-gold rows already adjudicated (`results/alias-wrong-but-valid-adjudicated-2026-11-16.csv`: 60 wrong, 7 defensible, 4 lossy). Labels are reused as-is, Tier D, single reader. Correction 5 of the results file shows 43 of the 60 are artifacts of a substring matcher; they remain valid test items for a gate, but they are easier than organic errors, and the report says so.
- **E3b.** The frontier proxy's valid-but-non-gold predictions (25-28% of prompts by the 2026-11-16 re-score). Run 2 only, because it is the one run whose gold-stripped inputs are file-evidenced (correction 2). Run 3's schema batch is excluded in any case, and fields whose gold path does not exist in 1.8.0 (`src_endpoint.hw_info.model`, `dst_endpoint.hw_info.model`) are dropped. Distinct `(source, field, predicted_path)` pairs are deduplicated, a seeded sample of up to 80 is drawn, and the sample is labelled under the E2 rubric.

E3 is phase 2 and optional on owner time. Its results never enter the decision rules below except where a rule names it.

## 6. Metrics

Each `(triple or injection, arm)` pair gets exactly one outcome:

| Outcome | Item is an error | Item is correct |
|---|---|---|
| arm flags it | **loud catch** | **false alarm** (loud, wrong) |
| arm passes it with a judgment | **silent miss** | quiet pass |
| arm abstains (cannot type a side) | **silent miss (abstain)** | quiet pass (abstain) |

Reported per arm, per stratum and per error set: catches, silent misses (with abstentions split out), false alarms on items labelled `correct` or `defensible`, abstention rate over all 715 triples, and catch rate = catches / eligible items, with abstentions counted as misses. Every catch rate is also reported on the **jointly typed** subset (items where both compared arms type both sides), so a gap caused by one arm's source typer abstaining can be told apart from a gap in checking. For paired comparisons on E1-K1 (O1 vs S2, O1 vs S3, O2 vs O1) the exact McNemar test on discordant pairs is reported as descriptive; the E2 and E3 counts are too small for a test and are reported as counts.

## 7. Decision rules (thresholds frozen)

Notation: `ΔK` = O1's catch rate minus S2's on E1-K1, in percentage points, abstentions counted as misses (the jointly typed ΔK is reported beside it, and if the two differ in which verdict band they fall in, the verdict is recorded as TEMPERS with the reading *typer-driven*). `ΔR` = type-crossing real errors in E2 caught by O1 minus those caught by S2. `ΔF` = O1's false alarms minus S2's on E2 items labelled `correct` or `defensible`.

- **SUPPORTS** (the ontology gate catches wrong mappings a competent schema-only pipeline misses): `ΔK ≥ +10` **and** `ΔR ≥ +3`, **and** `ΔF ≤ ΔR − 1`, so the extra catches are not bought with an equal number of false alarms.
- **REFUTES** (the null holds for the correctness clause, which is the hypothesis's own falsification condition): `ΔK ≤ +5` **and** `ΔR ≤ +1` **and** `ΔF > −3` (the ontology gate does not buy materially fewer false alarms either). This clause already covers the case where S2 is ahead on both.
- **TEMPERS**: every other outcome, including mixed-direction results (S2 ahead on injected errors, O1 ahead on real ones, or the reverse). Named readings are recorded if they occur. *Precision only*: catches tie (`|ΔK| ≤ 5`, `|ΔR| ≤ 1`) but `ΔF ≤ −3`, so the authored disjointness buys fewer false alarms, not more catches. *Injected only*: `ΔK ≥ +10` but `ΔR ≤ +1`, so the advantage does not reach errors people actually made. *Typer-driven*: see the ΔK note above.

**E1-K2 reading (reported, outside the verdict).** If S2 catches materially more E1-K2 items than O1 (O1 abstains on them), the finding is that the gate's grounding vocabulary covers less of OCSF than OCSF's own object types do. That bears on how far the gate can be trusted unattended, not on whether reasoning beats lookup.

**Attribution rules** apply whatever the verdict:

- **Reasoner.** If O1 and S3 agree on every non-`Session` item, the reasoner added nothing over its tables on this corpus, and any O1 advantage over S2 is attributed to the authored kind tables plus the disjointness judgment. The essay may then say "an authored typed vocabulary with disjointness", not "a reasoner".
- **Shipped ontology.** If O2 differs from O1 on any item, that difference is where D3FEND's shipped axioms do work, and it is reported row by row. If O2 equals O1, D3FEND contributes the class names only.
- **Shipped disjointness.** O0's catch count is reported next to O1's in every summary line.
- **Coverage.** No verdict here moves the coverage clause.

**Confidence.** The hypothesis is registered unscored (PROPOSED, gated-pending), so no score moves from this bench. The verdict goes to the karen-evaluator → hypothesis-validator → contradiction-detector gate and Jeremy rules on any wording change.

## 8. Procedure (deterministic, no LLM calls in scoring)

1. **R, reproduction.** Run the as-built `ocsf_d3fend_corpus_validation.py all` unchanged. It must print 925 rows, 364 testable, 231 classes, selfcheck clean, 15 fired (the same 15 class names as `corpus_validation_fp.json`), and 231/231. Any difference stops the bench and is reported as harness drift; Java 25 against the original Java 17 is the likely suspect.
2. Freeze the harness addendum (section 11) with code hashes.
3. Draw the E2 label pool and generate E1 from the fixed seed; hash both.
4. Adjudicate the E2 pool (first batch) and hash the labels.
5. Run every arm over the 715 triples and all E1 strata.
6. Adjudicate the pooled second batch, blind and with decoys.
7. Score, apply section 7, and write `RESULTS-<date>.md` with actual against predicted (section 9).
8. Phase 2, optional: E3a, then E3b sample, label and score.

Outputs land in `ontology-vs-schema-gate/results/`. Nothing outside this directory is rewritten. The unchanged gate writes its JSON next to itself, resolves the matrix at `../external-engagements/ocsf-crosswalk-field-matrix.md` and the jar at `/tmp/robot.jar`, so step R runs on hash-checked copies laid out as `ontology-vs-schema-gate/repro/d3fend-wall/ocsf_d3fend_corpus_validation.py` and `ontology-vs-schema-gate/repro/external-engagements/ocsf-crosswalk-field-matrix.md`, with the pinned jar placed at `/tmp/robot.jar` (its sha256 checked there), and the hub originals stay untouched.

## 9. Predictions (M6 fields, frozen)

- **Predicted result.** S3 matches O1 on every item except triples whose target grounds to `Session`, where O1 passes and S3 flags; I expect that from reading the code (section 2.2), and the bench checks it. S2 against O1 on E1-K1: `|ΔK| < 5` pp, with S2 more likely ahead than behind because its equality rule is a total disjointness. On E1-K2, S2 well ahead of O1 (I expect most of O1's E1-K2 outcomes to be abstentions), which is a coverage finding outside the verdict. On E1-T and E1-INV, S1, S2 catch nearly all and O0, O1, O2, S3 catch only those that also cross kinds. On E1-R, every arm near zero. On E2: `|ΔR| ≤ 1` and `ΔF` between −4 and +2, so most likely **REFUTES**, with *precision only* the main alternative. I put roughly 70% on not-SUPPORTS. O0 catches about zero. O2 equals O1 on most items, with any differences coming from D3FEND's subclass tree touching `ServiceApplication`, `URL` or `Session`.
- **Predicted confidence delta.** None numeric, because the hypothesis is unscored. Predicted wording consequence: the correctness clause narrows to "kind discipline with explicit disjointness catches type-crossing mappings whether or not it lives in an ontology", which shifts the hypothesis's weight onto the coverage clause and onto subsumption, the two things a flat kind check cannot do.
- **Assumption under test.** That the 2026-06-04 gate's effectiveness on this corpus comes from its reasoner and ontology rather than from the kind tables and the one authored disjointness axiom it reasons over.
- **Falsifier of this prediction.** Any one of these proves the prediction wrong:
  - O1 differs from S3 on any non-`Session` item, which would mean my reading of the reasoner is wrong;
  - `ΔK ≥ +10` on E1-K1;
  - `ΔR ≥ +3` on E2.

## 10. Threats to validity

- **Authored axioms and a single author.** Jeremy wrote the hypothesis, the gate, the disjointness axiom and the corpus, and is the named adjudicator. Blinding, shuffled order, decoys and the kappa subset reduce the risk but do not remove it, and an independent second reader on E2 would do more than any extra row.
- **Injected against real errors.** E1 errors are generated by a rule, so a catch rate on E1 says how an arm handles that rule's errors. E2 is small (about 115 to 150 labelled triples, with maybe 10 to 25 real errors), and E3 sits on a different corpus.
- **One corpus.** One six-schema matrix into seven OCSF 1.8.0 classes, built by Jeremy and agents from crosswalk documents that have not been independently verified. The coarse eight-kind vocabulary limits where subsumption can help, so a tie here does not test the case where a finer source typing (`ExecutableFile ⊑ File`) meets a coarser OCSF target. That case is named as a follow-on, not claimed.
- **Typer dependence.** O1 and S3 share `source_type()`, which produced about 7 of the 15 firings. S2 uses a different typer, so an S2-vs-O1 gap can come from typer coverage rather than from reasoning. The abstention rates and the S3 ablation exist to separate the two, and a secondary analysis re-scores the E2 pool with the adjudicated source kind in place of every typer.
- **Already-seen data.** The 15 firings and the gate's tables are public and were read while designing this bench, so only the S arms, the new injector and the labels are prospective, and the S2 typer rule in section 4 is honour-system.
- **Toolchain drift.** ROBOT 1.9.10 has to be re-downloaded (section 12), and the host now runs OpenJDK 25.0.5 against the original Java 17; step R guards both.
- **Version labels.** The D3FEND checkout describes itself as `0.16.0-299-g12e2762` (2026-07-22). The hub's 1.6.0 cache is JSON, not the TTL, so the ontology release label of that commit is confirmed and recorded at harness freeze.

## 11. Harness addendum (owed before step 3; append below, do not edit above)

To record:

- sha256 for the wrapper, the S1/S2/S3 code, the S1 leaf-type table, the S2 typer, the injector and the scorer;
- sha256 for `robot.jar` 1.9.10 and the three fetched OCSF class JSONs;
- the D3FEND release label for commit `12e2762`;
- who wrote the S2 typer and what they had read;
- the E1 eligible counts, the E2 pool hash and the first label-batch hash.

## 12. Inputs (sha256 recorded 2026-11-17)

| Input | Path | sha256 |
|---|---|---|
| Corpus (field matrix) | `~/project1/02-projects/external-engagements/ocsf-crosswalk-field-matrix.md` | `8317d3ad57f0e9357a98b300dee007b53057c89f6139120553469f4e8a5be7cc` |
| Gate script (corpus) | `~/project1/02-projects/d3fend-wall/ocsf_d3fend_corpus_validation.py` | `8de6557d6189f68f4b5b9a9a5b23dbf4e24604c2b3ae07a7bb9a21c6c08da443` |
| Gate script (7-field toy, smoke test only) | `~/project1/02-projects/d3fend-wall/ocsf_d3fend_validation.py` | `236ee1065c2c0b573be3242178f286b24af897592b451e3098aa689b6bfb4f9c` |
| Gate output, firings | `~/project1/02-projects/d3fend-wall/corpus_validation_fp.json` | `91469aed356a4d0035c81fc3cbccfd3f15a9085ab86e849bdd44158318f5ec9e` |
| Gate output, inject | `~/project1/02-projects/d3fend-wall/corpus_validation_catch.json` | `3edf7503e1f799bd8961c588a1441a09a8c327c68f009047fe211c291c33b772` |
| Gate result note | `~/project1/02-projects/d3fend-wall/ocsf-d3fend-validation-corpus-result.md` | `4f2e8679158776368adbbe56e08caa4ca7b8b8997ebe1376ff44ca03ac6baf6f` |
| Gate plan note | `~/project1/02-projects/d3fend-wall/ocsf-d3fend-validation-corpus-plan.md` | `15dae9318a798976331bf0a6136543cf99e196ff046e8ee6780a75f6e073838a` |
| D3FEND ontology (O0, O2) | `~/d3fend-ontology/src/ontology/d3fend-protege.ttl` (commit `12e2762`, clean) | `4ddb80135ec4ee2ff397ad4b42b264f27b8e94d1c379514c53b5ae806a4c2038` |
| OCSF 1.8.0 API fetch (manifest of all files) | `~/sdw-lab-benchmarks/ocsf-deterministic-mapper/schema-ocsf-1.8.0-api-2026-11-16/` | `fafebc0db944e968aa470f5e6cbedfcf355e2ff71b0a37e90c49376902a277c0` |
| OCSF fetch metadata | `.../schema-ocsf-1.8.0-api-2026-11-16/FETCH-META.json` | `dae533671b50dc4829e4cd4ded8705626690fca1954028a03bc68757d485758c` |
| Source crosswalk, CIM | `~/project1/02-projects/external-engagements/cim-ocsf-crosswalk.md` | `73c361fa11d42f89bf8b60cd45243d34eb6655b292c08f7efdbee56c7afb7ecc` |
| Source crosswalk, UDM | `.../udm-ocsf-crosswalk.md` | `756efb488d8edffb4da6c20282c5b2c5c143a4f3b7d98b7f062892560a306066` |
| Source crosswalk, ASIM | `.../asim-ocsf-crosswalk.md` | `6307758b17519963aa7289359aab56c758e37d74537ead0b276948f10c5c70df` |
| Source crosswalk, ECS | `.../ecs-ocsf-crosswalk.md` | `79d2592b3d86b487a4a280a9fc32b0a66fce7ed091dab2aafd0fa77f2e51b7d7` |
| Source crosswalk, OTel | `.../otel-ocsf-crosswalk.md` | `8278b19dd66f5425a14cb6814ec0e4570398410b68fcfb7701bf93f42558a271` |
| Source crosswalk, Zeek | `.../zeek-ocsf-crosswalk.md` | `c891220892d62d11c6b0b4fd39141bb3d1a56556dc1a7c0364f0ef8ff91d8eca` |
| E3a labels | `~/sdw-lab-benchmarks/ocsf-deterministic-mapper/results/alias-wrong-but-valid-adjudicated-2026-11-16.csv` | `c76d4ce279bdbd00396b48bd960d02a6b81d602fa121a094865ee4e12b6d0945` |
| E3b prompts | `~/sdw-lab-benchmarks/ocsf-mapping-oracle/_frontier/frontier_prompts.json` | `c6a98ecbb8491c706689fad9b3ac252c18870cbcedcb785c640f98c6e8dbdfee` |
| E3b predictions, run 2 | `~/sdw-lab-benchmarks/ocsf-mapping-oracle/_frontier/predictions_run2.json` | `feb9448c5e0798dd958d9b3e21710a9620dd0050c78089f46700b31801437bd1` |
| E3b run-2 directory (manifest) | `~/sdw-lab-benchmarks/ocsf-mapping-oracle/_frontier/run2/` | `c538f5c670924981e3f7de422b4768d0e8bde12beeb76d17a0b5c98b1cd79163` |
| Frontier run 1 predictions (not used, recorded) | `~/sdw-lab-benchmarks/ocsf-mapping-oracle/_frontier/predictions.json` | `26c374b63cdc8b89a8492904b5afd60f289e3a0ab9b974ed45fe555b0c9347fe` |
| Frontier run-3 directory (excluded, recorded) | `~/sdw-lab-benchmarks/ocsf-mapping-oracle/_frontier/run3/` | `d85183b26823de869d72c888cf0f19d15bf95534347387422477e914f39d2056` |
| Re-score script (path walker reused) | `~/sdw-lab-benchmarks/ocsf-deterministic-mapper/frontier_behind_constraint_2026_11_16.py` | `689718d8dd2c75a4fdabe6fdfd27cb4e241fbdb49f5206b9797edf2e78b76ea8` |
| Re-score results | `.../ocsf-deterministic-mapper/results/results-frontier-constrained-2026-11-16.json` | `4c25361fe87feb878fa6c4958fec072781f45377fc34f2e78cb5c3bf10923a4d` |
| Re-score write-up | `.../ocsf-deterministic-mapper/results/RESULTS-FRONTIER-CONSTRAINED-2026-11-16.md` | `3c35857a8a3e63965cddced328d73a73fd2214fdb86acc0dcf0cf0c29912d951` |
| Hypothesis file | `~/project1/01-knowledge-base/hypotheses/extended-hypotheses.md` | `890580925d2fa0b5f20dbe6e6c74ec0ce71a0df76dee125d821e7f8b7d6c60d4` |
| Effectiveness ledger | `~/project1/02-projects/securitydataworks/content/drafts-2026-11/23-research/internal-effectiveness-ledger.md` | `c9cbf082da5d31d26db3364b6137641fe6888f2cee875bc5d5a4a55b3e069b88` |
| Synthesis | `.../23-research/00-SYNTHESIS.md` | `f045b8da030177749a7b612294402240eb0d754a295ed039c9a7031cbcc30d44` |
| Site page | `~/sdw-site-articles-2026-11/src/pages/writing/detection/catching-the-mistake.astro` | `cd6bd744525e4869e9591c62ad15759283f1ffba391923625156edef6dca5791` |
| Site page | `~/sdw-site-articles-2026-11/src/pages/writing/detection/what-your-data-means.astro` | `f275e7af9282cfe9f1edc69c25842dbea4b6acf9ebd22815c7bcff9a2e599b8b` |
| ROBOT | `/tmp/robot.jar` (the path hard-coded in the gate) | **missing**: re-download 1.9.10 and hash at the addendum |

## 13. Cost and runtime

- **Compute.** $0: local Python and Java. ELK on the stub module takes seconds per pass, and the first-pass full-ontology run took 3.69 s on this class of host. Every arm over 715 triples plus all four E1 strata should finish in under 10 minutes, including the ROBOT JVM start-ups.
- **Network.** One ROBOT jar download (about 80 MB, from the obolibrary GitHub release) and three OCSF class JSON fetches.
- **Owner time, phase 1 (E2).** About 125 to 165 rows at about 40 s each, so roughly 1.5 to 1.8 h, which fits two sittings within the one-hour-a-day budget.
- **Owner time, phase 2 (E3b).** Up to 80 rows, under 1 h, optional.
- **Agent fallback.** If used for labels, two readers over about 250 rows, likely under $3.
- **Build time.** One session to write the wrapper, S1 to S3, the injector and the scorer.

## 14. Hand-offs

- The hub index row in `~/project1/02-projects/securitydataworks/PRE-REGISTRATION-LEDGER.md` is owed and is the main session's to add; this spawn did not edit it.
- The freeze is the main session's commit of this file in `~/sdw-lab-benchmarks`.
- Section 2's findings (the corpus run does not load D3FEND, the inject is tautological, 94 testable triples went untested) bear on ledger row 9 and on `catching-the-mistake.astro:139-160` whatever this bench later shows. Correcting those pages is a separate, gated edit.

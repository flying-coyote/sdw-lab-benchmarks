---
type: benchmark-spec
title: "HARNESS ADDENDUM to the ontology-vs-schema gate pre-registration (section 11)"
status: harness built, step R reproduced, S2 typer pending, E1 not generated, no arm scored
created: 2026-11-17
prereg: PREREGISTRATION.md (frozen at lab commit e7deceb, not edited)
---

# Harness addendum (PREREGISTRATION.md section 11), 2026-11-17

This file is the section 11 addendum. It records what the harness build decided where the prereg left a choice open, every input and code hash, and what is still owed before a scored run. The prereg itself is untouched. Owner rulings that bound this build came through the coordinating session on 2026-11-17 and are cited as "ruling 0" to "ruling 3".

## 1. Toolchain and step R (reproduction)

| Item | Value |
|---|---|
| Java | OpenJDK 25.0.5.0.3 (build 25.0.5.0.3+1-1-24.04.1-Ubuntu, 2026-10-24) |
| ROBOT | 1.9.10, from `https://github.com/ontodev/robot/releases/download/v1.9.10/robot.jar`, at `tools/robot.jar` |
| ROBOT jar sha256 | `16a73c074f3df359a7338a84b4e0788785fe06117f931bb9796e9619ea776105` (82,604,728 bytes; the release publishes no checksum to compare against) |
| Python | 3.12.3 |
| D3FEND checkout | `~/d3fend-ontology` at `12e2762` (2026-07-22), clean. `git describe` gives `0.16.0-299-g12e2762`; the Makefile at that commit sets `D3FEND_VERSION ?=1.4.0`; the 1.4.0 tag (2026-03-31) is not an ancestor, and the commit is an ancestor of the 1.5.0 (2026-08-04) and 1.6.0 tags. Release label: post-1.4.0 development build, pre-1.5.0. |

**Step R result: PASS.** `harness/step_r_repro.py` imports the byte-identical copy `repro/d3fend-wall/ocsf_d3fend_corpus_validation.py` (sha256 `8de6557d…`, equal to the hub original) and sets only `mod.ROBOT` to `tools/robot.jar` (ruling 1). The matrix is read from the byte-identical copy `repro/external-engagements/ocsf-crosswalk-field-matrix.md` (`8317d3ad…`). Output, `results/step-r-reproduction.json` and `results/step-r-stdout.txt`:

- 925 rows parsed, 364 testable, 231 distinct testable classes, selfcheck clean (unsat `[]`);
- 15 fired, and the 15 class names equal `corpus_validation_fp.json`'s `fired` list;
- 231 injected, 231 caught;
- the regenerated `corpus_validation_fp.json` and `corpus_validation_catch.json` in `repro/d3fend-wall/` are byte-identical to the hub's (`91469aed…`, `3edf7503…`), so Java 25 against the original Java 17 changed nothing.

ROBOT exit codes were checked, because the gate's `reason()` ignores them: selfcheck rc 0 with nothing unsatisfiable, then corpus and inject both rc 1 with ROBOT's own "unsatisfiable" report. ROBOT 1.9.x exits 1 after writing `--dump-unsatisfiable` whenever unsatisfiable classes exist, so rc 1 with that report is the expected success shape, and the wrapper treats any other combination as a crash.

## 2. Input verification (step 1)

All 26 file inputs in prereg section 12 matched except one, and the three directory manifests matched with the method `find . -type f | sort | xargs sha256sum | sha256sum` run inside each directory (the method was not written in the prereg; it reproduces all three recorded values, so it is recorded here).

**D1, the one mismatch (ruling 0, accepted as benign).** `~/sdw-site-articles-2026-11/src/pages/writing/detection/catching-the-mistake.astro`: the prereg's `cd6bd744525e4869e9591c62ad15759283f1ffba391923625156edef6dca5791` is the blob at site commit `61b79c1`. The live page is `92857c9b8b55c162c91b7bc45dbc6b5ccee6a1c997a9602ef33f7dd107eac35d` from commit `d813d69` (2026-11-17 11:28:35), the correction prereg section 14 said was owed. No arm, injector, scorer or step R reads that page, so the citation pins the `61b79c1` blob.

## 3. OCSF 1.8.0 fetches

The three missing class definitions and the type dictionary were fetched from `https://schema.ocsf.io/1.8.0/api` on 2026-11-17 by `harness/fetch_ocsf_missing_classes.py` (same method as `fetch_ocsf_1_8_0_full_2026_11_16.py`: GET, `json.dump(indent=1, sort_keys=True)`). They sit in a sibling directory, `~/sdw-lab-benchmarks/ocsf-deterministic-mapper/schema-ocsf-1.8.0-api-classes-2026-11-17/`, so the pinned manifest of the 2026-11-16 directory (`fafebc0d…`) is unchanged (re-checked after the fetch). `/api/version` returned 1.8.0.

| File | sha256 |
|---|---|
| `class_process_activity.json` (uid 1007) | `c7dafa6d17de02119b60ce14df735a81ef1a4f2ed42c45cea61506f78e4d346b` |
| `class_file_activity.json` (uid 1001) | `e3b7e54b163022880baf4f591707df42060fe6517df62c579fa2b1943ed226ad` |
| `class_account_change.json` (uid 3001) | `0b23e3268e696fb78e6b5ea7ed0702fa299eacfe7b88f115c7ba1ab001d5b6f6` |
| `data_types.json` (needed for the type families, D5) | `9323ac82b3eb2de0920278fd7174ef33ff5b7af9ae43af7ee4d2ce2ce943d3bd` |
| `FETCH-META.json` | `cd80558d208bdb2c36350f2cadce9b515709f4cf9f801857e291ef08a9b1bc6a` |

The class files were fetched twice (the second run added `data_types`), and the class hashes were identical both times.

## 4. Decisions the prereg left open

Each is the conservative reading I could defend from the prereg's text. D6 is the one that can move the verdict, and it is flagged for confirmation.

- **D2, jar location (ruling 1).** The jar lives in `tools/`, not `/tmp/robot.jar`. Every ROBOT call in the harness goes through the pinned path, and `common.verify_pins()` checks its hash before any arm runs.
- **D3, a triple's class.** The 715 triples are distinct `(schema, source, ocsf_path)`, and 91 of them appear in more than one class section. A triple's class is the first section it appears in (matrix order); the full list is kept in `classes` and shown on the adjudication sheet. Path validity, leaf type and the injector's candidate pool all use the first class. The section-aware parser in `common.parse_cells()` is asserted equal, cell for cell, to the gate's own `parse_matrix()`.
- **D4, matrix notation on the OCSF side.** A trailing `.*` (`dst_endpoint.*`) means the object itself, and a final brace set (`actor.process.parent_process.{name,pid,uid}`) is valid only if every member is, with a leaf type only when all members share one. Without this, those rows read as invalid paths purely because of how the matrix writes them. With it, 11 distinct `(class, path)` pairs remain invalid in 1.8.0 (for example `http_request.url.text`, `user.sid`, `process.exit_code`). Those are real shape errors and stay in.
- **D5, OCSF type families.** Every OCSF type is mapped to a family through `/api/data_types` base types:
  - **ip:** `ip_t`, `subnet_t`.
  - **port:** `port_t`.
  - **timestamp:** `timestamp_t`, `datetime_t`.
  - **integer:** `integer_t`.
  - **long:** `long_t`.
  - **float:** `float_t`.
  - **boolean:** `boolean_t`.
  - **hash:** `file_hash_t`.
  - **mac:** `mac_t`.
  - **json:** `json_t`.
  - **object:** `object_t`.
  - **string:** `string_t` and every other `string_t`-based subtype (`username_t`, `hostname_t`, `file_path_t`, `url_t`, `email_t`, `uuid_t` and so on).

  The prereg's examples (`user.name` → `process.name` is type-preserving) need those subtypes grouped as `string`, which is why they are.
- **D6, S1 type compatibility (FLAGGED FOR CONFIRMATION).** A source family passes a target family when they are equal, or when:
  - both are numeric (`integer`, `long`, `float`);
  - the target is `port` and the source is numeric, or the reverse;
  - the target is `json`;
  - the target is `object` and the source is `object`.

  A scalar source on an `object` target is an abstention, and so is an unknown or `ambiguous` source family. A cast the matrix cell itself declares for that source token, `(enum)` or `(int)`, sets the source family to `integer`, the post-transform type, and an injected item keeps its original row's cell because the injector changes only the path.

  The reason is that the matrix legend defines `(enum)` as a string-to-integer bridge and `(int)` as a cast. A strict family match would flag every correct enum-bridge row. Those flags would add false alarms to S1 and through it to S2, which moves ΔF, and would also make S2 "catch" E1-K items for a reason unrelated to kind (the prereg says S1 passes E1-K by construction). The fixture dry run confirms S1 catches 0 of 5 K1 injections under this rule.

  Owner check: if the intended S1 is the stricter "documented type only, no declared transforms", `arms.COMPAT`/`declared_cast` change and the code hash moves before E1 is generated.
- **D7, S2 composition and target kind.** S2 flags when S1 flags or the kinds differ. It abstains when S1 did not flag and either kind is unknown, and passes otherwise. The target kind is the OCSF object type of the deepest object-typed segment, normalised to its root under `extends` (`network_endpoint` and `device` → `endpoint`; `process` → `process_entity`; the chain stops before `_entity`/`object`). A row passes when the source kind is the target root or descends from it. Because the target is already a root, this is root equality. A top-level scalar path (`time`, `severity_id`) has no target kind, so S2 abstains on it unless S1 flags.
- **D8, E1-K strata.** These need the same type family (D5, with `object` a family, so object-to-object swaps are type-preserving).
  - **K1:** both paths ground under `ground_path()` to different artifacts, and both have OCSF root kinds that differ.
  - **K2:** a root-kind crossing where a gate grounding is missing on either side, or a gate-artifact crossing where a root kind is missing.
  - **Disagreement:** both systems type both sides but disagree on whether the swap is a crossing. These go in neither stratum, and the number of such candidate pairs is reported as `k_disagree_pairs`. This is the conservative reading of "both kind systems agree the swap is a crossing".
- **D9, E1-T.** Both families known and different, with any family including `object` and `json`.
- **D10, E1-R.** The swaps are `src_endpoint` ↔ `dst_endpoint`, `actor.user` ↔ `user` and `actor.process` ↔ `process`, applied as a path prefix with the `actor.*` rules first. The swapped path must be in the same class's first column and valid, so a triple has at most one R candidate.
- **D11, E1-INV.** The candidates are every attribute name carried by any OCSF 1.8.0 object or by any of the seven classes, appended to the deepest object-typed prefix of the original path when that object does not carry the name. Each candidate is confirmed invalid by the walk. A triple with no object-typed segment, an invalid original or a brace-set original is ineligible.
- **D12, seeding.** Each `(triple, stratum)` draw uses `random.Random(int(sha256("20261117|<stratum>|<tid>"), 16)).choice(sorted(candidates))`, so one triple's draw does not depend on any other's eligibility. Triple id is `T` + the first 12 hex digits of `sha256("<schema>|<source>|<ocsf>")`.
- **D13, O arms.** One OWL class per item (fixing the first-seen collapse, as the prereg declares). An item abstains when `ground_path()` returns nothing or `source_type()` is not confident.
  - **Axioms per arm:**
    - O1 is the gate's own `PREFIX` + `disjoint_ttl()` + item classes, reasoned alone.
    - O2 is the same stub merged with `d3fend-protege.ttl` (`robot merge --input <d3fend> --input <stub> reason`).
    - O0 is `PREFIX` + item classes merged with D3FEND, with no `AllDisjointClasses`. `PREFIX`'s only non-declaration axiom, `NetworkSession ⊑ Session`, is already shipped in D3FEND (`d3fend-protege.ttl:22089`), so O0 adds no authored axiom.
  - **Reading the result:** unsatisfiable classes are read from ROBOT's log, because the dump also lists the superclasses that unsatisfiable classes reference (first noticed as nine "extra" d3f classes on the fixture). The gate's own method, align# IRIs in the dump, is computed beside it and must agree, or the run stops.
  - **Shipped D3FEND:** with the stub's one deliberately conflicting probe class, the merged D3FEND reports exactly one unsatisfiable class, so the shipped ontology contributes none of its own under ELK.
- **D14, the S1 source data-type table.**
  - **Authorship.** `harness/s1_source_type_table.csv` (422 `(schema, leaf token)` rows) was not written by hand by the harness author. Six delegated readers (Claude Sonnet subagents, one per schema) authored it on 2026-11-17 under the frozen brief `harness/s1_table_work/BRIEF.md`, from official documentation only. They saw only the source field names (`request-*.json`), never the OCSF targets, the crosswalks or the gate. Each reader wrote only its own `response-*.csv`, which I checked on disk.
  - **Merge and rulings.** `harness/build_s1_table.py` merges the six files and applies the harness author's literal rulings on nine flagged judgment calls, recorded per row in `harness_ruling` with the reader's original family kept in `reader_family`:
    - CIM `dest_port` and `file_hash` move to `long` and `string`;
    - Zeek `community_id` moves to `string`;
    - Zeek `orig_l2_addr` and `resp_l2_addr` stay `mac` on the field doc's mac-logging note;
    - the four OTel ISO 8601 timestamp rows stay `timestamp`, with paraphrased evidence replaced by verbatim text I checked against opentelemetry.io.
  - **Spot checks.** I also checked UDM `md5`, `ip` and `mac` against the live page.
  - **Families.** 254 string, 45 long, 19 timestamp, 17 ip, 16 object, 14 hash, 11 integer, 8 mac, 5 float, 5 boolean, 2 port, 1 json, 4 ambiguous and 21 abstain (reader counts before the rulings: string 252, long 44, hash 16, port 3).
  - **Caveats.**
    - Much of the evidence column is the fetch tool's paraphrase, not verbatim text.
    - ECS was read from unpinned `main` of `elastic/ecs` (`generated/ecs/ecs_flat.yml`, version file 9.6.0-dev).
    - The last ~13k characters of the UDM field list page were not read.
    - The OTel semantic-conventions version is not shown on the registry pages.
    - CIM was read from the help.splunk.com CIM 6.0 pages, because docs.splunk.com returned 403.
  - **Tier.** The table is Tier B for what each field's type is (vendor documentation of its own schema), with these caveats.
- **D15, adjudication sheet.**
  - **What it shows.** Each row carries:
    - the matrix cell, which includes the transform hint and the `~` low-confidence marker, both the crosswalk's own data;
    - every row in the per-schema crosswalk whose first column holds that source field;
    - the OCSF 1.8.0 description of each segment on the path.
  - **What it hides.** It carries no arm output and no pool origin.
  - **Extra column.** The prereg's rubric fields are `label` and `kind_crossing`. I added an optional `source_kind_adjudicated` column because prereg section 10 promises a secondary analysis "with the adjudicated source kind in place of every typer", which needs that field.
  - **Format.** The rubric is the leading `#` lines (read with `comment='#'`).
  - **Key file.** The item-to-triple key, with `origin` (fired/random) and the kappa flag, is a separate file. The adjudicator should not open it.
- **D16, pool seeds.**
  - The 100-triple random sample is `random.Random(20261117).sample(sorted(remaining 700 tids), 100)`.
  - The pool is shuffled with seed 20261118.
  - The 20-row kappa subset is drawn with seed 20261119.
  - Batch 2 draws its 10 decoys with seed 20261120 and shuffles with 20261121.
  - Item ids are `E2<batch>-` + the first 8 hex digits of `sha256("20261117|<batch>|<tid>")`.
  - The 15 fired triples come from `fired_detail` in the hash-pinned `corpus_validation_fp.json`.
- **D17, order of step 3.** Prereg step 3 draws the E2 pool and generates E1 together. I drew the E2 pool (batch 1) now, because the coordinator asked for the blind sheet and the draw depends on no arm code. E1 generation waits until the S2 typer exists and its hash is recorded here. The injector does not call the typer, but if the typer's author finds a defect in `common.py`'s OCSF kind code, fixing it after E1 exists would break the freeze.
- **D18, dry runs.** `harness/dryrun.py` runs all six arms, the injector and the scorer on a synthetic fixture: 12 invented `fx.*` source fields over real OCSF 1.8.0 paths, asserted to share no triple and no source field with the corpus. It writes to `results/dryrun/`.
  - S2 ran there only through `FIXTURE_TYPER`, a seven-entry stub keyed on the invented `fx.<object>` names, which is test scaffolding and not the S2 typer.
  - One fixture row uses a real schema name (`Elastic ECS`) with an invented field, so the real S1 table is loaded and exercised.
  - The fixture verdict line ("REFUTES") is an artefact of the fixture and carries no evidential weight; the summary file says so.
- **D19, scorer scope.**
  - **Built:**
    - catch rates per arm and stratum, with abstentions as misses;
    - joint-typed rates for every stratum and for the pairs O1-S2, O1-S3, O2-O1, O1-S1, S2-S1 and O1-O0;
    - exact McNemar on E1-K1 for the three prereg pairs;
    - ΔK, joint ΔK, ΔR, ΔF and the section 7 verdict with its named readings;
    - the attribution lists (O1 vs S3 non-Session disagreements, O2 vs O1 differences, O0 and O1 flag counts);
    - E2 counts, decoy consistency and Cohen's kappa on the double-read subset;
    - a count of E1 catches where the same arm also flagged the original row (inherited flags).
  - **Label handling:** label values are validated and a bad value stops the scorer.
  - **Not built:**
    - The section 10 secondary analysis for the O arms, because it needs an OCSF-kind → D3FEND-artifact map the prereg does not define. The S2 half is built.
    - E3 (phase 2).

## 5. What the harness author read (section 4 blindness rule for S2)

This session read `ocsf_d3fend_corpus_validation.py` in full, including `SEG_RULES`, `SEG_ARTIFACT` and `source_type()`, and saw the 15 firings in the step R output. It therefore did not write the S2 source typer (ruling 2). It also wrote the OCSF-side kind code in `common.py` and the S2 composition in `arms.run_s2`, neither of which types a source field.

**S2 typer, pending.** A fresh author writes `harness/s2_source_typer.py` exposing `source_kind(schema: str, field: str) -> str | None`, which returns an OCSF 1.8.0 object name from `schema-ocsf-1.8.0-api-2026-11-16/objects/` or `None` to abstain.

- **Schema spellings:** `schema` is one of the gate's spellings, `Splunk CIM`, `Google UDM`, `Microsoft ASIM`, `Elastic ECS`, `OpenTelemetry` or `Zeek`.
- **Field list:** the fields to cover are the `source_fields` lists in `harness/s1_table_work/request-*.json`.
- **What it may read:**
  - the OCSF 1.8.0 object list and object JSONs;
  - the official public schema documentation for the six sources;
  - those request files.
- **What it must not open:**
  - `repro/`, `results/` and `harness/arms.py`;
  - `harness/common.py`, `harness/inject.py` and `harness/score.py`;
  - `harness/s1_source_type_table.csv` and `harness/s1_table_work/response-*`;
  - `ADJUDICATION-SHEET.csv` and the E2 key;
  - the hub's `02-projects/d3fend-wall/` and the six crosswalk files;
  - this addendum's sections 1 and 4.

  `arms.run_s2` refuses to run until the file exists and rejects any return value that is not an OCSF object. Its author, what they read and its sha256 are appended here before E1 is generated.

## 6. Code and data hashes (frozen before the E2 pool draw)

| File | sha256 |
|---|---|
| `harness/common.py` | `9cc3cd61f2d7ae0cf411f039267419e89d690ed5081bbd8d2ca71533da52a0eb` |
| `harness/arms.py` (S1, S2 composition, S3, O0, O1, O2) | `8da16c45c5feca143af72d0b5b4354baad6bd94fb276e67c96a13c044e51008f` |
| `harness/inject.py` (E1 injector) | `84be6b34e97840ffdc7fc8c29e714c5657d86ad100cee8bc15452b8b0d5ee6c7` |
| `harness/pool.py` (E2 pool, sheet, batch 2) | `0612c1e2eac3ff1c67796a9041904457d3277f5d67f921fb8f05e07b6738faf7` |
| `harness/score.py` (scorer) | `fa008b39ac48f8c024d50029ece2fb6033bad6e2392983d01ea532ecfffe5185` |
| `harness/run_scored.py` (scored-run driver, not run) | `4a646c55f31023e556496dbc239170009401da241770473457f081dd2065d444` |
| `harness/step_r_repro.py` (step R wrapper) | `9bd6702d7fc32de255afaeb967c54d8302ea9a9d59a1a783d1b828f1d039e87f` |
| `harness/dryrun.py` (fixture dry run) | `3a2f9677841c09fecfa99ebf3218424ece61870ae13f03cb7eb813cf7a6cf3f0` |
| `harness/fetch_ocsf_missing_classes.py` | `61f78e5df139e218ed09f6b662141bf4b5ee41633b2cfb9e1065678c189551fc` |
| `harness/build_s1_table.py` | `fc1018fc16659d4474bedee3e0e892b6694b24fb207f1fb176c476ac7deea793` |
| `harness/s1_source_type_table.csv` (S1 leaf-type table) | `a7c76fb7c0db567fb7a69c068bc1d41137c046b0206a3f61ccc4aa7f8c1a8609` |
| `harness/s1_table_work/BRIEF.md` | `c0d738b5159da7d160292c1f363c19d4db87f74f9dbc689cc1be63f977cdbc28` |
| `harness/s1_table_work/request-{asim,cim,ecs,opentelemetry,udm,zeek}.json` | `1f35bb8f…0eb`, `f1a37c2d…93c7`, `d2d0854f…cb2`, `f8639da7…e2`, `6a8aaddd…5c`, `99d516c0…44ad` |
| `harness/s1_table_work/response-{asim,cim,ecs,opentelemetry,udm,zeek}.csv` | `21c82992…ecfb`, `2e7ec717…fd77`, `220616b0…6ee`, `ffd8d724…734`, `f70fd7c0…adf`, `7b733e3d…ecfb` |
| `harness/s2_source_typer.py` | **pending** (separate author) |
| `tools/robot.jar` | `16a73c074f3df359a7338a84b4e0788785fe06117f931bb9796e9619ea776105` |
| `repro/d3fend-wall/ocsf_d3fend_corpus_validation.py` | `8de6557d6189f68f4b5b9a9a5b23dbf4e24604c2b3ae07a7bb9a21c6c08da443` (= hub) |
| `repro/external-engagements/ocsf-crosswalk-field-matrix.md` | `8317d3ad57f0e9357a98b300dee007b53057c89f6139120553469f4e8a5be7cc` (= hub) |
| `results/step-r-reproduction.json` | `34a5e8209b47ccb3d88a8535da62d4784b4a6b25a7ed03f455a8e9844a27b4f3` |
| `results/step-r-stdout.txt` | `890bc46c2b28aba3d87bf102e9cf5f8826331d37ea68a35942f6be3edddf16df` |

Full request and response hashes are reproducible with `sha256sum harness/s1_table_work/*`. The `__pycache__` directories under `harness/` and `repro/d3fend-wall/` are Python bytecode, are not inputs, and can be deleted.

## 7. E1 and E2 records

- **E1 eligible counts:** pending (D17).
- **E2 pool (batch 1) and blind sheet:** see section 8, appended after the draw.
- **First label-batch hash:** pending owner adjudication.

## 8. E2 pool, batch 1 (drawn 2026-11-17, after the section 6 hashes)

`python3 -I harness/pool.py batch1 ADJUDICATION-SHEET.csv results/e2-pool-key-batch1.csv`, with `pool.py` at `0612c1e2…` as recorded above.

| Artifact | sha256 |
|---|---|
| `ADJUDICATION-SHEET.csv` (blind, unlabelled, 115 rows, rubric in the `#` header) | `69332f7e5dad14856a0b136f3107e7d015c404377960c0aeb89f5eb19a9fd76e` |
| `results/e2-pool-key-batch1.csv` (item id → triple, origin, kappa flag; not for the adjudicator) | `dd3d35237e40c852275bfca479f9609de89e210145b03506c09ff2d3474d081d` |

The pool is 15 fired + 100 random = 115 distinct triples, with 20 rows flagged for the kappa double read in the key only. Eight rows have no crosswalk row whose first column holds the source field, and the sheet says so on those rows. Six rows have an OCSF path that does not exist in 1.8.0, and their description cell says "(path not found in OCSF 1.8.0 …)". That is an OCSF fact rather than an arm output, though it does tell the adjudicator what S1's path check will say on those six.

`pool.py batch2` was dry-run on three synthetic flags into the session scratchpad, and produced 3 flagged + 10 decoys. Nothing from that run is kept in the lab tree.

For scoring, copy the labelled sheet and its key into the score directory as `labels-batch1.csv` and `key-batch1.csv` (and `labels-batch2.csv`/`key-batch2.csv`, plus `labels-kappa.csv` for the second read of the kappa subset). That is the layout `score.py` reads.

## 9. Still owed before the scored run

1. **S2 source typer.** Fresh author per section 5; append its sha256, author and reading list here.
2. **Owner confirmation of D6** (S1 compatibility with declared casts). If it changes, re-hash `arms.py` here.
3. **Generate E1.** Run `python3 -I harness/inject.py results/e1-items.jsonl results/e1-counts.json` and record the eligible counts and the items hash here (prereg step 3).
4. **Adjudicate batch 1** (prereg step 4). Jeremy labels `ADJUDICATION-SHEET.csv` blind, about 115 rows at about 40 s each, roughly 1.3 h. Hash the labelled file here before any arm runs; the fallback is the Tier-D two-reader protocol.
5. **Run the arms.** Steps 5 to 7: `run_scored.py` (it refuses to start without the E1 and label hashes), then `pool.py batch2` and its blind adjudication, then `score.py` and `RESULTS-<date>.md`.
6. **E3** (phase 2, optional) has no harness yet.

## Main-session rulings (2026-11-17)

- **D6 confirmed (default compatibility rule).** The pre-registration asks for a strong schema-only baseline; a strict documented-type-only match would flag every correct enum-bridge row and hand S1/S2 false alarms and kind-irrelevant "catches", which weakens the null unfairly. The default rule stands as hashed.
- **S1 table authorship deviation accepted and disclosed.** The prereg said hand-written; it was written by six agent sessions from official docs under a frozen brief, with nine literal rulings by the harness author. This is a threat to validity for S1 only and is reported with the result.
- **D3FEND version note.** The pinned checkout `12e2762` is a post-1.4.0 development build, not the v1.6.0 release the D3FEND Wall uses. O2 runs against the pinned build as frozen; any claim about "full D3FEND" in the write-up names this build, and a v1.6.0 re-run of O0/O2 is a separate, later addendum if wanted.
- **`tools/robot.jar`** is gitignored (82 MB; its sha256 is recorded above), as are `__pycache__/` directories.
- **S2 typer frozen (2026-11-17).** `harness/s2_source_typer.py` sha256 `421b745365417c05c4dfbaaf1591cb716bfcdc74e63a14f3ce6180b8ffedcc68`, written by a fresh agent under the blindness rule; its exposure statement is in `harness/S2-TYPER-NOTES.md` (saw OCSF's own d3fend object names and forbidden file names only; no typing used them). Interface questions resolved by the main session from `arms.py:117-140`: the harness passes the full source string (`it["source"]`), and it normalises kinds itself through `extends` (`C.root_kind`, `C.kinds_related`), so raw OCSF object names are correct. Coverage check: all 715 corpus triples resolve without error, 539 typed.
- **E1 generated and frozen (2026-11-17), seed 20261117.** `results/e1-items.jsonl` sha256 `bc677e81e07a1a03ddb59e6af815c821c46e9b7ccd5b4af5041532a6da0f6a83`; `results/e1-counts.json` sha256 `6b4b001c9d2705a2f6dbf85c6601101727c185b4b27ce3065fe5ffe5975111d8`. Eligible per stratum: K1 274 (the decision stratum), K2 362, T 676, R 130, INV 588; 23 kind-disagree pairs excluded from both K strata (D8). No arm has run on any corpus row. Remaining: owner blind labels for `ADJUDICATION-SHEET.csv` (hash the label file), then `run_scored.py`.

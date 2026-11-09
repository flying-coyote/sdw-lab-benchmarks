METHOD.md sha256 `4b756f629b8332081f4f043c019f9185cee09297900b3d4df347637ccf6ee2e0`, frozen 2026-11-09T22:56:49Z (UTC wall clock; no durations measured, so the WSL timer-drift note does not apply): frozen by agent before run; not owner-reviewed.

# R8 results: D3FEND AI artifact nouns vs OCSF ai_* objects

Analysis, not a bench, so there is no variance to report; every grade is a reading of pinned
definitions (METHOD.md lists the pins). The table is `vocabulary-table.csv` and
`vocabulary-table.md`, regenerated with `python3 -I build_table.py`.

## Grade counts (25 rows)

| Direction | exact | partial | wrong-kind | none |
|---|---:|---:|---:|---:|
| D3FEND to OCSF (14 rows) | 0 | 9 | 2 | 3 |
| OCSF to D3FEND (11 rows) | 0 | 4 | 3 | 4 |

No row reaches exact in either direction, which seems right for two vocabularies that grew a few
months apart without looking at each other, and the partials are mostly granularity or version
gaps rather than disagreements about what the thing is.

## What the rows say

- The model is the sharpest mismatch. OCSF `ai_model` (in 1.9.0) is an identity descriptor with
  four attributes (`ai_provider`, `name`, `version`, `uid`), while the residual `MachineLearningModel`
  and the MVP `ext:AIModel` denote the learned parameters. They are different kinds of thing, so a
  plain `seeAlso` would overclaim. The OCSF-side gap is a digest of the weights and a base-model
  link, without which a swapped model reusing a name looks identical in telemetry.
- The tool-definition residual (AML.T0084.001) has its best counterpart in OCSF `ai_capability`,
  but that object is on main only (1.10.0-dev, not in 1.9.0). It describes one capability and
  holds the description and schemas by fingerprint, while #601's `AIAgentToolConfiguration` is the
  whole declaration set. The carrier half (`AIAgentToolManifest`) has no AI-specific OCSF object,
  only `file`.
- OCSF has two competing tool-call shapes right now. Main identifies the called capability
  structurally through `ai_capability`, and the #1754 draft's `ai_agent_tool_use_info` uses a
  free-text tool name with input and response payloads and an `is_pre_occurrence` flag, without
  referencing `ai_capability` (the event itself can still carry `ai_capability` through the
  `ai_operation` profile on its Application base, so the duplication is in the info object). Both the D3FEND MVP
  `AIToolInvocation` and PR #601's `AIAgentToolCall` define the call as "proposed or issued", so
  each class spans both states without a property to tell them apart, and that flag is the
  discriminator neither D3FEND proposal has, which makes it probably the most useful single point
  to bring to #1754 and #606. (Corrected in verification: the earlier text said #601 lacked the
  "proposed or issued" wording, but its definition carries it verbatim; see VERIFICATION.md.)
- RAG retrieval and agent memory both resolve to `d3f:Database` on the D3FEND side, consistent with
  the concession on #606. OCSF carries retrieval as a role value (`ai_role_id = Retriever`), which
  agrees that it is a role and not a kind, but it has nothing for agent memory, so AML.T0080.000
  (memory poisoning) has no telemetry home. `memory_activity` is OS process memory and does not
  count.
- `delegation` (1.9.0, with `scopes`, `audience` and `expiration_time` added on main) has no
  D3FEND counterpart of the same kind. `d3f:AccessToken` is the carrier and
  `d3f:PermissionGrantingEvent` is the act, but the grant and its re-delegation chain are not an
  artifact in D3FEND, so scope attenuation across agent hops has nothing to attach to.
- Training and fine-tuning events have no OCSF counterpart at all (rows D12 and D13, two of the
  3 `none` rows on the D3FEND side; the third is agent memory, D8), while inference maps partially to API Activity (6003) carrying the `ai_operation` profile.
- Both MVP provenance (`ext:ProvenanceAttestation`) and OCSF `attestation` exist, but OCSF's
  attests the log record, not the artifact, so the two should not be linked.
- One naming hazard is worth stating on both threads: OCSF `agent` is a security sensor, OCSF
  `ai_agent` is the AI agent, and `d3f:Agent` is any intentional actor whose existing `seeAlso`
  points at OCSF `actor`. A by-name mapper would get this wrong.

## Source notes

- RESIDUAL.md says "4×MachineLearningModel" in its summary line while its own table and the #606
  thread list three techniques (AML.T0005.002, T0016.002, T0043.002). The "five residual nouns" in
  the R8 brief are five techniques across three nouns. I flagged this and did not edit the file,
  which is outside this directory.
- #1754 is a work-in-progress draft. 7 of its 9 info objects are empty stubs, so its rows will move.
- The #606 MVP table is an image. Its four classes are transcribed from `sources/img/mvp.png`.

## Limits

- No reasoner was run and no OWL bridge file was written. Grades are judgement against definitions,
  graded with the ontology-thinking checklist, so this is analysis, not measurement.
- The rows cover the R8 scope only (the residual, #586, #601, the #606 MVP, the event family, and
  OCSF `ai_*` plus #1754). They do not cover the 117 existing-artifact mappings or other OCSF
  objects that an AI event may also carry.
- OCSF main and both open PRs change weekly. Re-pin before quoting a row on #606 or #1754.
- Nothing was posted. Any comment on #606 or #1754 is an outward post and stays with the owner.

## Commands run (all read-only)

```
gh issue view 586|606 -R d3fend/d3fend-ontology [--comments]
gh pr view 601 -R d3fend/d3fend-ontology --json ... ; gh pr diff 601 -R d3fend/d3fend-ontology
gh api repos/d3fend/d3fend-ontology/commits/develop
gh api -H "Accept: application/vnd.github.raw" repos/d3fend/d3fend-ontology/contents/src/ontology/d3fend-protege.ttl?ref=048c6936...
gh pr view 1754 -R ocsf/ocsf-schema --json files,headRefOid,...
gh api repos/ocsf/ocsf-schema/commits/main ; gh api repos/ocsf/ocsf-schema/git/trees/{main,v1.9.0}?recursive=1
gh api ... contents/{objects,profiles,events}/*.json?ref={d1cbd619,v1.9.0}   (copies under sources/)
gh api ... repos/davemcatcisco/ocsf-schema/contents/...?ref=08d6f530         (PR #1754 files)
gh search code ai_operation --repo ocsf/ocsf-schema
curl -sSL https://github.com/user-attachments/assets/88750fc4-...           (#606 MVP image)
python3 -I build_table.py
```

Machine: Beelink, WSL2 (6.6.87.2-microsoft-standard-WSL2), Python 3.12.3 stdlib, gh 2.83.2.

Version cells verified against tag trees: `ai_model`, `message_context` and the `ai_operation`
profile first appear in v1.8.0 (none in v1.7.0); `ai_agent` and `delegation` first appear in
v1.9.0; `ai_capability` and `ai_status` are on main only. `ai_role_id = 6 Retriever` is present in
v1.9.0.

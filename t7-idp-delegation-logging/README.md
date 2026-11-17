# t7-idp-delegation-logging (T7)

## What it measures

Does an identity provider's own audit trail record an agent delegation chain? Keycloak 26.8.1 in Docker, OAuth 2.0
Token Exchange (RFC 8693), a chain `alice -> app-frontend -> agent-a -> agent-b -> tool-api`, with R7's `reacquire`
and `new` scope plants, in two arms: the default Standard Token Exchange V2, and the preview
`token-exchange-delegation` feature that issues `may_act` / `act`. Captures: admin REST events and admin events,
the `jboss-logging` stdout lines, and the signature-verified claims of every issued token. Scores: which fields each
hop event carries, whether a parent pointer exists, whether the chain can be reconstructed from events alone, whether
the R7 escalation is detectable from IdP events, and how far it maps to OCSF 1.9.0 (`authentication`, `account_change`,
`entity_management`, the `delegation` object). No LLM arm, so methodology §10 does not apply.

## Result

Every Keycloak `TOKEN_EXCHANGE` event names the client the subject token was issued to and the id of the token it
issued, but never the subject token's own id, so the chain is explicit at client granularity and only implicit at
token granularity; with one user token exchanged by three agent instances in one session, the pre-registered
nearest-earlier rule attributed 5 of 15 hops correctly (`RESULTS.md`, Headline). The delegation preview puts the actor
into both token and event and drops the session identifier from both. These are measured properties of real
software, and the RESULTS file says plainly that a scope-matching heuristic would have scored 15 of 15 only because
the plants gave each chain a distinct scope set.

## What would have made it fail

Each hypothesis in `PREREGISTRATION.md` names what would prove it wrong, and the scoring rubric was fixed before the
run. The two arms (default exchange and the delegation preview) are compared on the same scenarios, and the
signature-verified token claims are the ground truth the events are scored against.

## Pre-registration

`PREREGISTRATION.md`, frozen by agent before the run and not owner-reviewed, at 2026-11-10T01:05:35Z
(`results/freeze.txt`). The file now carries one dated amendment (analysis-side, after the run, no harness line
changed), so the freeze hash on `results/freeze.txt` line 2 (`f95931e8…`) no longer matches the whole file; it does
match the file's first 203 lines, everything above the amendment text, and the post-amendment hash on line 13
(`10814580…`) matches the current file. The harness hashes recorded at freeze (`kc.py`, `harness.py`, `run_all.sh`,
`requirements.txt`) and the analysis hashes recorded afterwards (`score.py`, `map_ocsf.py`) all still match, and the
final verification hashes on lines 29 and 30 match the current `RESULTS.md` and `VERIFICATION.md`. The amendment
declares one analysis rule that was not pre-registered (arm D hop linkage by `userId` and client), and `RESULTS.md`
reports it as such.

## Reproduce

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && ./run_all.sh && .venv/bin/python score.py && .venv/bin/python map_ocsf.py
```

Docker is required, and `run_all.sh` pulls `quay.io/keycloak/keycloak:26.8.1` by digest. The raw capture tree
`results/raw/<arm>/` (per-hop chain records, `events.json`, `admin-events.json`, `container-log.txt`,
`realm-config.json`, the redacted `fixture-secrets.json` and `driver.log`) is not committed, so `score.py` and
`map_ocsf.py` cannot be re-run from this tree; the committed outputs are listed below.

Files: `kc.py` (Keycloak REST and OIDC helpers, scripted login and consent), `harness.py` (setup, run, enforcer,
capture), `run_all.sh` (driver for both arms, sequential containers on 127.0.0.1:8080), `score.py` (rubric) and
`map_ocsf.py` (OCSF records and the public validator).

## Results

- `RESULTS.md` is the entry point: headline, hypothesis verdicts, field inventories, claims per token position, R7
  detectability, OCSF 1.9.0 mapping, limits, deviations.
- `results/score.json`, `results/tables.md`, `results/ocsf_mapping.json` and `results/ocsf_records_*.jsonl` are the
  committed outputs; `results/freeze.txt` holds the hashes and clock readings.
- `VERIFICATION.md` is the independent re-run and cross-provider check (VERIFIED-WITH-FIXES). Under `verification/`,
  `RESULTS.pre-verification.md` is a superseded copy from before the verifier's wording fixes, and
  `analysis-rerun/`, `full-rerun/` and `rerun-diff.txt` are the verifier's re-runs; none of them is the current result.

## Versions and pins

`requirements.txt` pins PyJWT 2.15.1, cryptography 50.0.2, cffi 2.1.1 and pycparser 3.12, every line with `==`.
Keycloak runs from a digest-pinned image (`RESULTS.md`, rig stamp).

## Evidence tier and limits

Tier B (first-party, single host, one IdP product at one version, synthetic realm; `RESULTS.md` frontmatter). One
product at one version, dev-mode storage, a synthetic realm and scripted logins, and timings under contention that
are reported only to show the harness was not the bottleneck. See Limits in `RESULTS.md`.

## Corrections

- 2026-11-10: one dated amendment appended to `PREREGISTRATION.md`, and RESULTS wording fixes at verification
  recorded in `results/freeze.txt`.
- 2026-11-17: this README was restructured to the lab layout and now records the prefix-hash check and the
  uncommitted `results/raw/` tree. `RESULTS.md` and `VERIFICATION.md` were left byte-identical, because
  `results/freeze.txt` records their hashes; this README already differed from the hash recorded there before this
  pass.

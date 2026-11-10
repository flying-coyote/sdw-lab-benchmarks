# t7-idp-delegation-logging (T7)

Does an identity provider's own audit trail record an agent delegation chain? Keycloak 26.8.1 in Docker, OAuth 2.0
Token Exchange (RFC 8693), a chain `alice -> app-frontend -> agent-a -> agent-b -> tool-api`, with R7's `reacquire`
and `new` scope plants, in two arms: the default Standard Token Exchange V2, and the preview
`token-exchange-delegation` feature that issues `may_act` / `act`. Captures: admin REST events and admin events,
the `jboss-logging` stdout lines, and the signature-verified claims of every issued token. Scores: which fields each
hop event carries, whether a parent pointer exists, whether the chain can be reconstructed from events alone, whether
the R7 escalation is detectable from IdP events, and how far it maps to OCSF 1.9.0 (`authentication`, `account_change`,
`entity_management`, the `delegation` object). No LLM arm, so methodology §10 does not apply.

- `PREREGISTRATION.md`: question, arms, scenarios, hypotheses, rubric; frozen before the run, one dated amendment.
- `RESULTS.md`: headline, hypothesis verdicts, field inventories, OCSF fill, limits, deviations.
- `VERIFICATION.md`: independent re-run and cross-provider check (verdict VERIFIED-WITH-FIXES); re-run copies under `verification/`.
- `kc.py` (Keycloak REST + OIDC helpers, scripted login/consent), `harness.py` (setup / run / enforcer / capture),
  `run_all.sh` (driver: both arms, sequential containers on 127.0.0.1:8080), `score.py` (rubric), `map_ocsf.py`
  (OCSF records + public validator).
- `results/freeze.txt`: hashes and clock at freeze, plus the post-freeze analysis-code hashes.
- `results/raw/<arm>/`: `chains-rep*.json` (per-hop status, request, verified claims, monotonic ns), `capture/`
  (`events.json`, `admin-events.json`, `container-log.txt`), `realm-config.json`, `fixture-secrets.json` (runtime
  test fixtures for a throwaway realm; values redacted after the run), `driver.log`.
- `results/score.json`, `results/tables.md`, `results/ocsf_mapping.json`, `results/ocsf_records_*.jsonl`.

Reproduce: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && ./run_all.sh && .venv/bin/python
score.py && .venv/bin/python map_ocsf.py` (Docker required; pulls `quay.io/keycloak/keycloak:26.8.1` by digest).

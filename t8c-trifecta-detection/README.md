# t8c-trifecta-detection (T8c)

Can the lethal trifecta be detected as a sequence inside one agent session, over OCSF 1.9.0 `api_activity` events
carrying the `ai_operation` profile? Chains shaped like ATLAS AML.CS0066 (ZombieAgent, the T1698 → T1700 shape
through connectors) and AML.CS0067 (Claude Code GitHub Action, the same shape through a CI agent) are planted at
their defender-visible steps among benign agent sessions, and three tiers of rule are scored DETECTED / NOISY /
MISSED at precision floor T = 0.9 on DuckDB 1.5.3 and stdlib SQLite: single-step Sigma rules per leg, session rules
(pySigma `temporal` correlation and hand SQL), and session rules after a delegation walk to the root session.

- Design, frozen before the run: `PREREGISTRATION.md` (sha256 in `results/PREREG.sha256`, freeze time in `.frozen`)
- Results, verdicts, deviations and limits: `RESULTS.md`
- Per-step observability table for the two ATLAS case studies: `results/chain_steps.md`
- Ledger row text for the hub's `PRE-REGISTRATION-LEDGER.md`: `LEDGER-ROW.md` (the hub file is not edited from here)
- Rules: `rules/*.yml` (Sigma, compiled through pySigma 2.0.3 + pySigma-backend-sqlite 2.1.1); hand SQL in `run.py`
- Reproduce (local CPU only, zero spend, about 3 minutes per seed, most of it corpus writing):

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
taskset -c 0-3 nice -n 10 .venv/bin/python -I run.py                      # three seeds -> results/coverage.json
taskset -c 0-3 nice -n 10 .venv/bin/python -I run.py --scale 20000 --seeds 20261109 --sql-only --out results/coverage-scale20k.json
```

Everything in the corpus is synthetic test fixture: reserved hostnames (`.invalid`, `.example`), a labelled fixture
marker where the injected content would be, and a fixture string where the de-prefixed key would be. No real
credentials, no real data, no exploit content, no model in the loop. Column paths are validated mechanically against
the OCSF 1.9.0 schema JSON in `../atlas-ocsf-observables/sources/ocsf-1.9.0/` (read-only).

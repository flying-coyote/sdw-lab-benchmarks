# t3-guardrail-adaptive (T3)

What a vendor claim like "blocks prompt injection" can mean in measured terms: three small open
prompt-injection / jailbreak classifiers (Protect AI DeBERTa v2, deepset DeBERTa, jackhhao BERT jailbreak
classifier) run on CPU against public, citable attack and benign sets (deepset prompt-injections, Lakera
Gandalf, in-the-wild jailbreaks, NotInject, Dolly, JBB benign), untransformed and under nine documented input
transformations from the literature (character spacing, Base64, ROT13, leetspeak, upper-casing, vowel removal,
zero-width characters, Cyrillic homoglyphs). Detection rate, false-positive rate, the drop under each
transform, Wilson and paired-bootstrap 95% intervals, truncation share, determinism.

Meta Prompt Guard 2 was named in the brief and is not here: its repos are gated and this host has no Hugging
Face token (declared in `PREREGISTRATION.md` before the run).

- Design, frozen before the run: `PREREGISTRATION.md` (hash and time in `FROZEN.sha256`)
- Results, verdicts per hypothesis, deviations and limits: `RESULTS.md`
- Tables and raw metrics: `results/tables.md`, `results/summary.json`
- Reproduce (local CPU only, no paid calls): `python -m venv .venv && .venv/bin/pip install -r requirements.txt`
  (torch from `https://download.pytorch.org/whl/cpu`), then `fetch_data.py`, `run.py <model>` for each of
  `protectai-v2`, `deepset`, `jackhhao-jb`, `run_stability.py <model>`, `analyze.py`. Exact commands with
  timestamps: `COMMANDS.log`. Fixtures regenerate from pinned dataset revisions; `fixtures/MANIFEST.json`
  carries their sha256 so a regeneration can be checked.

Scope as run: seven of the nine transforms (T6 and T8 were dropped by the stop rule) and A3/B4 capped; see RESULTS.md, Deviations.

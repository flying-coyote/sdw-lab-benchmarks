# Notebook substrate — marimo .py vs .ipynb

Tests H-NOTEBOOK-SUBSTRATE-01: the authoring layer is detection-as-code's reproducibility/lock-in
frontier. A Jupyter `.ipynb` is JSON that embeds execution counts and (when worked) outputs — git-noisy,
hidden-state-prone (~24% of public notebooks re-run / ~4% reproduce, Pimentel et al. MSR 2019). marimo's
reactive pure-`.py` model is reproducible and portable by construction. `hunt.py` is a real marimo OCSF
hunt over the shared testbed corpus; `run.py` exercises it three ways.

## Result (Tier B/C — a demonstration)

- **Reproducibility:** exported to a flat script and run twice headless — identical output, result
  `{beacon_conns: 60, no_mfa_attachpolicy: 1}` (it finds the planted needles).
- **Lock-in surface:** the `.py` carries 0 execution-count fields; the same notebook exported to `.ipynb`
  carries 4 (JSON slots that mutate every run; a worked notebook also accretes embedded outputs there).
- **Portability:** plain SQL over DuckDB, no notebook-runtime lock-in APIs (dbutils / displayHTML / `.dbc`).

Full write-up in [results/RESULTS.md](results/RESULTS.md). It's a demonstration on one hunt, not a
population study — Pimentel et al.'s rates are the external anchor.

## Run it

```bash
pip install -r ocsf-marimo-hunt/requirements.txt
python ocsf-marimo-hunt/run.py          # exports + double-runs + format contrast
marimo edit ocsf-marimo-hunt/hunt.py    # or open the notebook interactively
```

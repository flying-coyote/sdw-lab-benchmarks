# agent-telemetry-retention (R6)

What a year of agent and LLM telemetry costs to keep, in bytes per million billed tokens, when OCSF 1.9.0
records carrying the `ai_operation` profile are stored with metadata only, with a hash of the text, with the
per-request delta text, or with the full prompt as sent. Parquet (pyarrow 24.0.0) and Iceberg (pyiceberg
0.12.0), zstd levels, Parquet dictionary encoding, row order, and a trained zstd dictionary for the
per-record regime; priced with the inputs in `../cost-to-serve-retention/cost_model.py`.

- Design, frozen before the run: `PREREGISTRATION.md`
- Results, verdicts, deviations and limits: `RESULTS.md`
- Reproduce: the Commands block in `RESULTS.md` (local CPU only, no paid calls; about 3 minutes on the Beelink)
- Verification (2026-11-09): `VERIFICATION.md`. Exact numbers reproduce from the original `data/` corpora
  (sha256 in `results/data-sha256.txt`); the real-text corpora do not regenerate byte-identically because
  `generate.py` reads the lab's live markdown as its prose pool.

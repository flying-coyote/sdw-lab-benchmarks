# scripts

Repository tooling, as opposed to bench code.

- `bench_index.py` regenerates the bench index in the top-level `README.md` from every `*/bench.yaml`.
  It uses only the standard library, writes nothing but the block between the two `BENCH-INDEX` marker
  comments, exits non-zero unless the index has exactly the expected number of rows (81 by default,
  `--expect N` to change it), and gives byte-identical output on a second run. `--check` reports drift
  without writing, and `--strict` fails on a `bench.yaml` value outside the contract in
  [`../docs/BENCH-LAYOUT.md`](../docs/BENCH-LAYOUT.md).
- `secret-scan.sh` is a pre-commit scan of the staged diff for credential patterns (API keys, tokens,
  private-key headers), reinstated on 2026-06-30; it blocks the commit and prints the matching lines.
  Install it as a git pre-commit hook to use it.

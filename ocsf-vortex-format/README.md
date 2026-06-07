# Vortex vs Parquet on OCSF data

Vortex (the LF AI & Data columnar format, `vortex-data`) claims large random-access and scan speedups over
Parquet with comparable compression. This tests that on security-shaped data — an OCSF Network Activity corpus
with a realistic encoding mix — on the axes that decide a lakehouse format: on-disk size, write time, full
decode to Arrow, and a low-selectivity needle (`dst_port = 3389`) via each format's predicate pushdown. The
corpus is seeded-random (deterministic but not artificially regular — a monotonic/modular synthetic corpus
flatters zstd's ratio in a way real telemetry doesn't).

> **ECOSYSTEM-STATUS + FIRST-LOOK READ — not a settled format-performance claim.** The read comparison
> measures each format's *native reader* to Arrow (pyarrow for Parquet, `vortex-data` for Vortex), not
> a single common engine over both — that is a native-reader confound. A fair settled comparison requires
> a common engine (DuckDB 1.5+ once the Vortex extension builds against that line); until then
> decode-to-Arrow is the fairest available variable but the confound is real and acknowledged. The
> vendor's headline 10–100× speedup was **not replicated** — observed gains are single-digit× (1.7–2.6×
> decode, ~3.3–4× needle). Run your own numbers before citing the launch post.

## Result (Tier B)

`vortex-data` 0.74.0, pyarrow 23.0.1, one host. Parquet written zstd; Vortex written with its adaptive
cascading encodings. Two scales, because the size conclusion turned out to be scale-dependent.

| scale | format | size | write | decode→Arrow | needle (dst_port=3389) |
|---|---|--:|--:|--:|--:|
| 100K | parquet | 1.6 MB | 43 ms | 6.4 ms | 6.0 ms |
| 100K | **vortex** | **1.5 MB** | 57 ms | **2.5 ms** | **1.5 ms** |
| 1M | parquet | **11.3 MB** | 192 ms | 33.2 ms | 34.7 ms |
| 1M | **vortex** | 14.2 MB | 398 ms | **19.7 ms** | **10.4 ms** |

The trade is consistent and clear: **Vortex reads faster — decode ~1.7–2.6×, the needle ~3.3–4× — at a write
cost (~1.3–2× slower) and a storage cost that depends on scale** (Vortex ~9% smaller at 100K, ~26% larger at
1M). Answers are identical across both formats at both scales — row count, the needle count, and a full
logical fingerprint of the data all match — so the read speed comes with no correctness give. The read
advantage is real but single-digit×, not the vendor's headline 10–100×, which is exactly why you run your own
numbers on your own data rather than cite the launch post.

Two honest qualifiers. The **size conclusion flips with scale**, so "comparable compression" holds only within
a small factor and the direction depends on the corpus and the row count — the methodology's sweep-the-scale
rule earning its keep, since a single 1M point would have said "Vortex is bigger" and a single 100K point would
have said "Vortex is smaller." And the read comparison is each format's **native reader** to Arrow (pyarrow vs
`vortex-data`), not one engine over both — no engine on DuckDB 1.5.3 reads Vortex (the extension targets the 1.4
LTS line), so a common-engine read isn't available here and decode-to-Arrow is the fairest single variable.

## Format + ecosystem status (checked 2026-06)

- **Installable — the old "blocked" was a rename.** `vortex-array` was renamed to **`vortex-data`** (the old
  name is yanked on PyPI with exactly that note); the live package is 0.74.0 and installs cleanly. The earlier
  install-blocked status was tracking the abandoned name, not a real block.
- **Format stable.** Backward-compatible since v0.36.0, so files written now stay readable; the Python/Rust API
  still ships breaking changes, so the harness pins `vortex-data`. The project was donated to the Linux
  Foundation (LF AI & Data), repo at `vortex-data/vortex`.
- **Multi-engine, single core.** DuckDB (core extension, 1.4 LTS line), DataFusion, Polars, and Spark read it —
  all bindings over one Rust implementation, so it's multi-*engine* but not multi-*implementation* the way
  Parquet is (independent C++/Java/Rust readers). That distinction matters for an open-read-contract stack.
- **Not yet an Iceberg data file.** Iceberg 1.11.0 (May 2026) shipped the pluggable File Format API; Vortex as
  an Iceberg data file is open issue [apache/iceberg#15416](https://github.com/apache/iceberg/issues/15416). So
  this is a standalone-format datapoint, not a swap-in for the Iceberg table format the rest of the MOAR stack
  reads — Vortex inside Iceberg stays a future arm.

## Run it

```bash
pip install -r ocsf-vortex-format/requirements.txt
python ocsf-vortex-format/run.py                 # 1,000,000 rows
VX_N=100000 python ocsf-vortex-format/run.py     # a smaller scale point
```

Deterministic corpus (seeded off `lib.common`). Tier B, single machine; the per-format table is version- and
scale-bound — re-run on a `vortex-data` upgrade. The DuckDB-Vortex extension arm (DuckDB 1.4 LTS) and the
Iceberg-Vortex path are future work, gated on the extension building for our DuckDB line and on #15416.

# #25 Dremio-arm finding — Reflections don't persist over the open Nessie/Iceberg path (2026-06-15)

#25 (`mv-rewrite-freshness`) compares two transparent-rewrite accelerators at matched freshness on a
live Iceberg table: **Dremio Reflections** vs **StarRocks async MV**. This note records the
Dremio-arm blocker, established across two independent read paths. Tier B, single host (ejs stack:
Dremio OSS 26.0, Nessie REST catalog, MinIO, the SOC `conn` Iceberg table).

## Both Dremio read paths fail to give a usable Reflection

1. **Nessie-versioned source (BRANCH `main`)** — the path the lab's Dremio arm uses. A raw
   reflection *materializes* but expires instantly: `sys.reflections` shows
   `available_until = 1970-01-01` (epoch 0), `acceleration_status` never reaches `CAN_ACCELERATE`
   (documented in `zeek-flagship-rerun/dremio_arm.py`). Dremio-26 cannot compute a valid
   freshness/expiry for a BRANCH-versioned, `register_table`'d Iceberg table, so the "ON" arm
   degenerates to "OFF".

2. **Non-versioned raw S3 source (this probe, `dremio_reflection_probe.py`)** — the untried fix
   (point an S3 source straight at MinIO so Dremio auto-promotes the Iceberg metadata without the
   version context). The S3 source connects and lists the folders, but **promotion fails**:
   `Failed to get iceberg metadata: /warehouse/soc/conn_<uuid>`. The folder's `metadata/` holds
   **six `00000-*.metadata.json` files plus a `99999-…metadata.json`** and **no `version-hint.text`**
   — Nessie tracks the current metadata pointer in the catalog, not on the object store, so a
   catalog-less S3 reader has no deterministic way to pick the live metadata. Dremio's S3 Iceberg
   promotion needs a Hadoop-style version hint (or its own catalog) and there is none.

## Conclusion (the fair-broker finding)

On Dremio OSS 26.0, **Reflections do not work over an Iceberg table managed by an external Nessie
catalog** — neither through the versioned Nessie source (reflection materializes then expires at
epoch 0) nor through a raw S3 source (the catalog-managed metadata layout has no version hint to
promote). This is an orchestration/integration limit of Dremio-26 over the open-catalog path, not a
measurement. (The separate Dremio Reflections-OFF engine results in `zeek-flagship-rerun` are
withheld under Dremio's benchmark-publication terms; this finding is about the Reflections-ON
integration path being blocked, not about Dremio's measured latency.)

## What this means for #25

The Dremio-Reflections-vs-StarRocks-MV matched-freshness comparison **cannot be run as designed** on
the open Nessie/Iceberg substrate. Options for the achievable bench:
- **StarRocks async MV half** is viable (the `make_mvs.sql` build works after the `REFRESH ASYNC →
  REFRESH MANUAL` fix; for a *live* table use `REFRESH ASYNC EVERY (INTERVAL …)`). Run it + the
  no-acceleration control on a continuously-appended table → the freshness-vs-acceleration curve for
  one accelerator, paired with this Dremio-blocked finding.
- A Dremio Reflection that *would* persist needs a Dremio-native catalog (Dremio Arctic / its own
  Iceberg catalog) or a Hadoop-tables layout with a version hint — i.e. NOT the open Nessie path the
  rest of the lab standardizes on. Out of scope unless the substrate changes.

Probe: `dremio_reflection_probe.py` (S3 source create + promote + reflection + sys.reflections poll).
Re-run on a newer Dremio release before repeating — this is version-bound to Dremio OSS 26.0.

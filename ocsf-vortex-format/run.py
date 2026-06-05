"""Vortex vs Parquet — guarded stub (install-blocked). See README.md."""
import sys
try:
    import vortex  # noqa: F401
except Exception:
    print("Vortex Python library not installed (vortex-array is yanked on PyPI as of 2026-06).\n"
          "This benchmark is recorded as pending; see README.md for the design when unblocked.",
          file=sys.stderr)
    sys.exit(2)
print("vortex present — implement the Parquet-vs-Vortex comparison per README.md")

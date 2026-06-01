"""C1 — OCSF field-mapping fidelity harness (SCAFFOLD, not yet runnable).

This is intentionally a stub. C1 measures how real vendor schemas map into OCSF
1.8.0, which needs real inputs in ``schemas/`` rather than a synthetic corpus.
Until those are gathered the harness raises, so nobody mistakes an empty run for a
result. The protocol is fixed in ``README.md``; fill in the loaders and the scorer
once the schema samples exist.
"""

import os

SOURCES = ("crowdstrike", "okta", "palo_alto", "cisco", "zscaler")
OCSF_VERSION = "1.8.0"
SCHEMAS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schemas")


def _load_source_fields(source: str):
    """Return the source's field inventory from schemas/<source>/.

    TODO: parse the checked-in real schema/sample and return typed field paths.
    """
    raise NotImplementedError(
        f"C1 needs a real schema sample for '{source}' in {SCHEMAS_DIR}/{source}/. "
        "See README.md for the protocol. No synthetic stand-in is used here on "
        "purpose — C1 is a real-input benchmark."
    )


def _load_ocsf_schema():
    """Return the OCSF 1.8.0 attribute set. TODO: load from a checked-in copy."""
    raise NotImplementedError("Provide an OCSF 1.8.0 schema copy under schemas/ocsf/.")


def score_source(source: str):
    """coverage / lossy / detection-breaking for one source. TODO: implement."""
    fields = _load_source_fields(source)  # raises until inputs exist
    ocsf = _load_ocsf_schema()
    raise NotImplementedError("Mapping + scoring not implemented; see README.md step 3.")


def run():
    raise NotImplementedError(
        "C1 is a scaffold. Gather real vendor schemas into schemas/, then implement the "
        "loaders and scorer per README.md. The flattening-fidelity benchmark "
        "(../flattening-fidelity/run.py) is a runnable example of the shape."
    )


if __name__ == "__main__":
    run()

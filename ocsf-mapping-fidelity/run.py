"""Run C1 — OCSF field-mapping fidelity — and write results.

Like the flattening and sigma benchmarks, this is fully deterministic: the inputs
are static checked-in files (the vendor inventories, the OCSF 1.8.0 schema subset,
the mappings), so the score is a pure function of them. The runner computes it
twice and asserts the two are byte-identical before writing anything.

Usage:
    python run.py
"""

import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
sys.path.insert(0, HERE)

from common import canonical  # noqa: E402
import map_fidelity as M  # noqa: E402

RESULTS_DIR = os.path.join(HERE, "results")


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)

    first = M.score_all()
    second = M.score_all()
    deterministic = canonical(first) == canonical(second)
    if not deterministic:
        raise SystemExit("non-deterministic score — refusing to publish")

    results = {
        "benchmark": "ocsf-mapping-fidelity (C1)",
        "evidence_tier": "B (reproducible, first-party mapping judgement against real "
                         "documented vendor schemas and the real OCSF 1.8.0 schema; "
                         "not production telemetry)",
        "ocsf_version": first["ocsf_version"],
        "scope": {
            "okta": "System Log LogEvent -> Authentication (3002); anchored on Okta's "
                    "okta/okta-ocsf-syslog reference mapper where it maps",
            "crowdstrike": "Detection Summary Event (Event Streams) -> Detection Finding "
                           "(2004); best-effort vs OCSF 1.8.0 (no public vendor field mapping)",
            "note": "Okta inventory is the documented typed schema; CrowdStrike inventory "
                    "is the publicly-reproduced Detection Summary Event, NOT the gated full "
                    "FDR schema. Coverage is over each scoped field set, not all telemetry.",
        },
        "per_source": {s: first["per_source"][s] for s in first["per_source"]},
        "detections": first["detections"],
    }

    with open(os.path.join(RESULTS_DIR, "results.json"), "w") as f:
        json.dump(results, f, indent=2)
    _write_markdown(results)

    digest = hashlib.sha256(canonical(first).encode()).hexdigest()[:16]
    print(f"determinism_verified={deterministic}  ocsf={results['ocsf_version']}  "
          f"results_sha256[:16]={digest}")
    for s, scored in results["per_source"].items():
        sm = scored["summary"]
        line = (f"  {s:12s} {sm['class']:26s} fields={sm['total_fields']:2d}  "
                f"typed={sm['typed']:2d} coerced={sm['coerced']:2d} unmapped={sm['unmapped']:2d}  "
                f"coverage={sm['coverage']:.2f} lossy={sm['lossy_fraction']:.2f}")
        if "official_mapped" in sm:
            line += f"  okta-shipped-maps={sm['official_mapped']}/{sm['total_fields']} impl-gap={sm['implementation_gap']}"
        print(line)
    broke = [d for d in results["detections"] if not d["survives_clean"]]
    clean = [d for d in results["detections"] if d["survives_clean"]]
    print(f"  detections: {len(broke)}/{len(results['detections'])} lose at least one field; "
          f"clean: {', '.join(d['name'] for d in clean)}")
    print(f"wrote {os.path.join(RESULTS_DIR, 'results.json')}")
    print(f"wrote {os.path.join(RESULTS_DIR, 'RESULTS.md')}")


def _write_markdown(results):
    lines = []
    a = lines.append
    a("# Results — OCSF field-mapping fidelity (C1)\n")
    a(f"- OCSF version: **{results['ocsf_version']}**  ·  evidence tier: {results['evidence_tier']}")
    a("- Determinism (re-score is byte-identical): **True**  ")
    a("- Every OCSF target below is validated against the checked-in 1.8.0 schema "
      "subset; an invented attribute would fail the run.\n")

    a("## Scope\n")
    a(f"- **Okta** — {results['scope']['okta']}")
    a(f"- **CrowdStrike** — {results['scope']['crowdstrike']}")
    a(f"- {results['scope']['note']}\n")

    a("## Coverage per source\n")
    a("`coverage` counts only fields that land on a typed OCSF attribute with "
      "semantics preserved. `coerced` = a typed home exists but a boundary is "
      "crossed (enum narrows, array collapses, id/label lost). `unmapped` = no "
      "typed home; only OCSF `unmapped`/`raw_data` can hold it.\n")
    a("| source | OCSF class | fields | typed | coerced | unmapped | coverage | lossy |")
    a("|---|---|--:|--:|--:|--:|--:|--:|")
    for s, scored in results["per_source"].items():
        sm = scored["summary"]
        a(f"| {s} | {sm['class']} | {sm['total_fields']} | {sm['typed']} | {sm['coerced']} | "
          f"{sm['unmapped']} | {sm['coverage']:.0%} | {sm['lossy_fraction']:.0%} |")
    a("")

    # Okta implementation gap
    okta = results["per_source"].get("okta", {}).get("summary", {})
    if "official_mapped" in okta:
        a("## Okta: the schema gap vs the shipped-mapper gap\n")
        a(f"OCSF 1.8.0 has a typed (or coercible) home for "
          f"{okta['typed'] + okta['coerced']} of {okta['total_fields']} Okta fields, but "
          f"Okta's own reference mapper (`okta/okta-ocsf-syslog`) carries only "
          f"{okta['official_mapped']} of {okta['total_fields']} into the OCSF event. "
          f"So {okta['implementation_gap']} fields have an OCSF home the shipped mapper "
          f"leaves on the floor:\n")
        a("> " + ", ".join("`" + f + "`" for f in okta["implementation_gap_fields"]) + "\n")
        a("Several of those are detection-relevant (the autonomous-system fields, the "
          "ISP/domain enrichment, the network zone, the credential type). The schema "
          "can hold them; the integration does not.\n")

    a("## Detections — which break, and on which field\n")
    a("Detection-breaking = a field a named detection needs that does not map "
      "cleanly (coerced or unmapped). Two detections survive clean — the result is "
      "*which* break, not that everything does.\n")
    a("| detection | source | breaks on |")
    a("|---|---|---|")
    for d in results["detections"]:
        if d["survives_clean"]:
            cell = "— (all fields typed)"
        else:
            cell = ", ".join(f"`{b['field']}` ({b['status']})" for b in d["breaking"])
        a(f"| {d['name']} | {d['source']} | {cell} |")
    a("")

    a("## Field-by-field (auditable)\n")
    a("The full per-field mapping, status and rationale is in `results.json` and "
      "`mapping.py`. Lossy fields, grouped:\n")
    for s, scored in results["per_source"].items():
        coerced = [r for r in scored["fields"] if r["status"] == "coerced"]
        unmapped = [r for r in scored["fields"] if r["status"] == "unmapped"]
        a(f"### {s} — coerced ({len(coerced)})\n")
        for r in coerced:
            a(f"- `{r['field']}` → `{r['ocsf']}` — {r['note']}")
        a(f"\n### {s} — unmapped ({len(unmapped)})\n")
        for r in unmapped:
            a(f"- `{r['field']}` — {r['note']}")
        a("")

    with open(os.path.join(RESULTS_DIR, "RESULTS.md"), "w") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()

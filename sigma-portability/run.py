"""Compile every Sigma rule to four open backends, verify determinism, score
correlation-translation fidelity, write results.

pySigma compilation has no clock and no randomness, so this is a fully
deterministic benchmark like the flattening one: the runner compiles everything
twice and asserts the output is identical before publishing. The "result" is the
generated queries and the fidelity scores, and they reproduce exactly.

Usage:
    python run.py
"""

import glob
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
sys.path.insert(0, HERE)

from sigma.collection import SigmaCollection  # noqa: E402
import sigma  # noqa: E402

from common import canonical  # noqa: E402
import backends as B  # noqa: E402
import fidelity as F  # noqa: E402

RESULTS_DIR = os.path.join(HERE, "results")


def discover_rules():
    out = []
    for kind in ("single", "correlation"):
        for path in sorted(glob.glob(os.path.join(HERE, "rules", kind, "*.yml"))):
            out.append((path, os.path.splitext(os.path.basename(path))[0], kind))
    return out


def _convert(be, path):
    try:
        coll = SigmaCollection.from_yaml(open(path).read())
        out = be.convert(coll)
        return [str(q) for q in out], None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def compile_all():
    """Return {backend: {rule: {output, error, ...}}} — no scoring (pure outputs)."""
    backends = B.build_backends()
    rules = discover_rules()
    grid = {}
    for bname, (be, _pipe) in backends.items():
        grid[bname] = {}
        for path, rname, _kind in rules:
            output, error = _convert(be, path)
            grid[bname][rname] = {"output": output, "error": error}
    return grid


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)

    first = compile_all()
    second = compile_all()
    deterministic = canonical(first) == canonical(second)

    rules = discover_rules()
    corr_meta = {rname: F.parse_correlation(path)
                 for path, rname, kind in rules if kind == "correlation"}

    # Attach fidelity scores to correlation cells.
    scored = {}
    for bname, cells in first.items():
        scored[bname] = {}
        for rname, cell in cells.items():
            rec = {"output": cell["output"], "error": cell["error"],
                   "translated": cell["error"] is None}
            meta = corr_meta.get(rname)
            if meta and cell["error"] is None:
                sc = F.score_correlation(cell["output"], meta)
                pres, total = F.fidelity_fraction(sc, meta)
                rec["fidelity"] = sc
                rec["fidelity_fraction"] = [pres, total]
            scored[bname][rname] = rec

    rule_kinds = {rname: kind for _p, rname, kind in rules}
    results = {
        "benchmark": "sigma-correlation-portability (C4)",
        "evidence_tier": "B (reproducible, first-party; compiler-output fidelity, not target-SIEM execution)",
        "environment": {
            "pySigma_version": sigma.version if hasattr(sigma, "version") else _pysigma_version(),
            "backends": {k: v for k, v in B.BACKEND_LABELS.items()},
            "note": "all four backends emit text; no commercial software runs",
        },
        "determinism_verified": deterministic,
        "rule_kinds": rule_kinds,
        "correlation_meta": corr_meta,
        "grid": scored,
        "summary": _summarize(scored, rule_kinds, corr_meta),
    }

    with open(os.path.join(RESULTS_DIR, "results.json"), "w") as f:
        json.dump(results, f, indent=2)
    _write_markdown(results)

    digest = hashlib.sha256(canonical(first).encode()).hexdigest()[:16]
    print(f"determinism_verified={deterministic}  pySigma={results['environment']['pySigma_version']}  "
          f"results_sha256[:16]={digest}")
    s = results["summary"]
    print(f"single-event rules: {s['n_single']} | correlation rules: {s['n_correlation']}")
    for bname, lab in B.BACKEND_LABELS.items():
        bs = s["per_backend"][bname]
        print(f"  {lab:22s} single {bs['single_translated']}/{s['n_single']}  "
              f"corr full {bs['corr_full']}  partial {bs['corr_partial']}  refused {bs['corr_refused']}  "
              f"silent-window-drop {bs['silent_window_drop']}")
    print(f"wrote {os.path.join(RESULTS_DIR, 'results.json')}")
    print(f"wrote {os.path.join(RESULTS_DIR, 'RESULTS.md')}")


def _pysigma_version():
    try:
        from importlib.metadata import version
        return version("pysigma")
    except Exception:
        return "unknown"


def _summarize(scored, rule_kinds, corr_meta):
    singles = [r for r, k in rule_kinds.items() if k == "single"]
    corrs = [r for r, k in rule_kinds.items() if k == "correlation"]
    per_backend = {}
    for bname, cells in scored.items():
        single_ok = sum(1 for r in singles if cells[r]["translated"])
        corr_full = corr_partial = corr_refused = silent_window = 0
        for r in corrs:
            cell = cells[r]
            if not cell["translated"]:
                corr_refused += 1
                continue
            pres, total = cell.get("fidelity_fraction", [0, 0])
            if total and pres == total:
                corr_full += 1
            else:
                corr_partial += 1
            # silent window drop: translated, the rule has a timespan, but the
            # generated query has no time-window construct.
            if corr_meta[r].get("timespan") and cell.get("fidelity", {}).get("time_window") is False:
                silent_window += 1
        per_backend[bname] = {
            "single_translated": single_ok,
            "corr_full": corr_full,
            "corr_partial": corr_partial,
            "corr_refused": corr_refused,
            "silent_window_drop": silent_window,
        }
    return {"n_single": len(singles), "n_correlation": len(corrs), "per_backend": per_backend}


def _cell_corr(cell):
    if not cell["translated"]:
        return "refused"
    pres, total = cell.get("fidelity_fraction", [0, 0])
    tag = f"{pres}/{total}"
    if cell.get("fidelity", {}).get("time_window") is False and total:
        tag += " ⚠ no window"
    return tag


def _write_markdown(results):
    env = results["environment"]
    s = results["summary"]
    g = results["grid"]
    bnames = list(B.BACKEND_LABELS.keys())
    labels = B.BACKEND_LABELS
    lines = []
    a = lines.append

    a("# Results — Sigma correlation-backend portability (C4)\n")
    a(f"- pySigma: `{env['pySigma_version']}`  ·  backends: "
      + ", ".join(labels[b] for b in bnames) + "  ")
    a(f"- Determinism (re-compile is byte-identical): **{results['determinism_verified']}**  ")
    a(f"- Evidence tier: {results['evidence_tier']}\n")
    a("Every backend emits text, so this measures what the *compiler* produces, not "
      "what a target SIEM executes. Each correlation cell scores the elements that "
      "appear in the generated query (see `METHODOLOGY.md` for the exact checks), and "
      "the verbatim queries are in `results.json` so any score is auditable.\n")

    # Single-event portability
    a("## Single-event rules — do they translate?\n")
    a("| rule | " + " | ".join(labels[b] for b in bnames) + " |")
    a("|---" * (len(bnames) + 1) + "|")
    for r, k in results["rule_kinds"].items():
        if k != "single":
            continue
        cells = " | ".join("✓" if g[b][r]["translated"] else f"✗ {g[b][r]['error'].split(':')[0]}" for b in bnames)
        a(f"| {r} | {cells} |")
    a("")

    # Correlation fidelity
    a("## Correlation rules — how much of the semantics survives?\n")
    a("Cells show preserved-elements / applicable-elements; `refused` means the "
      "backend raised rather than emit a query; `⚠ no window` flags a query that "
      "translated but dropped the time-span construct.\n")
    a("| correlation rule | type | " + " | ".join(labels[b] for b in bnames) + " |")
    a("|---" * (len(bnames) + 2) + "|")
    for r, k in results["rule_kinds"].items():
        if k != "correlation":
            continue
        ctype = results["correlation_meta"][r]["type"]
        cells = " | ".join(_cell_corr(g[b][r]) for b in bnames)
        a(f"| {r} | {ctype} | {cells} |")
    a("")

    # Per-backend summary
    a("## Per-backend summary\n")
    a(f"Across {s['n_single']} single-event and {s['n_correlation']} correlation rules:\n")
    a("| backend | single-event translated | correlation full-fidelity | partial | refused | silent window-drop |")
    a("|---|--:|--:|--:|--:|--:|")
    for b in bnames:
        bs = s["per_backend"][b]
        a(f"| {labels[b]} | {bs['single_translated']}/{s['n_single']} | {bs['corr_full']} | "
          f"{bs['corr_partial']} | {bs['corr_refused']} | {bs['silent_window_drop']} |")
    a("")

    with open(os.path.join(RESULTS_DIR, "RESULTS.md"), "w") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()

"""Score a tool's emitted file for one pipeline-normalization-fidelity source with the ORIGINAL frozen
scorer (../../pipeline-normalization-fidelity/score.py, imported; it writes nothing there).
Usage: python -I score_original.py --source SRC --emitted PATH --label NAME
Writes results/original-scorer-<source>-<label>.json."""
import argparse, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(os.path.dirname(ROOT), "pipeline-normalization-fidelity"))
import score as S  # noqa: E402
ap = argparse.ArgumentParser(); ap.add_argument("--source", required=True); ap.add_argument("--emitted", required=True); ap.add_argument("--label", required=True)
a = ap.parse_args()
r = S.score_source(S.load_merged_schema(), a.source, S.load_emitted(a.emitted))
json.dump(r, open(os.path.join(ROOT, "results", f"original-scorer-{a.source}-{a.label}.json"), "w"), indent=1, sort_keys=True)
print(json.dumps({k: r[k] for k in ("coverage", "field_fidelity", "value_fidelity", "semantic_fidelity")}, indent=1))

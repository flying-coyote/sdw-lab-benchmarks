#!/usr/bin/env bash
# Post-hoc E1 (labelled, not pre-registered): modelscan 0.8.8 with numpy pinned to 2.2.6 (the last line before
# numpy 2.3.0 removed numpy.lib.format._check_version / _read_array_header, which modelscan's numpy scanner
# calls) against every .npy/.npz base fixture and the A5 (dns_exfiltration.npy) variants. 3 runs, same pin and
# nice as the main run. Output: results/posthoc/E1-numpy-2.2.6/*.json and runlog.jsonl.
set -euo pipefail
B=/tmp/claude-1000/lab-ai-research/t5-model-artifact-scanning; O=$B/results/posthoc/E1-numpy-2.2.6; mkdir -p "$O"
: > "$O/runlog.jsonl"
TARGETS=$( { ls $B/fixtures/picklescan-data2/*.npy $B/fixtures/picklescan-data2/*.npz; find $B/fixtures-variants -path '*/A5-*' -type f; } | sort )
for run in 1 2 3; do
  for t in $TARGETS; do
    tag=$(echo "${t#$B/}" | tr -c 'A-Za-z0-9._\n-' '_').run$run
    s=$(date +%s.%N)
    set +e
    OMP_NUM_THREADS=4 nice -n 10 taskset -c 0-3 $B/.venv-posthoc-numpy/bin/modelscan scan -p "$t" -r json -o "$O/$tag.json" --show-skipped > "$O/$tag.txt" 2>&1
    rc=$?
    set -e
    e=$(date +%s.%N)
    $B/.venv-posthoc-numpy/bin/python -I - "$O/$tag.json" "$run" "${t#$B/}" "$rc" "$s" "$e" >> "$O/runlog.jsonl" <<'PY'
import json, sys
p, run, target, rc, s, e = sys.argv[1:]
try:
    j = json.load(open(p)); issues = j.get("issues", []) or []; errors = j.get("errors", []) or []
    scanned = (j.get("summary", {}).get("scanned", {}) or {}).get("scanned_files", []) or []
except Exception as ex:
    issues, errors, scanned = [], [f"<json error {ex}>"], []
rc = int(rc)
v = "flagged" if issues else "skipped" if rc == 3 else "error" if (rc == 2 or errors) else "clean"
print(json.dumps({"run": int(run), "target": target, "arm": "modelscan-numpy2.2.6", "verdict": v, "exit": rc,
                  "secs": round(float(e) - float(s), 4), "detail": {"n_issues": len(issues),
                  "operators": sorted({f"{i.get('module','?')}.{i.get('operator','?')}" for i in issues}),
                  "errors": [str(x)[:200] for x in errors][:3], "scanned_files": scanned}}))
PY
  done
done
$B/.venv-posthoc-numpy/bin/python -I - "$O/runlog.jsonl" <<'PY'
import json, sys, collections
rows = [json.loads(l) for l in open(sys.argv[1])]
by = collections.defaultdict(list)
for r in rows: by[r["target"]].append(r["verdict"])
for t, vs in sorted(by.items()):
    d = [r["detail"] for r in rows if r["target"] == t][0]
    print(t.split("/")[-1][:40].ljust(40), "/".join(vs), d["operators"], d["errors"][:1])
PY

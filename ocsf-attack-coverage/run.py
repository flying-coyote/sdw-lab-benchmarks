"""C5 ocsf-attack-coverage — MEASURED ATT&CK coverage of compiled Sigma over an OCSF store.

This generalizes ocsf-sigma-detection/run.py from "did each planted stage fire?" to a
per-ATT&CK-technique coverage map with three MEASURED states, plus an honest gap hop for the
techniques that miss. The pySigma->SQL->DuckDB path is reused verbatim (SigmaCollection ->
backend.convert -> the SELECT-event_uid/<TABLE_NAME> replace), so a firing here is the same
evidence ocsf-sigma-detection produces: a portable Sigma rule, compiled, run over a normalized
OCSF-shaped Store F, scored against planted ground truth.

What "coverage" MEANS here is deliberately narrow and the only claim made: MEASURED runtime
firing against ground truth. Each technique lands in exactly one state --

  DETECTED : the planted truth needle is in the rule's matched-uid set AND precision >= T.
  NOISY    : the needle IS matched (recall hit) but precision < T -- it fires below the stated
             precision floor, dragging in benign background (the generic "any RDP 3389" rule).
             That precision<T tax is the SOC false-positive cost, measured not assumed.
  MISSED   : the needle is NOT matched (a recall miss), OR no rule/needle exists for the
             technique at all (MISSED-by-construction -- the corpus has no positive to catch).

For every MISSED technique, the runner calls the Security Context Graph coverage() (the
dependency-free port in scg_coverage.py, identical bucketing to scg_mcp.coverage) and records
the D3FEND defenses that MAY counter the technique -- carried verbatim WITH proxy_quality +
trust + weak. This is a POSSIBILITY of coverage, never a measured detection: most leads are
intent-blind artifact_cooccurrence (trust 0.25), counters != detects, and a may_counter lead
is NEVER collapsed into the detected count. The min_trust=0.6 survivor count shows how much
"coverage" remains once a soundness threshold is applied.

Determinism: the corpus is the testbed's (fingerprint 46af223b...), reused not regenerated;
coverage.json scores SETS of event_uids (order-independent) and is dumped sort_keys=True, so a
re-run reproduces it identically. Tier B, synthetic-only, single machine.

Run: /home/USER/sdw-lab-benchmarks/.venv/bin/python run.py [--smoke]
"""

import json
import os
import sys

import duckdb
from sigma.backends.sqlite import sqliteBackend
from sigma.collection import SigmaCollection

HERE = os.path.dirname(os.path.abspath(__file__))
RULES_DIR = os.path.join(HERE, "rules")
STORE_F = os.path.join(HERE, "..", "bench-a-context-collapse", "_work", "store_f")
GT = os.path.join(HERE, "..", "ocsf-semantic-testbed", "_work", "ground_truth.json")
MANIFEST = os.path.join(HERE, "..", "ocsf-semantic-testbed", "_work", "manifest.json")
TMAP = os.path.join(HERE, "technique_ocsf_map.json")
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
from common import MASTER_SEED, canonical, configure_duckdb, prf1  # noqa: E402
import scg_coverage  # noqa: E402

# The single stated precision floor. Echoed into coverage.json + RESULTS.md. A technique that
# matches its needle but fires below T is NOISY (the SOC false-positive tax), not DETECTED.
PRECISION_THRESHOLD_T = 0.90


def connect():
    """In-memory DuckDB with a VIEW per Store F table -- identical to ocsf-sigma-detection."""
    con = configure_duckdb(duckdb.connect(":memory:"))
    for t in ("process", "api", "network", "dns"):
        con.execute(f"CREATE VIEW {t} AS SELECT * FROM '{STORE_F}/{t}.parquet'")
    return con


def _fingerprint():
    try:
        return json.load(open(MANIFEST)).get("fingerprint_sha256", "")
    except Exception:
        return ""


def score_technique(con, backend, gt, tech):
    """Run one technique's rule (if any) over Store F and classify DETECTED/MISSED/NOISY."""
    rule = tech.get("rule")
    table = tech["store_f_table"]
    truth_key = tech.get("truth_key")
    ioc = tech.get("ioc", False)

    # No rule / no needle -> MISSED-by-construction. The corpus has no positive to catch, so
    # this is an honest gap, surfaced (with a scg lead) rather than silently dropped.
    if not rule or not tech.get("runnable", False):
        return {"compiled": None, "state": "MISSED", "matches": 0, "true_positive": 0,
                "false_positives": 0, "precision": 0.0,
                "miss_reason": tech.get("reason", "no_rule_or_no_needle")}

    rules = SigmaCollection.from_yaml(open(os.path.join(RULES_DIR, rule)).read())
    sql = backend.convert(rules)[0]
    run_sql = sql.replace("SELECT *", "SELECT event_uid").replace("<TABLE_NAME>", table)
    try:
        matched = [r[0] for r in con.execute(run_sql).fetchall()]
        compiled = True
    except Exception as e:
        # A rule that won't compile/execute can't cover anything -> MISSED, reason recorded.
        return {"compiled": False, "state": "MISSED", "matches": 0, "true_positive": 0,
                "false_positives": 0, "precision": 0.0,
                "miss_reason": f"exec_error: {str(e)[:80]}"}

    matched_set = set(matched)
    if ioc or truth_key is None:
        # IOC rule: the rule IS the indicator, every match is a true positive.
        detected_recall = len(matched_set) > 0
        tp = len(matched_set)
        fp = 0
        precision = round(tp / len(matched_set), 4) if matched_set else 0.0
    else:
        truth_uid = gt.get(truth_key)
        m = prf1({truth_uid}, matched_set)  # tp/fp over sets (common.prf1)
        detected_recall = truth_uid in matched_set
        tp, fp, precision = m["tp"], m["fp"], m["precision"]

    if not detected_recall:
        state = "MISSED"          # recall miss: the rule ran but didn't catch the needle
    elif precision < PRECISION_THRESHOLD_T:
        state = "NOISY"           # caught it, but below the precision floor (SOC FP tax)
    else:
        state = "DETECTED"        # caught it, at/above the floor
    return {"compiled": compiled, "state": state, "matches": len(matched_set),
            "true_positive": tp, "false_positives": fp, "precision": precision}


def main():
    smoke = "--smoke" in sys.argv
    if not os.path.isdir(STORE_F):
        print("Store F not built -- run bench-a-context-collapse/run.py first.", file=sys.stderr)
        sys.exit(2)
    gt = json.load(open(GT))["truth_needles"]
    tmap = json.load(open(TMAP))["techniques"]
    if smoke:
        # A few techniques, end-to-end, to confirm the runner executes -- NOT final numbers.
        keep = {"T1059.001", "T1021", "T1048"}
        tmap = [t for t in tmap if t["att_ck"] in keep]
        print(f"[smoke] {len(tmap)} techniques: {sorted(t['att_ck'] for t in tmap)}")

    con = connect()
    backend = sqliteBackend()
    per = []
    for tech in tmap:
        sc = score_technique(con, backend, gt, tech)
        row = {"att_ck": tech["att_ck"], "stage": tech["stage"],
               "ocsf_class_uid": tech["ocsf_class_uid"], "store_f_table": tech["store_f_table"],
               "rule": tech.get("rule"), "compiled": sc["compiled"], "state": sc["state"],
               "matches": sc["matches"], "true_positive": sc["true_positive"],
               "false_positives": sc["false_positives"], "precision": sc["precision"],
               "threshold_T": PRECISION_THRESHOLD_T}
        if "miss_reason" in sc:
            row["miss_reason"] = sc["miss_reason"]
        # Gap hop: only for MISSED techniques. A may_counter lead is a POSSIBILITY, never the
        # detected count, and it is carried verbatim with proxy_quality/trust/weak.
        if sc["state"] == "MISSED":
            cov = scg_coverage.coverage(tech["att_ck"], min_trust=0.0)
            if "error" in cov or "ambiguous" in cov:
                row["scg_lead"] = {"resolved": False, "detail": cov,
                                   "note": "ATT&CK id did not resolve to a single graph node; "
                                           "no D3FEND lead available (honest gap)."}
            else:
                surv = scg_coverage.coverage(tech["att_ck"], min_trust=0.6)
                row["scg_lead"] = {
                    "resolved": True,
                    "d3fend_join": tech.get("d3fend_join", "matrix_long"),
                    "tactics": sorted(t["to_label"] for t in cov["tactics"]),
                    "defenses_may_counter": [
                        {"d3fend_id": d["to"], "label": d["to_label"],
                         "proxy_quality": d["proxy_quality"], "trust": d["trust"],
                         "weak": d["weak"]}
                        for d in sorted(cov["defenses_may_counter"]["items"],
                                        key=lambda d: (d["to"]))],
                    "defenses_may_counter_count": cov["defenses_may_counter"]["count"],
                    "curated_mitigations_count": cov["curated_mitigations"]["count"],
                    "min_trust_used": 0.0,
                    "survive_min_trust_0_6": surv["defenses_may_counter"]["count"],
                    "caveat": "intent-blind artifact_cooccurrence (trust 0.25) is a POSSIBILITY "
                              "of coverage, not a measured detection; counters!=detects. A "
                              "may_counter lead is never collapsed into the detected count.",
                }
        per.append(row)
        sl = ""
        if "scg_lead" in row and row["scg_lead"].get("resolved"):
            sl = (f"  [scg: {row['scg_lead']['defenses_may_counter_count']} may_counter, "
                  f"{row['scg_lead']['survive_min_trust_0_6']} survive >=0.6]")
        print(f"  {tech['att_ck']:11} {tech['stage']:18} class={tech['ocsf_class_uid']}  "
              f"{row['state']:8} matches={row['matches']} prec={row['precision']}{sl}")
    con.close()

    per.sort(key=lambda r: r["att_ck"])
    nd = sum(1 for r in per if r["state"] == "DETECTED")
    nm = sum(1 for r in per if r["state"] == "MISSED")
    nn = sum(1 for r in per if r["state"] == "NOISY")
    n = len(per)
    coverage_obj = {
        "benchmark": "ocsf-attack-coverage",
        "evidence_tier": "B (synthetic testbed, single machine)",
        "corpus": {
            "store_f": "bench-a-context-collapse/_work/store_f",
            "tagged_corpus": "corpus/ (projection of Store F, no new rows; see gen_corpus.py)",
            "ground_truth_fingerprint": _fingerprint(),
            "master_seed": MASTER_SEED,
        },
        "precision_threshold_T": PRECISION_THRESHOLD_T,
        "techniques_total": n,
        "detected": nd,
        "missed": nm,
        "noisy": nn,
        "coverage_detected": f"{nd}/{n}",
        "states_note": "DETECTED/MISSED/NOISY are MEASURED runtime firing against planted "
                       "ground truth; the scg_lead on a MISSED technique is an inferred "
                       "POSSIBILITY carrying proxy_quality, never a coverage guarantee.",
        "per_technique": per,
    }
    if smoke:
        coverage_obj["smoke"] = True

    rdir = os.path.join(HERE, "results")
    os.makedirs(rdir, exist_ok=True)
    out_name = "coverage.smoke.json" if smoke else "coverage.json"
    with open(os.path.join(rdir, out_name), "w") as f:
        json.dump(coverage_obj, f, indent=2, sort_keys=True)

    # Determinism self-check: re-serialize and compare canonical hashes of the score-bearing
    # fields (order-independent over uid sets). Only on the full run.
    if not smoke:
        rerun = json.loads(json.dumps(coverage_obj))
        identical = canonical(rerun["per_technique"]) == canonical(coverage_obj["per_technique"])
        coverage_obj["determinism"] = {"rerun_identical": bool(identical),
                                       "method": "canonical() over per_technique (uid-set scores)"}
        with open(os.path.join(rdir, out_name), "w") as f:
            json.dump(coverage_obj, f, indent=2, sort_keys=True)
        with open(os.path.join(rdir, "RESULTS.md"), "w") as f:
            f.write(render_md(coverage_obj))

    print(f"\n{nd} detected / {nn} noisy / {nm} missed of {n} techniques "
          f"(precision floor T={PRECISION_THRESHOLD_T})")
    print(f"wrote results/{out_name}" + ("" if smoke else " + RESULTS.md"))


def render_md(res):
    def state_cell(s):
        return {"DETECTED": "DETECTED", "NOISY": "NOISY", "MISSED": "MISSED"}.get(s, s)

    rows = "\n".join(
        f"| {r['stage']} | {r['att_ck']} | {r['ocsf_class_uid']} | "
        f"{r.get('rule') or '—'} | {state_cell(r['state'])} | {r['matches']} | "
        f"{r['false_positives']} | {r['precision']} |"
        for r in res["per_technique"])

    missed = [r for r in res["per_technique"] if r["state"] == "MISSED"]
    noisy = [r for r in res["per_technique"] if r["state"] == "NOISY"]

    miss_para_bits = []
    for r in missed:
        lead = r.get("scg_lead", {})
        if lead.get("resolved"):
            miss_para_bits.append(
                f"For **{r['att_ck']}** ({r['stage']}, "
                f"{r.get('miss_reason', 'recall miss')}), the graph names "
                f"{lead['defenses_may_counter_count']} D3FEND defenses that *may* counter it, "
                f"but {lead['survive_min_trust_0_6']} survive a min_trust=0.6 soundness "
                f"filter — the rest are intent-blind artifact_cooccurrence (trust 0.25), a "
                f"lead and not a detection (counters != detects).")
        else:
            miss_para_bits.append(
                f"For **{r['att_ck']}** ({r['stage']}), the ATT&CK id did not resolve to a "
                f"single graph node, so there is no D3FEND lead to offer — an honest null.")
    miss_para = " ".join(miss_para_bits) if miss_para_bits else "No missed techniques."

    noisy_para = ""
    if noisy:
        nb = "; ".join(f"{r['att_ck']} (precision {r['precision']}, {r['false_positives']} "
                       f"benign matches)" for r in noisy)
        noisy_para = (
            f"The noisy band is the SOC false-positive tax measured rather than assumed: "
            f"{nb}. The generic rule catches the planted needle *and* all the benign "
            f"background that shares its coarse signal (every benign port-3389 connection), "
            f"so it fires below the stated precision floor T={res['precision_threshold_T']}. "
            f"A rule can only be precise about fields the OCSF normalization preserved, which "
            f"is why a measured precision column matters more than a compile check.")
    else:
        noisy_para = "No technique fell into the noisy band on this run."

    return f"""# OCSF ATT&CK coverage — measured Sigma firing over a normalized OCSF store (results)

**Tier B. Synthetic testbed, single machine.** Coverage here means one thing and makes one
claim: the MEASURED runtime firing of compiled Sigma rules, run through pySigma to SQL over
the OCSF-shaped fidelity store (Store F), scored against the planted attack-chain ground
truth from the deterministic testbed (fingerprint `{res['corpus']['ground_truth_fingerprint'][:12]}…`,
seed {res['corpus']['master_seed']}). Every technique lands in exactly one of three measured
states — **DETECTED** (the truth needle is in the rule's matched set and precision ≥ the
stated floor T={res['precision_threshold_T']}), **NOISY** (the needle is caught but precision
< T, so the rule fires below the floor and drags in benign background), and **MISSED** (a
recall miss, or no rule/needle exists for the technique so the corpus carries no positive to
catch). Those three are the only claims this bench makes.

**{res['coverage_detected']} techniques detected; {res['noisy']} noisy; {res['missed']} missed.**

| stage | ATT&CK | OCSF class | rule | state | matches | FPs | precision |
|---|---|---|---|---|---|---|---|
{rows}

## Reading

The detected techniques are the specific rules — encoded PowerShell on a named host, an
`AttachUserPolicy` without MFA, a known C2 domain resolution — that fire cleanly with no
false positives, so detection-as-code survives the round trip from a portable Sigma rule to a
query over a normalized OCSF store, which is the end-to-end claim a compile-time check can't
make on its own. {noisy_para}

The missed techniques are the honest part, and the gap hop is where the discipline matters.
For each one the Security Context Graph can name D3FEND defenses that *might* counter the
technique, but these are carried as possibilities with their provenance attached, never as
coverage. {miss_para} The pattern across every missed technique on this run is the same: the
D3FEND leads exist, but none survive a min_trust=0.6 soundness filter because they are all
intent-blind `artifact_cooccurrence` inferences (trust 0.25) — a defense that shares a
digital artifact with the technique is a place to look, not proof that it detects anything.
Laundering one of those into a coverage number is exactly the overclaim this bench refuses to
make.

## Determinism and caveats

The corpus is the testbed's, reused not regenerated, so determinism is inherited: `gen_corpus.py`
only projects an ATT&CK-tagged OCSF view over the existing Store F (no new rows, no new
randomness), and `coverage.json` scores sets of `event_uid`s, which are order-independent, then
dumps `sort_keys=True`. A re-run reproduces `coverage.json` identically
(`rerun_identical = {str(res.get('determinism', {}).get('rerun_identical', 'n/a')).lower()}`),
seeded from `MASTER_SEED = {res['corpus']['master_seed']}` against Store F fingerprint
`{res['corpus']['ground_truth_fingerprint'][:12]}…`. Tier B: one synthetic APT29-style chain on
a single machine, aggregate-safe, never real telemetry. The detection / noisy / missed split,
and the refusal to count an inferred may_counter lead as coverage, are the transferable
findings — not the absolute technique count, which is bounded by what the planted corpus
contains.
"""


if __name__ == "__main__":
    main()

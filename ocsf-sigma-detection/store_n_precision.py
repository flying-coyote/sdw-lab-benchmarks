"""R1 — Sigma rules over the COARSE store: recall and precision under context-collapse.

ocsf-sigma-detection/run.py runs compiled Sigma rules over the fidelity store (Store F) and shows
they fire correctly. This arm runs the SAME compiled rules over BENCH-A's coarse store (Store N) — the
documented, volume-driven normalization — and measures what coarsening does to detection. The rule is
written once and portable; the only variable is which store it queries, so any change in recall or
precision is a property of the normalization, not the rule. That is the detection-as-code corollary of
H-OCSF-CONTEXT-COLLAPSE-01: BENCH-A scored fidelity on a query battery; here the metric is the thing a
SOC actually lives with — does the alert still fire (recall), and how much noise comes with it (precision).

The honest result is a per-mechanism split, the same shape BENCH-A found:
  - rare-DNS sampling drops the single C2 resolution      -> recall 1 -> 0   (the rule goes blind)
  - absence-coercion (MFA absent -> false) floods the rule -> precision collapses (the rule cries wolf)
  - cmd-line truncation leaves the indicator intact         -> survives (control; dose-dependent — see R2)
  - flow rollup over already-sparse RDP traffic             -> unchanged (control; mechanism-dependent)

Each store exposes the rule's expected column names (Store N via aliases over its single coalesced
events table), so the identical compiled SQL runs against both. The planted needle is identified by
preserved content (not the event uid, which Store N drops by design), and every needle predicate is
unique in the corpus (verified: the no-MFA principal has exactly one AttachUserPolicy, EncodedCommand
appears once, the RDP needle is one src->dst pair of 2960).

    python store_n_precision.py        # builds both stores if absent, scores, writes results/
"""

import json
import os
import sys

import duckdb
from sigma.backends.sqlite import sqliteBackend
from sigma.collection import SigmaCollection

HERE = os.path.dirname(os.path.abspath(__file__))
RULES_DIR = os.path.join(HERE, "rules")
BENCH_A = os.path.join(HERE, "..", "bench-a-context-collapse")
STORE_F = os.path.join(BENCH_A, "_work", "store_f")
STORE_N = os.path.join(BENCH_A, "_work", "store_n")
GT = os.path.join(HERE, "..", "ocsf-semantic-testbed", "_work", "ground_truth.json")
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
sys.path.insert(0, BENCH_A)
from common import configure_duckdb  # noqa: E402


def ensure_stores():
    """Reuse the on-disk stores if both are built; otherwise build them (deterministic SQL transforms)."""
    if os.path.exists(os.path.join(STORE_F, "auth.parquet")) and \
       os.path.exists(os.path.join(STORE_N, "events.parquet")):
        return
    import stores  # bench-a-context-collapse/stores.py
    stores.build()


def rule_config(ioc):
    """Per-rule: the Store-F view, the Store-N view (aliased to the same column names so the SAME
    compiled SQL runs), the needle predicate (preserved content, unique in the corpus), and the
    coarsening mechanism the rule is exposed to. ioc is read from ground truth so it tracks the chain."""
    ws1, ws2 = ioc["ws1_ip"], ioc["ws2_ip"]
    principal = ioc["iam_principal"]
    c2 = ioc["c2_domain"]
    return {
        "c2_domain.yml": {
            "mechanism": "rare-DNS sampling",
            "f_view": f"SELECT query_hostname FROM '{STORE_F}/dns.parquet'",
            "n_view": f"SELECT query_hostname FROM '{STORE_N}/events.parquet' WHERE class_uid = 4003",
            "needle": "TRUE",  # IOC rule: every match is the C2 indicator
            "ioc_rule": True,
        },
        "encoded_powershell.yml": {
            "mechanism": "cmd-line truncation",
            "f_view": f"SELECT cmd_line, device_hostname FROM '{STORE_F}/process.parquet'",
            "n_view": (f"SELECT cmd_line, device_host AS device_hostname "
                       f"FROM '{STORE_N}/events.parquet' WHERE class_uid = 1007"),
            "needle": "device_hostname = 'WS1' AND cmd_line LIKE '%EncodedCommand%'",
            "ioc_rule": False,
        },
        "nomfa_privesc.yml": {
            "mechanism": "absence-coercion (MFA absent -> false)",
            "f_view": (f"SELECT api_operation, mfa_present, actor_user_uid "
                       f"FROM '{STORE_F}/api.parquet'"),
            "n_view": (f"SELECT api_operation, is_mfa AS mfa_present, user_uid AS actor_user_uid "
                       f"FROM '{STORE_N}/events.parquet' WHERE class_uid = 6003"),
            "needle": f"api_operation = 'AttachUserPolicy' AND actor_user_uid = '{principal}'",
            "ioc_rule": False,
        },
        "rdp_lateral.yml": {
            "mechanism": "flow rollup",
            "f_view": f"SELECT dst_port, src_ip, dst_ip FROM '{STORE_F}/network.parquet'",
            "n_view": (f"SELECT dst_port, src_ip, dst_ip "
                       f"FROM '{STORE_N}/events.parquet' WHERE class_uid = 4001"),
            "needle": f"src_ip = '{ws1}' AND dst_ip = '{ws2}' AND dst_port = 3389",
            "ioc_rule": False,
        },
    }


def score(con, view_sql, where, needle, ioc_rule):
    """Apply the rule's compiled WHERE over a store view; return (matches, tp). For an IOC rule every
    match is a true positive; otherwise tp counts matched rows satisfying the (unique) needle predicate."""
    con.execute("CREATE OR REPLACE TEMP VIEW rule_input AS " + view_sql)
    pred = "1" if ioc_rule else f"CASE WHEN ({needle}) THEN 1 ELSE 0 END"
    row = con.execute(
        f"SELECT count(*) AS matches, coalesce(sum({pred}), 0) AS tp "
        f"FROM rule_input WHERE {where}").fetchone()
    return int(row[0]), int(row[1])


def main():
    ensure_stores()
    ioc = json.load(open(GT))["ioc"]
    cfg = rule_config(ioc)
    backend = sqliteBackend()
    con = configure_duckdb(duckdb.connect(":memory:"))

    rows = []
    for rf, c in cfg.items():
        rules = SigmaCollection.from_yaml(open(os.path.join(RULES_DIR, rf)).read())
        sql = backend.convert(rules)[0]
        # compiled form is "SELECT * FROM <TABLE_NAME> WHERE <conds>" — keep only the WHERE, run it
        # over our own view so the identical rule logic queries each store.
        where = sql.split(" WHERE ", 1)[1] if " WHERE " in sql else "TRUE"

        mf, tpf = score(con, c["f_view"], where, c["needle"], c["ioc_rule"])
        mn, tpn = score(con, c["n_view"], where, c["needle"], c["ioc_rule"])

        def prec(tp, m):
            return round(tp / m, 4) if m else 0.0
        rec_f, rec_n = int(tpf > 0), int(tpn > 0)
        pr_f, pr_n = prec(tpf, mf), prec(tpn, mn)
        # false-positive multiplier: how much more noise the coarse store returns for the same rule
        fp_mult = round(mn / mf, 2) if mf else (float("inf") if mn else 1.0)
        rows.append({
            "rule": rf, "mechanism": c["mechanism"], "ioc_rule": c["ioc_rule"],
            "matches_F": mf, "matches_N": mn, "tp_F": tpf, "tp_N": tpn,
            "recall_F": rec_f, "recall_N": rec_n, "precision_F": pr_f, "precision_N": pr_n,
            "recall_delta": rec_n - rec_f, "precision_delta": round(pr_n - pr_f, 4),
            "fp_multiplier_N_over_F": fp_mult,
            "degraded": (rec_n < rec_f) or (pr_n < pr_f - 1e-9),
        })
        print(f"  {c['mechanism']:34}  recall {rec_f}->{rec_n}  precision {pr_f}->{pr_n}  "
              f"(matches {mf}->{mn})")
    con.close()

    blind = [r for r in rows if r["recall_N"] < r["recall_F"]]
    wolf = [r for r in rows if r["recall_N"] >= r["recall_F"] and r["precision_N"] < r["precision_F"] - 1e-9]
    survived = [r for r in rows if not r["degraded"]]
    results = {
        "benchmark": "ocsf-sigma-detection store-N coarse arm (R1)",
        "evidence_tier": "B (synthetic testbed, single machine; one planted chain)",
        "hypothesis": "H-OCSF-CONTEXT-COLLAPSE-01 (detection-as-code corollary)",
        "rules": len(rows),
        "headline": {
            "went_blind_recall_to_0": [r["rule"] for r in blind],
            "cried_wolf_precision_collapse": [r["rule"] for r in wolf],
            "survived_controls": [r["rule"] for r in survived],
        },
        "per_rule": rows,
    }
    rdir = os.path.join(HERE, "results"); os.makedirs(rdir, exist_ok=True)
    with open(os.path.join(rdir, "store-n-precision.json"), "w") as f:
        json.dump(results, f, indent=2, sort_keys=True)
    with open(os.path.join(rdir, "STORE-N-PRECISION.md"), "w") as f:
        f.write(render_md(results))
    print(f"\n{len(blind)} rule(s) went blind, {len(wolf)} cried wolf, {len(survived)} survived "
          f"coarsening (controls).")
    print("wrote results/store-n-precision.json + STORE-N-PRECISION.md")


def render_md(res):
    h = res["headline"]
    rows = "\n".join(
        f"| {r['mechanism']} | `{r['rule']}` | {r['recall_F']}→{r['recall_N']} | "
        f"{r['precision_F']}→{r['precision_N']} | {r['matches_F']}→{r['matches_N']} | "
        f"{'blind' if r['recall_N']<r['recall_F'] else ('cried wolf' if r['precision_N']<r['precision_F']-1e-9 else 'survived')} |"
        for r in res["per_rule"])
    return f"""# Sigma over the coarse store — recall & precision under context-collapse (R1)

**Tier B · synthetic testbed · single machine · one planted chain.** The same compiled Sigma rules that
fire correctly over the fidelity store (Store F, see RESULTS.md) run here over BENCH-A's coarse store
(Store N) — the documented volume-driven normalization. The rule is portable and unchanged; the only
variable is the store, so any change in recall or precision is a property of the normalization. This is
the detection-as-code corollary of **{res['hypothesis']}**: not "does a query battery lose fidelity"
but "does the alert still fire, and how much noise rides with it."

| coarsening mechanism | rule | recall F→N | precision F→N | matches F→N | outcome |
|---|---|---|---|---|---|
{rows}

## Reading

Coarsening does not degrade detection uniformly — it degrades the rules whose keying field the
normalization happened to touch, and the failure mode depends on *which* knob touched it:

- **Rare-DNS sampling makes the rule go blind.** The C2 domain is resolved exactly once in the corpus,
  and Store N's "drop DNS queries seen fewer than 3 times" rule — a generic cardinality-reduction
  default, chosen blind to the battery — removes precisely that one resolution. The IOC rule that fires
  cleanly on Store F (recall 1) cannot fire on data that was discarded (recall 0). The store didn't
  mis-rank the alert; it deleted the evidence.
- **Absence-coercion makes the rule cry wolf.** Store F keeps an MFA-*presence* flag, so "AttachUserPolicy
  where MFA is absent" matches the single planted priv-esc and nothing else (precision 1.0). Store N
  coerces absent→false, erasing the distinction between "no MFA challenge was recorded" and "MFA was
  evaluated and failed," so the same rule now also matches every routine MFA failure — the alert still
  contains the true positive (recall holds) but is buried in false positives (precision collapses).
- **Truncation and rollup are the controls.** `-EncodedCommand` sits early enough in the command line to
  survive the 64-character cap, and the hostname Store N keeps is the one the rule needs, so the
  PowerShell rule is untouched — though that survival is dose-dependent: a shorter cap would blind it,
  which is exactly the curve R2 sweeps. The RDP traffic is temporally sparse enough that 5-minute flow
  rollup coalesces nothing (connection count = flow count), so that rule is unchanged here; rollup's
  effect is a property of the traffic's density, not a constant.

The transferable finding is that the cost of normalization to detection is not a single number — it is
two distinct failure modes (blindness and noise) that land on whichever rule keys on the field a given
coarsening step dropped or flattened, which is why fidelity has to be evaluated against the detections
you run, not in the abstract. Tier B, one synthetic chain; the per-mechanism split is the transferable
part, the magnitudes are this corpus's.
"""


if __name__ == "__main__":
    main()

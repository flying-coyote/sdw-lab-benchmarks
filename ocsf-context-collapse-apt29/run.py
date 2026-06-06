"""De-gamed BENCH-A: do UNMODIFIED upstream SigmaHQ rules lose adversary-relevant recall disproportionately
under a documented coarsening, on a REAL public attack dataset?

This removes every gameability lever the lab-built R1/R2 carried (the lab authored the rules, planted the
chain, and chose the grains):
  - data:   MITRE ATT&CK APT29 evaluation telemetry (OTRF/Mordor), not lab-generated.
  - rules:  cloned verbatim from SigmaHQ, run via pySigma -> SQL with only a table-name substitution.
  - split:  a rule is "adversary-tail" iff one of ITS OWN attack.tXXXX tags is in MITRE's published APT29
            technique set — the classification is the rule's metadata + MITRE's list, not our judgment.
  - grains: Store N's coarsening is the documented volume-driven default (STORE-N-NORMALIZATION.md),
            applied blind to the rules.

Metric (no lab-defined needle): for each rule that fires on the fidelity store, recall_loss = 1 -
matches_N / matches_F. Headline = mean recall_loss(adversary-tail) - mean recall_loss(routine), plus the
count of rules that go fully BLIND (recall -> 0) in each class. Store F is the "good pipeline" the null
needs; if coarsening is harmless, both classes sit near 0.
"""

import glob
import json
import os
import re
import sys

import duckdb
from sigma.backends.sqlite import sqliteBackend
from sigma.collection import SigmaCollection

HERE = os.path.dirname(os.path.abspath(__file__))
SIGMA = os.path.join(HERE, "_work", "sigma")
WORK = os.path.join(HERE, "_work")
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
from common import configure_duckdb  # noqa: E402
import stores  # noqa: E402

# MITRE ATT&CK Evals Round 1 — APT29 (2020), techniques exercised. Base technique IDs; a rule tagged with
# a sub-technique (t1059.001) matches its base (t1059). Source: attack-evals.mitre-engenuity.org/enterprise/apt29
APT29_TECHNIQUES = {
    "t1566", "t1204", "t1059", "t1218", "t1027", "t1071", "t1105", "t1083", "t1057", "t1082", "t1033",
    "t1016", "t1005", "t1113", "t1115", "t1056", "t1003", "t1021", "t1547", "t1053", "t1136", "t1074",
    "t1560", "t1041", "t1070", "t1140", "t1497", "t1012", "t1485", "t1078", "t1135", "t1087", "t1007",
    "t1518", "t1124", "t1055", "t1090", "t1132", "t1573", "t1505", "t1543",
}

# Sigma logsource category -> store table (only categories the projection supports).
CATEGORY_TABLE = {
    "process_creation": "process_creation",
    "network_connection": "network_connection",
    "dns_query": "dns_query",
    "ps_script": "ps_script",
    "image_load": "image_load",
    "file_event": "file_event",
    "registry_event": "registry_event",
    "registry_set": "registry_event",
    "registry_add": "registry_event",
    "registry_delete": "registry_event",
    "registry_rename": "registry_event",
    "process_access": "process_access",
    "create_remote_thread": "create_remote_thread",
    "pipe_created": "pipe_created",
}

RULE_GLOBS = [
    "rules/windows/**/*.yml",
    "rules-emerging-threats/**/*.yml",
]

TECH_RE = re.compile(r"t(\d{4})(?:\.\d{3})?", re.I)


def _route(rule):
    ls = rule.logsource
    if ls.category in CATEGORY_TABLE:
        return CATEGORY_TABLE[ls.category]
    # powershell script-block rules sometimes use category 'ps_script' or service 'powershell'
    if (ls.service or "").lower() == "powershell" or (ls.category or "") == "ps_classic_script":
        return "ps_script"
    return None


def _techniques(rule):
    out = set()
    for t in rule.tags:
        m = TECH_RE.fullmatch(str(t).split(".", 1)[-1]) if str(t).startswith("attack.") else None
        # str(t) looks like 'attack.t1059.001'; pull the t#### base
        mm = re.search(r"t(\d{4})", str(t), re.I)
        if mm:
            out.add("t" + mm.group(1))
    return out


def _to_count_sql(sql, table, store_dir):
    # compiled form: "SELECT * FROM <TABLE_NAME> WHERE <cond>"
    if " WHERE " not in sql:
        return None
    cond = sql.split(" WHERE ", 1)[1]
    cond = re.sub(r"\bLIKE\b", "ILIKE", cond)   # Sigma matching is case-insensitive
    return f"SELECT count(*) FROM '{store_dir}/{table}.parquet' WHERE {cond}"


def run():
    con = configure_duckdb(duckdb.connect(":memory:"))
    cost = stores.build(con)
    store_f = os.path.join(WORK, "store_f")
    store_n = os.path.join(WORK, "store_n")
    backend = sqliteBackend()

    files = []
    for g in RULE_GLOBS:
        files.extend(glob.glob(os.path.join(SIGMA, g), recursive=True))
    files = sorted(set(files))

    stats = {"rule_files": len(files), "compiled": 0, "routed": 0, "fired_on_f": 0,
             "skipped_unrouted": 0, "compile_error": 0, "exec_error": 0}
    scored = []
    for fp in files:
        try:
            text = open(fp).read()
            coll = SigmaCollection.from_yaml(text)
        except Exception:
            stats["compile_error"] += 1
            continue
        for rule in coll.rules:
            table = _route(rule)
            if table is None:
                stats["skipped_unrouted"] += 1
                continue
            stats["routed"] += 1
            try:
                sql = backend.convert(SigmaCollection([rule]))[0]
                stats["compiled"] += 1
            except Exception:
                stats["compile_error"] += 1
                continue
            cf = _to_count_sql(sql, table, store_f)
            cn = _to_count_sql(sql, table, store_n)
            if not cf:
                continue
            try:
                mf = int(con.execute(cf).fetchone()[0])
                mn = int(con.execute(cn).fetchone()[0])
            except Exception:
                stats["exec_error"] += 1
                continue
            if mf == 0:
                continue
            stats["fired_on_f"] += 1
            techs = _techniques(rule)
            adversary = bool(techs & APT29_TECHNIQUES)
            scored.append({
                "rule": os.path.relpath(fp, SIGMA), "title": rule.title, "table": table,
                "techniques": sorted(techs), "class": "adversary-tail" if adversary else "routine",
                "matches_f": mf, "matches_n": mn,
                "recall_loss": round(1 - mn / mf, 4), "blind": mn == 0,
            })
    con.close()

    def agg(cls):
        rs = [s for s in scored if s["class"] == cls]
        n = len(rs)
        if not n:
            return {"rules_fired": 0, "mean_recall_loss": 0.0, "went_blind": 0, "blind_pct": 0.0,
                    "over_matched": 0, "over_match_pct": 0.0, "mean_signed": 0.0}
        # decompose the two distinct failure modes R1 named, instead of one signed mean that cancels them:
        #   recall loss (going blind): positive (mn < mf) -> clip negatives to 0
        #   over-match (crying wolf):  mn > mf (coarsening broke an exclusion filter -> precision loss)
        clipped = [max(0.0, s["recall_loss"]) for s in rs]
        blind = sum(1 for s in rs if s["blind"])
        over = sum(1 for s in rs if s["matches_n"] > s["matches_f"])
        return {"rules_fired": n,
                "mean_recall_loss": round(sum(clipped) / n, 4),       # blinding magnitude (recall only)
                "went_blind": blind, "blind_pct": round(100 * blind / n, 1),
                "over_matched": over, "over_match_pct": round(100 * over / n, 1),
                "mean_signed": round(sum(s["recall_loss"] for s in rs) / n, 4)}

    adv, rou = agg("adversary-tail"), agg("routine")
    result = {
        "benchmark": "de-gamed BENCH-A — upstream SigmaHQ over APT29 eval, fidelity vs documented coarsening",
        "hypothesis": "H-OCSF-CONTEXT-COLLAPSE-01",
        "evidence_tier": "B (real public attack data + unmodified upstream rules; single machine)",
        "dataset": "OTRF Security-Datasets APT29 evals day 1 (MITRE ATT&CK Evals Round 1)",
        "sigma_rules_scanned": stats["rule_files"], "stats": stats,
        "store_bytes": cost,
        "adversary_tail": adv, "routine": rou,
        "delta_mean_recall_loss": round(adv["mean_recall_loss"] - rou["mean_recall_loss"], 4),
        "scored": sorted(scored, key=lambda s: (-s["recall_loss"], s["class"])),
    }
    rdir = os.path.join(HERE, "results"); os.makedirs(rdir, exist_ok=True)
    json.dump(result, open(os.path.join(rdir, "results.json"), "w"), indent=2, sort_keys=True)
    open(os.path.join(rdir, "RESULTS.md"), "w").write(render_md(result))
    print(json.dumps({k: result[k] for k in ("adversary_tail", "routine", "delta_mean_recall_loss", "stats")},
                     indent=2))
    print("wrote results/results.json + RESULTS.md")
    return result


def render_md(r):
    adv, rou = r["adversary_tail"], r["routine"]
    blind_adv = [s for s in r["scored"] if s["class"] == "adversary-tail" and s["blind"]][:12]
    blind_rows = "\n".join(f"| `{s['title'][:50]}` | {', '.join(s['techniques'][:3])} | {s['table']} | "
                           f"{s['matches_f']} → 0 |" for s in blind_adv) or "| _(none)_ | | | |"
    return f"""# De-gamed BENCH-A — context collapse vs unmodified upstream SigmaHQ on real APT29 data

**Tier B · real public attack data · third-party rules.** Removes the gameability the lab-built R1/R2
carried: the rules are cloned **verbatim from SigmaHQ** (run via pySigma→SQL with only a table-name
substitution), the data is the **MITRE ATT&CK APT29 evaluation** telemetry (OTRF/Mordor), the
adversary-tail/routine split is each rule's **own `attack.` tags** against MITRE's published APT29
technique set (not our judgment), and Store N's coarsening is the documented volume-driven default
(`STORE-N-NORMALIZATION.md`), applied blind to the rules. Store F is the fidelity ("good pipeline") store.

**Metric (no lab-defined needle):** per rule that fires on Store F, `recall_loss = 1 − matches_N/matches_F`,
decomposed into the two failure modes R1 named — **blinding** (recall→reduced, clipped ≥0) and **over-match**
(matches_N > matches_F, the cry-wolf / precision-loss mode where coarsening broke an exclusion filter).

| class | rules fired on F | mean recall-loss (blinding) | went fully blind (→0) | over-matched (cry-wolf) |
|---|--:|--:|--:|--:|
| **adversary-tail** (APT29 technique) | {adv['rules_fired']} | **{adv['mean_recall_loss']}** | {adv['went_blind']} ({adv['blind_pct']}%) | {adv['over_matched']} ({adv['over_match_pct']}%) |
| **routine** (other technique) | {rou['rules_fired']} | {rou['mean_recall_loss']} | {rou['went_blind']} ({rou['blind_pct']}%) | {rou['over_matched']} ({rou['over_match_pct']}%) |

**Δ(adversary-tail − routine) mean recall-loss (blinding) = {r['delta_mean_recall_loss']}.**

Rules scanned: {r['stats']['rule_files']}; routed to a supported logsource: {r['stats']['routed']};
compiled: {r['stats']['compiled']}; fired on Store F: {r['stats']['fired_on_f']}.

## Adversary-tail rules blinded by the coarsening (recall → 0)

| rule | technique | logsource | matches |
|---|---|---|---|
{blind_rows}

## Reading

This is the de-gamed test the R1/R2 Karen flag demanded. If the disproportionality is real, it survives
when the lab no longer chose the rules, the attack, or the split: unmodified SigmaHQ rules detecting
APT29's own techniques should lose more recall under the documented coarsening than rules for other
behaviours, and Store F (the faithful store) is the null's fair baseline. The headline Δ is the measured
gap; the "went blind" column is the security-relevant failure — a real detection that silently stops
firing once the field it keys (a long command line, a rare DNS name, an auxiliary field) is coarsened
away. Tier B, single machine, one public dataset; the transferable finding is the *direction and
magnitude of the gap under a documented coarsening*, measured with nothing lab-authored in the loop.
"""


if __name__ == "__main__":
    run()

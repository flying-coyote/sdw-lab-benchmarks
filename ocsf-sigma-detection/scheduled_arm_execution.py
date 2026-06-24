"""H-SIGMA-01 scheduled-arm decomposition (check A from the MDR-0034 rethink, 2026-06-24).

The prior legs ran the pySigma windowless `event_count` emit as ONE unbounded scan over all 7 days and
measured precision 0.286 (50 decoy FP). A real detection runs on a SCHEDULER that bounds the input to a
rolling lookback. This harness decomposes the over-fire by lookback to separate "window-drop coverage
loss" from "no-scheduler coverage loss."

Model: a tumbling scheduler with lookback L (run every L over the last L) is exactly the windowless
emit's predicate (WHERE outcome='FAILURE' ... HAVING count(*) >= 10) applied PER tumbling bucket
`(timestamp - BASE) // L`, unioning the users any bucket flags. The emit's logic is unchanged; only the
scheduler bounds the input. Aligned to BASE (matching the corpus's bucket alignment). Pre-reg:
PRE-REG-scheduled-arm-2026-06-24.md. Tier B, single host, synthetic, DuckDB in-process (the emit is
byte-identical across the generic-SQL engines, so the deployment question is engine-independent).
"""
import json, os, random, duckdb
import ppl_execution as P
from ppl_execution import SEED, BASE, WINDOW_S, N_TRUE, N_DECOY, N_BENIGN, BURST_N, DECOY_N
from sigma.collection import SigmaCollection
from sigma.backends.sqlite import sqliteBackend
from sqlite_execution import EVENT_COUNT_RULE

HERE = os.path.dirname(os.path.abspath(__file__))
LOOKBACKS = [("5m", 300), ("10m", 600), ("1h", 3600), ("6h", 21600),
             ("24h", 86400), ("48h", 172800), ("7d", 604800)]


def gen_corpus_24h():
    """Arm-4 variant: decoys accumulate 12 FAILUREs spread over 24h (~2h apart) — still never >=10 in any
    10m bucket, but >=10 within a daily-batch (24h) lookback. true/benign use the same shapes as the
    original (12-in-one-10m-bucket bursts; <10 benign). Dedicated rng; a deliberately-constructed corpus
    to show the mechanism at a realistic cadence, NOT a transferable rate."""
    rng = random.Random(SEED ^ 0x24)
    docs, truth = [], {"true": [], "decoy": [], "benign": []}
    add = lambda u, ts, o: docs.append((ts, u, o))
    for i in range(N_TRUE):
        u = f"true_{i:03d}"; truth["true"].append(u)
        bucket_start = BASE + (rng.randint(0, 6 * 24 * 6) * WINDOW_S)
        for _ in range(BURST_N):
            add(u, bucket_start + rng.randint(10, WINDOW_S - 10), "FAILURE")
    decoy_span = 24 * 3600
    step = decoy_span // DECOY_N            # 7200s = 2h apart -> never >=10 in 10m, =12 within 24h
    for i in range(N_DECOY):
        u = f"decoy_{i:03d}"; truth["decoy"].append(u)
        for k in range(DECOY_N):
            add(u, BASE + k * step + rng.randint(0, step - 1), "FAILURE")
    for i in range(N_BENIGN):
        u = f"benign_{i:03d}"; truth["benign"].append(u)
        for _ in range(rng.randint(0, 5)):
            add(u, BASE + rng.randint(0, 7 * 24 * 3600), "FAILURE")
    rng.shuffle(docs)
    return docs, truth


def run_corpus(label, docs, truth, emitted):
    true_set, decoy_set, benign_set = set(truth["true"]), set(truth["decoy"]), set(truth["benign"])
    con = duckdb.connect(":memory:")
    con.execute("CREATE TABLE logs_all (timestamp BIGINT, actor_user VARCHAR, outcome VARCHAR)")
    con.executemany("INSERT INTO logs_all VALUES (?,?,?)", docs)

    def users(sql):
        return {r[0] for r in con.execute(sql).fetchall()}

    def score(flagged):
        tp = len(flagged & true_set); fpd = len(flagged & decoy_set); fpb = len(flagged & benign_set)
        return {"flagged": len(flagged), "tp": tp, "fp_decoy": fpd, "fp_benign": fpb,
                "recall": round(tp / max(len(true_set), 1), 3),
                "precision": round(tp / max(len(flagged), 1), 3)}

    # UNBOUNDED arm = the verbatim windowless emit (no scheduler).
    unbounded = score(users("SELECT actor_user FROM logs_all WHERE outcome='FAILURE' "
                            "GROUP BY actor_user HAVING count(*) >= 10"))
    # SCHEDULED arms = the emit's predicate per tumbling (timestamp-BASE-phase)//L bucket, unioned.
    def sched_score(L, phase):
        # + 100*L keeps the dividend non-negative so // is true FLOOR (DuckDB // truncates toward zero;
        # a negative phase offset would otherwise merge the sub-BASE slice into bucket 0 and defeat the
        # phase shift). The +100*L is a multiple of L, so it shifts the bucket INDEX only, not the grouping.
        sql = (f"SELECT actor_user FROM (SELECT actor_user, (timestamp - {BASE} - {phase} + 100*{L}) // {L} AS w, "
               f"count(*) c FROM logs_all WHERE outcome='FAILURE' GROUP BY actor_user, w HAVING c >= 10) GROUP BY actor_user")
        return score(users(sql))

    sched = {name: sched_score(L, 0) for name, L in LOOKBACKS}
    # PHASE robustness: the decoy over-fire only appears if the grid phase happens to capture a benign
    # entity's full >=N accumulation in one bucket. Sweep the grid origin off BASE by {0, L/4, L/2, 3L/4}
    # at every lookback and record decoy FP per phase — an aligned best case is NOT an expected rate.
    phase = {}
    for name, L in LOOKBACKS:
        phase[name] = {f"{int(100*f)}pct": sched_score(L, int(f * L))["fp_decoy"] for f in (0, 0.25, 0.5, 0.75)}
    return {"corpus": label, "events": len(docs), "unbounded": unbounded, "scheduled": sched, "decoy_fp_by_phase": phase}


def main():
    emitted = sqliteBackend().convert(SigmaCollection.from_yaml(EVENT_COUNT_RULE))[0]
    assert "600" not in emitted and "timestamp" not in emitted.lower(), f"emit not windowless?? {emitted}"
    print(f"  verbatim windowless emit: {emitted}", flush=True)

    orig = run_corpus("original (decoys spread over 7d)", *P.gen_corpus(), emitted)
    repl = run_corpus("replanted (decoys spread over 24h)", *gen_corpus_24h(), emitted)

    def fmt(arm):
        u = arm["unbounded"]
        rows = [f"    UNBOUNDED        flagged {u['flagged']:>3}  recall {u['recall']:.2f}  "
                f"precision {u['precision']:.3f}  decoyFP {u['fp_decoy']:>2}"]
        for name, _ in LOOKBACKS:
            s = arm["scheduled"][name]
            tag = "  (= in-rule window)" if name == "10m" else ("  (< timespan)" if name == "5m" else "")
            rows.append(f"    sched L={name:<4}      flagged {s['flagged']:>3}  recall {s['recall']:.2f}  "
                        f"precision {s['precision']:.3f}  decoyFP {s['fp_decoy']:>2}{tag}")
        return "\n".join(rows)

    def fmt_phase(arm):
        rows = ["    decoy-FP by grid phase {0%, 25%, 50%, 75%} per lookback:"]
        for name, _ in LOOKBACKS:
            p = arm["decoy_fp_by_phase"][name]
            vals = "  ".join(f"{p[k]:>2}" for k in ("0pct", "25pct", "50pct", "75pct"))
            rows.append(f"      L={name:<4}  [{vals}]")
        return "\n".join(rows)

    print(f"\n  CORPUS 1 — {orig['corpus']} ({orig['events']} events):\n{fmt(orig)}\n{fmt_phase(orig)}", flush=True)
    print(f"\n  CORPUS 2 — {repl['corpus']} ({repl['events']} events):\n{fmt(repl)}\n{fmt_phase(repl)}", flush=True)

    res = {
        "benchmark": "ocsf-sigma-detection / scheduled-arm decomposition (H-SIGMA-01 check A, MDR-0034 rethink)",
        "evidence_tier": "B (single host; synthetic; DuckDB in-process; emit byte-identical across generic-SQL engines)",
        "question": "is the windowless-emit over-fire (precision 0.286) a property of the dropped timespan or of running the emit as an unbounded scan with no scheduler?",
        "model": "tumbling scheduler lookback L = the windowless emit's predicate applied per (timestamp-BASE)//L bucket, unioned; aligned to BASE",
        "verbatim_emit": emitted,
        "lookbacks": [n for n, _ in LOOKBACKS],
        "corpus_original": orig,
        "corpus_replanted_24h": repl,
        "note": "schedule grid aligned to BASE -> true-burst recall flattered (decoy-FP-vs-lookback curve is the result of interest). Re-planted corpus is a deliberately-constructed demonstration of the mechanism at a realistic daily-batch cadence, NOT a transferable rate.",
    }
    rdir = os.path.join(HERE, "results"); os.makedirs(rdir, exist_ok=True)
    json.dump(res, open(os.path.join(rdir, "scheduled_arm.json"), "w"), indent=2, sort_keys=True)
    print("\n  wrote results/scheduled_arm.json", flush=True)


if __name__ == "__main__":
    main()

"""Cross-tool assurance gap — the first-party measurement behind the four-layer
data-health framework (source -> flow -> quality -> cross-tool gap).

The productised "data quality / assurance" deliverable the SDW Capability Matrix
scores, and the thing the consulting actually sells, rests on one claim: *the
true state of a security estate lives in the cross-tool view, not in any single
tool*. No single source — CMDB, EDR, vulnerability scanner, identity provider —
holds the whole truth about an asset; each observes a partial, characteristically
flawed slice (a coverage gap, a staleness lag, an authority limit), and the
assurance that matters is what you recover when you merge them by freshness and
authority rather than by trusting one console. Until now that claim was a thesis
with no first-party benchmark. This is the benchmark.

The design is the two-store discipline the rest of the lab uses, generalised to
N sources. We plant the *true* state of ~20,000 assets (the ground truth, known
because we generated it). Each source tool then observes the estate through a
deterministic flaw model — it misses some assets entirely (coverage), it reports
some attributes from a stale snapshot (staleness), and on a few attributes it is
simply not authoritative (disagreement). We then measure, as exact set-based
accuracy over (entity, attribute) cells:

  1. SINGLE-TOOL recovery   — each tool alone: what fraction of true cells it
                              reports correctly (coverage x freshness x authority).
  2. CROSS-TOOL recovery    — a freshness/authority-ranked merge ("best source
                              per attribute"): show it materially exceeds the best
                              single tool.
  3. RESIDUAL gap           — (entity, attribute) cells NO tool reports correctly:
                              the real blind spot, the risk surface assurance is
                              meant to find.
  4. CONFIDENCE lever       — the same merge driven by a per-(entity, attribute,
                              source) confidence+freshness score is what produces
                              (2); a naive last-writer / single-authority merge
                              does not. The score is the lever, quantified.

This is a correctness / coverage benchmark, not a latency benchmark, so there are
no timings and the time_trials CV machinery does not apply. The numbers are exact
set cardinalities over planted ground truth; a re-run reproduces them bit for bit,
which run.py asserts before publishing.

    SDW_DUCK_MEMORY_LIMIT=12GB python3 run.py
"""

import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# The determinism core (one master seed, one fixed clock anchor, the scoring
# helpers) lives in the repo-level lib/, shared with every other benchmark.
sys.path.insert(0, os.path.join(HERE, "..", "lib"))

import duckdb  # noqa: E402

from common import new_rng, BASE_EPOCH, connect, prf1, canonical  # noqa: E402

RESULTS_DIR = os.path.join(HERE, "results")

# ---------------------------------------------------------------------------
# Corpus parameters. These are the knobs the headline magnitudes depend on; they
# are documented in METHODOLOGY.md as parameters, not universal constants. The
# ratio-independent finding is the ORDER: cross-tool > best single tool, and the
# residual gap is small but nonzero.
# ---------------------------------------------------------------------------
N_ASSETS = 20_000
SECONDS_PER_DAY = 86_400

# The five attributes whose true state we plant. Each maps to an authoritative
# source and a freshness profile, the way a real estate splits across consoles.
ATTRIBUTES = (
    "owner",                # who owns the asset (org/business attribute)
    "business_criticality",  # tier-1..tier-4 (org/business attribute)
    "os_version",           # the running OS build (endpoint-state attribute)
    "ip_address",           # current address (network-state attribute)
    "last_seen",            # last activity day-of-year (network-state attribute)
    "open_vuln_count",      # current open vulns (scan-state attribute)
    "is_managed",           # under endpoint management (endpoint-state attribute)
)

# Authority OF RECORD: the source an ops team names as the system of record for
# each attribute — what a naive "trust the inventory" merge would pick. This is
# the "authority" half of the lever. The CMDB is the named system of record for
# the asset's *inventory* attributes, including the volatile network state
# (ip_address, last_seen, os_version) — which is exactly the trap: the CMDB is
# authoritative-by-policy but STALE in fact on those volatile attributes, while a
# fresher operational source (EDR) holds the correct current value. The freshness
# half of the lever is what overrides the stale authority of record, so a merge
# that ranks by freshness-decayed confidence beats one that just trusts the CMDB.
AUTHORITY = {
    "owner": "cmdb",                 # CMDB authoritative AND fresh (slow-moving)
    "business_criticality": "cmdb",  # CMDB authoritative AND fresh (slow-moving)
    "is_managed": "cmdb",            # CMDB authoritative AND fresh (slow-moving)
    "os_version": "cmdb",            # CMDB = system of record, but STALE; EDR fresh
    "ip_address": "cmdb",            # CMDB = system of record, but STALE; EDR fresh
    "last_seen": "cmdb",             # CMDB = system of record, but STALE; EDR fresh
    "open_vuln_count": "vuln",       # only the scanner ever holds this
}

OS_VERSIONS = ("win10-19045", "win11-22631", "win11-23H2", "ubuntu-22.04",
               "ubuntu-24.04", "rhel-9.3", "macos-14.4", "ios-firmware-17.2")
CRITICALITY = ("tier-1", "tier-2", "tier-3", "tier-4")
ASSET_KINDS = ("workstation", "server", "network-gear", "shadow-cloud")


# ---------------------------------------------------------------------------
# Ground truth
# ---------------------------------------------------------------------------
def gen_ground_truth(seed: int):
    """The TRUE state of every asset, planted deterministically.

    Each asset has a kind, which governs which tools can even see it (network
    gear and shadow-cloud assets are not managed endpoints, so EDR is blind to
    them by construction — the coverage gap is a property of the estate, not of
    a coin flip per tool). Every attribute has a true value; the merge is scored
    against these.
    """
    rng = new_rng(seed)
    truth = []
    for i in range(N_ASSETS):
        # Estate composition: most assets are managed endpoints, a real minority
        # are network gear / shadow cloud that endpoint tooling never sees.
        r = rng.random()
        if r < 0.62:
            kind = "workstation"
        elif r < 0.80:
            kind = "server"
        elif r < 0.91:
            kind = "network-gear"
        else:
            kind = "shadow-cloud"

        is_managed = kind in ("workstation", "server")
        truth.append({
            "asset_id": i,
            "kind": kind,
            "owner": f"team-{rng.randint(0, 39)}",
            "business_criticality": rng.choice(CRITICALITY),
            "os_version": rng.choice(OS_VERSIONS),
            # true current address; 10.x for managed, 172.16.x for infra/shadow
            "ip_address": (f"10.{rng.randint(0,255)}.{rng.randint(0,255)}.{rng.randint(1,254)}"
                           if is_managed else
                           f"172.16.{rng.randint(0,255)}.{rng.randint(1,254)}"),
            "last_seen": rng.randint(150, 158),       # day-of-year, "now" ~ day 158
            "open_vuln_count": rng.randint(0, 47),
            "is_managed": is_managed,
        })
    return truth


def validate_corpus(truth):
    """Integrity check: the planted ground truth must be internally consistent
    before any tool observes it, or a 'gap' could be a corpus bug rather than a
    tool flaw. Returns a dict of assertions, all of which must hold.

    - exactly N_ASSETS, asset_ids are 0..N-1 with no gaps/dupes
    - every attribute present and in-domain on every asset
    - is_managed is fully determined by kind (the coverage invariant the EDR
      flaw model relies on)
    """
    ids = [a["asset_id"] for a in truth]
    checks = {
        "row_count_ok": len(truth) == N_ASSETS,
        "ids_contiguous_unique": sorted(ids) == list(range(N_ASSETS)),
        "all_attributes_present": all(
            all(attr in a for attr in ATTRIBUTES) for a in truth),
        "criticality_in_domain": all(a["business_criticality"] in CRITICALITY for a in truth),
        "os_in_domain": all(a["os_version"] in OS_VERSIONS for a in truth),
        "is_managed_determined_by_kind": all(
            a["is_managed"] == (a["kind"] in ("workstation", "server")) for a in truth),
        "last_seen_in_range": all(150 <= a["last_seen"] <= 158 for a in truth),
        "vuln_count_nonneg": all(a["open_vuln_count"] >= 0 for a in truth),
    }
    checks["all_passed"] = all(checks.values())
    return checks


# ---------------------------------------------------------------------------
# Source tools — each is a deterministic flaw model over the ground truth.
#
# An observation is a row (asset_id, source, attribute, value, observed_day,
# confidence). confidence is the source's self-reported trust in that reading,
# BEFORE freshness decay; the merge combines it with staleness to pick a winner.
# A tool that does not observe an asset (coverage gap) emits no rows for it. A
# tool that reports a stale value emits the value it last saw, with an old
# observed_day, so freshness decay can demote it.
#
# "now" is day 158 (BASE_EPOCH is the epoch anchor; we use day-of-year integers
# for legibility — no datetime.now, fully seeded).
# ---------------------------------------------------------------------------
NOW_DAY = 158


def gen_observations(truth, seed: int):
    """Build every source's observation rows under its characteristic flaw model.

    CMDB  — authoritative on owner/business_criticality (high confidence, fresh
            there), but its network state (ip_address, last_seen) is STALE: it
            reports an out-of-date address from its last reconciliation and an old
            last_seen. It also MISSES shadow-cloud assets entirely (never
            onboarded) — the classic "CMDB doesn't know about the thing".
    EDR   — FRESH on os_version/ip_address/last_seen/is_managed for the endpoints
            it covers, but it covers ONLY managed endpoints: network-gear and
            shadow-cloud assets are invisible to it (no agent). High confidence
            where present.
    VULN  — open_vuln_count, but PARTIAL coverage (a scan window misses a
            fraction of assets each cycle) and scan-cadence STALENESS: the count
            it holds is from the last scan, which for some assets is days old and
            no longer matches the true current count.
    IDP   — identity attributes; here it re-asserts owner for the assets tied to
            an identity, FRESHER than CMDB for the subset it knows, which lets it
            win owner on those by freshness even though CMDB is the named
            authority. Demonstrates the freshness half of the lever overriding
            the authority half.
    """
    rng = new_rng(seed)
    obs = []  # (asset_id, source, attribute, value, observed_day, confidence)

    def emit(aid, src, attr, val, day, conf):
        obs.append((aid, src, attr, str(val), int(day), float(conf)))

    for a in truth:
        aid = a["asset_id"]
        kind = a["kind"]
        managed = a["is_managed"]

        # ---- CMDB (system of record) ------------------------------------------
        # Misses shadow-cloud (never onboarded). Authoritative AND fresh on the
        # slow-moving organisational attributes (owner, criticality, is_managed).
        # It is also the NAMED system of record for the volatile inventory
        # attributes (os_version, ip_address, last_seen) — but its values there
        # are STALE, from its last reconciliation weeks ago, so they are usually
        # wrong now. That is the trap the freshness lever has to beat: the
        # authority of record is confidently out of date.
        if kind != "shadow-cloud":
            emit(aid, "cmdb", "owner", a["owner"], NOW_DAY - rng.randint(0, 2), 0.95)
            emit(aid, "cmdb", "business_criticality", a["business_criticality"],
                 NOW_DAY - rng.randint(0, 2), 0.95)
            emit(aid, "cmdb", "is_managed", a["is_managed"], NOW_DAY - rng.randint(0, 5), 0.90)
            # STALE os_version: the build recorded at onboarding/last reconcile;
            # ~75% have since been patched/upgraded away from it.
            cmdb_os = a["os_version"] if rng.random() < 0.25 else rng.choice(OS_VERSIONS)
            emit(aid, "cmdb", "os_version", cmdb_os, NOW_DAY - rng.randint(21, 75), 0.65)
            # STALE ip: an OLD address from the last reconciliation; ~70% drifted.
            stale_ip = f"10.{rng.randint(0,255)}.{rng.randint(0,255)}.{rng.randint(1,254)}"
            cmdb_ip = a["ip_address"] if rng.random() < 0.30 else stale_ip
            emit(aid, "cmdb", "ip_address", cmdb_ip, NOW_DAY - rng.randint(14, 60), 0.65)
            # STALE last_seen: days behind the true value.
            cmdb_last_seen = a["last_seen"] - rng.randint(10, 40)
            emit(aid, "cmdb", "last_seen", cmdb_last_seen, NOW_DAY - rng.randint(14, 60), 0.65)

        # ---- EDR --------------------------------------------------------------
        # Only managed endpoints. Fresh and high-confidence where present.
        if managed:
            # A small fraction of managed endpoints have a dormant/uninstalled
            # agent and report nothing this cycle (coverage staleness within EDR).
            if rng.random() < 0.93:
                emit(aid, "edr", "os_version", a["os_version"], NOW_DAY - rng.randint(0, 1), 0.92)
                emit(aid, "edr", "ip_address", a["ip_address"], NOW_DAY, 0.90)
                emit(aid, "edr", "last_seen", a["last_seen"], NOW_DAY, 0.90)
                emit(aid, "edr", "is_managed", a["is_managed"], NOW_DAY, 0.95)

        # ---- VULN scanner -----------------------------------------------------
        # Partial coverage + scan-cadence staleness. ~78% of assets are in the
        # last scan window; of those, the count is current only if scanned
        # recently, otherwise it is the stale prior-scan count (drifted).
        if rng.random() < 0.78:
            days_since_scan = rng.randint(0, 35)
            if days_since_scan <= 7:
                vuln_val = a["open_vuln_count"]                 # current
                conf = 0.88
            else:
                # stale: the prior scan's number, which has since drifted
                drift = rng.randint(-9, 9)
                vuln_val = max(0, a["open_vuln_count"] + drift)
                conf = 0.55
            emit(aid, "vuln", "open_vuln_count", vuln_val, NOW_DAY - days_since_scan, conf)

        # ---- IDP --------------------------------------------------------------
        # Knows owner for identity-bound assets (workstations mostly), FRESHER
        # than CMDB for that subset. High confidence, today. This is the case
        # where freshness should override the named authority (CMDB) on owner.
        if kind == "workstation" and rng.random() < 0.55:
            emit(aid, "idp", "owner", a["owner"], NOW_DAY, 0.80)

    return obs


# ---------------------------------------------------------------------------
# Scoring — exact set-based accuracy over (entity, attribute) cells, in DuckDB.
# ---------------------------------------------------------------------------
def _truth_long(truth):
    """Ground truth as long rows (asset_id, attribute, true_value-as-string)."""
    rows = []
    for a in truth:
        for attr in ATTRIBUTES:
            rows.append((a["asset_id"], attr, str(a[attr])))
    return rows


def score(truth, obs):
    """Returns the four measures plus the per-tool and per-attribute breakdowns.

    correctness is exact: a (asset_id, attribute) cell counts as RECOVERED only
    if the chosen value string equals the planted true value string. No fuzzy
    matching, no timing. The denominator is N_ASSETS * len(ATTRIBUTES) — every
    cell the estate truly has.
    """
    con = connect()
    # Bulk-load via Arrow tables (register + CREATE TABLE AS). Row-by-row
    # executemany on ~190k rows is the slow path and dominated runtime; an
    # Arrow column scan is near-instant and changes no result — the rows are
    # identical, only the load mechanism differs, so it stays determinism-safe.
    import pyarrow as pa
    tl = _truth_long(truth)
    truth_tbl = pa.table({
        "asset_id": pa.array([r[0] for r in tl], pa.int32()),
        "attribute": pa.array([r[1] for r in tl]),
        "true_value": pa.array([r[2] for r in tl]),
    })
    obs_tbl = pa.table({
        "asset_id": pa.array([r[0] for r in obs], pa.int32()),
        "source": pa.array([r[1] for r in obs]),
        "attribute": pa.array([r[2] for r in obs]),
        "value": pa.array([r[3] for r in obs]),
        "observed_day": pa.array([r[4] for r in obs], pa.int32()),
        "confidence": pa.array([r[5] for r in obs], pa.float64()),
    })
    con.register("truth_arrow", truth_tbl)
    con.register("obs_arrow", obs_tbl)
    con.execute("CREATE TABLE truth AS SELECT * FROM truth_arrow")
    con.execute("CREATE TABLE obs AS SELECT * FROM obs_arrow")

    total_cells = N_ASSETS * len(ATTRIBUTES)
    sources = ("cmdb", "edr", "vuln", "idp")

    # --- (1) per-tool single-tool recovery -------------------------------------
    # A tool's reading of a cell is "correct" iff it reported that cell AND the
    # value matches truth. (Staleness shows up here as a reported-but-wrong cell.)
    per_tool = {}
    for s in sources:
        # reported_cells = cells the tool actually observed (inner join), so
        # accuracy_where_reported isolates staleness/authority error from pure
        # coverage absence; recovery uses the full estate as denominator.
        row = con.execute("""
            SELECT
              COUNT(*) FILTER (WHERE o.value = t.true_value)  AS correct_cells,
              COUNT(*)                                        AS reported_cells
            FROM truth t
            JOIN obs o
              ON o.asset_id = t.asset_id AND o.attribute = t.attribute AND o.source = ?
        """, [s]).fetchone()
        correct, reported = int(row[0]), int(row[1])
        per_tool[s] = {
            "correct_cells": correct,
            "reported_cells": reported,
            # recovery = correct cells / ALL true cells (coverage x accuracy)
            "recovery": round(correct / total_cells, 4),
            # accuracy among the cells the tool DID report (isolates staleness/
            # authority error from pure coverage absence)
            "accuracy_where_reported": round(correct / reported, 4) if reported else 0.0,
        }
    best_single = max(per_tool, key=lambda s: per_tool[s]["recovery"])
    best_single_recovery = per_tool[best_single]["recovery"]

    # --- (4) the confidence+freshness score IS the lever -----------------------
    # effective_score = confidence * freshness_decay(observed_day) and, for the
    # tie/near-tie band, an authority bonus so the named authority wins when
    # equally fresh. Freshness decay is exponential with a 14-day half-life:
    # a value 14 days old counts half as much, which is what lets a fresh IDP
    # owner beat a slightly-less-fresh CMDB owner, and lets a fresh EDR ip beat a
    # stale CMDB ip. This is computed in SQL so the selection is reproducible.
    con.execute("""
        CREATE TABLE scored AS
        SELECT *,
          confidence
            * pow(0.5, (CAST(? AS DOUBLE) - observed_day) / 14.0)   AS freshness_score,
          confidence
            * pow(0.5, (CAST(? AS DOUBLE) - observed_day) / 14.0)
            + CASE WHEN source = CASE attribute
                """ + "\n".join(
                    f"WHEN '{a}' THEN '{src}'" for a, src in AUTHORITY.items()
                ) + """ END
                   THEN 0.05 ELSE 0 END                              AS effective_score
        FROM obs
    """, [NOW_DAY, NOW_DAY])

    # --- (2) cross-tool best-context merge -------------------------------------
    # For each (asset, attribute) pick the observation with the highest
    # effective_score (freshness-decayed confidence + authority bonus). Ties
    # broken deterministically by source name so the result is reproducible.
    con.execute("""
        CREATE TABLE best_context AS
        SELECT asset_id, attribute, value AS chosen_value, source AS chosen_source
        FROM (
          SELECT *, row_number() OVER (
                     PARTITION BY asset_id, attribute
                     ORDER BY effective_score DESC, source ASC) AS rn
          FROM scored
        ) WHERE rn = 1
    """)
    cross_correct = int(con.execute("""
        SELECT COUNT(*)
        FROM truth t JOIN best_context b
          ON b.asset_id = t.asset_id AND b.attribute = t.attribute
        WHERE b.chosen_value = t.true_value
    """).fetchone()[0])
    cross_recovery = round(cross_correct / total_cells, 4)

    # --- (4b) naive baseline merge — single fixed authority, no freshness ------
    # The counterfactual that shows the score is the lever: always take the named
    # authority's value if present, else any source's, with NO freshness ranking.
    # If this ~= cross_recovery, the score added nothing.
    con.execute("""
        CREATE TABLE naive_merge AS
        WITH authority_pick AS (
          SELECT s.asset_id, s.attribute, s.value AS chosen_value
          FROM scored s
          WHERE s.source = CASE s.attribute
            """ + "\n".join(f"WHEN '{a}' THEN '{src}'" for a, src in AUTHORITY.items()) + """ END
        ),
        any_pick AS (
          SELECT asset_id, attribute, value AS chosen_value
          FROM (SELECT *, row_number() OVER (
                  PARTITION BY asset_id, attribute ORDER BY source ASC) rn
                FROM scored) WHERE rn = 1
        )
        SELECT t.asset_id, t.attribute,
               COALESCE(a.chosen_value, p.chosen_value) AS chosen_value
        FROM truth t
        LEFT JOIN authority_pick a ON a.asset_id=t.asset_id AND a.attribute=t.attribute
        LEFT JOIN any_pick      p ON p.asset_id=t.asset_id AND p.attribute=t.attribute
    """)
    naive_correct = int(con.execute("""
        SELECT COUNT(*) FROM truth t JOIN naive_merge n
          ON n.asset_id=t.asset_id AND n.attribute=t.attribute
        WHERE n.chosen_value = t.true_value
    """).fetchone()[0])
    naive_recovery = round(naive_correct / total_cells, 4)

    # --- (3) residual assurance gap --------------------------------------------
    # Cells where NO source reported the correct value — invisible to every tool,
    # and therefore to any merge however clever. This is the true blind spot.
    any_correct = int(con.execute("""
        SELECT COUNT(*) FROM (
          SELECT DISTINCT t.asset_id, t.attribute
          FROM truth t JOIN obs o
            ON o.asset_id=t.asset_id AND o.attribute=t.attribute
          WHERE o.value = t.true_value
        )
    """).fetchone()[0])
    residual_cells = total_cells - any_correct
    residual_gap = round(residual_cells / total_cells, 4)

    # Ceiling check: the best-context merge can never beat "some tool got it
    # right somewhere" (any_correct). Recorded so the gap math is auditable.
    cross_ceiling = round(any_correct / total_cells, 4)

    # --- per-attribute cross-tool recovery (where the lever helps most) --------
    per_attr = {}
    for attr in ATTRIBUTES:
        bc = int(con.execute("""
            SELECT COUNT(*) FROM truth t JOIN best_context b
              ON b.asset_id=t.asset_id AND b.attribute=t.attribute
            WHERE b.attribute=? AND b.chosen_value=t.true_value
        """, [attr]).fetchone()[0])
        # best single tool FOR THIS ATTRIBUTE:
        bs_attr = 0
        bs_src = None
        for s in sources:
            c = int(con.execute("""
                SELECT COUNT(*) FROM truth t LEFT JOIN obs o
                  ON o.asset_id=t.asset_id AND o.attribute=t.attribute AND o.source=?
                WHERE t.attribute=? AND o.value=t.true_value
            """, [s, attr]).fetchone()[0])
            if c > bs_attr:
                bs_attr, bs_src = c, s
        # residual for this attribute
        anyc = int(con.execute("""
            SELECT COUNT(*) FROM (
              SELECT DISTINCT t.asset_id FROM truth t JOIN obs o
                ON o.asset_id=t.asset_id AND o.attribute=t.attribute
              WHERE t.attribute=? AND o.value=t.true_value)
        """, [attr]).fetchone()[0])
        per_attr[attr] = {
            "authority_source": AUTHORITY[attr],
            "best_single_tool": bs_src,
            "best_single_correct": bs_attr,
            "best_single_recovery": round(bs_attr / N_ASSETS, 4),
            "cross_tool_correct": bc,
            "cross_tool_recovery": round(bc / N_ASSETS, 4),
            "cross_minus_best_single": round((bc - bs_attr) / N_ASSETS, 4),
            "residual_gap": round((N_ASSETS - anyc) / N_ASSETS, 4),
        }
    con.close()

    return {
        "total_cells": total_cells,
        "n_assets": N_ASSETS,
        "attributes": list(ATTRIBUTES),
        "sources": list(sources),
        # measure 1
        "per_tool_single_recovery": per_tool,
        "best_single_tool": best_single,
        "best_single_recovery": best_single_recovery,
        # measure 2
        "cross_tool_recovery": cross_recovery,
        "cross_tool_correct_cells": cross_correct,
        "cross_minus_best_single": round(cross_recovery - best_single_recovery, 4),
        # measure 3
        "residual_gap": residual_gap,
        "residual_cells": residual_cells,
        "cross_tool_ceiling": cross_ceiling,   # any-tool-correct upper bound
        # measure 4
        "lever": {
            "scored_merge_recovery": cross_recovery,
            "naive_authority_merge_recovery": naive_recovery,
            "lever_gain": round(cross_recovery - naive_recovery, 4),
            "note": ("scored = freshness-decayed confidence + authority bonus; "
                     "naive = fixed authority, no freshness. The gap is the lever."),
        },
        "per_attribute": per_attr,
    }


def run():
    truth = gen_ground_truth(seed=701)
    integrity = validate_corpus(truth)
    obs = gen_observations(truth, seed=702)
    scored = score(truth, obs)
    return {
        "benchmark": "ocsf-data-health: cross-tool assurance gap",
        "evidence_tier": ("B (reproducible, first-party, controlled synthetic "
                          "estate; exact set-based accuracy over planted ground "
                          "truth; NOT production telemetry)"),
        "n_observations": len(obs),
        "corpus_integrity": integrity,
        "measures": scored,
    }


# ---------------------------------------------------------------------------
# Determinism + outputs
# ---------------------------------------------------------------------------
def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)

    first = run()
    second = run()
    deterministic = canonical(first) == canonical(second)
    if not deterministic:
        raise SystemExit("DETERMINISM FAILED: two in-process runs differ — refusing to publish.")
    if not first["corpus_integrity"]["all_passed"]:
        raise SystemExit("CORPUS INTEGRITY FAILED: planted ground truth is inconsistent.")

    results = {
        **first,
        "environment": {
            "duckdb_version": duckdb.__version__,
            "master_seed": 20260601,
        },
        "determinism_verified": deterministic,
    }

    with open(os.path.join(RESULTS_DIR, "results.json"), "w") as f:
        json.dump(results, f, indent=2, sort_keys=True)
    _write_markdown(results)

    digest = hashlib.sha256(canonical(first).encode()).hexdigest()[:16]
    m = first["measures"]
    print(f"determinism_verified={deterministic}  corpus_integrity={first['corpus_integrity']['all_passed']}  "
          f"duckdb={duckdb.__version__}  results_sha256[:16]={digest}")
    print(f"best single tool ({m['best_single_tool']}): {m['best_single_recovery']:.1%}  |  "
          f"cross-tool: {m['cross_tool_recovery']:.1%}  (+{m['cross_minus_best_single']:.1%})  |  "
          f"residual gap: {m['residual_gap']:.1%}  |  lever gain: {m['lever']['lever_gain']:.1%}")
    print(f"wrote {os.path.join(RESULTS_DIR, 'results.json')}")
    print(f"wrote {os.path.join(RESULTS_DIR, 'RESULTS.md')}")


def _write_markdown(results):
    m = results["measures"]
    pt = m["per_tool_single_recovery"]
    lines = []
    a = lines.append

    a("# Results — cross-tool assurance gap (ocsf-data-health)\n")
    a(f"- DuckDB: `{results['environment']['duckdb_version']}`  ")
    a(f"- Master seed: `{results['environment']['master_seed']}`  ")
    a(f"- Determinism (two in-process runs byte-identical): **{results['determinism_verified']}**  ")
    a(f"- Corpus integrity (planted truth internally consistent): **{results['corpus_integrity']['all_passed']}**  ")
    a(f"- Evidence tier: {results['evidence_tier']}\n")
    a(f"Synthetic estate of **{m['n_assets']:,} assets x {len(m['attributes'])} attributes "
      f"= {m['total_cells']:,} ground-truth cells**, observed through "
      f"{len(m['sources'])} source tools ({m['n_observations'] if False else results['n_observations']:,} "
      f"observation rows). All numbers are exact set cardinalities over planted ground truth — this is a "
      f"correctness/coverage benchmark, not a latency one, so there are no timings and no CV.\n")

    # Headline
    a("## Headline — the four measures\n")
    a("| measure | value |")
    a("|---|--:|")
    a(f"| **(1)** best *single* tool recovery (`{m['best_single_tool']}`) | **{m['best_single_recovery']:.1%}** |")
    a(f"| **(2)** *cross-tool* best-context recovery | **{m['cross_tool_recovery']:.1%}** |")
    a(f"|     — cross-tool minus best single tool | **+{m['cross_minus_best_single']:.1%}** |")
    a(f"| **(3)** residual assurance gap (no tool correct) | **{m['residual_gap']:.1%}** |")
    a(f"| **(4)** lever gain (scored merge − naive authority merge) | **+{m['lever']['lever_gain']:.1%}** |\n")
    a(f"The cross-tool merge recovers **{m['cross_tool_recovery']:.1%}** of the estate's true state against the "
      f"best single tool's **{m['best_single_recovery']:.1%}** — a **+{m['cross_minus_best_single']:.1%}** lift, "
      f"the central thesis claim made measurable: *assurance lives in the cross-tool view*. The residual "
      f"**{m['residual_gap']:.1%}** is the blind spot no tool covers correctly — the actual risk surface — and the "
      f"merge tops out at its ceiling of {m['cross_tool_ceiling']:.1%} (any-tool-correct), which equals "
      f"100% − residual by construction.\n")

    # Measure 1 detail
    a("## (1) Single-tool recovery — each tool's partial, flawed view\n")
    a("Recovery = correct cells / all true cells (coverage x freshness x authority). "
      "Accuracy-where-reported isolates staleness/authority error from pure absence.\n")
    a("| tool | correct cells | reported cells | recovery | accuracy where reported |")
    a("|---|--:|--:|--:|--:|")
    for s in m["sources"]:
        v = pt[s]
        a(f"| {s} | {v['correct_cells']:,} | {v['reported_cells']:,} | "
          f"{v['recovery']:.1%} | {v['accuracy_where_reported']:.1%} |")
    a("\nNo single tool clears half the estate's true state: each is authoritative on its own attributes and "
      "blind or stale elsewhere. CMDB knows owners but its network state is weeks stale; EDR is fresh but sees "
      "only managed endpoints; the scanner is partial and scan-cadence stale.\n")

    # Measure 2/4 — per attribute
    a("## (2)+(4) Where the cross-tool merge wins — per attribute\n")
    a("The merge picks, per (asset, attribute), the observation with the highest "
      "**freshness-decayed confidence + authority bonus** (14-day half-life). That score is the lever: a "
      "naive fixed-authority merge with no freshness scores **{:.1%}** overall, the scored merge **{:.1%}** "
      "(**+{:.1%}**).\n".format(m['lever']['naive_authority_merge_recovery'],
                                 m['lever']['scored_merge_recovery'], m['lever']['lever_gain']))
    a("| attribute | authority | best single tool | best-single recovery | cross-tool recovery | cross − best | residual gap |")
    a("|---|---|---|--:|--:|--:|--:|")
    for attr in m["attributes"]:
        v = m["per_attribute"][attr]
        a(f"| {attr} | {v['authority_source']} | {v['best_single_tool']} | "
          f"{v['best_single_recovery']:.1%} | {v['cross_tool_recovery']:.1%} | "
          f"+{v['cross_minus_best_single']:.1%} | {v['residual_gap']:.1%} |")
    a("\nTwo different effects show up in this table, and they are worth keeping apart. The **cross − best-single** "
      "column is the lift from *combining* tools: it is positive on `os_version` and `ip_address`, where EDR "
      "covers managed endpoints the stale CMDB gets wrong AND CMDB covers the unmanaged assets EDR can't see, so "
      "the union beats either alone. The bigger story is the **lever** (the overall +{:.1%} of the scored merge "
      "over the naive authority merge above): on `os_version`, `ip_address`, and `last_seen` the named authority "
      "of record is the CMDB, but the CMDB is stale there, so a merge that just trusts the system of record picks "
      "the wrong value while the freshness-decayed score picks fresh EDR — that is why the naive merge lands at "
      "{:.1%} and the scored merge at {:.1%}. On `last_seen`, cross-tool equals best-single (EDR) because nothing "
      "else holds a fresh last_seen, yet the scored merge still beats the naive one by demoting CMDB's stale "
      "reading. On attributes only one tool ever holds (`open_vuln_count`), cross-tool = best single and the "
      "gain is residual coverage, not a merge effect — which is honest: the merge cannot invent coverage no tool "
      "has.\n".format(m['lever']['lever_gain'],
                       m['lever']['naive_authority_merge_recovery'],
                       m['lever']['scored_merge_recovery']))

    # Measure 3
    a("## (3) Residual assurance gap — the real blind spot\n")
    a(f"**{m['residual_cells']:,} of {m['total_cells']:,} cells ({m['residual_gap']:.1%})** are reported "
      f"correctly by *no* tool. That is the surface the four-layer data-health review exists to surface: an "
      f"asset whose true state nothing in the stack actually holds — a shadow-cloud host no console onboarded, "
      f"a network device EDR can't see and CMDB last touched weeks ago, a vuln count no recent scan covered. "
      f"No merge recovers it; only adding a source that *covers* it can. Quantifying this gap is the deliverable "
      f"the assurance engagement sells.\n")

    a("## Honesty boundary\n")
    a("Tier B: reproducible, first-party, single-host, **synthetic**. The flaw models (CMDB staleness window, "
      "EDR coverage of managed-only, scanner cadence, IDP owner overlap) are corpus *parameters*, not universal "
      "constants; the magnitudes move if you move them. The transferable, parameter-independent finding is the "
      "**order**: cross-tool recovery > best single tool, the residual gap is small but nonzero, and the "
      "freshness/confidence score is what produces the lift over a naive authority merge. See `METHODOLOGY.md` "
      "for the flaw models and the falsification condition.\n")

    with open(os.path.join(RESULTS_DIR, "RESULTS.md"), "w") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()

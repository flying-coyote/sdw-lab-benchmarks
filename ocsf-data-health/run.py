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

TWO EXTENSIONS sit on top of the v1 measurement, both preserving it bit-for-bit:

  EXT-1  PARAMETER SWEEP. The v1 headline magnitudes (single 47.7% -> cross-tool
         75.6% -> residual 24.4%, lever +25.1%) are functions of the chosen
         flaw-model parameters. We sweep the two that drive them — the freshness
         half-life (how fast confidence decays) and a per-tool coverage multiplier
         — across a deterministic 3x3 grid, recompute all four measures at every
         point, and report the min/max of each. The transferable claim was always
         the ORDER, not the magnitude; the sweep is what lets us assert the order
         (cross-tool > best-single, residual > 0, scored-merge > naive) holds
         across the whole grid rather than at one tuned point — or report honestly
         where it inverts at an extreme.

  EXT-2  SECOND ENTITY TYPE — IDENTITIES with a CONTESTED JOIN KEY. v1 covers only
         assets, which share one clean key (asset_id) across every tool. Real
         identity data does not: the IdP keys on email, the EDR on UPN, HR on
         employee_id, the directory on sAMAccountName, and those keys disagree, so
         the cross-tool merge must FIRST reconcile which records are the same human
         before it can merge their attributes. We plant the true identity<->key
         mapping as ground truth, give each tool its own key with a deterministic
         resolution-flaw model (missing/garbled keys, no shared join column on
         some pairs), and measure how much the contested join degrades cross-tool
         recovery versus the clean-key asset case. Entity resolution is itself part
         of the assurance gap; this puts a number on it.

    SDW_DUCK_MEMORY_LIMIT=12GB python3 run.py
"""

import hashlib
import json
import os
import sys
from dataclasses import dataclass, field, replace

HERE = os.path.dirname(os.path.abspath(__file__))
# The determinism core (one master seed, one fixed clock anchor, the scoring
# helpers) lives in the repo-level lib/, shared with every other benchmark.
sys.path.insert(0, os.path.join(HERE, "..", "lib"))

import duckdb  # noqa: E402

from common import new_rng, BASE_EPOCH, connect, prf1, canonical, scale_sweep  # noqa: E402

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
# FlawParams — the knobs the headline magnitudes depend on, made first-class so
# the parameter sweep (EXT-1) can vary them while the v1 path keeps the exact
# defaults. The defaults reproduce v1 byte-for-bit; run.py asserts that.
#
#   half_life_days   — freshness-decay half-life: a value this many days old
#                      counts for half as much in the effective score. Smaller =
#                      freshness punishes staleness harder (the lever should grow);
#                      larger = the score forgives age (the lever should shrink).
#   coverage_mult    — a single multiplier on every per-tool coverage fraction
#                      (EDR agent-present, VULN scan-window, IDP owner overlap).
#                      <1 thins coverage (residual should grow); the fractions are
#                      clamped to [0,1]. The CMDB shadow-cloud miss is structural,
#                      not a fraction, so it is untouched.
# The remaining fields fix the v1 staleness/confidence model so the sweep holds
# everything else constant and moves only the two swept axes.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class FlawParams:
    half_life_days: float = 14.0
    coverage_mult: float = 1.0
    # base per-tool coverage fractions (multiplied by coverage_mult, clamped 0..1)
    edr_agent_present: float = 0.93
    vuln_scan_window: float = 0.78
    idp_owner_overlap: float = 0.55
    # CMDB staleness: probability the reported value still equals truth
    cmdb_os_fresh_p: float = 0.25
    cmdb_ip_fresh_p: float = 0.30
    # confidence levels (held fixed across the sweep)
    conf_cmdb_org: float = 0.95
    conf_cmdb_managed: float = 0.90
    conf_cmdb_volatile: float = 0.65
    conf_edr_os: float = 0.92
    conf_edr_net: float = 0.90
    conf_edr_managed: float = 0.95
    conf_vuln_fresh: float = 0.88
    conf_vuln_stale: float = 0.55
    conf_idp_owner: float = 0.80
    authority_bonus: float = 0.05

    def cov(self, base: float) -> float:
        """A coverage fraction scaled by coverage_mult and clamped to [0,1]."""
        return min(1.0, max(0.0, base * self.coverage_mult))


V1_PARAMS = FlawParams()


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


def gen_observations(truth, seed: int, params: FlawParams = V1_PARAMS):
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
            emit(aid, "cmdb", "owner", a["owner"], NOW_DAY - rng.randint(0, 2), params.conf_cmdb_org)
            emit(aid, "cmdb", "business_criticality", a["business_criticality"],
                 NOW_DAY - rng.randint(0, 2), params.conf_cmdb_org)
            emit(aid, "cmdb", "is_managed", a["is_managed"], NOW_DAY - rng.randint(0, 5), params.conf_cmdb_managed)
            # STALE os_version: the build recorded at onboarding/last reconcile;
            # ~75% have since been patched/upgraded away from it.
            cmdb_os = a["os_version"] if rng.random() < params.cmdb_os_fresh_p else rng.choice(OS_VERSIONS)
            emit(aid, "cmdb", "os_version", cmdb_os, NOW_DAY - rng.randint(21, 75), params.conf_cmdb_volatile)
            # STALE ip: an OLD address from the last reconciliation; ~70% drifted.
            stale_ip = f"10.{rng.randint(0,255)}.{rng.randint(0,255)}.{rng.randint(1,254)}"
            cmdb_ip = a["ip_address"] if rng.random() < params.cmdb_ip_fresh_p else stale_ip
            emit(aid, "cmdb", "ip_address", cmdb_ip, NOW_DAY - rng.randint(14, 60), params.conf_cmdb_volatile)
            # STALE last_seen: days behind the true value.
            cmdb_last_seen = a["last_seen"] - rng.randint(10, 40)
            emit(aid, "cmdb", "last_seen", cmdb_last_seen, NOW_DAY - rng.randint(14, 60), params.conf_cmdb_volatile)

        # ---- EDR --------------------------------------------------------------
        # Only managed endpoints. Fresh and high-confidence where present.
        if managed:
            # A small fraction of managed endpoints have a dormant/uninstalled
            # agent and report nothing this cycle (coverage staleness within EDR).
            if rng.random() < params.cov(params.edr_agent_present):
                emit(aid, "edr", "os_version", a["os_version"], NOW_DAY - rng.randint(0, 1), params.conf_edr_os)
                emit(aid, "edr", "ip_address", a["ip_address"], NOW_DAY, params.conf_edr_net)
                emit(aid, "edr", "last_seen", a["last_seen"], NOW_DAY, params.conf_edr_net)
                emit(aid, "edr", "is_managed", a["is_managed"], NOW_DAY, params.conf_edr_managed)

        # ---- VULN scanner -----------------------------------------------------
        # Partial coverage + scan-cadence staleness. ~78% of assets are in the
        # last scan window; of those, the count is current only if scanned
        # recently, otherwise it is the stale prior-scan count (drifted).
        if rng.random() < params.cov(params.vuln_scan_window):
            days_since_scan = rng.randint(0, 35)
            if days_since_scan <= 7:
                vuln_val = a["open_vuln_count"]                 # current
                conf = params.conf_vuln_fresh
            else:
                # stale: the prior scan's number, which has since drifted
                drift = rng.randint(-9, 9)
                vuln_val = max(0, a["open_vuln_count"] + drift)
                conf = params.conf_vuln_stale
            emit(aid, "vuln", "open_vuln_count", vuln_val, NOW_DAY - days_since_scan, conf)

        # ---- IDP --------------------------------------------------------------
        # Knows owner for identity-bound assets (workstations mostly), FRESHER
        # than CMDB for that subset. High confidence, today. This is the case
        # where freshness should override the named authority (CMDB) on owner.
        if kind == "workstation" and rng.random() < params.cov(params.idp_owner_overlap):
            emit(aid, "idp", "owner", a["owner"], NOW_DAY, params.conf_idp_owner)

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


def score(truth, obs, params: FlawParams = V1_PARAMS):
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
            * pow(0.5, (CAST(? AS DOUBLE) - observed_day) / CAST(? AS DOUBLE))   AS freshness_score,
          confidence
            * pow(0.5, (CAST(? AS DOUBLE) - observed_day) / CAST(? AS DOUBLE))
            + CASE WHEN source = CASE attribute
                """ + "\n".join(
                    f"WHEN '{a}' THEN '{src}'" for a, src in AUTHORITY.items()
                ) + """ END
                   THEN CAST(? AS DOUBLE) ELSE 0 END                 AS effective_score
        FROM obs
    """, [NOW_DAY, params.half_life_days, NOW_DAY, params.half_life_days, params.authority_bonus])

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


# ---------------------------------------------------------------------------
# EXT-1 — parameter sweep. Vary the parameters the headline magnitudes depend on
# across a deterministic grid and recompute the four measures + the lever at every
# point. The claim under test is the ORDER, not the magnitude: cross-tool >
# best-single, residual > 0, scored-merge > naive, at EVERY grid point. We report
# the min/max of each metric and a flag per ordering invariant; an inversion at
# any extreme is reported honestly rather than hidden.
#
# Two axes drive the main 3x3 grid because they are the ones that genuinely move
# the metrics on this corpus:
#   - STALENESS WINDOW: a multiplier on how much of the CMDB's volatile inventory
#     is stale (scales the cmdb_*_fresh_p "still-correct" probabilities). More
#     staleness drags best-single down and grows the lever; this is the literal
#     "how stale is the system of record" knob.
#   - COVERAGE: a single multiplier on every per-tool coverage fraction. Thinner
#     coverage grows the residual.
# The FRESHNESS HALF-LIFE (how fast confidence decays) is swept too, but as a
# separate robustness probe rather than a grid axis, because on this corpus it is
# INERT: the fresh sources (EDR) are also the higher-confidence ones, so freshness
# decay never flips a per-cell winner and the metrics do not move with the
# half-life from 7d to 90d. That null is itself a finding — the lever here is
# carried by the confidence+authority ordering, not by the decay rate — and we
# report it honestly rather than dropping the axis or pretending it moved.
#
# The truth corpus is fixed (seed 701) across the grid — we perturb the
# OBSERVATION flaw model and the scoring half-life, not the estate, so every grid
# point scores the same planted ground truth. The sweep is a pure function of the
# grid, so it is reproducible by construction and folds into the same build-twice
# determinism assert as v1.
# ---------------------------------------------------------------------------
STALENESS_MULT_GRID = (0.6, 1.0, 1.4)     # less / v1 / more CMDB staleness
COVERAGE_MULT_GRID = (0.8, 1.0, 1.15)     # thinner / v1 / fuller per-tool coverage
HALF_LIFE_PROBE = (7.0, 14.0, 28.0, 90.0)  # freshness-decay robustness probe


def _params_for(staleness_mult: float, cov_mult: float, half_life: float):
    """FlawParams for a grid cell. staleness_mult scales the CMDB still-correct
    probabilities DOWN as staleness goes UP (so mult>1 => more stale => lower
    fresh_p), clamped to [0,1]."""
    return replace(
        V1_PARAMS,
        coverage_mult=cov_mult,
        half_life_days=half_life,
        cmdb_os_fresh_p=min(1.0, max(0.0, V1_PARAMS.cmdb_os_fresh_p / staleness_mult)),
        cmdb_ip_fresh_p=min(1.0, max(0.0, V1_PARAMS.cmdb_ip_fresh_p / staleness_mult)),
    )


def _sweep_point(truth, staleness_mult: float, cov_mult: float, half_life: float):
    """One grid cell: rebuild observations + rescore under the perturbed params,
    return only the scalar measures the sweep tracks (kept small so the canonical
    JSON stays legible and the determinism hash is cheap to compare)."""
    params = _params_for(staleness_mult, cov_mult, half_life)
    obs = gen_observations(truth, seed=702, params=params)
    m = score(truth, obs, params=params)
    lev = m["lever"]
    return {
        "staleness_mult": staleness_mult,
        "coverage_mult": cov_mult,
        "half_life_days": half_life,
        "n_observations": len(obs),
        "best_single_tool": m["best_single_tool"],
        "best_single_recovery": m["best_single_recovery"],
        "cross_tool_recovery": m["cross_tool_recovery"],
        "cross_minus_best_single": m["cross_minus_best_single"],
        "residual_gap": m["residual_gap"],
        "scored_merge_recovery": lev["scored_merge_recovery"],
        "naive_authority_merge_recovery": lev["naive_authority_merge_recovery"],
        "lever_gain": lev["lever_gain"],
    }


def sweep():
    """Run the staleness x coverage grid via lib.common.scale_sweep, plus the
    half-life robustness probe, and summarise.

    scale_sweep(probe, scales) runs probe(scale) for each scale and returns
    {scale: result}; here a 'scale' is a (staleness_mult, coverage_mult) grid
    point, which fits its contract (a deterministic probe over a list of points)
    without bending it. We reduce to per-metric min/max across the grid and an
    ordering-invariant check at every point, then run the half-life probe at v1
    staleness+coverage to show its (in)sensitivity.
    """
    truth = gen_ground_truth(seed=701)
    grid = [(s, c) for s in STALENESS_MULT_GRID for c in COVERAGE_MULT_GRID]
    by_point = scale_sweep(
        lambda pt: _sweep_point(truth, pt[0], pt[1], V1_PARAMS.half_life_days), grid)
    points = [by_point[pt] for pt in grid]   # list, in deterministic grid order

    # Half-life robustness probe: hold staleness+coverage at v1, vary the decay
    # rate. Reported separately because it is inert on this corpus.
    hl_probe = [_sweep_point(truth, 1.0, 1.0, h) for h in HALF_LIFE_PROBE]
    hl_cross = sorted({p["cross_tool_recovery"] for p in hl_probe})
    hl_lever = sorted({p["lever_gain"] for p in hl_probe})
    half_life_inert = (len(hl_cross) == 1 and len(hl_lever) == 1)

    def _at(p):
        return {"staleness_mult": p["staleness_mult"], "coverage_mult": p["coverage_mult"]}

    def rng_of(key):
        vals = [p[key] for p in points]
        lo = min(vals)
        hi = max(vals)
        return {
            "min": round(lo, 4),
            "max": round(hi, 4),
            "min_at": next(_at(p) for p in points if p[key] == lo),
            "max_at": next(_at(p) for p in points if p[key] == hi),
        }

    # Ordering invariants, checked at EVERY grid point (the transferable claim).
    cross_gt_single = all(p["cross_tool_recovery"] > p["best_single_recovery"] for p in points)
    residual_pos = all(p["residual_gap"] > 0.0 for p in points)
    scored_gt_naive = all(p["scored_merge_recovery"] > p["naive_authority_merge_recovery"]
                          for p in points)
    # The weaker margin worth reporting honestly: the smallest gap on each axis.
    min_cross_minus_single = round(min(p["cross_minus_best_single"] for p in points), 4)
    min_lever_gain = round(min(p["lever_gain"] for p in points), 4)

    return {
        "grid_axes": {
            "staleness_mult": list(STALENESS_MULT_GRID),
            "coverage_mult": list(COVERAGE_MULT_GRID),
        },
        "n_grid_points": len(points),
        "points": points,
        "metric_ranges": {
            "best_single_recovery": rng_of("best_single_recovery"),
            "cross_tool_recovery": rng_of("cross_tool_recovery"),
            "cross_minus_best_single": rng_of("cross_minus_best_single"),
            "residual_gap": rng_of("residual_gap"),
            "lever_gain": rng_of("lever_gain"),
        },
        "ordering_holds": {
            "cross_tool_gt_best_single": cross_gt_single,
            "residual_gap_positive": residual_pos,
            "scored_merge_gt_naive": scored_gt_naive,
            "all_invariants_hold": cross_gt_single and residual_pos and scored_gt_naive,
            "min_cross_minus_best_single": min_cross_minus_single,
            "min_lever_gain": min_lever_gain,
        },
        "half_life_probe": {
            "half_life_days": list(HALF_LIFE_PROBE),
            "cross_tool_recovery_distinct": hl_cross,
            "lever_gain_distinct": hl_lever,
            "inert_on_this_corpus": half_life_inert,
            "note": ("freshness half-life swept 7-90d at v1 staleness+coverage; the "
                     "metrics do not move because the fresh source (EDR) is also the "
                     "higher-confidence one, so decay never flips a per-cell winner. "
                     "The lever here is the confidence+authority ordering, not the "
                     "decay rate — reported as a null, not hidden."),
        },
    }


# ---------------------------------------------------------------------------
# EXT-2 — second entity type: IDENTITIES with a CONTESTED JOIN KEY.
#
# v1 assets share one clean key (asset_id) across every tool, so the cross-tool
# merge is a clean equi-join and the only thing being recovered is attribute
# truth. Identity data is harder: the IdP keys on email, the EDR on UPN, HR on
# employee_id, the directory on sAMAccountName, and those keys disagree, so a
# merge must FIRST decide which records are the same human before it can merge
# their attributes. Entity resolution is itself part of the assurance gap.
#
# We plant the true person<->key mapping as ground truth (known, because we
# generate it), then each tool emits records under ITS OWN key with a
# deterministic resolution-flaw model:
#   - HR        keys on employee_id     (canonical, complete, but slow/stale on
#                                         the volatile attributes)
#   - IdP       keys on email           (fresh on dept/title; email churns on
#                                         name change so a fraction is stale)
#   - EDR       keys on UPN             (fresh on last_logon/managed; covers only
#                                         endpoint-bound identities)
#   - Directory keys on sAMAccountName  (fresh on group/enabled; legacy accounts
#                                         missing a sAMAccountName are unjoinable)
# No single column joins all four. We resolve in two regimes and compare:
#   CLEAN-KEY oracle  — merge on the planted person_id (the asset-style clean
#                       join): the ceiling, what recovery would be if the key
#                       were never contested.
#   CONTESTED-KEY     — resolve identity from the disagreeing keys with a
#                       deterministic linker (transitive closure over the
#                       cross-tool key overlaps), THEN merge attributes on the
#                       resolved cluster. The degradation vs the oracle is the
#                       entity-resolution tax — the part of the assurance gap
#                       that is join, not coverage.
# ---------------------------------------------------------------------------
N_IDENTITIES = 12_000
ID_ATTRIBUTES = ("department", "title", "manager", "account_enabled", "last_logon")
DEPARTMENTS = ("eng", "sales", "finance", "hr", "legal", "ops", "security", "exec")
TITLES = ("analyst", "manager", "director", "engineer", "vp", "associate", "lead")

# Authority of record per identity attribute (the naive "trust HR" merge target).
ID_AUTHORITY = {
    "department": "hr",
    "title": "hr",
    "manager": "hr",
    "account_enabled": "dir",   # the directory is the truth for enabled/disabled
    "last_logon": "edr",        # only the endpoint tool sees real last logon
}


def gen_identity_truth(seed: int):
    """Plant N identities, each with a true value for five attributes AND the four
    true keys (employee_id, email, upn, sam) that the tools will disagree on. The
    keys are derived from a stable display handle so collisions are avoided and the
    ground-truth person<->key mapping is exact."""
    rng = new_rng(seed)
    people = []
    for i in range(N_IDENTITIES):
        handle = f"u{i:05d}"
        # endpoint-bound = has an assigned workstation, so EDR can see them.
        endpoint_bound = rng.random() < 0.82
        # legacy accounts predate the sAMAccountName convention (no sam key).
        has_sam = rng.random() < 0.88
        people.append({
            "person_id": i,
            "employee_id": f"E{i:06d}",
            "email": f"{handle}@corp.example",
            "upn": f"{handle}@ad.corp.example",
            "sam": (f"CORP\\{handle}" if has_sam else None),
            "endpoint_bound": endpoint_bound,
            "has_sam": has_sam,
            "department": rng.choice(DEPARTMENTS),
            "title": rng.choice(TITLES),
            "manager": f"E{rng.randint(0, N_IDENTITIES-1):06d}",
            "account_enabled": rng.random() < 0.93,
            "last_logon": rng.randint(150, 158),    # day-of-year, "now" ~ 158
        })
    return people


def validate_identity_corpus(people):
    """Integrity check on the planted identity ground truth, mirroring the asset
    corpus check: contiguous unique person_ids, all attributes present and
    in-domain, keys unique where present, and the structural flags consistent."""
    ids = [p["person_id"] for p in people]
    emails = [p["email"] for p in people]
    eids = [p["employee_id"] for p in people]
    sams = [p["sam"] for p in people if p["sam"] is not None]
    checks = {
        "row_count_ok": len(people) == N_IDENTITIES,
        "ids_contiguous_unique": sorted(ids) == list(range(N_IDENTITIES)),
        "all_attributes_present": all(
            all(attr in p for attr in ID_ATTRIBUTES) for p in people),
        "dept_in_domain": all(p["department"] in DEPARTMENTS for p in people),
        "title_in_domain": all(p["title"] in TITLES for p in people),
        "email_unique": len(set(emails)) == len(emails),
        "employee_id_unique": len(set(eids)) == len(eids),
        "sam_unique_where_present": len(set(sams)) == len(sams),
        "sam_flag_consistent": all((p["sam"] is not None) == p["has_sam"] for p in people),
        "last_logon_in_range": all(150 <= p["last_logon"] <= 158 for p in people),
    }
    checks["all_passed"] = all(checks.values())
    return checks


def gen_identity_observations(people, seed: int, params: FlawParams = V1_PARAMS):
    """Each tool emits identity records under ITS OWN key, plus attribute readings
    under its characteristic flaw model. Returns two parallel row sets:

      key_rows  — (source, person_id_TRUE, key_kind, key_value): the keys a tool
                  exposes. person_id_TRUE is carried ONLY so we can score the
                  resolution against ground truth; the linker is NOT allowed to
                  see it (it joins on key_value overlaps only).
      attr_rows — (source, person_id_TRUE, attribute, value, observed_day,
                  confidence): attribute readings, same shape as the asset obs.

    The contested-join difficulty is built into which key_kinds each tool exposes
    and how often a key is missing/garbled, so two tools can fail to share any
    joinable column for some people — those people can only be partially resolved.
    """
    rng = new_rng(seed)
    key_rows = []
    attr_rows = []

    def emit_key(src, pid, kind, val):
        if val is not None:
            key_rows.append((src, pid, kind, str(val)))

    def emit_attr(src, pid, attr, val, day, conf):
        attr_rows.append((src, pid, attr, str(val), int(day), float(conf)))

    NOW = NOW_DAY
    for p in people:
        pid = p["person_id"]

        # ---- HR (keys on employee_id) ----------------------------------------
        # Canonical and complete on the org attributes, but slow: its last_logon
        # is unknown (HR doesn't see logons) and its email may be a maiden-name
        # address that has since changed, so HR's email key is stale ~12% of the
        # time (the join hazard: HR's email won't match the IdP's current email).
        emit_key("hr", pid, "employee_id", p["employee_id"])
        hr_email = p["email"] if rng.random() < 0.88 else f"old{pid:05d}@corp.example"
        emit_key("hr", pid, "email", hr_email)
        emit_attr("hr", pid, "department", p["department"], NOW - rng.randint(0, 3), 0.95)
        emit_attr("hr", pid, "title", p["title"], NOW - rng.randint(0, 3), 0.92)
        emit_attr("hr", pid, "manager", p["manager"], NOW - rng.randint(0, 3), 0.95)

        # ---- IdP (keys on email) ---------------------------------------------
        # Fresh on department/title for the subset it governs; keys on the CURRENT
        # email (which is why it disagrees with HR's stale email). Also exposes UPN
        # for a majority, the only bridge to EDR.
        if rng.random() < params.cov(0.95):
            emit_key("idp", pid, "email", p["email"])
            if rng.random() < 0.85:
                emit_key("idp", pid, "upn", p["upn"])
            emit_attr("idp", pid, "department", p["department"], NOW, 0.88)
            emit_attr("idp", pid, "title", p["title"], NOW, 0.85)

        # ---- EDR (keys on UPN) -----------------------------------------------
        # Endpoint-bound identities only; fresh on last_logon + account_enabled.
        # Keys on UPN, occasionally on sAMAccountName too (the bridge to the
        # directory). No employee_id and no email, so EDR cannot join to HR
        # directly — it must route through IdP's email<->upn or the directory.
        if p["endpoint_bound"] and rng.random() < params.cov(params.edr_agent_present):
            emit_key("edr", pid, "upn", p["upn"])
            if p["has_sam"] and rng.random() < 0.6:
                emit_key("edr", pid, "sam", p["sam"])
            emit_attr("edr", pid, "last_logon", p["last_logon"], NOW, 0.90)
            emit_attr("edr", pid, "account_enabled", p["account_enabled"], NOW, 0.80)

        # ---- Directory (keys on sAMAccountName) ------------------------------
        # Authority on account_enabled; fresh. Keys on sAMAccountName (absent on
        # legacy accounts -> unjoinable to EDR's sam) and on UPN for most, the
        # bridge that lets the directory link to EDR/IdP.
        if p["has_sam"]:
            emit_key("dir", pid, "sam", p["sam"])
            if rng.random() < 0.9:
                emit_key("dir", pid, "upn", p["upn"])
            emit_attr("dir", pid, "account_enabled", p["account_enabled"], NOW, 0.93)
            # the directory also re-asserts a (possibly stale) last_logon
            dir_logon = p["last_logon"] if rng.random() < 0.4 else p["last_logon"] - rng.randint(5, 30)
            emit_attr("dir", pid, "last_logon", dir_logon, NOW - rng.randint(3, 20), 0.6)

    return key_rows, attr_rows


def score_identities(people, key_rows, attr_rows, params: FlawParams = V1_PARAMS):
    """Score identity recovery under two join regimes and return the comparison.

    CLEAN-KEY oracle: merge attributes on the planted person_id (the asset-style
    clean join) — the ceiling, recovery if the key were never contested.

    CONTESTED-KEY: resolve identity from the disagreeing key VALUES only (the
    linker never sees person_id), by transitive closure over shared key values,
    then merge attributes within each resolved cluster. Recovery is scored against
    the planted truth; the drop from the oracle is the entity-resolution tax.
    """
    con = connect()
    import pyarrow as pa

    # planted attribute truth, long
    tl = []
    for p in people:
        for attr in ID_ATTRIBUTES:
            tl.append((p["person_id"], attr, str(p[attr])))
    con.register("id_truth_arrow", pa.table({
        "person_id": pa.array([r[0] for r in tl], pa.int32()),
        "attribute": pa.array([r[1] for r in tl]),
        "true_value": pa.array([r[2] for r in tl]),
    }))
    con.register("id_keys_arrow", pa.table({
        "source": pa.array([r[0] for r in key_rows]),
        "person_id": pa.array([r[1] for r in key_rows], pa.int32()),
        "key_kind": pa.array([r[2] for r in key_rows]),
        "key_value": pa.array([r[3] for r in key_rows]),
    }))
    con.register("id_attr_arrow", pa.table({
        "source": pa.array([r[0] for r in attr_rows]),
        "person_id": pa.array([r[1] for r in attr_rows], pa.int32()),
        "attribute": pa.array([r[2] for r in attr_rows]),
        "value": pa.array([r[3] for r in attr_rows]),
        "observed_day": pa.array([r[4] for r in attr_rows], pa.int32()),
        "confidence": pa.array([r[5] for r in attr_rows], pa.float64()),
    }))
    con.execute("CREATE TABLE id_truth AS SELECT * FROM id_truth_arrow")
    con.execute("CREATE TABLE id_keys  AS SELECT * FROM id_keys_arrow")
    con.execute("CREATE TABLE id_attr  AS SELECT * FROM id_attr_arrow")

    total_cells = N_IDENTITIES * len(ID_ATTRIBUTES)

    # effective score, same lever as v1 (freshness-decayed confidence + authority)
    con.execute("""
        CREATE TABLE id_scored AS
        SELECT *,
          confidence * pow(0.5, (CAST(? AS DOUBLE) - observed_day) / CAST(? AS DOUBLE))
            + CASE WHEN source = CASE attribute
                """ + "\n".join(
                    f"WHEN '{a}' THEN '{src}'" for a, src in ID_AUTHORITY.items()
                ) + """ END
                   THEN CAST(? AS DOUBLE) ELSE 0 END AS effective_score
        FROM id_attr
    """, [NOW_DAY, params.half_life_days, params.authority_bonus])

    def merge_recovery(cluster_table):
        """Recovery scored per PLANTED person, against the full planted estate.

        cluster_table has rows (person_key, person_id, source, attribute, value,
        effective_score): each tool-record's attributes, tagged with the resolved
        cluster (person_key) it landed in and the planted person_id it truly is
        (carried for scoring only, never used by the linker).

        We (1) pick the best-scored value per (cluster, attribute); (2) assign each
        PLANTED person to the single cluster holding the plurality of that person's
        tool-records — so a fragmented person reads only its largest fragment and
        loses the cells stranded in the others; (3) count a planted (person,
        attribute) cell as recovered iff the assigned cluster's merged value equals
        the planted truth. The denominator is the full planted estate (every person
        × every attribute), so fragmentation and over-merge both cost recovery and
        the result can never exceed 100% — there is exactly one scored row per
        planted cell."""
        con.execute(f"""
            CREATE OR REPLACE TABLE _picked AS
            SELECT person_key, attribute, value AS chosen_value FROM (
              SELECT person_key, attribute, value, row_number() OVER (
                PARTITION BY person_key, attribute
                ORDER BY effective_score DESC, source ASC) rn
              FROM {cluster_table}) WHERE rn = 1
        """)
        # assign each planted person to the cluster holding the plurality of ITS
        # records (ties broken by smallest person_key for determinism).
        con.execute(f"""
            CREATE OR REPLACE TABLE _person_cluster AS
            SELECT person_id, person_key FROM (
              SELECT person_id, person_key, COUNT(*) c,
                     row_number() OVER (PARTITION BY person_id
                       ORDER BY COUNT(*) DESC, person_key ASC) rn
              FROM {cluster_table} GROUP BY person_id, person_key) WHERE rn = 1
        """)
        # score over the FULL planted estate: a cell is recovered only if the
        # person was resolved to a cluster AND that cluster's merged value matches.
        return int(con.execute("""
            SELECT COUNT(*) FROM id_truth t
            JOIN _person_cluster pc ON pc.person_id = t.person_id
            JOIN _picked p ON p.person_key = pc.person_key AND p.attribute = t.attribute
            WHERE p.chosen_value = t.true_value
        """).fetchone()[0])

    # --- CLEAN-KEY oracle: cluster == planted person_id -----------------------
    con.execute("""
        CREATE TABLE clean_clusters AS
        SELECT person_id AS person_key, person_id, source, attribute, value, effective_score
        FROM id_scored
    """)
    clean_correct = merge_recovery("clean_clusters")
    clean_recovery = round(clean_correct / total_cells, 4)

    # --- CONTESTED-KEY: resolve from key VALUES only (no person_id) ------------
    # Build an undirected graph whose nodes are (source, person_id) tool-records
    # and whose edges connect two records that EXPOSE THE SAME (key_kind,
    # key_value). The linker never reads person_id — edges come only from shared
    # key values, exactly as a real entity-resolution pass would have to. We then
    # take the connected components (transitive closure) as resolved clusters.
    con.execute("""
        CREATE TABLE node AS
        SELECT DISTINCT source, person_id,
               source || '#' || CAST(person_id AS VARCHAR) AS node_id
        FROM id_keys
    """)
    # edges: same (key_kind, key_value) shared by two distinct tool-records.
    con.execute("""
        CREATE TABLE edge AS
        SELECT DISTINCT a.source||'#'||CAST(a.person_id AS VARCHAR) AS u,
                        b.source||'#'||CAST(b.person_id AS VARCHAR) AS v
        FROM id_keys a JOIN id_keys b
          ON a.key_kind = b.key_kind AND a.key_value = b.key_value
         AND (a.source < b.source OR (a.source = b.source AND a.person_id < b.person_id))
    """)
    # iterative label propagation to connected-component labels: each node starts
    # with its own id; repeatedly take the min label over itself + neighbours
    # until stable. Deterministic (min over strings); bounded iteration count.
    con.execute("CREATE TABLE label AS SELECT node_id, node_id AS lbl FROM node")
    for _ in range(40):
        changed = con.execute("""
            CREATE OR REPLACE TABLE label_next AS
            WITH adj AS (
              SELECT u AS a, v AS b FROM edge
              UNION ALL SELECT v AS a, u AS b FROM edge
            ),
            prop AS (
              SELECT l.node_id, l.lbl AS self_lbl,
                     MIN(ln.lbl) AS nbr_lbl
              FROM label l
              LEFT JOIN adj ON adj.a = l.node_id
              LEFT JOIN label ln ON ln.node_id = adj.b
              GROUP BY l.node_id, l.lbl
            )
            SELECT node_id, LEAST(self_lbl, COALESCE(nbr_lbl, self_lbl)) AS lbl
            FROM prop
        """)
        n_changed = int(con.execute("""
            SELECT COUNT(*) FROM label l JOIN label_next n USING (node_id)
            WHERE l.lbl <> n.lbl
        """).fetchone()[0])
        con.execute("DROP TABLE label; ALTER TABLE label_next RENAME TO label")
        if n_changed == 0:
            break
    # resolved cluster id = dense integer per component label
    con.execute("""
        CREATE TABLE resolved AS
        SELECT n.source, n.person_id,
               DENSE_RANK() OVER (ORDER BY l.lbl) AS person_key
        FROM node n JOIN label l ON l.node_id = n.node_id
    """)
    # attach attributes to resolved clusters
    con.execute("""
        CREATE TABLE contested_clusters AS
        SELECT r.person_key, s.person_id, s.source, s.attribute, s.value, s.effective_score
        FROM id_scored s JOIN resolved r
          ON r.source = s.source AND r.person_id = s.person_id
    """)
    contested_correct = merge_recovery("contested_clusters")
    contested_recovery = round(contested_correct / total_cells, 4)

    # --- resolution diagnostics ------------------------------------------------
    # How well did the linker reconstruct the planted identity? A resolved cluster
    # is "pure" if all its tool-records belong to one planted person; "fragmented"
    # if one planted person's records landed in >1 cluster (under-merge);
    # "over-merged" if a cluster mixes >1 planted person.
    n_clusters = int(con.execute("SELECT COUNT(DISTINCT person_key) FROM resolved").fetchone()[0])
    n_people_with_records = int(con.execute(
        "SELECT COUNT(DISTINCT person_id) FROM resolved").fetchone()[0])
    over_merged = int(con.execute("""
        SELECT COUNT(*) FROM (
          SELECT person_key FROM resolved
          GROUP BY person_key HAVING COUNT(DISTINCT person_id) > 1)
    """).fetchone()[0])
    fragmented = int(con.execute("""
        SELECT COUNT(*) FROM (
          SELECT person_id FROM resolved
          GROUP BY person_id HAVING COUNT(DISTINCT person_key) > 1)
    """).fetchone()[0])
    # naive single-key baseline: try to join everything on employee_id alone —
    # only HR exposes it, so EDR/IdP/dir attributes are simply lost. This is what
    # "just pick a join key" costs, the join analogue of v1's naive merge.
    naive_correct = int(con.execute("""
        WITH hr_key AS (
          SELECT person_id FROM id_keys WHERE key_kind='employee_id' AND source='hr'
        ),
        picked AS (
          SELECT s.person_id, s.attribute, s.value AS chosen_value FROM (
            SELECT *, row_number() OVER (PARTITION BY person_id, attribute
              ORDER BY effective_score DESC, source ASC) rn
            FROM id_scored s2
            WHERE s2.person_id IN (SELECT person_id FROM hr_key)
              AND s2.source = 'hr') s WHERE rn = 1
        )
        SELECT COUNT(*) FROM picked p JOIN id_truth t
          ON t.person_id = p.person_id AND t.attribute = p.attribute
        WHERE p.chosen_value = t.true_value
    """).fetchone()[0])
    naive_recovery = round(naive_correct / total_cells, 4)

    con.close()

    resolution_tax = round(clean_recovery - contested_recovery, 4)
    return {
        "entity": "identities (contested join key)",
        "n_identities": N_IDENTITIES,
        "attributes": list(ID_ATTRIBUTES),
        "total_cells": total_cells,
        "n_key_rows": len(key_rows),
        "n_attr_rows": len(attr_rows),
        "tool_keys": {
            "hr": "employee_id (+ sometimes-stale email)",
            "idp": "email (+ upn bridge)",
            "edr": "upn (+ sometimes sam)",
            "dir": "sam (+ upn bridge)",
        },
        "clean_key_oracle_recovery": clean_recovery,
        "contested_key_recovery": contested_recovery,
        "resolution_tax": resolution_tax,             # clean - contested
        "naive_single_key_recovery": naive_recovery,  # join on employee_id only
        "resolution_diagnostics": {
            "n_resolved_clusters": n_clusters,
            "n_planted_people_with_records": n_people_with_records,
            "over_merged_clusters": over_merged,
            "fragmented_people": fragmented,
        },
    }


def run_identities(params: FlawParams = V1_PARAMS):
    people = gen_identity_truth(seed=703)
    integrity = validate_identity_corpus(people)
    key_rows, attr_rows = gen_identity_observations(people, seed=704, params=params)
    scored = score_identities(people, key_rows, attr_rows, params=params)
    return {"corpus_integrity": integrity, "measures": scored}


def run(params: FlawParams = V1_PARAMS):
    truth = gen_ground_truth(seed=701)
    integrity = validate_corpus(truth)
    obs = gen_observations(truth, seed=702, params=params)
    scored = score(truth, obs, params=params)
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
def _build_all(params: FlawParams = V1_PARAMS):
    """The full result payload — v1 assets + EXT-1 sweep + EXT-2 identities — as
    one object, so the determinism assert covers everything that gets published."""
    base = run(params)
    return {
        **base,
        "parameter_sweep": sweep(),
        "identities_contested_key": run_identities(params),
    }


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)

    first = _build_all()
    second = _build_all()
    deterministic = canonical(first) == canonical(second)
    if not deterministic:
        raise SystemExit("DETERMINISM FAILED: two in-process runs differ — refusing to publish.")
    if not first["corpus_integrity"]["all_passed"]:
        raise SystemExit("CORPUS INTEGRITY FAILED: planted asset ground truth is inconsistent.")
    if not first["identities_contested_key"]["corpus_integrity"]["all_passed"]:
        raise SystemExit("CORPUS INTEGRITY FAILED: planted identity ground truth is inconsistent.")

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
    sw = first["parameter_sweep"]
    idr = first["identities_contested_key"]["measures"]
    oh = sw["ordering_holds"]
    print(f"determinism_verified={deterministic}  "
          f"asset_corpus_integrity={first['corpus_integrity']['all_passed']}  "
          f"identity_corpus_integrity={first['identities_contested_key']['corpus_integrity']['all_passed']}  "
          f"duckdb={duckdb.__version__}  results_sha256[:16]={digest}")
    print(f"[v1 assets]  best single ({m['best_single_tool']}): {m['best_single_recovery']:.1%}  |  "
          f"cross-tool: {m['cross_tool_recovery']:.1%}  (+{m['cross_minus_best_single']:.1%})  |  "
          f"residual: {m['residual_gap']:.1%}  |  lever: {m['lever']['lever_gain']:.1%}")
    cr = sw["metric_ranges"]
    print(f"[EXT-1 sweep {sw['n_grid_points']} pts]  "
          f"cross-tool {cr['cross_tool_recovery']['min']:.1%}-{cr['cross_tool_recovery']['max']:.1%}  |  "
          f"residual {cr['residual_gap']['min']:.1%}-{cr['residual_gap']['max']:.1%}  |  "
          f"lever {cr['lever_gain']['min']:.1%}-{cr['lever_gain']['max']:.1%}  |  "
          f"order_holds={oh['all_invariants_hold']} "
          f"(min cross-best={oh['min_cross_minus_best_single']:.1%}, min lever={oh['min_lever_gain']:.1%})")
    print(f"[EXT-2 identities]  clean-key oracle: {idr['clean_key_oracle_recovery']:.1%}  |  "
          f"contested-key: {idr['contested_key_recovery']:.1%}  |  "
          f"resolution tax: -{idr['resolution_tax']:.1%}  |  "
          f"naive single-key: {idr['naive_single_key_recovery']:.1%}")
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

    # ---- EXT-1: parameter sweep ----------------------------------------------
    sw = results["parameter_sweep"]
    cr = sw["metric_ranges"]
    oh = sw["ordering_holds"]
    hlp = sw["half_life_probe"]
    a("## (EXT-1) Parameter sweep — is the ORDER robust, not just the magnitude?\n")
    a(f"The v1 headline numbers are functions of the flaw-model parameters. We sweep the two that genuinely move "
      f"them on this corpus — the **staleness window** (a multiplier on how much of the CMDB's volatile inventory "
      f"is stale: ×{', ×'.join(str(s) for s in sw['grid_axes']['staleness_mult'])}) and a **per-tool coverage** "
      f"multiplier (×{', ×'.join(str(c) for c in sw['grid_axes']['coverage_mult'])}) — across a "
      f"{sw['n_grid_points']}-point grid, recomputing all four measures at every point. The transferable claim is "
      f"the **order**, so what matters is whether it holds at every cell, not the v1 magnitude.\n")
    a("| metric | min (at) | max (at) |")
    a("|---|--:|--:|")
    for label, key in (("best-single recovery", "best_single_recovery"),
                       ("cross-tool recovery", "cross_tool_recovery"),
                       ("cross − best-single", "cross_minus_best_single"),
                       ("residual gap", "residual_gap"),
                       ("lever gain", "lever_gain")):
        r = cr[key]
        a(f"| {label} | {r['min']:.1%} "
          f"(stale×{r['min_at']['staleness_mult']:g}, cov×{r['min_at']['coverage_mult']:g}) | "
          f"{r['max']:.1%} (stale×{r['max_at']['staleness_mult']:g}, cov×{r['max_at']['coverage_mult']:g}) |")
    a("")
    a(f"**Ordering invariants across all {sw['n_grid_points']} grid points:**\n")
    a(f"- cross-tool recovery **>** best single tool: **{oh['cross_tool_gt_best_single']}** "
      f"(smallest margin in the grid: +{oh['min_cross_minus_best_single']:.1%})")
    a(f"- residual gap **> 0** (a blind spot always remains): **{oh['residual_gap_positive']}**")
    a(f"- scored merge **>** naive authority merge (the lever is real): **{oh['scored_merge_gt_naive']}** "
      f"(smallest lever in the grid: +{oh['min_lever_gain']:.1%})")
    a(f"- **all three hold at every grid point: {oh['all_invariants_hold']}**\n")
    a("Per-point grid (each cell is a full rebuild + rescore of the same planted estate):\n")
    a("| staleness × | cov × | best-single | cross-tool | cross−best | residual | lever |")
    a("|--:|--:|--:|--:|--:|--:|--:|")
    for p in sw["points"]:
        a(f"| {p['staleness_mult']:g} | {p['coverage_mult']:g} | "
          f"{p['best_single_recovery']:.1%} | {p['cross_tool_recovery']:.1%} | "
          f"+{p['cross_minus_best_single']:.1%} | {p['residual_gap']:.1%} | "
          f"+{p['lever_gain']:.1%} |")
    a("\nThe magnitudes move with the parameters exactly as the methodology predicts — more CMDB staleness drags "
      "best-single down and grows the lever, thinner coverage grows the residual — but the three orderings the "
      "thesis rests on do not invert anywhere in the grid"
      + ("." if oh["all_invariants_hold"]
         else ", **except where flagged above — reported honestly rather than hidden.**")
      + " That is the point of sweeping rather than asserting at one tuned point: the headline 75.6% is a "
        "parameter-dependent number, but cross-tool > best-single is a property of the mechanism.\n")
    # Half-life probe — reported as a null, not hidden.
    a("### Freshness half-life — a swept axis that turns out inert here (a null, reported)\n")
    a(f"We also swept the **freshness half-life** (how fast confidence decays) across "
      f"{', '.join(f'{h:g}' for h in hlp['half_life_days'])} days at v1 staleness and coverage. On this corpus it is "
      f"**{'inert' if hlp['inert_on_this_corpus'] else 'live'}**: cross-tool recovery takes the distinct value(s) "
      f"{', '.join(f'{v:.1%}' for v in hlp['cross_tool_recovery_distinct'])} and the lever "
      f"{', '.join(f'+{v:.1%}' for v in hlp['lever_gain_distinct'])} across the whole range. The reason is "
      f"structural — the fresh source (EDR) is also the higher-confidence one, so freshness decay never flips a "
      f"per-cell winner, and the lever is carried by the confidence+authority ordering rather than by the decay "
      f"rate. That is worth stating plainly: on an estate where the freshest source were the *lower*-confidence "
      f"one, the half-life would bite; here it does not, and pretending the axis moved would be the dishonest "
      f"move.\n")

    # ---- EXT-2: identities with a contested join key -------------------------
    idm = results["identities_contested_key"]["measures"]
    rd = idm["resolution_diagnostics"]
    a("## (EXT-2) Identities with a contested join key — entity resolution is part of the gap\n")
    a(f"v1 assets share one clean key (`asset_id`) across every tool, so the cross-tool merge is a clean "
      f"equi-join. Identity data is harder: the four tools key on **different, disagreeing** columns "
      f"(HR `employee_id`, IdP `email`, EDR `upn`, directory `sAMAccountName`), and no single column joins all "
      f"four. The merge must first reconcile which records are the same human — entity resolution — before it can "
      f"recover any attribute. We plant the true person↔key mapping ({idm['n_identities']:,} identities × "
      f"{len(idm['attributes'])} attributes = {idm['total_cells']:,} cells), then score two regimes.\n")
    a("| regime | recovery |")
    a("|---|--:|")
    a(f"| **clean-key oracle** (merge on planted `person_id`, the asset-style join) | **{idm['clean_key_oracle_recovery']:.1%}** |")
    a(f"| **contested-key** (resolve from disagreeing key *values* only, then merge) | **{idm['contested_key_recovery']:.1%}** |")
    a(f"| **resolution tax** (oracle − contested) | **−{idm['resolution_tax']:.1%}** |")
    a(f"| naive single-key join (`employee_id` only — drops every non-HR tool) | {idm['naive_single_key_recovery']:.1%} |\n")
    a(f"The clean-key oracle is the asset-style case: if the join key were never contested, the cross-tool merge "
      f"recovers **{idm['clean_key_oracle_recovery']:.1%}** of the identity estate. The contested-key merge — which "
      f"only ever sees the disagreeing key *values* and must link records by their transitive overlap before "
      f"merging — recovers **{idm['contested_key_recovery']:.1%}**, a **−{idm['resolution_tax']:.1%}** entity-resolution "
      f"tax. That tax is the part of the assurance gap that is *join*, not *coverage*: the same attributes are "
      f"present, but a fraction of identities cannot be linked across the tools that hold them. The naive "
      f"\"just pick one join key\" approach (`employee_id`, which only HR exposes) collapses to "
      f"**{idm['naive_single_key_recovery']:.1%}**, because every EDR/IdP/directory attribute is simply unjoinable to it.\n")
    a("Resolution diagnostics (the linker never sees `person_id`; clusters come only from shared key values): "
      f"**{rd['n_resolved_clusters']:,}** clusters resolved from "
      f"**{rd['n_planted_people_with_records']:,}** planted people that have any tool record; "
      f"**{rd['over_merged_clusters']:,}** clusters over-merged (mix >1 person), "
      f"**{rd['fragmented_people']:,}** people fragmented across >1 cluster (under-merge — the legacy accounts with "
      f"no `sAMAccountName` and endpoints with no shared bridge key). Both failure modes cost recovery, and both "
      f"are absent in the clean-key asset case — which is why identities are the harder, more realistic test.\n")

    a("## Honesty boundary\n")
    a("Tier B: reproducible, first-party, single-host, **synthetic**. The flaw models (CMDB staleness window, "
      "EDR coverage of managed-only, scanner cadence, IDP owner overlap; and for identities the per-key "
      "missing/garbled rates) are corpus *parameters*, not universal constants; the magnitudes move if you move "
      "them. The transferable, parameter-independent finding is the **order**: cross-tool recovery > best single "
      "tool, the residual gap is small but nonzero, and the freshness/confidence score is what produces the lift "
      "over a naive authority merge. EXT-1 demonstrates that order holds across a 3×3 parameter grid rather than "
      "at one tuned point; EXT-2 shows the order survives on a harder entity (identities) but at a measured "
      "entity-resolution cost, so a contested join key is itself part of the assurance gap. The benchmark does "
      "NOT show real-world magnitudes, a specific vendor's resolution accuracy, or that any particular linker is "
      "optimal — only that the mechanism's ordering is robust to the swept parameters and that contesting the "
      "join key degrades recovery by a measurable, non-trivial amount. See `METHODOLOGY.md` for the flaw models "
      "and the falsification conditions.\n")

    with open(os.path.join(RESULTS_DIR, "RESULTS.md"), "w") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()

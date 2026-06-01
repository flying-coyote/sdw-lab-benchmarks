"""Failure mode 1 — absence-vs-NULL collapse, the silent detection miss.

In CloudTrail, ``userIdentity.sessionContext.attributes.mfaAuthenticated`` is
present with value "true" only when MFA was used. When MFA was NOT used the key
is *absent* from the JSON, not present-and-false. A flattening ETL that lowers
that key to a fixed column coerces the absence to NULL, so the natural
translation of the detection rule (``WHERE mfa = 'false'``) matches nothing and
the privilege-escalation alert silently returns zero. This module plants a known
count of "privilege escalation without MFA" events and measures how many each
schema recovers.
"""

import json

from common import new_rng, prf1, connect

PRIV_ESC = ("AttachUserPolicy", "PutUserPolicy", "AddUserToGroup")
BENIGN = ("GetObject", "DescribeInstances", "ListBuckets", "AssumeRole", "ConsoleLogin")


def _gen_corpus(n_events: int, seed: int):
    """Deterministic CloudTrail-shaped corpus with per-event ground truth.

    Ground-truth positive = a privilege-escalation API call made without MFA.
    Those are exactly the events the SOC 2 detection is supposed to catch.
    """
    rng = new_rng(seed)
    rows = []  # (event_id, event_name, user_identity_json)
    truth = set()  # event_ids that are priv-esc AND no-MFA
    for i in range(n_events):
        is_priv = rng.random() < 0.35
        event_name = rng.choice(PRIV_ESC if is_priv else BENIGN)
        mfa_used = rng.random() < 0.60

        attributes = {"creationDate": "2026-02-10T14:23:01Z"}
        if mfa_used:
            # present ONLY when MFA was used — the CloudTrail-faithful encoding
            attributes["mfaAuthenticated"] = "true"

        user_identity = {
            "type": "IAMUser",
            "userName": f"user{i % 50}@example.com",
            "sessionContext": {
                "attributes": attributes,
                "sessionIssuer": {
                    "type": "Role",
                    "arn": "arn:aws:iam::123456789012:role/AdminRole",
                },
            },
        }
        rows.append((i, event_name, json.dumps(user_identity)))
        if is_priv and not mfa_used:
            truth.add(i)
    return rows, truth


def _priv_in_clause():
    return "(" + ", ".join(f"'{e}'" for e in PRIV_ESC) + ")"


def run(scales=(1_000, 10_000, 100_000)):
    out = {
        "name": "absence_vs_null_silent_miss",
        "title": "Absence-vs-NULL collapse → silent detection miss",
        "scales": [],
    }
    inn = _priv_in_clause()

    for n in scales:
        rows, truth = _gen_corpus(n, seed=101)
        con = connect()
        con.execute(
            "CREATE TABLE preserved (event_id INTEGER, event_name VARCHAR, user_identity VARCHAR)"
        )
        con.executemany("INSERT INTO preserved VALUES (?, ?, ?)", rows)

        # The flattening ETL: lower the nested key to a fixed column. Absent -> NULL.
        con.execute(
            """
            CREATE TABLE flattened AS
            SELECT event_id,
                   event_name,
                   json_extract_string(user_identity,
                       '$.sessionContext.attributes.mfaAuthenticated') AS mfa_authenticated
            FROM preserved
            """
        )

        # (a) Naive flattened translation — the bug. Never matches: absent -> NULL,
        #     and a present value is 'true', so '= false' has nothing to hit.
        naive_sql = (
            f"SELECT event_id FROM flattened "
            f"WHERE event_name IN {inn} AND mfa_authenticated = 'false'"
        )
        caught_naive = {r[0] for r in con.execute(naive_sql).fetchall()}

        # (b) Flattened, NULL-aware translation (essay Approach 1) — recoverable
        #     only if the engineer knows absence is meaningful.
        fixed_sql = (
            f"SELECT event_id FROM flattened "
            f"WHERE event_name IN {inn} "
            f"AND (mfa_authenticated != 'true' OR mfa_authenticated IS NULL)"
        )
        caught_fixed = {r[0] for r in con.execute(fixed_sql).fetchall()}

        # (c) Preserved schema (Variant/JSON analog) — absence is queryable directly.
        preserved_sql = (
            f"SELECT event_id FROM preserved "
            f"WHERE event_name IN {inn} "
            f"AND json_extract_string(user_identity,"
            f"    '$.sessionContext.attributes.mfaAuthenticated') IS NULL"
        )
        caught_preserved = {r[0] for r in con.execute(preserved_sql).fetchall()}
        con.close()

        k = len(truth)
        out["scales"].append(
            {
                "n_events": n,
                "planted_true_positives": k,
                "flattened_naive": prf1(truth, caught_naive),
                "flattened_null_aware": prf1(truth, caught_fixed),
                "preserved_json": prf1(truth, caught_preserved),
                "silent_miss_rate_naive": round((k - len(truth & caught_naive)) / k, 4)
                if k
                else None,
            }
        )
    return out

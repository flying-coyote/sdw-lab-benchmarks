#!/usr/bin/env python3
"""Build the frozen S1 source data-type table (prereg section 4, S1) from the six per-schema
response files in s1_table_work/ (authored by six delegated readers under s1_table_work/BRIEF.md),
then apply the harness author's literal rulings on the readers' flagged judgment calls
(HARNESS-ADDENDUM.md, D14). Output: s1_source_type_table.csv.
Usage: python3 -I build_s1_table.py
"""
import csv
import json
import os

H = os.path.dirname(os.path.abspath(__file__))
W = os.path.join(H, "s1_table_work")
SCHEMAS = ["cim", "udm", "asim", "ecs", "opentelemetry", "zeek"]
FAMILIES = {"ip", "port", "timestamp", "string", "integer", "long", "float", "boolean", "hash", "mac",
            "object", "json", "ambiguous", ""}

# (schema, leaf_token) -> (family, ruling text[, verbatim evidence replacing a paraphrase])
RULINGS = {
    ("Splunk CIM", "dest_port"): ("long", "brief rule 2 applies only to generic strings; declared number -> long, "
                                  "as the reader did for other CIM numbers"),
    ("Splunk CIM", "file_hash"): ("string", "description says 'cryptographic identifier', not a hash digest; "
                                  "rule 2 not met literally"),
    ("Zeek", "community_id"): ("string", "only a script summary ('community hash IDs'), no field description; "
                               "rule 2 not met literally"),
    ("Zeek", "orig_l2_addr"): ("mac", "kept: the field doc says it is present if policy/protocols/conn/mac-logging "
                               "is loaded (checked on docs.zeek.org 2026-11-17)",
                               "orig_l2_addr : string &log &optional (present if policy/protocols/conn/mac-logging is loaded)"),
    ("Zeek", "resp_l2_addr"): ("mac", "kept, as orig_l2_addr",
                               "resp_l2_addr : string &log &optional (present if policy/protocols/conn/mac-logging is loaded)"),
    ("OpenTelemetry", "accessed"): ("timestamp", "kept; verbatim checked 2026-11-17",
                                    "Time when the file was last accessed, in ISO 8601 format."),
    ("OpenTelemetry", "created"): ("timestamp", "kept; verbatim checked 2026-11-17",
                                   "Time when the file was created, in ISO 8601 format."),
    ("OpenTelemetry", "modified"): ("timestamp", "kept; verbatim checked 2026-11-17",
                                    "Time when the file content was last modified, in ISO 8601 format."),
    ("OpenTelemetry", "time"): ("timestamp", "kept; verbatim checked 2026-11-17",
                                "The date and time the process was created, in ISO 8601 format."),
}


def main():
    rows = []
    for s in SCHEMAS:
        req = json.load(open(os.path.join(W, f"request-{s}.json")))
        resp = list(csv.DictReader(open(os.path.join(W, f"response-{s}.csv"))))
        assert [r["leaf_token"] for r in resp] == list(req["leaf_tokens"]), s
        for r in resp:
            r["schema"] = req["schema"]
            r["reader_family"] = r["family"]
            r["harness_ruling"] = ""
            k = (r["schema"], r["leaf_token"])
            if k in RULINGS:
                rl = RULINGS[k]
                r["family"], r["harness_ruling"] = rl[0], rl[1]
                if len(rl) > 2:
                    r["evidence"] = rl[2]
            assert r["family"] in FAMILIES, (k, r["family"])
            assert not r["family"] or r["doc_url"], k
            rows.append(r)
    hdr = ["schema", "leaf_token", "source_fields", "doc_type", "family", "reader_family", "harness_ruling",
           "doc_url", "fetch_date", "evidence"]
    out = os.path.join(H, "s1_source_type_table.csv")
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=hdr, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(len(rows), "rows;", sum(bool(r["harness_ruling"]) for r in rows), "ruled")


if __name__ == "__main__":
    main()

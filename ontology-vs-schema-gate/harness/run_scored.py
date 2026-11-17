#!/usr/bin/env python3
"""Scored-run driver (PREREGISTRATION.md section 8 step 5). NOT RUN at harness build.

Runs each requested arm over the 715 corpus triples (item_id = triple id) and over the E1 items,
writing results/arms/<ARM>-corpus.jsonl and <ARM>-e1.jsonl. Refuses to start unless the E1 items
file and the first E2 label batch exist with the sha256 values passed on the command line, which
must equal the ones recorded in HARNESS-ADDENDUM.md (section 8 steps 3 and 4 come first).
Usage: python3 -I run_scored.py <e1-items.jsonl> <e1_sha256> <labels-batch1.csv> <labels_sha256> [ARM ...]
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import arms as A  # noqa: E402
import common as C  # noqa: E402

OUT = os.path.join(C.G, "results", "arms")


def corpus_items():
    return [{"item_id": t["tid"], "tid": t["tid"], "schema": t["schema"], "source": t["source"],
             "ocsf": t["ocsf"], "cls": t["cls"], "cell": t["cell"]} for t in C.triples()]


def main(argv):
    e1_path, e1_sha, lab_path, lab_sha = argv[1:5]
    arms = argv[5:] or ["S1", "S2", "S3", "O0", "O1", "O2"]
    C.verify_pins()
    for p, h in ((e1_path, e1_sha), (lab_path, lab_sha)):
        if C.sha256(p) != h:
            raise SystemExit(f"hash mismatch on {p}; record it in the addendum before running arms")
    e1 = C.read_jsonl(e1_path)
    corpus = corpus_items()
    assert len(corpus) == 715
    for arm in arms:
        for name, items in (("corpus", corpus), ("e1", e1)):
            recs, meta = A.run_arm(arm, items)
            path = os.path.join(OUT, f"{arm}-{name}.jsonl")
            C.write_jsonl(path, recs)
            print(json.dumps({"arm": arm, "set": name, "n": len(recs), "meta": meta, "sha256": C.sha256(path)}))


if __name__ == "__main__":
    main(sys.argv)

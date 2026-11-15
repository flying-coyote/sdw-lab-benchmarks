#!/usr/bin/env python3
"""POST-HOC sensitivity (not pre-registered): treat ClickHouse's SUM-over-empty-set = 0 as equal to the SQL-standard
NULL the oracle returns. Three corpus queries return an empty qualifying set (two_stream_03, ueba_two_level_01,
ueba_two_level_03); both ClickHouse arms answer `0` where DuckDB, StarRocks and Trino answer NULL
(ClickHouse default aggregate_functions_null_for_empty = 0). The primary scoring counts those as silent_wrong, as
pre-registered; this re-scores with them counted as matches and writes results/scores_posthoc_empty_sum.json.
"""
import json

import score

orig_load = score.load_raw


def patched():
    raw = orig_load()
    oracle = json.loads((score.RESULTS / "oracle.json").read_text())["answers"]
    for arm, d in raw.items():
        for key, rec in d["queries"].items():
            if rec.get("matches_oracle") is False and key.startswith("corpus:"):
                gt = oracle[key.split(":", 1)[1]]
                fixed = [["0" if c == "NULL" else c for c in row] for row in gt]
                if rec["answer"] == fixed and gt[0][0] == "0":
                    rec["matches_oracle"] = True
                    rec["posthoc_empty_sum_match"] = True
    return raw


score.load_raw = patched
_write = score.Path.write_text


def write_text(self, data, *a, **k):
    if self.name == "scores.json":
        self = self.with_name("scores_posthoc_empty_sum.json")
    return _write(self, data, *a, **k)


score.Path.write_text = write_text
score.main()

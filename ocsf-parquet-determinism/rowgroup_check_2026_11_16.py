"""Post-hoc check (2026-11-16): what differs between the probe's unstable files, row-group order or row-group contents?

Uses the unmodified probe's corpus and coalesced SQL (determinism_probe.build_corpus / coalesced_sql), writes the
default multi-threaded store three times, and for each file records every row group's row count and an
order-independent hash of its rows, then lists which row groups (by content) any two files share and where.
Prompted by an adversarial review of the sibling essay's "row groups land in a different order" explanation.

    <venv>/bin/python -I -B rowgroup_check_2026_11_16.py <label>
"""
import hashlib, importlib.metadata as md, json, os, sys, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import duckdb, pyarrow.parquet as pq
import determinism_probe as dp


def main(label):
    d = tempfile.mkdtemp(prefix="rgcheck_"); con = duckdb.connect(); dp.build_corpus(con); sql = dp.coalesced_sql()
    files = []
    for i in range(3):
        p = os.path.join(d, f"f{i}.parquet"); con.execute(f"COPY ({sql}) TO '{p}' (FORMAT parquet)")
        f = pq.ParquetFile(p); groups = []
        for r in range(f.num_row_groups):
            t = f.read_row_group(r); rows = sorted(map(repr, zip(*[c.to_pylist() for c in t.columns])))
            groups.append([t.num_rows, hashlib.sha256("\n".join(rows).encode()).hexdigest()[:10]])
        files.append({"bytes": os.path.getsize(p), "row_groups": groups})
    shared = {f"{a},{b}": [[i, j] for i, x in enumerate(files[a]["row_groups"]) for j, y in enumerate(files[b]["row_groups"]) if x == y]
              for a in range(3) for b in range(a + 1, 3)}
    res = {"label": label, "run_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "duckdb": md.version("duckdb"), "pyarrow": md.version("pyarrow"), "files": files,
           "shared_row_groups_by_content_[pos_a,pos_b]": shared}
    json.dump(res, open(os.path.join(HERE, f"rowgroup-check-2026-11-16-{label}.json"), "w"), indent=2)
    print(json.dumps(res))


if __name__ == "__main__":
    main(sys.argv[1])

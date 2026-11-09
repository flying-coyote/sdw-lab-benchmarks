"""R6 measurement: bytes per million billed tokens for each arm x order x Parquet/Iceberg variant.

    python measure.py            # all corpora in data/ except held-out seed 99
Writes results/parquet.jsonl, results/iceberg.jsonl, results/dict.jsonl, results/corpus.jsonl.
Sizes are exact; nothing here is timed, so no latency claims follow from it.
"""
import glob
import hashlib
import json
import os
import shutil
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.feather as feather
import pyarrow.parquet as pq
import zstandard as zstd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
RES = os.path.join(HERE, "results")
WORK = os.path.join(HERE, "work")
TEXT = ["prompt_text_delta", "prompt_text_full", "response_text", "prompt_sha256", "response_sha256"]
ARMS = ["T0_metadata", "T1_hash", "T2_delta", "T3_full"]
VARIANTS = {
    "snappy_default": dict(compression="snappy"),
    "zstd_default": dict(compression="zstd"),
    "zstd_1": dict(compression="zstd", compression_level=1),
    "zstd_3": dict(compression="zstd", compression_level=3),
    "zstd_9": dict(compression="zstd", compression_level=9),
    "zstd_19": dict(compression="zstd", compression_level=19),
    "zstd_default_nodict_text": dict(compression="zstd", nodict_text=True),
    "zstd_default_page8m": dict(compression="zstd", data_page_size=8 * 1024 * 1024),
}
COMMON = dict(row_group_size=1_048_576, version="2.6")


def load(name):
    t = feather.read_table(os.path.join(DATA, name + ".arrow"))
    t = t.set_column(t.schema.get_field_index("time"), "time", pc.cast(t["time"], pa.timestamp("us", tz="UTC")))
    for i, f in enumerate(t.schema):  # chat tier has no tool calls -> all-null columns; give them a type
        if pa.types.is_null(f.type):
            t = t.set_column(i, f.name, pc.cast(t[f.name], pa.string()))
    return t.rename_columns([c.replace(".", "__") for c in t.column_names])


def arm_table(t, arm):
    base = [c for c in t.column_names if c not in TEXT]
    if arm == "T0_metadata":
        return t.select(base)
    if arm == "T1_hash":
        return t.select(base + ["prompt_sha256", "response_sha256"])
    src = "prompt_text_delta" if arm == "T2_delta" else "prompt_text_full"
    return t.select(base + [src, "response_text"]).rename_columns(base + ["prompt_text", "response_text"])


def col_bytes(path):
    md = pq.ParquetFile(path).metadata
    out, enc, codec = {}, {}, None
    for rg in range(md.num_row_groups):
        r = md.row_group(rg)
        for i in range(r.num_columns):
            c = r.column(i)
            out[c.path_in_schema] = out.get(c.path_in_schema, 0) + c.total_compressed_size
            if c.path_in_schema == "prompt_text" or (codec is None):
                enc[c.path_in_schema] = sorted(set(map(str, c.encodings)))
                codec = c.compression
    return out, md.num_row_groups, codec, enc.get("prompt_text")


def run_parquet(job):
    name, arm = job
    t = load(name)
    meta = json.load(open(os.path.join(DATA, name + ".json")))
    tok = int(pc.sum(t["message_context__total_tokens"]).as_py())
    at = arm_table(t, arm)
    rows = []
    perm = np.random.default_rng(4242).permutation(at.num_rows)
    d = tempfile.mkdtemp(dir=WORK)
    # raw JSONL reference (order-independent)
    jsonl = sum(len(json.dumps(r, default=str)) + 1 for r in at.to_pylist())
    for order in ["session_sorted", "random"]:
        ot = at if order == "session_sorted" else at.take(perm)
        for vname, v in VARIANTS.items():
            if vname == "zstd_default_page8m" and not (arm == "T3_full" and order == "session_sorted"):
                continue
            kw = dict(COMMON)
            kw.update({k: val for k, val in v.items() if k != "nodict_text"})
            if v.get("nodict_text"):
                kw["use_dictionary"] = [c for c in ot.column_names if c not in ("prompt_text", "response_text")]
            p = os.path.join(d, f"{order}-{vname}.parquet")
            pq.write_table(ot, p, **kw)
            size = os.path.getsize(p)
            cb, nrg, codec, enc = col_bytes(p)
            text_bytes = sum(cb.get(c, 0) for c in ("prompt_text", "response_text", "prompt_sha256", "response_sha256"))
            rows.append(dict(corpus=name, tier=name.split("-")[0], corpus_kind=name.split("-")[1],
                             seed=int(name.rsplit("s", 1)[1]), arm=arm, order=order, variant=vname,
                             rows=at.num_rows, billed_tokens=tok, file_bytes=size,
                             bytes_per_mtok=size / tok * 1e6, bytes_per_record=size / at.num_rows,
                             text_col_bytes=text_bytes, text_share=text_bytes / sum(cb.values()),
                             col_bytes=cb, row_groups=nrg, codec_read_back=codec,
                             prompt_text_encodings=enc, jsonl_bytes=jsonl,
                             jsonl_bytes_per_mtok=jsonl / tok * 1e6, users=meta["users"]))
            os.remove(p)
    shutil.rmtree(d)
    return rows


def run_iceberg(job):
    name, arm = job
    from pyiceberg.catalog.sql import SqlCatalog
    t = arm_table(load(name), arm)
    tok = int(pc.sum(t["message_context__total_tokens"]).as_py())
    d = tempfile.mkdtemp(dir=WORK)
    cat = SqlCatalog("lab", uri=f"sqlite:///{d}/cat.db", warehouse=f"file://{d}/wh")
    cat.create_namespace("r6")
    out = []
    props_sets = {
        "iceberg_default": {},
        "iceberg_parity_zstd_default": {"write.parquet.compression-codec": "zstd",
                                         "write.parquet.row-group-limit": "1048576",
                                         "write.parquet.page-size-bytes": "1048576",
                                         "write.parquet.dict-size-bytes": "1048576",
                                         # pyiceberg passes write_batch_size=20000 by default vs pyarrow's 1024;
                                         # that sets page boundaries, so parity needs it pinned (found in smoke test)
                                         "write.parquet.page-row-limit": "1024"},
    }
    for pname, props in props_sets.items():
        tb = cat.create_table(f"r6.{pname}", schema=t.schema, properties=props)
        tb.append(t)
        root = os.path.join(d, "wh")
        data_files = [p for p in glob.glob(f"{root}/**/*.parquet", recursive=True) if f"/{pname}/" in p]
        meta_files = [p for p in glob.glob(f"{root}/**/*", recursive=True)
                      if os.path.isfile(p) and f"/{pname}/" in p and "/metadata/" in p]
        data_b = sum(os.path.getsize(p) for p in data_files)
        meta_b = sum(os.path.getsize(p) for p in meta_files)
        md = pq.ParquetFile(data_files[0]).metadata
        c0 = md.row_group(0).column(0)
        out.append(dict(corpus=name, tier=name.split("-")[0], corpus_kind=name.split("-")[1],
                        seed=int(name.rsplit("s", 1)[1]), arm=arm, order="session_sorted", variant=pname,
                        billed_tokens=tok, data_bytes=data_b, metadata_bytes=meta_b, n_data_files=len(data_files),
                        data_bytes_per_mtok=data_b / tok * 1e6,
                        total_bytes_per_mtok=(data_b + meta_b) / tok * 1e6,
                        codec_read_back=c0.compression, row_groups=md.num_row_groups,
                        writer=md.created_by, props=props))
    # exploratory: plain pyarrow Parquet with pyiceberg's default write_batch_size, to isolate that knob
    p = os.path.join(d, "plain_wbs20000.parquet")
    pq.write_table(t, p, compression="zstd", write_batch_size=20000, **COMMON)
    out.append(dict(corpus=name, tier=name.split("-")[0], corpus_kind=name.split("-")[1],
                    seed=int(name.rsplit("s", 1)[1]), arm=arm, order="session_sorted",
                    variant="EXPLORATORY_plain_parquet_zstd_default_wbs20000", billed_tokens=tok,
                    data_bytes=os.path.getsize(p), metadata_bytes=0, data_bytes_per_mtok=os.path.getsize(p) / tok * 1e6,
                    total_bytes_per_mtok=os.path.getsize(p) / tok * 1e6))
    shutil.rmtree(d)
    return out


def run_dict(job):
    tier, kind, seed = job
    name = f"{tier}-{kind}-s{seed}"
    t = feather.read_table(os.path.join(DATA, name + ".arrow"))
    h = feather.read_table(os.path.join(DATA, f"{tier}-{kind}-s99.arrow"))
    tok = int(pc.sum(t["message_context.total_tokens"]).as_py())
    out = []
    for col in ["prompt_text_delta", "prompt_text_full"]:
        held = [s.encode() for s in h[col].to_pylist()]
        rng = np.random.default_rng(7)
        idx = rng.permutation(len(held))
        samples, total = [], 0
        for i in idx:  # cap the training set at ~32 MB of held-out text
            if total > 32_000_000:
                break
            samples.append(held[i]); total += len(held[i])
        dct = zstd.train_dictionary(112_640, samples, level=3)
        plain = zstd.ZstdCompressor(level=3)
        withd = zstd.ZstdCompressor(level=3, dict_data=dct)
        vals = [s.encode() for s in t[col].to_pylist()]
        raw = sum(map(len, vals))
        b_plain = sum(len(plain.compress(v)) for v in vals)
        b_dict = sum(len(withd.compress(v)) for v in vals)
        out.append(dict(corpus=name, tier=tier, corpus_kind=kind, seed=seed, column=col, rows=len(vals),
                        billed_tokens=tok, raw_bytes=raw, per_record_zstd3=b_plain,
                        per_record_zstd3_dict=b_dict, dict_bytes=len(dct.as_bytes()),
                        dict_gain=b_plain / b_dict, train_samples=len(samples), train_bytes=total))
    return out


def corpus_stats(name):
    t = feather.read_table(os.path.join(DATA, name + ".arrow"))
    blob = ("\n".join(t["prompt_text_delta"].to_pylist()) + "\n".join(t["response_text"].to_pylist())).encode()
    c = zstd.ZstdCompressor(level=3).compress(blob)
    meta = json.load(open(os.path.join(DATA, name + ".json")))
    meta.update(delta_plus_response_raw_bytes=len(blob), zstd3_ratio_raw_text=len(blob) / len(c),
                text_sha256=hashlib.sha256(blob).hexdigest())
    return meta


def main():
    os.makedirs(RES, exist_ok=True); os.makedirs(WORK, exist_ok=True)
    names = sorted(os.path.basename(p)[:-6] for p in glob.glob(os.path.join(DATA, "*.arrow")) if not p.endswith("s99.arrow"))
    what = sys.argv[1:] or ["corpus", "parquet", "iceberg", "dict"]
    with ProcessPoolExecutor(max_workers=10) as ex:
        if "corpus" in what:
            with open(os.path.join(RES, "corpus.jsonl"), "w") as f:
                for m in ex.map(corpus_stats, names):
                    f.write(json.dumps(m) + "\n")
        if "parquet" in what:
            jobs = [(n, a) for n in names for a in ARMS]
            jobs.sort(key=lambda j: j[1] != "T3_full")  # start the slow ones first
            with open(os.path.join(RES, "parquet.jsonl"), "w") as f:
                for rows in ex.map(run_parquet, jobs):
                    for r in rows:
                        f.write(json.dumps(r) + "\n")
                    f.flush(); print("parquet", rows[0]["corpus"], rows[0]["arm"], flush=True)
        if "iceberg" in what:
            jobs = [(n, a) for n in names for a in ARMS]
            with open(os.path.join(RES, "iceberg.jsonl"), "w") as f:
                for rows in ex.map(run_iceberg, jobs):
                    for r in rows:
                        f.write(json.dumps(r) + "\n")
                    print("iceberg", rows[0]["corpus"], rows[0]["arm"], flush=True)
        if "dict" in what:
            jobs = [(t, k, s) for t in ["coding", "chat"] for k in ["real", "high_entropy"] for s in [0, 1, 2]]
            with open(os.path.join(RES, "dict.jsonl"), "w") as f:
                for rows in ex.map(run_dict, jobs):
                    for r in rows:
                        f.write(json.dumps(r) + "\n")
                    print("dict", rows[0]["corpus"], flush=True)


if __name__ == "__main__":
    main()

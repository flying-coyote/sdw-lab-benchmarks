"""v2 config surface (Measure 2), image footprint (part of Measure 1) and the engine-specific
SQL sub-measure of platform dependence (Measure 5c), for all four arms.

Config LOC uses July's frozen counter unchanged (measure_complexity.count_loc: non-blank,
non-comment, Python docstrings stripped) and July's bucket rule. B and S file lists are
July's exactly. F: compose service, SQL program, deploy script (the pipeline's runtime
config is inline in the deploy script; HTTP ingress/egress need no connector config).
BC: B's job file plus its Dockerfile and compose file.

Image bytes, two bases, because this daemon uses the containerd image store
(driver-type io.containerd.snapshotter.v1): `docker image inspect .Size` (the July basis)
reports the image's content size, which for apache/kafka:4.3.1 is 238,880,881 bytes
while the unpacked on-disk size `docker system df -v` reports is 686 MB. Both are recorded.

Engine-specific SQL lines (5c): one uniform rule for every arm, a detection line counts if
it contains any construct named in the pre-reg for any engine (WATERMARK FOR, TUMBLE,
LATENESS, emit_final, append_only, DuckDB floor-division windowing `//`). Denominator is the
arm's detection SQL LOC (July counter); for B the SQL text inside batch_job.py.
"""

import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from measure_complexity import BATCH_FILES, STREAM_FILES, config_surface, count_loc  # noqa: E402

FELDERA_FILES = {
    "compose_orchestration": ["feldera/docker-compose.yml"],
    "engine_config": [],
    "job_and_scheduler": ["feldera/detection.sql", "feldera/deploy_pipeline.sh"],
}
BC_FILES = {
    "compose_orchestration": ["bc/docker-compose.yml", "bc/Dockerfile.batch"],
    "engine_config": [],
    "job_and_scheduler": ["batch/batch_job.py"],
}
IMAGES = {
    "S": ["apache/kafka:4.3.1", "smx-flink-kafka:2.2.1"],
    "F": ["images.feldera.com/feldera/pipeline-manager@sha256:3dae7d8285a7c4e50b3761952543560f427544fec57f0167c621ce606e9ae0fc"],
    "BC": ["smx-bc-batch:v2"],
    "B": [],
}
CONSTRUCT_RE = re.compile(r"WATERMARK\s+FOR|TUMBLE|LATENESS|emit_final|append_only|//\s*\{?WINDOW_SECONDS|//\s*60",
                          re.IGNORECASE)


def image_bytes():
    df = json.loads(subprocess.run(["docker", "system", "df", "-v", "--format", "{{json .Images}}"],
                                   capture_output=True, text=True).stdout)
    by_id = {}
    for i in df:
        by_id.setdefault(i["ID"], i)
    out = {}
    for arm, imgs in IMAGES.items():
        rows = []
        for img in imgs:
            ins = subprocess.run(["docker", "image", "inspect", img, "--format", "{{.Id}} {{.Size}}"],
                                 capture_output=True, text=True).stdout.split()
            iid, size = ins[0], int(ins[1])
            rows.append({"image": img, "id": iid, "inspect_size_bytes_july_basis": size,
                         "unpacked_disk_size_docker_system_df": by_id.get(iid, {}).get("Size")})
        out[arm] = {"images": rows, "n_distinct_images": len(rows),
                    "total_inspect_size_bytes_july_basis": sum(r["inspect_size_bytes_july_basis"] for r in rows)}
    return out


def detection_lines(path, sql_only_block=None):
    lines = open(path).read().splitlines()
    if sql_only_block:
        a, b = sql_only_block
        lines = lines[a:b]
    code = [ln for ln in lines if ln.strip() and not ln.strip().startswith(("--", "#"))]
    hits = [ln.strip() for ln in code if CONSTRUCT_RE.search(ln)]
    return {"detection_sql_loc": len(code), "engine_specific_lines": len(hits),
            "pct": round(100.0 * len(hits) / len(code), 1) if code else None, "lines": hits}


def main():
    rep = {"config_surface": {
        "B": config_surface(ROOT, BATCH_FILES), "S": config_surface(ROOT, STREAM_FILES),
        "F": config_surface(ROOT, FELDERA_FILES), "BC": config_surface(ROOT, BC_FILES)}}
    b = rep["config_surface"]["B"]["total_loc"]
    rep["config_ratio_to_B"] = {k: round(v["total_loc"] / b, 2) for k, v in rep["config_surface"].items()}
    rep["images"] = image_bytes()
    bj = open(os.path.join(ROOT, "batch", "batch_job.py")).read().splitlines()
    start = next(i for i, ln in enumerate(bj) if "rows = con.execute" in ln) + 1
    end = next(i for i in range(start, len(bj)) if '""").fetchall()' in bj[i])
    rep["engine_specific_sql"] = {
        "rule": "line counts if it contains any pre-reg-named construct (WATERMARK FOR, TUMBLE, LATENESS, "
                "emit_final, append_only, DuckDB // floor-division windowing); same rule every arm",
        "B": detection_lines(os.path.join(ROOT, "batch", "batch_job.py"), (start, end)),
        "BC": detection_lines(os.path.join(ROOT, "batch", "batch_job.py"), (start, end)),
        "S": detection_lines(os.path.join(ROOT, "streaming", "flink_job.sql")),
        "F": detection_lines(os.path.join(ROOT, "feldera", "detection.sql")),
    }
    out = os.path.join(ROOT, "results", "v2", "complexity-v2.json")
    json.dump(rep, open(out, "w"), indent=2)
    for a in ("B", "S", "F", "BC"):
        print(a, "LOC", rep["config_surface"][a]["total_loc"], "ratio", rep["config_ratio_to_B"][a],
              "images", rep["images"][a]["total_inspect_size_bytes_july_basis"],
              "eng-specific", rep["engine_specific_sql"][a]["engine_specific_lines"], "/",
              rep["engine_specific_sql"][a]["detection_sql_loc"])


if __name__ == "__main__":
    main()

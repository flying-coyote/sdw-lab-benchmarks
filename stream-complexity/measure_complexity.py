"""Measure 1 (moving parts) + Measure 2 (config surface) from the pre-reg. Writes
results/complexity.json.

Moving parts is a LIVE snapshot (docker ps + host ps), not a static count from reading
the compose file — run this while both arms are actually running (run_clean_trial.sh
does) or the counts will just read as zero and say so honestly, rather than silently
reporting the "designed" topology as if it were observed.

Config LOC inclusion rule (pre-reg Measure 2: "compose + engine config + job
definition + scheduler", stated here because the deliverable requires it be stated in
the output): a file is counted under exactly one bucket —

  compose_orchestration  the running topology's definition: docker-compose.yml and any
                         Dockerfile that builds a custom engine image referenced by it.
  engine_config          config/provisioning that is NOT the detection logic itself
                         (e.g. topic creation/partitioning).
  job_and_scheduler      the detection query/logic, AND whatever causes it to run
                         repeatedly or continuously (a scheduler loop, or a one-shot
                         submission into an always-on engine).

Corpus generation and replay/producer/consumer harness scripts (gen_corpus.py,
batch/land_microbatches.py, streaming/producer.py, streaming/consume_alerts.py) are
EXCLUDED — they are test-harness machinery common to feeding both arms, not part of
either arm's deployed operational config surface. LOC counting strips blank lines,
full-line `#`/`--`/`//` comments, and — for .py files specifically — module/function/
class docstring literals (via `ast`, see `_python_docstring_lines`; without this,
batch_job.py's documentation would count as "code" while the YAML/SQL/shell files'
`#`/`--` comments on the streaming side would not, unfairly inflating the batch
count for the sin of being well-commented). It does NOT strip inline trailing
comments or non-docstring multi-line strings — a known, stated limitation of a
line-count proxy, not a hidden one.
"""

import argparse
import ast
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUT = os.path.join(HERE, "results", "complexity.json")

INCLUSION_RULE = (
    "Config LOC = non-blank, non-full-line-comment lines (plus, for .py files, "
    "docstring literals also stripped via ast — otherwise Python's documentation "
    "would count as code while YAML/SQL/shell '#'/'--' comments would not) in files "
    "bucketed by primary purpose: compose_orchestration (docker-compose.yml + "
    "Dockerfiles building a custom engine image), engine_config (provisioning/config "
    "that is not the detection logic itself, e.g. topic creation), job_and_scheduler "
    "(the detection query/logic plus whatever causes it to run repeatedly/"
    "continuously). Corpus generation and replay/producer/consumer harness scripts "
    "are EXCLUDED as test-harness machinery common to both arms, not either arm's "
    "deployed operational config surface."
)

BATCH_FILES = {
    "job_and_scheduler": [
        "batch/batch_job.py",
    ],
}

STREAM_FILES = {
    "compose_orchestration": [
        "streaming/docker-compose.yml",
        "streaming/Dockerfile.flink",
    ],
    "engine_config": [
        "streaming/init-topics.sh",
    ],
    "job_and_scheduler": [
        "streaming/flink_job.sql",
        "streaming/submit_flink_job.sh",
    ],
}

COMMENT_PREFIXES = ("#", "--", "//")


def _python_docstring_lines(src):
    """Line numbers (1-indexed) covered by a module/function/class docstring literal.
    Needed because the plain comment-prefix heuristic below only strips '#'-style
    line comments — it would otherwise count every line of a Python module's
    triple-quoted docstring as "code", unfairly inflating batch_job.py's LOC just
    for being well-documented relative to the YAML/SQL/shell files on the streaming
    side, where '#'/'--' line comments (already stripped) are the natural doc form."""
    lines = set()
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return lines
    nodes = [tree] + [n for n in ast.walk(tree)
                      if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
    for node in nodes:
        body = getattr(node, "body", None)
        if not body:
            continue
        first = body[0]
        if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)):
            start = first.lineno
            end = getattr(first, "end_lineno", start)
            lines.update(range(start, end + 1))
    return lines


def count_loc(path):
    if not os.path.exists(path):
        return None
    with open(path) as f:
        raw_lines = f.readlines()
    skip = _python_docstring_lines("".join(raw_lines)) if path.endswith(".py") else set()
    n = 0
    for i, line in enumerate(raw_lines, start=1):
        if i in skip:
            continue
        s = line.strip()
        if not s:
            continue
        if s.startswith(COMMENT_PREFIXES):
            continue
        n += 1
    return n


def config_surface(root, file_map):
    buckets = {}
    total = 0
    for bucket, files in file_map.items():
        entries = []
        for rel in files:
            abs_path = os.path.join(root, rel)
            loc = count_loc(abs_path)
            entries.append({"file": rel, "loc": loc, "exists": loc is not None})
            total += loc or 0
        buckets[bucket] = entries
    return {"buckets": buckets, "total_loc": total}


def docker_ps(name_filter):
    """Live snapshot: running containers whose name matches a substring filter."""
    try:
        out = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}|{{.Image}}|{{.Status}}"],
            capture_output=True, text=True, timeout=15, check=True,
        ).stdout
    except Exception as e:  # noqa: BLE001 - docker unavailable is a valid, reportable state
        return None, str(e)
    rows = []
    for line in out.splitlines():
        parts = line.split("|")
        if len(parts) != 3:
            continue
        name, image, status = parts
        if name_filter in name:
            rows.append({"name": name, "image": image, "status": status})
    return rows, None


def docker_image_sizes(image_names):
    out = {}
    for img in sorted(set(image_names)):
        try:
            size = subprocess.run(
                ["docker", "image", "inspect", img, "--format", "{{.Size}}"],
                capture_output=True, text=True, timeout=15, check=True,
            ).stdout.strip()
            out[img] = int(size)
        except Exception:
            out[img] = None
    return out


def host_processes(pattern):
    """Live snapshot of host processes matching a substring (e.g. 'batch_job.py')."""
    try:
        out = subprocess.run(["ps", "-eo", "pid,args"], capture_output=True, text=True,
                              timeout=15, check=True).stdout
    except Exception as e:  # noqa: BLE001
        return None, str(e)
    rows = []
    for line in out.splitlines()[1:]:
        line = line.strip()
        if not line:
            continue
        pid, _, args = line.partition(" ")
        if pattern in args and "grep" not in args and int(pid) != os.getpid():
            rows.append({"pid": int(pid), "args": args[:200]})
    return rows, None


def measure_moving_parts():
    batch_containers = []  # batch never launches a container, by design (see note below)
    stream_containers, stream_err = docker_ps("smx-")
    # smx-kafka-data-init / smx-flink-checkpoints-init / smx-topic-init are one-shot and
    # exit immediately; `docker ps` (running only, not -a) naturally excludes them once
    # done, which is correct — they are not standing moving parts at steady state.

    # gen_corpus.py / batch/land_microbatches.py / streaming/producer.py are the
    # replay/ingest HARNESS — a stand-in for whatever upstream source (log shipper,
    # EDR agent, syslog relay) would feed either arm in a real deployment, symmetric
    # across arms, and deliberately excluded here for the same reason they're excluded
    # from the config-LOC measure. batch_job.py (job + scheduler + its own sink, all in
    # one) and consume_alerts.py (the streaming arm's sink, per the task brief: "count
    # it as a moving part honestly") DO count — they're each arm's own architecture.
    batch_procs, bp_err = host_processes("batch_job.py")
    stream_procs, _ = host_processes("streaming/consume_alerts.py")

    images = list({c["image"] for c in (stream_containers or [])})
    image_sizes = docker_image_sizes(images)

    return {
        "batch": {
            "containers": batch_containers or [],
            "n_containers": len(batch_containers or []),
            "host_processes": batch_procs or [],
            "n_host_processes": len(batch_procs or []),
            "note": "batch is deliberately containerless (bare python process + files, "
                    "per the pre-reg); n_containers=0 is the designed result, not a "
                    "measurement gap.",
        },
        "stream": {
            "containers": stream_containers or [],
            "n_containers": len(stream_containers or []),
            "distinct_images": images,
            "n_distinct_images": len(images),
            "image_sizes_bytes": image_sizes,
            "host_processes": stream_procs,
            "n_host_processes": len(stream_procs),
        },
        "ratio_containers_plus_processes": (
            None if not (batch_containers or batch_procs)
            else round((len(stream_containers or []) + len(stream_procs)) /
                       max(1, len(batch_containers or []) + len(batch_procs or [])), 2)
        ),
        "docker_error": stream_err,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args()

    report = {
        "inclusion_rule": INCLUSION_RULE,
        "moving_parts": measure_moving_parts(),
        "config_surface": {
            "batch": config_surface(HERE, BATCH_FILES),
            "stream": config_surface(HERE, STREAM_FILES),
        },
    }
    batch_loc = report["config_surface"]["batch"]["total_loc"]
    stream_loc = report["config_surface"]["stream"]["total_loc"]
    report["config_surface"]["ratio_stream_to_batch"] = (
        round(stream_loc / batch_loc, 2) if batch_loc else None
    )

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(report, f, indent=2, sort_keys=True)

    mp = report["moving_parts"]
    print(f"moving parts: batch={mp['batch']['n_containers']} containers + "
          f"{mp['batch']['n_host_processes']} host processes | "
          f"stream={mp['stream']['n_containers']} containers + "
          f"{mp['stream']['n_host_processes']} host processes")
    print(f"config LOC: batch={batch_loc}  stream={stream_loc}  "
          f"ratio={report['config_surface']['ratio_stream_to_batch']}")
    print(f"report written -> {args.out}")


if __name__ == "__main__":
    main()

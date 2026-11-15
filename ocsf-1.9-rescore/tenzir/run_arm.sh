#!/usr/bin/env bash
# ocsf-1.9-rescore arm (d): run Tenzir's shipped zeek mapping over the pinned corpus.
# Usage: run_arm.sh <image> <library-sha> <library-extract-dir> <label>
#   image e.g. tenzir/tenzir:v6.22.0 (pinned digest in PREREGISTRATION.md); library fetched as a
#   codeload tarball at <library-sha> and extracted to <library-extract-dir> (outside the repo).
# The library is copied into a named Docker volume with `docker cp` (Docker Desktop does not share the
# WSL /tmp scratchpad, and the image has no tar), then run with --network none and read-only mounts.
set -euo pipefail
IMG="$1"; SHA="$2"; LIBDIR="$3"; LABEL="$4"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; ROOT="$(dirname "$HERE")"
WORK="$(dirname "$ROOT")/pipeline-normalization-fidelity/_work"
VOL="sdw-tzlib-${SHA:0:8}"
docker volume rm "$VOL" >/dev/null 2>&1 || true
docker volume create "$VOL" >/dev/null
C=$(docker create -v "$VOL":/library --entrypoint sh "$IMG"); docker cp -q "$LIBDIR"/. "$C":/library/; docker rm "$C" >/dev/null
docker run --rm --network none -v "$VOL":/library:ro --entrypoint sh "$IMG" -c 'test -f /library/zeek/package.yaml'
OUT="$ROOT/results/tenzir_${SRC:-zeek_conn}.${LABEL}.emitted.jsonl"
docker run --rm --network none -v "$VOL":/library:ro -v "$WORK":/work:ro -v "$HERE/${TQL:-map_zeek_conn.tql}":/q.tql:ro \
  --entrypoint tenzir "$IMG" --package-dirs=/library -f /q.tql > "$OUT" 2> "$ROOT/results/tenzir_${SRC:-zeek_conn}.${LABEL}.stderr.txt"
echo "wrote $OUT ($(wc -l < "$OUT") lines) sha256 $(sha256sum "$OUT" | cut -d' ' -f1)"
docker volume rm "$VOL" >/dev/null

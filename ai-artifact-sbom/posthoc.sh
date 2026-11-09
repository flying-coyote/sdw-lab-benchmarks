#!/usr/bin/env bash
# Post-hoc, labelled exploratory runs (not pre-registered). Every command logged by bash -x.
set -euxo pipefail
D=/tmp/claude-1000/lab-ai-research/ai-artifact-sbom; B=$D/tools/bin; O=$D/results/posthoc
export SYFT_CHECK_FOR_APP_UPDATE=false TRIVY_CACHE_DIR=$D/cache/trivy
E1=$D/fixtures-posthoc/E1-mcp-config
for r in 1 2 3; do
  $D/.venv/bin/ai-bom scan $E1 -f cyclonedx -q --no-color -o $O/E1-aibom-run$r.json
  $B/syft scan dir:$E1 -q -o syft-json=$O/E1-syft-run$r.json
  $B/trivy fs -q --skip-db-update --list-all-pkgs --format json -o $O/E1-trivy-run$r.json $E1
  # E2: Syft with every file hashed (non-default: file.metadata.selection=all)
  for fx in mcp-npm variants/V5 mcp-pip variants/V7 vscode variants/V8 ollama-store variants/V3; do
    n=$(echo $fx | tr / _)
    SYFT_FILE_METADATA_SELECTION=all $B/syft scan dir:$D/fixtures/$fx -q -o syft-json=$O/E2-syft-all-$n-run$r.json
  done
done

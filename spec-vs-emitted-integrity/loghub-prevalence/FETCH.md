---
type: reference
title: "LogHub Corpus Fetch — Reproducible Download Script for Spec-vs-Emitted Integrity Benchmark"
created: 2026-06-17
tags: [loghub, corpus, reproducibility, runbook, spec-vs-emitted, integrity]
---

# Corpus fetch (reproducible) — LogHub real-production-log samples

Raw logs are NOT committed (public research corpus; reproducible). Fetch:

```bash
mkdir -p raw && cd raw
for sys in Apache Linux OpenSSH HDFS Zookeeper Proxifier; do
  curl -s -o "$sys.log" "https://raw.githubusercontent.com/logpai/loghub/master/$sys/${sys}_2k.log"
done
```

Then: `python3 loghub_prevalence.py`. Per-system corpus_sha16 fingerprints are recorded in
`results/loghub_prevalence.json` to pin the exact corpus a result depends on.

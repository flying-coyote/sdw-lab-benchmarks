# EDR/Sysmon Data Generation Plan

**Status:** spec (2026-05-24). Implementation pending.

## Building blocks (all free / open-source)

| Component | Purpose | Source |
|---|---|---|
| Windows VM (10/11 or Server 2019+) | Endpoint target for techniques | Generic Windows install |
| Sysmon | Endpoint telemetry collector | Microsoft Sysinternals (free) |
| SwiftOnSecurity Sysmon config | Production-tuned event filter | github.com/SwiftOnSecurity/sysmon-config (Tier C, community) |
| Atomic Red Team | Adversary-emulation technique runner | github.com/redcanaryco/atomic-red-team (Apache 2.0) |
| Invoke-AtomicRedTeam | PowerShell driver for Atomic Red Team | github.com/redcanaryco/invoke-atomicredteam |
| Winlogbeat or NXLog | Event-log forwarder | Open-source agents |
| OCSF normalizer | Sysmon → OCSF Process / File / Network Activity classes | Built alongside (extend the zeek-to-ocsf-mapping library pattern) |

## Pipeline

```
Windows VM (Sysmon + SwiftOnSecurity config)
        │
        ▼
Invoke-AtomicRedTeam executes techniques
        │
        ▼  Sysmon writes events to Windows Event Log
        │
        ▼  Winlogbeat / NXLog forwards as JSON
        │
        ▼  OCSF normalizer maps to Process Activity (1007),
        │  File System Activity (1001), Network Activity (4001),
        │  Module Activity (1005), Registry Key Activity (201001)
        │
        ▼  Substrate ingest (ClickHouse / Iceberg / candidate-under-test)
```

## Volume targets

- Baseline (idle Windows VM with Sysmon installed): ~10 events/sec
- Atomic Red Team active execution: bursts to 1K–5K events/sec during technique runs
- For sustained-ingest benchmark: replay captured Atomic Red Team event streams in loop, scaled to target rate (10K–100K events/sec)
- For methodology variety: rotate technique sets across runs (initial-access set, persistence set, lateral-movement set) to avoid pathological cardinality

## Corpus generation method

Two paths, both kept:

1. **Live capture** — Atomic Red Team runs against a live VM; Sysmon events captured in real time. Lower throughput, higher fidelity. Use for spec / smoke runs.
2. **Replay** — capture once, replay-at-scale. Use a replay tool (or simple `jq` + timing script) to drive a target ingest rate. Use for sustained-throughput benchmark runs.

The corpus itself (JSON event stream, OCSF-normalized) ships under NDA per the leverage-trio publication strategy.

## ATT&CK coverage selection

Atomic Red Team covers 261 ATT&CK techniques. For substrate benchmarking, **coverage breadth doesn't matter** — what matters is that the technique mix exercises representative event types:

- ≥3 techniques producing high `process_create` rates
- ≥3 techniques producing high `file_write` rates
- ≥2 techniques producing high `network_connect` rates
- ≥2 techniques producing registry / image-load rates

The exact technique IDs picked are noted in `results/run-manifests/` per run. The point is *representative cardinality and event-type mix*, not threat coverage.

## OCSF mapping strategy

Extend the existing `~/project1/02-projects/zeek-to-ocsf-mapping/` pattern. Build a sibling library — `sysmon-to-ocsf-mapping/` or generalize the existing one — that takes Sysmon JSON (from Winlogbeat) and emits OCSF-conformant records for the relevant classes:

- Sysmon Event ID 1 (Process Create) → OCSF Process Activity (1007) `activity_id: 1 (Launch)`
- Sysmon Event ID 11 (FileCreate) → OCSF File System Activity (1001) `activity_id: 1 (Create)`
- Sysmon Event ID 3 (Network Connect) → OCSF Network Activity (4001)
- Sysmon Event ID 7 (Image Load) → OCSF Module Activity (1005)
- Sysmon Event ID 13 (RegistryEventValueSet) → OCSF Registry Key Activity (201001)

Other Sysmon event types map secondarily. Document mapping decisions per event type in `data/ocsf-mapping.md` (TBD).

## Caveats to document

- SwiftOnSecurity config makes opinionated filtering choices — what's *not* in the corpus matters as much as what is; document the filter posture
- Atomic Red Team techniques fire detection rules; the corpus is *not* threat-free — substrate teams should not use it for production rule-testing without understanding that
- Replay scaling is synthetic — sustained 100K events/sec from replay does not equal sustained 100K events/sec from 100K real endpoints. The ingest path is what's being tested, not the endpoint population.

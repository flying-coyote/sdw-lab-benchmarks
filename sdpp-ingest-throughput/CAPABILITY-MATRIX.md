# SDPP Ingest Throughput Benchmark — Capability & Limitations Matrix

*Last updated: 2026-06-08. Throughput numbers are measured separately in `run.py` / `results/`. This document covers the qualitative layer: what each tool can and cannot do, which modes are fair to run per tool, and where the real constraints live.*

---

## 1. Category Overview

**Security Data Pipeline Platforms (SDPP)** are the processing layer between raw telemetry sources (syslog daemons, agents, cloud APIs) and storage/SIEM destinations. The benchmark spans two sub-populations with different testing rules:

**Runnable OSS pipelines** — self-hostable, locally benchmarkable, no license gate on throughput:
Vector, Tenzir, rsyslog, syslog-ng OSE + AxoSyslog fork, Fluent Bit, Fluentd, OpenTelemetry Collector, Grafana Alloy, Logstash, NXLog CE.

**Commercial / SaaS (documented-reference only)** — vendor-stated capabilities, no controlled throughput run possible without a production-scale deployment and billing agreement:
Cribl Stream/Edge, Observo AI (now SentinelOne Data Pipelines, acquired Sept 2025), Edge Delta, Onum (now CrowdStrike Falcon, acquired Aug 2025), DataBahn, Monad (acquired Tarsal June 2025), Abstract Security, Splunk Edge Processor / Ingest Actions.

**Proprietary-but-free agent (installable, ecosystem-gated)** — the **Splunk Universal Forwarder** sits in its own category: free to run and locally installable, but a *forwarder*, not a transform pipeline (output is Splunk's S2S protocol, transform is minimal, no parse). It's included for completeness as a documented/limited-runnable reference; its natural metric is forwarding throughput to an indexer (not the read→filter→sink modes the OSS pipelines run), and because it is Splunk software, publishing its numbers falls under the same Splunk EULA the project applies to SIEM benchmarks.

**Category consolidations since 2024:**
- **Observo AI → SentinelOne**: $225M acquisition announced Sept 8 2025; now marketed as "SentinelOne Data Pipelines." [source: SentinelOne press release, 2025-09-08]
- **Onum → CrowdStrike Falcon NG SIEM**: acquisition announced Aug 27 2025; Onum's pipeline detection integrated into Falcon. [source: CrowdStrike press release, 2025-08-27]
- **Monad + Tarsal**: Monad (SaaS security pipeline) acquired Tarsal (YC S21, pre-built SaaS connector ETL) June 23 2025. Combined platform retains the Monad brand. [source: Monad blog, 2025]

---

## 2. Capability Tables

Tables are split across three themes to stay readable. Cells use ✓ (full), ~ (partial / needs config), ✗ (absent/not supported), and a brief qualifier.

### 2a. Runtime / License / Deployment

| Tool | Language / Runtime | Idle Memory | License | Usage Gate | Deployment Model |
|------|-------------------|-------------|---------|------------|-----------------|
| **Vector** | Rust | ~10–30 MB | MPL-2.0 (OSS-OSI) | None | Single static binary; no control plane |
| **Tenzir** | C++ (Node binary) | ~50–200 MB (enrichment tables add more) | BSD-3-Clause (Node OSS) + proprietary (Platform/App) | Community Edition free; Enterprise for control plane, fleet, platform | Binary + optional Platform SaaS; Docker recommended |
| **rsyslog** | C | ~3–10 MB | GPLv3 (core); LGPL (runtime lib) | None | Single daemon; Linux/Unix native; Windows via commercial Windows Agent (Adiscon) |
| **syslog-ng OSE** | C (Python/Java/Lua/Perl plugins) | ~5–15 MB | LGPL-2.1 core + GPL-2 modules | None for OSE | Single daemon; Linux/Unix only (OSE) |
| **AxoSyslog** | C (same base as syslog-ng) | ~5–15 MB | GPL-3.0-or-later (as of v4.12) | None | Single daemon; Linux/containers; no native Windows |
| **Fluent Bit** | C | ~450 KB – 1 MB | Apache 2.0 | None | Single static binary; Linux/Windows/macOS/containers |
| **Fluentd** | Ruby (C extensions) | 30–60 MB+ (plugin-dependent) | Apache 2.0 | None | Ruby gem / daemon; Linux/Windows/macOS |
| **OTel Collector** | Go | ~50–100 MB | Apache 2.0 | None | Single binary (core/contrib distro); Linux/Windows/macOS |
| **Grafana Alloy** | Go (OTel Collector distro) | ~60–120 MB | Apache 2.0 | None | Single binary; Linux/Windows/macOS; component DAG architecture |
| **Logstash** | JVM (Ruby DSL + Java core) | 1–4 GB heap (default 1 GB; recommended 4 GB) | Apache 2.0 | None | JVM process; Linux/Windows/macOS; slow startup (~15–30s) |
| **NXLog CE** | C | ~5–20 MB | NXLog Public License (source-available, not OSI) | Cannot bundle CE into a product that depends on it; commercial license required then | Single binary; Linux + Windows (primary strength) |
| **Splunk Universal Forwarder** | C/C++ | ~100–200 MB | Proprietary (Splunk EULA); free to use | Free to forward, but locked to a Splunk indexer; download account-gated; publishing benchmarks is Splunk-EULA-sensitive | Per-host agent; forwards via S2S to indexers; optional Deployment Server control plane |
| | | | | | |
| **Cribl Stream** | Go (Workers) + Node.js (Leader) | N/A (SaaS / self-hosted) | Commercial; Free ≤1 TB/day | Free: 1 TB/day; Standard: ≤5 TB/day; Enterprise: unlimited | Distributed: Leader + Worker nodes (control plane required); single-instance option for low volume; self-hosted or Cribl.Cloud |
| **SentinelOne Data Pipelines** (fmr. Observo AI) | N/A (SaaS) | N/A | Commercial SaaS | Vendor pricing | SaaS with fleet management; no self-host |
| **Edge Delta** | N/A (SaaS + agent) | N/A | Commercial SaaS | Vendor pricing | SaaS control plane + lightweight on-host agent |
| **CrowdStrike Falcon (fmr. Onum)** | N/A (integrated into Falcon) | N/A | Commercial (Falcon licensing) | Falcon NG SIEM subscription | Integrated Falcon platform; no standalone |
| **DataBahn** | N/A (SaaS) | N/A | Commercial SaaS | Vendor pricing; $17M Series A (2025) | SaaS + Smart Edge agent; AWS Marketplace |
| **Monad (+Tarsal)** | N/A (SaaS) | N/A | Commercial SaaS; public beta: 1 TB/month free | Beta free tier; paid tiers undisclosed | SaaS; hybrid/on-prem option stated but not detailed |
| **Abstract Security** | N/A (SaaS) | N/A | Commercial SaaS | Vendor pricing; value-based (not volume-based) | Cloud-native composable SIEM layer |
| **Splunk Edge Processor** | Go (SPL2 engine) | N/A | Commercial (Splunk license) | Splunk Cloud / Enterprise license | Distributed: control plane (Splunk Cloud) + on-prem Edge Processor workers |

### 2b. Inputs / Outputs / Parsing

| Tool | Syslog (3164/5424) | File/tail | JSON/NDJSON | OTLP in | WinEvtLog | Kafka in | Cloud (S3/CloudTrail) | HTTP in | File/null out | Kafka out | Object store (S3/Iceberg) | HTTP/SIEM out | OTLP out | Native JSON parse | Grok/regex | Typed/structured |
|------|-------------------|-----------|-------------|---------|-----------|---------|----------------------|---------|--------------|-----------|--------------------------|--------------|---------|-------------------|------------|-----------------|
| **Vector** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ (S3, CloudWatch, many) | ✓ | ✓ | ✓ | ✓ (S3; no native Iceberg catalog) | ✓ (Splunk HEC, HTTP) | ✓ | ✓ | ✓ (VRL regex) | ✓ (VRL typed) |
| **Tenzir** | ✓ | ✓ | ✓ | ✓ | ~ (via Fluent Bit agent relay) | ✓ | ✓ (S3, Azure Blob) | ✓ | ✓ | ✓ | ✓ (Parquet/object store; no Iceberg catalog natively) | ✓ | ✓ | ✓ | ✓ | ✓ (Arrow-typed schema) |
| **rsyslog** | ✓ (native) | ✓ | ~ (requires mmjsonparse module) | ✗ | ✗ (Linux daemon; Windows Agent separate commercial product) | ✓ (omkafka) | ~ (S3 via omhttp/3rd party) | ~ (imhttp module) | ✓ | ✓ | ~ (S3 via plugin) | ✓ (omhttp) | ✗ | ~ (mmjsonparse; limited field-level filter) | ✓ (mmnormalize, regex) | ~ (typed via mmjsonparse) |
| **syslog-ng OSE** | ✓ (native) | ✓ | ~ (json-parser module) | ✗ | ✗ (OSE; Linux/Unix only) | ✓ | ~ (S3 via 3rd party) | ✓ (http source) | ✓ | ✓ | ~ (S3 via plugin) | ✓ | ✗ | ✓ (json-parser) | ✓ | ~ (typed via json-parser) |
| **AxoSyslog** | ✓ | ✓ | ✓ (FilterX native) | ✓ (OTLP source) | ✗ (no native Windows) | ✓ | ✓ (S3, GCS, BigQuery) | ✓ | ✓ | ✓ | ✓ (S3, ClickHouse) | ✓ (Splunk HEC, Loki, many) | ✓ | ✓ (FilterX) | ✓ | ✓ (FilterX typed) |
| **Fluent Bit** | ✓ | ✓ | ✓ | ✓ (native OTLP/HTTP+gRPC) | ✓ (winlog + winevtlog plugins) | ✓ | ✓ (S3, CloudWatch) | ✓ | ✓ | ✓ | ✓ (S3) | ✓ | ✓ | ✓ | ✓ | ✓ |
| **Fluentd** | ✓ | ✓ | ✓ | ~ (via plugin) | ~ (plugin; not native) | ✓ | ✓ (via plugins) | ✓ | ✓ | ✓ | ✓ (via plugins) | ✓ | ~ (via plugin) | ✓ | ✓ (1000+ plugins) | ✓ |
| **OTel Collector** | ~ (via receiver contrib) | ✓ (filelog receiver) | ✓ | ✓ (native) | ~ (windowseventlog receiver; contrib) | ✓ | ✓ (AWS, GCP receivers) | ✓ | ✓ | ✓ | ✓ (S3 exporter) | ✓ | ✓ | ✓ | ~ (via transform processor) | ~ (attribute typing) |
| **Grafana Alloy** | ~ (via OTel components) | ✓ (filelog receiver inherited) | ✓ | ✓ | ~ (via OTel windowseventlog) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ (Loki, S3) | ✓ | ✓ | ✓ | ~ (via OTel processors) | ~ |
| **Logstash** | ✓ | ✓ | ✓ | ~ (via contrib plugin) | ✓ | ✓ | ✓ (S3, Kinesis, Azure) | ✓ | ✓ | ✓ | ✓ (S3) | ✓ (200+ output plugins) | ~ | ✓ | ✓ (grok is native strength) | ✓ |
| **NXLog CE** | ✓ | ✓ | ✓ | ✗ | ✓ (primary use case; Windows native) | ~ (limited CE vs Enterprise) | ~ | ~ | ✓ | ~ (limited CE) | ✗ | ✓ (syslog fwd, HTTP) | ✗ | ✓ | ✓ (CSV/XML/KVP/W3C) | ~ |
| **Splunk Universal Forwarder** | ✓ | ✓ | ~ (raw fwd; no field parse) | ✗ | ✓ (Windows strength) | ✗ | ~ (add-ons) | ~ (HEC) | ✗ (no generic sink) | ✗ | ✗ | ~ (S2S to Splunk; syslog-out only) | ✗ | ✗ (UF doesn't parse) | ~ (SEDCMD) | ✗ |
| | | | | | | | | | | | | | | | | |
| **Cribl Stream** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ (S3, Iceberg via S3) | ✓ | ✓ | ✓ | ✓ | ✓ |
| **SentinelOne / Observo** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ (SIEM routing) | ✓ | ✓ | ✓ | ✓ (AI-assisted parse) |
| **Edge Delta** | ✓ | ✓ | ✓ | ✓ (OTel) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| **CrowdStrike / Onum** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | N/A | ✓ | ✓ | ✓ (Falcon-only) | ✓ | ✓ | ✓ | ✓ |
| **DataBahn** | ✓ | ✓ | ✓ | ~ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ (500+ integrations) | ~ | ✓ | ✓ | ✓ |
| **Monad (+Tarsal)** | ~ | ✓ (SaaS) | ✓ | ~ | ✓ (SaaS) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ (data lake routing) | ✓ | ~ | ✓ | ✓ | ✓ |
| **Abstract Security** | ✓ | ✓ | ✓ | ~ | ✓ | ✓ | ✓ | ✓ | N/A | ✓ | ✓ (Amazon Security Lake) | ✓ | ~ | ✓ | ✓ | ✓ |
| **Splunk Edge Processor** | ✓ | ✓ | ✓ | ✗ | ✓ | ~ | ✓ (S3 routing) | ~ | ✓ (S3) | ✗ | ~ (S3 only) | ✓ (Splunk/HEC) | ✗ | ✓ | ✓ (SPL2) | ✓ |

### 2c. Transform / Security-Native / Reliability / State

| Tool | Filter | Route/fan-out | Aggregate/window | Dedup | Sampling/reduction | Lookup/enrichment | GeoIP | Threat-intel | OCSF output/mapping | PII/redact | Detection-in-pipeline | Schema awareness | Backpressure | On-disk buffer | At-least-once/acks | Stateful aggregation | Windows native |
|------|--------|--------------|-----------------|-------|-------------------|------------------|-------|--------------|---------------------|-----------|----------------------|-----------------|-------------|---------------|-------------------|---------------------|---------------|
| **Vector** | ✓ | ✓ | ✓ (reduce/window) | ✓ | ✓ (sample transform) | ✓ (enrichment tables; CSV/mmdb/file) | ✓ (mmdb enrichment) | ~ (lookup tables; no native TI feed) | ~ (community VRL remaps at github.com/crowdalert/ocsf-vrl; not first-party) | ~ (VRL redact functions) | ✗ (no native detection) | ✗ (no schema registry) | ✓ | ✓ (disk buffers) | ✓ (E2E acks) | ~ (reduce is windowed but no cross-stream join) | ✓ |
| **Tenzir** | ✓ | ✓ | ✓ (native window ops) | ✓ | ✓ | ✓ (contexts; enrichment framework) | ✓ | ✓ (TI lookup contexts) | ✓ (first-party: ocsf::derive, ocsf::apply, ocsf::trim, ocsf::cast; v1.6 + v5.10) | ✓ | ✓ (Sigma/YARA detection operators; Python execution) | ✓ (Arrow-typed; OCSF schema validation) | ✓ | ✓ | ✓ | ✓ (stateful contexts; cross-event correlation) | ~ (no native Windows node; Windows Event Log via Fluent Bit relay) |
| **rsyslog** | ✓ | ✓ | ~ (mmaggregate; limited) | ✗ | ~ (simple) | ~ (mmfields; mmlookup; limited) | ~ (mmgeoip2 module) | ✗ | ✗ | ~ (mmdarwin for masking; limited) | ✗ | ✗ | ✓ (imptcp backpressure) | ✓ (disk queues) | ✓ | ✗ (no windowed aggregation) | ✗ (Linux daemon; commercial Windows Agent is separate) |
| **syslog-ng OSE** | ✓ | ✓ | ~ (limited; some features PE-only) | ✗ | ~ | ~ (db-parser enrichment; Python plugin) | ~ (geoip2 plugin) | ✗ | ✗ | ~ | ✗ | ✗ | ✓ | ✓ (disk buffer) | ✓ | ✗ | ✗ (OSE; PE has Windows) |
| **AxoSyslog** | ✓ | ✓ | ~ | ✗ | ~ | ✓ (FilterX lookup; Python hooks) | ✓ (FilterX geoip) | ~ | ✗ (no native OCSF) | ~ | ✗ | ✗ | ✓ | ✓ | ✓ | ✗ | ✗ |
| **Fluent Bit** | ✓ | ✓ | ~ (limited; multiline + basic) | ✗ | ~ (throttle filter) | ~ (record_modifier; Lua; no native table lookup) | ✓ (GeoIP2 filter) | ✗ | ✗ | ~ (Lua plugin) | ✗ | ✗ | ✓ | ✓ (filesystem buffer) | ✓ | ✗ (no stateful cross-event) | ✓ |
| **Fluentd** | ✓ | ✓ | ✓ (fluent-plugin-aggregate; richer than Fluent Bit) | ~ | ✓ (sampling plugin) | ✓ (1000+ plugins incl. Redis, DB lookups) | ✓ (GeoIP plugin) | ~ (plugin) | ✗ | ~ (plugin) | ✗ | ✗ | ✓ | ✓ | ✓ | ~ (plugins; heavier state) | ~ (limited; primarily Linux/containers) |
| **OTel Collector** | ✓ (filter processor) | ✓ | ~ (metrics only mature; log aggregation limited) | ✗ | ✓ (probabilistic/tail sampler for traces; logs: limited) | ~ (transform processor; no enrichment table natively) | ✗ (no native; contrib extension) | ✗ | ✗ (OCSF/OTel alignment work ongoing; no production operator) | ~ (redaction processor; contrib) | ✗ | ✗ | ✓ (memory_limiter) | ~ (persistent queue; experimental) | ~ (partial; retry exporters) | ✗ (stateless; tail sampling only) | ✓ |
| **Grafana Alloy** | ✓ (inherited OTel) | ✓ | ~ (metrics/Prometheus strong; log aggregation weak) | ✗ | ~ | ~ (inherited OTel gaps) | ✗ | ✗ | ✗ | ~ | ✗ | ✗ | ✓ | ~ | ~ | ✗ | ✓ |
| **Logstash** | ✓ | ✓ | ~ (aggregate filter; heavier) | ✗ | ~ | ✓ (translate filter; JDBC lookup; Redis) | ✓ (GeoIP filter; native) | ~ (threat lookup via translate/plugin) | ✗ (no native OCSF) | ✓ (mutate; anonymize filter) | ✗ | ✗ | ✓ | ✓ (persistent queue; 64 MB/pipeline) | ✓ | ~ (aggregate filter; stateful but heavyweight) | ✓ |
| **NXLog CE** | ✓ | ✓ | ✗ | ✗ | ✗ | ~ (very limited; no lookup tables) | ✗ | ✗ | ✗ | ~ (basic masking) | ✗ | ✗ | ~ | ~ (limited in CE) | ~ | ✗ | ✓ (primary strength) |
| **Splunk Universal Forwarder** | ~ (nullQueue drop) | ~ (output routing) | ✗ | ✗ | ~ (drop only) | ✗ | ✗ | ✗ | ✗ | ~ (SEDCMD mask) | ✗ | ✗ | ✓ | ✓ (persistent queue) | ✓ (useACK) | ✗ | ✓ (primary strength) |
| | | | | | | | | | | | | | | | | | |
| **Cribl Stream** | ✓ | ✓ | ✓ | ✓ | ✓ (up to 60–80% reduction vendor-stated) | ✓ (GeoIP, lookup tables, Redis) | ✓ | ✓ (TI packs; in-stream enrichment) | ✓ (AI-assisted OCSF mapping via Copilot; OCSF v1.6 for Security Hub) | ✓ (mask/redact functions) | ~ (routing rules; no Sigma-native) | ✓ (schema-aware routing) | ✓ | ✓ | ✓ | ✓ | ✓ |
| **SentinelOne / Observo** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ (GeoIP + TI enrichment) | ✓ | ✓ (AI-native TI enrichment) | ✓ (AI-assisted OCSF normalization) | ✓ (PII masking; zero-touch) | ✓ (AI-powered in-pipeline detection) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| **Edge Delta** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ (GeoIP + dynamic lookup + TI) | ✓ | ✓ | ✓ (OCSF output supported) | ✓ (PII masking/hashing) | ✓ (IOC detection; ML anomaly) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| **CrowdStrike / Onum** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ (Falcon TI) | ✓ (Falcon OCSF normalization) | ✓ | ✓ (in-pipeline; Falcon native) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| **DataBahn** | ✓ | ✓ | ✓ | ✓ | ✓ (40–70% volume reduction vendor-stated) | ✓ (virtual CMDB; 500+ context sources) | ✓ | ✓ | ✓ (OCSF normalization; schema drift alerting) | ✓ | ~ (AIDI in-stream decisions; not Sigma-based) | ✓ (schema drift detection) | ✓ | ✓ | ✓ | ✓ | ✓ |
| **Monad (+Tarsal)** | ✓ | ✓ | ~ | ✓ (70% noise reduction vendor-stated) | ✓ | ✓ (175+ enrichment sources) | ✓ | ~ | ~ (OCSF support not confirmed in public docs) | ~ | ✗ (no in-pipeline detection stated) | ~ | ✓ | ✓ | ✓ | ~ | ✓ |
| **Abstract Security** | ✓ | ✓ | ~ | ✓ | ✓ | ✓ (live-streaming TI enrichment) | ✓ | ✓ | ✓ (real-time OCSF normalization to Amazon Security Lake) | ~ | ✓ (in-stream + historical + distributed detection) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| **Splunk Edge Processor** | ✓ | ✓ | ✗ | ✗ | ✓ (filter/drop) | ✗ | ✗ | ✗ | ✗ | ✓ (mask/redact via SPL2 rules) | ✗ | ~ (Splunk schema only) | ✗ (no delivery guarantee documented) | ✗ | ✗ (no delivery guarantee; data loss on outage) | ✗ | ✓ |

---

## 3. Limitations — Per-Tool Detail

### OSS Runnable Pipelines

**Vector**
Vector's transformation language (VRL) is intentionally stateless across events — it explicitly lacks cross-event state, so windowed aggregation and sequence correlation require the `reduce` transform with a timer, which covers basic use cases but is not a full stream processor. There is no native OCSF operator; OCSF mappings exist as community VRL scripts (github.com/crowdalert/ocsf-vrl) rather than a first-party supported feature. Enrichment table support (CSV, mmdb) works but requires static files loaded at startup; there is no live-reloading lookup against a running database. No built-in threat-intel feed integration. No schema registry or schema validation. No detection layer — Vector positions as pure pipeline, not analytics. The free license is MPL-2.0, which means modifications to Vector itself must be disclosed, but use in pipelines is unrestricted. Windows is supported but the Windows ecosystem is less documented than Linux.

**Tenzir**
The Node (OSS, BSD-3) is capable, but the Platform (the UI, fleet management, multi-node orchestration, and the cloud-hosted control plane) is proprietary and requires a Community or Enterprise subscription. Running Tenzir at scale without the Platform means managing nodes manually with no central config push or fleet visibility. The TQL (Tenzir Query Language) is a custom DSL — not SQL, not YAML, not SPL — with a learning curve. There is no native Windows node binary; Windows Event Log collection requires routing through a Fluent Bit agent relay, adding a hop. The storage engine (Tenzir's indexed on-disk format) has its own management overhead and is not a standard open format; Parquet export is available, but the native store is not Iceberg-catalog-compatible out of the box. Memory scales with enrichment context size; large lookup tables can push idle footprint well above 200 MB.

**rsyslog**
rsyslog is a line-oriented syslog daemon at its core. JSON field-level filtering requires loading `mmjsonparse`, which imposes the constraint that the JSON must be a valid, complete top-level object with no trailing content — partial or streaming JSON is not handled. There is no native OTLP input or output. No Windows native binary — the rsyslog Windows Agent is a separate commercial product from Adiscon (not OSS). No threat-intel enrichment, no GeoIP without `mmgeoip2` module, and no OCSF support. Aggregation (via `mmaggregate`) is limited compared to modern stream processors. Configuration is a custom RainerScript DSL that has grown organically over 20+ years and is notoriously dense; the module system requires careful load ordering. No dedup or sampling primitives in the core.

**syslog-ng OSE**
The open-source edition lacks Windows support entirely — that is a Premium Edition (PE) exclusive. Several features documented in the syslog-ng admin guide are PE-only (encrypted log store, compliance features). No OTLP input or output in OSE. No OCSF. No threat-intel. Aggregation and stateful processing are minimal. The OSE branch can lag the PE branch in bug fixes when fixes are tied to PE-gated features. Configuration syntax is expressive but non-obvious for complex routing trees.

**AxoSyslog**
AxoSyslog is a genuine fork (post v4.7.1, GPL-3.0 as of v4.12) with material improvements over syslog-ng OSE — FilterX is significantly more capable than syslog-ng's legacy statement model, and cloud destinations (S3, ClickHouse, BigQuery, PubSub) are first-class. However, it still has no native Windows binary; Windows collection requires an agent relay. No OCSF native output. No threat-intel primitives. No stateful cross-event aggregation beyond basic window operations. The GPL-3 license change (from syslog-ng's LGPL/GPL-2) means linking AxoSyslog into a commercial product requires GPL-3 compliance — a meaningful constraint for vendors building products on top of it. [Source: Axoflow blog, AxoSyslog license update]

**Fluent Bit**
Fluent Bit's primary limitation for security workloads is the near-absence of stateful cross-event processing. There is no native windowed aggregation, no join, no sequence detection — it is a high-throughput forwarder and light transformer, not a stream processor. When memory limits are hit, Fluent Bit pauses the input plugin rather than spilling to disk by default, which means data generated during that window is dropped unless filesystem buffering is explicitly configured. The plugin ecosystem (100+ built-in) is significantly smaller than Fluentd's 1000+ gems. There is no native OCSF, no threat-intel, no detection. GeoIP requires the GeoIP2 filter plugin. Custom logic beyond built-in transforms requires Lua (high skill bar for complex logic) or Go plugins (compilation required). The `winlog` and `winevtlog` inputs for Windows require admin privileges to read the Security channel.

**Fluentd**
Fluentd's Ruby runtime is the dominant limitation: the 30–60 MB+ idle footprint and Ruby GIL mean it does not match C/Rust/Go tools at high throughput. CPU-intensive Ruby logic (`enable_ruby`) blocks the processing thread and degrades throughput non-linearly. Plugin quality varies widely across the 1000+ gem ecosystem — many plugins are community-maintained and unmaintained. Cloud providers (AWS, GCP) have migrated their default log collectors from Fluentd to Fluent Bit precisely because of the performance gap. No OCSF. No threat-intel. No detection. Stateful aggregation is available via plugins but heavier than purpose-built stream processors. CNCF published a Fluentd-to-Fluent-Bit migration guide in Oct 2025, signaling Fluentd's diminishing role as a primary agent. [Source: CNCF blog, 2025-10-01]

**OpenTelemetry Collector**
The OTel Collector's log pipeline is less mature than its metrics and traces pipelines — this gap was still visible in the 2026 OTel Collector follow-up survey. There is no built-in enrichment table support; lookup/join requires a custom processor or external call. No GeoIP native. No threat-intel. No OCSF operator. The transform processor provides basic field manipulation but is not a general-purpose stream processing DSL. Configuration changes require a full restart — there is no hot-reload of individual pipelines (a top user complaint per the 2026 follow-up survey). Persistent queue is experimental and not production-hardened across all distros. At high cardinality or volume, the Collector becomes a bottleneck without horizontal scaling, which then requires an operator layer. No stateful cross-event aggregation (tail-based sampling is the only stateful feature, and it is traces-only). The security-relevant posture is: standards-neutral transport layer, not a security analytics engine.

**Grafana Alloy**
Alloy inherits all OTel Collector limitations for log pipelines. The additional constraint is Grafana-specific: the configuration language (Alloy Flow, HCL-like) is not portable to the standard OTel Collector config YAML, creating vendor-specific lock-in for pipeline definitions. The component DAG adds a small runtime overhead. Alloy is optimized for the Grafana stack (Loki/Mimir/Tempo/Pyroscope); security-native features (OCSF, threat-intel, detection) are absent. The Prometheus-native pipeline is strong; the security pipeline is undifferentiated from upstream OTel.

**Logstash**
The JVM is the overriding constraint. Default heap is 1 GB; recommended for production is 4–8 GB. Startup takes 15–30 seconds. Each persistent queue pipeline requires at least 128 MB heap. At 10 pipelines, memory consumption can reach 10+ GB (there are community reports of 80 GB at scale). Throughput per core is the lowest in this comparison by a wide margin. Logstash is tightly coupled to the Elastic stack — while it can output to non-Elastic destinations, the primary development investment is in Elasticsearch/Logstash/Kibana integration. No OCSF native. GeoIP is a native filter. Threat-intel lookup via translate filter or plugin. Detection logic requires custom Ruby filter, which degrades throughput. Aggregate filter supports state but is heavyweight.

**NXLog CE**
NXLog CE's license (NXLog Public License) is not OSI-approved and contains a commercial bundling restriction: if your product or service depends on NXLog CE to function, you need a commercial license. This makes it unsuitable as a redistributable component. CE lacks enterprise features available in NXLog Platform/Enterprise: no fleet management, no central config push, no advanced routing rules, limited Kafka support. No OTLP input/output. No OCSF. No GeoIP or threat-intel. No aggregation or stateful processing. No buffering durability beyond basic queue. Windows support is the tool's primary differentiator — it is a strong native Windows Event Log collector and forwarder. Windows Server 2025 support was added in NXLog Platform 6.6, with CE 3.2.x carrying it at limited/unofficial status. CE development velocity has slowed as NXLog focuses on the commercial Platform product.

**Splunk Universal Forwarder** *(proprietary-but-free agent)*
The UF is a forwarder, not a transform pipeline — the defining limitation for this benchmark. It does not parse events (parsing happens at a Heavy Forwarder or the indexer), so it has no JSON field-filtering, enrichment, aggregation, GeoIP, threat-intel, OCSF, or detection. Its only in-stream transforms are nullQueue routing (drop events) and SEDCMD (regex masking), and both require putting the UF into a parsing mode it isn't optimized for. Output is Splunk's proprietary S2S protocol to an indexer; there is no clean generic file/null/Kafka/object sink, so the read→filter→sink modes (A–D) used for the OSS tools don't apply — the UF's natural measurement is forwarding throughput (KBps, self-reported in `metrics.log`) to a receiver, which is a different test that needs a Splunk receiver. It is free but proprietary (Splunk EULA), download is account-gated, and it is locked to the Splunk ecosystem. Because it is Splunk software, publishing UF throughput numbers is subject to the same Splunk EULA (1.2(v)/3(f)) the project applies to SIEM benchmarks — any public number must be genericized or cleared. Genuine strengths: small footprint, robust at-least-once delivery (persistent queue + useACK), and best-in-class Windows Event Log collection.

---

### Commercial / SaaS (Documented-Reference)

*All claims in this section are vendor-stated unless otherwise noted. No independent throughput runs were performed.*

**Cribl Stream / Edge**
The central limitation is architectural: a distributed Cribl deployment requires a Leader node acting as control plane — configuration, credential management, and fleet orchestration flow through it. While single-instance deployments can run standalone, any production-scale multi-worker setup requires the Leader (self-hosted or Cribl.Cloud). The free tier caps at 1 TB/day with a 50-worker-process limit. The 1 TB/day free cap is meaningful for benchmarking reference but not production-scale security environments. Cribl Edge (the lightweight endpoint agent) requires the Stream/Cloud control plane for config management — it cannot fully self-configure independently. OCSF support arrived via AI-assisted Copilot Editor and the Security Hub integration (Dec 2025) — it is not a Day-1 native feature but a maturing add-on. No native Sigma-based detection operator; detection-in-pipeline is rule-based routing, not a detection engine.

**SentinelOne Data Pipelines (fmr. Observo AI)**
SaaS-only; no self-hosted path. The acquisition by SentinelOne (Sept 2025, $225M) means the roadmap is now driven by SentinelOne's Autonomous SOC vision — the standalone pipeline product may be consolidated into the SentinelOne platform over time, creating lock-in for customers who adopted it as a neutral pipeline. Pricing is undisclosed. The AI-native parse and enrichment features are vendor-stated and not independently verified.

**Edge Delta**
SaaS control plane with on-host agent; no fully on-prem/air-gapped deployment documented. ML-based anomaly detection and IOC identification are vendor-stated capabilities. OCSF output is supported per product page but fidelity of the mapping is undocumented independently.

**CrowdStrike Falcon (fmr. Onum)**
Post-acquisition, Onum's pipeline technology is fully integrated into Falcon NG SIEM — it is not available as a standalone product. Customers must have a Falcon NG SIEM subscription. The pipeline detection runs exclusively within the Falcon ecosystem, meaning outputs other than Falcon are not first-class. Vendor-stated performance claims (5× faster processing, 50% storage reduction, 70% faster incident response) are marketing figures without published methodology.

**DataBahn**
Early-stage commercial product ($17M Series A, 2025). AIDI (Autonomous In-Stream Data Intelligence) announced March 2026 is the AI-native decision layer — it is early-access, with design partner figures (40–70% log volume optimization) being vendor-stated without independent validation. Deployment model involves a Smart Edge agent plus SaaS control plane; full air-gap is not documented. The 500+ connector count includes third-party integrations, not all of which are native parsers.

**Monad (+Tarsal)**
Still in public beta at time of writing (1 TB/month free). The Tarsal acquisition added pre-built SaaS/cloud connectors (audit logs, one-click ETL), which is Monad's primary differentiation. On-prem / hybrid is stated as available but details are thin. OCSF support is not confirmed in public documentation as of 2026-06-08. Pricing beyond the beta free tier is not disclosed. The platform is well-suited for SaaS-heavy environments (Okta, GitHub, cloud CSPM) but thin on raw network telemetry sources (Zeek, Suricata, Sysmon direct ingest).

**Abstract Security**
Positions as a composable SIEM layer, not a pure pipeline — detection (in-stream, historical, distributed) is a core feature, not a bolt-on, which differentiates it from the pure-pipeline tools. Real-time OCSF normalization to Amazon Security Lake is a documented feature. Pricing departs from volume-based to value-based tiers (Real Time / Hot / Warm storage), which is architecturally interesting but makes apples-to-apples cost comparison difficult. PII masking details are sparse in public documentation.

**Splunk Edge Processor / Ingest Actions**
The Edge Processor explicitly provides no delivery guarantee: data loss can occur under backpressure or destination outage per Splunk's own documentation. It does not support metrics data (logs only). Output routing is Splunk-centric — the primary destination model is Splunk Cloud/Enterprise or S3; non-Splunk SIEM routing requires custom HTTP output. No OTLP input or output. No enrichment, GeoIP, or threat-intel. No stateful aggregation. The configuration language is SPL2 (a Splunk-proprietary rewrite of SPL), creating lock-in. Ingest Actions provides a GUI over the same filtering/masking/routing logic with lower operational barrier but identical capability ceiling. Both require a Splunk subscription; there is no standalone deployment.

---

## 4. Fair-Test Implications for the Throughput Benchmark

This section maps each tool's capability constraints to which benchmark modes are valid.

### What the throughput bench actually runs (see `results/RESULTS.md`)
The implemented bench (`run.py`) measures the **mode-B** transform — JSON-parse + single-field filter — under two sink variants, across the no-sudo OSS engines (Vector, Tenzir, OTel Collector, Grafana Alloy, rsyslog):
- **`discard`** = read + parse + filter → null/nop sink (pure pipeline throughput).
- **`file`** = the full route: read + parse + filter + re-serialize + write to a file.

rsyslog is run in two sub-modes that bracket the A↔B line below: a **raw-line-match** sub-mode (substring match, no parse ≈ mode-A) and a **json-parse** sub-mode (`mmjsonparse`, the parse-comparable ≈ mode-B). The fuller mode-C (enrich/route) and mode-D (syslog regex) battery defined below is the design target, not yet implemented — the A–D taxonomy stays here as the fairness map for when those modes are added and for the engines still pending a sudo install. Measured numbers, the two timing models (stdin-drain vs tailing-daemon), the documented Cribl + Splunk-UF references, and the pending-sudo list all live in `results/RESULTS.md`.

### Mode definitions (design taxonomy for the full battery)
- **mode-A**: raw-line passthrough (no parse) — syslog or NDJSON input → null/file sink, no transform
- **mode-B**: JSON parse + field-filter — parse NDJSON, filter on one field, write matching events to file/null *(this is the implemented bench)*
- **mode-C**: JSON parse + enrich + route — parse, enrich from lookup table, route to two sinks
- **mode-D**: syslog parse + regex extract + route — raw syslog RFC5424, extract fields via regex, route

#### OSS Runnable Pipeline — mode validity

| Tool | Mode-A | Mode-B | Mode-C | Mode-D | Notes |
|------|--------|--------|--------|--------|-------|
| **Vector** | ✓ | ✓ | ✓ | ✓ | All modes valid. Use VRL `parse_syslog()` for mode-D. |
| **Tenzir** | ✓ | ✓ | ✓ | ✓ | All modes valid. Use `read_syslog` operator for mode-D. |
| **rsyslog** | ✓ (mode-A: raw line match, no parse) | ~ (mode-B valid only with `mmjsonparse` loaded; exclude if mmjsonparse absent from build) | ✗ (mode-C: no lookup-table enrichment natively; skip or note as N/A) | ✓ (mode-D: native syslog parsing) | Mode-B must document whether mmjsonparse is enabled; results without it are raw-line-only and not comparable to JSON-native tools on that mode. |
| **syslog-ng OSE** | ✓ | ~ (mode-B valid with `json-parser`; document whether enabled) | ✗ (no enrichment table; skip mode-C) | ✓ | Same caveat as rsyslog for mode-B. Mode-C not fair. |
| **AxoSyslog** | ✓ | ✓ (FilterX native JSON) | ~ (mode-C: lookup possible via FilterX; validate config) | ✓ | All modes potentially valid; document FilterX config for mode-C. |
| **Fluent Bit** | ✓ | ✓ | ~ (mode-C: use record_modifier or Lua for enrichment; note Lua overhead) | ✓ | Mode-C valid but enrichment method (Lua vs native) affects throughput interpretation — document. |
| **Fluentd** | ✓ | ✓ | ✓ (record_transformer + plugin enrichment) | ✓ | All modes valid. JVM overhead: account for warm-up; exclude first 30s of results. |
| **OTel Collector** | ✓ | ✓ | ~ (mode-C: no native lookup table; use transform processor with static attribute; note limited enrichment) | ~ (mode-D: syslog receiver available but contrib; validate) | Mode-C enrichment must be noted as static-attribute only (no DB lookup). Mode-D requires contrib build — document distro used (core vs contrib). |
| **Grafana Alloy** | ✓ | ✓ | ~ (same as OTel Collector; inherited limitations) | ~ | Same constraints as OTel Collector. Document Alloy version and which OTel components are used. |
| **Logstash** | ✓ | ✓ | ✓ (translate filter for enrichment; GeoIP native) | ✓ | All modes valid. **Exclude from JVM startup comparisons**: measure only steady-state throughput after warm-up (exclude first 60s minimum). Flag 4 GB heap as baseline config. |
| **NXLog CE** | ✓ | ✓ (JSON parse supported) | ✗ (mode-C: no lookup enrichment in CE; skip) | ✓ | Mode-C not fair for CE. Windows-specific modes (Windows Event Log source) are the primary CE use case; not applicable to this Linux-focused benchmark unless dual-platform. |
| **Splunk Universal Forwarder** | ✗ | ✗ | ✗ | ✗ | Forwarder, not a transform pipeline: no generic file/null sink and no parse, so modes A–D don't apply. Measure separately as a forwarding-rate test (file → S2S → a Splunk receiver); any published number is Splunk software under the project's EULA genericization. |

#### Commercial / SaaS — mode applicability

Commercial tools are excluded from controlled throughput runs in this benchmark. For documented-reference comparison:
- Vendor-stated throughput claims (Cribl: "several TB/day per worker"; DataBahn: "40–70% volume reduction"; CrowdStrike/Onum: "5× faster processing") should be cited with source and flagged as vendor-stated without independent replication.
- Where a vendor publishes reproducible benchmark methodology, note the citation; otherwise all commercial numbers are marketing claims.

#### Cross-tool comparability notes

1. **Syslog daemons vs JSON-native tools on mode-B**: rsyslog and syslog-ng without their JSON modules are fundamentally different tools from Vector/Fluent Bit on this mode. A raw rsyslog mode-B without mmjsonparse is a line-passthrough benchmark, not a JSON-parse benchmark. Present these as separate sub-groups if both are run.
2. **JVM startup exclusion**: Logstash results must note heap size and exclude the warm-up window. Comparing cold-start Logstash to cold-start Vector overstates the gap; compare steady-state.
3. **Null sink vs file sink**: Vector's blackhole sink, Fluent Bit's null output, rsyslog's omfile with /dev/null, and OTel Collector's debug/noop exporter are not identical in overhead. Document which sink was used for each tool.
4. **Tenzir enrichment memory**: mode-C with large lookup tables pushes Tenzir memory footprint materially; document context size loaded.
5. **Grafana Alloy vs OTel Collector**: Alloy wraps OTel components — the throughput difference is the DAG evaluation overhead. Running both with the same underlying filelog receiver and transform processor isolates that overhead.
6. **Splunk Universal Forwarder is a different test + EULA-gated**: the UF has no read→filter→sink path (output is Splunk S2S), so it isn't comparable on modes A–D. If measured at all it's a forwarding-rate test (file → S2S → a Splunk receiver) requiring a receiver, and any published number is Splunk software subject to the project's EULA genericization ("schema-on-read SIEM forwarder").

---

## 5. Sources

License and capability claims:
- Vector license (MPL-2.0): https://github.com/vectordotdev/vector
- VRL stateless design / limitations: https://vector.dev/docs/reference/vrl/
- VRL OCSF community remaps: https://github.com/crowdalert/ocsf-vrl
- Tenzir OCSF operators (v5.10, ocsf::derive/apply/trim/cast): https://tenzir.com/blog/simplify-ocsf-mapping-with-three-new-tenzir-operators
- Tenzir license (BSD-3 Node; proprietary Platform): https://tenzir.com/legal/terms-and-conditions
- Tenzir 2025 changelog: https://docs.tenzir.com/changelog/timeline/2025/
- rsyslog license (GPLv3): https://www.rsyslog.com/doc/licensing.html
- rsyslog Windows support (no native; Windows Agent commercial): https://www.rsyslog.com/doc/faq/does-rsyslog-run-under-windows.html
- mmjsonparse limitations: https://rsyslog.readthedocs.io/en/latest/configuration/modules/mmjsonparse.html
- syslog-ng OSE license (LGPL-2.1 + GPL-2): https://lwn.net/Articles/402298/
- syslog-ng OSE vs PE features (Windows PE-only): https://syslog-ng.github.io/admin-guide/020_The_concepts_of_syslog-ng/011_Commercial_version.html
- AxoSyslog fork + GPL-3 license: https://axoflow.com/blog/axosyslog-syslog-ng-fork-license-change-gpl3
- AxoSyslog capabilities: https://axoflow.com/axosyslog
- Fluent Bit license (Apache 2.0): https://docs.fluentbit.io/manual/about/license
- Fluent Bit vs Fluentd memory comparison: https://docs.fluentbit.io/manual/about/fluentd-and-fluent-bit
- Fluentd-to-Fluent-Bit migration guide (CNCF, 2025-10-01): https://www.cncf.io/blog/2025/10/01/fluentd-to-fluent-bit-a-migration-guide/
- OTel Collector 2026 follow-up survey (config restart limitation): https://opentelemetry.io/blog/2026/otel-collector-follow-up-survey-analysis/
- Grafana Alloy capabilities (1-year recap, May 2025): https://grafana.com/blog/2025/05/08/alloy-one-year/
- Logstash JVM heap recommendations (4–8 GB): https://www.elastic.co/guide/en/logstash/8.19/jvm-settings.html
- NXLog CE license (NXLog Public License; commercial bundling restriction): https://nxlog.co/nxlog-public-license
- NXLog CE vs Platform feature gaps: https://nxlog.co/news-and-blog/posts/nxp-vs-ce
- Cribl Stream licensing (Free 1 TB/day; Standard 5 TB/day; Enterprise unlimited): https://docs.cribl.io/stream/licensing/
- Cribl OCSF support (Dec 2025, Security Hub + Copilot Editor): https://www.globenewswire.com/news-release/2025/12/02/3198404/0/en/Cribl-Supercharges-Incident-Response-in-Amazon-Security-Hub-with-Open-Cybersecurity-Schema-Framework-OCSF-Support.html
- Cribl Stream no delivery guarantee (Edge Processor): https://help.splunk.com/en/data-management/process-data-at-the-edge/use-edge-processors-for-splunk-cloud-platform/introduction/about-the-edge-processor-solution
- SentinelOne acquisition of Observo AI ($225M, Sept 8 2025): https://www.sentinelone.com/press/sentinelone-to-acquire-observo-ai-to-revolutionize-siem-and-security-operations/
- CrowdStrike acquisition of Onum (Aug 27 2025): https://www.crowdstrike.com/en-us/press-releases/crowdstrike-to-acquire-onum/
- Monad acquisition of Tarsal (June 23 2025): https://www.monad.com/blog/monad-welcomes-tarsal
- DataBahn $17M Series A (2025): https://www.databahn.ai/press-releases/databahn-ai-raises-17m-series-a-to-redefine-enterprise-data-pipelines-for-security-observability-and-ai
- DataBahn AIDI announcement (March 2026): https://www.databahn.ai/press-releases/databahn-advances-security-data-pipeline-with-autonomous-in-stream-data-intelligence
- Abstract Security + Amazon Security Lake + OCSF: https://www.abstract.security/blog/abstract-security-amazon-security-lake-ocsf-upgraded-security-data-management
- Splunk Edge Processor no delivery guarantee (Splunk docs): https://help.splunk.com/en/data-management/process-data-at-the-edge/use-edge-processors-for-splunk-cloud-platform/introduction/about-the-edge-processor-solution
- Edge Delta Security Data Pipelines GA: https://www.prnewswire.com/news-releases/edge-delta-announces-general-availability-of-security-data-pipelines-revolutionizing-real-time-security-data-management-302378396.html

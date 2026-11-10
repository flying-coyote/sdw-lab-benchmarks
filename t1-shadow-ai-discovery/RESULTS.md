---
type: benchmark-results
area: T1-shadow-ai-discovery
date: 2026-11-09
hypothesis_served: H-AI-ARTIFACT-INVENTORY-01 (discovery half; PROPOSED, gated-pending, no score; nothing here moves its confidence, that goes through the evidence gate and the owner)
related: ai-artifact-sbom/ (R4)
---

# Results: which discovery method sees which shadow-AI surface?

**Pre-registration:** `PREREGISTRATION.md`, sha256 `bc2920c93e85e871bf6edb1cc8c71ce12c69d5d564f51103f28fc9e812b7060d`,
frozen 2026-11-10T00:55:54Z (local evening of 2026-11-09), frozen by agent before run; not owner-reviewed. The
file's hash at write-up time matches the frozen hash (checked with `sha256sum`), so it was not edited after the
run. Independently verified 2026-11-09 (local; 01:23Z-01:40Z on 2026-11-10) by a second agent (`VERIFICATION.md`, verdict VERIFIED-WITH-FIXES): three
fresh full runs reproduced every fired-rule set exactly, and the fixes it made are marked *[verification fix]* below.

**Rig stamp (§7b; every duration here is secondary and was taken under contention):** Beelink, AMD Ryzen 7 5800H,
14 vCPU / 47 GB to WSL2, kernel 6.6.87.2-microsoft-standard-WSL2, Docker 29.5.3. Several other benches ran on
the host at the same time, so every container was pinned to `--cpuset-cpus 0-3` and every host command ran under
`nice -n 10 taskset -c 0-3`; the timings below are **taken under contention** and support no latency claim.
Clock: chrony; `chronyc tracking` at freeze read `System time` 0.607 s slow of NTP (larger than the methodology's
milliseconds guideline), 36 µs fast at write-up; every duration was timed with `time.monotonic()`, which the
offset does not affect. Lab runs 2026-11-10 01:05Z to 01:08Z, methods pass 01:09Z to 01:14Z.

**Instruments as run:** Zeek 8.0.11 (`zeek/zeek:8.0.11`, `zeek -C -r <pcap> local LogAscii::use_json=T`), tcpdump
4.99.5 and dnsmasq 2.91 (alpine 3.22 sidecar), osquery 5.24.0 (deb sha256 `8ae0416d…5592`, inside the endpoint
container, `osqueryi --json`), Syft 1.55.0 (the R4 binary, checksum verified there), the egress check
(`run_methods.py`, deterministic). Endpoint: `python:3.12-slim` (Debian 13, Python 3.12.13, curl 8.14.1), Ollama
0.20.6 (host binary bind-mounted), Cline 4.1.26 from Open VSX (vsix sha256 `d8ea4c35…1c4d`), eight AI packages
pinned in `fixtures/ml-requirements.txt` (63 dists after resolution, `fixtures/ml-venv-freeze.txt`). Every command
is in `COMMANDS.log`; per-run raw output in `results/run{1,2,3}/`.

**Runs:** 3 full runs (fresh containers, fresh pcap each time) after one discarded shake-out run (`results/run0-discarded/`, small text outputs kept in the repo, large files gitignored like every run;
see Deviations). Every method's fired-rule set was identical across the three runs (0 differing runs for each of the
six method views, `results/scores.json` → `variance_runs_differing_from_run1`), so the matrix is reported once.

## Headline

Across nine planted surfaces (ten cells, since the Ollama store is scored separately as S7b), the union of the
five methods reaches eight at "found", one only partially (the local OpenAI-compatible server, S2, which every
method sees as a port or a URI and none names), and misses one outright (the model weights in the Ollama store,
S7b). The shape is lopsided: osquery on the endpoint scores six of ten at "found" (runtime process, IDE
extension, MCP config content, browser extension, packages, model files) and is the *only* method that reaches
the IDE extension, the MCP configs and the browser extension at all; the three network methods (Zeek, the DNS
log, the egress allowlist) each score two, both of them the remote surfaces (API calls, SaaS visits), and see
the local runtimes only as a port on a peer's connection; Syft scores two (packages, named model files), the
same two it scored in R4, and reports nothing at all for the extension directories or the config files. Five
of the ten cells on the osquery column (four of its six finds, plus the S7b miss) depended on knowing where to
look *[verification fix: the original said four while listing five]*: the venv packages appear only with
the venv path in the query (the undirected `python_packages` returns just `pip` from `/usr/local`); the
Ollama blobs do not appear under the pre-registered `/home/dev/%%` glob at all, because osquery's recursive
wildcard skips hidden directories, so S7b is a miss for osquery under the frozen rule and a find under a
labelled post-hoc query that names `.ollama/models/blobs/` (`results/posthoc/P1b`); the MCP configs were
reached only because the query carried the seven client config paths; and the IDE and browser extensions were
reached only because the analyst knew the `vscode_extensions` and `chrome_extensions` tables exist and the
fixture carried the files they read. Two of the six osquery finds also rest on post-run harness changes that are
listed as deviations, so under the literally frozen query and scoring text osquery scores four, not six (see H5)
*[verification fix]*. False positives were
exactly the pre-registered one: the port rules (Zeek `http`/`conn` on 8080, osquery `listening_ports` 8080) fired
on the benign Python file server; no domain, package, process, extension or model-file rule fired on any control.

## The surface × method matrix (run 1; identical in runs 2 and 3)

found = a pre-registered rule fires and the output names the surface; partial = fires but ambiguous or
incomplete; missed (structural) = the method's input cannot contain the surface; missed (rule gap) = the input
contains it and the frozen rule did not fire. The two kinds of rule gap differ in who can fix them: osquery's
(S6 undirected, S7b glob, S8/S9 no socket rule *[verification fix]*) close with a changed query, Syft's (S3, S4, S5, S7b) mean no cataloger emits a
component for that path, which no analyst-side query changes.

| Surface | M1 Zeek (eth0 pcap) | M2 DNS log | M3 osquery | M4 Syft | M5 Egress allowlist | union |
|---|---|---|---|---|---|---|
| S1 Ollama runtime :11434 | partial (peer `http.log` `/api/tags`, `/api/generate`; `conn` 11434; `registry.ollama.ai` SNI+DNS from the pull) | partial (`registry.ollama.ai` only) | **found** (`processes`: `ollama serve` and `ollama runner --model …/blobs/sha256-2af3…`; `listening_ports` 11434) | missed (structural) | partial (`registry.ollama.ai` flagged) | found |
| S2 local OpenAI-compatible server :8000 | partial (peer `http.log` `POST /v1/chat/completions`; `conn` 8000) | missed (structural) | partial (`listening_ports` 8000, owner unresolved, see Deviation 4; process rule does not match `python3 openai_compat_stub.py`) | missed (structural) | missed (structural) | partial |
| S3 IDE extension (Cline 4.1.26) | missed (structural) | missed (structural) | **found** (`vscode_extensions`: `saoudrizwan.claude-dev` 4.1.26) | missed (rule gap: 0 components under `.vscode/extensions/`) | missed (structural) | found |
| S4 MCP client configs (2 files) | missed (structural) | missed (structural) | **found** (`file` path ×2 and `yara_file` `mcpServers` match ×2) | missed (rule gap: 0 components) | missed (structural) | found |
| S5 browser extension (Chrome manifest) | missed (structural) | missed (structural) | **found** (`chrome_extensions`: "AI Chat Sidebar (lab fixture)", id `ibblkdem…`) | missed (rule gap: 0 components) | missed (structural) | found |
| S6 Python ML packages (8) | missed (structural) | missed (structural) | **found**, directed query only (O4b: 8 of 8; undirected O4a: 0 of 8) | **found** (8 of 8, PURLs `pkg:pypi/…`) | missed (structural) | found |
| S7 model files (GGUF + safetensors) | missed (structural) | missed (structural) | **found** (`file`: both paths by extension) | **found** (`TinyLlama` from the GGUF header, `MiniLM-L6-H384-uncased` from `config.json`; type `model`, no PURL) | missed (structural) | found |
| S7b weights in the Ollama store | missed (structural) | missed (structural) | missed (rule gap: `%%` skips hidden dirs; post-hoc explicit path finds all 5 blobs) | missed (rule gap, as in R4) | missed (structural) | **missed** |
| S8 outbound model-API calls (8 hosts) | **found** (SNI 8 of 8, DNS 8 of 8) | **found** (8 of 8) | missed (rule gap: no pre-registered socket rule; `process_open_sockets` held TIME_WAIT rows to the remote :443 addresses, IP only) *[verification fix: was "structural"]* | missed (structural) | **found** (8 of 8 flagged) | found |
| S9 AI SaaS visits (5 hosts) | **found** (SNI 5 of 5, DNS 5 of 5, plus the `copilot.com` redirect) | **found** (5 of 5) | missed (rule gap, as S8) *[verification fix]* | missed (structural) | **found** (5 of 5 plus `copilot.com`) | found |
| **found count (of 10)** | 2 | 2 | 6 | 2 | 2 | 8 |

Benign controls and false positives (per method, distinct controls flagged):

| Method | Controls flagged | By which rule | Controls not flagged |
|---|---|---|---|
| M1 Zeek | 1 (C1 benign `http.server` on 8080) | Z3 `http.log` port rule, Z4 `conn.log` port rule | C2 five benign domains (not in `AI_DOMAINS`) |
| M2 DNS log | 0 | | C2 |
| M3 osquery | 1 (C1) | O2 `listening_ports` 8080 | C3 prettier (not in `AI_EXT_IDS`), C4 benign Chrome fixture, C5 requests/numpy, C6 `archive.bin` (`.bin` is not in `MODEL_EXT`) |
| M4 Syft | 0 | | C3, C5 (reported as packages, not matched), C6 |
| M5 Egress | 0 | all five C2 hosts matched the allowlist | |

## What each method structurally cannot see (and what it saw that it should not be credited for)

- **An eth0 tap (Zeek) has no files and no loopback.** The 32-row `http.log` from the secondary `-i any`
  capture (`results/run1/zeek-any/`) shows what the 4-row eth0 `http.log` cannot: the IDE-style loopback calls
  to `127.0.0.1:11434` and `:8000`, Ollama's own runner subprocess answering `/health`, `/load` and
  `/completion` on an ephemeral port (33139 in run 1), and the `ollama/0.20.6 (amd64 linux) Go/go1.24.1` user
  agent on the `/api/pull` call. On eth0 the runtimes exist only because a second workstation called them;
  a runtime used solely from the same machine is invisible to the network, and the one footprint it leaves is
  the registry pull (`registry.ollama.ai`), which a runtime with its models already downloaded never makes.
  Zeek named every TLS destination by SNI in all three runs (20 distinct SNIs per run, 20 DNS names); no ECH
  was observed with curl 8.14.1 against these hosts on 2026-11-10, which is a property of today's clients and
  will not hold indefinitely.
- **A DNS log sees names, not purpose, and only names the client resolved.** It matched the 13 remote AI hosts
  and `registry.ollama.ai`, and nothing else by construction. It cannot tell `api.openai.com` reached by an IDE
  extension from the same name reached by a sanctioned internal gateway, and it saw nothing of S2 to S7.
- **The egress allowlist is a control whose log is a sensor.** It flagged 15 destinations per run: the 13 AI
  hosts, `registry.ollama.ai`, and `copilot.com` (the redirect target of `copilot.microsoft.com`, which is *not*
  in the pre-registered `AI_DOMAINS`, so Zeek's and the DNS log's domain rules did not fire on it while the
  allowlist did, because an allowlist does not need to know what a thing is to know it is not sanctioned).
  It flagged no benign host. It is blind to everything on the host.
- **Syft sees package manifests and the two model formats it has catalogers for.** It reports 72 artifacts
  for the home directory: 64 Python dists from the venv (8 AI, 2 controls, 54 dependencies), 2 model
  components, and 6 `binary` hits for pip's vendored `distlib` launcher `.exe` stubs. Zero components for the
  Cline and prettier extension directories (so no npm identity even as a partial), zero for the Chrome
  extension, zero for the MCP configs, zero for the Ollama blobs. The two model components carry no PURL, which
  matches R4 exactly.
- **osquery sees whatever a query names, and only that.** Its coverage here is an artefact of the frozen query
  list as much as of the tables: `vscode_extensions` and `chrome_extensions` worked because the tables exist
  in 5.24.0 and the fixtures carried the files those tables read (`extensions.json`; `Preferences` with a
  profile name and a manifest `key`); `python_packages` found the venv only when told the path; `file` skipped
  every hidden directory under `/home/dev/%%` (15,618 regular files returned, none under `.ollama`, `.vscode`,
  `.config` or `.cursor`), and the MCP configs were reached only because `MCP_CONFIG_PATHS` named them. A fleet
  query that does not already contain the path of the thing does not find the thing.

## Hypotheses

| | Prediction | Outcome |
|---|---|---|
| H1 | Zeek, DNS log, egress find S8 and S9 in all runs via name/SNI; structurally miss S3-S7 | **Supported.** 13 of 13 hosts by SNI and by DNS in 3 of 3 runs; no filesystem surface reported by any network method |
| H2 | Zeek sees S1/S2 only via the peer (`http.log` on 11434/8000), nothing of loopback; `-i any` shows loopback; the pull gives `registry.ollama.ai` | **Supported.** eth0 `http.log`: 4 rows, all from the peer (3 runtime calls plus the C1 GET); `any` `http.log`: 32, 28 and 29 rows in runs 1-3 *[verification fix: was "32"]*, including loopback and Ollama's internal runner; `registry.ollama.ai` in `dns.log` and `ssl.log` every run |
| H3 | osquery finds S1, S7, S7b, S3, S5, S4 (file partial, yara found); S6 only directed; S2 partial; O1 does not match the stub | **Supported except S7b, and the port-ownership half was untestable here.** The prediction that O2 shows 11434 owned by `ollama` and 8000 by `python3` was not observed in any run (`pid = -1` everywhere) because the container lacked `CAP_SYS_PTRACE` (Deviation 4, P2e shows both owners with the capability). O3's `%%` glob skipped the hidden `.ollama` directory, so S7b is a rule-gap miss under the frozen query; the labelled post-hoc P1b with the explicit blob path returns all 5 blobs. O4a returned only `pip` from `/usr/local` (0 of 8), O4b 8 of 8. O1 did not match the stub. The `sigrule` content query works on `yara_file`; the `yara` name also exists in 5.24.0 but does not expose the hidden `sigrule` column (Deviation 2) |
| H4 | Syft finds S6 (8 of 8 with PURL) and S7 (both, MiniLM under its base-model name); misses S7b, S4, S5, S2; S3 at most an npm package | **Supported, S3 stricter than predicted.** 8 of 8 packages with PURLs; `TinyLlama` and `MiniLM-L6-H384-uncased` as `model` without PURL; S3 produced 0 components, not a partial npm identity |
| H5 | Union reaches all surfaces as found or partial; no single method ≥6 found; S4 and S5 found by osquery alone | **Wrong on two of three parts as run, and both falsifications are contingent** *[verification fix]*. osquery scores exactly 6 of 10 at found (the falsifier was "six or more"), but S3's grade rests on the post-run `name`-column read (Deviation 3; without it S3 is a rule-gap miss) and S4's on the post-run `yara` → `yara_file` change (Deviation 2; without it S4 is partial on file presence), so under the literally frozen text osquery scores four and this part of H5 holds. The union misses S7b only on the ten-cell scoring; H5 is worded over nine surfaces, and the union does reach S7 (model files) at found. S4 and S5 by osquery alone holds |
| H6 | Port rules fire on C1 (one FP each for Zeek and osquery); no other rule fires on a control | **Supported.** Zeek Z3 and Z4 on 8080, osquery O2 on 8080; every other rule 0 controls |
| H7 | Syft reproduces R4 on S7/S7b; osquery reaches the store by path | **Supported for Syft, wrong for osquery as pre-registered.** Same two Syft model components as R4 (names, `UNKNOWN` versions, no PURL), nothing in the store; osquery's frozen path rule did not reach the store (hidden-dir semantics), only the post-hoc explicit path did |

For H-AI-ARTIFACT-INVENTORY-01's discovery half this adds, on one host and one fixture set: the network has a
clean view of *remote* AI use (every hostname, every run) and almost none of *local* AI use; the endpoint
agent has the only view of configs, extensions and local runtimes, and that view is exactly as wide as the
query list someone maintained; and the one artifact every method missed under its frozen rules is the same one
R4 found no tool for, the weights sitting in a runtime's own store.

## Post-hoc probes (labelled; not pre-registered; `results/posthoc/`)

- **P1 osquery hidden directories.** `file WHERE path LIKE '/home/dev/.%%'` returns 15,874 regular files (the
  hidden tree, which is mostly Cline), and `path LIKE '/home/dev/.ollama/models/blobs/%'` returns the five blobs
  with sizes (637,699,456 bytes for the weights). `'/home/dev/%%'` returns 16,944 entries (all types), none hidden.
  So the `%%` wildcard does not descend into dot-directories, and `.%%` also matched `..` and re-listed the
  visible tree under `/home/dev/../dev/`, which is why P1d shows the model files there. The rule gap is a glob
  semantics gap, and an analyst who does not know it writes exactly the query that was frozen here.
- **P2 osquery socket-to-process mapping.** In the runs, `listening_ports` and `process_open_sockets` returned
  `pid = -1` and an empty process name for every socket. In a fresh container started with `--cap-add SYS_PTRACE`
  the same query returns `python3` (`openai_compat_stub.py 8000`), `python3` (`http.server 8080`) and `ollama`
  (`ollama serve`, 11434). Docker's default capability set lacks `CAP_SYS_PTRACE`, so root in the container
  cannot read `/proc/<pid>/fd` of another user's process; a real osquery deployment runs with it. This is a
  lab-environment limit, and it did not change any grade: S1 was found through the process rule, S2 was
  pre-registered as partial either way, and C1's false positive fires on the port alone.
- **P3 `vscode_extensions` columns.** The table fills `name` with the full `publisher.name` id from
  `extensions.json` and leaves `publisher` and `publisher_id` empty, so the pre-registered identity was read from
  `name` (Deviation 3).

## Comparison with R4 (`ai-artifact-sbom/`)

| | R4 (SBOM and scanner tooling, filesystem only) | T1 (five methods, live endpoint + network) |
|---|---|---|
| Named GGUF / safetensors | Syft: found as AI, no PURL; Trivy: not found | Syft: identical result; osquery `file` by extension: found |
| Weights in the Ollama store | no tool, any mode | no method under frozen rules; osquery only with the explicit store path (post-hoc) |
| MCP servers | as npm/PyPI packages with advisories (Syft+Grype, Trivy `rootfs`); never as MCP servers; ai-bom sees them in client configs only (E1) | client *configs* found by osquery path + yara content; Syft 0 components for the configs; the installed server packages were not planted here |
| IDE extension | Syft 0 components; Trivy `rootfs` a mislabelled npm package | Syft 0 components again; osquery `vscode_extensions` names it |
| Browser extension, runtimes, network | out of scope | osquery names the browser extension; network methods see remote use completely and local use only via a peer |

The R4 conclusion (the tools reach MCP servers as packages but not model weights in a store, and not the
extension as an extension) stands, and T1 adds that the gap closes for configs and extensions only when the
endpoint agent is told the paths and table names, and never closes for the store without a path the analyst
already knows.

## Timing (secondary, under contention; median and CV over 3 runs, `time.monotonic()`)

| Step | Median | CV | Samples (s) |
|---|---|---|---|
| Zeek over eth0 pcap (~4.7 MB) | 2.24 s | 10.2% | 2.72, 2.18, 2.24 |
| Zeek over `any` pcap (~4.8 MB) | 2.25 s | 4.2% | 2.17, 2.40, 2.25 |
| Syft over the 1.7 GB home | 34.2 s | 73.6% | 110.0, 18.6, 34.2 |
| osquery, 12 queries | 7.65 s | 8.2% | 8.11, 7.65, 6.64 |
| endpoint activity script (incl. tinyllama generate, 8 tokens, 4 threads) | 19.2 s | 8.9% | 19.19, 17.45, 21.66 |
| peer calls (incl. a second generate) | 25.9 s | 16.8% | 26.16, 25.95, 17.76 |

The Syft CV reflects a cold first pass plus contention; no timing comparison is claimed.

## Limits

- One host, one simulated endpoint, one version of each instrument, default configs except the labelled
  post-hoc queries. The network view is a single eth0 tap on one container; a real sensor sees a segment.
- The surfaces are planted, so their shape is known in advance and the rules were written by the same agent
  that planted them. The "found" grades therefore say what the methods *can* see with a competent query,
  not what a team would see with the queries it happens to have; the two cells where the frozen query fell
  short (S7b hidden-dir glob, S6 undirected `python_packages`) are the evidence for how much that matters.
- S2 is a stdlib stub serving the API shape, not vLLM or LM Studio; a real server would carry a recognizable
  process name, which would move osquery's S2 from partial to found and leave every other column unchanged.
- S5 is an authored manifest, not a published extension; `chrome_extensions` read it because the fixture
  carries the `key`, `Preferences` and profile-name structure Chrome writes, which were added after the
  discarded run (Deviation 1), so the grade depends on that structure being present.
- The Docker default capability set removed the socket-to-process join from osquery (P2); the grades did not
  depend on it, but the O2 rows in `results/run*/osquery/` carry `pid = -1` and should not be read as osquery's
  behaviour on a host.
- Dummy keys returned 401/400 as expected; openrouter.ai and huggingface.co returned 200 for unauthenticated
  model listings, which changes nothing here.
- Independently re-run by a second agent (`VERIFICATION.md`); same host, same images and fixture home, so it rules out
  run-to-run and transcription error, not host- or fixture-specific effects.
- The lab makes ~20 HTTPS requests per run to public AI and benign hosts. Nothing employer-related is involved.

## Deviations from the pre-registration

1. **One shake-out run discarded** (`results/run0-discarded/`; its logs and osquery JSON stay in the repo, its pcaps, Zeek logs, Syft JSON and file listing are gitignored like every run's). Three harness bugs
   surfaced in it and were fixed before runs 1-3: the peer image (`python:3.12-slim`) has no `curl`, so the peer
   calls were rewritten with `urllib` (same four calls); the osquery query against `yara` failed with `no such column:
   sigrule`, because in 5.24.0 `yara` resolves without the hidden `sigrule` column while `yara_file` carries it
   *[verification fix: the original said the table is named `yara_file`, not `yara`]*; the Chrome fixture lacked the structure the `chrome_extensions` table needs (a `key` in the
   manifest, a `Preferences` with a profile name) and used ids outside Chrome's `a-p` alphabet, so
   `fixtures/make_chrome_fixtures.py` now generates RSA keys and derives the ids the way Chrome does. The run-0
   `chrome_extensions` result was 0 rows ("Failed to acquire the name of the following profile").
2. **O7b table name**: `yara` → `yara_file`. Both names exist in 5.24.0 (`PRAGMA table_info(yara)` lists path, matches,
   count, sig_group, sigfile, strings, tags); only `yara_file` accepts the hidden `sigrule` constraint *[verification fix]*.
3. **O5 identity normalization** in scoring: the id is taken from `name` when `publisher` is empty and `name`
   contains the dot (P3). The rule (id ∈ `AI_EXT_IDS`) is unchanged; without the normalization the first
   scoring pass graded S3 as a rule-gap miss, which was a harness error, not an osquery one.
4. **O2 owner resolution** failed in every run (`pid = -1`) because the container lacked `CAP_SYS_PTRACE`
   (P2e shows it working with the capability). The pre-registration said the port would be "reported with the
   owning process name"; it was reported without one.
5. **O1 identifier** in the fired-rule sets was changed from `name pid=N` to `name + first two cmdline tokens`
   so that run-to-run variance is measured on stable identifiers; pids moved to the detail field. Cosmetic.
6. **Zeek image age**: `zeek/zeek:8.0.11` was last updated 2026-10-26, exactly 14 days before the run date.
7. **osquery `listening_ports` rows appear twice** per socket in the run output (both rows `pid = -1`); the
   false-positive count is by distinct control (1), not by row (2).
8. **`copilot.com`** (redirect from `copilot.microsoft.com`) is not in the frozen `AI_DOMAINS`, so Z1/Z2/D1 did
   not match it while E1 flagged it; it is attributed to S9 in the ground-truth map, and S9 was found by every
   network method through the other five hosts regardless.
9. **Clock** at freeze: 0.607 s slow of NTP, above the methodology's pre-run guideline; durations are monotonic
   and unaffected, wall-clock stamps in `COMMANDS.log` and the activity logs may be off by that much.
10. **Fixture home size** is about 1.7 GB on disk (the Ollama blob is a copy of the GGUF, the GGUF itself a
    hardlink of R4's T1), larger than the "about 60 MB of wheels" the Cost section counted because it did not
    count the local model copies.
11. **Recorded by the verifier, not in the original list** *[verification fix]*: the scoring ground truth gained
    `copilot.com` in `S9_HOSTS` after the discarded run (the code comment says so), i.e. after the freeze; the
    Chrome fixture was rebuilt after the freeze too (Deviation 1). The sidecar base `alpine:3.22` is a local image
    created 2026-11-05 (Alpine 3.22.8), inside the two-week cooldown the pre-registration applied to osquery 5.24.1;
    the lab's written methodology carries no cooldown rule, so this and Deviation 6 are self-imposed conventions.
    The post-hoc P1-P3 SQL was not written to `COMMANDS.log` (the verifier re-derived it and got the same counts).
    The first scoring pass's `fired.json` files were overwritten by the `--score-only` re-score and do not survive.
    The endpoint's services bound `0.0.0.0` on the `t1lab` bridge (needed for the peer calls) with nothing published
    to the host, which is "lab network only" rather than strictly localhost.

---
type: benchmark-results
area: T1-shadow-ai-discovery
date: 2026-11-16
evidence_tier: B (first-party, one container, post-hoc probe, agent-run, not independently re-run)
---

# Post-hoc probe (2026-11-16): where osquery's `%%` skips dot-directories

**What this is.** A labelled post-hoc probe, not covered by the frozen pre-registration, run after an external review
(Fable, 2026-11-16) read osquery's source and argued that the recursive `%%` wildcard skips dot-entries only at the
first level under the query's base path, not at every depth. `RESULTS.md` words the hidden-directory result more
generally ("`%%` does not descend into dot-directories"); this file tests the narrower reading. No tracked file was
modified.

**Source reading (osquery tag 5.24.0).** `osquery/filesystem/filesystem.cpp` `genGlobs`: a trailing `**` is
replaced by `*`, the first level is expanded by `platformGlob`, and each directory returned is walked by
`dfsTraverseDirectories`, which iterates every entry with `fs::directory_iterator` and has no dot test.
`osquery/filesystem/posix/fileops.cpp` `platformGlob` calls `::glob(..., GLOB_TILDE | GLOB_MARK | GLOB_BRACE, ...)`
without `GLOB_PERIOD`, so a leading-dot name is not matched at the globbed level.

**Run.** 2026-11-16, Docker `python:3.12-slim` (image id `sha256:78976a69…a0db`, created 2026-11-05), osquery 5.24.0
installed from `osquery_5.24.0-1.linux_amd64.deb`, sha256 `8ae0416d85336a1aea6883920ae9c2751a98538fe0bb624822e92934d3be5592`
(the same package and hash as the T1 runs). Script: `posthoc_glob_probe_2026_11_16.sh`. Raw output:
`results/posthoc/P4_glob_first_level_2026-11-16.txt`. Fixture: dot-directories directly under the home
(`.ollama/models/blobs/`, `.cursor/`), dot-directories nested under visible directories (`projects/x/.cursor/`,
`projects/x/.vscode/`, `a/.hidden/b/`), a dot-file in a visible directory (`projects/x/.mcp.json`) and one visible file.

## Result

| Query | Returned | Skipped |
|---|---|---|
| `path LIKE '/home/dev/%%'` | 5 files: `a/.hidden/b/nested.txt`, `projects/x/.cursor/mcp.json`, `projects/x/.mcp.json`, `projects/x/.vscode/mcp.json`, `visible.txt` | `.cursor/mcp.json` and `.ollama/models/blobs/sha256-test`, the two under dot-directories directly below `/home/dev` |
| `path LIKE '/home/%%'` | all 7 files, including `/home/dev/.cursor/mcp.json` and `/home/dev/.ollama/models/blobs/sha256-test` | none |

So on Linux, `%%` skips a dot-directory only when it sits directly under the query's base path; dot-directories
deeper in the tree are walked, and a query based one level higher reaches the home-level ones. This matches the
source reading and T1's verification note that the dot-containing rows under `%%` were hidden files in visible
directories. The T1 numbers stand (the store, `.vscode`, `.config` and `.cursor` all sat directly under `/home/dev`);
the general wording in `RESULTS.md` ("does not descend into dot-directories") should be read as "does not descend
into dot-directories directly under the base path". Windows uses a separate implementation and was not tested.

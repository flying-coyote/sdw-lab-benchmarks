---
type: benchmark-posthoc-observation
area: R4-ai-artifact-inventory
date: 2026-11-16
status: post-hoc, not pre-registered, read-only, one host; agent-run; follows posthoc-ollama-api-digest-2026-11-16.md
---

# Post-hoc observation: `/api/show` names the weights blob (2026-11-16)

Same Beelink lab host and Ollama service (`/api/version` → 0.20.6). Read-only; nothing pulled, written or re-tagged.

```text
$ curl -s http://127.0.0.1:11434/api/show -d '{"model":"tinyllama"}'   # modelfile, FROM line only
FROM /usr/share/ollama/.ollama/models/blobs/sha256-2af3b81862c6be03c769683af18efdadb2c33f60ff32ab6f83e42c043d6c7816
```

Reading: the Modelfile `/api/show` returns names the weights blob itself by its SHA-256 (the same hash as
`fixture-sha256.txt:1` and `:10`), while `/api/tags` returns the manifest's SHA-256 (previous note). So the
weights-level digest is available from the runtime API one call further in. The manifest digest changes when a
model is rebuilt from the same weights with a different template, system prompt or parameters (the manifest's
other layers change); that, `ollama cp` re-tags, actual weight swaps and `/api/ps` (empty, nothing loaded at the
time) were not tested here.

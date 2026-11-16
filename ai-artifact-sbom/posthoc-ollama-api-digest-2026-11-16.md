---
type: benchmark-posthoc-observation
area: R4-ai-artifact-inventory
date: 2026-11-16
status: post-hoc, not pre-registered, read-only, one host; agent-run
---

# Post-hoc observation: what Ollama's `/api/tags` digest names (2026-11-16)

Question: R4 found no scanner reads Ollama's store. Does the runtime's own API expose a content digest, and is it
the weights blob's hash or the manifest's?

Host: the same Beelink lab host R4 used; Ollama service reports `{"version":"0.20.6"}` from `/api/version`.
Read-only calls only; nothing was pulled, written or re-tagged.

Commands and output (verbatim, 2026-11-16):

```text
$ curl -s http://127.0.0.1:11434/api/tags   # filtered to tinyllama
tinyllama:latest 2644915ede352ea7bdfaff0bfac0be74c719d5d5202acb63a6fb095b52f394a4

$ sha256sum /usr/share/ollama/.ollama/models/manifests/registry.ollama.ai/library/tinyllama/latest
2644915ede352ea7bdfaff0bfac0be74c719d5d5202acb63a6fb095b52f394a4  .../library/tinyllama/latest

$ manifest layers[].digest
sha256:2af3b81862c6be03c769683af18efdadb2c33f60ff32ab6f83e42c043d6c7816   # the GGUF weights blob (fixture-sha256.txt:1, :10)
sha256:af0ddbdaaa26f30d54d727f9dd944b76bdb926fdaf9a58f63f78c532f57c191f
sha256:c8472cd9daed5e7c20aa53689e441e10620a002aacd58686aeac2cb188addb5c
sha256:fa956ab37b8c21152f975a7fcdd095c4fee8754674b21d9b44d710435697a00d
```

Reading: on this host and version, the `digest` that `/api/tags` returns is the SHA-256 of the model's manifest
file, and the manifest names the weights blob by its own SHA-256. So the API digest names the weights
transitively: a re-tag that copies the manifest (R4 variant V3) keeps the same API digest, and a change to the
weights blob would change the manifest and so the digest. Ollama documents the field as "SHA256 digest
identifier of the model contents" (docs.ollama.com/api/tags, read 2026-11-16). Not tested: other Ollama versions,
`/api/ps`, or an actual weight swap.

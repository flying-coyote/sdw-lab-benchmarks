# EvidenceForge external-validity arm -- machine-generated summary

Tier B. Corpus: /tmp/claude-1000/-home-jerem-project1/3f346061-99d6-407a-9395-0757dbd37f05/scratchpad/ef-branch. Provenance: EvidenceForge @ 7cbcc6a9,
scenario `scenarios/branch-office-example/scenario.yaml`, eval 97.12/100
acceptance_passed=True.

See ../RESULTS-evidenceforge-arm-2026-07-04.md for the full write-up, method, and honest caveats.
This file is the auto-generated per-run companion (mirrors the pattern in ../results/RESULTS.md).

| rule | stage | ATT&CK | storyline target | result | matches | false positives | precision |
|---|---|---|---|---|---|---|---|
| rdp_lateral.yml | lateral movement | T1021.001 | evt-004 | DETECTED | 138 | 137 | 0.0072 |
| c2_domain.yml | C2 | T1071.001 | evt-006 | MISSED | 0 | 0 | None |
| encoded_powershell.yml | execution | T1059.001 | none planted | N/A | 0 | 0 | None |
| nomfa_privesc.yml | priv-esc | T1098 | none planted | N/A | 0 | 0 | None |

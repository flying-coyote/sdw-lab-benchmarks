# De-gamed BENCH-A — context collapse vs unmodified upstream SigmaHQ on real APT29 data

**Tier B · real public attack data · third-party rules.** Removes the gameability the lab-built R1/R2
carried: the rules are cloned **verbatim from SigmaHQ** (run via pySigma→SQL with only a table-name
substitution), the data is the **MITRE ATT&CK APT29 evaluation** telemetry (OTRF/Mordor), the
adversary-tail/routine split is each rule's **own `attack.` tags** against MITRE's published APT29
technique set (not our judgment), and Store N's coarsening is the documented volume-driven default
(`STORE-N-NORMALIZATION.md`), applied blind to the rules. Store F is the fidelity ("good pipeline") store.

**Metric (no lab-defined needle):** per rule that fires on Store F, `recall_loss = 1 − matches_N/matches_F`,
decomposed into the two failure modes R1 named — **blinding** (recall→reduced, clipped ≥0) and **over-match**
(matches_N > matches_F, the cry-wolf / precision-loss mode where coarsening broke an exclusion filter).

| class | rules fired on F | mean recall-loss (blinding) | went fully blind (→0) | over-matched (cry-wolf) |
|---|--:|--:|--:|--:|
| **adversary-tail** (APT29 technique) | 29 | **0.3477** | 9 (31.0%) | 1 (3.4%) |
| **routine** (other technique) | 25 | 0.16 | 4 (16.0%) | 0 (0.0%) |

**Δ(adversary-tail − routine) mean recall-loss (blinding) = 0.1877.**

Rules scanned: 2853; routed to a supported logsource: 2277;
compiled: 2276; fired on Store F: 54.

## Adversary-tail rules blinded by the coarsening (recall → 0)

| rule | technique | logsource | matches |
|---|---|---|---|
| `Uncommon Connection to Active Directory Web Servic` | t1087 | network_connection | 10 → 0 |
| `Windows Screen Capture with CopyFromScreen` | t1113 | ps_script | 2 → 0 |
| `Suspicious FromBase64String Usage On Gzip Archive ` | t1132 | ps_script | 2 → 0 |
| `Malicious PowerShell Keywords` | t1059 | ps_script | 2 → 0 |
| `Potential Suspicious PowerShell Keywords` | t1059 | ps_script | 3 → 0 |
| `Suspicious New-PSDrive to Admin Share` | t1021 | ps_script | 1 → 0 |
| `PowerShell Base64 Encoded FromBase64String Cmdlet` | t1059, t1140 | process_creation | 1 → 0 |
| `Malicious Base64 Encoded PowerShell Keywords in Co` | t1059 | process_creation | 1 → 0 |
| `Suspicious Execution of Powershell with Base64` | t1059 | process_creation | 1 → 0 |

## Reading

This is the de-gamed test the R1/R2 Karen flag demanded. If the disproportionality is real, it survives
when the lab no longer chose the rules, the attack, or the split: unmodified SigmaHQ rules detecting
APT29's own techniques should lose more recall under the documented coarsening than rules for other
behaviours, and Store F (the faithful store) is the null's fair baseline. The headline Δ is the measured
gap; the "went blind" column is the security-relevant failure — a real detection that silently stops
firing once the field it keys (a long command line, a rare DNS name, an auxiliary field) is coarsened
away. Tier B, single machine, one public dataset; the transferable finding is the *direction and
magnitude of the gap under a documented coarsening*, measured with nothing lab-authored in the loop.

# Sigma detection execution vs the testbed (results)

**Tier B.** Real Sigma rules compiled to SQL via pySigma and executed over the fidelity store
(Store F), scored against the planted-chain ground truth. C4 measured whether rules *compile*; this
measures whether they *fire correctly* end-to-end — portable rule → compiler → OCSF store → catch.

**4/4 planted-chain stages detected.**

| stage | ATT&CK | compiled | detected | matches | false positives | precision |
|---|---|---|---|---|---|---|
| execution | T1059.001 | True | ✓ | 1 | 0 | 1.0 |
| priv-esc | T1098 | True | ✓ | 1 | 0 | 1.0 |
| lateral movement | T1021 | True | ✓ | 2960 | 2959 | 0.0003 |
| C2 | T1071 | True | ✓ | 1 | 0 | 1.0 |

## Reading

Every rule compiled cleanly through pySigma to SQL and ran over the OCSF store, and each detected its
planted stage — so detection-as-code survives the round trip from a portable rule to a query over a
normalized OCSF store, which is the end-to-end claim C4's compile-time result couldn't make on its
own. The precision column is the honest half: the specific rules (encoded PowerShell on a named host,
AttachUserPolicy without MFA, a known C2 domain) fire cleanly with no false positives, while the
generic one — "any RDP connection" — catches the lateral-movement needle *and* all the benign
port-3389 background, so its precision is low. That's the real SOC trade-off (a portable rule is only
as good as its specificity) measured rather than assumed, and it's why the OCSF grounding matters: the
rule can only be precise about fields the normalization preserved. Tier B, one synthetic chain; the
detection/precision split is the transferable finding.

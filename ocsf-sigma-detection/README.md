# Sigma detection execution vs the testbed

C4 measured whether a Sigma rule *compiles* to four backends. This measures whether compiled rules
*fire correctly* end-to-end: real Sigma rules → pySigma → SQL → executed over the fidelity store
(Store F) → do they detect the planted attack chain, and how much background do they also match?

## Result (Tier B)

**4/4 planted-chain stages detected.** Every rule compiled and ran over the OCSF store and caught its
stage — detection-as-code survives the full round trip a compile-time check can't prove. The precision
split is the honest half: the specific rules (encoded PowerShell on a named host, AttachUserPolicy
without MFA, a known C2 domain) fire at precision 1.0; the generic "any RDP connection" rule detects
the lateral-movement needle but also matches 2,960 benign port-3389 connections (precision 0.0003) —
the real SOC noise problem, and why the rule can only be as precise as the fields the OCSF
normalization preserved. Full numbers in [results/RESULTS.md](results/RESULTS.md).

## Run it

```bash
pip install -r ocsf-sigma-detection/requirements.txt
# Store F must be built (see bench-a-context-collapse)
python ocsf-sigma-detection/run.py
```

Rules in `rules/` (committed); each runs against the Store F table named in the runner registry.
Tier B, one synthetic chain. Complements C4 (compile-time portability) with execution-time detection.

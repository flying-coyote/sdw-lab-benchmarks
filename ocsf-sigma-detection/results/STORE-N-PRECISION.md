# Sigma over the coarse store — recall & precision under context-collapse (R1)

**Tier B · synthetic testbed · single machine · one planted chain.** The same compiled Sigma rules that
fire correctly over the fidelity store (Store F, see RESULTS.md) run here over BENCH-A's coarse store
(Store N) — the documented volume-driven normalization. The rule is portable and unchanged; the only
variable is the store, so any change in recall or precision is a property of the normalization. This is
the detection-as-code corollary of **H-OCSF-CONTEXT-COLLAPSE-01 (detection-as-code corollary)**: not "does a query battery lose fidelity"
but "does the alert still fire, and how much noise rides with it."

| coarsening mechanism | rule | recall F→N | precision F→N | matches F→N | outcome |
|---|---|---|---|---|---|
| rare-DNS sampling | `c2_domain.yml` | 1→0 | 1.0→0.0 | 1→0 | blind |
| cmd-line truncation | `encoded_powershell.yml` | 1→1 | 1.0→1.0 | 1→1 | survived |
| absence-coercion (MFA absent -> false) | `nomfa_privesc.yml` | 1→1 | 1.0→0.0037 | 1→268 | cried wolf |
| flow rollup | `rdp_lateral.yml` | 1→1 | 0.0003→0.0003 | 2960→2960 | survived |

## Reading

Coarsening does not degrade detection uniformly — it degrades the rules whose keying field the
normalization happened to touch, and the failure mode depends on *which* knob touched it:

- **Rare-DNS sampling makes the rule go blind.** The C2 domain is resolved exactly once in the corpus,
  and Store N's "drop DNS queries seen fewer than 3 times" rule — a generic cardinality-reduction
  default, chosen blind to the battery — removes precisely that one resolution. The IOC rule that fires
  cleanly on Store F (recall 1) cannot fire on data that was discarded (recall 0). The store didn't
  mis-rank the alert; it deleted the evidence.
- **Absence-coercion makes the rule cry wolf.** Store F keeps an MFA-*presence* flag, so "AttachUserPolicy
  where MFA is absent" matches the single planted priv-esc and nothing else (precision 1.0). Store N
  coerces absent→false, erasing the distinction between "no MFA challenge was recorded" and "MFA was
  evaluated and failed," so the same rule now also matches every routine MFA failure — the alert still
  contains the true positive (recall holds) but is buried in false positives (precision collapses).
- **Truncation and rollup are the controls.** `-EncodedCommand` sits early enough in the command line to
  survive the 64-character cap, and the hostname Store N keeps is the one the rule needs, so the
  PowerShell rule is untouched — though that survival is dose-dependent: a shorter cap would blind it,
  which is exactly the curve R2 sweeps. The RDP traffic is temporally sparse enough that 5-minute flow
  rollup coalesces nothing (connection count = flow count), so that rule is unchanged here; rollup's
  effect is a property of the traffic's density, not a constant.

The transferable finding is that the cost of normalization to detection is not a single number — it is
two distinct failure modes (blindness and noise) that land on whichever rule keys on the field a given
coarsening step dropped or flattened, which is why fidelity has to be evaluated against the detections
you run, not in the abstract. Tier B, one synthetic chain; the per-mechanism split is the transferable
part, the magnitudes are this corpus's.

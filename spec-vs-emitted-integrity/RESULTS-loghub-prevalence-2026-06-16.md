# SPEC-INTEGRITY real-log prevalence leg — spec-vs-emitted disagreement measured on REAL emitted logs (2026-06-16)

The prevalence gate H-SPEC-INTEGRITY-01 left open: the synthetic leg (2026-06-15) and the real-vendor
doc-replay leg (2026-06-16) grounded the *mechanism* but explicitly were "existence/format-class, NOT a
prevalence rate" — a rate needs real *emitted* logs (public vendor docs are internally self-consistent, so
replaying them discovers no new disagreement). This leg measures a real spec-vs-emitted **deviation rate on
real emitted logs**, code-only.

**The realistic vs ideal call (owner-directed):** the ideal — a disagreement rate over real *commercial
security-vendor* telemetry — is impractical (availability + the security-telemetry-injection boundary). The
appropriate-enough real substitute: **LogHub** (github.com/logpai/loghub) 2,000-line real-production-log
samples for 6 systems (Linux, OpenSSH, Apache, HDFS, Zookeeper, Proxifier — 12,000 real lines), parsed
**code-only** against each format's **published-standard grammar** (RFC3164 BSD syslog, Apache httpd
error_log, the documented HDFS/Zookeeper/Proxifier layouts). Code-only diff, no LLM, no rows into model
context — the injection boundary doesn't bind. `loghub_prevalence.py` + `results/loghub_prevalence.json`.
Tier B.

## Result — real spec-vs-emitted deviation is real, severe where it occurs, and source/config-dependent

| system | format class | conform | deviation | failure mode |
|---|---|--:|--:|---|
| **Linux** | RFC3164 syslog | 56.9% | **43.1%** | SILENT (program `sshd(pam_unix)` vs documented `sshd`) |
| OpenSSH | RFC3164 syslog | 100.0% | 0.0% | — (emits clean `sshd[pid]`) |
| Apache | httpd error_log | 100.0% | 0.0% | — |
| HDFS | positional-prefix | 100.0% | 0.0% | — |
| Zookeeper | `ts - LVL [thread] - msg` | 91.8% | 8.2% | nested brackets in thread (`[QuorumPeer[myid=1]…]`) |
| Proxifier | `[ts] prog - msg` | 63.6% | 36.4% | space-bearing program (`svchost.exe *64`) |

**Aggregate: 14.6% deviation across 12,000 real lines** (7.2% counted silent conservatively, 7.4% loud).

**The robust, security-critical anchor (code-verified):** the *same daemon* (sshd) emits its program token
two ways across two real deployments — the OpenSSH corpus emits `sshd` (0% deviation), the Linux corpus
emits `sshd(pam_unix)` for **677 of 677** sshd events. A detection or normalization keyed on the documented
program name `sshd` **silently misses 100% of the real sshd auth events** (including the authentication
failures and break-in attempts in the corpus) on the PAM-annotated deployment — the events are present,
under a program token the rule never matches, and nothing fires. Same for `su(pam_unix)` (172 events) and
`ftpd` was the largest tag (916). This is the hypothesis's silent-misalignment, on real emitted logs, with a
concrete security consequence.

## What it does to the hypothesis — and the honest scope

This is the first time the silent-misalignment is measured on **real emitted logs** (not synthetic, not
doc-replay), with a real prevalence and a security-critical instance — the prevalence dimension the gate
wanted. It generalizes the failure mode off PAN-OS onto real OS/infra sources. But four caveats bound it:

1. **The deviation rate is the robust metric; the silent-vs-loud split is consumer-dependent.** A
   strict-regex consumer fails LOUD (null) on a deviation; a positional/delimiter consumer (the
   hypothesis's subject) reads it SILENTLY wrong-but-present. This run counts silent conservatively (only
   Linux's tag annotation); the Zookeeper nested-bracket and Proxifier space-in-program deviations would
   also be silent under a delimiter consumer, so **true silent ≥ 7.2%**. That "spec-faithful" is itself
   underdetermined (a bracket-field parser and a delimiter parser disagree on what even *counts* as a
   deviation) is the hypothesis's "parsing layer nobody owns" point, not a measurement defect.
2. **The `sshd(pam_unix)` form is a known syslog facility-annotation convention; mature SIEM parsers may
   strip it.** The miss is real for a parser faithful to the *documented standard* (RFC3164 alphanumeric
   tag = `sshd`); catching it requires handling an emit convention the standard never documented — which is
   exactly the "you can't trust the published spec, you must measure the real emit" claim. It is not a claim
   that every parser in the field misses it.
3. **Prevalence is deployment/config-dependent** (0% vs 100% for the *same* daemon), not a fixed vendor
   property — so the honest reading is "spec-vs-emitted disagreement is real and can be total, but its
   occurrence depends on the source's logging config," which tempers any universal-high-rate framing.
4. **Scope: real but OS/infra/app logs, NOT commercial security-vendor telemetry.** It transfers to the
   positional/prefixed format *class* (the hypothesis's structural claim); the security-vendor-specific
   prevalence stays an extrapolation anchored on the PAN-OS PR-294 first-hand instance.

## Gate disposition

Route through karen → hypothesis-validator → contradiction-detector. Recommended: attach as the **real-log
prevalence leg** and move **3/5 → 3.5/5** — the gate's standing "needs a real-log corpus" requirement is
now substantively addressed with a real prevalence (0–43% per source, a code-verified 100%-silent-miss of
real sshd auth events under a documented-name parser), capped at 3.5 (not 4) by the OS-vs-security-vendor
scope, the config-dependence, and the consumer-dependent silent/loud split. No contradiction — complements
the synthetic mechanism leg, the real-vendor doc-replay leg, and the C1 mapping-fidelity evidence; supports
the normalize-loses-fidelity side near H-OCSF-CONTEXT-COLLAPSE-01. Anchored on the PAN-OS PR-294 authority.
A move to 4/5 would need the real *security-vendor* prevalence rate (boundary-permitting) or a
production-caught (not config-inferred) disagreement.

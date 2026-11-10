### Benchmark Claim Reviews

* **CLAIM 1 (H1 falsified on a6): AGREE.**
  The pre-registered criteria explicitly designated the planted `bash.exec` as "not truth for any rule" and specified falsification if $a6$ scored NOISY on any seed. Because $a6$ achieved $p=0.5$ ($<0.9$ threshold) under the frozen ground truth, H1 is strictly falsified; treating the post-hoc re-scoring as a truth redefinition rather than a validation is methodologically sound.
  * *Overreach check:* No overreach.

* **CLAIM 2 (H2 falsified): AGREE.**
  Rule $b3$ achieved precision of $\sim 0.20$, failing both the $[0.6, 0.9)$ absolute precision target and the $\ge +0.3$ gain threshold over $a5$ (yielding $-0.44$ at event level and $\approx +0.08$ at session level). The verifier's ceiling analysis correctly demonstrates that with at most 10 direct true positives and $\ge 10$ false positives from lookalike $LA5$, the band was mathematically unreachable.
  * *Overreach check:* No overreach.

* **CLAIM 3 (H3 holds): AGREE.**
  Under the pre-registered conditions, $b4$ achieved zero false positives on all seeds across both engines, $1.0$ recall on direct plants, and precision $1.0$, satisfying DETECTED status.
  * *Overreach check:* **Flagged for generalizability overreach.** While the formal hypothesis holds on this dataset, $b4$'s performance is heavily dependent on specific content matching (the fixture credential prefix `api03-`) and a rigid burst heuristic rather than generic sequence detection.

* **CLAIM 4 (H4 holds): AGREE.**
  Direct session sequence rules ($b1$–$b4$) exhibited $0.0$ recall on delegated chains, whereas the cross-session graph rules ($c1$, $c2$) achieved $1.0$ recall across all 20 chains while matching the precision tiers of $b3$ (NOISY) and $b4$ (DETECTED).
  * *Overreach check:* No overreach in the claim itself; the verifier correctly notes the ecological caveat that $c1$/$c2$ depend on `delegation_parent_uid`, a field not populated by production event sources.

* **CLAIM 5 (H5 holds, H6 falsified): AGREE.**
  Tier (a) rules yielded identical results across both engines while DuckDB failed on correlation rules due to the unescaped reserved word `end`, satisfying H5; meanwhile, $b1$ and $b2$ produced identical false-positive counts across all seeds, refuting H6 because $LA3$ sessions lacked leg 1 entirely.
  * *Overreach check:* No overreach.

---

### Evaluation of the Essay Claim

> *"The trifecta is easier to detect as a sequence of legs inside one session than as any single step"*

**No, nothing in this benchmark justifies this claim.** The empirical results directly contradict it on three distinct fronts:

1. **Single-step content detection outperformed pure sequences:** Single-step rule $a4$ achieved perfect detection ($p=1.0$, DETECTED) on its own without multi-leg correlation, whereas intra-session sequence rule $b3$ collapsed to $p \approx 0.20$ (NOISY).
2. **Intra-session sequences failed on modern agent architectures:** All single-session sequence rules ($b1$–$b4$) scored exactly $0.0$ recall on delegated chains, missing 50% of the planted attacks entirely.
3. **Sequence detection required content filtering or cross-session walks:** Multi-leg detection only succeeded when either augmented with content-level fixture matching ($b4$) or expanded into cross-session graph walks ($c1$/$c2$), invalidating the assertion that a simple *sequence of legs inside one session* makes detection easier.

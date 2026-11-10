CLAIM 1: PARTLY
While the per-engine slot classifications are accurately reproduced by the data, claiming that the marginal-step column credits all 22 slots is an overclaim and factual error; only 14 slots belong to the marginal set, whereas all 22 belong to `reaches_steps`.

CLAIM 2: SUPPORTED
The data confirms that E1 generated zero planted alerts because valid credentials passed the auth gate, and D1/D7 produced zero alerts because planted pooled-account events stayed beneath the volume ceilings. A relevant experimental caveat is that these ceilings were arbitrary round numbers selected by the author to ensure planted volumes stayed under them.

CLAIM 3: PARTLY
The recall (1.0), precision ranges (0.03–0.08), and missed compromise are verified by the data, but the claim misstates the realised unpinned background share as 30% instead of the observed 21–23%. Furthermore, asserting equivalence to the "2026 state of PyPI attestations and Hugging Face artifacts" introduces an unverified outside fact that lacks any supporting source or data.

CLAIM 4: SUPPORTED
The reported recall drops, precision scores, engine parity under case folding, and DuckDB's improved state on E5c match the data precisely. Evaluating H5 as holding on E5a and E5c while remaining untested on E5b is correct because E5b lacked the pre-registered mixed-case planted content.

CLAIM 5: PARTLY
While the mechanism set's CAUGHT share does exceed the rule set's by the reported factor of four to eight across all seeds, claiming all text checks landed NOISY or MISSED is contradicted by E5c achieving CAUGHT on DuckDB. Additionally, it omits the caveat that structural catch E3 achieved precision 1.0 by construction because the background dataset contained zero non-approved readers.

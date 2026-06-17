"""BENCH-C v2 — Okapi BM25-lite over entity docs (committed BEFORE the scored re-run).

Addendum §4: hybrid retrieval for the LOOKUP class (A2/A6/A8) adds a real BM25 / keyword channel
alongside the existing vector top-k, UNIONed before the locked ego traversal, so an exact substring
(a PowerShell command, a C2 domain, a specific uid) is findable by literal match, not only by vector
similarity at ~7 events/seed. If `rank_bm25` is importable we use it; otherwise this documented
tokenized Okapi-BM25 implementation is the fallback — NOT a bare substring hack.

This is a retrieval-STRATEGY change. It does NOT touch K_SEED / NODE_BUDGET / HOPS / EDGE_BUDGET
(those stay at the v1 locked values); the union is taken before the same locked ego traversal runs.

Okapi BM25 (Robertson/Sparck-Jones), standard form:
    score(D, Q) = sum_{t in Q} IDF(t) * f(t,D)*(k1+1) / ( f(t,D) + k1*(1 - b + b*|D|/avgdl) )
    IDF(t) = ln( 1 + (N - n_t + 0.5) / (n_t + 0.5) )            # non-negative ("lite") IDF
k1, b are the standard 1.5 / 0.75 (see bench_c_v2_config). Deterministic: pure function of the
fixed entity-doc corpus + the query string; ties broken by doc id so order is reproducible.
"""
import math
import re

# Try the real library first (addendum §4 prefers rank_bm25 when importable).
try:
    from rank_bm25 import BM25Okapi as _BM25Okapi  # type: ignore
    HAVE_RANK_BM25 = True
except Exception:
    _BM25Okapi = None
    HAVE_RANK_BM25 = False

_TOKEN = re.compile(r"[A-Za-z0-9_.:@\-]+")


def tokenize(text):
    """Lowercase alnum/.:@-_ tokens. Keeps IPs, uids, domains, and base64-ish substrings whole-ish
    so a literal needle (a uid like `api-needle-nomfa`, a domain `cdn-telemetry-sync.net`) is a
    matchable token rather than being shredded."""
    return [t.lower() for t in _TOKEN.findall(text or "")]


class BM25Lite:
    """Documented fallback Okapi-BM25 over a fixed list of (doc_id, doc_text). Used only when
    rank_bm25 is unavailable. Same ranking contract as rank_bm25.BM25Okapi.get_scores."""

    def __init__(self, doc_ids, docs, *, k1=1.5, b=0.75):
        self.k1, self.b = k1, b
        self.ids = list(doc_ids)
        self.corpus = [tokenize(d) for d in docs]
        self.N = len(self.corpus)
        self.doc_len = [len(d) for d in self.corpus]
        self.avgdl = (sum(self.doc_len) / self.N) if self.N else 0.0
        # document frequency per term
        df = {}
        for toks in self.corpus:
            for t in set(toks):
                df[t] = df.get(t, 0) + 1
        self.idf = {t: math.log(1 + (self.N - n + 0.5) / (n + 0.5)) for t, n in df.items()}
        # term frequency per doc (precomputed)
        self.tf = []
        for toks in self.corpus:
            counts = {}
            for t in toks:
                counts[t] = counts.get(t, 0) + 1
            self.tf.append(counts)

    def get_scores(self, query):
        q_terms = tokenize(query)
        scores = [0.0] * self.N
        for i in range(self.N):
            tf_i, dl = self.tf[i], self.doc_len[i]
            denom_norm = self.k1 * (1 - self.b + self.b * (dl / self.avgdl if self.avgdl else 0))
            s = 0.0
            for t in q_terms:
                f = tf_i.get(t)
                if not f:
                    continue
                s += self.idf.get(t, 0.0) * (f * (self.k1 + 1)) / (f + denom_norm)
            scores[i] = s
        return scores

    def topk(self, query, k):
        scores = self.get_scores(query)
        order = sorted(range(self.N), key=lambda i: (-scores[i], self.ids[i]))
        # keep only docs with a non-zero keyword match (a zero-score "top-k" would be noise)
        return [self.ids[i] for i in order[:k] if scores[i] > 0.0]


def build_bm25(doc_ids, docs, *, k1=1.5, b=0.75):
    """Factory: returns (engine, path_label). Prefers rank_bm25 when present."""
    if HAVE_RANK_BM25:
        tok = [tokenize(d) for d in docs]
        bm = _BM25Okapi(tok, k1=k1, b=b)

        class _Wrap:
            def topk(self, query, k):
                scores = bm.get_scores(tokenize(query))
                order = sorted(range(len(doc_ids)), key=lambda i: (-scores[i], doc_ids[i]))
                return [doc_ids[i] for i in order[:k] if scores[i] > 0.0]
        return _Wrap(), "rank_bm25.BM25Okapi"
    return BM25Lite(doc_ids, docs, k1=k1, b=b), "BM25Lite (documented Okapi fallback; rank_bm25 unavailable)"

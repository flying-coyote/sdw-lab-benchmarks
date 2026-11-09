"""R6 generator: synthetic OCSF 1.9.0 API Activity records with the ai_operation profile.

One record = one model API request. Text comes from real files (CPython stdlib code, the lab's public
markdown) or, for the high-entropy control, Zipf-sampled synthetic words. Token counts use tiktoken
o200k_base as a counting proxy; a full-context prompt's token count is the sum of its segments' counts.

    python generate.py --tier coding --corpus real --seed 0
Writes data/<tier>-<corpus>-s<seed>.arrow (uncompressed Arrow IPC) plus a JSON sidecar with realized volume.
See PREREGISTRATION.md for the parameters and their basis.
"""
import argparse
import glob
import hashlib
import json
import os
import random

import numpy as np
import pyarrow as pa
import pyarrow.compute  # noqa: F401
import pyarrow.feather as feather
import tiktoken

HERE = os.path.dirname(os.path.abspath(__file__))
LAB = os.path.dirname(HERE)
DATA = os.path.join(HERE, "data")
ENC = tiktoken.get_encoding("o200k_base")

TIERS = {
    # target billed tokens per user-day, users per corpus, system prompt tokens, session-length mean,
    # delta median tokens, output median tokens, lognormal sigma, request interarrival seconds
    "coding": dict(target=23_500_000, users=2, sys_tokens=15_000, sess_mean=40, delta_med=800,
                   out_med=300, sigma=1.0, gap=20, max_req=120, tools=True),
    "chat": dict(target=200_000, users=100, sys_tokens=1_000, sess_mean=6, delta_med=80,
                 out_med=400, sigma=0.8, gap=60, max_req=60, tools=False),
}
TOOLS = ["Read", "Grep", "Bash", "Edit", "Glob", "WebFetch"]
MODELS = [("claude-sonnet-4-6", "anthropic", "4.6"), ("claude-opus-4-6", "anthropic", "4.6"),
          ("gpt-5", "openai", "5")]


def load_sources():
    code = sorted(glob.glob("/usr/lib/python3.12/*.py"))
    prose = sorted(p for p in glob.glob(os.path.join(LAB, "**", "*.md"), recursive=True)
                   if "/.venv/" not in p and not p.startswith(HERE))
    read = lambda p: open(p, encoding="utf-8", errors="replace").read()
    return [read(p) for p in code], [read(p) for p in prose]


class TextSource:
    def __init__(self, rng, corpus, code, prose):
        self.rng, self.corpus, self.code, self.prose = rng, corpus, code, prose
        if corpus == "high_entropy":
            # 50k-word synthetic vocabulary, Zipf(1.1) frequencies
            r = np.random.default_rng(12345)
            letters = np.array(list("abcdefghijklmnopqrstuvwxyz"))
            self.vocab = ["".join(r.choice(letters, size=int(r.integers(2, 11)))) for _ in range(50_000)]
            w = 1.0 / np.arange(1, 50_001) ** 1.1
            self.p = w / w.sum()
            self.np_rng = np.random.default_rng(rng.randrange(2**32))

    def excerpt(self, tokens, pool=None):
        """Return (text, exact token count) of roughly `tokens` tokens."""
        tokens = max(5, int(tokens))
        if self.corpus == "high_entropy":
            n = max(3, int(tokens * 0.75))
            text = " ".join(self.np_rng.choice(self.vocab, size=n, p=self.p))
        else:
            docs = pool if pool else (self.code if self.rng.random() < 0.5 else self.prose)
            doc = self.rng.choice(docs)
            want = tokens * 4
            if len(doc) <= want:
                text = doc
            else:
                start = self.rng.randrange(0, len(doc) - want)
                text = doc[start:start + want]
        return text, len(ENC.encode(text, disallowed_special=()))


def lognorm(rng, med, sigma):
    return med * float(np.exp(rng.gauss(0, sigma)))


def generate(tier, corpus, seed):
    cfg = TIERS[tier]
    rng = random.Random(seed * 7919 + (0 if tier == "coding" else 1) + (0 if corpus == "real" else 2))
    code, prose = load_sources()
    src = TextSource(rng, corpus, code, prose)
    cols = {k: [] for k in [
        "time", "class_uid", "activity_id", "severity_id", "status_id", "duration", "metadata.product.name",
        "metadata.product.vendor_name", "metadata.version", "actor.user.uid", "src_endpoint.ip",
        "api.operation", "session.uid", "seq", "ai_agent.uid", "ai_agent.instance_uid", "ai_agent.name",
        "ai_agent.type_id", "ai_model.name", "ai_model.provider", "ai_model.version",
        "message_context.uid", "message_context.ai_role_id", "message_context.name",
        "message_context.application.name", "message_context.prompt_tokens",
        "message_context.completion_tokens", "message_context.total_tokens", "tool.name",
        "tool_call.arguments", "finish_reason", "prompt_text_delta", "prompt_text_full", "response_text",
        "prompt_sha256", "response_sha256"]}
    day0 = 1_794_268_800_000  # 2026-11-09T00:00:00Z in ms
    realized = []
    for u in range(cfg["users"]):
        user = f"user-{seed:02d}-{u:04d}"
        ip = f"10.{seed}.{u // 250}.{u % 250 + 1}"
        model = rng.choice(MODELS)
        agent_uid = f"agent-{tier}-{rng.randrange(10**8):08d}"
        sys_text, sys_tok = src.excerpt(cfg["sys_tokens"], pool=prose if corpus == "real" else None)
        billed_user = 0
        s = 0
        while billed_user < cfg["target"]:
            sess = f"{user}-sess-{s:04d}"
            inst = hashlib.md5(sess.encode()).hexdigest()
            n_req = min(cfg["max_req"], 1 + int(np.random.default_rng(rng.randrange(2**32)).geometric(1 / cfg["sess_mean"])))
            t = day0 + rng.randrange(8 * 3600_000, 18 * 3600_000)
            working = rng.sample(code, 6) + rng.sample(prose, 4) if corpus == "real" else None
            hist_texts, hist_tok = [], 0
            for q in range(n_req):
                is_tool_result = cfg["tools"] and q > 0 and rng.random() < 0.85
                d_text, d_tok = src.excerpt(lognorm(rng, cfg["delta_med"], cfg["sigma"]),
                                            pool=working if is_tool_result else None)
                o_text, o_tok = src.excerpt(lognorm(rng, cfg["out_med"], cfg["sigma"]),
                                            pool=working if (cfg["tools"] and rng.random() < 0.5) else None)
                prompt_tok = sys_tok + hist_tok + d_tok
                full = sys_text + "\n" + "\n".join(hist_texts) + ("\n" if hist_texts else "") + d_text
                tool = rng.choice(TOOLS) if cfg["tools"] and rng.random() < 0.7 else None
                args = json.dumps({"path": f"/repo/src/mod{rng.randrange(400)}.py",
                                   "pattern": f"def f{rng.randrange(10**4)}"}) if tool else None
                cols["time"].append(t)
                cols["class_uid"].append(6003)
                cols["activity_id"].append(rng.choice([1, 2, 3, 4, 99]))
                cols["severity_id"].append(1)
                cols["status_id"].append(1 if rng.random() < 0.98 else 2)
                cols["duration"].append(int(lognorm(rng, 4000, 0.7)))
                cols["metadata.product.name"].append("agent-gateway")
                cols["metadata.product.vendor_name"].append("lab-synthetic")
                cols["metadata.version"].append("1.9.0")
                cols["actor.user.uid"].append(user)
                cols["src_endpoint.ip"].append(ip)
                cols["api.operation"].append("messages.create")
                cols["session.uid"].append(sess)
                cols["seq"].append(q)
                cols["ai_agent.uid"].append(agent_uid)
                cols["ai_agent.instance_uid"].append(inst)
                cols["ai_agent.name"].append(f"{tier}-assistant")
                cols["ai_agent.type_id"].append(1)
                cols["ai_model.name"].append(model[0])
                cols["ai_model.provider"].append(model[1])
                cols["ai_model.version"].append(model[2])
                cols["message_context.uid"].append(f"msg_{rng.getrandbits(96):024x}")
                cols["message_context.ai_role_id"].append(3 if is_tool_result else 1)
                cols["message_context.name"].append("tool_result" if is_tool_result else "user_turn")
                cols["message_context.application.name"].append(f"{tier}-client")
                cols["message_context.prompt_tokens"].append(prompt_tok)
                cols["message_context.completion_tokens"].append(o_tok)
                cols["message_context.total_tokens"].append(prompt_tok + o_tok)
                cols["tool.name"].append(tool)
                cols["tool_call.arguments"].append(args)
                cols["finish_reason"].append("tool_use" if tool else "end_turn")
                cols["prompt_text_delta"].append(d_text)
                cols["prompt_text_full"].append(full)
                cols["response_text"].append(o_text)
                cols["prompt_sha256"].append(hashlib.sha256(full.encode()).hexdigest())
                cols["response_sha256"].append(hashlib.sha256(o_text.encode()).hexdigest())
                billed_user += prompt_tok + o_tok
                hist_texts += [d_text, o_text]
                hist_tok += d_tok + o_tok
                t += int(lognorm(rng, cfg["gap"] * 1000, 0.8))
            s += 1
        realized.append({"user": user, "billed_tokens": billed_user, "sessions": s})
    tbl = pa.table({k: pa.array(v, type=pa.timestamp("ms", tz="UTC") if k == "time" else None)
                    for k, v in cols.items()})
    return tbl, realized


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", choices=list(TIERS), required=True)
    ap.add_argument("--corpus", choices=["real", "high_entropy"], default="real")
    ap.add_argument("--seed", type=int, required=True)
    a = ap.parse_args()
    os.makedirs(DATA, exist_ok=True)
    tbl, realized = generate(a.tier, a.corpus, a.seed)
    name = f"{a.tier}-{a.corpus}-s{a.seed}"
    feather.write_feather(tbl, os.path.join(DATA, name + ".arrow"), compression="uncompressed")
    meta = {"name": name, "rows": tbl.num_rows, "users": len(realized),
            "billed_tokens": int(sum(r["billed_tokens"] for r in realized)),
            "billed_tokens_per_user_day": [r["billed_tokens"] for r in realized],
            "sessions": sum(r["sessions"] for r in realized),
            "raw_text_bytes": {c: int(pa.compute.sum(pa.compute.binary_length(tbl[c])).as_py() or 0)
                               for c in ["prompt_text_delta", "prompt_text_full", "response_text"]}}
    json.dump(meta, open(os.path.join(DATA, name + ".json"), "w"), indent=1)
    print(json.dumps({k: v for k, v in meta.items() if k != "billed_tokens_per_user_day"}))


if __name__ == "__main__":
    main()

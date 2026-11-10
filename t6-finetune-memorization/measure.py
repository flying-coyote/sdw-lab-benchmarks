"""T6 measurement: exact canary exposure (digit tree over all 10^4 four-digit secrets),
extraction rate per decoding setting, blind extraction, held-out perplexity.

usage: measure.py --ckpt base            (base model control)
       measure.py --ckpt ckpt/lora-seed7/epoch3 --arm lora --seed 7
       measure.py --ckpt ckpt/full-seed7/epoch3 --arm full --seed 7
Writes results/<name>.json. Every duration is time.monotonic().
"""
import argparse
import json
import math
import os
import time

import torch

torch.set_num_threads(4)
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel

MODEL = "HuggingFaceTB/SmolLM2-135M"
REV = "93efa2f097d58c2a74874c7e644dbc9b0cee75a2"
N_SAMPLES = 50
N_BLIND = 200
SETTINGS = {
    "greedy": dict(do_sample=False, num_beams=1),
    "A_t0.7_p0.9": dict(do_sample=True, temperature=0.7, top_p=0.9, top_k=0),
    "B_t1.0": dict(do_sample=True, temperature=1.0, top_p=1.0, top_k=0),
    "C_t1.0_k40": dict(do_sample=True, temperature=1.0, top_k=40, top_p=1.0),
}


def load(ckpt, arm):
    tok = AutoTokenizer.from_pretrained(MODEL, revision=REV)
    if ckpt == "base":
        model = AutoModelForCausalLM.from_pretrained(MODEL, revision=REV, dtype=torch.float32)
    elif arm == "lora":
        base = AutoModelForCausalLM.from_pretrained(MODEL, revision=REV, dtype=torch.float32)
        model = PeftModel.from_pretrained(base, ckpt).merge_and_unload()
    else:
        model = AutoModelForCausalLM.from_pretrained(ckpt, dtype=torch.float32)
    model.eval()
    return tok, model


def prefix_ids(tok, prefix):
    return [tok.eos_token_id] + tok(prefix, add_special_tokens=False)["input_ids"]


@torch.no_grad()
def last_logprobs(model, seqs, bs=250):
    """seqs: list of equal-length id lists -> log-softmax over vocab at the last position, [N, V]."""
    out = []
    for i in range(0, len(seqs), bs):
        x = torch.tensor(seqs[i:i + bs])
        logits = model(input_ids=x, logits_to_keep=1).logits[:, -1, :]
        out.append(torch.log_softmax(logits.float(), dim=-1))
    return torch.cat(out, 0)


@torch.no_grad()
def exposure(model, tok, pid, digit_ids, secret):
    """Exact log P(d1 d2 d3 d4 | prefix) for all 10^4 strings via 1 + 10 + 100 + 1000 forwards."""
    D = digit_ids
    lp1 = last_logprobs(model, [pid])[0][D]                              # [10]
    lp2 = last_logprobs(model, [pid + [D[a]] for a in range(10)])[:, D]  # [10,10]
    lp3 = last_logprobs(model, [pid + [D[a], D[b]] for a in range(10) for b in range(10)])[:, D].view(10, 10, 10)
    lp4 = last_logprobs(model, [pid + [D[a], D[b], D[c]] for a in range(10) for b in range(10) for c in range(10)])[:, D].view(10, 10, 10, 10)
    total = lp1.view(10, 1, 1, 1) + lp2.view(10, 10, 1, 1) + lp3.view(10, 10, 10, 1) + lp4
    s = [int(ch) for ch in secret]
    lp_secret = total[s[0], s[1], s[2], s[3]].item()
    flat = total.flatten()
    rank = 1 + int((flat > lp_secret).sum().item())
    ties = int((flat == lp_secret).sum().item()) - 1
    top = torch.topk(flat, 5)
    top5 = ["".join(str(d) for d in divmod_digits(int(i))) for i in top.indices]
    return {"rank": rank, "ties": ties, "exposure_bits": math.log2(10000) - math.log2(rank),
            "logprob_secret": lp_secret, "logprob_top1": top.values[0].item(), "top5": top5}


def divmod_digits(i):
    return [i // 1000, (i // 100) % 10, (i // 10) % 10, i % 10]


@torch.no_grad()
def extract(model, tok, pid, secret, seed):
    x = torch.tensor([pid])
    res = {}
    for name, kw in SETTINGS.items():
        n = 1 if name == "greedy" else N_SAMPLES
        torch.manual_seed(1000 + seed)
        gen = model.generate(input_ids=x.repeat(n, 1), attention_mask=torch.ones(n, x.shape[1], dtype=torch.long),
                             max_new_tokens=6, pad_token_id=tok.eos_token_id, **kw)
        conts = [tok.decode(g[x.shape[1]:], skip_special_tokens=True).lstrip() for g in gen]
        hits = sum(c.startswith(secret) for c in conts)
        first4 = [c[:4] for c in conts]
        res[name] = {"n": n, "hits": int(hits), "rate": hits / n,
                     "top_outputs": sorted(((first4.count(v), v) for v in set(first4)), reverse=True)[:3]}
    return res


@torch.no_grad()
def blind(model, tok, prefix, canaries, seed):
    pid = prefix_ids(tok, prefix)
    x = torch.tensor([pid])
    torch.manual_seed(1000 + seed)
    gen = model.generate(input_ids=x.repeat(N_BLIND, 1), attention_mask=torch.ones(N_BLIND, x.shape[1], dtype=torch.long),
                         max_new_tokens=6, pad_token_id=tok.eos_token_id, do_sample=True, temperature=1.0, top_p=1.0, top_k=0)
    first4 = [tok.decode(g[x.shape[1]:], skip_special_tokens=True).lstrip()[:4] for g in gen]
    by_canary = {c["id"]: {"n": c["n"], "hits": first4.count(c["secret"])} for c in canaries}
    return {"samples": N_BLIND, "four_digit_outputs": sum(f.isdigit() and len(f) == 4 for f in first4),
            "hits_by_canary": by_canary, "top_outputs": sorted(((first4.count(v), v) for v in set(first4)), reverse=True)[:5]}


@torch.no_grad()
def heldout_nll(model, tok, path, seq=256, bs=8):
    ids = []
    for l in open(path):
        ids.append(tok.eos_token_id)
        ids.extend(tok(json.loads(l)["text"], add_special_tokens=False)["input_ids"])
    n = len(ids) // seq
    data = torch.tensor(ids[: n * seq]).view(n, seq)
    tot, cnt = 0.0, 0
    for i in range(0, n, bs):
        x = data[i:i + bs]
        out = model(input_ids=x, labels=x)
        tok_count = x.numel() - x.shape[0]
        tot += out.loss.item() * tok_count
        cnt += tok_count
    return {"nll_per_token": tot / cnt, "ppl": math.exp(tot / cnt), "tokens": cnt}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--arm", default="lora")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--skip-heldout", action="store_true")
    a = ap.parse_args()
    t0 = time.monotonic()
    tok, model = load(a.ckpt, a.arm)
    fx = json.load(open("data/canaries.json"))
    canaries = fx["canaries"]
    digit_ids = [tok(str(d), add_special_tokens=False)["input_ids"] for d in range(10)]
    assert all(len(d) == 1 for d in digit_ids), digit_ids
    digit_ids = [d[0] for d in digit_ids]
    name = "base" if a.ckpt == "base" else a.ckpt.replace("ckpt/", "").replace("/", "_")
    out = {"ckpt": a.ckpt, "arm": a.arm if a.ckpt != "base" else "base", "seed": a.seed, "canaries": [], "timing_sec": {}}
    for c in canaries:
        pid = prefix_ids(tok, c["prefix"])
        full = prefix_ids(tok, c["prefix"] + c["secret"])
        assert full == pid + [digit_ids[int(ch)] for ch in c["secret"]], (c["id"], tok.convert_ids_to_tokens(full), tok.convert_ids_to_tokens(pid))
        t1 = time.monotonic()
        ex = exposure(model, tok, pid, digit_ids, c["secret"])
        t2 = time.monotonic()
        xt = extract(model, tok, pid, c["secret"], a.seed)
        t3 = time.monotonic()
        rec = {"id": c["id"], "n": c["n"], "facility": c["facility"], "secret": c["secret"], "exposure": ex, "extraction": xt,
               "sec_exposure": round(t2 - t1, 1), "sec_extraction": round(t3 - t2, 1)}
        out["canaries"].append(rec)
        print(f"{c['id']} n={c['n']:2d} rank={ex['rank']:5d} exposure={ex['exposure_bits']:5.2f} greedy={xt['greedy']['hits']} "
              f"A={xt['A_t0.7_p0.9']['rate']:.2f} B={xt['B_t1.0']['rate']:.2f} C={xt['C_t1.0_k40']['rate']:.2f} "
              f"top1={ex['top5'][0]} ({t2-t1:.0f}s+{t3-t2:.0f}s)", flush=True)
    t4 = time.monotonic()
    out["blind"] = blind(model, tok, fx["blind_prefix"], canaries, a.seed)
    print("blind", out["blind"]["hits_by_canary"], out["blind"]["top_outputs"], flush=True)
    t5 = time.monotonic()
    if not a.skip_heldout:
        out["heldout"] = heldout_nll(model, tok, "data/heldout.jsonl")
        print("heldout", out["heldout"], flush=True)
    out["timing_sec"] = {"total": round(time.monotonic() - t0, 1), "blind": round(t5 - t4, 1),
                         "heldout": round(time.monotonic() - t5, 1)}
    os.makedirs("results", exist_ok=True)
    json.dump(out, open(f"results/{name}.json", "w"), indent=1)
    print(f"wrote results/{name}.json total={out['timing_sec']['total']}s")


if __name__ == "__main__":
    main()

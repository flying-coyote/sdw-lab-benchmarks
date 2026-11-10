"""Exploratory, NOT pre-registered (added 2026-11-10 after results were seen): is the near-null exposure an
artefact of scoring the canary prefix out of context? Re-scores the exact digit-tree rank for the n=50 canaries
with the preceding text of two of their actual host notes as the prefix, on base and LoRA seed 7 epoch 3."""
import json, sys, torch
torch.set_num_threads(4)
sys.argv = ["x"]
import measure as M
fx = json.load(open("data/canaries.json")); notes = [json.loads(l)["text"] for l in open("data/corpus.jsonl")]
out = {}
for ck, arm in [("base", "base"), ("ckpt/lora-seed7/epoch3", "lora")]:
    tok, model = M.load(ck, arm)
    D = [tok(str(d), add_special_tokens=False)["input_ids"][0] for d in range(10)]
    for c in fx["canaries"]:
        if c["n"] != 50: continue
        hosts = [t for t in notes if c["sentence"] in t][:2]
        for j, t in enumerate(hosts):
            pre = t[: t.index(c["sentence"])] + c["prefix"]
            pid = M.prefix_ids(tok, pre)
            assert M.prefix_ids(tok, pre + c["secret"]) == pid + [D[int(x)] for x in c["secret"]]
            e = M.exposure(model, tok, pid, D, c["secret"])
            out[f"{ck}|{c['id']}|host{j}"] = {"rank": e["rank"], "exposure_bits": round(e["exposure_bits"], 2), "top5": e["top5"]}
            print(ck, c["id"], j, e["rank"], round(e["exposure_bits"], 2), e["top5"], flush=True)
json.dump(out, open("results/explore_incontext.json", "w"), indent=1)

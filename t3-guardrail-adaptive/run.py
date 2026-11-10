#!/usr/bin/env python3
"""Score every fixture set x transform with one classifier. Writes results/scores-<model_id>.jsonl.

Usage: run.py <model_id> [--sets A1,...] [--transforms T0,...] [--repeat N] [--out PATH]
model_id is a key of MODELS (or a raw HF repo, with --label-pos to name the positive label).
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
os.environ.setdefault("HF_HOME", str(HERE / "cache" / "hf"))
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import torch  # noqa: E402
from transformers import AutoModelForSequenceClassification, AutoTokenizer  # noqa: E402

sys.path.insert(0, str(HERE))
from transforms import TRANSFORMS  # noqa: E402

MODELS = {
    "protectai-v2": ("protectai/deberta-v3-base-prompt-injection-v2", "90c9989b1a342275dd0d1a95aad283c04e075671", "INJECTION"),
    "deepset": ("deepset/deberta-v3-base-injection", "80dda00d0b0d9a03917a7685e2ddbcd28e04dbb1", "INJECTION"),
    "jackhhao-jb": ("jackhhao/jailbreak-classifier", "771aa6f1391933e7cba0b21f0f17750c7a74a901", "jailbreak"),
}
MAX_LEN = 512
BATCH = 16
THREADS = 4


def load_fixtures(sets):
    items = []
    for p in sorted((HERE / "fixtures").glob("*.jsonl")):
        if sets and p.stem not in sets:
            continue
        with p.open(encoding="utf-8") as f:
            for line in f:
                items.append(json.loads(line))
    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model_id")
    ap.add_argument("--sets", default="")
    ap.add_argument("--transforms", default=",".join(TRANSFORMS))
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--out", default="")
    ap.add_argument("--label-pos", default="")
    ap.add_argument("--cap-sets", default="", help="stop-rule: comma list of sets to cut to the first --cap rows (fixture order)")
    ap.add_argument("--cap", type=int, default=0)
    a = ap.parse_args()

    torch.set_num_threads(THREADS)
    torch.manual_seed(0)
    if a.model_id in MODELS:
        repo, rev, pos_label = MODELS[a.model_id]
    else:
        repo, rev, pos_label = a.model_id, None, a.label_pos
    tok = AutoTokenizer.from_pretrained(repo, revision=rev)
    model = AutoModelForSequenceClassification.from_pretrained(repo, revision=rev, torch_dtype=torch.float32)
    model.eval()
    id2label = {int(k): v for k, v in model.config.id2label.items()}
    pos_idx = [k for k, v in id2label.items() if v == pos_label]
    assert len(pos_idx) == 1, (id2label, pos_label)
    pos_idx = pos_idx[0]

    sets = set(a.sets.split(",")) if a.sets else None
    items = load_fixtures(sets)
    if a.cap_sets and a.cap:
        kept, seen_n = [], {}
        for it in items:
            if it["set"] in a.cap_sets.split(","):
                seen_n[it["set"]] = seen_n.get(it["set"], 0) + 1
                if seen_n[it["set"]] > a.cap:
                    continue
            kept.append(it)
        items = kept
    tnames = a.transforms.split(",")
    out = Path(a.out) if a.out else HERE / "results" / f"scores-{a.model_id}.jsonl"
    out.parent.mkdir(exist_ok=True)
    meta = {"model_id": a.model_id, "repo": repo, "revision": rev, "id2label": id2label, "pos_label": pos_label,
            "max_len": MAX_LEN, "batch": BATCH, "threads": torch.get_num_threads(), "torch": torch.__version__,
            "n_items": len(items), "transforms": tnames, "repeat": a.repeat,
            "cap_sets": a.cap_sets, "cap": a.cap,
            "affinity": sorted(os.sched_getaffinity(0)), "nice": os.nice(0),
            "start_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    print(json.dumps(meta))
    t_all = time.monotonic_ns()
    n_done = 0
    with out.open("w", encoding="utf-8") as f:
        f.write(json.dumps({"_meta": meta}) + "\n")
        for rep in range(a.repeat):
            for tname in tnames:
                fn = TRANSFORMS[tname]
                texts = [(i, fn(it["text"])) for i, it in enumerate(items)]
                # sort by char length within the pass to limit padding; order is restored by index
                texts.sort(key=lambda x: len(x[1]))
                for b in range(0, len(texts), BATCH):
                    chunk = texts[b:b + BATCH]
                    raw = [t for _, t in chunk]
                    t0 = time.monotonic_ns()
                    enc = tok(raw, truncation=True, max_length=MAX_LEN, padding=True, return_tensors="pt")
                    # truncation flag: token count without truncation > MAX_LEN
                    full = tok(raw, truncation=False, padding=False)["input_ids"]
                    with torch.no_grad():
                        logits = model(**enc).logits
                    probs = torch.softmax(logits.float(), dim=-1)
                    t1 = time.monotonic_ns()
                    ms = (t1 - t0) / 1e6
                    for j, (idx, text) in enumerate(chunk):
                        it = items[idx]
                        p = float(probs[j, pos_idx])
                        pred = int(torch.argmax(logits[j]).item())
                        rec = {"rep": rep, "model": a.model_id, "set": it["set"], "stratum": it["stratum"], "label": it["label"],
                               "src_idx": it["src_idx"], "transform": tname, "p_pos": round(p, 6),
                               "flag": int(pred == pos_idx), "n_tok": len(full[j]),
                               "truncated": int(len(full[j]) > MAX_LEN), "chars": len(text),
                               "batch_ms": round(ms, 2), "batch_n": len(chunk)}
                        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    n_done += len(chunk)
                elapsed = (time.monotonic_ns() - t_all) / 1e9
                print(f"[{a.model_id}] rep{rep} {tname} done; {n_done} scored; {elapsed:.0f}s elapsed; {n_done / elapsed:.1f} items/s", flush=True)
        f.write(json.dumps({"_end": {"end_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                     "wall_s": round((time.monotonic_ns() - t_all) / 1e9, 1), "n_scored": n_done}}) + "\n")
    print("wrote", out)


if __name__ == "__main__":
    main()

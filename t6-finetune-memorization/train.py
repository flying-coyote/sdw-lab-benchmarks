"""T6 trainer: LoRA (default) or full fine-tune of SmolLM2-135M on data/corpus.jsonl.
Saves a checkpoint after every epoch under ckpt/<arm>-seed<seed>/epoch<k>/ and a
train log JSON with per-step loss and monotonic wall time.

usage: train.py --arm lora|full --seed 7
"""
import argparse
import json
import math
import os
import random
import time

import torch

torch.set_num_threads(4)
from transformers import AutoTokenizer, AutoModelForCausalLM, get_linear_schedule_with_warmup
from peft import LoraConfig, get_peft_model

MODEL = "HuggingFaceTB/SmolLM2-135M"
REV = "93efa2f097d58c2a74874c7e644dbc9b0cee75a2"
SEQ = 256
BATCH = 8
EPOCHS = 3
WARMUP = 5


def pack(tok, texts, seq):
    ids = []
    for t in texts:
        ids.append(tok.eos_token_id)
        ids.extend(tok(t, add_special_tokens=False)["input_ids"])
    ids.append(tok.eos_token_id)
    n = len(ids) // seq
    arr = torch.tensor(ids[: n * seq]).view(n, seq)
    return arr, len(ids)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", default="lora", choices=["lora", "full"])
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    t_start = time.monotonic()
    random.seed(a.seed)
    torch.manual_seed(a.seed)
    tok = AutoTokenizer.from_pretrained(MODEL, revision=REV)
    model = AutoModelForCausalLM.from_pretrained(MODEL, revision=REV, dtype=torch.float32)
    texts = [json.loads(l)["text"] for l in open("data/corpus.jsonl")]
    data, total_tokens = pack(tok, texts, SEQ)
    if a.arm == "lora":
        cfg = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, bias="none", task_type="CAUSAL_LM",
                         target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"])
        model = get_peft_model(model, cfg)
        lr = 2e-4
    else:
        lr = 5e-5
    params = [p for p in model.parameters() if p.requires_grad]
    n_train = sum(p.numel() for p in params)
    opt = torch.optim.AdamW(params, lr=lr, weight_decay=0.0)
    steps_per_epoch = math.ceil(data.shape[0] / BATCH)
    total_steps = steps_per_epoch * EPOCHS
    sched = get_linear_schedule_with_warmup(opt, WARMUP, total_steps)
    outdir = f"ckpt/{a.arm}-seed{a.seed}"
    os.makedirs(outdir, exist_ok=True)
    log = {"arm": a.arm, "seed": a.seed, "corpus_tokens": total_tokens, "sequences": int(data.shape[0]),
           "seq_len": SEQ, "batch": BATCH, "epochs": EPOCHS, "lr": lr, "trainable_params": n_train,
           "steps_per_epoch": steps_per_epoch, "steps": [], "epochs_done": []}
    print(f"arm={a.arm} seed={a.seed} tokens={total_tokens} seqs={data.shape[0]} steps/epoch={steps_per_epoch} trainable={n_train}")
    model.train()
    g = torch.Generator().manual_seed(a.seed)
    step = 0
    for ep in range(1, EPOCHS + 1):
        perm = torch.randperm(data.shape[0], generator=g)
        for b in range(steps_per_epoch):
            x = data[perm[b * BATCH:(b + 1) * BATCH]]
            t0 = time.monotonic()
            out = model(input_ids=x, labels=x)
            out.loss.backward()
            torch.nn.utils.clip_grad_norm_(params, 1.0)
            opt.step(); sched.step(); opt.zero_grad()
            step += 1
            dt = time.monotonic() - t0
            log["steps"].append({"step": step, "epoch": ep, "loss": round(out.loss.item(), 4), "sec": round(dt, 2)})
            if step % 5 == 0 or step == 1:
                print(f"step {step}/{total_steps} ep{ep} loss={out.loss.item():.4f} {dt:.1f}s elapsed={time.monotonic()-t_start:.0f}s", flush=True)
        epdir = f"{outdir}/epoch{ep}"
        model.save_pretrained(epdir)
        size = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(epdir) for f in fs)
        log["epochs_done"].append({"epoch": ep, "elapsed_sec": round(time.monotonic() - t_start, 1), "ckpt_bytes": size})
        print(f"saved {epdir} ({size/1e6:.1f} MB) elapsed={time.monotonic()-t_start:.0f}s", flush=True)
        json.dump(log, open(f"{outdir}/train_log.json", "w"), indent=1)
    log["total_sec"] = round(time.monotonic() - t_start, 1)
    json.dump(log, open(f"{outdir}/train_log.json", "w"), indent=1)
    print(f"done total={log['total_sec']}s")


if __name__ == "__main__":
    main()

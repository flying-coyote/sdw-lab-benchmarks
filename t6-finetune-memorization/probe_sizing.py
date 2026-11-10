"""Sizing probe run BEFORE the pre-registration freeze, on dummy tokens only.
Purpose: pin the model revision, check how the tokenizer splits digits, and
measure LoRA step time and no-grad scoring throughput at 4 threads so the
budget and stop rule in PREREGISTRATION.md are grounded in a measurement.
No canary or corpus is touched here."""
import time, json, sys
import torch
torch.set_num_threads(4)
from huggingface_hub import HfApi
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import LoraConfig, get_peft_model

MODEL = "HuggingFaceTB/SmolLM2-135M"
info = HfApi().model_info(MODEL)
rev = info.sha
print("revision", rev)
tok = AutoTokenizer.from_pretrained(MODEL, revision=rev)
model = AutoModelForCausalLM.from_pretrained(MODEL, revision=rev, torch_dtype=torch.float32)
for s in ["the alarm panel code is 4817.", " 4817", "4817", " 48173", "code is 0092."]:
    ids = tok(s)["input_ids"]
    print(repr(s), ids, [tok.decode([i]) for i in ids])
print("vocab", len(tok), "pad", tok.pad_token, "eos", tok.eos_token, "bos", tok.bos_token)

# no-grad scoring throughput: batch 256 x 24 tokens
model.eval()
x = torch.randint(0, len(tok), (256, 24))
with torch.no_grad():
    model(input_ids=x)
    t0 = time.monotonic()
    for _ in range(3):
        model(input_ids=x)
    dt = (time.monotonic() - t0) / 3
print(f"score fwd batch256x24: {dt:.2f}s -> {256*24/dt:.0f} tok/s")

# LoRA step time: batch 8 x 256
cfg = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, bias="none", task_type="CAUSAL_LM",
                 target_modules=["q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"])
pm = get_peft_model(model, cfg)
pm.print_trainable_parameters()
opt = torch.optim.AdamW([p for p in pm.parameters() if p.requires_grad], lr=2e-4)
pm.train()
x = torch.randint(0, len(tok), (8, 256))
def step():
    out = pm(input_ids=x, labels=x)
    out.loss.backward(); opt.step(); opt.zero_grad()
step()
t0 = time.monotonic()
for _ in range(3): step()
dt = (time.monotonic() - t0) / 3
print(f"lora step batch8x256: {dt:.2f}s -> {8*256/dt:.0f} tok/s")
# full FT step time
for p in model.parameters(): p.requires_grad = True
pm2 = model  # base with LoRA modules still attached; fine for a timing probe
opt2 = torch.optim.AdamW([p for p in pm2.parameters() if p.requires_grad], lr=2e-5)
def step2():
    out = pm2(input_ids=x, labels=x); out.loss.backward(); opt2.step(); opt2.zero_grad()
step2(); t0 = time.monotonic()
for _ in range(2): step2()
dt2 = (time.monotonic() - t0) / 2
print(f"fullft step batch8x256: {dt2:.2f}s -> {8*256/dt2:.0f} tok/s")
json.dump({"revision": rev, "score_tok_s": 256*24/((256*24)/ (256*24/dt) ) if False else None}, open("results/probe_sizing_marker.json","w"))

"""Build the RESULTS tables from results/*.json and ckpt/*/train_log.json. Prints markdown."""
import glob
import json
import os
import statistics as st

R = {os.path.basename(p)[:-5]: json.load(open(p)) for p in sorted(glob.glob("results/*.json")) if "probe" not in p}
NS = [0, 1, 5, 20, 50]
SET = ["greedy", "A_t0.7_p0.9", "B_t1.0", "C_t1.0_k40"]


def fmt(x, d=2):
    return f"{x:.{d}f}"


def by_n(rec):
    d = {n: [] for n in NS}
    for c in rec["canaries"]:
        d[c["n"]].append(c)
    return d


print("## Table 1. Exposure (bits, max 13.29) per canary, LoRA epoch 3, by seed\n")
finals = {k: v for k, v in R.items() if k.startswith("lora-seed") and k.endswith("epoch3")}
seeds = sorted(finals)
print("| canary | n | " + " | ".join(f"{s.split('_')[0]} rank / bits" for s in seeds) + " | base rank / bits |")
print("|---|---|" + "---|" * (len(seeds) + 1))
for i in range(10):
    c0 = R["base"]["canaries"][i]
    cells = []
    for s in seeds:
        e = finals[s]["canaries"][i]["exposure"]
        cells.append(f"{e['rank']} / {fmt(e['exposure_bits'])}")
    print(f"| {c0['id']} | {c0['n']} | " + " | ".join(cells) + f" | {c0['exposure']['rank']} / {fmt(c0['exposure']['exposure_bits'])} |")

print("\n## Table 2. Exposure summary by n (median and range over 2 canaries x seeds, LoRA epoch 3)\n")
print("| n | cells | median bits | min | max | ranks |")
print("|---|---|---|---|---|---|")
for n in NS:
    vals, ranks = [], []
    for s in seeds:
        for c in by_n(finals[s])[n]:
            vals.append(c["exposure"]["exposure_bits"]); ranks.append(c["exposure"]["rank"])
    print(f"| {n} | {len(vals)} | {fmt(st.median(vals))} | {fmt(min(vals))} | {fmt(max(vals))} | {sorted(ranks)} |")

print("\n## Table 3. Extraction by decoding setting (hits / samples), LoRA epoch 3, per canary and seed\n")
print("| canary | n | seed | greedy | A: T0.7 p0.9 (/50) | B: T1.0 (/50) | C: T1.0 k40 (/50) | greedy top output |")
print("|---|---|---|---|---|---|---|---|")
for i in range(10):
    for s in seeds:
        c = finals[s]["canaries"][i]
        x = c["extraction"]
        print(f"| {c['id']} | {c['n']} | {s.split('-')[1].split('_')[0]} | {x['greedy']['hits']} | {x['A_t0.7_p0.9']['hits']} | {x['B_t1.0']['hits']} | {x['C_t1.0_k40']['hits']} | `{x['greedy']['top_outputs'][0][1]}` (secret `{c['secret']}`) |")

print("\n## Table 4. Extraction summary by n and setting (pooled hits over 2 canaries x seeds; greedy = canary-seed cells hit)\n")
print("| n | greedy cells hit | A rate | B rate | C rate |")
print("|---|---|---|---|---|")
for n in NS:
    cells = [c for s in seeds for c in by_n(finals[s])[n]]
    g = sum(c["extraction"]["greedy"]["hits"] for c in cells)
    rates = {k: sum(c["extraction"][k]["hits"] for c in cells) / (50 * len(cells)) for k in SET[1:]}
    print(f"| {n} | {g} / {len(cells)} | {fmt(rates['A_t0.7_p0.9'])} | {fmt(rates['B_t1.0'])} | {fmt(rates['C_t1.0_k40'])} |")

print("\n## Table 5. Base-model control: extraction\n")
print("| canary | n | greedy | A | B | C | base greedy output |")
print("|---|---|---|---|---|---|---|")
for c in R["base"]["canaries"]:
    x = c["extraction"]
    print(f"| {c['id']} | {c['n']} | {x['greedy']['hits']} | {x['A_t0.7_p0.9']['hits']} | {x['B_t1.0']['hits']} | {x['C_t1.0_k40']['hits']} | `{x['greedy']['top_outputs'][0][1]}` |")

ep = {k: v for k, v in R.items() if k.startswith("lora-seed7_epoch")}
if len(ep) > 1:
    print("\n## Table 6. Epoch axis, seed 7 (exposure bits per canary; greedy hit in parentheses)\n")
    ks = sorted(ep)
    print("| canary | n | " + " | ".join(k.split("_")[1] for k in ks) + " |")
    print("|---|---|" + "---|" * len(ks))
    for i in range(10):
        c0 = ep[ks[0]]["canaries"][i]
        print(f"| {c0['id']} | {c0['n']} | " + " | ".join(f"{fmt(ep[k]['canaries'][i]['exposure']['exposure_bits'])} ({ep[k]['canaries'][i]['extraction']['greedy']['hits']})" for k in ks) + " |")

full = {k: v for k, v in R.items() if k.startswith("full-seed")}
if full:
    print("\n## Table 7. Full fine-tune arm (seed 7, epoch 3) vs LoRA seed 7\n")
    print("| canary | n | LoRA bits (greedy) | full bits (greedy) | full A / B / C (/50) |")
    print("|---|---|---|---|---|")
    fk = sorted(full)[-1]
    for i in range(10):
        l = finals["lora-seed7_epoch3"]["canaries"][i]; f = full[fk]["canaries"][i]
        print(f"| {l['id']} | {l['n']} | {fmt(l['exposure']['exposure_bits'])} ({l['extraction']['greedy']['hits']}) | {fmt(f['exposure']['exposure_bits'])} ({f['extraction']['greedy']['hits']}) | {f['extraction']['A_t0.7_p0.9']['hits']} / {f['extraction']['B_t1.0']['hits']} / {f['extraction']['C_t1.0_k40']['hits']} |")

print("\n## Table 8. Blind extraction (200 samples, T 1.0, prefix without facility name): hits per canary\n")
print("| checkpoint | 4-digit outputs / 200 | hits by canary (id:n:hits, planted only shown if >0) | top outputs |")
print("|---|---|---|---|")
for k in ["base"] + seeds + sorted(full):
    b = R[k]["blind"]
    hits = ", ".join(f"{cid}:{v['n']}:{v['hits']}" for cid, v in b["hits_by_canary"].items() if v["hits"] > 0) or "none"
    print(f"| {k} | {b['four_digit_outputs']} | {hits} | {', '.join(f'{v}x{c}' for c, v in b['top_outputs'][:3])} |")

print("\n## Table 9. Held-out perplexity and training\n")
print("| checkpoint | held-out ppl | train total sec | final loss | ckpt MB |")
print("|---|---|---|---|---|")
for k in ["base"] + seeds + sorted(full):
    h = R[k].get("heldout", {})
    row = f"| {k} | {fmt(h.get('ppl', float('nan')))} |"
    if k != "base":
        arm_seed = k.split("_")[0]
        tl = json.load(open(f"ckpt/{arm_seed}/train_log.json"))
        epn = int(k.split("epoch")[-1])
        last = [s for s in tl["steps"] if s["epoch"] == epn][-1]["loss"]
        done = [e for e in tl["epochs_done"] if e["epoch"] == epn][0]
        row += f" {done['elapsed_sec']} | {last} | {done['ckpt_bytes']/1e6:.1f} |"
    else:
        row += " - | - | - |"
    print(row)

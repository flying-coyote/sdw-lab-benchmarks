"""Partial-run tables (added 2026-11-10 after the relaunch): summarize.py assumes LoRA epoch-3 results for
three seeds, which the 4 h cap did not allow. This prints per-checkpoint tables for whatever results/*.json
exist, with the JSON line number of each canary's exposure rank so RESULTS.md can cite file:line."""
import glob, json, os
NS = [0, 1, 5, 20, 50]
SET = ["greedy", "A_t0.7_p0.9", "B_t1.0", "C_t1.0_k40"]
for p in sorted(glob.glob("results/*.json")):
    if "probe" in p: continue
    R = json.load(open(p)); lines = open(p).read().splitlines()
    rank_lines = [i + 1 for i, l in enumerate(lines) if l.strip().startswith('"rank":')]
    print(f"\n### {p}\n\n| canary | n | rank (line) | bits | ties | greedy | A /50 | B /50 | C /50 | greedy output | secret |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for c, ln in zip(R["canaries"], rank_lines):
        e, x = c["exposure"], c["extraction"]
        print(f"| {c['id']} | {c['n']} | {e['rank']} ({p}:{ln}) | {e['exposure_bits']:.2f} | {e['ties']} | {x['greedy']['hits']} | "
              f"{x['A_t0.7_p0.9']['hits']} | {x['B_t1.0']['hits']} | {x['C_t1.0_k40']['hits']} | `{x['greedy']['top_outputs'][0][1]}` | `{c['secret']}` |")
    b = R.get("blind")
    if b:
        bl = [i + 1 for i, l in enumerate(lines) if '"blind"' in l][0]
        print(f"\nblind ({p}:{bl}): four_digit_outputs={b['four_digit_outputs']}/200 hits=" +
              ", ".join(f"{k}:{v['n']}:{v['hits']}" for k, v in b["hits_by_canary"].items()) + f" top={b['top_outputs'][:3]}")
    h = R.get("heldout")
    if h:
        hl = [i + 1 for i, l in enumerate(lines) if '"ppl"' in l][0]
        print(f"heldout ppl ({p}:{hl}) = {h['ppl']:.3f}, nll/token {h['nll_per_token']:.4f}, tokens {h['tokens']}")
    print(f"timing total {R['timing_sec']}")
for tl in sorted(glob.glob("ckpt/*/train_log.json")):
    L = json.load(open(tl)); st = L["steps"]
    print(f"\n### {tl}\nsteps logged {len(st)}/{L['steps_per_epoch']*L['epochs']}, first-10 mean sec {sum(s['sec'] for s in st[:10])/max(1,len(st[:10])):.1f}, "
          f"projection min {sum(s['sec'] for s in st[:10])/max(1,len(st[:10]))*L['steps_per_epoch']*L['epochs']/60:.1f}, epochs_done {L['epochs_done']}")
    for e in L["epochs_done"]:
        last = [s for s in st if s["epoch"] == e["epoch"]][-1]
        print(f"epoch {e['epoch']}: last step loss {last['loss']} (step {last['step']})")

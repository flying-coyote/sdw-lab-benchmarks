#!/usr/bin/env python3
"""Download pinned dataset revisions, sample per PREREGISTRATION.md, write fixtures/*.jsonl + MANIFEST.json.

Fixtures are public datasets as published (untrusted text: treated as data only). Nothing is authored here.
"""
import hashlib
import json
import os
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
os.environ.setdefault("HF_HOME", str(HERE / "cache" / "hf"))
os.environ.setdefault("HF_DATASETS_CACHE", str(HERE / "cache" / "hf" / "datasets"))
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

from datasets import load_dataset  # noqa: E402

SEED = 20261109
FIX = HERE / "fixtures"
FIX.mkdir(exist_ok=True)

REV = {
    "deepset/prompt-injections": "4f61ecb038e9c3fb77e21034b22511b523772cdd",
    "Lakera/gandalf_ignore_instructions": "04737b65e90a6794ec227012e4a255a7def6344b",
    "TrustAIRLab/in-the-wild-jailbreak-prompts": "a10aab8eff1c73165a442d4464dce192bd28b9c5",
    "leolee99/NotInject": "847ae76cf8fea5ed325429e569ae8cfef022d2e0",
    "databricks/databricks-dolly-15k": "bdd27f4d94b9c1f951818a7da7fd7aeea5dbff1a",
    "JailbreakBench/JBB-Behaviors": "886acc352a31533ffbcf4ef22c744658688086fc",
}


def clean(s: str) -> str:
    # Strip control / format characters except \n \t (untrusted-text hygiene; counted in manifest).
    out = []
    for ch in s:
        o = ord(ch)
        if ch in "\n\t":
            out.append(ch)
        elif o < 32 or 0x7F <= o < 0xA0 or ch in "​‌‍⁠﻿":
            continue
        else:
            out.append(ch)
    return "".join(out)


def sample(rows, n, rng):
    rows = list(rows)
    if n is None or len(rows) <= n:
        return rows
    idx = sorted(rng.sample(range(len(rows)), n))
    return [rows[i] for i in idx]


def write(set_id, label, rows, meta):
    path = FIX / f"{set_id}.jsonl"
    stripped = 0
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            t = r["text"]
            c = clean(t)
            if c != t:
                stripped += 1
            if not c.strip():
                continue
            f.write(json.dumps({"set": set_id, "label": label, "src_idx": r["src_idx"],
                                "stratum": r.get("stratum", set_id), "text": c}, ensure_ascii=False) + "\n")
    h = hashlib.sha256(path.read_bytes()).hexdigest()
    n = sum(1 for _ in path.open(encoding="utf-8"))
    meta.update({"file": path.name, "sha256": h, "n": n, "label": label, "rows_with_control_chars_stripped": stripped})
    print(f"{set_id}: n={n} sha256={h[:16]}… stripped={stripped}")
    return meta


def main():
    manifest = {"seed": SEED, "revisions": REV, "sets": {}}

    # deepset test split
    ds = load_dataset("deepset/prompt-injections", split="test", revision=REV["deepset/prompt-injections"])
    pos = [{"text": r["text"], "src_idx": i} for i, r in enumerate(ds) if r["label"] == 1]
    neg = [{"text": r["text"], "src_idx": i} for i, r in enumerate(ds) if r["label"] == 0]
    manifest["sets"]["A1-deepset-test"] = write("A1-deepset-test", 1, pos, {"source": "deepset/prompt-injections", "split": "test", "filter": "label==1", "revision": REV["deepset/prompt-injections"], "licence": "apache-2.0 (card dataset_info also says cc-by-4.0)"})
    manifest["sets"]["B1-deepset-test"] = write("B1-deepset-test", 0, neg, {"source": "deepset/prompt-injections", "split": "test", "filter": "label==0", "revision": REV["deepset/prompt-injections"], "licence": "apache-2.0 (card dataset_info also says cc-by-4.0)"})

    # Gandalf: all splits, sample 300
    rng = random.Random(SEED)
    rows = []
    for sp in ("train", "validation", "test"):
        d = load_dataset("Lakera/gandalf_ignore_instructions", split=sp, revision=REV["Lakera/gandalf_ignore_instructions"])
        rows += [{"text": r["text"], "src_idx": f"{sp}:{i}"} for i, r in enumerate(d)]
    total = len(rows)
    manifest["sets"]["A2-gandalf"] = write("A2-gandalf", 1, sample(rows, 300, rng), {"source": "Lakera/gandalf_ignore_instructions", "split": "train+validation+test", "pool": total, "revision": REV["Lakera/gandalf_ignore_instructions"], "licence": "mit"})

    # In-the-wild jailbreak + regular, sample 300 each
    rng = random.Random(SEED)
    d = load_dataset("TrustAIRLab/in-the-wild-jailbreak-prompts", "jailbreak_2023_12_25", split="train", revision=REV["TrustAIRLab/in-the-wild-jailbreak-prompts"])
    rows = [{"text": r["prompt"], "src_idx": i} for i, r in enumerate(d)]
    manifest["sets"]["A3-itw-jailbreak"] = write("A3-itw-jailbreak", 1, sample(rows, 300, rng), {"source": "TrustAIRLab/in-the-wild-jailbreak-prompts", "config": "jailbreak_2023_12_25", "pool": len(rows), "revision": REV["TrustAIRLab/in-the-wild-jailbreak-prompts"], "licence": "mit"})
    rng = random.Random(SEED)
    d = load_dataset("TrustAIRLab/in-the-wild-jailbreak-prompts", "regular_2023_12_25", split="train", revision=REV["TrustAIRLab/in-the-wild-jailbreak-prompts"])
    rows = [{"text": r["prompt"], "src_idx": i} for i, r in enumerate(d)]
    manifest["sets"]["B4-itw-regular"] = write("B4-itw-regular", 0, sample(rows, 300, rng), {"source": "TrustAIRLab/in-the-wild-jailbreak-prompts", "config": "regular_2023_12_25", "pool": len(rows), "revision": REV["TrustAIRLab/in-the-wild-jailbreak-prompts"], "licence": "mit"})

    # NotInject, all three subsets, stratum kept
    rows = []
    for sp in ("NotInject_one", "NotInject_two", "NotInject_three"):
        d = load_dataset("leolee99/NotInject", split=sp, revision=REV["leolee99/NotInject"])
        rows += [{"text": r["prompt"], "src_idx": f"{sp}:{i}", "stratum": sp} for i, r in enumerate(d)]
    manifest["sets"]["B2-notinject"] = write("B2-notinject", 0, rows, {"source": "leolee99/NotInject", "split": "one+two+three", "revision": REV["leolee99/NotInject"], "licence": "mit"})

    # Dolly instructions, sample 300
    rng = random.Random(SEED)
    d = load_dataset("databricks/databricks-dolly-15k", split="train", revision=REV["databricks/databricks-dolly-15k"])
    rows = [{"text": r["instruction"], "src_idx": i} for i, r in enumerate(d)]
    manifest["sets"]["B3-dolly"] = write("B3-dolly", 0, sample(rows, 300, rng), {"source": "databricks/databricks-dolly-15k", "field": "instruction", "pool": len(rows), "revision": REV["databricks/databricks-dolly-15k"], "licence": "cc-by-sa-3.0"})

    # JBB benign behaviors
    d = load_dataset("JailbreakBench/JBB-Behaviors", "behaviors", split="benign", revision=REV["JailbreakBench/JBB-Behaviors"])
    rows = [{"text": r["Goal"], "src_idx": i} for i, r in enumerate(d)]
    manifest["sets"]["B5-jbb-benign"] = write("B5-jbb-benign", 0, rows, {"source": "JailbreakBench/JBB-Behaviors", "config": "behaviors", "split": "benign", "field": "Goal", "revision": REV["JailbreakBench/JBB-Behaviors"], "licence": "mit"})

    (FIX / "MANIFEST.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("wrote", FIX / "MANIFEST.json")


if __name__ == "__main__":
    sys.exit(main())

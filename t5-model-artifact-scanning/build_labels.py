#!/usr/bin/env python3
"""Derive ground-truth labels for every fixture file, before any scan runs.

Sources of truth, in order:
  * picklescan tests/data and tests/data2 (tag v1.0.5, f15d54d): the suite's own expectations in
    tests/test_scanner.py (saved copy passed as argv[1]); a file is `unsafe` when the suite expects
    infected_files >= 1 for it, `benign` when it expects 0 issues, `junk` when it is not a pickle
    at all or the suite only checks that it parses as an error.
  * modelscan tests/data (tag v0.8.8): `unsafe_zip_pytorch.pt` is the suite's unsafe PyTorch zip,
    `password_protected.zip` is unscannable (junk).
  * fickling test/fixtures (tag v0.1.12): `squeezenet1_0_torchscript_v1_4.pt` is a benign TorchScript.
  * benign-models: real, permissively licensed models (benign).

Nothing here opens a fixture: labels come from names and the suites' test text only.
Usage: python3 -I build_labels.py <saved test_scanner.py> > labels.json
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(ROOT, "fixtures")
test_text = open(sys.argv[1], encoding="utf-8").read()

# Names the picklescan suite expects to parse with an error or treats as non-pickle.
PS_JUNK = {
    "bad_pytorch.pt": "PNG bytes with a .pt name; suite expects 0 issues, scan_err False",
    "not_a_pickle.bin": "starts with a GLOBAL opcode but is invalid UTF-8; suite expects 0 issues",
    "benign_password_protected.zip": "password-protected zip; cannot be opened without the password",
}
PS_BENIGN_EXTRA = {
    "pytorch_model.bin": "legacy PyTorch pickle, suite expects 0 issues",
    "new_pytorch_model.bin": "zip-format PyTorch, suite expects 0 issues",
    "int_array.npy": "numpy int array, suite expects 0 issues",
    "int_arrays.npz": "numpy int arrays, suite expects 0 issues",
    "int_arrays_compressed.npz": "numpy int arrays, suite expects 0 issues",
    "object_array.npy": "numpy object array; suite marks its globals Innocuous, 0 issues (policy call: object arrays are pickles)",
    "object_arrays.npz": "same as object_array.npy",
    "object_arrays_compressed.npz": "same as object_array.npy",
}


def mechanism_for(name):
    """Pull the Dangerous globals the picklescan suite expects for this file, when it names them."""
    stem = re.escape(name)
    pats = [rf'assert_scan\(\s*"{stem}",(.*?)\)\s*\n', rf'{stem}"\)\s*,\s*\n?\s*(?:ScanResult\()?(.*?)\)\s*\n']
    for p in pats:
        m = re.search(p, test_text, re.S)
        if m:
            g = re.findall(r'Global\(\s*"([^"]+)",\s*(?:name=)?"([^"]+)",\s*(?:safety=)?SafetyLevel\.Dangerous', m.group(1))
            if g:
                return [f"{a}.{b}" for a, b in g]
    # data/ style: compare_scan_results(scan_file_path(f"{_root_path}/data/NAME"), var) with var = ScanResult(...) earlier
    m = re.search(rf'data/{stem}"\)\s*,\s*\n?\s*(\w+)\s*,?\s*\n?\s*\)', test_text)
    if m:
        var = m.group(1)
        mv = re.search(rf'\n\s*{var}\s*=\s*ScanResult\((.*?)\)\s*\n\s*(?:compare|with|#|\w+\s*=)', test_text, re.S)
        if mv:
            g = re.findall(r'Global\(\s*"([^"]+)",\s*(?:name=)?"([^"]+)",\s*(?:safety=)?SafetyLevel\.Dangerous', mv.group(1))
            if g:
                return [f"{a}.{b}" for a, b in g]
    # malicious1 family shares one expectation block
    if name.startswith("malicious1_") or name == "malicious1.zip" or name == "malicious1.7z":
        return ["builtins.eval"]
    if name.startswith("malicious2_"):
        return ["posix.system"]
    return []


labels = {}
for sub in ("picklescan-data", "picklescan-data2"):
    for n in sorted(os.listdir(os.path.join(FIX, sub))):
        rel = f"{sub}/{n}"
        if n in PS_JUNK:
            labels[rel] = {"label": "junk", "why": PS_JUNK[n], "source": "picklescan v1.0.5 tests"}
        elif n.startswith("benign") or n in PS_BENIGN_EXTRA:
            labels[rel] = {"label": "benign", "why": PS_BENIGN_EXTRA.get(n, "suite benign fixture"), "source": "picklescan v1.0.5 tests"}
        else:
            labels[rel] = {"label": "unsafe", "mechanism": mechanism_for(n), "source": "picklescan v1.0.5 tests"}
            if n == "malicious-invalid-bytes.pkl":
                labels[rel]["why"] = "suite expects os.system Dangerous AND scan_err=True (partial parse)"
            if n == "broken_model.pkl":
                # No per-file expectation in the suite; the directory total (38 infected = 37 named files + this one)
                # counts it, and a byte view (xxd, no unpickling) shows a GLOBAL builtins exec opcode before the
                # truncated tail, so it is labelled unsafe with a partial-parse note.
                labels[rel]["mechanism"] = ["builtins.exec"]
                labels[rel]["why"] = "truncated pickle carrying builtins.exec; suite counts it in the directory total with scan_err=True"
labels["modelscan-data/unsafe_zip_pytorch.pt"] = {"label": "unsafe", "mechanism": ["(modelscan suite: unsafe PyTorch zip)"], "source": "modelscan v0.8.8 tests/data"}
labels["modelscan-data/password_protected.zip"] = {"label": "junk", "why": "password-protected zip", "source": "modelscan v0.8.8 tests/data"}
labels["fickling-fixtures/squeezenet1_0_torchscript_v1_4.pt"] = {"label": "benign", "why": "TorchScript v1.4 of torchvision squeezenet1_0 (BSD-3 torchvision), fickling test fixture", "source": "fickling v0.1.12 test/fixtures"}
for n, why in {
    "tinyllama-1.1b-chat.Q4_0.gguf": "TinyLlama 1.1B chat Q4_0 GGUF (Apache-2.0), bytes from Ollama tinyllama:latest, same file as R4 T1",
    "all-MiniLM-L6-v2.safetensors": "sentence-transformers/all-MiniLM-L6-v2 model.safetensors, HF rev 1110a24 (Apache-2.0), same file as R4 T3",
    "all-MiniLM-L6-v2.pytorch_model.bin": "same model, pytorch_model.bin (zip-format torch pickle), HF rev 1110a24",
    "all-MiniLM-L6-v2.tf_model.h5": "same model, tf_model.h5 (Keras HDF5), HF rev 1110a24",
    "all-MiniLM-L6-v2.model_O4.onnx": "same model, onnx/model_O4.onnx, HF rev 1110a24",
    "mnist-8.onnx": "onnx/models validated/vision/classification/mnist/model/mnist-8.onnx at main c5cae0f (Apache-2.0)",
}.items():
    labels[f"benign-models/{n}"] = {"label": "benign", "why": why, "source": "public model, permissive licence"}

missing = [k for k in labels if not os.path.exists(os.path.join(FIX, k))]
extra = []
for sub in sorted(os.listdir(FIX)):
    for n in sorted(os.listdir(os.path.join(FIX, sub))):
        if f"{sub}/{n}" not in labels:
            extra.append(f"{sub}/{n}")
assert not missing and not extra, (missing, extra)
counts = {}
for v in labels.values():
    counts[v["label"]] = counts.get(v["label"], 0) + 1
json.dump({"counts": counts, "files": labels}, sys.stdout, indent=1, sort_keys=True)
print(file=sys.stderr)
print("counts", counts, file=sys.stderr)
ps_data_unsafe = sum(1 for k, v in labels.items() if k.startswith("picklescan-data/") and v["label"] == "unsafe")
print("picklescan-data unsafe:", ps_data_unsafe, "(suite directory scan expects infected_files=38 of scanned_files=45)", file=sys.stderr)

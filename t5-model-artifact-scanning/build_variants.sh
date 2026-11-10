#!/usr/bin/env bash
# Builds fixtures-variants/ exactly as PREREGISTRATION.md lists: unchanged bytes of a base fixture under a new
# name or inside a container. Nothing here opens a fixture as a pickle. Logged with bash -x.
set -euxo pipefail
B=/tmp/claude-1000/lab-ai-research/t5-model-artifact-scanning; F=$B/fixtures; V=$B/fixtures-variants
rm -rf "$V"; mkdir -p "$V"
$B/.venv/bin/python -I - "$F" "$V" <<'PY'
import gzip, io, os, shutil, sys, tarfile, zipfile
F, V = sys.argv[1], sys.argv[2]
anchors = {
 "A1": "picklescan-data/malicious1_v4.pkl",
 "A2": "picklescan-data/malicious2_v4.pkl",
 "A3": "picklescan-data2/GHSA-4675-36f9-wf6r.pkl",
 "A4": "modelscan-data/unsafe_zip_pytorch.pt",
 "A5": "picklescan-data2/dns_exfiltration.npy",
 "B1": "benign-models/tinyllama-1.1b-chat.Q4_0.gguf",
 "B2": "benign-models/all-MiniLM-L6-v2.safetensors",
 "B3": "benign-models/all-MiniLM-L6-v2.pytorch_model.bin",
 "B4": "benign-models/all-MiniLM-L6-v2.tf_model.h5",
 "B5": "benign-models/mnist-8.onnx",
 "B6": "benign-models/all-MiniLM-L6-v2.model_O4.onnx",
 "B7": "picklescan-data/benign0_v4.pkl",
 "B8": "picklescan-data/pytorch_model.bin",
}
renames = {"N1": "", "N2": ".bin", "N3": ".txt", "N4": ".safetensors", "N5": ".pth"}
container_anchors = ["A1", "A2", "A3", "A4", "A5", "B5", "B2", "B7", "B8"]
torch_layout_anchors = ["A1", "A2", "A3", "B7"]
manifest = []
def out(code, tcode, name):
    d = os.path.join(V, f"{code}-{tcode}"); os.makedirs(d, exist_ok=True); return os.path.join(d, name)
for code, rel in anchors.items():
    src = os.path.join(F, rel); base = os.path.basename(rel); stem = os.path.splitext(base)[0]
    for tcode, ext in renames.items():
        p = out(code, tcode, stem + ext); shutil.copyfile(src, p); manifest.append((code, tcode, rel, p))
    if code in container_anchors:
        p = out(code, "C1", base + ".zip")
        with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as z: z.write(src, base)
        manifest.append((code, "C1", rel, p)); c1 = p
        p = out(code, "C2", stem + ".zip")
        with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as z: z.write(src, "payload.txt")
        manifest.append((code, "C2", rel, p))
        p = out(code, "C3", base + ".tar")
        with tarfile.open(p, "w") as t: t.add(src, arcname=base)
        manifest.append((code, "C3", rel, p))
        p = out(code, "C4", base + ".tar.gz")
        with tarfile.open(p, "w:gz") as t: t.add(src, arcname=base)
        manifest.append((code, "C4", rel, p))
        p = out(code, "C5", base + ".gz")
        with open(src, "rb") as fi, gzip.open(p, "wb") as fo: shutil.copyfileobj(fi, fo)
        manifest.append((code, "C5", rel, p))
        p = out(code, "C6", stem + "-nested.zip")
        with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as z: z.write(c1, os.path.basename(c1))
        manifest.append((code, "C6", rel, p))
    if code in torch_layout_anchors:
        p = out(code, "C7", stem + "-torchlayout.pt")
        with zipfile.ZipFile(p, "w", zipfile.ZIP_STORED) as z:
            z.write(src, "archive/data.pkl"); z.writestr("archive/version", "3\n")
        manifest.append((code, "C7", rel, p))
with open(os.path.join(V, "MANIFEST.tsv"), "w") as m:
    m.write("anchor\ttransform\tbase\tvariant\n")
    for row in manifest: m.write("\t".join(row) + "\n")
print(len(manifest), "variants")
PY
echo "# fixtures-variants/: test fixtures. Each file is the unchanged bytes of a published base fixture (see MANIFEST.tsv) under a different name or inside a container. No new payload is authored here." > "$V/README-TEST-FIXTURES.txt"
find "$V" -type f ! -name MANIFEST.tsv ! -name 'README-*' | sort | xargs sha256sum > "$B/variants-sha256.txt"
wc -l "$B/variants-sha256.txt"; du -sh "$V"

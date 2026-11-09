#!/usr/bin/env bash
# Builds the pre-registered fixture set. Every command is logged by `bash -x`.
set -euxo pipefail
D=/tmp/claude-1000/lab-ai-research/ai-artifact-sbom; F=$D/fixtures; OS=/usr/share/ollama/.ollama/models
BLOB=sha256-2af3b81862c6be03c769683af18efdadb2c33f60ff32ab6f83e42c043d6c7816
# T1 named GGUF
mkdir -p $F/models-gguf; cp $OS/blobs/$BLOB $F/models-gguf/tinyllama-1.1b-chat.Q4_0.gguf
# T2 Ollama store layout (manifest + all referenced blobs)
M=$F/ollama-store/models; mkdir -p $M/manifests/registry.ollama.ai/library/tinyllama $M/blobs
cp $OS/manifests/registry.ollama.ai/library/tinyllama/latest $M/manifests/registry.ollama.ai/library/tinyllama/latest
for b in $(python3 -c "import json,sys;d=json.load(open(sys.argv[1]));print(' '.join(x['digest'].replace(':','-') for x in [d['config']]+d['layers']))" $OS/manifests/registry.ollama.ai/library/tinyllama/latest); do cp $OS/blobs/$b $M/blobs/$b; done
# T3 safetensors at pinned revision
R=1110a243fdf4706b3f48f1d95db1a4f5529b4d41; H=$F/models-hf/all-MiniLM-L6-v2; mkdir -p $H
for f in config.json model.safetensors; do curl -sSfL -o $H/$f https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/resolve/$R/$f; done
# T4 npm MCP server
mkdir -p $F/mcp-npm; (cd $F/mcp-npm && npm init -y >/dev/null && npm install --ignore-scripts --no-audit --no-fund @modelcontextprotocol/server-filesystem@2025.3.28)
# T5 pip MCP server
python3 -m venv $F/mcp-pip/venv; $F/mcp-pip/venv/bin/pip install -q --disable-pip-version-check mcp-server-git==2025.7.1
# T6 VS Code extension from Open VSX
V=$F/vscode; mkdir -p $V/vsix $V/extensions/esbenp.prettier-vscode-12.4.0
curl -sSfL -o $V/vsix/esbenp.prettier-vscode-12.4.0.vsix https://open-vsx.org/api/esbenp/prettier-vscode/12.4.0/file/esbenp.prettier-vscode-12.4.0.vsix
EXP=$(curl -sSfL https://open-vsx.org/api/esbenp/prettier-vscode/12.4.0/file/esbenp.prettier-vscode-12.4.0.sha256 | awk '{print $1}')
echo "$EXP  $V/vsix/esbenp.prettier-vscode-12.4.0.vsix" | sha256sum -c -
TMP=$(mktemp -d); (cd $TMP && python3 -I -m zipfile -e $V/vsix/esbenp.prettier-vscode-12.4.0.vsix .); cp -r $TMP/extension/. $V/extensions/esbenp.prettier-vscode-12.4.0/; cp $TMP/extension.vsixmanifest $V/extensions/esbenp.prettier-vscode-12.4.0/.vsixmanifest; rm -rf $TMP
# Controls
mkdir -p $F/controls-npm; (cd $F/controls-npm && npm init -y >/dev/null && npm install --ignore-scripts --no-audit --no-fund lodash@4.17.15)
python3 -m venv $F/controls-pip/venv; $F/controls-pip/venv/bin/pip install -q --disable-pip-version-check --no-deps requests==2.19.1
# Variants
VV=$F/variants; mkdir -p $VV/V1 $VV/V2 $VV/V4
ln $F/models-gguf/tinyllama-1.1b-chat.Q4_0.gguf $VV/V1/weights.bin
ln $F/models-gguf/tinyllama-1.1b-chat.Q4_0.gguf $VV/V2/totally-safe-assistant.gguf
mkdir -p $VV/V3/models/manifests/registry.ollama.ai/library/totally-safe-assistant $VV/V3/models/blobs
cp $M/manifests/registry.ollama.ai/library/tinyllama/latest $VV/V3/models/manifests/registry.ollama.ai/library/totally-safe-assistant/latest
for b in $M/blobs/*; do ln $b $VV/V3/models/blobs/; done
cp $F/models-gguf/tinyllama-1.1b-chat.Q4_0.gguf $VV/V4/tinyllama-1.1b-chat.Q4_0.gguf
python3 -I - $VV/V4/tinyllama-1.1b-chat.Q4_0.gguf <<'PY'
import sys
p=sys.argv[1]; off=600_000_000  # deep in tensor data, past the GGUF header/metadata
with open(p,'r+b') as f:
    f.seek(off); b=f.read(1); f.seek(off); f.write(bytes([b[0]^0xFF]))
PY
cp -r $F/mcp-npm $VV/V5; echo '// V5 tamper: re-registered name serving different code' >> $VV/V5/node_modules/@modelcontextprotocol/server-filesystem/dist/index.js
cp -r $F/mcp-npm $VV/V6
python3 -I - $VV/V6/package-lock.json $F/controls-npm/package-lock.json <<'PY'
import json,sys
lk=json.load(open(sys.argv[1])); other=json.load(open(sys.argv[2]))['packages']['node_modules/lodash']
k='node_modules/@modelcontextprotocol/server-filesystem'
lk['packages'][k]['resolved']='https://registry.example.invalid/@modelcontextprotocol/server-filesystem/-/server-filesystem-2025.3.28.tgz'
lk['packages'][k]['integrity']=other['integrity']
json.dump(lk,open(sys.argv[1],'w'),indent=2)
PY
cp -r $F/mcp-pip $VV/V7
SP=$(ls -d $VV/V7/venv/lib/python3*/site-packages); echo '# V7 tamper' >> $SP/mcp_server_git/server.py
cp -r $F/vscode/extensions $VV/V8
python3 -I - $VV/V8/esbenp.prettier-vscode-12.4.0/package.json <<'PY'
import json,sys
p=sys.argv[1]; d=json.load(open(p)); d['publisher']='evil-publisher'; json.dump(d,open(p,'w'),indent=2)
PY

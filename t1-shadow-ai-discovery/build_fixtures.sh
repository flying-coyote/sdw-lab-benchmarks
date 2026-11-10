#!/usr/bin/env bash
# T1-shadow-ai-discovery: plant the static filesystem surfaces into fixtures/endpoint-home.
# Models (S7, S7b), prettier (C3) and the downloads were placed by the commands in COMMANDS.log before this ran.
set -euo pipefail
cd "$(dirname "$0")"
H=fixtures/endpoint-home
log(){ echo "$(date -u +%FT%TZ) $*" | tee -a COMMANDS.log; }

# S3: Cline from Open VSX, unpacked the way VS Code installs it, plus extensions.json
EXT=$H/.vscode/extensions
if [ ! -d "$EXT/saoudrizwan.claude-dev-4.1.26" ]; then
  mkdir -p scratch/vsix && (cd scratch/vsix && rm -rf extension && python3 -c "import zipfile; zipfile.ZipFile('../../dl/saoudrizwan.claude-dev-4.1.26.vsix').extractall('.')")
  mv scratch/vsix/extension "$EXT/saoudrizwan.claude-dev-4.1.26"
  log "S3 unpacked Cline 4.1.26 into $EXT/saoudrizwan.claude-dev-4.1.26 ($(find $EXT/saoudrizwan.claude-dev-4.1.26 -type f | wc -l) files)"
fi
cat > "$EXT/extensions.json" <<'EOF'
[{"identifier":{"id":"saoudrizwan.claude-dev"},"version":"4.1.26","location":{"$mid":1,"path":"/home/dev/.vscode/extensions/saoudrizwan.claude-dev-4.1.26","scheme":"file"},"relativeLocation":"saoudrizwan.claude-dev-4.1.26","metadata":{"installedTimestamp":1762646400000,"source":"gallery"}},
 {"identifier":{"id":"esbenp.prettier-vscode"},"version":"12.4.0","location":{"$mid":1,"path":"/home/dev/.vscode/extensions/esbenp.prettier-vscode-12.4.0","scheme":"file"},"relativeLocation":"esbenp.prettier-vscode-12.4.0","metadata":{"installedTimestamp":1762646400000,"source":"gallery"}}]
EOF

# S4: MCP client configs (no real secrets; LAB_DUMMY_TOKEN is a placeholder string)
cat > "$H/.cursor/mcp.json" <<'EOF'
{
  "mcpServers": {
    "filesystem": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "/home/dev/documents"]},
    "git": {"command": "uvx", "args": ["mcp-server-git", "--repository", "/home/dev/documents"], "env": {"LAB_DUMMY_TOKEN": "lab-dummy"}}
  }
}
EOF
cp "$H/.cursor/mcp.json" "$H/.config/Claude/claude_desktop_config.json"

# S5 and C4: authored Chrome MV3 manifests (fixtures, no code), laid out as Chrome does, ids derived from generated keys
python3 fixtures/make_chrome_fixtures.py "$H"
log "S4 MCP configs, S5/C4 Chrome extension fixtures written"

# C6 benign files, C1 served dir
echo "lab notes (benign control)" > "$H/documents/notes.txt"
head -c 4194304 /dev/zero > "$H/documents/archive.bin"
echo "<html><body>lab benign server (C1)</body></html>" > "$H/public/index.html"
cp fixtures/openai_compat_stub.py "$H/openai_compat_stub.py"

# S6 + C5: venv built with the image's Python so it runs inside the container; pinned
cat > fixtures/ml-requirements.txt <<'EOF'
openai==3.37.0
anthropic==2.3.0
huggingface-hub==2.3.0
safetensors==0.8.0
tokenizers==0.23.3
langchain-core==1.7.0
mcp==2.3.0
gguf==0.19.0
requests==2.34.2
numpy==2.5.4
EOF
if [ ! -x "$H/ml-venv/bin/python" ]; then
  docker run --rm --cpuset-cpus 0-3 -v "$PWD/$H:/home/dev" -v "$PWD/fixtures/ml-requirements.txt:/tmp/req.txt:ro" -u 1000:1000 -e HOME=/home/dev \
    python:3.12-slim sh -c 'python -m venv /home/dev/ml-venv && /home/dev/ml-venv/bin/pip install -q --no-cache-dir -r /tmp/req.txt && /home/dev/ml-venv/bin/pip freeze' | tee fixtures/ml-venv-freeze.txt
  log "S6 venv built in container ($(wc -l < fixtures/ml-venv-freeze.txt) dists)"
fi
chmod -R u+rwX "$H"
log "fixture build complete; sizes: $(du -sh $H | cut -f1) total"

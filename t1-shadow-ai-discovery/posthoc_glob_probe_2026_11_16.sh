set -e
dpkg -i /probe/osquery.deb >/dev/null 2>&1
osqueryi --version
mkdir -p /home/dev/.ollama/models/blobs /home/dev/.cursor /home/dev/projects/x/.cursor /home/dev/projects/x/.vscode /home/dev/a/.hidden/b
echo w > /home/dev/.ollama/models/blobs/sha256-test
echo '{"mcpServers":{}}' > /home/dev/.cursor/mcp.json
echo '{"mcpServers":{}}' > /home/dev/projects/x/.cursor/mcp.json
echo '{"servers":{}}' > /home/dev/projects/x/.vscode/mcp.json
echo '{"mcpServers":{}}' > /home/dev/projects/x/.mcp.json
echo n > /home/dev/a/.hidden/b/nested.txt
echo v > /home/dev/visible.txt
echo "== /home/dev/%%"
osqueryi --json "SELECT path FROM file WHERE path LIKE '/home/dev/%%' AND type='regular' ORDER BY path;"
echo "== /home/%%"
osqueryi --json "SELECT path FROM file WHERE path LIKE '/home/%%' AND type='regular' ORDER BY path;"

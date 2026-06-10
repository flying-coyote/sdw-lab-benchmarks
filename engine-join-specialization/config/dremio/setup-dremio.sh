#!/usr/bin/env bash
# Idempotent Dremio bootstrap: first user + Nessie source (adapted from the verified
# MOAR setup-dremio.sh; the three corrections it documents are kept: secure:false for
# plain-HTTP MinIO, awsRootPath with NO leading slash, real creds not placeholders).
# Run from the host: bash config/dremio/setup-dremio.sh
set -euo pipefail
DREMIO=${DREMIO:-http://localhost:9347}

for i in $(seq 1 60); do
  code=$(curl -s -o /dev/null -w '%{http_code}' "$DREMIO/apiv2/login" || true)
  [ "$code" != "000" ] && break
  sleep 3
done

curl -s -X PUT "$DREMIO/apiv2/bootstrap/firstuser" \
  -H 'Authorization: _dremionull' -H 'Content-Type: application/json' \
  -d '{"userName":"admin","firstName":"Ad","lastName":"Min","email":"admin@example.com","password":"dremioAdmin123"}' \
  >/dev/null 2>&1 || true

TOKEN=$(curl -s -X POST "$DREMIO/apiv2/login" -H 'Content-Type: application/json' \
  -d '{"userName":"admin","password":"dremioAdmin123"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')
AUTH="Authorization: _dremio$TOKEN"

if ! curl -s -o /dev/null -w '%{http_code}' -H "$AUTH" "$DREMIO/api/v3/catalog/by-path/nessie" | grep -q 200; then
  curl -s -X POST "$DREMIO/api/v3/catalog" -H "$AUTH" -H 'Content-Type: application/json' -d '{
    "entityType":"source","name":"nessie","type":"NESSIE",
    "config":{"nessieEndpoint":"http://nessie:19120/api/v2","nessieAuthType":"NONE",
      "awsRootPath":"warehouse","credentialType":"ACCESS_KEY",
      "awsAccessKey":"ejsbench","awsAccessSecret":"ejsbench123","secure":false,
      "propertyList":[{"name":"fs.s3a.path.style.access","value":"true"},
        {"name":"fs.s3a.endpoint","value":"minio:9000"},
        {"name":"dremio.s3.compat","value":"true"},
        {"name":"fs.s3a.connection.ssl.enabled","value":"false"}]}}' >/dev/null
  echo "nessie source created"
else
  echo "nessie source exists"
fi
echo "TOKEN=$TOKEN"

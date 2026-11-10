#!/usr/bin/env bash
# T7 driver: arm S (default features, standard token exchange V2) then arm D (preview token-exchange-delegation).
# Both containers bind 127.0.0.1:8080 only and are run sequentially. Process caps: --cpus=4 on the container,
# ActiveProcessorCount=4 in the JVM, taskset -c 10-13 + nice -n 10 on the harness.
set -euo pipefail
cd "$(dirname "$0")"
IMG="quay.io/keycloak/keycloak@sha256:3f3c5f8e03c614774b4bd9173b88391fefa4153bfc010d8012d59ad825377332"   # 26.8.1
P="taskset -c 10-13 nice -n 10 .venv/bin/python harness.py"
mkdir -p results/raw
LOG=results/raw/driver.log
exec > >(tee -a "$LOG") 2>&1
echo "=== T7 run start $(date -u +%FT%TZ)"
echo "--- clock"; chronyc tracking || true
echo "--- load"; cat /proc/loadavg
echo "--- versions"; docker version --format 'docker server {{.Server.Version}}'; .venv/bin/python --version; .venv/bin/pip freeze
docker image inspect "$IMG" --format 'image {{index .RepoDigests 0}} created {{.Created}}'
ADMIN_PW=$(python3 -c "import secrets;print(secrets.token_urlsafe(18))"); echo "$ADMIN_PW" > results/.admin-pw

start_kc() { # name, extra env...
  local name=$1; shift
  docker rm -f "$name" >/dev/null 2>&1 || true
  nice -n 10 docker run -d --name "$name" --cpus=4 --memory=2g -p 127.0.0.1:8080:8080 \
    -e KC_BOOTSTRAP_ADMIN_USERNAME=admin -e KC_BOOTSTRAP_ADMIN_PASSWORD="$ADMIN_PW" \
    -e JAVA_OPTS_APPEND="-XX:ActiveProcessorCount=4" \
    -e KC_SPI_EVENTS_LISTENER_JBOSS_LOGGING_SUCCESS_LEVEL=info -e KC_SPI_EVENTS_LISTENER_JBOSS_LOGGING_ERROR_LEVEL=warn \
    "$@" "$IMG" start-dev >/dev/null
  for i in $(seq 1 80); do curl -sf -o /dev/null http://127.0.0.1:8080/realms/master && return 0; sleep 3; done
  echo "!!! $name failed to start"; docker logs "$name" | tail -20; return 1
}

echo "=== ARM S: standard token exchange, default features  $(date -u +%FT%TZ)"
S_SINCE=$(date -u +%FT%TZ)
start_kc kc-t7-S
docker logs kc-t7-S 2>&1 | grep -E "Keycloak .* started|Preview features|Installed features" || true
$P setup --arm S --realm t7s
for r in 1 2 3 4 5; do echo "--- S rep $r load $(cut -d' ' -f1-3 /proc/loadavg)"; $P run --arm S --realm t7s --rep $r; done
$P enforcer --arm S --realm t7s --on
for r in 1 2 3; do echo "--- S enforcer rep $r load $(cut -d' ' -f1-3 /proc/loadavg)"; $P run --arm S --realm t7s --rep $r --enforcer; done
$P enforcer --arm S --realm t7s
sleep 2
$P capture --arm S --realm t7s --tag capture --container kc-t7-S --since "$S_SINCE"
docker exec kc-t7-S cat /opt/keycloak/version.txt > results/raw/S/keycloak-version.txt 2>/dev/null || true
docker rm -f kc-t7-S >/dev/null

echo "=== ARM D: preview token-exchange-delegation + parameterized-scopes  $(date -u +%FT%TZ)"
D_SINCE=$(date -u +%FT%TZ)
start_kc kc-t7-D -e KC_FEATURES=token-exchange-delegation,parameterized-scopes
docker logs kc-t7-D 2>&1 | grep -E "Keycloak .* started|Preview features" || true
$P setup --arm D --realm t7d
for r in 1 2 3; do echo "--- D rep $r load $(cut -d' ' -f1-3 /proc/loadavg)"; $P run --arm D --realm t7d --rep $r; done
sleep 2
$P capture --arm D --realm t7d --tag capture --container kc-t7-D --since "$D_SINCE"
docker rm -f kc-t7-D >/dev/null
rm -f results/.admin-pw
echo "--- clock"; chronyc tracking || true
echo "=== T7 run end $(date -u +%FT%TZ)"

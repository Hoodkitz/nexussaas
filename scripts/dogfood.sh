#!/usr/bin/env bash
# Dogfooding: run the project blueprints through the platform (register -> job -> approve -> wait -> reports).
# Usage: scripts/dogfood.sh [API_BASE] ; needs curl + python3. Prints one summary line per blueprint.
set -u
API="${1:-http://127.0.0.1:8000}"
OUT="${DOGFOOD_OUT:-var/dogfood}"; mkdir -p "$OUT"
EMAIL="${DOGFOOD_EMAIL:-dogfood-$(date +%s)@example.com}"; PW="${DOGFOOD_PASSWORD:-Dogfood-Pass-12345}"
j() { python3 -c "import sys,json; d=json.load(sys.stdin); print(eval(sys.argv[1]))" "$1"; }
TOKEN=$(curl -s -X POST "$API/api/v1/auth/register" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PW\",\"name\":\"Dogfood\",\"tenant_name\":\"Dogfood\"}" | j "d.get('access_token','')")
if [ -z "$TOKEN" ]; then
  TOKEN=$(curl -s -X POST "$API/api/v1/auth/login" -H 'Content-Type: application/json' -d "{\"email\":\"$EMAIL\",\"password\":\"$PW\"}" | j "d.get('access_token','')")
fi
[ -n "$TOKEN" ] || { echo "login failed"; exit 1; }
H=(-H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json')
for bp in projects/blueprints/*.json; do
  name=$(basename "$bp" .json)
  body=$(python3 -c "import json,sys; print(json.dumps({'blueprint': json.load(open(sys.argv[1])), 'idempotency_key': 'dogfood-'+sys.argv[2]+'-'+sys.argv[3]}))" "$bp" "$name" "$(date +%s)")
  resp=$(curl -s -X POST "$API/api/v1/jobs" "${H[@]}" -d "$body")
  id=$(echo "$resp" | j "d.get('id','')")
  if [ -z "$id" ]; then echo "$name | create failed | $resp"; continue; fi
  status=""; approvals=0
  for i in $(seq 1 240); do
    status=$(curl -s "$API/api/v1/jobs/$id" "${H[@]}" | j "d.get('status','')")
    case "$status" in
      BLUEPRINT_APPROVAL|HUMAN_RELEASE_APPROVAL)
        curl -s -X POST "$API/api/v1/jobs/$id/decision" "${H[@]}" -d '{"approve": true, "comment": "dogfood"}' >/dev/null; approvals=$((approvals+1));;
      COMPLETED|FAILED|CANCELLED|REJECTED) break;;
    esac
    sleep 2
  done
  for r in blueprint ddl static tests security; do curl -s "$API/api/v1/jobs/$id/reports/$r" "${H[@]}" > "$OUT/$name.$r.json"; done
  curl -s "$API/api/v1/jobs/$id/artifact" "${H[@]}" -o "$OUT/$name.zip"
  size=$(stat -c %s "$OUT/$name.zip" 2>/dev/null || echo 0)
  tests=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d.get('summary') or d.get('passed') or d.get('status') or str(d)[:80])" "$OUT/$name.tests.json" 2>/dev/null)
  sec=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d.get('summary') or d.get('findings') and len(d['findings']) or d.get('status') or str(d)[:80])" "$OUT/$name.security.json" 2>/dev/null)
  echo "$name | job $id | $status | approvals=$approvals | artifact ${size}B | tests: $tests | security: $sec"
done

#!/usr/bin/env bash
set -euo pipefail

HOST="${1:-localhost}"

function curl_json() {
  local label="$1"
  local url="$2"
  echo "==> $label: $url"
  http_code=$(curl -sS -m 8 -w "\n%{http_code}" "$url")
  body="$(echo "$http_code" | head -n -1)"
  code="$(echo "$http_code" | tail -n1)"
  echo "HTTP $code"
  # print small snippet of body for quick inspection
  echo "$body" | head -c 500
  echo -e "\n"
  [[ "$code" =~ ^2[0-9]{2}$ ]] || return 1
}

ok=0
fail=0

curl_json "Weather current" "http://$HOST:8001/current" && ((ok+=1)) || ((fail+=1))
curl_json "Govee sensors"   "http://$HOST:8002/sensors/current" && ((ok+=1)) || ((fail+=1))
curl_json "Hubitat devices" "http://$HOST:8000/devices" && ((ok+=1)) || ((fail+=1))

echo "--------------------------------------------------"
echo "Integration results: OK=$ok FAIL=$fail"
if [[ "$fail" -eq 0 ]]; then
  exit 0
else
  exit 1
fi

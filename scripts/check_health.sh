#!/usr/bin/env bash
set -euo pipefail

HOST="${1:-localhost}"

# name|url pattern; you can add/remove services here
SERVICES=(
  "weather|http://$HOST:8001/health"
  "govee|http://$HOST:8002/health"
  "database|http://$HOST:8003/health"
  "dashboard|http://$HOST:8004/"
  "hubitat|http://$HOST:8000/health"
)

GREEN="$(tput setaf 2 || true)"
RED="$(tput setaf 1 || true)"
YELLOW="$(tput setaf 3 || true)"
RESET="$(tput sgr0 || true)"

ok_count=0
fail_count=0

echo "Checking services on host: $HOST"
for entry in "${SERVICES[@]}"; do
  name="${entry%%|*}"
  url="${entry##*|}"

  # Accept 2xx and 3xx as OK (dashboard often redirects)
  code="$(curl -sS -m 5 -o /dev/null -w '%{http_code}' "$url" || true)"
  if [[ "$code" =~ ^2|3[0-9]{2}$ ]] || [[ "$code" =~ ^2[0-9]{2}$ ]] || [[ "$code" =~ ^3[0-9]{2}$ ]]; then
    printf "%s[OK]%s %-9s => %s (%s)\n" "$GREEN" "$RESET" "$name" "$url" "$code"
    ((ok_count+=1))
  else
    printf "%s[FAIL]%s %-9s => %s (%s)\n" "$RED" "$RESET" "$name" "$url" "${code:-no-response}"
    ((fail_count+=1))
  fi
done

echo "--------------------------------------------------"
if [[ "$fail_count" -eq 0 ]]; then
  echo -e "${GREEN}All services healthy ($ok_count/${#SERVICES[@]}).${RESET}"
  exit 0
else
  echo -e "${YELLOW}Healthy: $ok_count${RESET}  ${RED}Failed: $fail_count${RESET}  (total: ${#SERVICES[@]})"
  exit 1
fi

# Operations Runbook (Home Server)

Daily quick checks
- make health — Verify all services respond 200 OK
- make open-dashboard — Confirm dashboard loads and shows data
- make redis-monitor — Spot-check message flow (press Ctrl+C to exit)

Deep-dive tests
- make integration — Exercise weather, govee, and hubitat endpoints and print summaries
- Inspect logs of a service (example if using Docker): docker logs --tail=200 -f <container>

Troubleshooting

Health endpoint fails
1) Confirm service is running (docker ps or system service status).
2) Check logs for timeouts or authentication failures.
3) Validate environment variables (.env) and restart the service.

No data on dashboard
1) Hit backend endpoints directly (see integration test).
2) Ensure Redis is reachable: redis-cli ping (expect "PONG").
3) Wait for next scheduled update (weather ~15 minutes).

Redis monitor is silent
1) Ensure publishers are active (trigger an endpoint to publish).
2) Confirm pub/sub channel names in your configuration.
3) Check that Redis is accessible on port 6379 and not firewalled.

Rollback / restart
- Restart a single service container: docker restart <container_name>
- Rebuild and redeploy (only if needed): docker compose build <service> && docker compose up -d <service>
- If a new image misbehaves, redeploy the previous image tag (if you tag builds) or restore from a known-good backup.

Resource hygiene (low-cost)
- Avoid storing large logs or historical metrics.
- Keep intervals conservative to reduce load on devices and network.
- Prefer in-memory caches and short-lived data.

Useful one-liners
- Port check: lsof -i :8001 || netstat -tulpn | grep 8001
- Redis ping: redis-cli -h 127.0.0.1 -p 6379 ping
- Quick HTTP check: curl -sS -m 5 -o /dev/null -w "%{http_code}\n" http://localhost:8001/health

See docs/NEXT_STEPS.md for a complete verification flow and success criteria.

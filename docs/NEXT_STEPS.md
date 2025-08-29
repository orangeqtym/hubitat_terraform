# Next Steps Guide — IoT Infrastructure Deployment (Home Server, Low-Cost)

This guide helps you validate the full stack, exercise integrations, monitor runtime behavior, and know when you're "done" — all with minimal operational overhead and zero persistent data growth.

Current status
- ✅ Redis message broker (port 6379)
- ✅ Hubitat service (port 8000) — HEALTHY with connected devices
- ✅ Weather service (port 8001)
- ✅ Govee service (port 8002)
- ✅ Database service (port 8003)
- ✅ Dashboard service (port 8004)

Key fixes completed
- ✅ Redis client compatibility resolved
- ✅ Environment configuration fixed
- ✅ Docker images rebuilt and deployed

Immediate next steps

Option A — One-liners (recommended)
- Check all health endpoints:
  make health
- Test cross-service integration:
  make integration
- Monitor Redis pub/sub:
  make redis-monitor
- Open dashboard in a browser:
  make open-dashboard

Option B — Raw commands
1) Health check all services (5 min)
- Weather:   curl http://localhost:8001/health
- Govee:     curl http://localhost:8002/health
- Database:  curl http://localhost:8003/health
- Dashboard: curl http://localhost:8004/

2) Access dashboard (2 min)
- Browse to http://localhost:8004
- Expect to see live system health across services

3) Test service integration (10 min)
- Weather data:  curl http://localhost:8001/current
- Govee sensors: curl http://localhost:8002/sensors/current
- Hubitat devices: curl http://localhost:8000/devices

4) Monitor Redis communication (5 min)
- Docker (container named "redis"): docker exec -it redis redis-cli monitor
- Native: redis-cli -h 127.0.0.1 -p 6379 monitor

Verification checklist (success criteria)
- All health endpoints return HTTP 200 and show “healthy” state where applicable
- Dashboard shows real-time data updates
- Sensor data is flowing: Govee → Redis → Database
- Weather data updates roughly every 15 minutes
- Hubitat device list loads and device commands succeed (if you test commands)

Optional improvements

Short term
- Normalize any remaining async/await issues across services
- Verify end-to-end Govee → Database → Dashboard flow
- Validate weather collection and in-memory caching

Medium term
- Automate deployment in your environment
- Add minimal health monitoring and state-change alerts
- Enhance dashboard with charts

Long term
- CI/CD pipeline for automated builds and deploys
- TLS for service access
- Simple backup strategy for database and critical config

Troubleshooting (quick wins)
- Port conflicts: ensure ports 8000–8004 and 6379 are free (or update env).
- Redis connectivity: ping locally (redis-cli ping) and from services at startup.
- Config issues: verify .env values and restart services.
- Service stuck “unhealthy”: check logs for timeouts, auth, or upstream issues.
- Dashboard empty: confirm backend endpoints return data; refresh after 15 minutes to see scheduled updates.

Maintenance tips (low-cost)
- Keep logs small (stdout only, rely on system/container rotation).
- Use in-memory caching; avoid persistent analytics storage.
- Keep polling/scheduling intervals modest (15–30 min) unless you need faster updates.

You can run all checks and tests with the provided scripts in scripts/ and Makefile targets. See docs/RUNBOOK.md for daily operations and rollback tips.

.PHONY: help health integration redis-monitor open-dashboard

help:
	@echo "Common commands:"
	@echo "  make health           - Check all service health endpoints"
	@echo "  make integration      - Exercise cross-service flows"
	@echo "  make redis-monitor    - Monitor Redis pub/sub traffic"
	@echo "  make open-dashboard   - Open the dashboard in your browser"

health:
	@bash scripts/check_health.sh

integration:
	@bash scripts/test_integration.sh

redis-monitor:
	@bash scripts/monitor_redis.sh

open-dashboard:
	@if command -v xdg-open >/dev/null 2>&1; then xdg-open http://localhost:8004; \
	elif command -v open >/dev/null 2>&1; then open http://localhost:8004; \
	elif command -v start >/dev/null 2>&1; then start http://localhost:8004; \
	else echo "Open http://localhost:8004 in your browser"; fi

# Start Here: Sprint A (P0) — Low-Cost, Home Server Focus

Objective
- Complete the highest-impact, lowest-effort improvements (P0) to boost stability, clarity, and responsiveness without increasing storage cost.
- Keep everything simple, in-memory, and easy to maintain.

Outcomes of Sprint A (what “done” looks like)
- No blocking I/O in async paths; external calls use async clients with timeouts and small retry/backoff.
- Redis client is modern and uses a single shared connection/pool.
- Configuration is centralized and validated at startup.
- Logs are structured and bounded (stdout; keep short messages).
- Codebase passes basic lint/format/type checks.

Prerequisites (local/dev)
- Python 3.11+ recommended.
- A running Redis (Docker or native).
- A working virtual environment.

Quick setup
1) Create and activate a virtual environment
- macOS/Linux:
  python3 -m venv .venv
  source .venv/bin/activate
- Windows (PowerShell):
  py -3 -m venv .venv
  .\.venv\Scripts\Activate.ps1

2) Install baseline dependencies (example; adjust to your needs)
- Core:
  pip install fastapi uvicorn
- Async HTTP & retries:
  pip install "httpx[http2]" tenacity
- Redis (async API):
  pip install redis
- Config:
  pip install pydantic pydantic-settings python-dotenv
- Tooling:
  pip install ruff black isort mypy types-requests types-redis

3) Copy and fill your environment
- cp .env.sample .env
- Fill in your values (keep secrets local and out of version control).

How to work through Sprint A
1) Centralized configuration
- Introduce a small settings module using Pydantic Settings to load/validate environment variables on startup (fail fast with clear errors).
- Provide sensible defaults for non-sensitive values (e.g., Redis host/port).

2) Async-safe HTTP + timeouts + retries
- Replace blocking HTTP calls with an async client.
- Set reasonable timeouts (connect/read total under ~10 seconds for home use).
- Add a small retry with jitter for transient network issues (limit retries to keep latency bounded).

3) Modernize Redis client
- Use the maintained async API and one shared connection or pool.
- Keep messages small; no long histories.

4) Structured logging
- Emit JSON or concise key-value logs to stdout with timestamp, level, service, action, outcome, and latency_ms where applicable.
- Keep logs short; rely on system/container log rotation.

5) Lint/format/type-check
- Add ruff + black + isort + mypy; fix critical issues.
- Run tools locally before committing.

Validation (end of Sprint A)
- Basic smoke tests succeed.
- Health endpoint(s) respond quickly and show config/connection status.
- No lingering blocking calls in async paths (verified by code inspection and latency).
- Linters and type checks pass.

Timebox
- Total: ~1–2 days elapsed (can be completed over a weekend).
- Individual task budgets:
  - Config: 2–3h
  - Async HTTP + retries: 2–4h
  - Redis modernization: 2–3h
  - Logging structure: 2–3h
  - Tooling: 2–4h

Tips for home-server, low-cost setup
- Keep everything in memory; avoid persistent stores and large logs.
- Prefer longer polling intervals if acceptable (e.g., 15–30 minutes).
- Test changes incrementally; revert quickly if instability appears.

What to do next (Sprint B preview)
- Add /live and /ready endpoints, lightweight metrics, and an async scheduler for periodic tasks.

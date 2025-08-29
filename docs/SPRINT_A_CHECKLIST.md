# Sprint A Checklist (P0)

Goal: High-impact stability and clarity improvements with minimal cost and complexity.

Legend
- [ ] Todo
- [x] Done

1) Centralized configuration (Pydantic Settings)
- [ ] Create a settings module to load environment variables once at startup.
- [ ] Validate required keys (fail fast with clear error).
- [ ] Provide defaults for non-sensitive values (e.g., Redis host/port).
- [ ] Document variables in `.env.sample`.

Verification
- [ ] App fails fast on missing/invalid config with a clear message.
- [ ] `/health` or similar endpoint shows correct configuration-related status.

2) Async HTTP client with timeouts + retries
- [ ] Replace blocking HTTP calls with an async client.
- [ ] Add per-call timeouts (connect/read).
- [ ] Add small retry/backoff (with jitter) for transient errors.
- [ ] Reuse a single client/pool where possible.

Verification
- [ ] P95 latency improves or remains stable.
- [ ] Transient network hiccups no longer cause immediate failures.
- [ ] No warnings about blocking calls in async code paths.

3) Modernize Redis client
- [ ] Use maintained async Redis API.
- [ ] Single shared connection/pool; test `.ping()` at startup.
- [ ] Keep pub/sub payloads small and JSON-only.
- [ ] Handle publish errors gracefully (log, do not crash).

Verification
- [ ] Startup confirms Redis connectivity.
- [ ] Publish/subscribe works for basic messages.
- [ ] No unbounded memory growth or stale connections.

4) Structured logging to stdout
- [ ] Emit JSON or concise key-value logs with minimal schema:
      ts, level, service, action, outcome, latency_ms (when applicable)
- [ ] Keep messages short and avoid verbose dumps.
- [ ] Ensure logs rotate externally (journald/docker) if needed.

Verification
- [ ] Errors show clear context with minimal noise.
- [ ] Log volume remains small during normal operation.

5) Linting/formatting/type checks
- [ ] Add and run: ruff, black, isort, mypy.
- [ ] Configure basic rules; fix critical issues.

Suggested commands
- Format:
  black .
  isort .
- Lint:
  ruff check .
- Types:
  mypy .

Verification
- [ ] CI or a local script runs the above tools successfully.
- [ ] No blocking lint/type errors remain.

Smoke test (end of sprint)
- [ ] Start the service(s) and confirm they boot with validated config.
- [ ] Exercise a couple of endpoints; confirm successful responses.
- [ ] Check logs for clarity and errors.
- [ ] Observe Redis connectivity (ping + small pub/sub message).

Time estimates (for planning)
- Config: 2–3h
- Async HTTP + retries: 2–4h
- Redis modernization: 2–3h
- Logging structure: 2–3h
- Tooling: 2–4h

Notes for home environment
- Use conservative timeouts and retry counts.
- Avoid persistent storage; rely on in-memory caching and small logs.
- Keep intervals for scheduled tasks modest (e.g., 15–30 minutes).

# Project Upgrade Recommendations (Home Server, Low-Cost)

Context and constraints
- Runs on a home server; prioritize reliability and simplicity over enterprise features.
- Internet egress is free; storage incurs cost. Avoid persistent, high-volume storage.
- Keep resource usage low; prefer in-memory caches and ephemeral data.
- Aim for upgrades that reduce errors and maintenance while keeping infra minimal.

Priority levels
- P0 = Must do soon (stability, clarity, low effort/high impact)
- P1 = Should do next (reliability, observability, maintainability)
- P2 = Nice to have (power features, polish)

Estimation notes
- Estimates include implementation + basic tests + minimal docs.
- Add ~25% buffer if unfamiliar with the tools.
- Keep changes incremental and test after each step.

Roadmap overview
- Sprint A (P0, ~1–2 days): Async-safe HTTP, Redis client modernization, settings cleanup, structured logging, lint/type checks.
- Sprint B (P1, ~1–1.5 days): Readiness/liveness split, retry/backoff, lightweight metrics, async scheduler.
- Sprint C (P1/P2, ~1–2 days): Concurrency/rate limits, API polish, minimal infra hygiene, lightweight alerting.

---

P0 — High impact, low effort

1) Use async HTTP client with timeouts and retries
- What: Replace synchronous HTTP calls in async paths with an async client and add per-call timeouts plus small retry/backoff.
- Why: Prevents event loop blocking and improves responsiveness.
- Estimate: 2–4 hours

2) Modernize Redis client and connection handling
- What: Use a maintained async Redis client and keep a shared connection/pool; keep pub/sub payloads small (JSON only).
- Why: Fewer dependencies, better reliability.
- Estimate: 2–3 hours

3) Centralized configuration with validation
- What: Use a typed settings layer that reads environment variables once at startup, validates them, and provides sensible defaults. Include a concise `.env.sample`.
- Why: Prevents runtime surprises; improves local setup and testing.
- Estimate: 2–3 hours

4) Structured logging with size controls
- What: JSON logs with minimal schema (timestamp, level, service, endpoint, latency_ms, outcome). Log to stdout and rely on rotation where applicable.
- Why: Easier debugging without unbounded storage.
- Estimate: 2–3 hours

5) Linting, formatting, and type checks
- What: Add ruff + black + isort + mypy; fix critical issues and enforce via pre-commit or a simple CI task.
- Why: Improves readability and prevents common bugs.
- Estimate: 2–4 hours

Acceptance criteria for P0
- No blocking I/O in async code paths.
- App boots with validated config.
- Logs are structured; codebase passes basic lint/format/type checks.

---

P1 — Reliability and maintainability

6) Readiness vs liveness endpoints
- What: `/live` = process up; `/ready` = dependencies healthy (e.g., external APIs and Redis) and config valid.
- Why: Safer restarts and better health signaling for scripts or supervisors.
- Estimate: 1–2 hours

7) Retry/backoff and lightweight circuit breaker
- What: Add retries with jitter for transient failures and a simple breaker to avoid hammering failing dependencies.
- Why: Prevents cascading failures and reduces error bursts.
- Estimate: 3–5 hours

8) Lightweight metrics without persistent storage
- What: Expose in-memory metrics (request counts, latencies, error rates, cache hit/miss) on `/metrics`. Optionally run a tiny local scraper or rely on `/diagnostics`.
- Why: Observability with negligible storage cost.
- Estimate: 2–4 hours

9) Replace thread-based scheduler with async scheduler
- What: Use an async scheduler that runs within the event loop for periodic tasks with conservative intervals.
- Why: Avoids thread/event-loop mismatch; simpler lifecycle.
- Estimate: 2–3 hours

10) Concurrency caps and simple rate limits
- What: Use a semaphore to cap concurrent outbound calls; add a small in-memory token bucket per endpoint or key.
- Why: Prevents overload of local devices and external APIs.
- Estimate: 3–5 hours

Acceptance criteria for P1
- `/live` and `/ready` reflect accurate states.
- Transient failures don’t crash the app; retries are bounded and respectful.
- Metrics available without heavy dependencies.
- Scheduler integrates cleanly with the async runtime.

---

P2 — Power features and polish

11) API response models and clearer errors
- What: Define typed response models and include examples in the API docs; normalize error shapes.
- Why: Cleaner contracts and simpler client code.
- Estimate: 3–6 hours

12) Stale-while-revalidate cache
- What: Serve cached responses immediately and refresh in the background when the TTL expires.
- Why: Faster responses without persistent storage.
- Estimate: 3–5 hours

13) Minimal alerting for home use
- What: A small watchdog (cron or systemd timer) that checks `/ready` and `/health` and sends a lightweight notification on state changes.
- Why: Detect real failures without heavy monitoring stacks.
- Estimate: 2–3 hours

14) Minimal infrastructure hygiene
- What: Pin provider/tool versions, validate plans in a lightweight pipeline or pre-commit, and clean unused roles/bindings. Keep state handling simple.
- Why: Safer, more reproducible changes at home scale.
- Estimate: 3–6 hours

15) Developer experience
- What: Add a quick-start with local run instructions, basic Makefile targets, and a succinct README with environment variable documentation.
- Why: Faster maintenance and onboarding (for future you).
- Estimate: 2–4 hours

Acceptance criteria for P2
- API contracts are consistent and discoverable.
- Cache is responsive even during refresh.
- Simple alerts on health state changes.
- Basic infra processes are predictable.

---

Cost-conscious guidance
- Prefer in-memory and ephemeral storage; avoid local databases or long-lived logs.
- Keep message payloads small and avoid historical retention in queues.
- Limit scheduled jobs to modest intervals (e.g., every 15–30 minutes) unless real-time updates are required.
- If you later add metrics scraping, cap retention to a day or two and avoid high-cardinality labels.

Time estimates summary
- P0 total: ~8–16 hours
- P1 total: ~9–16 hours
- P2 total: ~10–20 hours
- Grand total (all): ~27–52 hours

Suggested execution order
1) P0 items 1–5
2) P1 items 6–9, then 10
3) P2 items 11–15 as needed

Measurable outcomes to aim for
- P95 latency down 30–50% for hot endpoints.
- Error rate < 1% under normal load.
- Boot-time config validation: failures are clear and logged once.
- Logs remain small and rotated; no persistent storage growth.

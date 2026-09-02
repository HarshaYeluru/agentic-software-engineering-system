# url_shortener architecture

Architecture notes specific to the generated URL-shortener service itself. For the agent that builds it — the orchestrator, the task graph, why writes are gated the way they are — see [../../docs/architecture.md](../../docs/architecture.md).

## Deployment path

The local reference service uses SQLite because it requires no setup. A production version would use PostgreSQL for links, Redis as a cache-aside lookup layer, and a queue plus worker for click analytics. Redirects should remain fast even if the analytics pipeline is delayed, so counts are eventually consistent.

See [hosting.md](hosting.md) for a concrete, step-by-step guide to actually standing this up.

## Observability

`url_shortener` exposes the three signals an on-call engineer needs to answer "is it up, is it healthy, and why":

- **Structured logs** — every request is logged as one JSON line (`request_id`, `method`, `path` [route template, not the raw URL, to keep cardinality bounded], `status`, `duration_ms`) via the `observability_middleware` in `url_shortener/app.py`. JSON-per-line is directly ingestible by Splunk/ELK/Datadog log pipelines without a parsing rule.
- **Metrics** — `GET /metrics` exposes Prometheus text format: `url_shortener_requests_total` (by method/path/status), `url_shortener_request_duration_seconds` (a histogram, for p50/p95/p99 latency and SLO burn-rate alerts), `url_shortener_links_created_total`, and `url_shortener_redirects_total{result=success|not_found}`. Point a Prometheus scrape config or a Grafana Agent at this endpoint; the histogram buckets are the default `prometheus_client` buckets, tunable once real traffic shows where the interesting latency band is.
- **Correlation IDs** — every response carries `X-Request-ID` (propagated from the caller's own header if present, so a request can be traced end-to-end across a future gateway/service boundary).

See [runbook.md](runbook.md) for how these signals are actually used during an incident.

## High availability and failover

The reference service is intentionally single-node for local review, but the design keeps HA additive rather than requiring a rewrite:

- **Liveness vs. readiness are separated on purpose.** `GET /health` only proves the process is scheduling requests (safe for a container orchestrator to use for restart decisions). `GET /ready` additionally pings the database (`LinkStore.ping`) and returns 503 if it can't reach it, so a load balancer or orchestrator can pull a node out of rotation *before* it serves failed requests — the standard signal a Kubernetes `readinessProbe` or an ALB health check expects.
- **Stateless application tier.** The FastAPI process holds no in-memory session state; all state is in the store. That means the app tier can run active-active behind a load balancer today — the only shared-state dependency is the database.
- **Data tier is the actual HA boundary.** SQLite is a single-writer, single-file store and is *not* the HA-capable piece; it's a stand-in for the production target: PostgreSQL with a synchronous standby (or a managed multi-AZ instance) for the link table, plus Redis for the cache-aside redirect path. Promoting a standby to primary on failure is the failover event; because the app tier is stateless, failover is transparent to it beyond a reconnect.
- **Multi-region posture.** With Postgres/Redis swapped in, an active-active multi-region deployment reduces to: region-local read replicas for redirect lookups (redirects are latency-sensitive and read-heavy), writes routed to the current primary region, and analytics decoupled onto a queue so a regional blip in the analytics worker never blocks the redirect path (this is already modeled today: click recording never blocks the 302 response).
- **Graceful degradation over hard failure.** Analytics are explicitly eventually consistent (see the deployment-path note above) so a slow or down analytics path degrades dashboard freshness, not redirect availability — the failure mode that matters least is allowed to fail first.

## Related docs

- [hosting.md](hosting.md) — a practical, step-by-step guide to hosting this service.
- [runbook.md](runbook.md) — on-call playbook and RCA template.
- [../../docs/architecture.md](../../docs/architecture.md) — the agent's own architecture (control flow, guardrails, why writes are gated the way they are).

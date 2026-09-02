# Operational runbook: url_shortener

An on-call playbook for the generated service, plus the RCA template used after an incident. This is written against the real signals the service emits (see [Observability](architecture.md#observability)) so every step below is something you can actually run today, not aspirational tooling.

## Service map

- **Process**: FastAPI app, single stateless process (`url_shortener.app:app`).
- **Dependency**: SQLite file (`data/url_shortener.sqlite3` locally; Postgres in the production target — see [architecture.md](architecture.md#url-shortener-deployment-path)).
- **Health surface**: `GET /health` (liveness — process is scheduling requests), `GET /ready` (readiness — process **and** database are reachable).
- **Metrics surface**: `GET /metrics` — `url_shortener_requests_total{method,path,status}`, `url_shortener_request_duration_seconds` (histogram), `url_shortener_links_created_total`, `url_shortener_redirects_total{result}`.
- **Logs**: one JSON line per request to stdout — `request_id`, `method`, `path`, `status`, `duration_ms`. `X-Request-ID` is echoed on every response, so a report from a user ("my redirect didn't work") can be traced to one exact log line if they capture that header.

## Alerting signals (what a Prometheus rule should watch)

| Signal | Query shape | Why it matters |
| --- | --- | --- |
| Error rate | `rate(url_shortener_requests_total{status=~"5.."}[5m])` | Server-side failures, not client 4xxs |
| Redirect miss rate | `rate(url_shortener_redirects_total{result="not_found"}[5m])` vs `{result="success"}` | A sudden spike usually means a bad deploy or expired-link mass-expiry, not organic 404s |
| Redirect latency | `histogram_quantile(0.99, url_shortener_request_duration_seconds_bucket{path="/{code}"})` | Redirects are the latency-sensitive path; this is the number users feel |
| Readiness flapping | `up{job="url_shortener"}` combined with repeated `/ready` 503s | Database connectivity issue, not an app bug |

## Incident playbooks

### 1. Redirect latency spike (p99 on `/{code}` climbing)

1. Check `/ready` first — if it's 503, this is a database problem, not an app problem; skip to the database section below.
2. Compare `url_shortener_request_duration_seconds` for `/{code}` against `/v1/links` — if only redirects are slow, suspect the `find_active_link` read path (index missing/degraded in the production DB) rather than the whole service.
3. Sample recent logs for `path: "/{code}"` and look at the `duration_ms` distribution and `request_id`s — grab a few slow ones and correlate with database-side slow-query logs by timestamp.
4. Mitigation: in the production target (Postgres + Redis), this is the cache-aside layer's job — confirm cache hit rate isn't degraded before assuming a DB regression.

### 2. Analytics undercounting (click counts look low or stalled)

1. This should **never** page on its own — analytics are explicitly eventually consistent so the redirect path is protected (see the architecture note). Confirm redirects (`url_shortener_redirects_total{result="success"}`) are still incrementing normally; if they are, this is isolated to the analytics/click-recording path.
2. Check for elevated 5xx on `GET /v1/links/{code}/analytics` specifically.
3. In the production design, click events are enqueued and processed by an async worker — check worker lag/queue depth, not the API process.

### 3. Link creation failures spike (elevated 5xx or 503 on `POST /v1/links`)

1. A `503` here specifically means `MAX_CODE_GENERATION_ATTEMPTS` (5) was exhausted — i.e., repeated short-code collisions. At low volume this points to a broken random source before it points to genuine keyspace exhaustion (7-character alphanumeric codes have ~3.5 trillion combinations).
2. Check `/ready` — if writes are failing because the database itself is unreachable, creation failures are a symptom of the database incident, not the root cause.
3. Grep logs for `"path": "/v1/links"` and `"status": 5` to get the affected `request_id`s and a request-rate estimate for the incident timeline.

### 4. Readiness probe failing / node pulled from rotation

1. `/ready` returning 503 means `LinkStore.ping()` failed. Confirm whether this is one node (network partition to the DB from that node) or all nodes (DB is actually down) — the blast radius changes the response.
2. If all nodes: this is a database incident, not an application incident — follow the database team's runbook; the app-tier action is simply "wait, don't restart the app" since restarting a stateless process won't fix an unreachable dependency.
3. If one node: the orchestrator/load balancer should already have pulled it from rotation via the failed readiness check — confirm it did, rather than manually intervening.

## RCA template

Fill this in after any page, even a false alarm — a false alarm with an undocumented cause becomes a real page later.

```
## Incident: <short title>
Detected: <UTC timestamp>            Resolved: <UTC timestamp>
Detected by: <alert name / person>   Severity: <Sev1-4>

### Timeline
- HH:MM  <what was observed, with the exact metric/log line>
- HH:MM  <action taken>
- HH:MM  <resolution>

### Impact
- Affected endpoint(s): <e.g. GET /{code}>
- User-visible effect: <e.g. 12% of redirects returned 503 for 6 minutes>
- Requests affected (from url_shortener_requests_total delta): <n>

### Root cause
<the actual mechanism, not the symptom — "database connection pool exhausted"
not "the site was slow">

### Contributing factors
<things that made it worse or harder to diagnose, e.g. missing alert,
ambiguous log line, no readiness check at the time>

### Action items
- [ ] <fix, owner, due date>
- [ ] <fix, owner, due date>
```

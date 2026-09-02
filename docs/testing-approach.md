# Testing approach

How correctness and output quality are validated in this project, and — as important — what isn't validated yet.

## The layers

This project has five distinct validation layers, each catching a different class of problem. They're deliberately not collapsed into one "run the tests" step, because they run at different times for different reasons.

### 1. Unit tests — the workflow logic itself

`tests/test_orchestrator.py`, `tests/test_materializer.py`, `tests/test_cleanup.py`. These exercise `agentic_system` directly: dependency-gated task sequencing, the approval gate (blocked vs. approved paths), risk-level escalation, brownfield impact scoring, and the file-materialization/cleanup safety rails (e.g. `remove_generated_application` refusing to delete an unmarked directory). Because the agent functions are deterministic, these are exact-value assertions (`assertEqual(result.status, "completed")`, specific risk thresholds) rather than fuzzy/semantic checks — see [Known limitations](#known-limitations-and-trade-offs) for what that trade-off costs.

### 2. Integration tests — the generated service, for real

`tests/test_url_shortener.py`. These run FastAPI's `TestClient` against a real (temp-file) SQLite database — no mocking of the store — covering the happy path (create → redirect → analytics), validation failures, unknown codes, and now the observability surface (`/health`, `/ready`, `/metrics`, the `X-Request-ID` header). This is the same test file that gets copied into every materialized application, so it validates both the reference implementation and every generated artifact with one source of truth.

### 3. Generated-artifact validation — a layer specific to this project

Most projects stop at "tests pass." Here, `agentic_system.verifier.verify_generated_application` runs as part of the workflow's own `validation` task, *every time the CLI produces an application*: it byte-compiles the materialized app, runs its copied test suite in an isolated subprocess, and confirms the generated `.github/workflows/{ci,cd}.yml` exist and contain a `jobs:` section. If any of that fails, the orchestrator doesn't just report a failure — `WorkflowOrchestrator._validate_implementation` retries once by rematerializing the known-good template and re-validating (see `orchestrator.py`), which is the project's concrete answer to the assignment's "demonstrate error handling and recovery" requirement. This is validation of the *output artifact*, not the code that produced it — a meaningfully different check than layers 1 and 2.

### 4. Static quality and security gates

`ruff` (lint/style/correctness signals — unused imports, import order, upgrade hints), `bandit` (SAST — flags things like unvetted `subprocess` use; see the documented `# nosec` justifications in `verifier.py` for the one place this fired and why it's safe), `pip-audit` (known CVEs in dependencies). These aren't behavioral tests — they catch a different failure class (a change that "works" in the happy path but introduces a vulnerability or a maintainability smell).

### 5. CI/CD enforcement

`.github/workflows/ci.yml` runs layers 1, 2, and 4 on every push/PR, then does one more thing none of the above do on their own: a full end-to-end CLI smoke test (`agentic_system.cli --clean --requirement ... --approve`), which is the closest thing to a system test this project has — it exercises the *entire* task graph, including materialization and validation, in one process. `cd.yml` repeats that smoke test after merge and uploads the result as a build artifact, so a reviewer can download exactly what a given commit produces without re-running anything locally.

## Run it all locally (mirrors CI exactly)

```powershell
python -m pip install -e ".[dev]"
ruff check .
bandit -q -r agentic_system url_shortener
pip-audit
python -m unittest discover -s tests -v
python -m agentic_system.cli --clean --requirement "Build a scalable URL shortener service with APIs, persistence, and analytics." --approve
```

## Known limitations and trade-offs

Being explicit about these rather than letting a reviewer find them first:

- **Deterministic logic means exact-match tests, which won't survive an LLM swap as-is.** `agentic_system.agents` is rule-based by design (see [Design boundaries and what's next](../README.md#design-boundaries-and-whats-next)), so tests assert precise field values. If `normalize_requirement`/`analyze_codebase` are later swapped for LLM-backed implementations, this test layer would need to become rubric- or tolerance-based (e.g. "risk_level is within a plausible band" rather than "risk_level == 0.21"), since LLM output isn't exactly reproducible run to run.
- **Brownfield scan accuracy is untested against a ground truth.** `analyze_codebase` is heuristic keyword scoring; the one test that exercises it (`test_brownfield_run_reports_candidate_files`) confirms it finds one obviously-relevant file in a tiny hand-built repo. There's no precision/recall measurement against a labeled corpus, so "how good is the impact scan, really" is not currently a testable claim.
- **Generated CI/CD YAML is validated structurally, not by execution.** `verify_generated_application` confirms `ci.yml`/`cd.yml` exist and contain a `jobs:` key — it does not run them through an Actions runner or a schema validator, so a subtly malformed workflow (bad step ordering, an invalid action reference) would not be caught automatically today. `actionlint` (or GitHub's own workflow schema) would close this gap.
- **No load or concurrency testing.** The API contract and architecture docs describe a scalable target design (Postgres, Redis, async analytics), but nothing in this repo load-tests SQLite's single-writer behavior under concurrent requests — the "scalable" claim is a design-level claim, not a measured one, and the docs say so (`docs/architecture.md`).
- **No coverage measurement.** Every module has tests, but coverage isn't quantified (no `coverage.py`/`pytest-cov` wired into CI), so "how much of the code every test run actually exercises" is a qualitative claim, not a reported number.
- **Quality gates run once, at the source.** `ruff`/`bandit` scan `agentic_system` and `url_shortener` (the source of truth); the *generated* copies under `generated/apps/url_shortener/` are byte-identical at materialization time but aren't independently re-scanned, since they're produced by, not edited around, the scanned source.

## Related docs

- [Example scenarios](scenarios/) — task decomposition, orchestration, and validation shown end to end for three real runs.
- [Operational runbook](runbook.md) — what happens after tests pass and the service is running.
- [Architecture](architecture.md) — where each of the above pieces sits in the system.

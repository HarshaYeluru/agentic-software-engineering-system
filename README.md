# Agentic Software Engineering System

## What this is

Give it one sentence describing a software requirement, and it works through the request the way a disciplined engineer would — not a chatbot that just talks about code, a system that actually decomposes, builds, and validates it.

```
"Build a scalable URL shortener service with APIs, persistence, and analytics."

1. Understand  — figures out what's being asked, and what's unclear about it
2. Plan        — an ordered checklist of the work, each step gated on the last
3. Design      — picks the architecture and explains why
4. Approve   — stops here. A human must say "go ahead" before anything is built
                 (anything that looks risky needs an even more deliberate approval)
5. Build       — writes the code, the tests, and the documentation
6. Verify      — runs it, tests it, and auto-repairs if something's broken
7. Summarize   — what shipped, the risks, and the trade-offs
```

Every one of those steps is written down as it happens — nothing happens silently, and anyone can see exactly what was decided and why.

To prove this is real and not just a pitch, the repo ships with something the system actually built: a working **URL shortener** (`url_shortener/`, like bit.ly) you can run and send real requests to. Three more real, captured examples of full runs — including one where the system correctly *stops and asks a human* instead of guessing — are written up in plain language in [docs/scenarios/](docs/scenarios/).

## Quick start

```powershell
git clone https://github.com/HarshaYeluru/agentic-software-engineering-system.git
Set-Location agentic-software-engineering-system

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

python -m unittest discover -s tests -v   # confirm the setup works: expect every test to pass

python -m agentic_system.cli --requirement "Build a scalable URL shortener service with APIs, persistence, and analytics." --approve
```

That last command *is* the system, end to end. It prints a status line and writes the full decision trail to `generated/run.json` — open it in any editor to see everything that was decided, in order, plus a runnable copy of the URL shortener at `generated/apps/url_shortener/`.

**Prerequisites:** Git 2.40+, Python 3.11+, PowerShell (all commands below are PowerShell). No database or API key needed. If your PowerShell execution policy blocks `Activate.ps1`, skip activation and prefix every command with `.\.venv\Scripts\python.exe -m` instead.

## Try the interesting behaviors

**Watch it pause instead of guess**, on a deliberately vague requirement:

```powershell
python -m agentic_system.cli --requirement "Make analytics better"
```

It still does real work — normalizes the request, checks the codebase, drafts a plan — then stops (`awaiting_approval`) instead of inventing an answer to a question it can't yet interpret. Write-up: [docs/scenarios/ambiguous.md](docs/scenarios/ambiguous.md).

**Watch its own deploy pipeline change shape with risk:**

```powershell
python -m agentic_system.cli --requirement "Build a scalable URL shortener service with APIs, persistence, and analytics." --approve
Get-Content generated\apps\url_shortener\.github\workflows\cd.yml

python -m agentic_system.cli --requirement "Delete all production data and migrate the URL shortener security model." --approve
Get-Content generated\apps\url_shortener\.github\workflows\cd.yml
```

The second, riskier requirement adds a dependency-security-audit step to CI and a manual-approval gate to the deploy pipeline. That pipeline is regenerated from the requirement on every run, not hand-maintained — see [GitHub Actions CI/CD](#github-actions-cicd) below.

**Point it at a real codebase:**

```powershell
python -m agentic_system.cli --requirement "Add expiry support to the existing URL shortener" --repository-path "C:\path\to\existing-repository" --approve
```

A bounded, read-only scan (at most 250 files) reports which files look relevant and how risky the change is. This alone never writes to the target repository — add `--apply-to-repository` (below) to actually change it. Write-up: [docs/scenarios/brownfield.md](docs/scenarios/brownfield.md).

**Let it actually write to a repository, safely:**

```powershell
python -m agentic_system.cli --requirement "Build a scalable URL shortener service with APIs, persistence, and analytics." --repository-path "C:\path\to\some-repo" --approve --apply-to-repository
```

Every run with `--repository-path` computes a diff preview and saves it to `generated/patches/latest.json`, whether or not you apply it. `--apply-to-repository` writes only that exact, previewed file set — nothing broader — and backs up anything it overwrites first, so it's always reversible with `agentic_system.patcher.rollback_patch`. Try it against an empty temp folder to see it materialize a real, independently-runnable copy of the service.

**Let it interpret the requirement with an LLM instead of keyword rules:**

```powershell
python -m pip install -e ".[llm]"
$env:ANTHROPIC_API_KEY = "sk-..."
python -m agentic_system.cli --requirement "Add expiry support to the existing URL shortener" --use-llm --approve
```

`--use-llm` routes requirement interpretation through Claude instead of the deterministic rules — but only the interpretive fields (intent, ambiguities, assumptions, clarification questions, risk level). Anything that gates real behavior (`approval_required`) is always recomputed by the same trusted rule, never taken from the model, and any failure (no key, network error, malformed response) falls back to the deterministic result automatically. See `agentic_system/prompted_agents.py` for the prompt and the validation logic.

**Use a browser instead of the command line:**

```powershell
python -m uvicorn agentic_system.review_app:app --reload --port 8001
```

Open [http://127.0.0.1:8001](http://127.0.0.1:8001) — run a requirement, inspect the full JSON trace, and approve (or not) before anything gets built.

## Run the generated URL-shortener service

```powershell
python -m uvicorn url_shortener.app:app --reload
```

Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) for interactive API docs, or exercise it directly:

```powershell
$link = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/v1/links" `
  -ContentType "application/json" -Body '{"url":"https://example.com/article"}'
$link
Invoke-RestMethod "http://127.0.0.1:8000/v1/links/$($link.code)/analytics"
```

Visit `$link.short_url` in a browser to record a click, then check analytics again. Local data lives in `data/url_shortener.sqlite3` (ignored by Git). If PowerShell can't find `uvicorn`, use `.\.venv\Scripts\python.exe -m uvicorn ...`.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Liveness — process is up |
| `GET` | `/ready` | Readiness — process **and** database are reachable |
| `GET` | `/metrics` | Prometheus metrics |
| `POST` | `/v1/links` | Create a short link |
| `GET` | `/{code}` | Redirect and record a click |
| `GET` | `/v1/links/{code}/analytics` | Total recorded clicks |

Every response carries an `X-Request-ID` header, and every request is logged as one JSON line — see [Observability](url_shortener/docs/architecture.md#observability) for what each signal is for and [url_shortener/docs/runbook.md](url_shortener/docs/runbook.md) for how they're used during an incident.

## What's inside

- **A controlled, dependency-aware workflow** with an explicit human-approval gate and risk-based escalation — the JSON trace in `generated/run.json` makes every decision inspectable.
- **Brownfield repository analysis** — a read-only impact scan against an existing codebase.
- **Real repository patching** — a bounded diff preview plus an explicit, backed-up, reversible apply step (`agentic_system.patcher`), gated separately from plan approval.
- **Optional LLM-backed requirement understanding** (`--use-llm`) — with every safety-critical field validated or recomputed, never trusted blindly from the model, and a deterministic fallback on any failure.
- **Persisted run history** under `generated/history/latest.json`, so runs stay reviewable and comparable.
- **A generated deploy pipeline** (GitHub Actions + a Dockerfile) for whatever it builds, regenerated every run from the requirement's risk level.
- **Its own CI/CD**, with lint (`ruff`), security scanning (`bandit`), and dependency auditing (`pip-audit`) on every push.
- **Observability** in the generated service: structured logs, correlation IDs, Prometheus metrics, separate liveness/readiness checks.

Each of those is covered in depth in its own doc rather than crammed in here. Docs live next to what they describe: agent docs in `docs/`, docs about the generated app in `url_shortener/docs/`.

| Doc | What's in it |
| --- | --- |
| [docs/architecture.md](docs/architecture.md) | The agent's control-flow diagram, separation of responsibilities, and write guardrails |
| [docs/scenarios/](docs/scenarios/) | Three real, captured runs: greenfield, brownfield, ambiguous |
| [docs/testing-approach.md](docs/testing-approach.md) | The five validation layers this project has, and their known limitations |
| [docs/hosting-the-agent.md](docs/hosting-the-agent.md) | Architecture for running the agent itself as a shared, hosted service |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Branching strategy and PR process |
| [url_shortener/docs/architecture.md](url_shortener/docs/architecture.md) | The generated app's deployment path, observability, and HA/failover design |
| [url_shortener/docs/runbook.md](url_shortener/docs/runbook.md) | On-call playbook and RCA template for the generated service |
| [url_shortener/docs/hosting.md](url_shortener/docs/hosting.md) | A practical, step-by-step guide to actually hosting the generated URL shortener |

## GitHub Actions CI/CD

Two separate pipelines exist, for two separate things:

- **The agent tool's own pipeline** (`.github/workflows/ci.yml`, `cd.yml`) — installs the package, lints with `ruff`, security-scans with `bandit`, audits dependencies with `pip-audit`, runs the full test suite, and smoke-tests the CLI end to end on every push and PR. `cd.yml` repeats that smoke test after a successful CI run and uploads the result as a build artifact.
- **CI/CD for the generated software** — a *separate* pipeline the workflow produces as one of its implementation artifacts (alongside the API contract and test cases), written to `generated/apps/url_shortener/.github/workflows/{ci,cd}.yml` plus a `Dockerfile`, every time it builds the URL shortener. It reacts to the requirement: a brownfield change adds a full regression pass, a high-risk change adds a dependency audit and a manual-approval gate before deploy (see [Try the interesting behaviors](#try-the-interesting-behaviors) above for a live comparison). The `cicd_pipeline` artifact in `generated/run.json` records why each step was included, and validation confirms the workflow files exist and are well-formed before a run is marked complete.

## Everyday commands

| What | Command |
| --- | --- |
| Run a requirement | `python -m agentic_system.cli --requirement "..." --approve` |
| Run without approving (see the gate) | `python -m agentic_system.cli --requirement "..."` |
| Scan an existing repo (preview only) | add `--repository-path "C:\path\to\repo"` |
| Actually write to that repo | add `--apply-to-repository` (requires `--approve` + `--repository-path`) |
| Use an LLM to interpret the requirement | add `--use-llm` (needs `ANTHROPIC_API_KEY`; falls back safely without it) |
| Reset local demo state | `python -m agentic_system.cli --clean` |
| Clean, then run fresh | add `--clean` to any run command |
| Run the test suite | `python -m unittest discover -s tests -v` |
| Lint / security-scan / audit (what CI runs) | `ruff check .` / `bandit -q -r agentic_system url_shortener` / `pip-audit` |

`--clean` removes `generated/run.json`, the materialized app under `generated/apps/url_shortener/`, and the local SQLite files — it never touches Git-tracked source, tests, or docs (the generated app folder is marked on creation, and cleanup refuses to remove an unmarked directory).

## Project layout

```text
agentic_system/       Workflow coordinator and deterministic agent functions
url_shortener/        FastAPI reference implementation and SQLite store
url_shortener/docs/   Docs about the generated app: architecture, hosting, runbook
tests/                Workflow and API tests
docs/                 Docs about the agent: architecture, testing approach, scenarios, hosting
.github/              CI/CD workflows, PR template, CODEOWNERS
CONTRIBUTING.md       Branching strategy and PR process
generated/            Local workflow output (ignored by Git)
data/                 Local SQLite database (ignored by Git)
```

## Design boundaries and what's next

SQLite keeps the local demo zero-setup. The production target is PostgreSQL for links, Redis for cache-aside redirects, and asynchronous analytics — see [HA and failover](url_shortener/docs/architecture.md#high-availability-and-failover) for how that maps to a multi-region deployment.

Known gaps, stated rather than hidden:

- **Repository patching only knows one implementation.** `agentic_system.patcher` genuinely writes to a real repository, with a diff preview, an explicit apply gate, and backup/rollback — but the content it writes is still the one reference URL-shortener implementation, not arbitrary generated code for an arbitrary requirement. It's real patching with a narrow, honest scope, not general code generation.
- **LLM-backed normalization is opt-in and narrow.** `--use-llm` (`agentic_system.prompted_agents`) improves intent/ambiguity interpretation specifically; it deliberately does not touch `functional_scope` or the rest of the pipeline (see the module docstring for why), and every safety-critical field is validated or recomputed rather than trusted from the model. The rest of `agentic_system.agents` remains deterministic by default, for reviewability.
- **No resume for interrupted runs** — runs are saved as snapshots, but there's no retry/resume lifecycle yet.
- **Brownfield analysis is heuristic** — keyword-scored, not a real dependency graph.
- **No richer risk-policy enforcement** — there's an approval gate, but no policy engine restricting destructive or high-impact autonomous actions beyond it.

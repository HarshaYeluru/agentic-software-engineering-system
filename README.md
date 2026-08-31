# Agentic Software Engineering System

This project is a small, runnable prototype for the interview assignment. It turns a requirement into a structured engineering outcome: a normalized problem statement, a dependency-aware plan, an architecture proposal, implementation artifacts, validation results, and a final summary.

It also includes a URL-shortener service that acts as the mandatory greenfield example. The workflow is deterministic for reviewability, but it now includes real interview-level features such as brownfield impact scoring, risk-aware approval gates, scenario outputs, sandbox patch preview metadata, and persisted run history. The orchestration boundary remains separate from the agent functions so an LLM or repository-inspection tool can be added later.

## What is included

- A controlled workflow with an explicit approval gate and risk-aware escalation.
- A JSON execution trace that makes task sequencing visible.
- Brownfield repository analysis with impact scoring and risk metadata.
- Persisted run snapshots under `generated/history/latest.json` for review and resume awareness.
- Scenario outputs for greenfield, brownfield, and ambiguous requirements.
- A sandbox patch preview model that records the intended file changes without writing to a real repository.
- A FastAPI URL-shortener service with SQLite storage, redirects, expiry handling, and click analytics.
- A generated deploy pipeline (GitHub Actions CI/CD workflows and a Dockerfile) for the generated application, recomputed on every run from the requirement's risk and classification. See [CI/CD for the generated software](#cicd-for-the-generated-software).
- Unit and API tests.
- A compact architecture note: [docs/architecture.md](docs/architecture.md).

## Prerequisites

- Git 2.40 or newer
- Python 3.11 or newer
- PowerShell on Windows (the commands below use PowerShell)

No database server or API key is required for the local demo.

## Get the project from scratch

### Option A: clone it from GitHub

After you create and push a remote repository, replace the placeholder URL with yours:

```powershell
git clone https://github.com/<your-github-username>/agentic-software-engineering-system.git
Set-Location agentic-software-engineering-system
```

## Set up Python

Create and activate a virtual environment, then install the project in editable mode:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

If your PowerShell policy prevents activation, use the virtual-environment interpreter directly in every command instead:

```powershell
.\.venv\Scripts\python.exe -m pip install -e .
```

## Verify the installation

Install the project and run the complete test suite:

```powershell
python -m pip install -e .
python -m unittest discover -s tests -v
```

Expected result: all tests pass.

## GitHub Actions CI/CD

This repository includes GitHub Actions workflows for continuous integration and release-style validation of the **agent tool itself**:

- `.github/workflows/ci.yml` runs on pushes and pull requests, installs the package, and executes the full unit test suite.
- `.github/workflows/cd.yml` runs after a successful CI pass (or via manual dispatch) to create a runtime smoke-test artifact from the generated workflow output.

The workflows are configured for Python 3.11 and target the same commands used in local validation so the GitHub pipeline matches the developer experience.

## CI/CD for the generated software

Separately from the workflows above, the engineering workflow also produces a deploy pipeline **for the software it generates**, as one of the implementation artifacts (alongside the API contract, implementation plan, and test cases). Every run writes:

- `generated/apps/url_shortener/.github/workflows/ci.yml` — installs the app and runs its test suite; on a brownfield change it adds a full regression pass, and on a high-risk change it adds a dependency security audit.
- `generated/apps/url_shortener/.github/workflows/cd.yml` — builds a Docker image and pushes it to a container registry; on a high-risk change it gates the job behind a `production` environment and a manual-approval step.
- `generated/apps/url_shortener/Dockerfile` — a runnable image for the generated app.

This pipeline definition is recomputed from the current requirement's risk level and greenfield/brownfield classification on every run, rather than hand-maintained, so it stays in sync with the software as it changes. The `cicd_pipeline` artifact in `generated/run.json` records the rationale for what was included; validation (`generated/run.json` → `validation.checks`) confirms the workflow files exist and are structurally valid before the run is marked complete.

To see it react to risk, compare two runs:

```powershell
python -m agentic_system.cli --requirement "Build a scalable URL shortener service with APIs, persistence, and analytics." --approve
Get-Content generated\apps\url_shortener\.github\workflows\cd.yml

python -m agentic_system.cli --requirement "Delete all production data and migrate the URL shortener security model." --approve
Get-Content generated\apps\url_shortener\.github\workflows\cd.yml
```

The second run adds a dependency audit step to CI and a manual-approval gate to CD; a subsequent low-risk run removes them again.

## Run the engineering workflow

The `--approve` flag represents a human approving the plan and recorded assumptions before implementation artifacts are produced.

To reset the local demo before an evaluation, run this optional cleanup command. It removes `generated/run.json`, the workflow-materialized application in `generated/apps/url_shortener/`, and the local URL-shortener SQLite files (including SQLite journal files). The generated application folder is marked when it is created, so cleanup refuses to remove an unmarked directory. It never deletes Git-tracked source code, tests, or documentation.

```powershell
python -m agentic_system.cli --clean
```

To clean and immediately create a fresh workflow result, add `--clean` to the run command below.

```powershell
python -m agentic_system.cli `
  --clean `
  --requirement "Build a scalable URL shortener service with APIs, persistence, and analytics." `
  --approve
```

The workflow writes `generated/run.json` and materializes a runnable URL-shortener artifact at `generated/apps/url_shortener/`. It also persists a latest snapshot in `generated/history/latest.json` so each run remains reviewable and easy to compare. The JSON includes task graph state, generated artifacts, validation checks, assumptions, risk metadata, and scenario outputs.

To run the generated application specifically, use:

```powershell
python -m uvicorn url_shortener.app:app --app-dir generated/apps --reload
```

To see the approval gate in action, omit `--approve`:

```powershell
python -m agentic_system.cli --requirement "Make analytics better"
```

High-risk requests automatically trigger a stronger approval requirement. The workflow records the normalized requirement risk level and keeps the approval boundary explicit.

### Brownfield analysis

Point the workflow at an existing repository to include a bounded, read-only impact scan in the engineering summary. The result includes impact scoring, candidate files, and a risk level for the requested change:

```powershell
python -m agentic_system.cli `
  --requirement "Add expiry support to the existing URL shortener" `
  --repository-path "C:\path\to\existing-repository" `
  --approve
```

The scan ignores common dependency/build directories, inspects at most 250 source files, reports heuristic candidate files, and now scores the likely impact for the requested change. It does not write to the target repository.

### Scenario outputs

The workflow now includes explicit scenario examples for common review cases:

- greenfield: a fresh service build
- brownfield: an enhancement to an existing system
- ambiguous: a vague requirement that pauses for human approval

These are included in the run artifact payload and can be inspected alongside the workflow trace.

### Local review UI

Start the reviewer interface:

```powershell
python -m uvicorn agentic_system.review_app:app --reload --port 8001
```

Open [http://127.0.0.1:8001](http://127.0.0.1:8001). The UI lets an interviewer run a requirement, inspect the full JSON trace, and choose whether to approve the plan before generated artifacts are materialized.

## Run the URL-shortener API

Start the API from the repository root:

```powershell
python -m uvicorn url_shortener.app:app --reload
```

If PowerShell cannot find `uvicorn`, use:

```powershell
.\.venv\Scripts\python.exe -m uvicorn url_shortener.app:app --reload
```

Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) for interactive Swagger documentation.

### Quick API check

In a second PowerShell window:

```powershell
$link = Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/v1/links" `
  -ContentType "application/json" `
  -Body '{"url":"https://example.com/article"}'

$link
Invoke-RestMethod "http://127.0.0.1:8000/v1/links/$($link.code)/analytics"
```

Visit `$link.short_url` in a browser to record a redirect event, then run the analytics command again. Local data is stored in `data/url_shortener.sqlite3`; it is ignored by Git.

## API endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Simple service health check |
| `POST` | `/v1/links` | Create a short link |
| `GET` | `/{code}` | Redirect and record a click |
| `GET` | `/v1/links/{code}/analytics` | Return total recorded clicks |

## Project layout

```text
agentic_system/       Workflow coordinator and deterministic agent functions
url_shortener/        FastAPI reference implementation and SQLite store
tests/                Workflow and API tests
docs/                 Architecture and design notes
generated/            Local workflow output (ignored by Git)
data/                 Local SQLite database (ignored by Git)
```

## Design boundaries and next steps

SQLite is used only to keep the example zero-setup. For production, the architecture proposes PostgreSQL for links, Redis for cache-aside redirects, and asynchronous analytics processing. The next assignment milestones are brownfield repository analysis, an LLM-backed agent implementation, and three polished scenario reports (greenfield, brownfield, and ambiguous).

## Create the first commit and push to GitHub

If this folder is not yet committed, run:

```powershell
git add .
git commit -m "Initial agentic engineering prototype"
```

Create an empty repository on GitHub, then connect and push it:

```powershell
git remote add origin https://github.com/<your-github-username>/agentic-software-engineering-system.git
git push -u origin main
```

Do not commit `.venv`, `generated`, `work`, or local SQLite files. The included `.gitignore` already handles these.

## Next steps

### Real repository patching
This system generates and validates artifacts, but it does not yet apply real code changes to an existing repository in a controlled patch workflow.

### Persistent run history and resume
Runs are saved as snapshots, but the project does not yet provide a full lifecycle of historical runs, retries, or resume flows for interrupted work.

### Stronger brownfield analysis
The repository scan is useful for a demo, but it is still heuristic-based and could be improved with deeper dependency and impact analysis.

### Polished scenario outputs
The project includes scenario examples, but the greenfield, brownfield, and ambiguous examples are not yet formalized as separate polished deliverables.

### Risk-policy enforcement
The system has an approval gate, but it still needs richer risk policies to restrict destructive or high-impact autonomous actions.

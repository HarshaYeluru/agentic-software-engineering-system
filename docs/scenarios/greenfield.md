# Scenario: greenfield

**Requirement:** "Build a scalable URL shortener service with APIs, persistence, and analytics." (the assignment's mandatory use case)

```powershell
python -m agentic_system.cli --clean --requirement "Build a scalable URL shortener service with APIs, persistence, and analytics." --approve
```

## Task decomposition

`normalize_requirement` classifies this as `greenfield` (no existing-repository signal, but the URL-shortener functional scope is recognized), with `risk_level = 0.15` — nothing in the high-risk keyword list (`delete`, `production`, `migrate`, ...) appears, so no escalation.

## Multi-step orchestration

The full trace, in the order tasks actually became ready and ran:

```
normalize -> codebase_analysis -> plan -> architecture -> approval -> implementation -> validation -> summary
```

`codebase_analysis` and `plan` both depend only on `normalize`, so the orchestrator considers them part of the same "ready set" — `codebase_analysis` reports `mode: not_requested` here because no `--repository-path` was given, which is itself a meaningful, recorded outcome rather than a skipped step. `architecture` then gates on *both* of them completing before it runs. Because `--approve` was passed, the approval task completes immediately instead of blocking.

`implementation` produces the full artifact set and, because an output directory was given, materializes two things to disk: the runnable application at `generated/apps/url_shortener/`, and — as its own artifact — a deploy pipeline at `generated/apps/url_shortener/.github/workflows/{ci,cd}.yml` sized for this requirement's risk (`risk_level=0.15`, `classification=greenfield`): no dependency audit, no manual-approval gate, just install → lint/security-scan → API tests, and a straight build-and-push CD.

## Output validation

`validation` ran three independent checks against the materialized app: `compile` (bytecode-compiles cleanly), `tests` (the copied `test_url_shortener.py` passes against the copied app), and `cicd_workflows` (the generated `ci.yml`/`cd.yml` exist and contain a `jobs:` section). All three passed, so no repair cycle was triggered — `validation.repair.attempted` is `false`.

## Generated artifacts

- `api_contract` — request/response shapes for `POST /v1/links`, `GET /{code}`, `GET /v1/links/{code}/analytics`.
- `implementation_plan` — 4 ordered steps (schema, validation/codegen, cache-aside redirect, async analytics).
- `test_cases` — 4 named cases covering validation, collision retry, 404, and analytics publication.
- `documentation` — a one-paragraph API note.
- `cicd_pipeline` — the deploy pipeline spec described above, plus its rationale string.
- `sandbox_patch_preview` — the file list a real patch would touch, including the two workflow files.

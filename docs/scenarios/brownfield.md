# Scenario: brownfield

**Requirement:** "Add expiry support to the existing URL shortener", scanned against `url_shortener/` as a stand-in for an existing repository.

```powershell
python -m agentic_system.cli --requirement "Add expiry support to the existing URL shortener" --repository-path url_shortener --approve
```

## Task decomposition

`normalize_requirement` sees `existing` (a brownfield signal word) and a repository path, so `classification = brownfield`. Brownfield changes always require human approval regardless of computed risk (`approval_required = risk_level >= 0.7 or is_brownfield`) — `--approve` supplies it here; without it the run stops at the gate exactly like the [ambiguous scenario](ambiguous.md).

## Codebase reasoning

`analyze_codebase` performs a bounded, read-only scan of the target repository: it inspected 3 files, scored them against requirement keywords plus the URL-shortener domain terms (`url`, `link`, `analytics`, `redirect`), and returned every file as a candidate:

```
impacted_files: ["app.py", "store.py", "__init__.py"]
impact_score:   0.3
risk_level:     0.21   (derived from impact_score, since no explicit high-risk keyword was present)
```

This is heuristic keyword scoring, not a dependency graph — the docs say so explicitly in the returned `notes`, and that's a known, stated limitation rather than a hidden one.

## Multi-step orchestration

Same graph shape as the greenfield run, but `codebase_analysis` now does real work instead of reporting `not_requested`, and its `risk_level` output feeds into `architecture`'s inputs alongside `normalize`'s. The run reached `completed`.

## Output validation

Same three checks as greenfield (`compile`, `tests`, `cicd_workflows`), all passing. The generated CI pipeline reacts to the brownfield classification: it adds a `run_full_regression` step (the full test suite, not just `test_url_shortener.py`) on top of the baseline install/lint/test steps — a brownfield change gets a stricter CI gate than a greenfield one, by design, not by hand-editing the workflow file.

## What this demonstrates

- Read-only repository inspection with an explicit file cap (250 files) and ignored-directory list, so it can't accidentally scan `.git`, `node_modules`, or its own `generated/` output.
- A risk score that blends the normalized requirement's own risk with the scan's impact score, rather than only using one signal.
- A CI/CD pipeline that changes shape based on *why* the run is brownfield, not just that it is.

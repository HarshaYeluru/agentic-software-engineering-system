# Scenario: ambiguous

**Requirement:** "Make analytics better" — no `--approve`, no repository path.

```powershell
python -m agentic_system.cli --requirement "Make analytics better"
```

## Task decomposition

`normalize_requirement` flags `better` as an ambiguous term (it's in the fixed ambiguous-word list: `better`, `improve`, `faster`, `more secure`) and finds no URL-shortener signal and no brownfield signal, so `functional_scope = ["Clarify and implement the requested change"]` and `classification = ambiguous`. Because the scope is unresolved, `risk_level` is floored at `0.25` even though no high-risk keyword matched — an unscoped, un-brownfield requirement is treated as inherently riskier than a well-understood one, not safer.

## Multi-step orchestration — and where it stops

The trace shows exactly where control returns to a human:

```
normalize -> codebase_analysis -> plan -> architecture -> approval: blocked
```

`normalize`, `codebase_analysis` (`mode: not_requested`, no path given), `plan`, and `architecture` all still run — `architecture` returns `{"decision": "Architecture deferred until ambiguity is resolved."}` rather than a real proposal, because `design_architecture` checks the resolved functional scope before committing to a design. The `approval` task is the one gated task in the graph (`requires_approval=True`); since `self.approved` is `False`, the orchestrator marks it `BLOCKED`, records `"blocked: human approval required"` in the trace, saves the run snapshot, and returns `status: awaiting_approval` — `implementation`, `validation`, and `summary` never execute. Nothing is materialized to disk.

## Why this is the interesting case

This is the "controlled autonomy" requirement in miniature: the system does real, independent work (four tasks execute) but refuses to manufacture a confident answer to a request it can't yet interpret unambiguously. `clarification_questions` comes back empty here (it's only populated for recognized URL-shortener or brownfield requests) — which is itself informative: the normalizer knows *that* it's unsure, and records the ambiguous term that caused it, even when it can't yet propose good clarifying questions for a scope it hasn't identified. Re-running the same requirement with `--approve` would *not* fix this — approval only unblocks a gate that already knows what it's approving; it doesn't resolve `functional_scope`. The real fix is a clearer requirement (e.g. "Reduce analytics query latency for the click-count endpoint"), which is the point.

from __future__ import annotations

from pathlib import Path
from typing import Any


URL_SHORTENER_SCOPE = ["Create short links", "Resolve a short link", "Record click analytics"]
REQUIRED_ARTIFACTS = {"api_contract", "implementation_plan", "test_cases", "documentation", "cicd_pipeline"}


def normalize_requirement(requirement: str, repository_path: Path | None = None) -> dict[str, Any]:
    """Turn raw request text into a compact brief the next stages can consume."""
    text = requirement.lower()
    ambiguous_terms = [term for term in ("better", "improve", "faster", "more secure") if term in text]
    is_url_shortener = "url shortener" in text or ("shorten" in text and "url" in text)
    brownfield_words = ("existing", "add", "fix", "refactor", "change", "update")
    is_brownfield = repository_path is not None or any(word in text for word in brownfield_words)
    assumptions: list[str] = []
    risk_flags: list[str] = []
    risk_weight = 0.15

    high_risk_patterns = {
        "delete": 0.18,
        "rewrite": 0.2,
        "production": 0.15,
        "database": 0.15,
        "all": 0.1,
        "disable": 0.18,
        "migrate": 0.15,
        "critical": 0.15,
        "security": 0.15,
    }
    for pattern, weight in high_risk_patterns.items():
        if pattern in text:
            risk_flags.append(pattern)
            risk_weight += weight

    if is_url_shortener:
        assumptions = [
            "Public API uses HTTPS and JSON.",
            "Short codes are unique, URL-safe, and at least seven characters.",
            "Redirect analytics are eventually consistent.",
        ]
        ambiguous_terms.extend(
            [
                "Expected traffic, latency, and availability targets are not specified.",
                "Analytics retention and privacy requirements are not specified.",
            ]
        )

    risk_level = min(1.0, round(risk_weight, 2))
    if not is_url_shortener and not is_brownfield:
        risk_level = max(risk_level, 0.25)

    return {
        "intent": "Deliver a maintainable engineering change with validated artifacts.",
        "functional_scope": URL_SHORTENER_SCOPE if is_url_shortener else ["Clarify and implement the requested change"],
        "ambiguities": ambiguous_terms,
        "assumptions": assumptions,
        "classification": "brownfield" if is_brownfield else ("greenfield" if is_url_shortener else "ambiguous"),
        "clarification_questions": _clarification_questions(is_url_shortener, is_brownfield),
        "requirement_terms": [word for word in text.replace(".", " ").split() if len(word) > 3],
        "risk_level": risk_level,
        "risk_flags": risk_flags,
        "approval_required": risk_level >= 0.7 or is_brownfield,
    }


def _clarification_questions(is_url_shortener: bool, is_brownfield: bool) -> list[str]:
    questions: list[str] = []
    if is_url_shortener:
        questions.extend(
            [
                "What peak redirect volume and latency target should the service support?",
                "What analytics retention period and privacy policy apply?",
            ]
        )
    if is_brownfield:
        questions.append("Which repository branch and compatibility constraints should this change preserve?")
    return questions


def analyze_codebase(repository_path: Path | None, normalized: dict[str, Any]) -> dict[str, Any]:
    """Perform a bounded, read-only first pass over a brownfield repository."""
    if repository_path is None:
        return {
            "mode": "not_requested",
            "impacted_files": [],
            "impact_score": 0.0,
            "risk_level": float(normalized.get("risk_level", 0.0)),
            "notes": ["No repository path was supplied."],
        }
    if not repository_path.is_dir():
        raise ValueError(f"Repository path does not exist or is not a directory: {repository_path}")

    ignored_directories = {".git", ".venv", "node_modules", "generated", "work", "__pycache__"}
    source_extensions = {".py", ".ts", ".tsx", ".js", ".java", ".go", ".sql", ".md", ".yaml", ".yml"}
    keywords = set(normalized["requirement_terms"])
    keywords.update({"url", "link", "analytics", "redirect"} if normalized["functional_scope"] == URL_SHORTENER_SCOPE else set())
    candidates: list[tuple[int, str]] = []
    inspected = 0

    for file_path in repository_path.rglob("*"):
        if inspected >= 250:
            break
        if any(part in ignored_directories for part in file_path.parts) or not file_path.is_file():
            continue
        if file_path.suffix.lower() not in source_extensions or file_path.stat().st_size > 250_000:
            continue
        inspected += 1
        relative_path = file_path.relative_to(repository_path)
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore").lower()
        except OSError:
            continue
        haystack = f"{relative_path.as_posix().lower()} {content}"
        score = sum(haystack.count(keyword) for keyword in keywords)
        if score:
            candidates.append((score, relative_path.as_posix()))

    candidates.sort(key=lambda item: (-item[0], item[1]))
    impacted_files = [path for _, path in candidates[:10]]
    impact_score = min(1.0, max(0.1, len(impacted_files) / 10.0) + (0.2 if normalized.get("risk_level", 0.0) >= 0.5 else 0.0))
    risk_level = round(min(1.0, max(float(normalized.get("risk_level", 0.0)), impact_score * 0.7)), 2)
    return {
        "mode": "read_only_repository_scan",
        "repository": str(repository_path),
        "files_inspected": inspected,
        "impacted_files": impacted_files,
        "impact_score": round(impact_score, 2),
        "risk_level": risk_level,
        "notes": [
            "Candidates are heuristic matches, not a substitute for dependency-graph analysis.",
            "The scan is capped at 250 source files and does not write to the repository.",
        ],
    }


def build_task_plan() -> dict[str, Any]:
    """Expose the workflow plan as an artifact instead of burying it in control flow."""
    return {
        "ordered_tasks": [
            "normalize",
            "codebase_analysis",
            "plan",
            "architecture",
            "approval",
            "implementation",
            "validation",
            "summary",
        ],
        "approval_reason": "A human reviews assumptions and design before implementation work is accepted.",
    }


def design_architecture(normalized: dict[str, Any]) -> dict[str, Any]:
    if normalized["functional_scope"] != URL_SHORTENER_SCOPE:
        return {"decision": "Architecture deferred until ambiguity is resolved."}
    return {
        "components": [
            "FastAPI REST service", "PostgreSQL link store", "Redis cache", "asynchronous analytics worker",
        ],
        "prototype_note": "The local reference service uses SQLite in place of PostgreSQL and Redis to keep setup simple.",
        "data_flow": "create -> validate URL -> persist mapping -> cache; redirect -> cache/store lookup -> 302 -> enqueue click event",
        "tradeoffs": [
            "Analytics are asynchronous to protect redirect latency, so dashboard counts are eventually consistent.",
            "Random identifiers avoid counter hot spots but require collision retry handling.",
        ],
    }


def generate_engineering_artifacts(normalized: dict[str, Any]) -> dict[str, Any]:
    if normalized["functional_scope"] != URL_SHORTENER_SCOPE:
        return {"note": "Implementation withheld pending clarified scope."}
    return {
        "api_contract": {
            "POST /v1/links": {"request": {"url": "https://example.com"}, "response": {"code": "aB3kLm9", "short_url": "https://sho.rt/aB3kLm9"}},
            "GET /{code}": {"response": "302 redirect"},
            "GET /v1/links/{code}/analytics": {"response": {"clicks": 42, "period": "all_time"}},
        },
        "implementation_plan": [
            "Create links table with a unique code index and expiry field.",
            "Implement URL validation, code generation, and collision retry.",
            "Implement redirect lookup with cache-aside behavior.",
            "Publish redirect events to an analytics worker.",
        ],
        "test_cases": [
            "Reject malformed and disallowed URLs.",
            "Retry after a generated-code collision.",
            "Return 404 for an unknown or expired code.",
            "Verify redirect response and analytics event publication.",
        ],
        "documentation": "API uses 201 for link creation and 302 for redirects. Analytics are eventually consistent.",
        "cicd_pipeline": generate_cicd_pipeline(normalized),
    }


def generate_cicd_pipeline(normalized: dict[str, Any]) -> dict[str, Any]:
    """Propose a deploy pipeline for the generated application.

    Recomputed from the current requirement on every run (classification, risk,
    scope) instead of being hand-maintained, so the pipeline definition tracks
    whatever the software looks like after this prompt rather than drifting
    from it over successive requirements.
    """
    if normalized["functional_scope"] != URL_SHORTENER_SCOPE:
        return {"note": "CI/CD pipeline withheld pending clarified scope."}

    is_brownfield = normalized.get("classification") == "brownfield"
    is_high_risk = normalized.get("risk_level", 0.0) >= 0.5

    ci_steps = ["install_dependencies", "run_api_tests"]
    if is_brownfield:
        ci_steps.append("run_full_regression")
    if is_high_risk:
        ci_steps.append("run_dependency_audit")

    cd_steps = ["build_image", "push_image"]
    if is_high_risk:
        cd_steps.insert(0, "require_manual_approval")

    return {
        "ci_pipeline": {
            "name": "URL Shortener CI",
            "trigger_paths": ["url_shortener/**", "tests/test_url_shortener.py"],
            "steps": ci_steps,
        },
        "cd_pipeline": {
            "name": "URL Shortener CD",
            "steps": cd_steps,
            "deploy_target": "container_registry (ghcr.io)",
        },
        "rationale": (
            f"classification={normalized.get('classification')}, "
            f"risk_level={normalized.get('risk_level', 0.0)}; "
            "regenerated for this requirement rather than hand-maintained."
        ),
    }


def generate_scenarios() -> dict[str, dict[str, Any]]:
    """Provide explicit example inputs and expected outputs for common review scenarios."""
    return {
        "greenfield": {
            "example": "Build a scalable URL shortener service with APIs, persistence, and analytics.",
            "expected_outcome": "Implementation plan, API contract, test cases, and validation path for a new service.",
        },
        "brownfield": {
            "example": "Add analytics and expiry support to the existing URL shortener.",
            "expected_outcome": "Read-only repository scan, change impact notes, and compatibility-aware plan.",
        },
        "ambiguous": {
            "example": "Make analytics better.",
            "expected_outcome": "Requirements are normalized, assumptions are surfaced, and the workflow pauses for approval.",
        },
    }


def validate_artifacts(artifacts: dict[str, Any]) -> dict[str, Any]:
    """Keep validation independent from artifact generation."""
    missing = sorted(REQUIRED_ARTIFACTS - artifacts.keys())
    return {
        "passed": not missing,
        "checks": ["API contract present", "test plan present", "trade-offs documented"],
        "findings": [f"Missing required artifact: {name}" for name in missing],
        "risk_controls": ["Do not execute repository writes without approval", "Validate generated API/test artifacts before handoff"],
    }

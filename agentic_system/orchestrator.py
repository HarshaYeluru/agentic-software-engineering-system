from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from . import agents, prompted_agents
from .materializer import materialize_cicd_workflows, materialize_url_shortener
from .models import EngineeringTask, RunResult, TaskState
from .observability import AGENT_RUN_DURATION, AGENT_RUNS_TOTAL, AGENT_TASK_DURATION, log_event
from .verifier import verify_generated_application


def _finish_run(status: str, requirement: str, started_at: float) -> None:
    duration_seconds = time.perf_counter() - started_at
    AGENT_RUNS_TOTAL.labels(status=status).inc()
    AGENT_RUN_DURATION.observe(duration_seconds)
    log_event(
        "run_finished",
        status=status,
        duration_ms=round(duration_seconds * 1000, 2),
        requirement=requirement[:120],
    )


def _build_sandbox_patch_preview(normalized_requirement: dict[str, Any]) -> dict[str, Any]:
    """Capture the patching intent without writing to a real repository."""
    return {
        "mode": "preview",
        "allowed": True,
        "files": [
            "url_shortener/__init__.py",
            "url_shortener/app.py",
            "url_shortener/store.py",
            "tests/test_url_shortener.py",
            ".github/workflows/ci.yml",
            ".github/workflows/cd.yml",
            "Dockerfile",
        ],
        "summary": f"Planned change for: {normalized_requirement.get('intent', 'engineering change')}",
    }


class WorkflowOrchestrator:
    """Run dependency-aware work and keep the human approval boundary explicit."""

    def __init__(self, approved: bool = False, use_llm: bool = False) -> None:
        self.approved = approved
        self.use_llm = use_llm

    def run(
        self,
        requirement: str,
        output_directory: Path | None = None,
        repository_path: Path | None = None,
    ) -> RunResult:
        run_started_at = time.perf_counter()
        tasks = {
            "normalize": EngineeringTask("normalize", "Understand and normalize requirement"),
            "codebase_analysis": EngineeringTask("codebase_analysis", "Analyze repository impact", ["normalize"]),
            "plan": EngineeringTask("plan", "Create dependency-aware engineering plan", ["normalize"]),
            "architecture": EngineeringTask("architecture", "Design architecture", ["normalize", "plan", "codebase_analysis"]),
            "approval": EngineeringTask("approval", "Human approval of assumptions and plan", ["architecture"], True),
            "implementation": EngineeringTask("implementation", "Generate engineering artifacts", ["approval"]),
            "validation": EngineeringTask("validation", "Validate generated artifacts", ["implementation"]),
            "summary": EngineeringTask("summary", "Prepare engineering summary", ["validation"]),
        }
        artifacts: dict[str, Any] = {}
        trace: list[dict[str, str]] = []
        normalize_fn = prompted_agents.normalize_requirement if self.use_llm else agents.normalize_requirement
        handlers: dict[str, Callable[[], dict[str, Any]]] = {
            "normalize": lambda: normalize_fn(requirement, repository_path),
            "codebase_analysis": lambda: agents.analyze_codebase(repository_path, artifacts["normalized_requirement"]),
            "plan": agents.build_task_plan,
            "architecture": lambda: agents.design_architecture(artifacts["normalized_requirement"]),
            "implementation": lambda: self._generate_implementation_artifacts(
                artifacts["normalized_requirement"], output_directory
            ),
            "validation": lambda: self._validate_implementation(artifacts, output_directory),
            "summary": lambda: self._summary(artifacts),
        }
        artifact_names = {
            "normalize": "normalized_requirement",
            "codebase_analysis": "codebase_analysis",
            "plan": "execution_plan",
            "architecture": "architecture",
            "implementation": "engineering_artifacts",
            "validation": "validation",
            "summary": "engineering_summary",
        }

        while True:
            ready = [
                task
                for task in tasks.values()
                if task.state is TaskState.PENDING
                and all(tasks[dependency].state is TaskState.COMPLETED for dependency in task.depends_on)
            ]
            if not ready:
                break
            for task in ready:
                if task.requires_approval and not self.approved:
                    normalized = artifacts.get("normalized_requirement", {"approval_required": False, "risk_level": 0.0})
                    if normalized.get("approval_required"):
                        task.state = TaskState.BLOCKED
                        trace.append({"task": task.id, "event": "blocked: human approval required for high-risk change"})
                    else:
                        task.state = TaskState.BLOCKED
                        trace.append({"task": task.id, "event": "blocked: human approval required"})
                    _finish_run("awaiting_approval", requirement, run_started_at)
                    if output_directory is not None:
                        result = RunResult(requirement, tasks, artifacts, trace, "awaiting_approval")
                        result.save_history(output_directory)
                        return result
                    return RunResult(requirement, tasks, artifacts, trace, "awaiting_approval")
                if not self._execute_task(task, handlers, artifacts, artifact_names, trace):
                    _finish_run("failed", requirement, run_started_at)
                    result = RunResult(requirement, tasks, artifacts, trace, "failed")
                    if output_directory is not None:
                        result.save_history(output_directory)
                    return result

        status = "completed" if tasks["summary"].state is TaskState.COMPLETED else "failed"
        _finish_run(status, requirement, run_started_at)
        result = RunResult(requirement, tasks, artifacts, trace, status)
        if output_directory is not None:
            result.save_history(output_directory)
            artifacts["scenarios"] = agents.generate_scenarios()
            result.artifacts = artifacts
            result.save_history(output_directory)
        return result

    @staticmethod
    def _generate_implementation_artifacts(
        normalized_requirement: dict[str, Any], output_directory: Path | None
    ) -> dict[str, Any]:
        artifacts = agents.generate_engineering_artifacts(normalized_requirement)
        artifacts["sandbox_patch_preview"] = _build_sandbox_patch_preview(normalized_requirement)
        if output_directory is not None and "api_contract" in artifacts:
            artifacts["generated_application"] = materialize_url_shortener(output_directory)
            artifacts["generated_cicd_pipeline"] = materialize_cicd_workflows(
                output_directory, artifacts["cicd_pipeline"]
            )
        return artifacts

    @staticmethod
    def _validate_implementation(artifacts: dict[str, Any], output_directory: Path | None) -> dict[str, Any]:
        validation = agents.validate_artifacts(artifacts["engineering_artifacts"])
        if output_directory is None or "generated_application" not in artifacts["engineering_artifacts"]:
            return validation

        application_validation = verify_generated_application(output_directory)
        repair: dict[str, Any] = {"attempted": False}
        if not application_validation["passed"]:
            # A deterministic prototype can retry by rematerializing its known-good template.
            repair = {"attempted": True, "action": "rematerialized reference application and cicd pipeline"}
            artifacts["engineering_artifacts"]["generated_application"] = materialize_url_shortener(output_directory)
            artifacts["engineering_artifacts"]["generated_cicd_pipeline"] = materialize_cicd_workflows(
                output_directory, artifacts["engineering_artifacts"]["cicd_pipeline"]
            )
            application_validation = verify_generated_application(output_directory)
            repair["passed_after_retry"] = application_validation["passed"]

        validation["application_verification"] = application_validation
        validation["repair"] = repair
        if not application_validation["passed"]:
            validation["passed"] = False
            validation["findings"].extend(application_validation["findings"])
        return validation

    @staticmethod
    def _execute_task(
        task: EngineeringTask,
        handlers: dict[str, Callable[[], dict[str, Any]]],
        artifacts: dict[str, Any],
        artifact_names: dict[str, str],
        trace: list[dict[str, str]],
    ) -> bool:
        """Run one task and record failures as reviewable workflow output."""
        task.state = TaskState.RUNNING
        trace.append({"task": task.id, "event": "started"})
        started_at = time.perf_counter()
        try:
            if task.requires_approval:
                task.result = {
                    "approved": True,
                    "approved_assumptions": artifacts["normalized_requirement"]["assumptions"],
                    "clarification_questions": artifacts["normalized_requirement"]["clarification_questions"],
                }
            else:
                task.result = handlers[task.id]()
                artifacts[artifact_names[task.id]] = task.result
        except (KeyError, ValueError) as error:
            duration_seconds = time.perf_counter() - started_at
            AGENT_TASK_DURATION.labels(task=task.id).observe(duration_seconds)
            task.state = TaskState.FAILED
            task.result = {"error": str(error)}
            trace.append({"task": task.id, "event": f"failed: {error}"})
            log_event("task_finished", task=task.id, status="failed", duration_ms=round(duration_seconds * 1000, 2))
            return False

        duration_seconds = time.perf_counter() - started_at
        AGENT_TASK_DURATION.labels(task=task.id).observe(duration_seconds)
        task.state = TaskState.COMPLETED
        trace.append({"task": task.id, "event": "completed"})
        log_event("task_finished", task=task.id, status="completed", duration_ms=round(duration_seconds * 1000, 2))
        return True

    @staticmethod
    def _summary(artifacts: dict[str, Any]) -> dict[str, Any]:
        validation = artifacts["validation"]
        dependence_summary = {
            "rationale": "Tasks were dependency-gated and independently validated before handoff.",
            "artifacts": list(artifacts["engineering_artifacts"].keys()),
            "validation_passed": validation["passed"],
            "risks_and_controls": validation["risk_controls"],
            "assumptions": artifacts["normalized_requirement"]["assumptions"],
            "risk_level": artifacts["normalized_requirement"].get("risk_level", 0.0),
            "approval_required": artifacts["normalized_requirement"].get("approval_required", False),
            "sandbox_patch_preview": artifacts["engineering_artifacts"].get("sandbox_patch_preview"),
            "scenarios": agents.generate_scenarios(),
        }
        return dependence_summary

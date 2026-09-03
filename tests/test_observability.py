import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agentic_system import observability, patcher
from agentic_system.orchestrator import WorkflowOrchestrator
from agentic_system.prompted_agents import normalize_requirement as llm_normalize
from agentic_system.review_app import create_review_app


def _counter_value(counter, **labels) -> float:
    child = counter.labels(**labels) if labels else counter
    return child._value.get()


def _histogram_count(histogram, **labels) -> float:
    for metric in histogram.collect():
        for sample in metric.samples:
            if sample.name.endswith("_count") and sample.labels == labels:
                return sample.value
    return 0.0


class OrchestratorObservabilityTests(unittest.TestCase):
    def test_run_increments_agent_runs_total_and_records_duration(self) -> None:
        before = _counter_value(observability.AGENT_RUNS_TOTAL, status="completed")
        before_count = _histogram_count(observability.AGENT_RUN_DURATION)

        WorkflowOrchestrator(approved=True).run(
            "Build a scalable URL shortener service with APIs, persistence, and analytics."
        )

        self.assertEqual(_counter_value(observability.AGENT_RUNS_TOTAL, status="completed"), before + 1)
        self.assertEqual(_histogram_count(observability.AGENT_RUN_DURATION), before_count + 1)

    def test_awaiting_approval_is_recorded_under_its_own_status(self) -> None:
        before = _counter_value(observability.AGENT_RUNS_TOTAL, status="awaiting_approval")

        WorkflowOrchestrator().run("Make analytics better")

        self.assertEqual(_counter_value(observability.AGENT_RUNS_TOTAL, status="awaiting_approval"), before + 1)

    def test_each_completed_task_records_a_duration_observation(self) -> None:
        before = _histogram_count(observability.AGENT_TASK_DURATION, task="normalize")

        WorkflowOrchestrator(approved=True).run(
            "Build a scalable URL shortener service with APIs, persistence, and analytics."
        )

        self.assertEqual(_histogram_count(observability.AGENT_TASK_DURATION, task="normalize"), before + 1)


class PromptedAgentsObservabilityTests(unittest.TestCase):
    REQUIREMENT = "Add expiry support to the existing URL shortener"

    def test_no_credentials_fallback_is_counted(self) -> None:
        before = _counter_value(observability.AGENT_LLM_FALLBACK_TOTAL, reason="no_credentials")

        with patch.dict("os.environ", {}, clear=True):
            llm_normalize(self.REQUIREMENT)

        self.assertEqual(_counter_value(observability.AGENT_LLM_FALLBACK_TOTAL, reason="no_credentials"), before + 1)

    def test_client_error_fallback_is_counted(self) -> None:
        class RaisingClient:
            def complete(self, prompt: str) -> str:
                raise RuntimeError("network is down")

        before = _counter_value(observability.AGENT_LLM_FALLBACK_TOTAL, reason="call_or_parse_error")

        llm_normalize(self.REQUIREMENT, client=RaisingClient())

        self.assertEqual(
            _counter_value(observability.AGENT_LLM_FALLBACK_TOTAL, reason="call_or_parse_error"), before + 1
        )


class PatcherObservabilityTests(unittest.TestCase):
    def test_apply_patch_records_applied_outcome(self) -> None:
        from agentic_system import agents

        normalized = agents.normalize_requirement(
            "Build a scalable URL shortener service with APIs, persistence, and analytics."
        )
        cicd_pipeline = agents.generate_cicd_pipeline(normalized)
        before = _counter_value(observability.AGENT_PATCH_APPLY_TOTAL, outcome="applied")

        with tempfile.TemporaryDirectory() as temporary_directory:
            plan = patcher.plan_patch(Path(temporary_directory), normalized, cicd_pipeline)
            patcher.apply_patch(plan)

        self.assertEqual(_counter_value(observability.AGENT_PATCH_APPLY_TOTAL, outcome="applied"), before + 1)

    def test_apply_patch_with_no_changes_records_that_outcome(self) -> None:
        before = _counter_value(observability.AGENT_PATCH_APPLY_TOTAL, outcome="no_changes")

        with tempfile.TemporaryDirectory() as temporary_directory:
            empty_plan = patcher.PatchPlan(Path(temporary_directory), [])
            patcher.apply_patch(empty_plan)

        self.assertEqual(_counter_value(observability.AGENT_PATCH_APPLY_TOTAL, outcome="no_changes"), before + 1)


class ReviewAppMetricsEndpointTests(unittest.TestCase):
    def test_metrics_endpoint_exposes_agent_metrics(self) -> None:
        from fastapi.testclient import TestClient

        with tempfile.TemporaryDirectory() as temporary_directory:
            client = TestClient(create_review_app(Path(temporary_directory)))
            client.post(
                "/api/runs",
                json={
                    "requirement": "Build a scalable URL shortener service with APIs, persistence, and analytics.",
                    "approved": True,
                },
            )

            response = client.get("/metrics")

            self.assertEqual(response.status_code, 200)
            self.assertIn("text/plain", response.headers["content-type"])
            self.assertIn("agent_runs_total", response.text)
            self.assertIn("agent_task_duration_seconds", response.text)


class LogEventTests(unittest.TestCase):
    def test_log_event_emits_one_json_line_with_the_event_name(self) -> None:
        with self.assertLogs("agentic_system", level="INFO") as captured:
            observability.log_event("unit_test_event", foo="bar")

        payload = json.loads(captured.records[-1].getMessage())
        self.assertEqual(payload["event"], "unit_test_event")
        self.assertEqual(payload["foo"], "bar")


if __name__ == "__main__":
    unittest.main()

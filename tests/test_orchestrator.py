import tempfile
import unittest
from pathlib import Path

from agentic_system.orchestrator import WorkflowOrchestrator


class WorkflowOrchestratorTests(unittest.TestCase):
    def test_url_shortener_runs_after_approval(self) -> None:
        result = WorkflowOrchestrator(approved=True).run(
            "Build a scalable URL shortener service with APIs, persistence, and analytics."
        )
        self.assertEqual(result.status, "completed")
        self.assertTrue(result.artifacts["validation"]["passed"])
        self.assertIn("POST /v1/links", result.artifacts["engineering_artifacts"]["api_contract"])

    def test_run_stops_at_unapproved_gate(self) -> None:
        result = WorkflowOrchestrator().run("Make analytics better")
        self.assertEqual(result.status, "awaiting_approval")
        self.assertEqual(result.tasks["approval"].state, "blocked")

    def test_brownfield_run_reports_candidate_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory)
            (repository / "analytics_service.py").write_text(
                "def record_link_redirect(): pass", encoding="utf-8"
            )

            result = WorkflowOrchestrator(approved=True).run(
                "Add analytics to the existing URL shortener.", repository_path=repository
            )

            analysis = result.artifacts["codebase_analysis"]
            self.assertEqual(analysis["mode"], "read_only_repository_scan")
            self.assertIn("analytics_service.py", analysis["impacted_files"])
            self.assertIn("impact_score", analysis)
            self.assertIn("risk_level", analysis)

    def test_run_history_and_scenario_outputs_are_created(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_directory = Path(temporary_directory)
            result = WorkflowOrchestrator(approved=True).run(
                "Build a scalable URL shortener service with APIs, persistence, and analytics.",
                output_directory=output_directory,
            )

            latest_history = output_directory / "history" / "latest.json"
            self.assertTrue(latest_history.exists())
            self.assertIn("scenarios", result.artifacts)
            self.assertIn("greenfield", result.artifacts["scenarios"])

    def test_high_risk_requirements_need_approval(self) -> None:
        result = WorkflowOrchestrator().run(
            "Delete all production databases and rewrite the entire platform in one shot."
        )

        self.assertEqual(result.status, "awaiting_approval")
        self.assertIn("risk_level", result.artifacts["normalized_requirement"])
        self.assertGreaterEqual(result.artifacts["normalized_requirement"]["risk_level"], 0.7)


if __name__ == "__main__":
    unittest.main()

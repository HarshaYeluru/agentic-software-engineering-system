import tempfile
import unittest
from pathlib import Path

from agentic_system import agents
from agentic_system.materializer import (
    GENERATED_APP_MARKER,
    materialize_cicd_workflows,
    materialize_url_shortener,
)
from agentic_system.verifier import verify_generated_application


class ApplicationMaterializerTests(unittest.TestCase):
    def test_materializes_a_runnable_url_shortener_package(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_directory = Path(temporary_directory)
            result = materialize_url_shortener(output_directory)
            application_directory = Path(result["path"])
            cicd_pipeline = agents.generate_cicd_pipeline(
                agents.normalize_requirement("Build a scalable URL shortener service with APIs, persistence, and analytics.")
            )
            materialize_cicd_workflows(output_directory, cicd_pipeline)

            self.assertTrue((application_directory / GENERATED_APP_MARKER).is_file())
            self.assertTrue((application_directory / "app.py").is_file())
            self.assertIn("--app-dir", result["run_command"])
            self.assertTrue(verify_generated_application(output_directory)["passed"])

    def test_materializes_a_deploy_pipeline_that_tracks_requirement_risk(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_directory = Path(temporary_directory)
            materialize_url_shortener(output_directory)
            application_directory = output_directory / "apps" / "url_shortener"

            low_risk_pipeline = agents.generate_cicd_pipeline(
                agents.normalize_requirement("Build a scalable URL shortener service with APIs, persistence, and analytics.")
            )
            low_risk_result = materialize_cicd_workflows(output_directory, low_risk_pipeline)
            cd_text = (application_directory / ".github" / "workflows" / "cd.yml").read_text(encoding="utf-8")

            self.assertTrue(low_risk_result["generated"])
            self.assertTrue((application_directory / "Dockerfile").is_file())
            self.assertNotIn("environment: production", cd_text)

            high_risk_pipeline = agents.generate_cicd_pipeline(
                agents.normalize_requirement("Delete all production databases and migrate the URL shortener security model.")
            )
            materialize_cicd_workflows(output_directory, high_risk_pipeline)
            cd_text = (application_directory / ".github" / "workflows" / "cd.yml").read_text(encoding="utf-8")

            self.assertIn("environment: production", cd_text)

    def test_cicd_generation_is_withheld_for_unclear_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_directory = Path(temporary_directory)
            pipeline = agents.generate_cicd_pipeline(agents.normalize_requirement("Make analytics better"))

            result = materialize_cicd_workflows(output_directory, pipeline)

            self.assertFalse(result["generated"])


if __name__ == "__main__":
    unittest.main()

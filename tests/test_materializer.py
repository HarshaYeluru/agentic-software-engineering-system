import tempfile
import unittest
from pathlib import Path

from agentic_system.materializer import GENERATED_APP_MARKER, materialize_url_shortener
from agentic_system.verifier import verify_generated_application


class ApplicationMaterializerTests(unittest.TestCase):
    def test_materializes_a_runnable_url_shortener_package(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            result = materialize_url_shortener(Path(temporary_directory))
            application_directory = Path(result["path"])

            self.assertTrue((application_directory / GENERATED_APP_MARKER).is_file())
            self.assertTrue((application_directory / "app.py").is_file())
            self.assertIn("--app-dir", result["run_command"])
            self.assertTrue(verify_generated_application(Path(temporary_directory))["passed"])


if __name__ == "__main__":
    unittest.main()

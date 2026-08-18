import tempfile
import unittest
from pathlib import Path

from agentic_system.cleanup import cleanup_local_state
from agentic_system.materializer import GENERATED_APP_MARKER


class CleanupTests(unittest.TestCase):
    def test_removes_only_known_runtime_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output_directory = root / "generated"
            output_directory.mkdir()
            run_output = output_directory / "run.json"
            run_output.write_text("{}", encoding="utf-8")

            database = root / "data" / "url_shortener.sqlite3"
            database.parent.mkdir()
            database.write_text("database", encoding="utf-8")
            wal_file = Path(f"{database}-wal")
            wal_file.write_text("wal", encoding="utf-8")

            generated_application = output_directory / "apps" / "url_shortener"
            generated_application.mkdir(parents=True)
            (generated_application / GENERATED_APP_MARKER).write_text("generated", encoding="utf-8")
            (generated_application / "app.py").write_text("generated source", encoding="utf-8")

            source_file = root / "app.py"
            source_file.write_text("source must remain", encoding="utf-8")

            removed = cleanup_local_state(output_directory, database)

            self.assertEqual(set(removed), {run_output, database, wal_file, generated_application})
            self.assertFalse(run_output.exists())
            self.assertFalse(database.exists())
            self.assertFalse(wal_file.exists())
            self.assertFalse(generated_application.exists())
            self.assertTrue(source_file.exists())


if __name__ == "__main__":
    unittest.main()

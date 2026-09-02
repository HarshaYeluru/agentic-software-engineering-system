import tempfile
import unittest
from pathlib import Path

from agentic_system import agents, patcher

REQUIREMENT = "Build a scalable URL shortener service with APIs, persistence, and analytics."


def _normalized_and_pipeline():
    normalized = agents.normalize_requirement(REQUIREMENT)
    cicd_pipeline = agents.generate_cicd_pipeline(normalized)
    return normalized, cicd_pipeline


class PlanPatchTests(unittest.TestCase):
    def test_creates_all_files_for_a_fresh_repository(self) -> None:
        normalized, cicd_pipeline = _normalized_and_pipeline()
        with tempfile.TemporaryDirectory() as temporary_directory:
            plan = patcher.plan_patch(Path(temporary_directory), normalized, cicd_pipeline)

            paths = {change.path for change in plan.changes}
            self.assertIn("url_shortener/app.py", paths)
            self.assertIn("url_shortener/store.py", paths)
            self.assertIn("tests/test_url_shortener.py", paths)
            self.assertIn(".github/workflows/ci.yml", paths)
            self.assertIn(".github/workflows/cd.yml", paths)
            self.assertIn("Dockerfile", paths)
            self.assertTrue(all(change.action == "create" for change in plan.changes))
            self.assertTrue(all(change.diff for change in plan.changes))

    def test_computes_an_update_diff_for_an_existing_file(self) -> None:
        normalized, cicd_pipeline = _normalized_and_pipeline()
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory)
            (repository / "url_shortener").mkdir()
            (repository / "url_shortener" / "app.py").write_text("stale content\n", encoding="utf-8")

            plan = patcher.plan_patch(repository, normalized, cicd_pipeline)

            app_change = next(change for change in plan.changes if change.path == "url_shortener/app.py")
            self.assertEqual(app_change.action, "update")
            self.assertIn("-stale content", app_change.diff)

    def test_skips_files_that_already_match(self) -> None:
        normalized, cicd_pipeline = _normalized_and_pipeline()
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory)
            first_plan = patcher.plan_patch(repository, normalized, cicd_pipeline)
            patcher.apply_patch(first_plan)

            second_plan = patcher.plan_patch(repository, normalized, cicd_pipeline)

            self.assertEqual(second_plan.changes, [])

    def test_empty_for_an_out_of_scope_requirement(self) -> None:
        normalized = agents.normalize_requirement("Make analytics better")
        with tempfile.TemporaryDirectory() as temporary_directory:
            plan = patcher.plan_patch(Path(temporary_directory), normalized, {})

            self.assertEqual(plan.changes, [])

    def test_never_touches_files_outside_the_bounded_set(self) -> None:
        normalized, cicd_pipeline = _normalized_and_pipeline()
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory)
            unrelated_file = repository / "unrelated_notes.md"
            unrelated_file.write_text("do not touch\n", encoding="utf-8")

            plan = patcher.plan_patch(repository, normalized, cicd_pipeline)
            patcher.apply_patch(plan)

            self.assertEqual(unrelated_file.read_text(encoding="utf-8"), "do not touch\n")


class ApplyAndRollbackPatchTests(unittest.TestCase):
    def test_apply_writes_files_and_backs_up_the_existing_one(self) -> None:
        normalized, cicd_pipeline = _normalized_and_pipeline()
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory)
            (repository / "url_shortener").mkdir()
            (repository / "url_shortener" / "app.py").write_text("stale content\n", encoding="utf-8")

            plan = patcher.plan_patch(repository, normalized, cicd_pipeline)
            outcome = patcher.apply_patch(plan)

            self.assertTrue(outcome["applied"])
            self.assertIn("url_shortener/app.py", outcome["files"])
            new_content = (repository / "url_shortener" / "app.py").read_text(encoding="utf-8")
            self.assertNotEqual(new_content, "stale content\n")

            backup_directory = Path(outcome["backup_directory"])
            self.assertEqual((backup_directory / "url_shortener" / "app.py").read_text(encoding="utf-8"), "stale content\n")
            self.assertTrue((backup_directory / "manifest.json").is_file())

    def test_apply_with_no_changes_reports_not_applied(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            plan = patcher.PatchPlan(Path(temporary_directory), [])

            outcome = patcher.apply_patch(plan)

            self.assertFalse(outcome["applied"])

    def test_rollback_restores_updates_and_removes_creations(self) -> None:
        normalized, cicd_pipeline = _normalized_and_pipeline()
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory)
            (repository / "url_shortener").mkdir()
            (repository / "url_shortener" / "app.py").write_text("stale content\n", encoding="utf-8")

            plan = patcher.plan_patch(repository, normalized, cicd_pipeline)
            outcome = patcher.apply_patch(plan)

            patcher.rollback_patch(repository, outcome["run_id"])

            self.assertEqual((repository / "url_shortener" / "app.py").read_text(encoding="utf-8"), "stale content\n")
            self.assertFalse((repository / "url_shortener" / "store.py").exists())
            self.assertFalse((repository / "Dockerfile").exists())

    def test_rollback_raises_for_an_unknown_run_id(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            with self.assertRaises(ValueError):
                patcher.rollback_patch(Path(temporary_directory), "not-a-real-run")


if __name__ == "__main__":
    unittest.main()

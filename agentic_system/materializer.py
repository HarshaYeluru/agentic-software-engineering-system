from __future__ import annotations

import shutil
from pathlib import Path


GENERATED_APP_MARKER = ".agentic-generated-app"
REFERENCE_APPLICATION = Path(__file__).resolve().parent.parent / "url_shortener"
REFERENCE_TEST = Path(__file__).resolve().parent.parent / "tests" / "test_url_shortener.py"


def generated_application_directory(output_directory: Path) -> Path:
    return output_directory / "apps" / "url_shortener"


def materialize_url_shortener(output_directory: Path) -> dict[str, object]:
    """Create a runnable application artifact from the checked-in reference template.

    The reference package remains available for development and tests. The copied
    artifact is the workspace an implementation agent would hand to a reviewer.
    """
    application_directory = generated_application_directory(output_directory)
    _clear_existing_generated_application(application_directory)
    application_directory.mkdir(parents=True)

    copied_files: list[str] = []
    for name in ("__init__.py", "app.py", "store.py"):
        shutil.copy2(REFERENCE_APPLICATION / name, application_directory / name)
        copied_files.append(name)

    test_directory = application_directory / "tests"
    test_directory.mkdir()
    shutil.copy2(REFERENCE_TEST, test_directory / "test_url_shortener.py")
    copied_files.append("tests/test_url_shortener.py")

    (application_directory / GENERATED_APP_MARKER).write_text(
        "This directory was materialized by the agentic workflow. It is safe to remove with --clean.\n",
        encoding="utf-8",
    )
    (application_directory / "README.md").write_text(
        "# Generated URL Shortener\n\n"
        "This is a runnable application artifact created by the engineering workflow. "
        "From the repository root, run:\n\n"
        "```powershell\n"
        "python -m uvicorn url_shortener.app:app --app-dir generated/apps --reload\n"
        "```\n",
        encoding="utf-8",
    )
    copied_files.extend([GENERATED_APP_MARKER, "README.md"])

    application_parent = application_directory.parent.as_posix()
    return {
        "path": str(application_directory),
        "files": copied_files,
        "run_command": f"python -m uvicorn url_shortener.app:app --app-dir {application_parent} --reload",
    }


def remove_generated_application(output_directory: Path) -> Path | None:
    """Remove one marked generated app, refusing to remove an unmarked directory."""
    application_directory = generated_application_directory(output_directory)
    marker = application_directory / GENERATED_APP_MARKER
    if not application_directory.exists():
        return None
    if not marker.is_file():
        raise ValueError(f"Refusing to remove unmarked directory: {application_directory}")

    shutil.rmtree(application_directory)
    return application_directory


def _clear_existing_generated_application(application_directory: Path) -> None:
    if not application_directory.exists():
        return
    marker = application_directory / GENERATED_APP_MARKER
    if not marker.is_file():
        raise ValueError(f"Refusing to overwrite unmarked directory: {application_directory}")
    shutil.rmtree(application_directory)

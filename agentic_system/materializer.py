from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

GENERATED_APP_MARKER = ".agentic-generated-app"
REFERENCE_APPLICATION = Path(__file__).resolve().parent.parent / "url_shortener"
REFERENCE_TEST = Path(__file__).resolve().parent.parent / "tests" / "test_url_shortener.py"

_DOCKERFILE_TEMPLATE = """FROM python:3.11-slim
WORKDIR /app
COPY . /app/url_shortener
RUN pip install --no-cache-dir "fastapi>=0.115,<1.0" "uvicorn[standard]>=0.30,<1.0" "prometheus-client>=0.20,<1.0"
EXPOSE 8000
CMD ["uvicorn", "url_shortener.app:app", "--app-dir", "/app", "--host", "0.0.0.0", "--port", "8000"]
"""

_CI_STEP_LIBRARY: dict[str, tuple[str, list[str]]] = {
    "install_dependencies": (
        "Install project dependencies",
        ["python -m pip install --upgrade pip setuptools", "python -m pip install -e \".[dev]\""],
    ),
    "lint_and_security_scan": (
        "Lint and security scan (ruff, bandit)",
        ["ruff check .", "bandit -q -r url_shortener"],
    ),
    "run_api_tests": ("Run url_shortener API tests", ["python -m unittest tests.test_url_shortener -v"]),
    "run_full_regression": ("Run full regression suite", ["python -m unittest discover -s tests -v"]),
    "run_dependency_audit": (
        "Run dependency security audit",
        ["python -m pip install pip-audit", "pip-audit"],
    ),
}

_CD_STEP_LIBRARY: dict[str, tuple[str, list[str]]] = {
    "require_manual_approval": (
        "Require manual release approval",
        ["echo 'High-risk change: this job runs under the production environment protection rule.'"],
    ),
    "build_image": ("Build Docker image", ["docker build -t url-shortener:${{ github.sha }} ."]),
    "push_image": (
        "Push image to GHCR",
        [
            'echo "${{ secrets.GITHUB_TOKEN }}" | docker login ghcr.io -u "${{ github.actor }}" --password-stdin',
            "docker tag url-shortener:${{ github.sha }} ghcr.io/${{ github.repository_owner }}/url-shortener:${{ github.sha }}",
            "docker push ghcr.io/${{ github.repository_owner }}/url-shortener:${{ github.sha }}",
        ],
    ),
}


def generated_application_directory(output_directory: Path) -> Path:
    return output_directory / "apps" / "url_shortener"


def reference_application_files() -> dict[str, str]:
    """The url_shortener reference implementation's contents, keyed by the relative
    path they occupy in a real target repository (``url_shortener/app.py``, not the
    ``generated/`` sandbox layout ``materialize_url_shortener`` writes to).

    Used by ``agentic_system.patcher`` to apply the same reference implementation
    to an existing repository, bounded to exactly these paths.
    """
    files = {
        f"url_shortener/{name}": (REFERENCE_APPLICATION / name).read_text(encoding="utf-8")
        for name in ("__init__.py", "app.py", "store.py")
    }
    files["tests/test_url_shortener.py"] = REFERENCE_TEST.read_text(encoding="utf-8")
    return files


def render_cicd_files(cicd_pipeline: dict[str, Any]) -> dict[str, str]:
    """The CI/CD workflow and Dockerfile contents, keyed by their relative path in a
    real target repository. Empty if the pipeline artifact has no ci/cd_pipeline yet
    (scope not clarified) — same guard ``materialize_cicd_workflows`` uses.
    """
    if "ci_pipeline" not in cicd_pipeline or "cd_pipeline" not in cicd_pipeline:
        return {}
    return {
        ".github/workflows/ci.yml": _render_ci_workflow(cicd_pipeline["ci_pipeline"]),
        ".github/workflows/cd.yml": _render_cd_workflow(cicd_pipeline["cd_pipeline"]),
        "Dockerfile": _DOCKERFILE_TEMPLATE,
    }


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


def materialize_cicd_workflows(output_directory: Path, cicd_pipeline: dict[str, Any]) -> dict[str, object]:
    """Write the deploy pipeline for the generated application.

    Runs on every workflow invocation, so the CI/CD definition is regenerated
    from the current requirement's ``cicd_pipeline`` artifact each time rather
    than being edited by hand and left to fall out of sync with the software.
    """
    application_directory = generated_application_directory(output_directory)
    if "ci_pipeline" not in cicd_pipeline or "cd_pipeline" not in cicd_pipeline:
        return {"generated": False, "reason": cicd_pipeline.get("note", "scope not clarified")}

    workflows_directory = application_directory / ".github" / "workflows"
    workflows_directory.mkdir(parents=True, exist_ok=True)

    ci_path = workflows_directory / "ci.yml"
    cd_path = workflows_directory / "cd.yml"
    dockerfile_path = application_directory / "Dockerfile"

    ci_path.write_text(_render_ci_workflow(cicd_pipeline["ci_pipeline"]), encoding="utf-8")
    cd_path.write_text(_render_cd_workflow(cicd_pipeline["cd_pipeline"]), encoding="utf-8")
    dockerfile_path.write_text(_DOCKERFILE_TEMPLATE, encoding="utf-8")

    return {
        "generated": True,
        "files": [
            str(ci_path.relative_to(output_directory).as_posix()),
            str(cd_path.relative_to(output_directory).as_posix()),
            str(dockerfile_path.relative_to(output_directory).as_posix()),
        ],
    }


def _render_steps(step_keys: list[str], library: dict[str, tuple[str, list[str]]]) -> str:
    blocks = []
    for key in step_keys:
        display_name, command_lines = library[key]
        block = [f"      - name: {display_name}", "        run: |"]
        block.extend(f"          {line}" for line in command_lines)
        blocks.append("\n".join(block))
    return "\n".join(blocks)


def _render_ci_workflow(spec: dict[str, Any]) -> str:
    trigger_paths = spec.get("trigger_paths", [])
    paths_yaml = "\n".join(f'      - "{path}"' for path in trigger_paths)
    steps_yaml = _render_steps(spec["steps"], _CI_STEP_LIBRARY)
    return (
        f"name: {spec['name']}\n"
        "\n"
        "on:\n"
        "  push:\n"
        "    branches:\n"
        "      - main\n"
        "      - master\n"
        "    paths:\n"
        f"{paths_yaml}\n"
        "  pull_request:\n"
        "    paths:\n"
        f"{paths_yaml}\n"
        "\n"
        "jobs:\n"
        "  test:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - name: Check out repository\n"
        "        uses: actions/checkout@v4\n"
        "      - name: Set up Python\n"
        "        uses: actions/setup-python@v5\n"
        "        with:\n"
        '          python-version: "3.11"\n'
        "          cache: pip\n"
        f"{steps_yaml}\n"
    )


def _render_cd_workflow(spec: dict[str, Any]) -> str:
    needs_environment = "require_manual_approval" in spec["steps"]
    environment_yaml = "    environment: production\n" if needs_environment else ""
    steps_yaml = _render_steps(spec["steps"], _CD_STEP_LIBRARY)
    return (
        f"name: {spec['name']}\n"
        "\n"
        "on:\n"
        "  workflow_run:\n"
        '    workflows: ["URL Shortener CI"]\n'
        "    types:\n"
        "      - completed\n"
        "  workflow_dispatch:\n"
        "\n"
        "jobs:\n"
        "  deploy:\n"
        "    if: ${{ github.event_name == 'workflow_dispatch' || github.event.workflow_run.conclusion == 'success' }}\n"
        "    runs-on: ubuntu-latest\n"
        f"{environment_yaml}"
        "    steps:\n"
        "      - name: Check out repository\n"
        "        uses: actions/checkout@v4\n"
        f"{steps_yaml}\n"
    )


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

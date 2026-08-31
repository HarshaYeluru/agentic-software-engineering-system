from __future__ import annotations

import os
import subprocess  # nosec B404 - fixed, hardcoded command list below; no untrusted input reaches this module
import sys
from pathlib import Path
from typing import Any

from .materializer import generated_application_directory


def verify_generated_application(output_directory: Path) -> dict[str, Any]:
    """Run a compact build-and-test check against the materialized application."""
    application_directory = generated_application_directory(output_directory)
    if not application_directory.is_dir():
        return {"passed": False, "checks": [], "findings": ["Generated application directory is missing."]}

    commands = [
        ("compile", [sys.executable, "-m", "compileall", "-q", "url_shortener"]),
        ("tests", [sys.executable, "-m", "unittest", "discover", "-s", "url_shortener/tests", "-v"]),
    ]
    checks: list[dict[str, Any]] = []
    findings: list[str] = []
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(application_directory.parent)

    for name, command in commands:
        try:
            completed = subprocess.run(  # nosec B603 - command is one of the two fixed lists above, not user input
                command,
                cwd=application_directory.parent,
                env=environment,
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
        except subprocess.TimeoutExpired:
            checks.append({"name": name, "passed": False, "output": "Timed out after 20 seconds."})
            findings.append(f"{name} check timed out.")
            continue

        output = (completed.stdout + completed.stderr).strip()
        checks.append({"name": name, "passed": completed.returncode == 0, "output": output[-2_000:]})
        if completed.returncode != 0:
            findings.append(f"{name} check failed with exit code {completed.returncode}.")

    cicd_check = _verify_cicd_workflows(application_directory)
    checks.append(cicd_check)
    if not cicd_check["passed"]:
        findings.append("cicd workflow files are missing or malformed.")

    return {"passed": not findings, "checks": checks, "findings": findings}


def _verify_cicd_workflows(application_directory: Path) -> dict[str, Any]:
    """Confirm the generated deploy pipeline files exist and look structurally sane."""
    ci_path = application_directory / ".github" / "workflows" / "ci.yml"
    cd_path = application_directory / ".github" / "workflows" / "cd.yml"
    missing = [str(path) for path in (ci_path, cd_path) if not path.is_file()]
    if missing:
        return {"name": "cicd_workflows", "passed": False, "output": f"missing: {', '.join(missing)}"}

    valid = "jobs:" in ci_path.read_text(encoding="utf-8") and "jobs:" in cd_path.read_text(encoding="utf-8")
    return {
        "name": "cicd_workflows",
        "passed": valid,
        "output": "ci.yml and cd.yml present" if valid else "workflow files are missing a jobs section",
    }

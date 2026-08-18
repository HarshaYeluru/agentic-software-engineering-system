from __future__ import annotations

import os
import subprocess
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
            completed = subprocess.run(
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

    return {"passed": not findings, "checks": checks, "findings": findings}

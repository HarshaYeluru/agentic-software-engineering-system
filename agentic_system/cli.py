from __future__ import annotations

import argparse
import json
from pathlib import Path

from .cleanup import cleanup_local_state
from .orchestrator import WorkflowOrchestrator


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a controlled engineering workflow.")
    parser.add_argument("--requirement", help="Requirement to analyze and turn into engineering artifacts.")
    parser.add_argument("--approve", action="store_true", help="Record human approval of assumptions and plan.")
    parser.add_argument("--output-dir", default="generated")
    parser.add_argument(
        "--repository-path",
        type=Path,
        help="Optional existing repository to scan read-only for brownfield impact analysis.",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove local workflow output and URL-shortener database files before running.",
    )
    args = parser.parse_args()
    output = Path(args.output_dir)

    if args.clean:
        removed = cleanup_local_state(output)
        if removed:
            print("Removed local demo artifacts:")
            for path in removed:
                print(f"- {path}")
        else:
            print("No local demo artifacts were found.")

    if args.requirement is None:
        if args.clean:
            return
        parser.error("--requirement is required unless --clean is used by itself")

    result = WorkflowOrchestrator(approved=args.approve).run(
        args.requirement,
        output,
        args.repository_path,
    )
    output.mkdir(parents=True, exist_ok=True)
    (output / "run.json").write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
    print(f"Workflow status: {result.status}")
    print(f"Review artifacts: {output / 'run.json'}")


if __name__ == "__main__":
    main()

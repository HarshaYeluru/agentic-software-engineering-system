from __future__ import annotations

import argparse
import json
from pathlib import Path

from .cleanup import cleanup_local_state
from .orchestrator import WorkflowOrchestrator
from .patcher import apply_patch, plan_patch


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
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help=(
            "Use an LLM (Anthropic, via ANTHROPIC_API_KEY) to interpret the requirement instead of "
            "the deterministic rule-based normalizer. Falls back to the deterministic result if no "
            "key is set or the call fails, so this is always safe to pass."
        ),
    )
    parser.add_argument(
        "--apply-to-repository",
        action="store_true",
        help=(
            "Write the bounded, previewed file changes into --repository-path. Requires --approve "
            "and --repository-path. Without this flag, a diff preview is still computed and saved "
            "under <output-dir>/patches/, but --repository-path is never written to."
        ),
    )
    args = parser.parse_args()

    if args.apply_to_repository and not args.approve:
        parser.error("--apply-to-repository requires --approve")
    if args.apply_to_repository and args.repository_path is None:
        parser.error("--apply-to-repository requires --repository-path")
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

    result = WorkflowOrchestrator(approved=args.approve, use_llm=args.use_llm).run(
        args.requirement,
        output,
        args.repository_path,
    )
    output.mkdir(parents=True, exist_ok=True)
    (output / "run.json").write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
    print(f"Workflow status: {result.status}")
    print(f"Review artifacts: {output / 'run.json'}")

    if args.repository_path is not None and result.status == "completed":
        normalized_requirement = result.artifacts["normalized_requirement"]
        cicd_pipeline = result.artifacts["engineering_artifacts"].get("cicd_pipeline", {})
        plan = plan_patch(args.repository_path, normalized_requirement, cicd_pipeline)

        patch_directory = output / "patches"
        patch_directory.mkdir(parents=True, exist_ok=True)
        plan_path = patch_directory / "latest.json"
        plan_path.write_text(json.dumps(plan.to_dict(), indent=2), encoding="utf-8")
        print(f"Patch preview: {plan_path} ({len(plan.changes)} file(s) would change)")

        if args.apply_to_repository:
            outcome = apply_patch(plan)
            if outcome["applied"]:
                print(f"Applied patch to {args.repository_path} (backup: {outcome['backup_directory']})")
            else:
                print(f"No changes applied: {outcome['reason']}")


if __name__ == "__main__":
    main()

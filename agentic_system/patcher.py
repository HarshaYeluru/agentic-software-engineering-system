from __future__ import annotations

import difflib
import json
import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .agents import URL_SHORTENER_SCOPE
from .materializer import reference_application_files, render_cicd_files

PATCH_BACKUP_DIRECTORY = ".agentic-patch-backup"


@dataclass
class FileChange:
    path: str
    action: str  # "create" or "update"
    diff: str
    new_content: str


@dataclass
class PatchPlan:
    target_repository: Path
    changes: list[FileChange] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_repository": str(self.target_repository),
            "files": [change.path for change in self.changes],
            "changes": [
                {"path": change.path, "action": change.action, "diff": change.diff} for change in self.changes
            ],
        }


def _candidate_files(normalized_requirement: dict[str, Any], cicd_pipeline: dict[str, Any]) -> dict[str, str]:
    """The exact, bounded set of paths this patcher is allowed to touch, and their
    intended new content — nothing outside this set is ever read, written, or backed up.

    This is deliberately the same file set ``orchestrator._build_sandbox_patch_preview``
    already declares as "what a real patch would touch": the preview and the actual
    bounded write target are the same list, so a run's stated intent and its real
    effect can never silently diverge.
    """
    if normalized_requirement.get("functional_scope") != URL_SHORTENER_SCOPE:
        return {}
    files = dict(reference_application_files())
    files.update(render_cicd_files(cicd_pipeline))
    return files


def plan_patch(
    target_repository: Path,
    normalized_requirement: dict[str, Any],
    cicd_pipeline: dict[str, Any] | None = None,
) -> PatchPlan:
    """Compute what would change in ``target_repository``, as unified diffs.

    Read-only: this never writes to ``target_repository``. Every path considered
    comes from ``_candidate_files``, so a requirement outside the recognized scope
    (functional_scope != URL_SHORTENER_SCOPE) always produces an empty plan rather
    than guessing at what to change.
    """
    candidates = _candidate_files(normalized_requirement, cicd_pipeline or {})
    changes: list[FileChange] = []

    for relative_path, new_content in sorted(candidates.items()):
        target_path = target_repository / relative_path
        existed = target_path.is_file()
        old_content = target_path.read_text(encoding="utf-8") if existed else ""
        if old_content == new_content:
            continue

        diff_text = "".join(
            difflib.unified_diff(
                old_content.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                fromfile=f"a/{relative_path}" if existed else "/dev/null",
                tofile=f"b/{relative_path}",
            )
        )
        changes.append(
            FileChange(
                path=relative_path,
                action="update" if existed else "create",
                diff=diff_text,
                new_content=new_content,
            )
        )

    return PatchPlan(target_repository, changes)


def apply_patch(plan: PatchPlan) -> dict[str, Any]:
    """Write ``plan``'s changes to its target repository, after backing up any file
    that already existed. Writes only the paths in ``plan.changes`` — never a
    broader set than what ``plan_patch`` computed and a caller reviewed.

    A manifest recording which files existed before is written alongside the
    backup so ``rollback_patch`` can restore updates and remove creations.
    """
    if not plan.changes:
        return {"applied": False, "reason": "no changes to apply", "files": []}

    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup_directory = plan.target_repository / PATCH_BACKUP_DIRECTORY / run_id
    applied_files: list[str] = []
    manifest_changes: list[dict[str, Any]] = []

    for change in plan.changes:
        target_path = plan.target_repository / change.path
        existed_before = target_path.is_file()
        if existed_before:
            backup_path = backup_directory / change.path
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target_path, backup_path)

        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(change.new_content, encoding="utf-8")
        applied_files.append(change.path)
        manifest_changes.append({"path": change.path, "existed_before": existed_before})

    backup_directory.mkdir(parents=True, exist_ok=True)
    manifest = {
        "target_repository": str(plan.target_repository),
        "run_id": run_id,
        "created_at": datetime.now(UTC).isoformat(),
        "changes": manifest_changes,
    }
    (backup_directory / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return {
        "applied": True,
        "run_id": run_id,
        "files": applied_files,
        "backup_directory": str(backup_directory),
    }


def rollback_patch(target_repository: Path, run_id: str) -> list[str]:
    """Undo one ``apply_patch`` run: restore files that were overwritten, and
    remove files that were newly created, using that run's manifest."""
    backup_directory = target_repository / PATCH_BACKUP_DIRECTORY / run_id
    manifest_path = backup_directory / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError(f"No backup manifest found for run {run_id} at {backup_directory}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    actions: list[str] = []
    for entry in manifest["changes"]:
        target_path = target_repository / entry["path"]
        if entry["existed_before"]:
            backup_path = backup_directory / entry["path"]
            shutil.copy2(backup_path, target_path)
            actions.append(f"restored: {entry['path']}")
        elif target_path.is_file():
            target_path.unlink()
            actions.append(f"removed: {entry['path']}")

    return actions

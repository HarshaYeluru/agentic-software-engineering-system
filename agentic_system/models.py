from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class TaskState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass
class EngineeringTask:
    id: str
    title: str
    depends_on: list[str] = field(default_factory=list)
    requires_approval: bool = False
    state: TaskState = TaskState.PENDING
    result: dict[str, Any] | None = None


@dataclass
class RunResult:
    requirement: str
    tasks: dict[str, EngineeringTask]
    artifacts: dict[str, Any]
    trace: list[dict[str, str]]
    status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "requirement": self.requirement,
            "status": self.status,
            "tasks": {task_id: asdict(task) for task_id, task in self.tasks.items()},
            "artifacts": self.artifacts,
            "trace": self.trace,
        }

    def save_history(self, output_directory: Path | None = None) -> Path | None:
        if output_directory is None:
            return None
        history_dir = output_directory / "history"
        history_dir.mkdir(parents=True, exist_ok=True)
        target = history_dir / "latest.json"
        target.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return target

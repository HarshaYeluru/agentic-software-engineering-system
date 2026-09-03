from __future__ import annotations

import json
import logging
from typing import Any

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

__all__ = [
    "CONTENT_TYPE_LATEST",
    "AGENT_RUNS_TOTAL",
    "AGENT_RUN_DURATION",
    "AGENT_TASK_DURATION",
    "AGENT_LLM_FALLBACK_TOTAL",
    "AGENT_PATCH_APPLY_TOTAL",
    "log_event",
    "metrics_text",
]

# Module-level: prometheus_client's default registry rejects re-registering a
# metric with the same name, and this module may be imported more than once
# per process (every test, every CLI invocation).
AGENT_RUNS_TOTAL = Counter(
    "agent_runs_total", "Total workflow runs by terminal status", ["status"]
)
AGENT_RUN_DURATION = Histogram(
    "agent_run_duration_seconds", "Total wall-clock duration of a workflow run"
)
AGENT_TASK_DURATION = Histogram(
    "agent_task_duration_seconds", "Duration of a single task within a run", ["task"]
)
AGENT_LLM_FALLBACK_TOTAL = Counter(
    "agent_llm_fallback_total",
    "Times --use-llm fell back to the deterministic result instead of the model's",
    ["reason"],
)
AGENT_PATCH_APPLY_TOTAL = Counter(
    "agent_patch_apply_total", "Repository patch apply attempts by outcome", ["outcome"]
)

logger = logging.getLogger("agentic_system")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def log_event(event: str, **fields: Any) -> None:
    """Emit one JSON line describing something the agent did.

    Same shape as url_shortener's request logging (an `event` key plus
    structured fields, one line per occurrence) so both halves of this
    project are ingestible by the same log pipeline without a parsing rule.
    """
    logger.info(json.dumps({"event": event, **fields}))


def metrics_text() -> bytes:
    """Render current metric values in Prometheus text exposition format."""
    return generate_latest()

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Protocol

from . import agents as deterministic_agents

VALID_CLASSIFICATIONS = {"greenfield", "brownfield", "ambiguous"}

NORMALIZE_REQUIREMENT_PROMPT = """You are a senior requirements analyst for a software engineering \
workflow. Read the requirement below and extract a structured brief. You are not writing code or \
a design yet — only interpreting intent and flagging what is unclear.

Requirement:
\"\"\"{requirement}\"\"\"

Repository context: {repository_context}

Respond with ONLY a single JSON object (no prose, no markdown fences) with exactly these keys:

- "intent": one sentence describing what is actually being asked for.
- "classification": one of "greenfield", "brownfield", or "ambiguous".
  Use "brownfield" if this changes an existing system or repository context is present.
  Use "ambiguous" if the request is too vague to act on without more information.
  Use "greenfield" only for a clearly-scoped new build.
- "risk_level": a number from 0.0 to 1.0 for how risky this change is to execute autonomously.
  Higher for anything touching production data, deletion, security, or migrations.
- "ambiguities": a list of short strings — specific things the requirement does not specify
  that a careful engineer would want clarified (empty list if none).
- "assumptions": a list of short strings — reasonable assumptions to proceed under given the
  ambiguities above (empty list if none).
- "clarification_questions": a list of short, specific questions a human should answer before
  this is implemented (empty list if the requirement is already clear).

Be conservative: if you are unsure whether something is risky or ambiguous, say so rather than
guessing. Respond with the JSON object and nothing else.
"""


class LLMClient(Protocol):
    """Structural interface any LLM backend must satisfy to be used here.

    Kept minimal on purpose: one method, one string in, one string out. That
    makes it trivial to substitute a fake in tests without touching the
    provider SDK, and trivial to add a second real provider later without
    changing any calling code.
    """

    def complete(self, prompt: str) -> str: ...


class AnthropicClient:
    """Thin adapter around the Anthropic SDK.

    The SDK is an optional dependency (``pip install -e ".[llm]"``) and is
    imported lazily here, inside the constructor, specifically so that
    importing this module — or the rest of the package — never requires it.
    Only instantiating this class does.
    """

    def __init__(self, model: str = "claude-sonnet-4-5", api_key: str | None = None) -> None:
        try:
            import anthropic
        except ImportError as error:
            raise RuntimeError(
                "The 'anthropic' package is required for LLM-backed normalization. "
                "Install it with: pip install -e \".[llm]\""
            ) from error
        resolved_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not resolved_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set and no api_key was provided.")
        self._client = anthropic.Anthropic(api_key=resolved_key)
        self._model = model

    def complete(self, prompt: str) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in response.content if getattr(block, "type", None) == "text")


def llm_available() -> bool:
    """Whether an LLM-backed run can proceed without an explicit client being passed in."""
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def normalize_requirement(
    requirement: str,
    repository_path: Path | None = None,
    client: LLMClient | None = None,
) -> dict[str, Any]:
    """LLM-backed requirement understanding, with a validated deterministic fallback.

    This never lets model output reach the approval gate unchecked. The
    deterministic normalizer (``agents.normalize_requirement``) always runs
    first as a computed fallback; the model's response is only accepted field
    by field, and only where it parses as JSON, has the right type, and (for
    risk_level/classification) is within the range/enum the rest of the
    system already trusts. ``approval_required`` is always recomputed from the
    resulting risk_level/classification rather than accepted from the model —
    that field gates real behavior (whether implementation proceeds without a
    human), so it stays under the same rule the deterministic path uses.

    ``functional_scope`` and ``requirement_terms`` are intentionally left to
    the deterministic fallback: several downstream functions (``analyze_codebase``,
    ``design_architecture``, ``generate_engineering_artifacts``) compare
    ``functional_scope`` against a fixed, known list by equality, so letting a
    model author free-form text there would silently break every stage after
    normalization. The model enriches *interpretation* (intent, risk,
    ambiguity, clarifying questions); the deterministic engine still owns the
    structural fields the rest of the pipeline is wired against.

    Any failure — no client available, a network error, malformed JSON, an
    out-of-range value — falls back to the deterministic result for that run.
    Nothing about calling this function can produce output the rest of the
    workflow doesn't already know how to validate.
    """
    fallback = deterministic_agents.normalize_requirement(requirement, repository_path)

    if client is None:
        if not llm_available():
            return fallback
        client = AnthropicClient()

    repository_context = str(repository_path) if repository_path is not None else "none (no existing repository given)"
    prompt = NORMALIZE_REQUIREMENT_PROMPT.format(requirement=requirement, repository_context=repository_context)

    try:
        raw_response = client.complete(prompt)
        parsed = _extract_json_object(raw_response)
    except Exception:
        return fallback

    return _validate_and_merge(parsed, fallback)


def _extract_json_object(text: str) -> dict[str, Any]:
    """Pull the first {...} block out of a response and parse it.

    Models occasionally wrap JSON in prose or a markdown fence despite being
    told not to; this tolerates that without trying to be a general-purpose
    parser.
    """
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match is None:
        raise ValueError("No JSON object found in model response.")
    parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("Parsed JSON was not an object.")
    return parsed


def _validate_and_merge(parsed: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    """Accept only well-typed, in-range fields from `parsed`; keep the fallback otherwise."""
    result = dict(fallback)

    intent = parsed.get("intent")
    if isinstance(intent, str) and intent.strip():
        result["intent"] = intent.strip()

    classification = parsed.get("classification")
    if isinstance(classification, str) and classification in VALID_CLASSIFICATIONS:
        result["classification"] = classification

    risk_level = parsed.get("risk_level")
    if isinstance(risk_level, (int, float)) and not isinstance(risk_level, bool) and 0.0 <= float(risk_level) <= 1.0:
        result["risk_level"] = round(float(risk_level), 2)

    for key in ("ambiguities", "assumptions", "clarification_questions"):
        value = parsed.get(key)
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            result[key] = value

    # approval_required gates real autonomous behavior downstream, so it is always
    # recomputed from the trusted rule rather than accepted from the model.
    result["approval_required"] = result["risk_level"] >= 0.7 or result["classification"] == "brownfield"
    return result

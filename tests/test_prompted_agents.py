import json
import unittest
from unittest.mock import patch

from agentic_system import prompted_agents
from agentic_system.agents import normalize_requirement as deterministic_normalize


class FakeClient:
    def __init__(self, response: str) -> None:
        self.response = response
        self.last_prompt: str | None = None

    def complete(self, prompt: str) -> str:
        self.last_prompt = prompt
        return self.response


class PromptedNormalizeRequirementTests(unittest.TestCase):
    REQUIREMENT = "Build a scalable URL shortener service with APIs, persistence, and analytics."

    def test_falls_back_when_no_client_and_no_api_key(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            result = prompted_agents.normalize_requirement(self.REQUIREMENT)

        self.assertEqual(result, deterministic_normalize(self.REQUIREMENT))

    def test_accepts_a_valid_well_formed_response(self) -> None:
        client = FakeClient(
            json.dumps(
                {
                    "intent": "Ship a production-ready URL shortener.",
                    "classification": "greenfield",
                    "risk_level": 0.4,
                    "ambiguities": ["Peak traffic target is unspecified."],
                    "assumptions": ["HTTPS only."],
                    "clarification_questions": ["What is the expected QPS?"],
                }
            )
        )

        result = prompted_agents.normalize_requirement(self.REQUIREMENT, client=client)

        self.assertEqual(result["intent"], "Ship a production-ready URL shortener.")
        self.assertEqual(result["classification"], "greenfield")
        self.assertEqual(result["risk_level"], 0.4)
        self.assertEqual(result["ambiguities"], ["Peak traffic target is unspecified."])
        self.assertEqual(result["clarification_questions"], ["What is the expected QPS?"])
        self.assertIsNotNone(client.last_prompt)

    def test_functional_scope_and_requirement_terms_stay_deterministic(self) -> None:
        client = FakeClient(json.dumps({"intent": "custom intent", "classification": "greenfield"}))
        fallback = deterministic_normalize(self.REQUIREMENT)

        result = prompted_agents.normalize_requirement(self.REQUIREMENT, client=client)

        self.assertEqual(result["functional_scope"], fallback["functional_scope"])
        self.assertEqual(result["requirement_terms"], fallback["requirement_terms"])

    def test_rejects_out_of_range_risk_level(self) -> None:
        client = FakeClient(json.dumps({"risk_level": 1.7, "classification": "greenfield"}))
        fallback = deterministic_normalize(self.REQUIREMENT)

        result = prompted_agents.normalize_requirement(self.REQUIREMENT, client=client)

        self.assertEqual(result["risk_level"], fallback["risk_level"])
        self.assertEqual(result["classification"], "greenfield")

    def test_rejects_invalid_classification(self) -> None:
        client = FakeClient(json.dumps({"classification": "somewhere-in-between"}))
        fallback = deterministic_normalize(self.REQUIREMENT)

        result = prompted_agents.normalize_requirement(self.REQUIREMENT, client=client)

        self.assertEqual(result["classification"], fallback["classification"])

    def test_falls_back_on_malformed_json(self) -> None:
        client = FakeClient("not json at all, sorry")

        result = prompted_agents.normalize_requirement(self.REQUIREMENT, client=client)

        self.assertEqual(result, deterministic_normalize(self.REQUIREMENT))

    def test_falls_back_when_client_raises(self) -> None:
        class RaisingClient:
            def complete(self, prompt: str) -> str:
                raise RuntimeError("network is down")

        result = prompted_agents.normalize_requirement(self.REQUIREMENT, client=RaisingClient())

        self.assertEqual(result, deterministic_normalize(self.REQUIREMENT))

    def test_approval_required_is_recomputed_not_trusted_from_the_model(self) -> None:
        # The model tries to mark a brownfield, high-risk change as not requiring
        # approval. That field must never be taken from the model directly.
        client = FakeClient(
            json.dumps(
                {
                    "classification": "brownfield",
                    "risk_level": 0.95,
                    "approval_required": False,
                }
            )
        )

        result = prompted_agents.normalize_requirement(self.REQUIREMENT, client=client)

        self.assertTrue(result["approval_required"])

    def test_llm_available_reflects_the_environment_variable(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            self.assertFalse(prompted_agents.llm_available())
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            self.assertTrue(prompted_agents.llm_available())


if __name__ == "__main__":
    unittest.main()

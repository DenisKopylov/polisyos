"""Constructed provider failures cannot leak credential-bearing diagnostic bodies."""

# This standalone unittest module uses the repository's ordinary test assertions.
# ruff: noqa: S101

import importlib
import sys
import unittest


class ErrorDiagnosticTests(unittest.TestCase):
    def test_success_envelope_facts_never_copy_content(self) -> None:
        owner = importlib.import_module(
            "docs.superpowers.journals.corr-evidence.c1-capacity.error_diagnostic"
        )
        private = "synthetic-private-value"
        body = {"choices": [{"finish_reason": "stop", "message": {
            "content": private, "reasoning_content": private,
            "tool_calls": [{"function": {"arguments": private}}],
        }}]}
        facts = owner.safe_response_shape(body)
        assert private not in str(facts)
        assert facts["content_type"] == "string"
        assert facts["content_length"] == len(private)
        assert facts["content_json"] == "invalid"
        assert facts["tool_call_count"] == 1
        null = owner.safe_response_shape({"choices": [{"message": {"content": None}}]})
        missing = owner.safe_response_shape({"choices": [{"message": {}}]})
        assert null["content_type"] == "null"
        assert missing["content_type"] == "absent"

    def test_only_declared_error_facts_survive(self) -> None:
        owner = importlib.import_module(
            "docs.superpowers.journals.corr-evidence.c1-capacity.error_diagnostic"
        )
        token = "synthetic-private-value"  # noqa: S105 - deliberate synthetic echo.
        result = owner.safe_error_facts(
            429, {"error": {"code": "insufficient_quota", "message": token}},
            {"retry-after": "30", "x-request-id": token},
        )
        assert token not in str(result)
        assert result["provider_code"] == "insufficient_quota"
        assert result["retry_after_seconds"] == 30.0
        assert result["origin"] == "not_established"
        unknown = owner.safe_error_facts(429, {"error": {"code": token}}, {})
        assert token not in str(unknown)
        assert unknown["provider_code_state"] == "unrecognized"
        assert owner.safe_error_facts(429, {}, {})["provider_code_state"] == "absent"
        assert (
            owner.safe_error_facts(429, {"error": {"code": None}}, {})["provider_code_state"]
            == "null"
        )


if __name__ == "__main__":
    if "--remove-shape-redaction" in sys.argv:
        sys.argv.remove("--remove-shape-redaction")
        module = importlib.import_module(
            "docs.superpowers.journals.corr-evidence.c1-capacity.error_diagnostic"
        )
        real_shape = module.safe_response_shape

        def removed_shape(body: object) -> dict:
            return {**real_shape(body), "undeclared_raw_body": body}

        module.safe_response_shape = removed_shape
    if "--remove-redaction" in sys.argv:
        sys.argv.remove("--remove-redaction")
        module = importlib.import_module(
            "docs.superpowers.journals.corr-evidence.c1-capacity.error_diagnostic"
        )

        class AcceptEveryCode:
            def __contains__(self, value: object) -> bool:
                del value
                return True

        module.KNOWN_CODES = AcceptEveryCode()
    unittest.main(verbosity=2)

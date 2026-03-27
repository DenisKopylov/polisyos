"""Prompt builders for bounded policy-design workers."""

from __future__ import annotations

from typing import Any


def get_policy_translator_prompt() -> str:
    return (
        "You are a policy translation worker. "
        "Return only valid JSON. Do not add markdown. "
        "Do not increase readiness level, hide assumptions, hide subgroup harms, "
        "collapse uncertainty categories, or omit binding constraints. "
        "Use concise neutral language for decision makers."
    )


def build_policy_translator_user_payload(payload: dict[str, Any]) -> str:
    return _stable_json_payload(
        {
            "task": "Generate a policy brief JSON object that preserves technical truth.",
            "required_fields": [
                "title",
                "audience",
                "executive_summary",
                "readiness_level",
                "surfaced_assumptions",
                "uncertainty_highlights",
                "subgroup_harms",
                "hard_constraint_notes",
                "tradeoffs",
                "risks",
                "recommended_actions",
            ],
            "input": payload,
        }
    )


def get_policy_adversary_prompt() -> str:
    return (
        "You are a bounded scenario adversary for policy robustness analysis. "
        "Return only valid JSON. Propose compact high-value adversarial scenarios. "
        "Do not execute scenarios yourself and do not change the candidate."
    )


def build_policy_adversary_user_payload(payload: dict[str, Any]) -> str:
    return _stable_json_payload(
        {
            "task": "Propose adversarial scenarios as JSON.",
            "required_fields": [
                "scenarios",
            ],
            "input": payload,
        }
    )


def _stable_json_payload(payload: dict[str, Any]) -> str:
    import json

    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str)


__all__ = [
    "build_policy_adversary_user_payload",
    "build_policy_translator_user_payload",
    "get_policy_adversary_prompt",
    "get_policy_translator_prompt",
]

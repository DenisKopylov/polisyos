"""Predeclare at most one retry of an observed failure; export no provider body.

This outcome-selected diagnostic does not enter pilot or throughput denominators.
It observes the existing SDK transport's HTTP response hook; the same extraction
owner, prompt, typed contract and input remain in force.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import httpx

PREFIX = "docs.superpowers.journals.corr-evidence.c1-capacity."
KNOWN_CODES = frozenset({
    "insufficient_quota", "insufficient_balance", "rate_limit_exceeded", "rate_limit_error",
    "overloaded", "model_overloaded", "no_available_nodes", "no_healthy_nodes",
    "resource_exhausted", "too_many_requests", "billing_hard_limit_reached",
})


def safe_error_facts(status: int, body: object, headers: dict[str, str]) -> dict[str, Any]:
    """Retain only closed code vocabulary and finite numeric retry delay."""
    nested = body.get("error") if isinstance(body, dict) else None
    container = nested if isinstance(nested, dict) else body
    has_code = isinstance(container, dict) and "code" in container
    code = container["code"] if has_code else None
    recognized = isinstance(code, str) and code in KNOWN_CODES
    state = "recognized" if recognized else (
        "null" if has_code and code is None else "unrecognized" if has_code else "absent"
    )
    delay = None
    try:
        candidate = float(headers["retry-after"])
        if math.isfinite(candidate) and candidate >= 0:
            delay = candidate
    except (KeyError, ValueError):
        pass
    return {
        "http_status": status, "provider_code_state": state,
        "provider_code": code if recognized else None, "retry_after_seconds": delay,
        "origin": "not_established", "provider_body_retained": False,
        "code_interpretation": "provider assertion, not independent cause or origin proof",
    }


def _source_hash() -> str:
    return "sha256:" + hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def safe_response_shape(body: object) -> dict[str, Any]:
    """Describe success-envelope structure without exporting text or arbitrary keys."""
    choices = body.get("choices") if isinstance(body, dict) else None
    choice = choices[0] if isinstance(choices, list) and choices else None
    message = choice.get("message") if isinstance(choice, dict) else None
    message = message if isinstance(message, dict) else {}
    content = message.get("content")
    content_type = "absent" if "content" not in message else (
        "null" if content is None else "string" if isinstance(content, str) else "other"
    )
    syntax, position, root_type = "not_text", None, None
    if isinstance(content, str):
        try:
            parsed = json.loads(content)
            syntax = "valid"
            root_type = (
                "object" if isinstance(parsed, dict) else "array" if isinstance(parsed, list)
                else "string" if isinstance(parsed, str) else "scalar"
            )
        except json.JSONDecodeError as exc:
            syntax, position = "invalid", exc.pos
    calls = message.get("tool_calls")
    reasoning = message.get("reasoning_content")
    finish = choice.get("finish_reason") if isinstance(choice, dict) else None
    return {
        "choice_count": len(choices) if isinstance(choices, list) else None,
        "content_type": content_type,
        "content_length": len(content) if isinstance(content, str) else None,
        "content_json": syntax, "json_error_position": position, "json_root_type": root_type,
        "content_has_code_fence": "```" in content if isinstance(content, str) else None,
        "content_has_object_braces": (
            "{" in content and "}" in content if isinstance(content, str) else None
        ),
        "tool_call_count": len(calls) if isinstance(calls, list) else None,
        "reasoning_length": len(reasoning) if isinstance(reasoning, str) else None,
        "finish_reason": finish if isinstance(finish, str) and finish in {
            "stop", "length", "tool_calls", "content_filter",
        }
        else "unrecognized_or_absent",
        "raw_content_retained": False,
    }


def declare(slug: str) -> Path:
    """Freeze the first ordinal failed request as a diagnostic, never a new sample."""
    common = importlib.import_module(PREFIX + "capacity_common")
    runner = importlib.import_module(PREFIX + "throughput_runner")
    plan_path = common.EVIDENCE / f"2026-09-09-{slug}-throughput-declaration.json"
    plan = runner.load_plan(plan_path)
    previous = Path(".tmp/corr-c1-capacity/throughput") / slug
    report_path = previous / "throughput-report.json"
    if not report_path.exists():
        raise ValueError("diagnostic_requires_terminal_experiment")
    selected = None
    for index, level in enumerate(plan["levels"]):
        level_root = previous / f"concurrency-{level['concurrency']}"
        if not level_root.exists():
            continue
        members = runner.level_members(plan, index)
        rows = runner.read_level_rows(level_root, members)
        for row in rows:
            if row["status"] == "failed":
                outcome_path = level_root / "outcomes" / f"{row['ordinal']:03}.json"
                outcome = json.loads(outcome_path.read_text())
                observation = json.loads(Path(outcome["provider_observation_path"]).read_text())
                selected = {
                    "member": members[row["ordinal"]], "original_outcome_path": str(outcome_path),
                    "original_outcome_hash": common.digest(outcome),
                    "original_prompt_hash": observation["prompt_hash"],
                    "original_error_kind": row["error_kind"],
                }
                break
        if selected is not None:
            break
    if selected is None:
        raise ValueError("diagnostic_requires_observed_failure")
    path = common.EVIDENCE / f"2026-09-09-{slug}-error-diagnostic-v2-declaration.json"
    common.SafeJsonWriter(common.load_credential())(path, common.seal({
        "schema_version": "corr.provider_error_diagnostic_declaration.v2",
        "declared_at": datetime.now(UTC).isoformat(), "synthetic": False,
        "authority_status": "candidate_measurement", "full_pass_authorized": False,
        "throughput_declaration_path": str(plan_path),
        "throughput_declaration_hash": plan["content_hash"],
        "helper_source_hash": _source_hash(), "selection": selected,
        "max_http_attempts": 1, "retries": 0, "model_id": plan["model_id"],
        "base_url": plan["base_url"], "purpose": "one_observed_failure_retry_diagnostic",
        "selection_rule": "first failed ordinal in earliest executed level; outcome-selected",
        "scope": "not a pilot, throughput, quality, calibration or representativeness estimate",
        "error_body_policy": "closed code vocabulary and numeric Retry-After only; no raw body",
        "success_body_policy": "closed structural types, lengths and JSON syntax only; no raw text",
        "output_root": f".tmp/corr-c1-capacity/error-diagnostic/{slug}",
    }))
    return path


async def run(path: Path) -> dict[str, Any]:
    """Execute the separately committed single retry with no body logging."""
    common = importlib.import_module(PREFIX + "capacity_common")
    runner = importlib.import_module(PREFIX + "throughput_runner")
    probe = importlib.import_module(PREFIX + "contract_probe")
    declaration = runner._committed(path)
    if declaration["helper_source_hash"] != _source_hash():
        raise ValueError("diagnostic_helper_source_changed")
    plan = runner.load_plan(Path(declaration["throughput_declaration_path"]))
    if plan["content_hash"] != declaration["throughput_declaration_hash"]:
        raise ValueError("diagnostic_model_configuration_changed")
    selection = declaration["selection"]
    original = json.loads(Path(selection["original_outcome_path"]).read_text())
    if common.digest(original) != selection["original_outcome_hash"]:
        raise ValueError("diagnostic_prior_outcome_changed")
    source = importlib.import_module(PREFIX + "throughput_declaration")
    work = source.read_selected_work(Path(plan["source_path"]), selection["member"])
    output = Path(declaration["output_root"])
    output.mkdir(parents=True, exist_ok=False)
    from polisyos.data_forge.domains.academic.batch.article_extractor import (
        ExtractorStats,
        PolicyArticleExtractor,
    )
    from polisyos.data_forge.domains.academic.batch.reextraction_transport import (
        ExtractionRequestError,
        SDKExtractionTransport,
    )
    from polisyos.data_forge.domains.academic.knowledge.variable_canonizer import VariableCanonizer
    from polisyos.ir import ArticleExtractionResult

    facts = []

    async def observe(response: httpx.Response) -> None:
        if len(facts) >= 1:
            raise ValueError("diagnostic_http_attempt_budget_exceeded")
        await response.aread()
        try:
            body = response.json()
        except (ValueError, UnicodeDecodeError):
            body = None
        facts.append({
            **safe_error_facts(response.status_code, body, dict(response.headers)),
            "success_shape": safe_response_shape(body) if not response.is_error else None,
        })

    async with SDKExtractionTransport(
        api_key=common.load_credential(), base_url=plan["base_url"], model_id=plan["model_id"],
        output_root=output, timeout_seconds=plan["timeout_seconds"],
        max_completion_tokens=plan["max_completion_tokens"],
        prompt_estimator=common.local_estimator,
    ) as transport:
        # Instrument the actual default HTTPX client; no replacement client or parser.
        transport._client._client.event_hooks["response"].append(observe)
        bound = transport.bind({
            "attempt_id": "diagnostic", "work_id": work["id"], "phase": "extraction",
            "campaign_id": declaration["content_hash"], "synthetic": False,
            "input_hash": selection["member"]["abstract_content_hash"],
        })

        class PromptBound:
            synthetic = False

            async def chat(self, *, model: str, temperature: float, prompt: str) -> tuple:
                prompt_hash = "sha256:" + hashlib.sha256(prompt.encode()).hexdigest()
                if prompt_hash != selection["original_prompt_hash"]:
                    raise ValueError("diagnostic_original_prompt_changed")
                return await bound.chat(model=model, temperature=temperature, prompt=prompt)

        client = probe._ObservedClient(PromptBound())
        extractor = PolicyArticleExtractor(
            screening_model=plan["model_id"], extraction_model=plan["model_id"], max_concurrent=1,
            canonizer=VariableCanonizer(), gonka_client=client, fulltext_timeout_seconds=3,
            cache_path=output / "unused-cache.jsonl", preserve_source_presence=True,
        )
        result, error = None, None
        try:
            result = await extractor._extract(
                work, work["abstract"], "abstract_fallback", ExtractorStats(),
            )
        except ExtractionRequestError as exc:
            error = exc.kind
        observation = json.loads((output / "provider_attempts/diagnostic.json").read_text())
        report = {
            "schema_version": "corr.provider_error_diagnostic.v2", "synthetic": False,
            "authority_status": "candidate_measurement",
            "declaration_hash": declaration["content_hash"],
            "actual_http_attempts": client.count, "response_facts": facts,
            "typed_contract_satisfied": isinstance(result, ArticleExtractionResult),
            "error_kind": error, "provider_observation": observation,
            "parsed_response": client.response,
            "scope": declaration["scope"], "raw_provider_error_body_retained": False,
        }
        report_path = common.EVIDENCE / (path.stem.replace("declaration", "result") + ".json")
        transport.safe_write_json(report_path, report)
    return {"actual_http_attempts": client.count, "response_facts": facts, "error_kind": error}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="mode", required=True)
    command = commands.add_parser("declare")
    command.add_argument("slug", choices=["deepseek", "minimax"])
    command = commands.add_parser("run")
    command.add_argument("declaration", type=Path)
    args = parser.parse_args()
    result = (
        {"declaration": str(declare(args.slug))}
        if args.mode == "declare" else asyncio.run(run(args.declaration))
    )
    common = importlib.import_module(PREFIX + "capacity_common")
    print(common.SafeJsonWriter(common.load_credential()).encode(result))  # noqa: T201


if __name__ == "__main__":
    main()

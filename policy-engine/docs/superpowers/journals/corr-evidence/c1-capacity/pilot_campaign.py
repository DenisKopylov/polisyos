"""Bind and run only the unchanged six-input pilot through durable extraction."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib
import json
import subprocess
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from polisyos.data_forge.domains.academic.batch.reextraction_campaign import (
    CampaignPlan,
    campaign_owner_projection,
    run_campaign,
)
from polisyos.data_forge.domains.academic.batch.reextraction_transport import (
    OBSERVATION_EPOCH,
    SafeJsonWriter,
    SDKExtractionTransport,
)

common = importlib.import_module(
    "docs.superpowers.journals.corr-evidence.c1-capacity.capacity_common"
)
probe = importlib.import_module(
    "docs.superpowers.journals.corr-evidence.c1-capacity.contract_probe"
)


def _committed(path: Path) -> None:
    if path.is_absolute() or path.parent != common.EVIDENCE:
        raise ValueError("pilot_binding_path_invalid")
    actual = subprocess.check_output([  # noqa: S603 - fixed read-only git invocation.
        "/usr/bin/git", "show", "HEAD:policy-engine/" + path.as_posix(),
    ])
    if actual != path.read_bytes():
        raise ValueError("pilot_binding_not_committed_before_call")


def declare(path: Path, contract: Path) -> Path:
    """Freeze exact owner inputs and implementation before the six-input pilot."""
    declaration, works = probe.declared_inputs(path)
    if declaration["purpose"] != "frozen_six_model_comparison_and_token_pilot" or len(works) != 6:
        raise ValueError("pilot_declaration_scope_invalid")
    verdict = json.loads(contract.read_text())
    _committed(contract)
    if verdict["contract_satisfied"] is not True or verdict["model_id"] != declaration["model_id"]:
        raise ValueError("pilot_model_contract_not_established")
    owner = campaign_owner_projection()
    frame_digest = "sha256:" + hashlib.sha256(
        "".join(common.digest(work) + "\n" for work in works).encode()
    ).hexdigest()
    slug = "deepseek" if declaration["model_id"].startswith("deepseek") else "minimax"
    plan = CampaignPlan(
        campaign_id="corr-frozen-six-" + slug + "-2026-09-09",
        synthetic=False, input_count=6, input_digest=frame_digest,
        provider_profile_hash=declaration["content_hash"],
        screening_model=declaration["model_id"], extraction_model=declaration["model_id"],
        concurrency=1, queue_capacity=2, max_attempts=18, max_attempts_per_phase=1,
        owner_source_hash=owner["content_hash"],
    )
    output = common.EVIDENCE / ("2026-09-09-" + slug + "-pilot-execution-binding.json")
    SafeJsonWriter(common.load_credential())(output, common.seal({
        "schema_version": "corr.pilot_execution_binding.v1", "synthetic": False,
        "authority_status": "candidate_only", "declared_at": datetime.now(UTC).isoformat(),
        "pilot_declaration_path": str(path), "pilot_declaration_hash": declaration["content_hash"],
        "contract_verdict_path": str(contract), "contract_verdict_hash": common.digest(verdict),
        "campaign_plan": asdict(plan), "owner_projection": owner,
        "transport_observation_epoch": OBSERVATION_EPOCH,
        "input_selection_change": "none", "full_pass_authorized": False,
        "resource_profile_limits": {
            "max_wall_seconds": 3600, "max_rss_bytes": 3 * 1024**3,
            "max_disk_write_bytes": 2 * 1024**3, "sample_interval_seconds": 0.25,
            "shutdown_grace_seconds": 2.0,
        },
        "output_root": ".tmp/corr-c1-capacity/pilots/" + slug,
        "pilot_scope": "six frozen inputs; no throughput samples",
    }))
    return output


async def run(path: Path) -> dict[str, Any]:
    """Run or resume the content-bound pilot without replacing any input."""
    _committed(path)
    binding = common.read_sealed(path)
    if binding["full_pass_authorized"] is not False:
        raise ValueError("pilot_full_pass_not_authorized")
    if datetime.fromisoformat(binding["declared_at"]) >= datetime.now(UTC):
        raise ValueError("pilot_binding_not_before_call")
    declaration, works = probe.declared_inputs(Path(binding["pilot_declaration_path"]))
    if declaration["content_hash"] != binding["pilot_declaration_hash"] or len(works) != 6:
        raise ValueError("pilot_input_scope_mismatch")
    verdict_path = Path(binding["contract_verdict_path"])
    _committed(verdict_path)
    verdict = json.loads(verdict_path.read_text())
    if common.digest(verdict) != binding["contract_verdict_hash"]:
        raise ValueError("pilot_contract_verdict_changed")
    plan = CampaignPlan(**binding["campaign_plan"])
    root = Path(binding["output_root"])
    async with SDKExtractionTransport(
        api_key=common.load_credential(), base_url=declaration["base_url"],
        model_id=declaration["model_id"], output_root=root,
        timeout_seconds=declaration["timeout_seconds"],
        max_completion_tokens=declaration["max_completion_tokens"],
        prompt_estimator=common.local_estimator,
    ) as transport:
        result = await run_campaign(
            plan, works=iter(works), output_root=root, client_factory=transport.bind,
            safe_write_json=transport.safe_write_json,
        )
    return {"binding_path": str(path), "binding_hash": binding["content_hash"],
            "model_id": declaration["model_id"], "output_root": str(root), "result": result}


def main() -> int:
    """Declare without calls, or execute the already committed six-input plan."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="mode", required=True)
    declare_command = commands.add_parser("declare")
    declare_command.add_argument("pilot_declaration", type=Path)
    declare_command.add_argument("contract_verdict", type=Path)
    run_command = commands.add_parser("run")
    run_command.add_argument("binding", type=Path)
    args = parser.parse_args()
    if args.mode == "declare":
        output: object = {"execution_binding": str(declare(
            args.pilot_declaration, args.contract_verdict,
        ))}
    else:
        output = asyncio.run(run(args.binding))
    sys.stdout.write(SafeJsonWriter(common.load_credential()).encode(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

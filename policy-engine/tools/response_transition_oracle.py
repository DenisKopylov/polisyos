"""Independent OPS-R5 transition oracle; no PolicyOS runtime imports are permitted.

This tools-owned semantic implementation uses the standard-library JSON decoder.
The runtime uses Pydantic-core. Only raw bytes cross their interpretation boundary.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

OWNER = "tools.response_transition_oracle"
SPEC = ("AUD-F06:FCT-01", "AUD-F06:FCT-02", "AUD-F06:FCT-03", "AUD-F06:FCT-04", "AUD-F08")


def decode_packet(raw: bytes) -> dict[str, Any]:
    """Decode raw corpus bytes independently, rejecting duplicate JSON keys."""

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("oracle_duplicate_key")
            result[key] = value
        return result

    value = json.loads(raw, object_pairs_hook=unique)
    if not isinstance(value, dict) or set(value) != {"version", "packets"}:
        raise ValueError("oracle_packet_shape")
    if value["version"] != "response-corpus.v1" or not isinstance(value["packets"], list):
        raise ValueError("oracle_packet_version")
    for packet in value["packets"]:
        if not isinstance(packet, dict) or not packet.get("events"):
            raise ValueError("oracle_packet_empty")
        for event in packet["events"]:
            for axis, size in (("E", 5), ("X", 5), ("V", 5), ("C", 4)):
                if event["requested"][axis] not in [f"{axis}{n}" for n in range(size)]:
                    raise ValueError("oracle_factor_unknown")
    return value


def expectation(event: dict[str, Any]) -> dict[str, Any]:
    """Derive candidate-only conformance facts from named research invariants."""
    target = event["requested"]
    product = []
    if target["V"] == "V2" and target["C"] == "C0":
        product.append("FCT-01")
    if (target["E"], target["X"], target["C"]) == ("E4", "X4", "C0") and event.get(
        "claim_depends_on_unacceptable_basis", True
    ):
        product.append("FCT-02")
    if target["V"] == "V4" and target["X"] == "X0":
        product.append("FCT-03")
    if target["V"] == "V3" and target["C"] == "C0":
        product.append("redesign_claim_inheritance")
    reasons = list(product)
    observation = event["observation"]
    if observation["maturity"] != "mature":
        reasons.append("observation_not_mature")
    if observation["health"] != "valid":
        reasons.append("measurement_not_valid")
    if observation["expected_denominator"] != observation["observed_denominator"]:
        reasons.append("denominator_changed")
    if observation.get("subgroup_blocked", False):
        reasons.append("subgroup_guardrail_block")
    if not event.get("charter_ref"):
        reasons.append("transition_charter_missing")
    high_harm = event.get("waiting_harm", "unknown") == "high"
    reasons.append("protective_containment_required" if high_harm else "investigation_only")
    if event.get("premature_loss", "unknown") == "high":
        reasons.append("premature_action_loss_unresolved")
    if event.get("reversibility", "unknown") == "irreversible":
        reasons.append("irreversible_response_review")
    if event.get("blast_radius", "unknown") == "wide":
        reasons.append("wide_blast_radius_review")
    if event.get("learning_requested", False):
        reasons.append("posterior_learning_not_admitted")
    if event.get("world_write_requested", False):
        reasons.append("world_write_not_admitted")
    if (
        event["operation"] in {"adjust_implementation", "partial_reissue", "redesign", "terminate"}
        and event["movement"] == "diagnosis_unresolved"
    ):
        reasons.append("diagnosis_unresolved_for_action")
    reasons.append(
        "owner_label_not_appointment"
        if event.get("declared_owner")
        else "institutional_signer_not_established"
    )
    if event["operation"] == "restart":
        reasons.append(
            "restart_candidate_unverified"
            if event.get("restart_candidate_ref")
            else "alert_disappearance_not_restart"
        )
    version_changed = bool(
        event.get("requested_version")
        and event["requested_version"] != event["intervention_version"]
    )
    epoch_changed = bool(
        event.get("requested_measurement_epoch")
        and event["requested_measurement_epoch"] != event["measurement_epoch"]
    )
    version_reuse = (version_changed or epoch_changed) and target["C"] == "C0"
    if version_reuse:
        reasons.append("version_identity_reused")
    if target["C"] == "C3" and target["X"] != "X4":
        reasons.append(
            "external_continuation_basis_unverified"
            if event.get("external_continuation_ref")
            else "external_continuation_basis_not_established"
        )
    if event.get("legal_deadline") and datetime.fromisoformat(
        event["valid_at"]
    ) >= datetime.fromisoformat(event["legal_deadline"]):
        reasons.append("legal_review_clock_elapsed")
    if event.get("execution_candidate_ref"):
        reasons.append("execution_receipt_unverified")
    expansion = int(target["X"][1:]) < int(event["current"]["X"][1:])
    if expansion:
        reasons.append("exposure_expansion_without_restart")
    admissible = (
        not product and not version_reuse and not expansion and event["operation"] != "restart"
    )
    return {
        "product_violations": product,
        "reasons": reasons,
        "candidate_admissible": admissible,
        "custody_factors": target if admissible else event["current"],
        "protective_containment_required": high_harm,
        "conservative_posture": "no_authority_expansion",
        "execution_authorized": False,
        "external_executed": False,
        "posterior_learning_allowed": False,
        "world_write_allowed": False,
        "claim_dependent_continuation": False,
        "external_continuation_observed": bool(event.get("external_continuation_ref")),
    }


def seal_material(root: Path) -> None:
    """Seal research-derived expectations before runtime implementation tuning."""
    raw = (root / "packets.json").read_bytes()
    corpus = decode_packet(raw)
    lines = [
        'version = "response-oracle.v1"',
        f'owner = "{OWNER}"',
        f'packet_sha256 = "{hashlib.sha256(raw).hexdigest()}"',
        f'oracle_source_sha256 = "{hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}"',
    ]
    for packet in corpus["packets"]:
        for offset, event in enumerate(packet["events"]):
            payload = json.dumps(expectation(event), sort_keys=True, separators=(",", ":"))
            lines.extend(
                [
                    "",
                    "[[expectations]]",
                    f'scenario_id = "{packet["scenario_id"]}"',
                    f"offset = {offset}",
                    f"payload = {json.dumps(payload)}",
                    f'sha256 = "{hashlib.sha256(payload.encode()).hexdigest()}"',
                ]
            )
    (root / "oracle.toml").write_text("\n".join(lines) + "\n")

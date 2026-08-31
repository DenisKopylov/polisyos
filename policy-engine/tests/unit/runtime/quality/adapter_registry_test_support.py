"""Test-only data mutation for verified post-G0 adapter admission."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
BASE_REGISTRY = (
    REPO_ROOT / "architecture/policy_design_case/layer3_g3_adapter_contract_registry.toml"
)
NEW_ADAPTER_ID = "layer3_g3_proof_record_to_audit_candidate"


def mutated_registry(
    path: Path,
    *,
    include_capability: bool = True,
    valid_until: str = "2099-01-01T00:00:00+00:00",
) -> Path:
    """Append one otherwise unknown adapter row without changing Python source."""

    capability = (
        f"""

[adapter_paths.capability_admission]
capability_ref = "capability:method:g3-proof-audit-candidate"
resource_kind = "method"
capability_purpose = "review_capability_candidates"
label = "G3 proof audit projection"
description = "Semantically preserved projection from a proof record into the G3 audit surface."
construct_refs = ["construct:proof-carrying-analytics", "construct:audit-projection"]
operation_id = "layer3.g3.project_proof_audit_candidate"
operation_kind = "semantic_identity_projection"
consumes_ports = ["layer3.g3.proof_record"]
produces_ports = ["layer3.g3.audit_surface"]
producer_ref = "runtime-quality:verified-adapter-admission-producer"
evidence_refs = ["repo://architecture/policy_design_case/layer3_g3_adapter_contract_registry.toml"]
valid_from = "2026-08-30T00:00:00+00:00"
valid_until = "{valid_until}"
"""
        if include_capability
        else ""
    )
    path.write_text(
        BASE_REGISTRY.read_text(encoding="utf-8")
        + f"""

[[adapter_paths]]
id = "{NEW_ADAPTER_ID}"
source_surface = "layer3.g3.proof_record"
target_surface = "layer3.g3.audit_surface"
field_families = [
  "runtime_refs",
  "final_claims",
  "source_data_context",
  "legal_context",
  "foundry_method_context",
  "scorecard_identity_and_gates",
  "approval_readiness_public_status",
  "mode_and_fallback_records",
]
required_semantic_fields = [
  "status",
  "provenance",
  "owner",
  "schema",
  "rule_version",
  "lineage",
  "tenant",
  "time_context",
  "jurisdiction",
  "source_family",
  "method_expectation",
  "claim_sets",
  "rights",
  "freshness",
  "contamination",
  "authority_boundary",
]
blocker_code = "layer3_g3_adapter_semantic_loss"
owner = "team-runtime-quality"
next_diagnostic_command = "uv run pytest tests/unit/runtime/quality/test_adapter_registry_free_growth.py -q"
{capability}
""",
        encoding="utf-8",
    )
    return path

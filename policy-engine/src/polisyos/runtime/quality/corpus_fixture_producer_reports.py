"""Corpus-grounded stub producer reports for W12.D validation mode."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

CORPUS_STUB_SCHEMA_VERSION = "policyos.runtime.producer_pipeline.corpus_stub.v1"
_SELECTED = frozenset({"selected", "pass", "satisfied"})
_LIMITED = frozenset({"limited", "publish-with-limitation", "downgraded"})
_BLOCKED = frozenset({"blocked", "missing", "typed_blocker", "unsupported"})


def load_corpus_stub_responses(
    *,
    stub_dir: str | Path,
    case_id: str,
) -> dict[str, Any]:
    """Load one per-case corpus stub response file."""

    path = Path(stub_dir) / f"{_slug(case_id)}.producer_stubs.json"
    if not path.exists():
        raise FileNotFoundError(f"corpus producer stub missing for case_id={case_id}: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if str(payload.get("case_id") or "") != case_id:
        raise ValueError(f"corpus producer stub case_id mismatch: {path}")
    return dict(payload)


def corpus_stub_authority_boundary(
    responses: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return the authority boundary for corpus stub mode."""

    payload = dict(responses or {})
    return {
        "schema_version": CORPUS_STUB_SCHEMA_VERSION,
        "mode": "corpus_stub",
        "case_id": payload.get("case_id"),
        "max_authority_posture": str(payload.get("max_authority_posture") or "governed-pilot"),
        "authoritative_for": [
            "corpus_validation_fixture",
            "compiler_path_useful_design_probe",
        ],
        "may_not_use_for": [
            "production_closeout_authority",
            "producer_domain_truth",
            "claim_evidence_authority",
            "public_projection_authority",
        ],
        "surface_state": "surface_out_of_scope",
        "owner": str(payload.get("owner") or "team-evaluation"),
    }


def build_corpus_stub_adapter_reports(
    *,
    run_id: str,
    responses: Mapping[str, Any],
    data_requirement_specs: Sequence[Any],
    legal_authority_requirement_specs: Sequence[Any],
    method_validity_requirement_specs: Sequence[Any],
    scholar_support_requirement_specs: Sequence[Any],
    participation_provenance_requirement_specs: Sequence[Any],
    capability_index_ref: str | None = None,
    construct_registry_ref: str | None = None,
    authority_composition_rule_ref: str | None = None,
) -> dict[str, dict[str, Any]]:
    """Build adapter-report shapes consumed by the W7.F binding translators."""

    binding_context = _binding_context(
        capability_index_ref=capability_index_ref,
        construct_registry_ref=construct_registry_ref,
        authority_composition_rule_ref=authority_composition_rule_ref,
    )
    return {
        "fabric": _fabric_report(
            responses=responses,
            specs=data_requirement_specs,
            binding_context=binding_context,
        ),
        "lex": _lex_report(
            responses=responses,
            specs=legal_authority_requirement_specs,
            binding_context=binding_context,
        ),
        "foundry": _foundry_report(
            responses=responses,
            specs=method_validity_requirement_specs,
            binding_context=binding_context,
        ),
        "scholar": _scholar_report(
            responses=responses,
            specs=scholar_support_requirement_specs,
            run_id=run_id,
            binding_context=binding_context,
        ),
        "participation": _participation_report(
            responses=responses,
            specs=participation_provenance_requirement_specs,
            binding_context=binding_context,
        ),
    }


def _fabric_report(
    *,
    responses: Mapping[str, Any],
    specs: Sequence[Any],
    binding_context: Mapping[str, str],
) -> dict[str, Any]:
    bindings = []
    for spec in specs:
        requirement_id = _requirement_id(spec)
        status = _status_for(responses, "fabric", requirement_id)
        bindings.append(
            {
                **_capability_fields(
                    component="fabric",
                    requirement_id=requirement_id,
                    spec=spec,
                    binding_context=binding_context,
                ),
                "requirement_id": requirement_id,
                "data_requirement_id": requirement_id,
                "binding_status": "blocked" if status in _BLOCKED else "selected",
                "candidate_ref": f"corpus-stub:fabric:{_slug(requirement_id)}",
                "source_family": _first_required_family(spec) or "corpus_stub_source",
                "reason_code": f"corpus_stub_{status}",
            }
        )
    return {
        "schema_version": "policyos.fabric.source_contract_requirement_bindings.v1",
        "status": _status_from_rows(bindings, key="binding_status"),
        "source_contract_bindings": bindings,
        "summary": _summary(bindings, key="binding_status"),
    }


def _lex_report(
    *,
    responses: Mapping[str, Any],
    specs: Sequence[Any],
    binding_context: Mapping[str, str],
) -> dict[str, Any]:
    records = []
    for spec in specs:
        requirement_id = _requirement_id(spec)
        status = _status_for(responses, "lex", requirement_id)
        records.append(
            {
                **_capability_fields(
                    component="lex",
                    requirement_id=requirement_id,
                    spec=spec,
                    binding_context=binding_context,
                ),
                "legal_authority_record_id": f"corpus-stub-lex-{_slug(requirement_id)}",
                "legal_requirement_ref": requirement_id,
                "legal_admissibility_grade": "blocked"
                if status in _BLOCKED
                else "proxy_with_limitation"
                if status in _LIMITED
                else "admissible",
                "norm_ref": f"corpus-stub:lex:{_slug(requirement_id)}",
            }
        )
    return {
        "schema_version": "policyos.lex.legal_authority_report.v1",
        "status": _status_from_legal(records),
        "legal_authority_records": records,
    }


def _foundry_report(
    *,
    responses: Mapping[str, Any],
    specs: Sequence[Any],
    binding_context: Mapping[str, str],
) -> dict[str, Any]:
    selected = []
    issues = []
    for spec in specs:
        requirement_id = _requirement_id(spec)
        status = _status_for(responses, "foundry", requirement_id)
        if status in _BLOCKED:
            issues.append(
                {
                    "code": "corpus_stub_method_blocked",
                    "method_requirement_ref": requirement_id,
                }
            )
            continue
        selected.append(
            {
                **_capability_fields(
                    component="foundry",
                    requirement_id=requirement_id,
                    spec=spec,
                    binding_context=binding_context,
                ),
                "method_id": f"corpus-stub:foundry:{_slug(requirement_id)}",
                "method_requirement_refs": [requirement_id],
                "selection_status": status,
            }
        )
    return {
        "schema_version": "policyos.foundry.method_requirement_selection.v1",
        "status": "blocked" if issues else "pass",
        "selected_methods": selected,
        "rejected_methods": [],
        "issues": issues,
    }


def _scholar_report(
    *,
    responses: Mapping[str, Any],
    specs: Sequence[Any],
    run_id: str,
    binding_context: Mapping[str, str],
) -> dict[str, Any]:
    support_links = []
    blockers = []
    for spec in specs:
        requirement_id = _requirement_id(spec)
        status = _status_for(responses, "scholar", requirement_id)
        if status in _BLOCKED:
            blockers.append(
                {
                    "code": "corpus_stub_scholar_blocked",
                    "requirement_id": requirement_id,
                }
            )
            continue
        support_links.append(
            {
                **_capability_fields(
                    component="scholar",
                    requirement_id=requirement_id,
                    spec=spec,
                    binding_context=binding_context,
                ),
                "requirement_id": requirement_id,
                "support_link_ref": f"corpus-stub:scholar:{_slug(requirement_id)}",
                "support_status": status,
            }
        )
    return {
        "schema_version": "policyos.scholar.academic_evidence_report.v1",
        "status": "blocked" if blockers else "pass",
        "scholar_evidence_ref": f"corpus-stub:scholar:{_slug(run_id)}",
        "support_links": support_links,
        "literature_deficit_blockers": blockers,
        "summary": {
            "support_link_count": len(support_links),
            "blocked": len(blockers),
        },
    }


def _participation_report(
    *,
    responses: Mapping[str, Any],
    specs: Sequence[Any],
    binding_context: Mapping[str, str],
) -> dict[str, Any]:
    evaluations = []
    for spec in specs:
        requirement_id = _requirement_id(spec)
        status = _status_for(responses, "participation", requirement_id)
        evaluations.append(
            {
                **_capability_fields(
                    component="participation",
                    requirement_id=requirement_id,
                    spec=spec,
                    binding_context=binding_context,
                ),
                "requirement_id": requirement_id,
                "status": "blocked"
                if status in _BLOCKED
                else "downgraded"
                if status in _LIMITED
                else "satisfied",
                "participation_ref": f"corpus-stub:participation:{_slug(requirement_id)}",
                "downgrade_reason": "corpus_stub_limited" if status in _LIMITED else None,
                "blocker_code": "corpus_stub_participation_blocked"
                if status in _BLOCKED
                else None,
            }
        )
    return {
        "schema_version": "policyos.participation_requirement.pipeline_evaluations.v1",
        "status": "blocked"
        if any(row["status"] == "blocked" for row in evaluations)
        else "pass",
        "evaluations": evaluations,
        "summary": {
            "satisfied": sum(1 for row in evaluations if row["status"] == "satisfied"),
            "downgraded": sum(1 for row in evaluations if row["status"] == "downgraded"),
            "blocked": sum(1 for row in evaluations if row["status"] == "blocked"),
        },
    }


def _status_for(responses: Mapping[str, Any], component: str, requirement_id: str) -> str:
    row = responses.get(component)
    raw = row.get(requirement_id) or row.get("*") if isinstance(row, Mapping) else None
    status = str(raw or "blocked").strip().casefold()
    if status in _SELECTED or status in _LIMITED or status in _BLOCKED:
        return status
    return "blocked"


def _requirement_id(spec: object) -> str:
    payload = spec if isinstance(spec, Mapping) else getattr(spec, "model_dump", lambda **_: {})()
    if not isinstance(payload, Mapping):
        return "requirement:unknown"
    return str(payload.get("requirement_id") or "requirement:unknown")


def _first_required_family(spec: object) -> str | None:
    payload = spec if isinstance(spec, Mapping) else getattr(spec, "model_dump", lambda **_: {})()
    if not isinstance(payload, Mapping):
        return None
    families = payload.get("required_data_families")
    if isinstance(families, Sequence) and not isinstance(families, str):
        return next((str(item) for item in families if str(item).strip()), None)
    return str(families).strip() if families else None


def _capability_fields(
    *,
    component: str,
    requirement_id: str,
    spec: object,
    binding_context: Mapping[str, str],
) -> dict[str, str]:
    capability_ref = f"capability:corpus_stub:{component}:{_slug(requirement_id)}"
    return {
        "capability_ref": capability_ref,
        "construct_ref": _construct_ref(spec, requirement_id=requirement_id),
        "capability_index_ref": binding_context["capability_index_ref"],
        "construct_registry_ref": binding_context["construct_registry_ref"],
        "authority_composition_rule_ref": binding_context[
            "authority_composition_rule_ref"
        ],
    }


def _binding_context(
    *,
    capability_index_ref: str | None,
    construct_registry_ref: str | None,
    authority_composition_rule_ref: str | None,
) -> dict[str, str]:
    return {
        "capability_index_ref": (
            str(capability_index_ref).strip()
            if str(capability_index_ref or "").strip()
            else "capability-index:corpus-stub"
        ),
        "construct_registry_ref": (
            str(construct_registry_ref).strip()
            if str(construct_registry_ref or "").strip()
            else "construct-registry:v1"
        ),
        "authority_composition_rule_ref": (
            str(authority_composition_rule_ref).strip()
            if str(authority_composition_rule_ref or "").strip()
            else "capability-authority-v1.0"
        ),
    }


def _construct_ref(spec: object, *, requirement_id: str) -> str:
    payload = spec if isinstance(spec, Mapping) else getattr(spec, "model_dump", lambda **_: {})()
    if isinstance(payload, Mapping):
        metadata = payload.get("metadata")
        if isinstance(metadata, Mapping):
            binding = metadata.get("capability_binding")
            if isinstance(binding, Mapping) and str(binding.get("construct_ref") or "").strip():
                return str(binding["construct_ref"]).strip()
            if str(metadata.get("construct_ref") or "").strip():
                return str(metadata["construct_ref"]).strip()
        for key in ("construct_ref", "target_construct_ref"):
            if str(payload.get(key) or "").strip():
                return str(payload[key]).strip()
        refs = payload.get("construct_refs") or payload.get("required_construct_refs")
        if isinstance(refs, Sequence) and not isinstance(refs, str):
            for ref in refs:
                if str(ref or "").strip():
                    return _prefixed_construct_ref(str(ref).strip())
    return f"construct:corpus_stub:{_slug(requirement_id)}"


def _prefixed_construct_ref(value: str) -> str:
    return value if value.startswith("construct:") else f"construct:{value}"


def _status_from_rows(rows: Sequence[Mapping[str, Any]], *, key: str) -> str:
    return "blocked" if any(str(row.get(key)) == "blocked" for row in rows) else "pass"


def _status_from_legal(records: Sequence[Mapping[str, Any]]) -> str:
    return (
        "blocked"
        if any(str(row.get("legal_admissibility_grade")) == "blocked" for row in records)
        else "pass"
    )


def _summary(rows: Sequence[Mapping[str, Any]], *, key: str) -> dict[str, int]:
    return {
        "selected": sum(1 for row in rows if str(row.get(key)) == "selected"),
        "blocked": sum(1 for row in rows if str(row.get(key)) == "blocked"),
    }


def _slug(value: object) -> str:
    text = str(value).strip().casefold()
    return "".join(char if char.isalnum() or char in "._-" else "-" for char in text).strip("-")


__all__ = [
    "CORPUS_STUB_SCHEMA_VERSION",
    "build_corpus_stub_adapter_reports",
    "corpus_stub_authority_boundary",
    "load_corpus_stub_responses",
]

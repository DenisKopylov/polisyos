#!/usr/bin/env python3
"""Validate and persist the Layer 3 G0 grounding readiness bundle."""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from polisyos.runtime.quality import layer3_grounding_inventory as g0
from tools.lib.fs import atomic_write_text

REPO_ROOT = Path(__file__).resolve().parents[3]
POLICY_DESIGN_CASE_DIR = Path("architecture/policy_design_case")
READINESS_MANIFEST_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g0_readiness_manifest.json"
ADR_PATH = Path("docs/adr/0175-layer3-grounding-subordination-discipline.md")

CAPABILITY_DATA_INVENTORY_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_g0_capability_data_inventory.json"
)
TRIAGE_REGISTRY_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g0_triage_registry.json"
PORT_MAP_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g0_port_map.json"
ADAPTER_ADMISSION_REGISTRY_PATH = (
    POLICY_DESIGN_CASE_DIR / "layer3_adapter_admission_registry.json"
)
DATA_ASSET_PORTS_PATH = POLICY_DESIGN_CASE_DIR / "layer3_data_asset_ports.json"
CONFORMANCE_HARNESS_PATH = POLICY_DESIGN_CASE_DIR / "layer3_conformance_harness.json"
HEALTH_METRIC_LEDGERS_PATH = POLICY_DESIGN_CASE_DIR / "layer3_health_metric_ledgers.toml"
IMPORT_FIREWALL_LINT_PATH = POLICY_DESIGN_CASE_DIR / "layer3_import_firewall_lint.json"
EMPTY_PORT_MAP_PATH = POLICY_DESIGN_CASE_DIR / "layer3_empty_port_map.json"
ADAPTER_COST_MAP_PATH = POLICY_DESIGN_CASE_DIR / "layer3_adapter_cost_map.json"
FIRST_VERTICAL_CASE_PATH = POLICY_DESIGN_CASE_DIR / "layer3_first_vertical_case.json"

JSON_ARTIFACT_PATHS: tuple[Path, ...] = (
    CAPABILITY_DATA_INVENTORY_PATH,
    TRIAGE_REGISTRY_PATH,
    PORT_MAP_PATH,
    ADAPTER_ADMISSION_REGISTRY_PATH,
    DATA_ASSET_PORTS_PATH,
    CONFORMANCE_HARNESS_PATH,
    IMPORT_FIREWALL_LINT_PATH,
    EMPTY_PORT_MAP_PATH,
    ADAPTER_COST_MAP_PATH,
    FIRST_VERTICAL_CASE_PATH,
    READINESS_MANIFEST_PATH,
)
TOML_ARTIFACT_PATHS: tuple[Path, ...] = (HEALTH_METRIC_LEDGERS_PATH,)
PERSISTED_BUNDLE_PATHS: tuple[Path, ...] = (
    CAPABILITY_DATA_INVENTORY_PATH,
    TRIAGE_REGISTRY_PATH,
    PORT_MAP_PATH,
    ADAPTER_ADMISSION_REGISTRY_PATH,
    DATA_ASSET_PORTS_PATH,
    CONFORMANCE_HARNESS_PATH,
    HEALTH_METRIC_LEDGERS_PATH,
    IMPORT_FIREWALL_LINT_PATH,
    EMPTY_PORT_MAP_PATH,
    ADAPTER_COST_MAP_PATH,
    FIRST_VERTICAL_CASE_PATH,
    READINESS_MANIFEST_PATH,
)
CLOSURE_ARTIFACT_PATHS: tuple[Path, ...] = (
    CAPABILITY_DATA_INVENTORY_PATH,
    TRIAGE_REGISTRY_PATH,
    PORT_MAP_PATH,
    ADAPTER_ADMISSION_REGISTRY_PATH,
    DATA_ASSET_PORTS_PATH,
    CONFORMANCE_HARNESS_PATH,
    HEALTH_METRIC_LEDGERS_PATH,
    IMPORT_FIREWALL_LINT_PATH,
    EMPTY_PORT_MAP_PATH,
    ADAPTER_COST_MAP_PATH,
    FIRST_VERTICAL_CASE_PATH,
    ADR_PATH,
)

ALL_ISSUE_CODES: tuple[str, ...] = (
    "layer3_g0_inventory_missing_capability_source",
    "layer3_g0_inventory_missing_data_asset",
    "layer3_g0_triage_missing_entry",
    "layer3_g0_quarantine_missing_required_entry",
    "layer3_g0_quarantined_source_admitted",
    "layer3_g0_port_map_drift",
    "layer3_g0_portless_capability_missing_open_question",
    "layer3_g0_adapter_maturity_overclaim",
    "layer3_g0_health_metric_missing",
    "layer3_g0_source_touchpoint_registration_missing",
    "layer3_g0_touchpoint_admission_without_contract",
    "layer3_g0_source_truth_lattice_mutated_in_g0",
    "layer3_g0_public_surface_unsynced",
    "layer3_g0_pdc_non_waist_import",
    "layer3_g0_import_policy_constitution_conflict_unrecorded",
    "layer3_g0_registry_conflation_unrecorded",
    "layer3_g0_import_firewall_artifact_missing",
    "layer3_g0_manifest_runtime_drift",
    "layer3_g0_adr_not_accepted",
    "layer3_g0_adr_human_acceptance_missing",
    "layer3_g0_adr_open_questions_missing",
    "layer3_g0_data_asset_evidence_missing",
    "layer3_g0_data_asset_unclassified",
    "layer3_g0_manifest_backed_data_scan_bypassed",
    "layer3_g0_processing_transform_unclassified",
    "layer3_g0_lex_triage_evidence_missing",
    "layer3_g0_lex_binary_projection_overquarantined",
    "layer3_g0_empty_port_map_missing_constraint_rank",
    "layer3_g0_adapter_cost_map_missing_near_typed_score",
    "layer3_g0_status_composition_missing",
    "layer3_g0_first_case_id_mismatch",
)


def validate_layer3_g0_readiness(repo_root: Path, *, write: bool = False) -> dict[str, Any]:
    """Build a Layer 3 G0 readiness report from runtime and persisted artifacts."""

    root = Path(repo_root).resolve()
    runtime_bundle = g0.build_layer3_g0_bundle(root)
    if write:
        _write_artifacts(root, runtime_bundle)
        _ensure_adr_placeholder(root)

    missing_paths = _missing_persisted_paths(root)
    issues = [_missing_artifact_issue(path) for path in missing_paths]

    persisted: g0.Layer3G0Bundle | dict[str, Any]
    if missing_paths:
        persisted = runtime_bundle
    else:
        try:
            persisted = _load_persisted_bundle(root)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            persisted = runtime_bundle
            issues.append(
                _issue(
                    "layer3_g0_manifest_runtime_drift",
                    "$.persisted_bundle",
                    f"persisted Layer 3 G0 artifacts could not be loaded: {error}",
                )
            )

    runtime_report = g0.validate_layer3_g0_bundle(root, persisted).model_dump(mode="json")
    issues.extend(runtime_report["issues"])

    adr_payload = _adr_payload(root)
    adr_report = g0.validate_layer3_g0_adr(adr_payload).model_dump(mode="json")
    issues.extend(adr_report["issues"])
    issues.extend(_supplemental_adr_issues(adr_payload))

    bundle_counts = runtime_bundle.readiness_manifest.counts
    summary = {**bundle_counts, **runtime_report.get("summary", {})}
    summary.pop("status", None)
    summary.update(_artifact_summary(root, runtime_bundle))
    summary.update(_adr_summary(adr_payload))

    normalized_issues = _deduplicate_issues(issues)
    return {
        "status": "fail" if normalized_issues else "pass",
        "issues": normalized_issues,
        "summary": summary,
        "write": write,
        "issue_code_dictionary": list(ALL_ISSUE_CODES),
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Run the Layer 3 G0 readiness check CLI."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--output-format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    report = validate_layer3_g0_readiness(args.repo_root, write=args.write)
    rendered = (
        _json_dumps(report) if args.output_format == "json" else _render_text_report(report)
    )
    if args.output is not None:
        output_path = _resolve_path(Path(args.repo_root), args.output)
        atomic_write_text(output_path, rendered)
    sys.stdout.write(rendered)
    return 0 if report["status"] == "pass" else 1


def _write_artifacts(repo_root: Path, bundle: g0.Layer3G0Bundle) -> None:
    base = {
        "schema_version": g0.LAYER3_G0_SCHEMA_VERSION,
        "rule_version": g0.LAYER3_G0_RULE_VERSION,
    }
    _write_json(
        repo_root / CAPABILITY_DATA_INVENTORY_PATH,
        {
            **base,
            "capability_inventory": _dump(bundle.capability_inventory),
            "data_asset_inventory": _dump(bundle.data_asset_inventory),
        },
    )
    _write_json(
        repo_root / TRIAGE_REGISTRY_PATH,
        {
            **base,
            "triage_registry": {"records": _dump(bundle.triage_registry)},
            "quarantine_registry": {"entries": _dump(bundle.quarantine_registry)},
            "runtime_quality_touchpoints": _dump(bundle.runtime_quality_touchpoints),
            "status_composition_matrix": _dump(bundle.status_composition_matrix),
        },
    )
    _write_json(repo_root / PORT_MAP_PATH, {**base, "port_map": _dump(bundle.port_map)})
    _write_json(
        repo_root / ADAPTER_ADMISSION_REGISTRY_PATH,
        {**base, "adapter_admission_registry": {"records": _dump(bundle.adapter_admission_registry)}},
    )
    _write_json(
        repo_root / DATA_ASSET_PORTS_PATH,
        {**base, "data_asset_ports": {"records": _dump(bundle.data_asset_ports)}},
    )
    _write_json(
        repo_root / CONFORMANCE_HARNESS_PATH,
        {**base, "conformance_harness": _dump(bundle.conformance_harness)},
    )
    _write_toml(
        repo_root / HEALTH_METRIC_LEDGERS_PATH,
        {
            **base,
            "health_metric_ledgers": _dump(bundle.health_metric_ledgers),
        },
    )
    _write_json(
        repo_root / IMPORT_FIREWALL_LINT_PATH,
        {**base, "import_firewall_lint": _dump(bundle.import_firewall_lint)},
    )
    _write_json(
        repo_root / EMPTY_PORT_MAP_PATH,
        {**base, "empty_port_map": {"entries": _dump(bundle.empty_port_map)}},
    )
    _write_json(
        repo_root / ADAPTER_COST_MAP_PATH,
        {**base, "adapter_cost_map": {"entries": _dump(bundle.adapter_cost_map)}},
    )
    _write_json(
        repo_root / FIRST_VERTICAL_CASE_PATH,
        {**base, "first_vertical_case": _dump(bundle.first_vertical_case)},
    )
    _write_json(repo_root / READINESS_MANIFEST_PATH, _dump(bundle.readiness_manifest))


def _load_persisted_bundle(repo_root: Path) -> dict[str, Any]:
    capability_data = _read_json(repo_root / CAPABILITY_DATA_INVENTORY_PATH)
    triage = _read_json(repo_root / TRIAGE_REGISTRY_PATH)
    health_ledgers = _read_toml(repo_root / HEALTH_METRIC_LEDGERS_PATH).get(
        "health_metric_ledgers", []
    )
    return {
        "capability_inventory": capability_data["capability_inventory"],
        "data_asset_inventory": capability_data["data_asset_inventory"],
        "triage_registry": _records(triage["triage_registry"]),
        "quarantine_registry": _entries(triage["quarantine_registry"]),
        "port_map": _read_json(repo_root / PORT_MAP_PATH)["port_map"],
        "runtime_quality_touchpoints": triage["runtime_quality_touchpoints"],
        "adapter_admission_registry": _records(
            _read_json(repo_root / ADAPTER_ADMISSION_REGISTRY_PATH)[
                "adapter_admission_registry"
            ]
        ),
        "data_asset_ports": _records(
            _read_json(repo_root / DATA_ASSET_PORTS_PATH)["data_asset_ports"]
        ),
        "conformance_harness": _read_json(repo_root / CONFORMANCE_HARNESS_PATH)[
            "conformance_harness"
        ],
        "health_metric_ledgers": health_ledgers,
        "import_firewall_lint": _read_json(repo_root / IMPORT_FIREWALL_LINT_PATH)[
            "import_firewall_lint"
        ],
        "status_composition_matrix": triage["status_composition_matrix"],
        "empty_port_map": _entries(_read_json(repo_root / EMPTY_PORT_MAP_PATH)["empty_port_map"]),
        "adapter_cost_map": _entries(
            _read_json(repo_root / ADAPTER_COST_MAP_PATH)["adapter_cost_map"]
        ),
        "first_vertical_case": _read_json(repo_root / FIRST_VERTICAL_CASE_PATH)[
            "first_vertical_case"
        ],
        "readiness_manifest": _read_json(repo_root / READINESS_MANIFEST_PATH),
    }


def _ensure_adr_placeholder(repo_root: Path) -> None:
    path = repo_root / ADR_PATH
    if path.exists():
        return
    atomic_write_text(path, _adr_placeholder_text())


def _adr_placeholder_text() -> str:
    return """# ADR-0175: Layer 3 Grounding Subordination Discipline

## Status

Proposed

## Context

Layer 3 G0 freezes the pre-adapter grounding discipline for the Policy Design
Case. It persists the capability/data inventory, triage registry, port map,
source-touchpoint registration, conformance harness, health ledgers, import
firewall lint, empty-port map, adapter-cost map, and first vertical case refs
before any adapter may claim authority.

Related: ADR-0174, ADR-0173, ADR-0156.

## Decision

G0 artifacts are deterministic readiness and audit evidence only. They are
authoritative for `layer3_g0_pre_adapter_inventory`,
`layer3_g0_triage_projection`, `layer3_g0_import_firewall_audit`,
`layer3_g0_manifest_drift_detection`, and
`layer3_g0_zero_adapter_admission_gate`. They may not be used for adapter
admission, publication authority, claim authority, production recommendation,
closeout authority, grounded conversion, useful design outcome, LLM authority,
or source-truth adapter path creation.

LLM output remains candidate material and never authority. Adapter discipline
is fail-closed: no adapter admission before G0, zero admitted adapters, and any
quarantined source must block adapter admission. The preservation registry for
source truth is distinct from the adapter admission registry; preserving legacy
paths is not the same as admitting a Layer 3 adapter.

The current import policy has a recorded conflict: `architecture/imports/policy.toml:112`
allows broader `pdc` imports than the constitution's narrow-waist posture for
Layer 3. A follow-up architecture ADR must narrow `policy.toml`'s `pdc`
allowlist after this freeze so `runtime`, `scientist`, and `ir` cannot become
implicit source-authority lanes for Policy Design Case code.

Constitution section 8.4 open questions remain `tracked_empirically_open`.
They are not resolved by this ADR; they are governed as empirical follow-up
questions with explicit evidence refs.

## Consequences

G0 can persist and replay the grounding inventory while blocking authority
laundering. Portless capability gaps remain governed waist-change questions,
health ledgers stay frozen until the next slice, and the readiness manifest
must match the runtime builder counts.

Until a human principal accepts this ADR, Layer 3 G0 remains blocked by the
governance gate. When a human principal accepts it, they must add fields named
accepted_by, accepted_at, and acceptance_ref in this document. An agent-written
status string is not sufficient evidence of acceptance.
"""


def _adr_payload(repo_root: Path) -> dict[str, Any]:
    path = repo_root / ADR_PATH
    if not path.exists():
        return {
            "adr": {
                "adr_id": "0175",
                "title": "Layer 3 Grounding Subordination Discipline",
                "status": "Proposed",
                "accepted_by": "",
                "accepted_at": "",
                "acceptance_ref": "",
                "open_questions_mode": "",
                "import_policy_constitution_conflict_recorded": False,
                "policy_toml_pdc_allowlist_narrowing_followup_recorded": False,
                "registry_crosswalk_clarification_recorded": False,
            }
        }

    text = path.read_text(encoding="utf-8")
    raw_status = _section_first_line(text, "Status") or _field(text, "status") or "Proposed"
    status = "Accepted" if raw_status.strip().strip("`").lower() == "accepted" else raw_status
    return {
        "adr": {
            "adr_id": "0175",
            "title": "Layer 3 Grounding Subordination Discipline",
            "status": status,
            "accepted_by": _field(text, "accepted_by") or _field(text, "Accepted by"),
            "accepted_at": _field(text, "accepted_at") or _field(text, "Accepted at"),
            "acceptance_ref": _field(text, "acceptance_ref") or _field(text, "Acceptance ref"),
            "open_questions_mode": "tracked_empirically_open"
            if "tracked_empirically_open" in text
            else "",
            "import_policy_constitution_conflict_recorded": "policy.toml" in text
            and "constitution" in text
            and "narrow" in text,
            "policy_toml_pdc_allowlist_narrowing_followup_recorded": "policy.toml" in text
            and "follow-up" in text
            and "narrow" in text,
            "registry_crosswalk_clarification_recorded": "preservation registry" in text
            and "admission registry" in text,
        }
    }


def _supplemental_adr_issues(adr_payload: Mapping[str, Any]) -> list[dict[str, str]]:
    adr = adr_payload.get("adr", adr_payload)
    if not isinstance(adr, Mapping):
        return []
    if adr.get("accepted_by") and adr.get("accepted_at") and adr.get("acceptance_ref"):
        return []
    return [
        _issue(
            "layer3_g0_adr_human_acceptance_missing",
            str(ADR_PATH),
            "Task 5 must record human-principal acceptance fields for ADR-0175.",
        )
    ]


def _artifact_summary(repo_root: Path, bundle: g0.Layer3G0Bundle) -> dict[str, Any]:
    return {
        "closure_artifact_count": len(bundle.readiness_manifest.closure_artifact_paths),
        "persisted_closure_artifact_count": sum(
            1 for path in CLOSURE_ARTIFACT_PATHS if (repo_root / path).exists()
        ),
        "readiness_manifest_count": 1 if (repo_root / READINESS_MANIFEST_PATH).exists() else 0,
    }


def _adr_summary(adr_payload: Mapping[str, Any]) -> dict[str, Any]:
    adr = adr_payload.get("adr", adr_payload)
    if not isinstance(adr, Mapping):
        return {}
    return {
        "adr_id": "0175",
        "adr_status": adr.get("status", ""),
        "adr_human_acceptance_ref_present": bool(
            adr.get("accepted_by") and adr.get("accepted_at") and adr.get("acceptance_ref")
        ),
        "adr_open_questions_mode": adr.get("open_questions_mode", ""),
        "import_policy_constitution_conflict_recorded": bool(
            adr.get("import_policy_constitution_conflict_recorded")
        ),
        "policy_toml_pdc_allowlist_narrowing_followup_recorded": bool(
            adr.get("policy_toml_pdc_allowlist_narrowing_followup_recorded")
        ),
        "registry_crosswalk_clarification_recorded": bool(
            adr.get("registry_crosswalk_clarification_recorded")
        ),
    }


def _missing_persisted_paths(repo_root: Path) -> list[Path]:
    return [path for path in PERSISTED_BUNDLE_PATHS if not (repo_root / path).exists()]


def _missing_artifact_issue(path: Path) -> dict[str, str]:
    code = (
        "layer3_g0_import_firewall_artifact_missing"
        if path == IMPORT_FIREWALL_LINT_PATH
        else "layer3_g0_manifest_runtime_drift"
    )
    return _issue(code, str(path), f"Layer 3 G0 artifact is missing: {path.as_posix()}")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _write_json(path: Path, payload: Any) -> None:
    atomic_write_text(path, _json_dumps(payload))


def _write_toml(path: Path, payload: Mapping[str, Any]) -> None:
    lines = [
        f"schema_version = {_toml_value(payload['schema_version'])}",
        f"rule_version = {_toml_value(payload['rule_version'])}",
        "",
    ]
    for row in payload.get("health_metric_ledgers", []):
        if not isinstance(row, Mapping):
            continue
        lines.append("[[health_metric_ledgers]]")
        for key in sorted(row):
            lines.append(f"{key} = {_toml_value(row[key])}")
        lines.append("")
    atomic_write_text(path, "\n".join(lines).rstrip() + "\n")


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True, default=str) + "\n"


def _toml_value(value: Any) -> str:
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    if isinstance(value, Mapping):
        pairs = [f"{key} = {_toml_value(value[key])}" for key in sorted(value)]
        return "{ " + ", ".join(pairs) + " }"
    raise TypeError(f"Unsupported TOML value: {value!r}")


def _dump(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): _dump(inner) for key, inner in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return [_dump(item) for item in value]
    return value


def _records(payload: Any) -> list[Any]:
    if isinstance(payload, Mapping):
        records = payload.get("records", [])
        return list(records) if isinstance(records, Sequence) and not isinstance(records, str) else []
    return list(payload) if isinstance(payload, Sequence) and not isinstance(payload, str) else []


def _entries(payload: Any) -> list[Any]:
    if isinstance(payload, Mapping):
        entries = payload.get("entries", [])
        return list(entries) if isinstance(entries, Sequence) and not isinstance(entries, str) else []
    return list(payload) if isinstance(payload, Sequence) and not isinstance(payload, str) else []


def _field(text: str, key: str) -> str:
    normalized = key.replace("_", " ").lower()
    variants = {key.lower(), normalized, key.replace("_", "-").lower()}
    for line in text.splitlines():
        stripped = line.strip().lstrip("- ").strip()
        lowered = stripped.lower()
        if any(lowered.startswith(variant) for variant in variants) and ":" in stripped:
            return stripped.split(":", 1)[1].strip().strip("`")
    return ""


def _section_first_line(text: str, heading: str) -> str:
    marker = f"## {heading}"
    start = text.find(marker)
    if start == -1:
        return ""
    section = text[start + len(marker) :]
    next_heading = section.find("\n## ")
    if next_heading != -1:
        section = section[:next_heading]
    for line in section.splitlines():
        stripped = line.strip()
        if stripped:
            return re.sub(r"^[-*]\s*", "", stripped).strip()
    return ""


def _deduplicate_issues(issues: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str, str]] = set()
    normalized: list[dict[str, str]] = []
    for issue in issues:
        code = str(issue.get("code", ""))
        path = str(issue.get("path", ""))
        message = str(issue.get("message", ""))
        key = (code, path, message)
        if key in seen:
            continue
        seen.add(key)
        normalized.append({"code": code, "path": path, "message": message})
    return normalized


def _issue(code: str, path: str, message: str) -> dict[str, str]:
    return {"code": code, "path": path, "message": message}


def _render_text_report(report: Mapping[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [f"status={report.get('status', '')}"]
    if isinstance(summary, Mapping):
        for key in sorted(summary):
            lines.append(f"{key}={_display_value(summary[key])}")
    issues = report.get("issues", [])
    if isinstance(issues, Sequence) and issues:
        lines.append("issues:")
        for issue in issues:
            if isinstance(issue, Mapping):
                lines.append(
                    f"- {issue.get('code', '')} {issue.get('path', '')}: "
                    f"{issue.get('message', '')}"
                )
    return "\n".join(lines).rstrip() + "\n"


def _display_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    return str(value)


def _resolve_path(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


if __name__ == "__main__":
    raise SystemExit(main())

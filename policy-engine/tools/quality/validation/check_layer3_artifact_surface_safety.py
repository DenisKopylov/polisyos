#!/usr/bin/env python3
"""Validate or regenerate Layer 3 artifact surface safety proof packets."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import tempfile
import tomllib
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

FAMILY_ID = "policy-design-case-layer3-artifact-surface-safety"
CAS_REPORT_PATH = "architecture/policy_design_case/layer3_gy_cas_integrity_reports.json"
SECRET_REPORT_PATH = "architecture/policy_design_case/layer3_gy_secret_pii_scan_reports.json"
OUTPUTS = [CAS_REPORT_PATH, SECRET_REPORT_PATH]
FIXTURE_SECRET = "sk-f2negativefixture1234567890abcdef"
FIXTURE_EMAIL = "policy.fixture@example.org"
FIXTURE_TENANT_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
FIXTURE_CELL_ID = "cell-a"
FIXED_TIME = datetime(2026, 6, 16, 12, 34, 56, tzinfo=UTC)


def declared_outputs() -> list[str]:
    """Return the generated artifacts this validator writes in --write mode."""

    return list(OUTPUTS)


def validate(repo_root: Path, *, write: bool = False) -> dict[str, Any]:
    """Return a drift report for the GY-F2 generated proof family."""

    _ensure_src_path(repo_root)
    issues: list[dict[str, str]] = []
    _validate_generated_artifacts_registration(repo_root, issues)
    expected = build_live_proof_payloads(repo_root)
    _validate_secret_reports(expected[SECRET_REPORT_PATH], issues)
    _validate_cas_reports(expected[CAS_REPORT_PATH], issues)
    if write:
        for relative_path, payload in expected.items():
            path = repo_root / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
    else:
        for relative_path, expected_payload in expected.items():
            committed = _read_json(repo_root / relative_path, issues)
            if committed != expected_payload:
                issues.append(
                    {
                        "code": "layer3_artifact_surface_safety_drift",
                        "path": relative_path,
                    }
                )
    return {
        "status": "pass" if not issues else "fail",
        "family_id": FAMILY_ID,
        "checked_artifacts": OUTPUTS,
        "write": write,
        "issues": issues,
    }


def build_live_proof_payloads(repo_root: Path) -> dict[str, dict[str, Any]]:
    """Recompute proof payloads from live CAS, connector, loop, and HTTP route code."""

    from polisyos.core import scan_secret_and_pii
    from polisyos.core.artifacts import FileSystemCAS, PutOptions, SchemaInfo
    from polisyos.core.artifacts.manifest import ProducerInfo
    from polisyos.data_forge.read_api.catalog import build_slice0_fixture_catalog_graph
    from polisyos.fabric.connectors.base import ConnectionConfig
    from polisyos.fabric.connectors.http_limits import read_bounded_response_body
    from polisyos.fabric.connectors.types import FetchError
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.quality.workspace.loop import WorkspaceLoop

    with tempfile.TemporaryDirectory(prefix="polisyos-layer3-surface-safety-") as tmp:
        root = Path(tmp)
        cas_root = root / ".polisyos"
        store = FileSystemCAS(cas_root)
        clean_ref = store.put_json(
            {"fixture": "clean-public-route", "value": 1},
            PutOptions(
                kind="surface.clean_payload",
                media_type="application/json",
                schema=SchemaInfo(name="surface.clean_payload", version="1.0"),
            ),
        )
        raw_secret_ref = store.put_json(
            {"fixture": "raw-secret", "api_key": FIXTURE_SECRET},
            PutOptions(
                kind="surface.raw_secret_payload",
                media_type="application/json",
                schema=SchemaInfo(name="surface.raw_secret_payload", version="1.0"),
            ),
        )
        manifest_secret_ref = store.put_json(
            {"fixture": "manifest-secret"},
            PutOptions(
                kind="surface.manifest_secret_payload",
                media_type="application/json",
                schema=SchemaInfo(name="surface.manifest_secret_payload", version="1.0"),
                producer=ProducerInfo(component=FIXTURE_EMAIL, version="1.0"),
            ),
        )
        export_secret_ref = store.put_json(
            {
                "title": "Fixture packet",
                "blocks": [
                    {
                        "id": "fixture-secret",
                        "author": "drafter",
                        "content": f"Contact {FIXTURE_EMAIL} before publication.",
                    }
                ],
            },
            PutOptions(
                kind="scientist.decision_packet",
                media_type="application/json",
                schema=SchemaInfo(name="scientist.decision_packet", version="1.0"),
            ),
        )
        _claim_route_fixture_owner(
            store,
            clean_ref.artifact_id,
            raw_secret_ref.artifact_id,
            manifest_secret_ref.artifact_id,
            export_secret_ref.artifact_id,
        )

        app = create_runtime_api_app(
            cas_root=cas_root,
            core_runs_root=cas_root / "runs",
            allow_unscoped_artifacts=True,
            allow_fixture_identity=True,
            enable_response_compression=False,
            enable_security_middlewares=False,
        )
        try:
            from fastapi.testclient import TestClient
        except ModuleNotFoundError as exc:  # pragma: no cover
            raise RuntimeError("F2 surface safety validator requires fastapi testclient") from exc

        route_checks: dict[str, dict[str, Any]] = {}
        with TestClient(app, raise_server_exceptions=False) as client:
            clean = client.get(f"/api/v1/artifacts/{clean_ref.artifact_id}/content")
            route_checks["clean_content_preview"] = {
                "status_code": clean.status_code,
                "leaked_secret": FIXTURE_SECRET in clean.text or FIXTURE_EMAIL in clean.text,
            }
            raw = client.get(
                f"/api/v1/artifacts/{raw_secret_ref.artifact_id}/content",
                headers={"Accept": "application/octet-stream"},
            )
            route_checks["raw_content_secret_fixture"] = {
                "status_code": raw.status_code,
                "blocked": raw.status_code == 409,
                "leaked_secret": FIXTURE_SECRET in raw.text,
            }
            download = client.get(
                f"/api/v1/artifacts/{raw_secret_ref.artifact_id}/download",
                headers={"Accept": "application/octet-stream"},
            )
            route_checks["download_secret_fixture"] = {
                "status_code": download.status_code,
                "blocked": download.status_code == 409,
                "leaked_secret": FIXTURE_SECRET in download.text,
            }
            manifest = client.get(f"/api/v1/artifacts/{manifest_secret_ref.artifact_id}")
            route_checks["cas_manifest_secret_fixture"] = {
                "status_code": manifest.status_code,
                "blocked": manifest.status_code == 409,
                "leaked_secret": FIXTURE_EMAIL in manifest.text,
            }
            export = client.get(f"/api/v1/artifacts/{export_secret_ref.artifact_id}/export")
            route_checks["export_secret_fixture"] = {
                "status_code": export.status_code,
                "blocked": export.status_code == 409,
                "leaked_secret": FIXTURE_EMAIL in export.text,
            }

        connector_config = ConnectionConfig(
            url="https://example.invalid/data",
            auth_method="bearer",
            auth_credentials={"token": FIXTURE_SECRET},
        )
        redacted_config = connector_config.to_dict(redact=True)
        connector_response_blocked = False
        try:
            asyncio.run(
                read_bounded_response_body(
                    _FakeResponse(json.dumps({"email": FIXTURE_EMAIL}).encode("utf-8")),
                    connector_id="validator.fixture",
                    url="https://example.invalid/data",
                    max_response_bytes=4096,
                    max_decompressed_bytes=4096,
                )
            )
        except FetchError:
            connector_response_blocked = True

        loop = WorkspaceLoop(
            artifact_store=store,
            catalog_graph=build_slice0_fixture_catalog_graph(root / "catalog"),
        )
        fixed_now = lambda: FIXED_TIME  # noqa: E731 - concise patch target for recompute.
        with (
            patch("polisyos.runtime.quality.workspace.loop._utc_now", fixed_now),
            patch("polisyos.runtime.quality.data_forge_binding._utc_now", fixed_now),
        ):
            exit_contract = loop.run_fixture(
                "ua_msme_credit_worldbank_measurement",
                acquisition_policy="disabled",
            )
            dag_secret_blocked = False
            try:
                loop._persist_loop_payload(  # noqa: SLF001 - validator exercises the write owner.
                    {"fixture_id": "negative-dag", "token": FIXTURE_SECRET},
                    kind="policyos.gy.negative_fixture_payload",
                )
            except ValueError:
                dag_secret_blocked = True

        secret_reports = []
        secret_reports.extend(
            scan_secret_and_pii(
                {"fixture_id": "negative-dag", "token": FIXTURE_SECRET},
                scope="DAG bundles",
                artifact_ref_or_route="gy-loop://policyos.gy.negative_fixture_payload",
                redact=False,
                block_on_findings=True,
            ).reports
        )
        secret_reports.extend(
            scan_secret_and_pii(
                connector_config.to_dict(redact=False),
                scope="connector request/response payloads",
                artifact_ref_or_route="connector://connection_config",
                redact=True,
                block_on_findings=False,
            ).reports
        )
        secret_reports.extend(
            scan_secret_and_pii(
                json.dumps({"email": FIXTURE_EMAIL}).encode("utf-8"),
                scope="connector request/response payloads",
                artifact_ref_or_route="connector://validator.fixture/response",
                redact=False,
                block_on_findings=True,
            ).reports
        )
        secret_reports.extend(
            scan_secret_and_pii(
                store.get_manifest(manifest_secret_ref.artifact_id).model_dump(mode="json"),
                scope="CAS manifests",
                artifact_ref_or_route=f"cas-manifest://{manifest_secret_ref.artifact_id}",
                redact=False,
                block_on_findings=True,
            ).reports
        )
        secret_reports.extend(
            scan_secret_and_pii(
                store.get_bytes(raw_secret_ref.artifact_id),
                scope="raw artifact content/download routes",
                artifact_ref_or_route=f"/api/v1/artifacts/{raw_secret_ref.artifact_id}/content",
                redact=False,
                block_on_findings=True,
            ).reports
        )
        secret_reports.extend(
            scan_secret_and_pii(
                store.get_bytes(export_secret_ref.artifact_id),
                scope="dashboard/public/export packets",
                artifact_ref_or_route=f"/api/v1/artifacts/{export_secret_ref.artifact_id}/export",
                redact=False,
                block_on_findings=True,
            ).reports
        )

        cas_payload = _build_cas_payload(
            store=store,
            exit_payload_refs=[
                envelope.payload_ref for envelope in exit_contract.artifact_envelopes
            ],
        )

        return {
            SECRET_REPORT_PATH: {
                "schema_version": "policyos.policy_design_case.layer3_gy.secret_pii_scan_reports.v1",
                "owner": "team-runtime-quality",
                "proof_source": "live_route_connector_loop_recompute",
                "route_checks": route_checks,
                "connector_checks": {
                    "request_config_redacted": FIXTURE_SECRET not in json.dumps(redacted_config),
                    "response_secret_blocked": connector_response_blocked,
                },
                "dag_checks": {"negative_fixture_blocked": dag_secret_blocked},
                "reports": [
                    report.model_dump(mode="json")
                    for report in sorted(
                        secret_reports,
                        key=lambda item: (
                            item.scope,
                            item.artifact_ref_or_route,
                            item.finding_kind,
                        ),
                    )
                ],
            },
            CAS_REPORT_PATH: cas_payload,
        }


def _build_cas_payload(
    *,
    store: Any,
    exit_payload_refs: list[str],
) -> dict[str, Any]:
    from polisyos.core.artifacts import (
        ArtifactID,
        build_cas_integrity_report,
    )
    from polisyos.core.artifacts._integrity_ops import verify_filesystem_artifact

    duplicate_payload = {"fixture": "duplicate-authority-payload", "value": 7}
    duplicate_a = _write_authority_payload(
        store,
        duplicate_payload,
        kind="surface.duplicate_authority_payload",
    )
    duplicate_b = _write_authority_payload(
        store,
        duplicate_payload,
        kind="surface.duplicate_authority_payload",
    )
    unreferenced = _write_authority_payload(
        store,
        {"fixture": "unreferenced-authority-payload", "value": 11},
        kind="surface.unreferenced_authority_payload",
    )
    duplicate_same_digest = duplicate_a == duplicate_b
    report_ids = [
        ArtifactID.model_validate(ref)
        for ref in [*exit_payload_refs, duplicate_a, unreferenced]
    ]
    tampered_ref = report_ids[0]
    blob_path, manifest_path = store.get_paths(tampered_ref)
    original = blob_path.read_bytes()
    blob_path.write_bytes(original + b"\nmutation")
    tamper_report = verify_filesystem_artifact(
        tampered_ref,
        blob_path=blob_path,
        manifest_path=manifest_path,
    )
    blob_path.write_bytes(original)
    if tamper_report.ok:
        tamper_probe_result = "failed_open"
    else:
        tamper_probe_result = f"rejected:{tamper_report.error}"
    referenced_roots = _cas_retain_roots(
        [str(artifact_id) for artifact_id in report_ids if str(artifact_id) != unreferenced]
    )
    reports = []
    for artifact_id in report_ids:
        is_unreferenced = str(artifact_id) == unreferenced
        reports.append(
            build_cas_integrity_report(
                store,
                artifact_id,
                referrers=[] if is_unreferenced else [f"workspace://gy-f2/{artifact_id.hex[:12]}"],
                report_index_refs=[] if is_unreferenced else ["report-index://layer3-gy-f2"],
                lineage_refs=[] if is_unreferenced else [f"lineage://{artifact_id}"],
                retain_roots={} if is_unreferenced else referenced_roots,
                tamper_probe_result=(
                    tamper_probe_result if artifact_id == tampered_ref else "verify_passed"
                ),
                mutation_probe_result=(
                    f"duplicate_write_same_digest:{duplicate_same_digest}"
                    if artifact_id == ArtifactID.model_validate(duplicate_a)
                    else "immutable_payload_ref"
                ),
            )
        )
    authority_missing = [
        report.artifact_ref for report in reports if report.authority_manifest_ref is None
    ]
    gc_not_retained = [
        report.artifact_ref for report in reports if report.gc_dry_run_result != "retain"
    ]
    return {
        "schema_version": "policyos.policy_design_case.layer3_gy.cas_integrity_reports.v1",
        "owner": "team-runtime-quality",
        "proof_source": "live_cas_workspace_loop_recompute",
        "dedup_probe": {
            "first_ref": duplicate_a,
            "second_ref": duplicate_b,
            "same_digest": duplicate_same_digest,
        },
        "tamper_probe": {
            "artifact_ref": str(tampered_ref),
            "result": tamper_probe_result,
        },
        "gc_dry_run_summary": {
            "authority_missing": authority_missing,
            "not_retained": [
                ref for ref in gc_not_retained if ref != unreferenced
            ],
            "unreferenced_authority_probe": {
                "artifact_ref": unreferenced,
                "result": next(
                    report.gc_dry_run_result
                    for report in reports
                    if report.artifact_ref == unreferenced
                ),
            },
        },
        "reports": [
            report.model_dump(mode="json")
            for report in sorted(reports, key=lambda item: item.artifact_ref)
        ],
    }


def _write_authority_payload(store: Any, payload: dict[str, Any], *, kind: str) -> str:
    from polisyos.core.artifacts import PutOptions, SchemaInfo
    from polisyos.core.artifacts.manifest import ProducerInfo
    from polisyos.core.canon import CanonSpec
    from polisyos.runtime.http.services.control.artifacts import write_authority_artifact

    generated_at = FIXED_TIME.isoformat().replace("+00:00", "Z")
    result = write_authority_artifact(
        store,
        payload,
        PutOptions(
            kind=kind,
            media_type="application/json",
            schema=SchemaInfo(name=kind, version="1.0"),
            producer=ProducerInfo(component="polisyos.validator.surface_safety", version="1.0"),
        ),
        evidence_id=f"{kind}-{json.dumps(payload, sort_keys=True)}",
        evidence_class="authority_bearing",
        authority_role="producer_authority",
        provenance_kind="runtime_emitted",
        owner="team-runtime-quality",
        reader_contract=kind,
        reader_contract_version="1.0",
        tenant_id="policyos-system",
        cell_id=None,
        run_id="run-layer3-surface-safety",
        job_id="job-layer3-surface-safety",
        trace_id="trace-layer3-surface-safety",
        span_id=f"span-{kind}",
        parent_span_id=None,
        requested_execution_profile="validator",
        effective_execution_profile="validator",
        phase="GY-F2",
        generated_at=generated_at,
        as_of_time=generated_at,
        same_input_closure={
            "closure_id": "layer3-surface-safety",
            "status": "closed",
            "run_id": "run-layer3-surface-safety",
            "job_id": "job-layer3-surface-safety",
            "tenant_id": "policyos-system",
            "cell_id": None,
            "evidence_input_refs": (),
        },
        input_refs=[],
        effective_mode_ref="validator",
        validation_status="pass",
        blocking_status="non_blocking",
        governance={
            "classification": "internal",
            "authority_boundary": "validator_proof",
            "pii": "secret_pii_scanned",
            "retention_policy": "policy_design_case_generated_artifact",
            "review_status": "runtime_generated",
            "override_policy": "no_override",
            "approval_policy": "not_publication_authority",
        },
        redaction_policy_ref="polisyos.core.llm.sanitization.v1",
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return str(result.cas_ref.artifact_id)


def _cas_retain_roots(artifact_refs: list[str]) -> dict[str, Any]:
    return {
        "report_index": {
            "index_ref": "report-index://layer3-gy-f2",
            "artifacts": [{"artifact_ref": ref} for ref in artifact_refs],
        },
        "lineage": {
            "lineage_ref": "lineage://layer3-gy-f2",
            "nodes": [{"artifact_id": ref, "parents": []} for ref in artifact_refs],
        },
        "workspace": {
            "workspace_ref": "workspace://gy-f2",
            "artifact_refs": list(artifact_refs),
        },
    }


def _claim_route_fixture_owner(store: Any, *artifact_ids: Any) -> None:
    for artifact_id in artifact_ids:
        store.record_artifact_owner(
            artifact_id,
            tenant_id=FIXTURE_TENANT_ID,
            cell_id=FIXTURE_CELL_ID,
            writer="layer3-artifact-surface-safety-validator",
        )


class _FakeContent:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    async def iter_chunked(self, chunk_size: int) -> AsyncIterator[bytes]:
        del chunk_size
        yield self._payload


class _FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self.headers = {"Content-Length": str(len(payload))}
        self.content = _FakeContent(payload)
        self._payload = payload

    async def read(self) -> bytes:
        return self._payload


def _validate_generated_artifacts_registration(
    repo_root: Path,
    issues: list[dict[str, str]],
) -> None:
    generated = tomllib.loads(
        (repo_root / "architecture/generated_artifacts.toml").read_text(encoding="utf-8")
    )
    families = {family.get("id"): family for family in generated.get("family", [])}
    family = families.get(FAMILY_ID)
    if not family:
        issues.append({"code": "layer3_artifact_surface_safety_family_missing"})
        return
    if set(family.get("outputs") or []) != set(OUTPUTS):
        issues.append({"code": "layer3_artifact_surface_safety_outputs_mismatch"})
    if family.get("owner") != "team-runtime-quality":
        issues.append({"code": "layer3_artifact_surface_safety_owner_mismatch"})
    if family.get("stale_output_behavior") != "fail":
        issues.append({"code": "layer3_artifact_surface_safety_stale_not_fail"})
    if "--check" not in list(family.get("check_command") or []):
        issues.append({"code": "layer3_artifact_surface_safety_check_missing_check"})
    if "--write" not in " ".join(family.get("regenerate_commands") or []):
        issues.append({"code": "layer3_artifact_surface_safety_regenerate_missing_write"})


def _validate_secret_reports(payload: dict[str, Any], issues: list[dict[str, str]]) -> None:
    reports = payload.get("reports")
    if not isinstance(reports, list) or not reports:
        issues.append({"code": "secret_pii_reports_missing"})
        return
    required_fields = {
        "scope",
        "artifact_ref_or_route",
        "detector_version",
        "finding_kind",
        "redaction_applied",
        "authority_surface_blocked",
        "negative_fixture_result",
    }
    scopes = set()
    blocked_fixtures = 0
    redacted_fixtures = 0
    for report in reports:
        if not isinstance(report, dict):
            issues.append({"code": "secret_pii_report_not_object"})
            continue
        if set(report) != required_fields:
            issues.append({"code": "secret_pii_report_fields_mismatch"})
        scopes.add(report.get("scope"))
        if report.get("negative_fixture_result") == "blocked":
            blocked_fixtures += 1
        if report.get("negative_fixture_result") == "redacted":
            redacted_fixtures += 1
    expected_scopes = {
        "DAG bundles",
        "connector request/response payloads",
        "CAS manifests",
        "raw artifact content/download routes",
        "dashboard/public/export packets",
    }
    if scopes != expected_scopes:
        issues.append({"code": "secret_pii_scope_coverage_mismatch"})
    if blocked_fixtures < 4:
        issues.append({"code": "secret_pii_blocked_fixture_coverage_missing"})
    if redacted_fixtures < 1:
        issues.append({"code": "secret_pii_redacted_fixture_missing"})
    for name, check in (payload.get("route_checks") or {}).items():
        if check.get("leaked_secret"):
            issues.append({"code": "secret_pii_route_leaked", "route": str(name)})
        if name != "clean_content_preview" and not check.get("blocked"):
            issues.append({"code": "secret_pii_route_not_blocked", "route": str(name)})
    connector_checks = payload.get("connector_checks") or {}
    if connector_checks.get("request_config_redacted") is not True:
        issues.append({"code": "connector_request_not_redacted"})
    if connector_checks.get("response_secret_blocked") is not True:
        issues.append({"code": "connector_response_not_blocked"})
    if (payload.get("dag_checks") or {}).get("negative_fixture_blocked") is not True:
        issues.append({"code": "dag_secret_fixture_not_blocked"})


def _validate_cas_reports(payload: dict[str, Any], issues: list[dict[str, str]]) -> None:
    reports = payload.get("reports")
    if not isinstance(reports, list) or not reports:
        issues.append({"code": "cas_integrity_reports_missing"})
        return
    required_fields = {
        "artifact_ref",
        "payload_digest",
        "canonicalization_rule_ref",
        "blob_uri",
        "manifest_ref",
        "authority_manifest_ref",
        "duplicate_group_id",
        "referrers",
        "report_index_refs",
        "lineage_refs",
        "tamper_probe_result",
        "mutation_probe_result",
        "gc_retain_reason",
        "gc_dry_run_result",
    }
    for report in reports:
        if not isinstance(report, dict):
            issues.append({"code": "cas_integrity_report_not_object"})
            continue
        if set(report) != required_fields:
            issues.append({"code": "cas_integrity_report_fields_mismatch"})
        if not report.get("authority_manifest_ref"):
            issues.append({"code": "cas_integrity_authority_manifest_missing"})
        unreferenced_probe = (
            (payload.get("gc_dry_run_summary") or {}).get("unreferenced_authority_probe")
            or {}
        )
        is_unreferenced_probe = report.get("artifact_ref") == unreferenced_probe.get(
            "artifact_ref"
        )
        if is_unreferenced_probe:
            if report.get("gc_dry_run_result") != "blocked":
                issues.append({"code": "cas_integrity_unreferenced_authority_retained"})
        elif report.get("gc_dry_run_result") != "retain":
            issues.append({"code": "cas_integrity_gc_not_retained"})
    dedup = payload.get("dedup_probe") or {}
    if dedup.get("same_digest") is not True or dedup.get("first_ref") != dedup.get("second_ref"):
        issues.append({"code": "cas_integrity_dedup_failed"})
    tamper = payload.get("tamper_probe") or {}
    if not str(tamper.get("result") or "").startswith("rejected:"):
        issues.append({"code": "cas_integrity_tamper_not_rejected"})
    gc_summary = payload.get("gc_dry_run_summary") or {}
    if gc_summary.get("authority_missing") or gc_summary.get("not_retained"):
        issues.append({"code": "cas_integrity_gc_summary_failed"})
    unreferenced_probe = gc_summary.get("unreferenced_authority_probe") or {}
    if unreferenced_probe.get("result") != "blocked":
        issues.append({"code": "cas_integrity_unreferenced_probe_not_blocked"})


def _read_json(path: Path, issues: list[dict[str, str]]) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        issues.append({"code": "layer3_artifact_surface_safety_missing", "path": str(path)})
    except json.JSONDecodeError as exc:
        issues.append(
            {
                "code": "layer3_artifact_surface_safety_invalid_json",
                "path": str(path),
                "detail": str(exc),
            }
        )
    return {}


def _ensure_src_path(repo_root: Path) -> None:
    src_path = repo_root / "src"
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[3])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    parser.add_argument("--output-format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    report = validate(args.repo_root.resolve(), write=args.write)
    if args.output_format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    elif report["status"] == "pass":
        print("PASS: Layer 3 artifact surface safety proofs are current.")
    else:
        print("FAIL: Layer 3 artifact surface safety proofs drifted or are invalid.")
        for issue in report["issues"]:
            print(f"- {issue}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

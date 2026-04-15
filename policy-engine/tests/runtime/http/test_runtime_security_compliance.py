from __future__ import annotations

import gzip
import json
import time
from pathlib import Path

from polisyos_tests_runtime_http_conftest import build_runtime_api_env

from polisyos.core.components.cli import main
from polisyos.core.security.rotation import (
    rotate_ed25519_signing_key,
    update_jwt_trust_anchor_manifest,
)
from polisyos.runtime.http.compliance import (
    RuntimeAuditQuery,
    apply_runtime_audit_retention,
    query_runtime_audit,
    summarize_runtime_audit,
    write_runtime_audit_report,
)


def test_cookie_authenticated_mutations_require_csrf_token(tmp_path: Path) -> None:
    env = build_runtime_api_env(
        tmp_path,
        include_test_client=True,
        app_kwargs={"enable_csrf_protection": True},
    )
    client = env["client"]
    client.cookies.set("polisyos_session", "session-1")
    client.cookies.set("polisyos_csrf", "csrf-1")
    payload_without_side_effects = {"data_source": {}}

    blocked = client.post(
        "/api/v1/control/runs",
        json=payload_without_side_effects,
    )
    allowed = client.post(
        "/api/v1/control/runs",
        json=payload_without_side_effects,
        headers={"X-CSRF-Token": "csrf-1"},
    )

    assert blocked.status_code == 403
    assert blocked.json()["code"] == "csrf_token_required"
    assert allowed.status_code == 400
    assert allowed.json()["code"] == "missing_data_source"


def test_runtime_audit_query_export_and_retention(tmp_path: Path) -> None:
    cas_root = tmp_path / ".polisyos"
    audit_root = cas_root / "runtime" / "audit"
    audit_root.mkdir(parents=True)
    old_timestamp = time.time() - (10 * 24 * 60 * 60)
    new_timestamp = time.time()
    (audit_root / "access.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "timestamp": old_timestamp,
                        "tenant_id": "tenant-a",
                        "actor": "alice",
                        "operation": "READ runtime.artifact",
                        "resource_kind": "runtime.artifact",
                        "resource_id": "sha256:old",
                        "outcome": "success",
                    }
                ),
                json.dumps(
                    {
                        "timestamp": new_timestamp,
                        "tenant_id": "tenant-a",
                        "actor": "bob",
                        "operation": "READ runtime.run",
                        "resource_kind": "runtime.run",
                        "resource_id": "R_new",
                        "outcome": "success",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (audit_root / "mutations.jsonl").write_text(
        json.dumps(
            {
                "timestamp": new_timestamp,
                "tenant_id": "tenant-a",
                "actor": "alice",
                "operation": "POST /api/v1/control/runs",
                "resource_ids": ["R_mutated"],
                "outcome": "success",
                "status_code": 200,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    entries = query_runtime_audit(
        cas_root,
        RuntimeAuditQuery(tenant_id="tenant-a", actor="alice"),
    )
    summary = summarize_runtime_audit(entries)
    report_path = tmp_path / "audit-report.json"
    write_runtime_audit_report(entries, report_path)
    retention = apply_runtime_audit_retention(
        cas_root,
        retention_days=7,
        archive_dir=tmp_path / "archive",
    )

    assert {entry["resource_id"] for entry in entries if entry.get("resource_id")} == {
        "sha256:old"
    }
    assert any("R_mutated" in entry.get("resource_ids", []) for entry in entries)
    assert summary["by_actor"]["alice"] == 2
    assert json.loads(report_path.read_text(encoding="utf-8"))["summary"]["total"] == 2
    assert retention.archived == 1
    assert retention.kept == 2
    assert retention.archive_paths
    with gzip.open(retention.archive_paths[0], "rt", encoding="utf-8") as handle:
        assert "sha256:old" in handle.read()


def test_rotation_helpers_and_cli_write_operator_manifests(tmp_path: Path, capsys) -> None:
    jwt_manifest = tmp_path / "security" / "jwt-trust-anchors.json"
    jwt_result = update_jwt_trust_anchor_manifest(
        manifest_path=jwt_manifest,
        issuer="https://issuer.example",
        jwks_uri="https://issuer.example/jwks",
        audience="polisyos-web",
        active_kids=("kid-a",),
        next_kids=("kid-b",),
        rotated_by="test",
    )
    ed_result = rotate_ed25519_signing_key(
        key_base=tmp_path / "keys" / "signer-2026q2",
        identity="ci-prod",
        trust_dir=tmp_path / "keys" / "trusted",
        identities_path=tmp_path / "keys" / "identities.json",
        revoked_dir=tmp_path / "keys" / "revoked",
    )

    assert jwt_result.active_kids == ("kid-a",)
    assert jwt_result.next_kids == ("kid-b",)
    assert ed_result.private_key_path.stat().st_mode & 0o777 == 0o600
    assert ed_result.trusted_key_path.exists()
    identities = json.loads(ed_result.identities_path.read_text(encoding="utf-8"))
    assert identities[ed_result.key_id] == "ci-prod"

    cli_manifest = tmp_path / "security" / "jwt-cli.json"
    assert main(
        [
            "security",
            "rotate-jwt",
            "--manifest",
            str(cli_manifest),
            "--issuer",
            "https://issuer.example",
            "--jwks-uri",
            "https://issuer.example/jwks",
            "--audience",
            "polisyos-web",
            "--active-kid",
            "kid-c",
            "--json",
        ]
    ) == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out)["active_kids"] == ["kid-c"]


def test_runtime_audit_cli_query_exports_json(tmp_path: Path, capsys) -> None:
    cas_root = tmp_path / ".polisyos"
    audit_root = cas_root / "runtime" / "audit"
    audit_root.mkdir(parents=True)
    (audit_root / "mutations.jsonl").write_text(
        json.dumps(
            {
                "timestamp": time.time(),
                "tenant_id": "tenant-a",
                "actor": "alice",
                "operation": "POST /api/v1/control/runs",
                "resource_ids": ["R_cli"],
                "outcome": "success",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    code = main(
        [
            "audit",
            "runtime-query",
            "--cas-root",
            str(cas_root),
            "--actor",
            "alice",
            "--json",
        ]
    )
    captured = capsys.readouterr()

    assert code == 0
    payload = json.loads(captured.out)
    assert payload["summary"]["total"] == 1
    assert payload["entries"][0]["resource_ids"] == ["R_cli"]

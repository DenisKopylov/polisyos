"""Exercise PUBLIC verification through the actual runtime app boundary."""

from pathlib import Path

from fastapi.testclient import TestClient

from polisyos.runtime.http.app import create_runtime_api_app


def test_legacy_browser_token_receives_public_verifier_refusal(tmp_path: Path) -> None:
    """A forged browser token reaches the verifier without private API context."""
    app = create_runtime_api_app(cas_root=tmp_path / "cas", core_runs_root=tmp_path / "runs")
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/public-decisions/verification",
            params={"record_id": "eyJwYWNrZXQiOnt9fQ.deadbeef"},
        )
    assert response.status_code == 200
    result = response.json()
    assert result["report_authentication"] == "invalid"
    assert "client_token_not_server_issued" in result["reason_codes"]
    assert result["public_document"] is None
    assert result["promoted_record"] is None


def test_public_verification_does_not_make_private_run_routes_public(tmp_path: Path) -> None:
    """The anonymous exception is restricted to the read-only verifier route."""
    app = create_runtime_api_app(cas_root=tmp_path / "cas", core_runs_root=tmp_path / "runs")
    with TestClient(app) as client:
        response = client.get("/api/v1/runs")
    assert response.status_code == 401


def _configure_verification_issuer(tmp_path, monkeypatch):
    import json

    from polisyos.core.artifacts import KeyPair

    pair = KeyPair.generate()
    private = tmp_path / "report-private.pem"
    private.write_bytes(pair.private_pem())
    private.chmod(0o600)
    (tmp_path / "report-public.pem").write_bytes(pair.public_pem())
    config = tmp_path / "report-issuer.json"
    config.write_text(
        json.dumps(
            {
                "issuer_id": "runtime-report-issuer",
                "private_key_path": "report-private.pem",
                "trusted_keys": [
                    {
                        "public_key_path": "report-public.pem",
                        "issuer_id": "runtime-report-issuer",
                        "purposes": ["public_decision_verification_record"],
                    }
                ],
            }
        )
    )
    monkeypatch.setenv("POLISYOS_PUBLIC_VERIFICATION_CONFIG", str(config))
    return config


def test_owned_run_packet_is_redacted_issued_and_publicly_verified(
    runtime_api_env, tmp_path, monkeypatch
):
    """Actual HTTP issuance resolves the private run and authenticates its projection."""
    from polisyos.core.security.identity import PolicyOSRole
    from tests.unit.runtime.http.test_runtime_api_authz import (
        _AllowOPA,
        _build_secure_client,
        _claims,
    )

    _configure_verification_issuer(tmp_path, monkeypatch)
    client, cell, provider = _build_secure_client(
        runtime_api_env, opa_client=_AllowOPA(), claims_by_token={}
    )
    provider.put_claim(
        "report-admin",
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="report-admin",
            roles=frozenset({PolicyOSRole.ADMIN}),
        ),
    )
    from polisyos.core.artifacts import ArtifactID, FileSystemCAS

    FileSystemCAS(runtime_api_env["cas_root"]).record_artifact_owner(
        ArtifactID.model_validate(runtime_api_env["decision_packet_artifact_id"]),
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=cell.cell_id,
    )
    with client:
        issued = client.post(
            f"/api/v1/runs/{runtime_api_env['core_run_id']}/public-verification-record",
            headers={"Authorization": "Bearer report-admin"},
        )
        assert issued.status_code == 201, issued.text
        locator = issued.json()
        assert locator["public_path"] == f"/public/decisions/{locator['record_id']}"
        response = client.get(
            "/api/v1/public-decisions/verification", params={"record_id": locator["record_id"]}
        )
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["report_authentication"] == "verified"
        assert result["cryptographic_signature"] == "valid"
        assert result["decision_id"] == runtime_api_env["core_run_id"]
        document = result["public_document"]
        assert document["run_id"] == runtime_api_env["core_run_id"]
        assert document["authority_role"] == "projection_only"
        assert document["public_export_classification"] == "public_redacted_projection"
        assert document["artifacts"]["decision_packet"]
        assert result["promoted_record"] is None
        assert set(result["dimensions"].values()) == {"not_established"}
        assert response.headers["cache-control"] == "no-store"
        import json

        root = runtime_api_env["cas_root"] / "runtime" / "public-verification"
        entry = json.loads((root / "issued" / f"{locator['record_id']}.json").read_bytes())
        evidence = FileSystemCAS(root / "cas")
        ref = ArtifactID.model_validate(entry["record_artifact_ref"])
        signature = evidence.get_signature(ref)
        assert signature is not None
        evidence.put_signature(ref, signature.model_copy(update={"signature_hex": "00" * 64}))
        refused = client.get(
            "/api/v1/public-decisions/verification", params={"record_id": locator["record_id"]}
        ).json()
        assert refused["report_authentication"] == "invalid"
        assert refused["cryptographic_signature"] == "invalid"
        assert "record_signature_invalid" in refused["reason_codes"]
        assert refused["public_document"] is None


def test_foreign_run_and_client_document_cannot_issue(runtime_api_env, tmp_path, monkeypatch):
    """A real issuer cannot be used to sign an unrelated tenant or caller body."""
    from polisyos.core.security.identity import PolicyOSRole
    from tests.unit.runtime.http.test_runtime_api_authz import (
        _AllowOPA,
        _build_secure_client,
        _claims,
    )

    _configure_verification_issuer(tmp_path, monkeypatch)
    client, cell, provider = _build_secure_client(
        runtime_api_env, opa_client=_AllowOPA(), claims_by_token={}
    )
    provider.put_claim(
        "report-admin",
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="report-admin",
            roles=frozenset({PolicyOSRole.ADMIN}),
        ),
    )
    with client:
        service = client.app.state.runtime_container.public_decision_verification_service
        for run_id, body in [
            (runtime_api_env["cross_tenant_run_id"], None),
            (runtime_api_env["core_run_id"], {"title": "invented", "verified": True}),
        ]:
            response = client.post(
                f"/api/v1/runs/{run_id}/public-verification-record",
                headers={"Authorization": "Bearer report-admin"},
                json=body,
            )
            assert response.status_code in {403, 422}, response.text
            assert service.issued_record_ids() == ()


def test_public_export_refusal_prevents_record_and_link_issuance(
    runtime_api_env, tmp_path, monkeypatch
):
    """A stored packet with a blocked workflow reaches the real export refusal."""
    import json

    from polisyos.core.artifacts import ArtifactID, ArtifactWriteOptions, FileSystemCAS
    from polisyos.core.run.context import RunContext
    from polisyos.core.security.identity import PolicyOSRole
    from tests.unit.runtime.http.test_runtime_api_authz import (
        _AllowOPA,
        _build_secure_client,
        _claims,
    )

    _configure_verification_issuer(tmp_path, monkeypatch)
    client, cell, provider = _build_secure_client(
        runtime_api_env, opa_client=_AllowOPA(), claims_by_token={}
    )
    provider.put_claim(
        "report-admin",
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="report-admin",
            roles=frozenset({PolicyOSRole.ADMIN}),
        ),
    )
    store = FileSystemCAS(runtime_api_env["cas_root"])
    source = json.loads(
        store.get_bytes(ArtifactID.model_validate(runtime_api_env["decision_packet_artifact_id"]))
    )
    boundary = source["authority_boundary"]
    boundary["authoritative_for"] = [
        purpose for purpose in boundary["authoritative_for"] if purpose != "publication"
    ]
    boundary["may_not_use_for"].append("publication")
    for surface in ("export", "public_packet"):
        source["authority_surface_packet"]["surfaces"][surface]["authority_result"] = "blocked"
    source["run_id"] = "R_report_publication_forbidden"
    packet = store.put_json(
        source,
        ArtifactWriteOptions(kind="scientist.decision_packet", media_type="application/json"),
    )
    store.record_artifact_owner(
        packet.artifact_id, tenant_id=runtime_api_env["tenant_a"], cell_id=cell.cell_id
    )
    registry = store.put_json(
        {"purpose": "report-negative-source"},
        ArtifactWriteOptions(kind="core.registry_bundle", media_type="application/json"),
    )
    run = RunContext.start(
        store=store,
        registry_bundle=registry,
        run_id=source["run_id"],
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=cell.cell_id,
    )
    run.add_output(packet)
    run.finalize(status="completed")
    with client:
        refused = client.post(
            f"/api/v1/runs/{source['run_id']}/public-verification-record",
            headers={"Authorization": "Bearer report-admin"},
        )
        assert refused.status_code == 409, refused.text
        assert refused.json()["detail"] == "authority_surface_blocked"
        assert (
            client.app.state.runtime_container.public_decision_verification_service.issued_record_ids()
            == ()
        )


def test_changed_source_bytes_cannot_issue_under_unchanged_run_reference(
    runtime_api_env, tmp_path, monkeypatch
):
    """Valid JSON at an owned but corrupted CAS address cannot become a new report."""
    from polisyos.core.artifacts import ArtifactID, FileSystemCAS
    from polisyos.core.security.identity import PolicyOSRole
    from tests.unit.runtime.http.test_runtime_api_authz import (
        _align_decision_packet_owner,
        _AllowOPA,
        _build_secure_client,
        _claims,
    )

    _configure_verification_issuer(tmp_path, monkeypatch)
    client, cell, provider = _build_secure_client(
        runtime_api_env, opa_client=_AllowOPA(), claims_by_token={}
    )
    provider.put_claim(
        "report-admin",
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="report-admin",
            roles=frozenset({PolicyOSRole.ADMIN}),
        ),
    )
    _align_decision_packet_owner(runtime_api_env, cell_id=cell.cell_id)
    store = FileSystemCAS(runtime_api_env["cas_root"])
    path, _ = store.get_paths(
        ArtifactID.model_validate(runtime_api_env["decision_packet_artifact_id"])
    )
    original = path.read_bytes()
    with client:
        loaded = client.get(
            f"/api/v1/runs/{runtime_api_env['core_run_id']}",
            headers={"Authorization": "Bearer report-admin"},
        )
        assert loaded.status_code == 200, loaded.text
        path.chmod(0o644)
        path.write_bytes(original + b" ")
        response = client.post(
            f"/api/v1/runs/{runtime_api_env['core_run_id']}/public-verification-record",
            headers={"Authorization": "Bearer report-admin"},
        )
        assert response.status_code == 409, response.text
        assert response.json()["detail"] == "public_document_source_unavailable"
        assert (
            client.app.state.runtime_container.public_decision_verification_service.issued_record_ids()
            == ()
        )

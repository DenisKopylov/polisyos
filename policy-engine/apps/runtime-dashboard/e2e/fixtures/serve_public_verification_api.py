"""Run the real Runtime API with an explicitly test-only verification-report key."""

from __future__ import annotations

import argparse
import io
import json
import os
import secrets
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import uvicorn
from fastapi import HTTPException, Request

from polisyos.core import artifacts
from polisyos.runtime.http.app import create_runtime_api_app


def main() -> None:
    """Issue a real report fixture, expose its scratch coordinates, and serve Runtime."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture-root", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8017)
    args = parser.parse_args()
    root = args.fixture_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    station = Path(tempfile.mkdtemp(prefix="report-fixture-", dir=root))
    pair = artifacts.KeyPair.generate()
    private_key = station / "report-private.pem"
    private_key.write_bytes(pair.private_pem())
    private_key.chmod(0o600)
    (station / "report-public.pem").write_bytes(pair.public_pem())
    configuration = station / "report-configuration.json"
    configuration.write_text(
        json.dumps(
            {
                "issuer_id": "browser-test-verification-report-issuer",
                "private_key_path": "report-private.pem",
                "trusted_keys": [
                    {
                        "public_key_path": "report-public.pem",
                        "issuer_id": "browser-test-verification-report-issuer",
                        "purposes": ["public_decision_verification_record"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    os.environ["POLISYOS_PUBLIC_VERIFICATION_CONFIG"] = str(configuration)
    cas_root = station / "runtime-cas"
    app = create_runtime_api_app(
        cas_root=cas_root,
        core_runs_root=station / "runs",
        allow_fixture_identity=False,
    )
    service = app.state.runtime_container.public_decision_verification_service
    title = "Candidate document from the real verification service"
    record_id = service.issue(
        decision_id="browser-test-candidate",
        public_document={"title": title, "candidate_only": True},
        issued_at=datetime.now(UTC),
    )
    verified = service.verify(record_id)
    if verified.report_authentication != "verified" or verified.promoted_record is not None:
        raise RuntimeError("browser fixture requires an authenticated report without promotion")
    verification_root = cas_root / "runtime" / "public-verification"
    entry = json.loads((verification_root / "issued" / f"{record_id}.json").read_bytes())
    # This isolated fixture is the deliberate non-cooperating CAS actor used
    # by the browser's signature-corruption probe. No filesystem path crosses
    # the fixture metadata/API boundary.
    store = artifacts.FileSystemCAS(verification_root / "cas")
    record_ref = artifacts.ArtifactID.model_validate(entry["record_artifact_ref"])
    blob_buffer = io.BytesIO()
    record_blob_receipt = store.copy_member_to(record_ref, "blob", blob_buffer)
    signature_path = store._sig_path(
        record_ref,
    )
    original_signature = store.get_signature_bytes(record_ref)
    original_mode = signature_path.stat().st_mode & 0o777
    fixture_token = secrets.token_urlsafe(24)

    async def mutate_signature(action: str, request: Request) -> dict[str, object]:
        if not secrets.compare_digest(
            request.headers.get("x-policyos-fixture-token", ""),
            fixture_token,
        ):
            raise HTTPException(status_code=404)
        if action == "damage":
            damaged = json.loads(original_signature)
            damaged["signature_hex"] = "00" * 64
            signature_path.chmod(0o600)
            signature_path.write_text(json.dumps(damaged), encoding="utf-8")
        elif action == "restore":
            signature_path.write_bytes(original_signature)
            signature_path.chmod(original_mode)
        else:
            raise HTTPException(status_code=404)
        after_buffer = io.BytesIO()
        after_receipt = store.copy_member_to(record_ref, "blob", after_buffer)
        if (
            after_receipt.sha256 != record_blob_receipt.sha256
            or after_receipt.byte_size != record_blob_receipt.byte_size
        ):
            raise RuntimeError("fixture_signature_mutation_changed_record_blob")
        return {
            "ok": True,
            "record_blob_sha256": after_receipt.sha256,
            "record_blob_byte_size": after_receipt.byte_size,
        }

    app.add_api_route(
        "/__test__/signature/{action}",
        mutate_signature,
        methods=["POST"],
        include_in_schema=False,
    )
    metadata = {
        "record_id": record_id,
        "title": title,
        "record_blob_sha256": record_blob_receipt.sha256,
        "record_blob_byte_size": record_blob_receipt.byte_size,
        "fixture_control_url": f"http://127.0.0.1:{args.port}/__test__/signature",
        "fixture_token": fixture_token,
    }
    (root / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()

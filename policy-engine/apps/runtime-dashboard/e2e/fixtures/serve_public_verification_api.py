"""Run the real Runtime API with an explicitly test-only verification-report key."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import uvicorn

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
    store = artifacts.FileSystemCAS(verification_root / "cas")
    record_blob, _ = store.get_paths(
        artifacts.ArtifactID.model_validate(entry["record_artifact_ref"])
    )
    metadata = {
        "record_id": record_id,
        "title": title,
        "record_blob_path": str(record_blob),
        "signature_path": str(record_blob.with_suffix(".sig")),
    }
    (root / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()

"""Public adapters foundry bridge module API."""
from __future__ import annotations

import json
import os
from contextlib import contextmanager
from pathlib import Path

from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.foundry import (
    CompileRequest,
    CompileResult,
    DerivedArtifact,
    ExecuteRequest,
    ExecuteResult,
)
from polisyos.core.security.settings import SecuritySettings, get_security_settings
from polisyos.core.security.tee import AttestationResult
from polisyos.core.security.tee_middleware import TEEGatekeeper
from polisyos.foundry.compile.api import compile as compile_foundry
from polisyos.foundry.execute.api import execute as execute_foundry
from polisyos.scientist.engine.context import FoundryPort


class DefaultFoundryPort(FoundryPort):
    """Default Foundry adapter for Scientist engine (E1.7)."""

    def __init__(
        self,
        *,
        settings: SecuritySettings | None = None,
        gatekeeper: TEEGatekeeper | None = None,
    ) -> None:
        self._settings = settings or get_security_settings()
        self._gatekeeper = gatekeeper
        if self._gatekeeper is None and self._settings.tee_enabled:
            self._gatekeeper = TEEGatekeeper.from_settings(settings=self._settings)

    def compile(self, store: FileSystemCAS, request: CompileRequest) -> CompileResult:
        return compile_foundry(store, request)

    def execute(self, store: FileSystemCAS, request: ExecuteRequest) -> ExecuteResult:
        attestation: AttestationResult | None = None
        if self._gatekeeper is not None:
            attestation = self._gatekeeper.enforce(
                node_id=os.getenv("HOSTNAME"),
                nonce=os.urandom(32),
            )

        with _tee_env_scope(attestation):
            result = execute_foundry(store, request)

        if attestation is None:
            return _maybe_attach_sbom(result=result, store=store, settings=self._settings)

        attestation_ref = _persist_attestation(store, attestation)
        derived = list(result.derived_refs)
        derived.append(DerivedArtifact(role="tee_attestation", ref=attestation_ref))
        notes = list(result.notes)
        notes.append(f"tee_attestation:{attestation.status.value}")
        with_attestation = result.model_copy(update={"derived_refs": derived, "notes": notes})
        return _maybe_attach_sbom(result=with_attestation, store=store, settings=self._settings)


def _persist_attestation(store: FileSystemCAS, attestation: AttestationResult) -> ArtifactRef:
    return store.put_json(
        attestation.model_dump(mode="json"),
        PutOptions(
            kind="security.tee_attestation",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.security.AttestationResult", version="1.0"),
        ),
    )


def _maybe_attach_sbom(
    *,
    result: ExecuteResult,
    store: FileSystemCAS,
    settings: SecuritySettings,
) -> ExecuteResult:
    if not settings.POLISYOS_SBOM_ENABLED:
        return result

    sbom_path = settings.POLISYOS_SBOM_PATH.strip() or os.getenv("POLISYOS_SBOM_PATH", "").strip()
    if not sbom_path:
        return result

    path = Path(sbom_path)
    if not path.exists() or not path.is_file():
        return result

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return result

    sbom_ref = store.put_json(
        payload,
        PutOptions(
            kind="security.sbom",
            media_type="application/vnd.cyclonedx+json",
            schema=SchemaInfo(name="cyclonedx", version=str(payload.get("specVersion", "1.5"))),
        ),
    )
    derived = list(result.derived_refs)
    derived.append(DerivedArtifact(role="sbom", ref=sbom_ref))
    notes = list(result.notes)
    notes.append("sbom:attached")
    return result.model_copy(update={"derived_refs": derived, "notes": notes})


@contextmanager
def _tee_env_scope(attestation: AttestationResult | None):
    if attestation is None:
        yield
        return

    keys = {
        "POLISYOS_TEE_ATTESTATION_STATUS": attestation.status.value,
        "POLISYOS_TEE_PLATFORM": (
            attestation.platform.value if attestation.platform is not None else ""
        ),
        "POLISYOS_TEE_REPORT_HASH": attestation.report_hash or "",
        "POLISYOS_TEE_MEASUREMENT": attestation.measurement or "",
        "POLISYOS_TEE_TCB_VERSION": (
            str(attestation.tcb_version) if attestation.tcb_version is not None else ""
        ),
        "POLISYOS_TEE_VERIFIED_AT": attestation.verified_at.isoformat(),
    }
    old_values = {key: os.environ.get(key) for key in keys}
    try:
        for key, value in keys.items():
            os.environ[key] = value
        yield
    finally:
        for key, value in old_values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


__all__ = ["DefaultFoundryPort"]

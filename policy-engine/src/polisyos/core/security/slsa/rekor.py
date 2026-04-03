"""Public slsa rekor module API."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import httpx

from polisyos.core.canon import content_hash

from .config import SLSAConfig, SlsaMode


@dataclass(frozen=True)
class RekorEntry:
    """Transparency log entry metadata persisted into audit package."""

    mode: str
    log_id: str
    log_index: int
    integrated_time: int
    payload_sha256: str
    verification_url: str
    created_at: str


class RekorClient:
    """Write attestation references to local/remote transparency log."""

    def __init__(self, config: SLSAConfig) -> None:
        self._config = config

    def upload(
        self,
        *,
        attestation_bytes: bytes,
        signature_hex: str,
        certificate_pem: str,
    ) -> RekorEntry | None:
        if self._config.mode == SlsaMode.OFF:
            return None

        payload_sha = _sha256(attestation_bytes)

        if self._config.mode == SlsaMode.LOCAL:
            return self._append_local_entry(
                payload_sha256=payload_sha,
                signature_hex=signature_hex,
                certificate_pem=certificate_pem,
            )

        if self._config.mode in {SlsaMode.PRIVATE, SlsaMode.PUBLIC}:
            return self._upload_remote(
                payload_sha256=payload_sha,
                attestation_bytes=attestation_bytes,
                signature_hex=signature_hex,
                certificate_pem=certificate_pem,
            )

        return None

    def _append_local_entry(
        self,
        *,
        payload_sha256: str,
        signature_hex: str,
        certificate_pem: str,
    ) -> RekorEntry:
        path = Path(self._config.local_transparency_log)
        path.parent.mkdir(parents=True, exist_ok=True)

        last_idx = -1
        if path.exists():
            for line in path.read_text("utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                idx = data.get("log_index")
                if isinstance(idx, int):
                    last_idx = max(last_idx, idx)

        log_index = last_idx + 1
        log_id = str(uuid.uuid4())
        now = int(datetime.now(timezone.utc).timestamp())
        created_at = _utc_now_iso()

        record = {
            "mode": "local",
            "log_id": log_id,
            "log_index": log_index,
            "integrated_time": now,
            "payload_sha256": payload_sha256,
            "signature_sha256": _sha256(signature_hex.encode("utf-8")),
            "certificate_sha256": _sha256(certificate_pem.encode("utf-8")),
            "created_at": created_at,
        }

        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True, ensure_ascii=True))
            handle.write("\n")
            handle.flush()

        return RekorEntry(
            mode="local",
            log_id=log_id,
            log_index=log_index,
            integrated_time=now,
            payload_sha256=payload_sha256,
            verification_url="",
            created_at=created_at,
        )

    def _upload_remote(
        self,
        *,
        payload_sha256: str,
        attestation_bytes: bytes,
        signature_hex: str,
        certificate_pem: str,
    ) -> RekorEntry:
        import base64

        entry = {
            "apiVersion": "0.0.2",
            "kind": "intoto",
            "spec": {
                "content": {
                    "envelope": base64.b64encode(attestation_bytes).decode("utf-8"),
                    "hash": {"algorithm": "sha256", "value": payload_sha256},
                },
                "publicKey": base64.b64encode(certificate_pem.encode("utf-8")).decode("utf-8"),
                "signature": base64.b64encode(bytes.fromhex(signature_hex)).decode("utf-8"),
            },
        }

        response = httpx.post(
            f"{self._config.rekor_url.rstrip('/')}/api/v1/log/entries",
            json=entry,
            timeout=self._config.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()

        if not isinstance(payload, dict) or not payload:
            raise RuntimeError("Rekor response is empty")

        entry_uuid = next(iter(payload))
        item = payload[entry_uuid]
        if not isinstance(item, dict):
            raise RuntimeError("Rekor response format is invalid")

        return RekorEntry(
            mode="remote",
            log_id=str(item.get("logID") or entry_uuid),
            log_index=int(item.get("logIndex") or -1),
            integrated_time=int(item.get("integratedTime") or 0),
            payload_sha256=payload_sha256,
            verification_url=f"{self._config.rekor_url.rstrip('/')}/api/v1/log/entries/{entry_uuid}",
            created_at=_utc_now_iso(),
        )



def _sha256(payload: bytes) -> str:
    return content_hash(payload)



def _utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )

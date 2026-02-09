"""NormPack resolution interfaces for informed critic and constitution generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.ir.norm_pack import NormPack


@runtime_checkable
class NormPackLoader(Protocol):
    """Resolves a norm pack for a specific context."""

    def load_for_context(
        self,
        *,
        jurisdiction: str,
        domain: str | None = None,
        as_of: str | None = None,
    ) -> NormPack | None:
        ...


@dataclass(slots=True)
class StaticNormPackLoader:
    """Test-friendly loader returning one preconfigured norm pack."""

    norm_pack: NormPack | None = None

    def load_for_context(
        self,
        *,
        jurisdiction: str,
        domain: str | None = None,
        as_of: str | None = None,
    ) -> NormPack | None:
        del jurisdiction, domain, as_of
        return self.norm_pack


class CASNormPackLoader:
    """Loads norm packs from CAS using direct ref or jurisdiction/domain lookup map."""

    def __init__(
        self,
        cas: FileSystemCAS,
        *,
        default_ref: str | None = None,
        refs_by_context: dict[str, str] | None = None,
    ) -> None:
        self._cas = cas
        self._default_ref = default_ref
        self._refs_by_context = dict(refs_by_context or {})

    def load_for_context(
        self,
        *,
        jurisdiction: str,
        domain: str | None = None,
        as_of: str | None = None,
    ) -> NormPack | None:
        del as_of

        keys: list[str] = []
        j = (jurisdiction or "").strip().lower()
        d = (domain or "").strip().lower()
        if j and d:
            keys.append(f"{j}:{d}")
        if j:
            keys.append(j)
        if d:
            keys.append(f"*:{d}")

        artifact_ref: str | None = None
        for key in keys:
            artifact_ref = self._refs_by_context.get(key)
            if artifact_ref:
                break
        if artifact_ref is None:
            artifact_ref = self._default_ref
        if artifact_ref is None:
            return None

        return self._load_from_cas(artifact_ref)

    def _load_from_cas(self, artifact_id: str) -> NormPack | None:
        try:
            aid = ArtifactID.model_validate(artifact_id)
            payload = from_canonical_bytes(self._cas.get_bytes(aid))
            return NormPack.model_validate(payload)
        except Exception:
            return None


__all__ = [
    "CASNormPackLoader",
    "NormPackLoader",
    "StaticNormPackLoader",
]

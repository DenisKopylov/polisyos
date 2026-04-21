"""Certificate resolution helpers for dispatcher/runtime integration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from polisyos.foundry.methods.base import ComputeBackend
from polisyos.foundry.methods.equivalence.protocol import (
    CrossBackendEquivalenceCertificate,
)

_default_equivalence_resolver: "EquivalenceCertificateResolver | None" = None


@dataclass(frozen=True, slots=True)
class ResolvedEquivalenceCertificate:
    """Resolved certificate plus external references needed for attachment."""

    certificate_ref: str
    certificate: CrossBackendEquivalenceCertificate
    attestation_ref: str | None = None


class EquivalenceCertificateResolver(Protocol):
    """Resolve one certificate for a concrete method/backend pair."""

    def resolve(
        self,
        *,
        method_fqn: str,
        source_backend: ComputeBackend,
        target_backend: ComputeBackend,
    ) -> ResolvedEquivalenceCertificate | None:
        ...


class InMemoryEquivalenceCertificateRegistry:
    """Small in-memory registry suitable for tests and local phase-0 wiring."""

    def __init__(
        self,
        entries: tuple[ResolvedEquivalenceCertificate, ...] = (),
    ) -> None:
        self._entries: list[ResolvedEquivalenceCertificate] = list(entries)

    def register(
        self,
        *,
        certificate_ref: str,
        certificate: CrossBackendEquivalenceCertificate,
        attestation_ref: str | None = None,
    ) -> None:
        self._entries.append(
            ResolvedEquivalenceCertificate(
                certificate_ref=str(certificate_ref),
                certificate=certificate,
                attestation_ref=None if attestation_ref is None else str(attestation_ref),
            )
        )

    def resolve(
        self,
        *,
        method_fqn: str,
        source_backend: ComputeBackend,
        target_backend: ComputeBackend,
    ) -> ResolvedEquivalenceCertificate | None:
        for entry in reversed(self._entries):
            envelope = entry.certificate.runtime_envelope
            if entry.certificate.method_fqn != method_fqn:
                continue
            if envelope.source_backend != source_backend:
                continue
            if envelope.target_backend != target_backend:
                continue
            return entry
        return None


def get_default_equivalence_resolver() -> EquivalenceCertificateResolver | None:
    """Return the process-global resolver used by the default dispatcher path."""
    return _default_equivalence_resolver


def set_default_equivalence_resolver(
    resolver: EquivalenceCertificateResolver | None,
) -> None:
    """Register the process-global resolver used by default dispatcher instances."""
    global _default_equivalence_resolver
    _default_equivalence_resolver = resolver


def reset_default_equivalence_resolver() -> None:
    """Clear the process-global resolver used by the default dispatcher path."""
    set_default_equivalence_resolver(None)


__all__ = [
    "EquivalenceCertificateResolver",
    "get_default_equivalence_resolver",
    "InMemoryEquivalenceCertificateRegistry",
    "reset_default_equivalence_resolver",
    "ResolvedEquivalenceCertificate",
    "set_default_equivalence_resolver",
]

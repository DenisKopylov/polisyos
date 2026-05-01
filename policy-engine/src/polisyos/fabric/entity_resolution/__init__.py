"""Entity-resolution helpers and CAS-backed candidate match persistence."""

from .models import (
    EntityMatchBatch,
    EntityMatchCandidate,
    EntityMatchEvidence,
    EntityOverrideAuditRecord,
    EntityOverrideEnvelope,
    EntityRecord,
)
from .resolver import ProbabilisticEntityResolver
from .store import EntityMatchStore

__all__ = [
    "EntityMatchBatch",
    "EntityMatchCandidate",
    "EntityMatchEvidence",
    "EntityMatchStore",
    "EntityOverrideAuditRecord",
    "EntityOverrideEnvelope",
    "EntityRecord",
    "ProbabilisticEntityResolver",
]

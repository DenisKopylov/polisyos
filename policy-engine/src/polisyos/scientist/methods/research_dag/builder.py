"""Builder and sanitization helpers for Scientist research DAGs."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.canon import content_hash, fingerprint
from polisyos.scientist.methods.research_dag.models import (
    FORBIDDEN_PUBLIC_METADATA_TOKENS,
    ResearchDAGArtifact,
    ResearchDAGEdge,
    ResearchDAGNode,
    ResearchEdgeType,
    ResearchNodeType,
    is_hidden_artifact_ref,
)

PROMPT_INJECTION_PATTERNS: tuple[str, ...] = (
    "ignore previous",
    "ignore all previous",
    "system prompt",
    "developer message",
    "developer prompt",
    "do not follow",
    "reveal hidden",
    "exfiltrate",
    "jailbreak",
)

_SAFE_SCALAR_TYPES = (str, int, bool, type(None))


def sanitize_public_metadata(value: Any) -> Any:
    """Drop hidden eval/transcript keys and keep metadata JSON-safe."""

    if isinstance(value, dict):
        output: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            lowered = key_text.lower()
            if any(token in lowered for token in FORBIDDEN_PUBLIC_METADATA_TOKENS):
                continue
            output[key_text] = sanitize_public_metadata(item)
        return output
    if isinstance(value, list | tuple):
        return [sanitize_public_metadata(item) for item in value]
    if isinstance(value, float):
        return str(value)
    if isinstance(value, _SAFE_SCALAR_TYPES):
        return value
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            return sanitize_public_metadata(model_dump(mode="json"))
        except (TypeError, ValueError):
            return str(value)
    return str(value)


def untrusted_content_summary(text: str) -> tuple[dict[str, Any], list[str]]:
    """Return non-instruction-bearing metadata for untrusted external text."""

    labels = ["untrusted_tool_output", "raw_content_redacted"]
    lowered = text.lower()
    if any(pattern in lowered for pattern in PROMPT_INJECTION_PATTERNS):
        labels.append("prompt_injection_candidate")
    return (
        {
            "untrusted_content_fingerprint": content_hash(text, prefix=True),
            "untrusted_content_char_count": len(text),
            "untrusted_content_redacted": True,
        },
        labels,
    )


def stable_fingerprint(value: Any) -> str:
    """Hash a JSON-like value without storing it in the DAG."""

    safe_value = sanitize_public_metadata(value)
    return fingerprint(safe_value, prefix=True)


def sanitize_public_artifact_refs(refs: list[ArtifactRef]) -> list[ArtifactRef]:
    """Drop hidden/private eval refs from the public Research DAG."""

    output: list[ArtifactRef] = []
    seen: set[str] = set()
    for ref in refs:
        if is_hidden_artifact_ref(ref):
            continue
        artifact_id = str(ref.artifact_id)
        if artifact_id in seen:
            continue
        seen.add(artifact_id)
        output.append(ref)
    return output


class ResearchDAGBuilder:
    """Append-only helper for constructing a validated research DAG."""

    def __init__(
        self,
        *,
        run_id: str,
        workflow_id: str,
        claim_ledger_ref: ArtifactRef | None = None,
        created_at: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.run_id = run_id
        self.workflow_id = workflow_id
        self.claim_ledger_ref = claim_ledger_ref
        self.created_at = created_at or datetime.now(UTC)
        self.metadata = sanitize_public_metadata(metadata or {})
        self._nodes: list[ResearchDAGNode] = []
        self._edges: list[ResearchDAGEdge] = []
        self._node_ids: set[str] = set()

    @property
    def nodes(self) -> tuple[ResearchDAGNode, ...]:
        return tuple(self._nodes)

    @property
    def edges(self) -> tuple[ResearchDAGEdge, ...]:
        return tuple(self._edges)

    def add_node(
        self,
        *,
        node_type: ResearchNodeType,
        producer: str,
        summary: str,
        node_id: str | None = None,
        artifact_refs: list[ArtifactRef] | None = None,
        claim_ids: list[str] | None = None,
        input_fingerprint: str | None = None,
        output_fingerprint: str | None = None,
        safety_labels: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        untrusted_text: str | None = None,
    ) -> ResearchDAGNode:
        safe_metadata = sanitize_public_metadata(metadata or {})
        safe_artifact_refs = sanitize_public_artifact_refs(artifact_refs or [])
        redacted_artifact_ref_count = len(artifact_refs or []) - len(safe_artifact_refs)
        if redacted_artifact_ref_count > 0:
            safe_metadata["redacted_artifact_ref_count"] = redacted_artifact_ref_count
        labels = list(safety_labels or [])
        if untrusted_text is not None:
            untrusted_metadata, untrusted_labels = untrusted_content_summary(untrusted_text)
            safe_metadata.update(untrusted_metadata)
            labels.extend(untrusted_labels)
            output_fingerprint = output_fingerprint or untrusted_metadata[
                "untrusted_content_fingerprint"
            ]
        resolved_node_id = self._unique_node_id(
            node_id
            or _node_id_from_parts(
                self.workflow_id,
                node_type.value,
                producer,
                str(len(self._nodes) + 1),
            )
        )
        node = ResearchDAGNode(
            node_id=resolved_node_id,
            node_type=node_type,
            run_id=self.run_id,
            workflow_id=self.workflow_id,
            producer=producer,
            summary=_compact_summary(summary),
            artifact_refs=safe_artifact_refs,
            claim_ids=list(dict.fromkeys(claim_ids or [])),
            input_fingerprint=input_fingerprint,
            output_fingerprint=output_fingerprint,
            safety_labels=sorted(set(labels)),
            metadata=safe_metadata,
        )
        self._nodes.append(node)
        self._node_ids.add(node.node_id)
        return node

    def add_edge(
        self,
        *,
        source_node_id: str,
        target_node_id: str,
        edge_type: ResearchEdgeType,
        claim_ids: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ResearchDAGEdge:
        edge = ResearchDAGEdge(
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            edge_type=edge_type,
            claim_ids=list(dict.fromkeys(claim_ids or [])),
            metadata=sanitize_public_metadata(metadata or {}),
        )
        self._edges.append(edge)
        return edge

    def artifact(self, *, metadata: dict[str, Any] | None = None) -> ResearchDAGArtifact:
        merged_metadata = {**self.metadata, **sanitize_public_metadata(metadata or {})}
        return ResearchDAGArtifact(
            run_id=self.run_id,
            workflow_id=self.workflow_id,
            nodes=list(self._nodes),
            edges=list(self._edges),
            claim_ledger_ref=self.claim_ledger_ref,
            hidden_content_redacted=True,
            created_at=self.created_at,
            metadata=merged_metadata,
        )

    def _unique_node_id(self, base_id: str) -> str:
        base = _slug(base_id) or "node"
        candidate = base
        index = 2
        while candidate in self._node_ids:
            candidate = f"{base}-{index}"
            index += 1
        return candidate


def _node_id_from_parts(*parts: str) -> str:
    return ":".join(_slug(part) for part in parts if _slug(part))


def _slug(value: str) -> str:
    lowered = value.strip().lower()
    lowered = re.sub(r"[^a-z0-9_.:-]+", "-", lowered)
    return lowered.strip("-")


def _compact_summary(summary: str, *, max_chars: int = 280) -> str:
    text = " ".join(str(summary).split())
    if not text:
        return "Research DAG node"
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


__all__ = [
    "PROMPT_INJECTION_PATTERNS",
    "ResearchDAGBuilder",
    "sanitize_public_artifact_refs",
    "sanitize_public_metadata",
    "stable_fingerprint",
    "untrusted_content_summary",
]

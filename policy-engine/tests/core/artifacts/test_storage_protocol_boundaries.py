from __future__ import annotations

import ast
from pathlib import Path
from typing import TYPE_CHECKING

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactManifest, ArtifactRef, IntegrityInfo
from polisyos.core.artifacts.registry import RegistryBundlePayload
from polisyos.core.canon import content_hash, from_canonical_bytes, to_canonical_bytes
from polisyos.core.compiler.report import CompileReport, put_compile_report, put_link_report
from polisyos.core.registry.builder import build_registry_bundle
from polisyos.core.registry.loader import load_registry_bundle, load_registry_bundle_content
from polisyos.ir.kernel import (
    DEFAULT_CONSTRAINT_REGISTRY,
    DEFAULT_MECHANISM_REGISTRY,
    DEFAULT_MERGE_RULE_REGISTRY,
    DEFAULT_METRIC_REGISTRY,
    DEFAULT_SELECTOR_FIELD_REGISTRY,
    DEFAULT_SLOT_REGISTRY,
    DEFAULT_UNITS_REGISTRY,
)
from polisyos.ir.linker import LinkIssue, LinkIssueCode, LinkReport, LinkSeverity

if TYPE_CHECKING:
    from polisyos.core.artifacts.protocol import ArtifactStore
    from polisyos.core.artifacts.write_contract import ArtifactWriteOptions


REPO_ROOT = Path(__file__).resolve().parents[3]
PROTOCOL_BOUNDARY_FILES = (
    "src/polisyos/core/compiler/report.py",
    "src/polisyos/core/registry/builder.py",
    "src/polisyos/core/registry/builder_from_fragments.py",
    "src/polisyos/core/registry/loader.py",
    "src/polisyos/core/run/context.py",
)


class RecordingArtifactStore:
    """Minimal in-memory ArtifactStore used to verify protocol-only helpers."""

    def __init__(self) -> None:
        self._payloads: dict[str, bytes] = {}
        self._manifests: dict[str, ArtifactManifest] = {}
        self.write_kinds: list[str] = []

    def has(self, artifact_id: ArtifactID) -> bool:
        return str(artifact_id) in self._payloads

    def get_bytes(self, artifact_id: ArtifactID) -> bytes:
        return self._payloads[str(artifact_id)]

    def get_manifest(self, artifact_id: ArtifactID) -> ArtifactManifest:
        return self._manifests[str(artifact_id)]

    def put_bytes(self, data: bytes, opts: ArtifactWriteOptions) -> ArtifactRef:
        artifact_id = ArtifactID.from_sha256_hex(content_hash(data))
        manifest = ArtifactManifest(
            artifact_id=artifact_id,
            kind=opts.kind,
            media_type=opts.media_type,
            byte_size=len(data),
            schema=opts.schema,
            canon=opts.canon,
            inputs=list(opts.inputs or []),
            producer=opts.producer,
            env=opts.env,
            integrity=IntegrityInfo(sha256=artifact_id.hex),
        )
        self._payloads[str(artifact_id)] = data
        self._manifests[str(artifact_id)] = manifest
        self.write_kinds.append(opts.kind)
        return ArtifactRef(
            artifact_id=artifact_id,
            kind=opts.kind,
            media_type=opts.media_type,
        )

    def put_json(
        self,
        obj: object,
        opts: ArtifactWriteOptions,
        canon_spec=None,
    ) -> ArtifactRef:
        return self.put_bytes(to_canonical_bytes(obj, canon_spec), opts)

    def verify(self, artifact_id: ArtifactID):  # pragma: no cover - not used in these tests
        raise NotImplementedError

    def iter_artifact_ids(self) -> list[ArtifactID]:
        return [ArtifactID.model_validate(value) for value in self._payloads]


def test_protocol_boundary_helpers_do_not_import_concrete_cas_details() -> None:
    violations: list[str] = []

    for relative_path in PROTOCOL_BOUNDARY_FILES:
        path = REPO_ROOT / relative_path
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            if node.module != "polisyos.core.artifacts.store":
                continue
            imported = {alias.name for alias in node.names}
            if imported & {"FileSystemCAS", "PutOptions"}:
                violations.append(
                    f"{relative_path}:{node.lineno}: concrete CAS import {sorted(imported)!r}"
                )

    assert not violations, "\n".join(violations)


def test_compiler_report_helpers_accept_protocol_store() -> None:
    store: ArtifactStore = RecordingArtifactStore()
    link_report = LinkReport(
        schema_version="1.0",
        ok=False,
        issues=[
            LinkIssue(
                severity=LinkSeverity.ERROR,
                code=LinkIssueCode.UNKNOWN_SLOT,
                message="missing slot",
            )
        ],
        notes=["link-failed"],
    )

    link_ref = put_link_report(store, link_report)
    compile_ref = put_compile_report(
        store,
        CompileReport(schema_version="1.0", ok=False, link_report_ref=link_ref),
    )

    assert link_ref.kind == "compiler.link_report"
    assert compile_ref.kind == "compiler.compile_report"
    assert store.get_manifest(link_ref.artifact_id).kind == "compiler.link_report"
    assert store.get_manifest(compile_ref.artifact_id).kind == "compiler.compile_report"


def test_registry_bundle_build_and_load_work_with_protocol_store() -> None:
    store: ArtifactStore = RecordingArtifactStore()

    bundle = build_registry_bundle(
        store,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
        constraint_registry=DEFAULT_CONSTRAINT_REGISTRY,
        selector_field_registry=DEFAULT_SELECTOR_FIELD_REGISTRY,
        metric_registry=DEFAULT_METRIC_REGISTRY,
        units_registry=DEFAULT_UNITS_REGISTRY,
    )

    loaded_bundle = load_registry_bundle(store, bundle.bundle_ref)
    loaded_content = load_registry_bundle_content(store, bundle.bundle_ref)
    payload = RegistryBundlePayload.model_validate(
        from_canonical_bytes(store.get_bytes(bundle.bundle_ref.artifact_id))
    )

    assert loaded_bundle.bundle_ref == bundle.bundle_ref
    assert loaded_content.slot_registry.model_dump() == DEFAULT_SLOT_REGISTRY.model_dump()
    assert loaded_content.merge_registry.model_dump() == DEFAULT_MERGE_RULE_REGISTRY.model_dump()
    assert payload.slot_registry == bundle.slot_registry
    assert "core.registry_bundle" in store.write_kinds

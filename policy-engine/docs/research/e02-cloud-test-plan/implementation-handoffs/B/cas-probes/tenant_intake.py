"""Read-only source experiment: real CAS custody versus scoped admission.

Run from policy-engine with PYTHONPATH=src:product. This records behavior; it does
not declare generic byte integrity to be authority eligibility or finding closure.
"""

from __future__ import annotations

import hashlib
import json
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from polisyos.core.artifacts._manifest_lifecycle import ManifestLifecycle
from polisyos.core.artifacts.manifest import (
    ArtifactManifest,
    ArtifactRef,
    ArtifactTenantContextInfo,
)
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.scientist.orchestration.engine.idempotency import NodeResultCache
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state

CASES = (
    ("same-tenant-none-cell", "tenant-a", None, "tenant-a", None),
    ("same-tenant-same-cell", "tenant-a", "cell-a", "tenant-a", "cell-a"),
    ("foreign-tenant", "tenant-a", None, "tenant-b", None),
    ("foreign-cell", "tenant-a", "cell-a", "tenant-a", "cell-b"),
    ("none-cell-to-scoped-cell", "tenant-a", None, "tenant-a", "cell-a"),
    ("scoped-cell-to-none-cell", "tenant-a", "cell-a", "tenant-a", None),
    ("bound-to-passive-custody", "tenant-a", "cell-a", None, None),
    ("unbound-to-scoped-owner", None, None, "tenant-b", "cell-b"),
)


def context(tenant: str | None, cell: str | None) -> ArtifactTenantContextInfo | None:
    return ArtifactTenantContextInfo(tenant_id=tenant, cell_id=cell) if tenant is not None else None


def store(root: Path, tenant: str | None, cell: str | None) -> FileSystemCAS:
    raw = FileSystemCAS(root)
    return raw.for_tenant(tenant, cell_id=cell) if tenant is not None else raw


def observation(
    target: FileSystemCAS,
    ref: ArtifactRef,
    owner_tenant: str | None,
    owner_cell: str | None,
    data: bytes,
    original_manifest: ArtifactManifest,
) -> dict[str, object]:
    index = target._ownership_index
    profile = ManifestLifecycle.profile_sha256(original_manifest)
    owner_args = {"tenant_id": owner_tenant, "cell_id": owner_cell}
    claims = (
        {
            "default": index.is_owned_by(ref.artifact_id, **owner_args),
            "blob": index.is_blob_readable_by(ref.artifact_id, **owner_args),
            "exact_view": index.is_view_owned_by(ref.artifact_id, profile, **owner_args),
        }
        if owner_tenant is not None
        else None
    )
    reopened = store(target.root, owner_tenant, owner_cell)
    return {
        "claims": claims,
        "any_claim": index.has_any_tenant_claim(ref.artifact_id),
        "pending_intent": index._read_transaction_intent(ref.artifact_id) is not None,
        "has_selected": reopened.has(ref),
        "reopened_bytes_equal": reopened.get_bytes(ref) == data,
        "manifest_preserved": reopened.get_manifest(ref) == original_manifest,
        "manifest_context": reopened.get_manifest(ref).tenant_context.model_dump()
        if reopened.get_manifest(ref).tenant_context is not None
        else None,
    }


def matrix(root: Path) -> list[dict[str, object]]:
    records = []
    for label, bound_tenant, bound_cell, owner_tenant, owner_cell in CASES:
        for route in ("archive", "directory", "exact-view"):
            work = root / label / route
            source = FileSystemCAS(work / "source")
            data = f"real filesystem {label} {route}".encode()
            ref = source.put_bytes(
                data,
                PutOptions(
                    kind="probe.tenant-intake",
                    media_type="application/octet-stream",
                    tenant_context=context(bound_tenant, bound_cell),
                ),
            )
            manifest = source.get_manifest(ref)
            target = store(work / "target", owner_tenant, owner_cell)
            record = {
                "case": label,
                "route": route,
                "bound": context(bound_tenant, bound_cell).model_dump() if bound_tenant else None,
                "write_owner": {"tenant_id": owner_tenant, "cell_id": owner_cell}
                if owner_tenant
                else None,
            }
            try:
                if route == "exact-view":
                    exact = ArtifactRef(
                        artifact_id=ref.artifact_id,
                        kind=ref.kind,
                        media_type=ref.media_type,
                        manifest_profile_sha256=ManifestLifecycle.profile_sha256(manifest),
                    )
                    imported = target.import_exact_view(
                        data, source.get_manifest_bytes(ref), artifact_id=exact
                    )
                else:
                    exported = source.export_subgraph(
                        [ref], work / "package", compress=route == "archive"
                    )
                    target.import_subgraph(exported.output_path, verify_integrity=True)
                    imported = ref
                record.update(
                    {
                        "outcome": "accepted",
                        **observation(target, imported, owner_tenant, owner_cell, data, manifest),
                    }
                )
            except Exception as exc:
                record.update(
                    {
                        "outcome": "refused",
                        "exception": type(exc).__name__,
                        "message": str(exc),
                        "any_claim": target._ownership_index.has_any_tenant_claim(ref.artifact_id),
                        "pending_intent": target._ownership_index._read_transaction_intent(
                            ref.artifact_id
                        )
                        is not None,
                        "has_selected": target.has(ref),
                    }
                )
            records.append(record)
    return records


def sibling_puts(root: Path) -> list[dict[str, object]]:
    records = []
    for label, bt, bc, ot, oc in CASES:
        target = store(root / label, ot, oc)
        data = f"sibling generic put {label}".encode()
        record = {
            "case": label,
            "route": "generic-put",
            "bound": context(bt, bc).model_dump() if bt else None,
            "write_owner": {"tenant_id": ot, "cell_id": oc} if ot else None,
        }
        try:
            ref = target.put_bytes(
                data,
                PutOptions(
                    kind="probe.bound-put", media_type="text/plain", tenant_context=context(bt, bc)
                ),
            )
            record.update(
                {
                    "outcome": "accepted",
                    **observation(target, ref, ot, oc, data, target.get_manifest(ref)),
                }
            )
        except Exception as exc:
            record.update(
                {
                    "outcome": "refused",
                    "exception": type(exc).__name__,
                    "message": str(exc),
                    "inventory": [str(aid) for aid in target.iter_artifact_ids()],
                }
            )
        records.append(record)
    return records


def actual_cache_consumer(root: Path) -> list[dict[str, object]]:
    records = []
    for label, bt, bc, ot, oc in CASES[:6]:
        source = FileSystemCAS(root / label / "source")
        source_cache = NodeResultCache(source, run_id="probe-run", tenant_context=context(bt, bc))
        outcome = NodeOutcome(
            status="ok",
            state=branch_state(ExperimentState(run_id="probe-run"), write_paths=()).state,
        )
        ref = source_cache.put("c" * 64, node_id="scientist.node_test@1.0.0", outcome=outcome)
        target = store(root / label / "target", ot, oc)
        try:
            imported = target.import_exact_view(
                source.get_bytes(ref), source.get_manifest_bytes(ref), artifact_id=ref
            )
            consumer = NodeResultCache(target, run_id="probe-run", tenant_context=context(ot, oc))
            loaded = consumer.load_entry(imported)
            records.append(
                {"case": label, "intake": "accepted", "consumer": "loaded" if loaded else "miss"}
            )
        except Exception as exc:
            records.append(
                {
                    "case": label,
                    "exception": type(exc).__name__,
                    "message": str(exc),
                    "intake_claim": target._ownership_index.has_any_tenant_claim(ref.artifact_id),
                }
            )
    return records


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="e02-cas-tenant-probe-") as name:
        root = Path(name)
        git = shutil.which("git")
        if git is None:
            raise RuntimeError("git executable is required to bind probe source")
        sys.stdout.write(
            json.dumps(
                {
                    "source_sha": subprocess.check_output(  # noqa: S603 -- fixed read-only git args
                        [git, "rev-parse", "HEAD"], text=True
                    ).strip(),
                    "python": platform.python_version(),
                    "platform": platform.platform(),
                    "store_source_sha256": hashlib.sha256(
                        Path("src/polisyos/core/artifacts/store.py").read_bytes()
                    ).hexdigest(),
                    "matrix": matrix(root / "matrix"),
                    "sibling_generic_put": sibling_puts(root / "put"),
                    "actual_node_result_cache_consumer": actual_cache_consumer(root / "cache"),
                    "limitations": (
                        "Local temporary real filesystem; no remote service, production dataset, "
                        "signature-required profile or new policy asserted."
                    ),
                },
                indent=2,
            )
            + "\n"
        )


if __name__ == "__main__":
    main()

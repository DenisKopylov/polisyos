"""Compose canonical acquisition routing with Fabric's new non-data intake plane.

Routing and report persistence remain owned by ``acquisition_planner``. This
module only binds an existing typed owner gap to the newly commissioned non-data
request. It neither maps acquisition types to strategies nor supplies a default
gap, and a routing report cannot lift the candidate authority ceiling.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core import artifacts
from polisyos.core.artifacts.manifest import ArtifactManifest, ArtifactRef
from polisyos.fabric import atomic_write_json, file_lock
from polisyos.fabric.evidence.non_data_acquisition import (
    NonDataAcquisitionRuntime,
    NonDataReceipt,
    NonDataRequest,
)
from polisyos.pdc import gy_recorded_content_hash
from polisyos.runtime.quality.acquisition_planner import (
    ACQUISITION_PLANNER_KIND,
    ACQUISITION_PLANNER_SCHEMA_NAME,
    ACQUISITION_PLANNER_SCHEMA_VERSION_SHORT,
    AcquisitionGap,
    load_acquisition_planner_report,
    persist_acquisition_planner_report,
    plan_evidence_acquisition,
)

CENSUS_PATH = "architecture/policy_design_case/layer3_gy_n13a_acquisition_census.json"
NON_DATA_PROJECTION_FAMILY = "architecture/policy_design_case/gy_aq1_non_data_projection"
NON_DATA_PROJECTION_BUNDLE_PATH = f"{NON_DATA_PROJECTION_FAMILY}/receipt-bundle.json"
_DIGEST = r"^sha256:[0-9a-f]{64}$"


@dataclass(frozen=True)
class NonDataAcquisitionRun:
    """The canonical routing artifact and its exact candidate runtime consumer."""

    planner_report_ref: ArtifactRef
    receipt: NonDataReceipt


def run_non_data_acquisition(
    *,
    runtime: NonDataAcquisitionRuntime,
    request: NonDataRequest,
    gap: AcquisitionGap,
    run_id: str,
    at: datetime,
) -> NonDataAcquisitionRun:
    """Route through the existing planner before candidate object admission."""
    request = NonDataRequest.model_validate(request.model_dump(mode="json"))
    gap = AcquisitionGap.model_validate(gap.model_dump(mode="json"))
    if gap.gap_id != request.gap_id or gap.claim_ref != request.claim_ref:
        raise ValueError("non_data_gap_binding_mismatch")
    report = plan_evidence_acquisition(run_id=run_id, gaps=[gap], generated_at=at)
    report_ref = persist_acquisition_planner_report(runtime.store, report)
    bound = NonDataRequest.model_validate(
        {
            **request.model_dump(mode="json"),
            "planner_report_ref": str(report_ref.artifact_id),
        }
    )
    receipt = runtime.acquire(bound, at=at)
    return NonDataAcquisitionRun(planner_report_ref=report_ref, receipt=receipt)


class _ProjectionEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    route_id: str = Field(min_length=1)
    route_sha256: str = Field(pattern=_DIGEST)
    route_hash_rule: Literal["polisyos.pdc.gy_recorded_content_hash.v1"] = (
        "polisyos.pdc.gy_recorded_content_hash.v1"
    )
    gap: AcquisitionGap
    run_id: str = Field(min_length=1)
    receipt_ref: str = Field(pattern=_DIGEST)


class _ProjectionBundle(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["policyos.runtime.non_data_refusal_bundle.v1"] = (
        "policyos.runtime.non_data_refusal_bundle.v1"
    )
    entries: tuple[_ProjectionEntry, ...]


@dataclass(frozen=True)
class VerifiedNonDataRoute:
    """A canonical, portlessly recomputed refusal for one content-bound route."""

    route_id: str
    receipt: NonDataReceipt


@dataclass(frozen=True)
class NonDataProjectionSource:
    """Verified refusals and the complete source byte identities they consumed."""

    routes: tuple[VerifiedNonDataRoute, ...]
    component_bindings: tuple[tuple[str, str], ...]


def _sha256(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _confined(root: Path, relative: str) -> Path:
    suffix = Path(relative)
    if suffix.is_absolute() or ".." in suffix.parts:
        raise ValueError("non_data_projection_namespace_escape")
    path = root
    for part in suffix.parts:
        path = path / part
        if path.is_symlink():
            raise ValueError("non_data_projection_namespace_symlink")
    return path


def _record_bytes(root: Path, path: Path, bindings: dict[str, str]) -> bytes:
    relative = path.relative_to(root).as_posix()
    _confined(root, relative)
    raw = path.read_bytes()
    identity = _sha256(raw)
    if relative in bindings and bindings[relative] != identity:
        raise ValueError("non_data_projection_source_changed_during_read")
    bindings[relative] = identity
    return raw


class _ProjectionCAS(artifacts.FileSystemCAS):
    """Use the canonical CAS while recording each consulted byte dependency."""

    def __init__(self, root: Path, bindings: dict[str, str], *, writable: bool = False) -> None:
        self.governed_root = root
        self.bindings = bindings
        self.unresolved_dependency = False
        base = _confined(root, f"{NON_DATA_PROJECTION_FAMILY}/cas/artifacts/sha256")
        if not writable and not base.is_dir():
            raise ValueError("non_data_projection_cas_missing")
        super().__init__(_confined(root, f"{NON_DATA_PROJECTION_FAMILY}/cas"))

    def _paths(self, artifact_id: artifacts.ArtifactID) -> tuple[Path, Path]:
        paths = super()._paths(artifact_id)
        for path in paths:
            _confined(self.governed_root, path.relative_to(self.governed_root).as_posix())
        return paths

    def _record(self, artifact_id: artifacts.ArtifactID | str, index: int) -> None:
        try:
            identity = artifacts.ArtifactID.model_validate(artifact_id)
            path = self.get_paths(identity)[index]
            # A symlink within the governed root must not escape this CAS either.
            path.resolve().relative_to(self.root.resolve())
            _record_bytes(self.governed_root, path, self.bindings)
        except (OSError, ValueError):
            self.unresolved_dependency = True
            raise

    def get_bytes(self, artifact_id: artifacts.ArtifactID | str) -> bytes:
        self._record(artifact_id, 0)
        raw = super().get_bytes(artifact_id)
        self._record(artifact_id, 0)
        return raw

    def get_manifest(self, artifact_id: artifacts.ArtifactID | str) -> ArtifactManifest:
        self._record(artifact_id, 1)
        manifest = super().get_manifest(artifact_id)
        self._record(artifact_id, 1)
        return manifest


def _read_census(root: Path, bindings: dict[str, str]) -> dict[str, object]:
    payload = json.loads(_record_bytes(root, _confined(root, CENSUS_PATH), bindings))
    if not isinstance(payload, dict) or payload.get("schema_version") != (
        "policyos.policy_design_case.gy_n13a.acquisition_census.v1"
    ):
        raise ValueError("non_data_projection_census_invalid")
    return payload


def _route(census: Mapping[str, object], route_id: str) -> Mapping[str, object]:
    rows = census.get("route_evidence")
    if not isinstance(rows, list):
        raise ValueError("non_data_projection_route_denominator_invalid")
    routes: dict[str, Mapping[str, object]] = {}
    for row in rows:
        route = row.get("route") if isinstance(row, Mapping) else None
        if not isinstance(route, Mapping) or not isinstance(route.get("route_id"), str):
            raise ValueError("non_data_projection_route_denominator_invalid")
        key = route["route_id"]
        if key in routes:
            raise ValueError("non_data_projection_duplicate_route")
        routes[key] = route
    if route_id not in routes:
        raise ValueError("non_data_projection_route_binding_mismatch")
    route = routes[route_id]
    # The recorded-content owner accepts general Python objects. This boundary
    # admits only finite JSON, as the original canonical-byte owner required.
    try:
        json.dumps(route, allow_nan=False)
    except (ValueError, TypeError) as exc:
        raise ValueError("non_data_projection_route_not_finite_json") from exc
    return route


def _bind_request(
    route: Mapping[str, object], request: NonDataRequest, gap: AcquisitionGap
) -> None:
    if (
        request.claim_ref != route.get("candidate_ref")
        or request.gap_id != route.get("requirement_gap_id")
        or request.claim_ref != gap.claim_ref
        or request.gap_id != gap.gap_id
    ):
        raise ValueError("non_data_projection_request_binding_mismatch")


def _verify_bundle(
    root: Path,
    bundle: _ProjectionBundle,
    census: Mapping[str, object],
    bindings: dict[str, str],
) -> tuple[VerifiedNonDataRoute, ...]:
    if len({entry.route_id for entry in bundle.entries}) != len(bundle.entries):
        raise ValueError("non_data_projection_duplicate_route")
    if not _confined(root, f"{NON_DATA_PROJECTION_FAMILY}/cas").is_dir():
        raise ValueError("non_data_projection_cas_missing")
    store = _ProjectionCAS(root, bindings)
    runtime = NonDataAcquisitionRuntime(
        store=store, journal_path=root / NON_DATA_PROJECTION_FAMILY / "events.jsonl"
    )
    routes = []
    for entry in bundle.entries:
        route = _route(census, entry.route_id)
        if gy_recorded_content_hash(route) != entry.route_sha256:
            raise ValueError("non_data_projection_route_binding_mismatch")
        receipt = runtime.read_receipt(entry.receipt_ref)
        if store.unresolved_dependency:
            raise ValueError("non_data_projection_unresolved_dependency")
        _bind_request(route, receipt.request, entry.gap)
        report_ref = receipt.planner_report_ref
        if report_ref is None or report_ref != receipt.request.planner_report_ref:
            raise ValueError("non_data_projection_planner_binding_mismatch")
        manifest = store.get_manifest(report_ref)
        if (
            manifest.kind != ACQUISITION_PLANNER_KIND
            or manifest.artifact_schema is None
            or manifest.artifact_schema.name != ACQUISITION_PLANNER_SCHEMA_NAME
            or manifest.artifact_schema.version != ACQUISITION_PLANNER_SCHEMA_VERSION_SHORT
        ):
            raise ValueError("non_data_projection_planner_owner_mismatch")
        actual = load_acquisition_planner_report(
            store,
            ArtifactRef(
                artifact_id=artifacts.ArtifactID.model_validate(report_ref),
                kind=manifest.kind,
                media_type=manifest.media_type,
            ),
        )
        expected = plan_evidence_acquisition(
            run_id=entry.run_id, gaps=[entry.gap], generated_at=receipt.evaluated_at
        )
        if actual != expected:
            raise ValueError("non_data_projection_planner_recomputation_mismatch")
        if receipt.resolution_state not in {
            "shape_not_established",
            "split_required",
            "admission_refused",
        }:
            raise ValueError("non_data_projection_receipt_not_portless_refusal")
        routes.append(VerifiedNonDataRoute(route_id=entry.route_id, receipt=receipt))
    return tuple(routes)


def load_non_data_projection_source(
    *, governed_root: Path, census: Mapping[str, object]
) -> NonDataProjectionSource:
    """Read the fixed public source family and recompute every candidate refusal.

    Missing bundles preserve the historical DS15 projection. A present invalid
    bundle or unresolved CAS dependency raises ``ValueError`` and never returns
    partial projected receipts.
    """
    root = Path(governed_root).resolve()
    try:
        path = _confined(root, NON_DATA_PROJECTION_BUNDLE_PATH)
        if not path.exists():
            return NonDataProjectionSource(routes=(), component_bindings=())
        bindings: dict[str, str] = {}
        actual_census = _read_census(root, bindings)
        if actual_census != census:
            raise ValueError("non_data_projection_census_binding_mismatch")
        bundle = _ProjectionBundle.model_validate_json(_record_bytes(root, path, bindings))
        routes = _verify_bundle(root, bundle, actual_census, bindings)
        for relative in tuple(bindings):
            _record_bytes(root, root / relative, bindings)
        return NonDataProjectionSource(routes, tuple(sorted(bindings.items())))
    except OSError as exc:
        raise ValueError("non_data_projection_source_unresolved") from exc


def publish_non_data_refusal(
    *,
    governed_root: Path,
    request: NonDataRequest,
    gap: AcquisitionGap,
    route_id: str,
    run_id: str,
    at: datetime,
) -> NonDataAcquisitionRun:
    """Run the canonical planner/AQ1 producer and publish a bound public refusal."""
    root = Path(governed_root).resolve()
    request = NonDataRequest.model_validate(request.model_dump(mode="json"))
    gap = AcquisitionGap.model_validate(gap.model_dump(mode="json"))
    if at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("non_data_projection_timezone_required")
    bindings: dict[str, str] = {}
    census = _read_census(root, bindings)
    route = _route(census, route_id)
    _bind_request(route, request, gap)
    path = _confined(root, NON_DATA_PROJECTION_BUNDLE_PATH)
    with file_lock(_confined(root, f"{NON_DATA_PROJECTION_FAMILY}/publish.lock")):
        retained = ()
        if path.exists():
            old = _ProjectionBundle.model_validate_json(path.read_bytes())
            retained = tuple(entry for entry in old.entries if entry.route_id != route_id)
        _confined(root, f"{NON_DATA_PROJECTION_FAMILY}/events.lock")
        runtime = NonDataAcquisitionRuntime(
            store=_ProjectionCAS(root, bindings, writable=True),
            journal_path=_confined(root, f"{NON_DATA_PROJECTION_FAMILY}/events.jsonl"),
        )
        result = run_non_data_acquisition(
            runtime=runtime, request=request, gap=gap, run_id=run_id, at=at
        )
        entry = _ProjectionEntry(
            route_id=route_id,
            route_sha256=gy_recorded_content_hash(route),
            gap=gap,
            run_id=run_id,
            receipt_ref=result.receipt.artifact_ref,
        )
        bundle = _ProjectionBundle(entries=(*retained, entry))
        _verify_bundle(root, bundle, census, bindings)
        for relative in tuple(bindings):
            _record_bytes(root, root / relative, bindings)
        atomic_write_json(path, bundle.model_dump(mode="json"))
        load_non_data_projection_source(governed_root=root, census=census)
        return result


def main(argv: Sequence[str] | None = None) -> int:
    """Publish an explicitly supplied owner demand as a read-only DS15 refusal."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--governed-root", type=Path, default=os.environ.get("POLISYOS_GOVERNED_ARTIFACT_ROOT")
    )
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--gap", type=Path, required=True)
    parser.add_argument("--route-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--at", required=True)
    args = parser.parse_args(argv)
    if args.governed_root is None:
        parser.error("--governed-root or POLISYOS_GOVERNED_ARTIFACT_ROOT is required")
    result = publish_non_data_refusal(
        governed_root=Path(args.governed_root),
        request=NonDataRequest.model_validate_json(args.request.read_bytes()),
        gap=AcquisitionGap.model_validate_json(args.gap.read_bytes()),
        route_id=args.route_id,
        run_id=args.run_id,
        at=datetime.fromisoformat(args.at),
    )
    sys.stdout.write(
        json.dumps(
            {"bundle": NON_DATA_PROJECTION_BUNDLE_PATH, "receipt_ref": result.receipt.artifact_ref}
        )
        + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Manifest helpers for advanced benchmark families."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ManifestCase:
    case_id: str
    family: str
    visibility: str
    case_class: str
    inputs_ref: str
    oracle_ref: str
    baseline_overlap: tuple[str, ...]
    gates: dict[str, Any]
    tags: tuple[str, ...]
    revision: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class ManifestBundle:
    family: str
    visibility: str
    revision: str
    cases: tuple[ManifestCase, ...]
    source: str
    path: str | None
    placeholder: bool = False
    degraded_reasons: tuple[str, ...] = ()
    dependency_status: dict[str, Any] | None = None

    @property
    def required_comparators(self) -> tuple[str, ...]:
        labels: dict[str, None] = {}
        for case in self.cases:
            for label in case.baseline_overlap:
                labels[label] = None
        return tuple(labels.keys())


DEFAULT_PUBLIC_MANIFESTS: dict[str, Path] = {
    "proof_closure": Path(__file__).resolve().parents[1]
    / "proof_closure"
    / "fixtures"
    / "public_cases.json",
    "distributional": Path(__file__).resolve().parents[1]
    / "distributional"
    / "fixtures"
    / "public_cases.json",
    "discovery_governance": Path(__file__).resolve().parents[1]
    / "governance"
    / "fixtures"
    / "public_cases.json",
    "strategic_solver": Path(__file__).resolve().parents[1]
    / "strategic"
    / "fixtures"
    / "public_cases.json",
    "abstraction_exactness": Path(__file__).resolve().parents[1]
    / "abstraction"
    / "fixtures"
    / "public_cases.json",
    "interaction_contracts": Path(__file__).resolve().parents[1]
    / "interaction"
    / "fixtures"
    / "public_cases.json",
}


def manifest_env_var(family: str, visibility: str) -> str:
    normalized_family = family.upper().replace("-", "_")
    if visibility == "hidden_release":
        return f"BENCH_HIDDEN_{normalized_family}_MANIFEST"
    if visibility == "prod_shadow":
        return f"BENCH_SHADOW_{normalized_family}_MANIFEST"
    raise ValueError(f"Unsupported manifest visibility {visibility!r}")


def load_public_manifest(family: str) -> ManifestBundle:
    path = DEFAULT_PUBLIC_MANIFESTS.get(family)
    if path is None:
        raise FileNotFoundError(f"No public manifest configured for family {family!r}")
    return _load_manifest(
        path=path, family=family, source="repo_public_manifest", placeholder=False
    )


def select_manifest(
    *,
    family: str,
    visibility: str,
    smoke_placeholder_allowed: bool,
) -> ManifestBundle:
    if visibility == "public":
        return load_public_manifest(family)

    env_var = manifest_env_var(family, visibility)
    raw_path = os.environ.get(env_var, "").strip()
    if raw_path:
        path = Path(raw_path).expanduser()
        if path.exists():
            return _load_manifest(
                path=path,
                family=family,
                source=f"external_{visibility}_manifest",
                placeholder=False,
            )
        dependency_status = {
            "manifest": {
                "env_var": env_var,
                "configured": True,
                "path": str(path),
                "exists": False,
            }
        }
        if smoke_placeholder_allowed:
            return _build_placeholder_bundle(
                family=family,
                visibility=visibility,
                dependency_status=dependency_status,
                degraded_reason=f"using local placeholder because {env_var} does not exist",
            )
        raise FileNotFoundError(f"{env_var} points to a missing manifest: {path}")

    dependency_status = {
        "manifest": {
            "env_var": env_var,
            "configured": False,
            "path": None,
            "exists": False,
        }
    }
    if smoke_placeholder_allowed:
        return _build_placeholder_bundle(
            family=family,
            visibility=visibility,
            dependency_status=dependency_status,
            degraded_reason=f"using local placeholder because {env_var} is unavailable",
        )
    raise FileNotFoundError(f"{env_var} is required for {visibility} manifests")


def _load_manifest(
    *,
    path: Path,
    family: str,
    source: str,
    placeholder: bool,
    degraded_reasons: tuple[str, ...] = (),
    dependency_status: dict[str, Any] | None = None,
) -> ManifestBundle:
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload_family = str(payload.get("family") or family)
    if payload_family != family:
        raise ValueError(
            f"Manifest family mismatch for {path}: expected {family!r}, got {payload_family!r}"
        )
    visibility = str(payload.get("visibility") or "public")
    revision = str(payload.get("revision") or "1.0")
    cases = tuple(
        _parse_case(payload_family, revision, item, visibility) for item in payload.get("cases", ())
    )
    if not cases:
        raise ValueError(f"Manifest {path} does not define any cases")
    return ManifestBundle(
        family=payload_family,
        visibility=visibility,
        revision=revision,
        cases=cases,
        source=source,
        path=str(path),
        placeholder=placeholder,
        degraded_reasons=degraded_reasons,
        dependency_status=dependency_status,
    )


def _parse_case(
    family: str,
    revision: str,
    payload: dict[str, Any],
    default_visibility: str,
) -> ManifestCase:
    required = {
        "case_id",
        "case_class",
        "inputs_ref",
        "oracle_ref",
    }
    missing = sorted(required.difference(payload))
    if missing:
        raise ValueError(f"Manifest case missing required keys {missing} for family {family!r}")
    visibility = str(payload.get("visibility") or default_visibility)
    gates = dict(payload.get("gates") or {})
    baseline_overlap = tuple(str(item) for item in payload.get("baseline_overlap", ()))
    tags = tuple(str(item) for item in payload.get("tags", ()))
    return ManifestCase(
        case_id=str(payload["case_id"]),
        family=str(payload.get("family") or family),
        visibility=visibility,
        case_class=str(payload["case_class"]),
        inputs_ref=str(payload["inputs_ref"]),
        oracle_ref=str(payload["oracle_ref"]),
        baseline_overlap=baseline_overlap,
        gates=gates,
        tags=tags,
        revision=str(payload.get("revision") or revision),
        payload={
            key: value
            for key, value in payload.items()
            if key
            not in {
                "case_id",
                "family",
                "visibility",
                "case_class",
                "inputs_ref",
                "oracle_ref",
                "baseline_overlap",
                "gates",
                "tags",
                "revision",
            }
        },
    )


def _build_placeholder_bundle(
    *,
    family: str,
    visibility: str,
    dependency_status: dict[str, Any],
    degraded_reason: str,
) -> ManifestBundle:
    try:
        public = load_public_manifest(family)
        placeholder_cases = tuple(
            ManifestCase(
                case_id=f"{visibility}::{case.case_id}",
                family=family,
                visibility=visibility,
                case_class=case.case_class,
                inputs_ref=f"placeholder://{case.inputs_ref}",
                oracle_ref=f"placeholder://{case.oracle_ref}",
                baseline_overlap=(),
                gates={**case.gates, "placeholder": True},
                tags=tuple((*case.tags, "placeholder")),
                revision=case.revision,
                payload={**case.payload, "placeholder": True},
            )
            for case in public.cases[: min(2, len(public.cases))]
        )
        revision = public.revision
    except Exception:
        placeholder_cases = (
            ManifestCase(
                case_id=f"{visibility}::{family}::placeholder",
                family=family,
                visibility=visibility,
                case_class="placeholder",
                inputs_ref=f"placeholder://{family}",
                oracle_ref=f"placeholder://{family}",
                baseline_overlap=(),
                gates={"placeholder": True},
                tags=("placeholder",),
                revision="placeholder-v1",
                payload={"placeholder": True},
            ),
        )
        revision = "placeholder-v1"
    return ManifestBundle(
        family=family,
        visibility=visibility,
        revision=revision,
        cases=placeholder_cases,
        source="local_placeholder_manifest",
        path=None,
        placeholder=True,
        degraded_reasons=(degraded_reason,),
        dependency_status=dependency_status,
    )


__all__ = [
    "DEFAULT_PUBLIC_MANIFESTS",
    "ManifestBundle",
    "ManifestCase",
    "load_public_manifest",
    "manifest_env_var",
    "select_manifest",
]

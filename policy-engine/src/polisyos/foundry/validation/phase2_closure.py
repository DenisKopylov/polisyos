"""Machine-check closure of Foundry Phase 2 deliverables."""

from __future__ import annotations

import importlib
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes

PHASE2_CLOSURE_SCHEMA_NAME = "polisyos.foundry.validation.FoundryPhase2ClosureReport"
PHASE2_CLOSURE_ENV_VAR = "POLISYOS_PHASE2_CLOSURE_REPORT"

_FRONTIER_FAMILIES = frozenset(
    {
        "econometrics_frontier",
        "distributional_frontier",
        "mobility_frontier",
        "network_identification",
        "spatial_identification",
    }
)


class FoundryPhase2TrackSummary(BaseModel):
    """Machine-readable closure summary for one Phase 2 track."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    track_id: str
    artifact_family: str
    typed_targets: tuple[str, ...] = ()
    acceptance_predicate: str
    blocking_transition: str
    passes_all: bool
    status: str
    required_acceptance_tests: tuple[str, ...] = ()
    required_benchmarks: tuple[str, ...] = ()
    required_synthetic_world_checks: tuple[str, ...] = ()
    required_judge_verdicts: tuple[str, ...] = ()
    missing_typed_targets: tuple[str, ...] = ()
    missing_acceptance_tests: tuple[str, ...] = ()
    failed_acceptance_tests: tuple[str, ...] = ()
    missing_benchmarks: tuple[str, ...] = ()
    failed_benchmarks: tuple[str, ...] = ()
    missing_synthetic_world_checks: tuple[str, ...] = ()
    failed_synthetic_world_checks: tuple[str, ...] = ()
    missing_judge_verdicts: tuple[str, ...] = ()
    failed_judge_verdicts: tuple[str, ...] = ()


class FoundryPhase2FamilySummary(BaseModel):
    """Artifact-family rollup consumed by readiness and promotion surfaces."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    artifact_family: str
    applies_to: tuple[str, ...] = ()
    blocking_transition: str
    passes_all: bool
    status: str
    track_ids: tuple[str, ...] = ()


class FoundryPhase2ClosureReport(BaseModel):
    """Typed closure report shared by CI and runtime."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    assessment_id: str = "foundry_phase2_closure"
    phase_id: str
    overall_status: str
    manifest_path: str
    acceptance_junit_xml: str
    benchmark_report: str
    evidence_report: str
    source_of_truth: dict[str, Any] = Field(default_factory=dict)
    tracks: dict[str, FoundryPhase2TrackSummary] = Field(default_factory=dict)
    artifact_families: dict[str, FoundryPhase2FamilySummary] = Field(default_factory=dict)
    notes: tuple[str, ...] = ()


def _repo_relative(path: Path, repo_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        return str(path.resolve())


def _default_repo_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "pyproject.toml").exists() and (candidate / "src").is_dir():
            return candidate
    raise RuntimeError("Could not resolve policy-engine repository root for Phase 2 closure.")


def default_foundry_phase2_manifest_path(repo_root: Path | None = None) -> Path:
    """Return the canonical Phase 2 manifest path."""

    resolved_root = (repo_root or _default_repo_root()).resolve()
    return resolved_root / "tools/quality/validation/foundry_phase2_manifest.json"


def default_foundry_phase2_closure_report_path(repo_root: Path | None = None) -> Path:
    """Return the canonical runtime-readable Phase 2 closure report path."""

    resolved_root = (repo_root or _default_repo_root()).resolve()
    return resolved_root / "benchmarks/_reports/foundry_phase2_latest/foundry_phase2_closure.json"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_named_items(values: object) -> tuple[str, ...]:
    if not isinstance(values, list):
        return ()
    return tuple(str(item).strip() for item in values if str(item).strip())


def _load_manifest(path: Path) -> dict[str, Any]:
    payload = _load_json(path)
    tracks = payload.get("tracks")
    if not isinstance(tracks, list) or not tracks:
        raise ValueError("Phase 2 manifest must declare a non-empty tracks list")

    seen_track_ids: set[str] = set()
    for item in tracks:
        if not isinstance(item, dict):
            raise ValueError("Each Phase 2 track entry must be an object")
        track_id = str(item.get("track_id") or "").strip()
        if not track_id:
            raise ValueError("Phase 2 track entries must declare track_id")
        if track_id in seen_track_ids:
            raise ValueError(f"Duplicate Phase 2 track_id in manifest: {track_id}")
        seen_track_ids.add(track_id)
        artifact_family = str(item.get("artifact_family") or "").strip()
        if not artifact_family:
            raise ValueError(f"track_id={track_id} is missing artifact_family")
        typed_targets = _normalize_named_items(item.get("typed_targets"))
        if not typed_targets:
            raise ValueError(f"track_id={track_id} must declare at least one typed target")
    return payload


def _parse_junit_xml(path: Path) -> tuple[set[str], set[str]]:
    root = ET.fromstring(path.read_text(encoding="utf-8"))
    all_tests: set[str] = set()
    passing: set[str] = set()
    for testcase in root.iter("testcase"):
        name = str(testcase.attrib.get("name", "")).strip()
        classname = str(testcase.attrib.get("classname", "")).strip()
        file_attr = str(testcase.attrib.get("file", "")).strip()
        base_name = name.split("[", 1)[0].strip() if name else ""
        variants = {value for value in (name, base_name) if value}
        name_variants = tuple(value for value in (name, base_name) if value)

        if classname and name_variants:
            for variant_name in name_variants:
                variants.add(f"{classname}::{variant_name}")

        if file_attr and name_variants:
            class_tail = classname.rsplit(".", 1)[-1] if classname else ""
            for variant_name in name_variants:
                variants.add(f"{file_attr}::{variant_name}")
                if class_tail and class_tail != Path(file_attr).stem:
                    variants.add(f"{file_attr}::{class_tail}::{variant_name}")

        if classname and name_variants:
            parts = [part for part in classname.split(".") if part]
            for index in range(len(parts), 0, -1):
                module_path = "/".join(parts[:index]) + ".py"
                remainder = parts[index:]
                for variant_name in name_variants:
                    variants.add(f"{module_path}::{variant_name}")
                    if remainder:
                        variants.add(f"{module_path}::{'::'.join(remainder)}::{variant_name}")
        failed = any(child.tag in {"failure", "error"} for child in testcase)
        skipped = any(child.tag == "skipped" for child in testcase)
        for variant in variants:
            if not variant:
                continue
            all_tests.add(variant)
            if not failed and not skipped:
                passing.add(variant)
    return all_tests, passing


def _benchmark_passed(entry: dict[str, Any]) -> bool:
    status = str(entry.get("status") or "").strip().lower()
    if status:
        return status in {"pass", "passed", "green", "ok", "success"}
    if "passed" in entry:
        return bool(entry.get("passed"))
    if "success" in entry:
        return bool(entry.get("success"))
    return False


def _parse_benchmark_json(path: Path) -> tuple[set[str], set[str]]:
    payload = _load_json(path)
    benchmarks = payload.get("benchmarks")
    if not isinstance(benchmarks, list):
        raise ValueError("benchmark report must contain a benchmarks list")
    all_names: set[str] = set()
    passing: set[str] = set()
    for item in benchmarks:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        all_names.add(name)
        if _benchmark_passed(item):
            passing.add(name)
    return all_names, passing


def _coerce_named_status_map(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in value.items()}


def _status_is_pass(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"pass", "passed", "green", "ok", "success", "promote"}
    if isinstance(value, dict):
        status = str(value.get("status") or "").strip().lower()
        decision = str(value.get("composite_decision") or "").strip().lower()
        if status:
            return status in {"pass", "passed", "green", "ok", "success"}
        if decision:
            return decision == "promote"
    return False


def _has_model_field(model: type[object], field_name: str) -> bool:
    model_fields = getattr(model, "model_fields", None)
    if isinstance(model_fields, Mapping):
        return field_name in model_fields
    annotations = getattr(model, "__annotations__", None)
    if isinstance(annotations, Mapping):
        return field_name in annotations
    return hasattr(model, field_name)


def _resolve_typed_target(target: str) -> bool:
    parts = [part for part in target.split(".") if part]
    if not parts:
        return False
    for index in range(len(parts), 0, -1):
        module_name = ".".join(parts[:index])
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            continue
        remainder = parts[index:]
        if not remainder:
            return True
        cursor: object = module
        for position, part in enumerate(remainder):
            if not hasattr(cursor, part):
                if position == len(remainder) - 1 and _has_model_field(cursor, part):  # type: ignore[arg-type]
                    return True
                return False
            cursor = getattr(cursor, part)
        return True
    return False


def _evaluate_track(
    *,
    track: dict[str, Any],
    junit_all: set[str],
    junit_passing: set[str],
    benchmark_all: set[str],
    benchmark_passing: set[str],
    evidence_payload: dict[str, Any],
) -> tuple[FoundryPhase2TrackSummary, list[str]]:
    track_id = str(track["track_id"])
    notes: list[str] = []
    typed_targets = _normalize_named_items(track.get("typed_targets"))
    required_tests = _normalize_named_items(track.get("required_acceptance_tests"))
    required_benchmarks = _normalize_named_items(track.get("required_benchmarks"))
    required_synthetic = _normalize_named_items(track.get("required_synthetic_world_checks"))
    required_judges = _normalize_named_items(track.get("required_judge_verdicts"))

    track_evidence = _coerce_named_status_map(
        _coerce_named_status_map(evidence_payload.get("tracks")).get(track_id)
    )
    synthetic_map = _coerce_named_status_map(track_evidence.get("synthetic_world_checks"))
    judge_map = _coerce_named_status_map(track_evidence.get("judge_verdicts"))

    missing_typed_targets = tuple(target for target in typed_targets if not _resolve_typed_target(target))
    missing_tests = tuple(name for name in required_tests if name not in junit_all)
    failed_tests = tuple(name for name in required_tests if name in junit_all and name not in junit_passing)
    missing_benchmarks = tuple(name for name in required_benchmarks if name not in benchmark_all)
    failed_benchmarks = tuple(
        name for name in required_benchmarks if name in benchmark_all and name not in benchmark_passing
    )
    missing_synthetic = tuple(name for name in required_synthetic if name not in synthetic_map)
    failed_synthetic = tuple(
        name for name in required_synthetic if name in synthetic_map and not _status_is_pass(synthetic_map[name])
    )
    missing_judges = tuple(name for name in required_judges if name not in judge_map)
    failed_judges = tuple(
        name for name in required_judges if name in judge_map and not _status_is_pass(judge_map[name])
    )

    status = "pass"
    if missing_typed_targets:
        status = "missing_typed_target_mapping"
    elif missing_tests or missing_benchmarks:
        status = "stale_manifest"
    elif failed_tests:
        status = "failed_acceptance_test"
    elif failed_benchmarks:
        status = "failed_benchmark"
    elif missing_synthetic:
        status = "synthetic_world_missing"
    elif failed_synthetic:
        status = "synthetic_world_failed"
    elif missing_judges:
        status = "judge_verdict_missing"
    elif failed_judges:
        status = "judge_verdict_failed"

    for target in missing_typed_targets:
        notes.append(f"missing_typed_target_mapping:{track_id}:{target}")
    for name in missing_tests:
        notes.append(f"stale_manifest:test_missing:{track_id}:{name}")
    for name in missing_benchmarks:
        notes.append(f"stale_manifest:benchmark_missing:{track_id}:{name}")
    for name in failed_tests:
        notes.append(f"failed_acceptance_test:{track_id}:{name}")
    for name in failed_benchmarks:
        notes.append(f"failed_benchmark:{track_id}:{name}")
    for name in missing_synthetic:
        notes.append(f"missing_synthetic_world:{track_id}:{name}")
    for name in failed_synthetic:
        notes.append(f"failed_synthetic_world:{track_id}:{name}")
    for name in missing_judges:
        notes.append(f"missing_judge_verdict:{track_id}:{name}")
    for name in failed_judges:
        notes.append(f"failed_judge_verdict:{track_id}:{name}")

    summary = FoundryPhase2TrackSummary(
        track_id=track_id,
        artifact_family=str(track.get("artifact_family")),
        typed_targets=typed_targets,
        acceptance_predicate=str(track.get("acceptance_predicate") or ""),
        blocking_transition=str(track.get("blocking_transition") or ""),
        passes_all=status == "pass",
        status=status,
        required_acceptance_tests=required_tests,
        required_benchmarks=required_benchmarks,
        required_synthetic_world_checks=required_synthetic,
        required_judge_verdicts=required_judges,
        missing_typed_targets=missing_typed_targets,
        missing_acceptance_tests=missing_tests,
        failed_acceptance_tests=failed_tests,
        missing_benchmarks=missing_benchmarks,
        failed_benchmarks=failed_benchmarks,
        missing_synthetic_world_checks=missing_synthetic,
        failed_synthetic_world_checks=failed_synthetic,
        missing_judge_verdicts=missing_judges,
        failed_judge_verdicts=failed_judges,
    )
    return summary, notes


def normalize_phase2_artifact_family(
    artifact_family: str | None,
    *,
    estimator_name: str | None = None,
    query_type: str | None = None,
) -> str:
    """Map frontier methods onto canonical Phase 2 artifact families."""

    normalized = str(artifact_family or "").strip().lower()
    if normalized in _FRONTIER_FAMILIES:
        return normalized

    evidence = " ".join(
        value.strip().lower()
        for value in (artifact_family or "", estimator_name or "", query_type or "")
        if value
    )
    if not evidence:
        return "causal_core"

    if any(
        token in evidence
        for token in (
            "post_selection",
            "high_dimensional",
            "iv",
            "threshold",
            "kink",
            "garch",
            "volatility",
            "econometric",
        )
    ):
        return "econometrics_frontier"
    if any(
        token in evidence
        for token in (
            "mobility",
            "attrition",
            "transition_matrix",
            "sequential_lifetime_transition_matrix",
            "refreshment_transition_matrix",
        )
    ):
        return "mobility_frontier"
    if any(
        token in evidence
        for token in (
            "peer_effect",
            "reflection",
            "strategic_formation",
            "formation",
            "ergm",
            "sbm",
            "embedding",
            "network",
            "missingness",
            "partial_observability",
        )
    ):
        return "network_identification"
    if any(
        token in evidence
        for token in (
            "spatial",
            "maup",
            "interference",
            "sae",
            "small_area",
            "hodge",
            "areal",
        )
    ):
        return "spatial_identification"
    if any(
        token in evidence
        for token in (
            "distributional",
            "bounds",
            "makarov",
            "lee_trimming",
            "mtr_",
            "sd_",
            "ordinal_poverty",
            "poverty",
        )
    ):
        return "distributional_frontier"
    return normalized or "causal_core"


def build_foundry_phase2_closure_report(
    *,
    repo_root: Path,
    manifest_path: Path,
    acceptance_junit_xml: Path,
    benchmark_report: Path,
    evidence_report: Path,
) -> FoundryPhase2ClosureReport:
    """Build the canonical Phase 2 closure report."""

    repo_root = repo_root.resolve()
    manifest_path = manifest_path.resolve()
    acceptance_junit_xml = acceptance_junit_xml.resolve()
    benchmark_report = benchmark_report.resolve()
    evidence_report = evidence_report.resolve()

    manifest = _load_manifest(manifest_path)
    junit_all, junit_passing = _parse_junit_xml(acceptance_junit_xml)
    benchmark_all, benchmark_passing = _parse_benchmark_json(benchmark_report)
    evidence_payload = _load_json(evidence_report)

    track_summaries: dict[str, FoundryPhase2TrackSummary] = {}
    family_to_tracks: dict[str, list[str]] = {}
    notes: list[str] = []

    for track in manifest["tracks"]:
        summary, track_notes = _evaluate_track(
            track=track,
            junit_all=junit_all,
            junit_passing=junit_passing,
            benchmark_all=benchmark_all,
            benchmark_passing=benchmark_passing,
            evidence_payload=evidence_payload,
        )
        track_summaries[summary.track_id] = summary
        family_to_tracks.setdefault(summary.artifact_family, []).append(summary.track_id)
        notes.extend(track_notes)

    family_summaries: dict[str, FoundryPhase2FamilySummary] = {}
    for artifact_family, track_ids in family_to_tracks.items():
        family_payload = next(
            (
                item
                for item in manifest["tracks"]
                if str(item.get("artifact_family") or "").strip() == artifact_family
            ),
            None,
        )
        statuses = [track_summaries[track_id] for track_id in track_ids]
        passes_all = all(item.passes_all for item in statuses)
        family_summaries[artifact_family] = FoundryPhase2FamilySummary(
            artifact_family=artifact_family,
            applies_to=tuple(
                dict.fromkeys(
                    [
                        artifact_family,
                        *(
                            _normalize_named_items(family_payload.get("applies_to"))
                            if isinstance(family_payload, dict)
                            else ()
                        ),
                    ]
                )
            ),
            blocking_transition=str(
                (
                    family_payload.get("blocking_transition")
                    if isinstance(family_payload, dict)
                    else manifest.get("blocking_transition")
                )
                or "PROOF_ONLY->ENGINEER_READY"
            ),
            passes_all=passes_all,
            status="pass" if passes_all else "incomplete",
            track_ids=tuple(track_ids),
        )

    overall_status = (
        "complete" if all(summary.passes_all for summary in track_summaries.values()) else "incomplete"
    )
    return FoundryPhase2ClosureReport(
        phase_id=str(manifest.get("phase_id") or "foundry.phase2"),
        overall_status=overall_status,
        manifest_path=_repo_relative(manifest_path, repo_root),
        acceptance_junit_xml=_repo_relative(acceptance_junit_xml, repo_root),
        benchmark_report=_repo_relative(benchmark_report, repo_root),
        evidence_report=_repo_relative(evidence_report, repo_root),
        source_of_truth=dict(manifest.get("source_of_truth") or {}),
        tracks=track_summaries,
        artifact_families=family_summaries,
        notes=tuple(notes),
    )


def persist_foundry_phase2_closure_report(
    store: FileSystemCAS,
    report: FoundryPhase2ClosureReport,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRef:
    """Persist the canonical Phase 2 closure report into CAS."""

    return store.put_json(
        report,
        PutOptions(
            kind="foundry.phase2_closure_report",
            media_type="application/json",
            schema=SchemaInfo(name=PHASE2_CLOSURE_SCHEMA_NAME, version=report.schema_version),
            inputs=list(inputs or []),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def load_foundry_phase2_closure_report(
    store: FileSystemCAS,
    ref: ArtifactRef,
) -> FoundryPhase2ClosureReport:
    """Load the canonical Phase 2 closure report from CAS."""

    payload = from_canonical_bytes(store.get_bytes(ref.artifact_id))
    return FoundryPhase2ClosureReport.model_validate(payload)


def load_foundry_phase2_closure_report_from_path(
    path: Path,
) -> FoundryPhase2ClosureReport:
    """Load the canonical Phase 2 closure report from disk."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    return FoundryPhase2ClosureReport.model_validate(payload)


def maybe_load_foundry_phase2_closure_report(
    *,
    repo_root: Path | None = None,
    explicit_path: str | Path | None = None,
) -> FoundryPhase2ClosureReport | None:
    """Best-effort runtime loader for the latest Phase 2 closure report."""

    candidate = explicit_path
    if candidate is None:
        env_value = os.environ.get(PHASE2_CLOSURE_ENV_VAR)
        if env_value:
            candidate = env_value
    if candidate is None:
        candidate = default_foundry_phase2_closure_report_path(repo_root=repo_root)
    path = Path(candidate)
    if not path.exists():
        return None
    try:
        return load_foundry_phase2_closure_report_from_path(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return None


__all__ = [
    "FoundryPhase2ClosureReport",
    "FoundryPhase2FamilySummary",
    "FoundryPhase2TrackSummary",
    "PHASE2_CLOSURE_ENV_VAR",
    "PHASE2_CLOSURE_SCHEMA_NAME",
    "build_foundry_phase2_closure_report",
    "default_foundry_phase2_closure_report_path",
    "default_foundry_phase2_manifest_path",
    "load_foundry_phase2_closure_report",
    "load_foundry_phase2_closure_report_from_path",
    "maybe_load_foundry_phase2_closure_report",
    "normalize_phase2_artifact_family",
    "persist_foundry_phase2_closure_report",
]

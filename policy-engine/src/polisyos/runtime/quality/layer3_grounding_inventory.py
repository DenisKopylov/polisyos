"""Layer 3 G0 grounding inventory contracts and read-only producers.

This module freezes the pre-adapter Layer 3 discipline. It inspects existing
repository artifacts as data, registers source touchpoints in shadow form, and
validates that quarantine/status/firewall rules block adapter admission before
any G1+ adapter work begins.
"""

from __future__ import annotations

import ast
import hashlib
import json
import tomllib
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

from pydantic import AliasChoices, Field, model_validator

from polisyos.pdc import AuthorityBoundary, Layer2ReadinessModel

LAYER3_G0_SCHEMA_VERSION = "policyos.policy_design_case.layer3_g0_grounding_inventory.v1"
LAYER3_G0_RULE_VERSION = "policyos.layer3.g0.grounding_subordination.v1"
LAYER3_G0_MANIFEST_ID = "layer3.g0.readiness"
SOURCE_TOUCHPOINT_SCAN_MODE = "ast_top_level_and_local_imports"
AUTHORITY_POSTURE = "llm_output_candidate_never_authority"
ADR_ACCEPTANCE_AUTHORITY = "human_principal_required"
NO_ADAPTER_ADMISSION_BEFORE_G0 = True
FIRST_VERTICAL_CORPUS_CASE_ID = "ua-msme-affordable-loans-2022"
FIRST_VERTICAL_CONSTRUCT_BUNDLE_ID = "ukrainian_msme_credit_constructs"

PDC_IMPORT_ALLOWLIST_ROOTS: tuple[str, ...] = ("core",)
PDC_IMPORT_ALLOWLIST_RATIONALE = (
    "core is shared primitive/DTO infrastructure, not a capability source"
)
POLICY_TOML_PDC_CONFLICT_ROOTS: tuple[str, ...] = ("runtime", "scientist", "ir")

CapabilityDisposition = Literal[
    "integrate_as_is",
    "integrate_after_refactor",
    "wrap_then_strangle",
    "quarantine",
]
DataKind = Literal["data_asset", "acquisition", "processing_transform"]
AdapterMaturity = Literal["fail_closed", "predictive", "calibrated"]
PromotionState = Literal["shadow", "governed_promoted", "promotion_blocked"]
AdapterAdmissionState = Literal["candidate_shadow_only", "blocked", "admitted"]
ConformanceStatus = Literal["not_run_pre_adapter", "pass", "blocked"]
GroundingDisposition = Literal[
    "grounded_binding",
    "grounded_limited",
    "grounded_abstention",
    "ungrounded_blocked",
]
HealthMetricId = Literal[
    "envelope-expansion-rate",
    "adapter-semantic-loss",
    "governance-throughput",
    "demand-pull-vs-abstention",
]
SourceTouchpointRegistrationStatus = Literal[
    "registered_pre_admission",
    "requires_adapter_contract",
    "blocked_by_quarantine",
]
PortlessCapabilityOpenQuestionStatus = Literal[
    "governed_open_question",
    "not_required",
]
BindingConstraintRank = Literal["substrate", "causal_support", "calibration"]
AdapterCostClass = Literal["near_typed", "raw", "conceptual_legacy"]
ValidationStatus = Literal["pass", "fail"]

_RUNTIME_QUALITY_SOURCE_ROOTS = frozenset(
    {
        "data_forge",
        "data_requirement",
        "fabric",
        "foundry",
        "lex",
        "method_requirement",
        "participation_requirement",
        "scholar",
        "scholar_requirement",
        "scientist",
    }
)
_REQUIRED_DATA_ASSET_ROOTS: tuple[str, ...] = (
    "production_data",
    "tools/ops_runners/ukraine_data",
    "tests/fixtures/universal-corpus/cases",
    "tests/fixtures/universal-corpus/producer_stubs",
    (
        "tests/fixtures/policy_design_case/semantic_evaluation_packs/hidden/"
        "layer2-sealed-universality-battery"
    ),
    "docs/research/universal-policy-design/outcome-corpus",
)
_STATUS_RULE_IDS: tuple[str, ...] = (
    "quarantine_dominates_admission",
    "pre_adapter_conformance_cannot_admit_authority",
    "maturity_cannot_exceed_evidence",
    "promotion_blocked_before_g4",
)
_HEALTH_METRICS: tuple[HealthMetricId, ...] = (
    "envelope-expansion-rate",
    "adapter-semantic-loss",
    "governance-throughput",
    "demand-pull-vs-abstention",
)


class ValidationIssue(Layer2ReadinessModel):
    """One content validation issue emitted by the G0 validator."""

    code: str = Field(..., min_length=1, max_length=160)
    path: str = Field(..., min_length=1, max_length=500)
    message: str = Field(..., min_length=1, max_length=1000)


class ValidationReport(Layer2ReadinessModel):
    """Validation report with issue list and derived summary metrics."""

    status: ValidationStatus
    issues: list[ValidationIssue] = Field(default_factory=list, max_length=500)
    summary: dict[str, Any] = Field(default_factory=dict)


class CapabilityInventoryEntry(Layer2ReadinessModel):
    """Inventory row for a package or data/corpus source root."""

    capability_id: str = Field(..., min_length=1, max_length=200)
    package_kind: str = Field(..., min_length=1, max_length=120)
    path: str = Field(..., min_length=1, max_length=500)
    file_count: int = Field(default=0, ge=0)
    loc: int = Field(default=0, ge=0)
    owner_evidence_ref: str = Field(..., min_length=1, max_length=500)
    current_capability_label: str = Field(..., min_length=1, max_length=120)
    current_imports: list[str] = Field(default_factory=list, max_length=200)
    source_refs: list[str] = Field(default_factory=list, max_length=200)
    mapped_port_ids: list[str] = Field(default_factory=list, max_length=80)


class DataAssetInventoryEntry(Layer2ReadinessModel):
    """Inventory row for one data asset discovered under a required root."""

    asset_id: str = Field(..., min_length=1, max_length=240)
    data_kind: DataKind
    path: str = Field(..., min_length=1, max_length=700)
    owning_root: str = Field(..., min_length=1, max_length=500)
    size_bytes: int | None = Field(default=None, ge=0)
    owner_evidence_ref: str = Field(..., min_length=1, max_length=700)
    lineage_evidence_ref: str = Field(..., min_length=1, max_length=700)
    rights_evidence_ref: str = Field(..., min_length=1, max_length=700)
    freshness_evidence_ref: str = Field(..., min_length=1, max_length=700)
    fitness_evidence_ref: str = Field(..., min_length=1, max_length=700)
    contamination_check_ref: str = Field(..., min_length=1, max_length=700)


class ProcessingTransformInventoryEntry(Layer2ReadinessModel):
    """Inventory row for one processing transform under a required root."""

    transform_id: str = Field(..., min_length=1, max_length=240)
    source_root: str = Field(..., min_length=1, max_length=500)
    output_asset_refs: list[str] = Field(default_factory=list, max_length=100)
    transform_script_refs: list[str] = Field(..., min_length=1, max_length=50)
    owner_evidence_ref: str = Field(..., min_length=1, max_length=700)
    replay_command_ref: str = Field(..., min_length=1, max_length=700)
    contamination_risk_refs: list[str] = Field(..., min_length=1, max_length=50)


class RequiredDataAssetRoot(Layer2ReadinessModel):
    """Required G0 data/corpus root and the entries discovered under it."""

    root_id: str = Field(..., min_length=1, max_length=180)
    path: str = Field(..., min_length=1, max_length=500)
    discovered_assets: list[str] = Field(default_factory=list, max_length=1000)
    discovered_transforms: list[str] = Field(default_factory=list, max_length=200)


class CapabilityTriageRecord(Layer2ReadinessModel):
    """Triage disposition for a capability source before adapter admission."""

    capability_id: str = Field(..., min_length=1, max_length=200)
    disposition: CapabilityDisposition
    rationale: str = Field(..., min_length=1, max_length=1000)
    evidence_refs: list[str] = Field(..., min_length=1, max_length=60)
    missing_capability_labels: list[str] = Field(default_factory=list, max_length=20)
    quarantine_ref: str | None = Field(default=None, max_length=500)
    adapter_admissibility: str = Field(..., min_length=1, max_length=120)
    authority_boundary: AuthorityBoundary | None = None


class QuarantineRegistryEntry(Layer2ReadinessModel):
    """Hard blocker entry consumed by adapter-admission validation."""

    target_id: str = Field(..., min_length=1, max_length=200)
    target_kind: str = Field(..., min_length=1, max_length=120)
    reason: str = Field(..., min_length=1, max_length=1000)
    pattern_ids: list[str] = Field(..., min_length=1, max_length=20)
    blocker_codes: list[str] = Field(..., min_length=1, max_length=30)
    enforcement_surface: str = Field(..., min_length=1, max_length=200)
    release_condition: str = Field(..., min_length=1, max_length=1000)


class Port(Layer2ReadinessModel):
    """Derived narrow-waist port from the cluster ownership map."""

    port_id: str = Field(
        ...,
        validation_alias=AliasChoices("port_id", "id"),
        min_length=1,
        max_length=200,
    )
    cluster: str = Field(..., min_length=1, max_length=80)
    facet: str = Field(..., min_length=1, max_length=160)
    publishes: list[str] = Field(default_factory=list, max_length=200)
    consumes: list[str] = Field(default_factory=list, max_length=200)
    source_line_ref: str = Field(..., min_length=1, max_length=700)


class PortlessCapabilityOpenQuestion(Layer2ReadinessModel):
    """Governed waist-change question for a capability with no current port."""

    capability_id: str = Field(..., min_length=1, max_length=200)
    missing_port_rationale: str = Field(..., min_length=1, max_length=1000)
    why_existing_ports_cannot_express_it: str = Field(..., min_length=1, max_length=1000)
    proposed_waist_change_question: str = Field(..., min_length=1, max_length=1000)
    owner: str = Field(..., min_length=1, max_length=200)
    evidence_refs: list[str] = Field(..., min_length=1, max_length=40)
    status: PortlessCapabilityOpenQuestionStatus


class SourceTouchpointRegistration(Layer2ReadinessModel):
    """Registration for one runtime/quality import of a subordinate source root."""

    touchpoint_id: str = Field(..., min_length=1, max_length=300)
    file: str = Field(..., min_length=1, max_length=500)
    line: int = Field(..., ge=1)
    import_root: str = Field(..., min_length=1, max_length=120)
    source_module: str = Field(..., min_length=1, max_length=500)
    registration_status: SourceTouchpointRegistrationStatus
    existing_source_truth_adapter_path_ref: str | None = Field(default=None, max_length=300)
    quarantine_check_result: str = Field(..., min_length=1, max_length=160)
    admission_allowed: bool = False


class AdapterAdmissionRecord(Layer2ReadinessModel):
    """Pre-admission adapter candidate record. G0 never admits adapters."""

    adapter_id: str = Field(..., min_length=1, max_length=240)
    source_ids: list[str] = Field(..., min_length=1, max_length=80)
    port_ids: list[str] = Field(..., min_length=1, max_length=80)
    maturity: AdapterMaturity
    promotion_state: PromotionState
    conformance_status: ConformanceStatus
    quarantine_check: str = Field(..., min_length=1, max_length=160)
    admission_state: AdapterAdmissionState
    admitted: bool = False
    adapter_contract_path_refs: list[str] = Field(default_factory=list, max_length=40)
    source_touchpoint_refs: list[str] = Field(default_factory=list, max_length=200)


class DataAssetPort(Layer2ReadinessModel):
    """Data asset binding to one or more G0 ports with evidence refs."""

    asset_id: str = Field(..., min_length=1, max_length=240)
    data_kind: DataKind
    path: str = Field(..., min_length=1, max_length=700)
    lineage_ref: str = Field(..., min_length=1, max_length=700)
    rights_ref: str = Field(..., min_length=1, max_length=700)
    freshness_ref: str = Field(..., min_length=1, max_length=700)
    fitness_ref: str = Field(..., min_length=1, max_length=700)
    contamination_check_ref: str = Field(..., min_length=1, max_length=700)
    port_ids: list[str] = Field(..., min_length=1, max_length=40)


class ConformanceHarnessRecord(Layer2ReadinessModel):
    """Pre-adapter conformance harness skeleton using existing preservation paths."""

    harness_id: str = Field(..., min_length=1, max_length=200)
    existing_source_truth_adapter_path_refs: list[str] = Field(..., min_length=1)
    adapter_loss_blocker_refs: list[str] = Field(..., min_length=1)
    status: ConformanceStatus
    negative_fixtures: list[str] = Field(..., min_length=1, max_length=80)


class HealthMetricLedger(Layer2ReadinessModel):
    """Frozen G0 health metric ledger row."""

    metric_id: HealthMetricId
    owner: str = Field(..., min_length=1, max_length=200)
    freeze_value: str | int | float | dict[str, Any]
    trend_vocabulary: list[str] = Field(..., min_length=1, max_length=10)
    per_slice_delta_rule: str = Field(..., min_length=1, max_length=1000)
    next_update_rule: str = Field(..., min_length=1, max_length=1000)


class StatusCompositionRule(Layer2ReadinessModel):
    """Rule proving G0 status composition cannot launder authority."""

    rule_id: str = Field(..., min_length=1, max_length=200)
    inputs: list[str] = Field(..., min_length=1, max_length=20)
    composed_result: str = Field(..., min_length=1, max_length=200)
    issue_code: str = Field(..., min_length=1, max_length=160)
    negative_fixture_ref: str = Field(..., min_length=1, max_length=700)


class EmptyPortMapEntry(Layer2ReadinessModel):
    """Empty-port blocker for the first vertical proving-ground case."""

    port_id: str = Field(..., min_length=1, max_length=200)
    proving_ground_case_id: str = Field(..., min_length=1, max_length=200)
    blocker_cause: str = Field(..., min_length=1, max_length=1000)
    binding_constraint_rank: BindingConstraintRank
    next_adapter_dependency: str = Field(..., min_length=1, max_length=300)


class AdapterCostMapEntry(Layer2ReadinessModel):
    """Adapter sequencing cost row for one source/port pair."""

    source_id: str = Field(..., min_length=1, max_length=200)
    port_id: str = Field(..., min_length=1, max_length=200)
    near_typed_raw_classification: AdapterCostClass
    existing_contract_refs: list[str] = Field(default_factory=list, max_length=50)
    adapter_effort_tier: str = Field(..., min_length=1, max_length=80)
    semantic_loss_risk: str = Field(..., min_length=1, max_length=500)
    sequencing_priority: int = Field(..., ge=1)


class FirstVerticalCaseRecord(Layer2ReadinessModel):
    """First vertical case identifiers kept separate across corpus and constructs."""

    case_ref: str = Field(..., min_length=1, max_length=500)
    first_vertical_corpus_case_id: str = Field(..., min_length=1, max_length=200)
    first_vertical_construct_bundle_id: str = Field(..., min_length=1, max_length=200)
    authority_posture: str = Field(..., min_length=1, max_length=200)


class CapabilityDataInventory(Layer2ReadinessModel):
    """Capability inventory for immediate source packages and data roots."""

    entries: list[CapabilityInventoryEntry] = Field(default_factory=list, max_length=300)
    summary: dict[str, Any] = Field(default_factory=dict)


class DataAssetInventory(Layer2ReadinessModel):
    """Data/corpus inventory with asset-level and transform-level rows."""

    scan_mode: str = Field(default="manifest_backed_lightweight")
    required_roots: list[RequiredDataAssetRoot] = Field(default_factory=list, max_length=20)
    data_assets: list[DataAssetInventoryEntry] = Field(default_factory=list, max_length=3000)
    processing_transforms: list[ProcessingTransformInventoryEntry] = Field(
        default_factory=list,
        max_length=300,
    )
    summary: dict[str, Any] = Field(default_factory=dict)


class PortMap(Layer2ReadinessModel):
    """Derived G0 port map."""

    ports: list[Port] = Field(default_factory=list, max_length=200)
    portless_capability_open_questions: list[PortlessCapabilityOpenQuestion] = Field(
        default_factory=list,
        max_length=100,
    )
    summary: dict[str, Any] = Field(default_factory=dict)


class RuntimeQualityTouchpointInventory(Layer2ReadinessModel):
    """AST-scanned runtime/quality source touchpoint inventory."""

    scan_mode: str = SOURCE_TOUCHPOINT_SCAN_MODE
    registrations: list[SourceTouchpointRegistration] = Field(
        default_factory=list,
        max_length=500,
    )
    summary: dict[str, Any] = Field(default_factory=dict)

    def __iter__(self) -> Iterator[SourceTouchpointRegistration]:
        """Iterate over source touchpoint registrations."""

        return iter(self.registrations)

    def __len__(self) -> int:
        """Return the number of source touchpoint registrations."""

        return len(self.registrations)


class ImportFirewallViolation(Layer2ReadinessModel):
    """Forbidden pdc import discovered by the Layer 3 G0 firewall."""

    file: str = Field(..., min_length=1, max_length=500)
    line: int = Field(..., ge=1)
    import_root: str = Field(..., min_length=1, max_length=120)
    issue_code: str = "layer3_g0_pdc_non_waist_import"


class ImportFirewallReport(Layer2ReadinessModel):
    """Report for the strict Layer 3 pdc narrow-waist import firewall."""

    allowlist_roots: list[str] = Field(default_factory=lambda: list(PDC_IMPORT_ALLOWLIST_ROOTS))
    allowlist_rationale: str = PDC_IMPORT_ALLOWLIST_RATIONALE
    forbidden_roots: list[str] = Field(default_factory=list, max_length=200)
    violations: list[ImportFirewallViolation] = Field(default_factory=list, max_length=500)
    summary: dict[str, Any] = Field(default_factory=dict)


class StatusCompositionMatrix(Layer2ReadinessModel):
    """Four-rule status composition matrix required by G0."""

    rules: list[StatusCompositionRule] = Field(..., min_length=4, max_length=4)

    @model_validator(mode="after")
    def _validate_exact_rule_set(self) -> StatusCompositionMatrix:
        if tuple(rule.rule_id for rule in self.rules) != _STATUS_RULE_IDS:
            raise ValueError("status composition matrix must use the exact G0 rule set")
        return self


class Layer3G0ReadinessManifest(Layer2ReadinessModel):
    """Replay/check manifest summarizing G0 closure artifacts and runtime counts."""

    manifest_id: str = LAYER3_G0_MANIFEST_ID
    schema_version: str = LAYER3_G0_SCHEMA_VERSION
    rule_version: str = LAYER3_G0_RULE_VERSION
    closure_artifact_paths: list[str] = Field(default_factory=list, max_length=20)
    counts: dict[str, Any] = Field(default_factory=dict)
    adr_ref: str = "docs/adr/0175-layer3-grounding-subordination-discipline.md"
    first_vertical_corpus_case_id: str = FIRST_VERTICAL_CORPUS_CASE_ID
    first_vertical_construct_bundle_id: str = FIRST_VERTICAL_CONSTRUCT_BUNDLE_ID
    runtime_builder_hash: str = Field(..., min_length=8, max_length=96)


class Layer3G0Bundle(Layer2ReadinessModel):
    """In-memory G0 bundle produced from committed repository state."""

    capability_inventory: CapabilityDataInventory
    data_asset_inventory: DataAssetInventory
    triage_registry: list[CapabilityTriageRecord]
    quarantine_registry: list[QuarantineRegistryEntry]
    port_map: PortMap
    runtime_quality_touchpoints: RuntimeQualityTouchpointInventory
    adapter_admission_registry: list[AdapterAdmissionRecord]
    data_asset_ports: list[DataAssetPort]
    conformance_harness: ConformanceHarnessRecord
    health_metric_ledgers: list[HealthMetricLedger]
    import_firewall_lint: ImportFirewallReport
    status_composition_matrix: StatusCompositionMatrix
    empty_port_map: list[EmptyPortMapEntry]
    adapter_cost_map: list[AdapterCostMapEntry]
    first_vertical_case: FirstVerticalCaseRecord
    readiness_manifest: Layer3G0ReadinessManifest


def build_capability_inventory(repo_root: Path) -> CapabilityDataInventory:
    """Build the G0 capability inventory from immediate packages and data roots."""

    src_root = repo_root / "src/polisyos"
    entries: list[CapabilityInventoryEntry] = []
    for package_path in sorted(path for path in src_root.iterdir() if path.is_dir()):
        if package_path.name == "__pycache__":
            continue
        rel = _repo_path(package_path, repo_root)
        py_files = sorted(package_path.rglob("*.py"))
        readme = package_path / "README.md"
        owner_ref = _repo_ref(readme if readme.exists() else package_path, repo_root)
        entries.append(
            CapabilityInventoryEntry(
                capability_id=package_path.name,
                package_kind=_package_kind(package_path.name),
                path=rel,
                file_count=len(py_files),
                loc=sum(_line_count(path) for path in py_files),
                owner_evidence_ref=owner_ref,
                current_capability_label="implemented_but_not_orchestrated"
                if package_path.name in _RUNTIME_QUALITY_SOURCE_ROOTS
                else "surface_out_of_scope"
                if package_path.name in {"common", "schemas"}
                else "implemented",
                current_imports=_imports_for_package(package_path),
                source_refs=[owner_ref],
                mapped_port_ids=[]
                if package_path.name != "runtime"
                else ["DESIGNER_ITSELF.closeout"],
            )
        )

    for root in _REQUIRED_DATA_ASSET_ROOTS:
        path = repo_root / root
        entries.append(
            CapabilityInventoryEntry(
                capability_id=_slug(root),
                package_kind="data_corpus_root",
                path=root,
                file_count=_file_count(path),
                loc=0,
                owner_evidence_ref=_repo_ref(
                    path / "README.md" if (path / "README.md").exists() else path, repo_root
                ),
                current_capability_label="artifact_missing",
                current_imports=[],
                source_refs=[_repo_ref(path, repo_root)],
                mapped_port_ids=["DESIGNER_ITSELF.cluster_evidence"],
            )
        )

    return CapabilityDataInventory(
        entries=entries,
        summary={
            "source_package_count": sum(
                1 for entry in entries if entry.package_kind != "data_corpus_root"
            ),
            "required_data_asset_root_count": len(_REQUIRED_DATA_ASSET_ROOTS),
        },
    )


def build_data_asset_inventory(repo_root: Path) -> DataAssetInventory:
    """Build a manifest-backed data and processing transform inventory."""

    required_roots: list[RequiredDataAssetRoot] = []
    data_assets: list[DataAssetInventoryEntry] = []
    transforms: list[ProcessingTransformInventoryEntry] = []

    production_root = repo_root / "production_data"
    root_manifest_path = production_root / "manifest.json"
    root_manifest = _load_json(root_manifest_path)
    bundles = root_manifest.get("bundles", {})
    production_assets: list[str] = []
    if isinstance(bundles, Mapping):
        for bundle_id, bundle in bundles.items():
            if not isinstance(bundle, Mapping):
                continue
            asset_path = f"production_data/{bundle.get('path', bundle_id)}"
            production_assets.append(asset_path)
            data_assets.append(
                _data_asset_entry(
                    asset_id=f"production-data-{_slug(str(bundle_id))}",
                    path=asset_path,
                    owning_root="production_data",
                    evidence_path=root_manifest_path,
                    repo_root=repo_root,
                )
            )

    ukraine_manifest_path = (
        production_root / "ukraine_agent_simulation_baseline_20260410/FINAL_ARTIFACTS_MANIFEST.json"
    )
    ukraine_manifest = _load_json(ukraine_manifest_path)
    ukraine_files = ukraine_manifest.get("files", [])
    if isinstance(ukraine_files, Sequence) and not isinstance(ukraine_files, (str, bytes)):
        for row in ukraine_files:
            if not isinstance(row, Mapping):
                continue
            rel_path = str(row.get("path", ""))
            if not rel_path:
                continue
            asset_path = f"production_data/ukraine_agent_simulation_baseline_20260410/{rel_path}"
            production_assets.append(asset_path)
            data_assets.append(
                _data_asset_entry(
                    asset_id=f"ukraine-simulation-{_slug(rel_path)}",
                    path=asset_path,
                    owning_root="production_data",
                    evidence_path=ukraine_manifest_path,
                    repo_root=repo_root,
                    size_bytes=_int_or_none(row.get("size_bytes")),
                )
            )

    academic_split_path = (
        production_root / "policyos_academic_runtime_slim_20260411T112032Z/SPLIT_MANIFEST.json"
    )
    academic_split = _load_json(academic_split_path)
    included_paths = academic_split.get("included_runtime_paths", [])
    if isinstance(included_paths, Sequence) and not isinstance(included_paths, (str, bytes)):
        for rel_path in included_paths:
            asset_path = (
                f"production_data/policyos_academic_runtime_slim_20260411T112032Z/{rel_path}"
            )
            production_assets.append(asset_path)
            data_assets.append(
                _data_asset_entry(
                    asset_id=f"academic-runtime-{_slug(str(rel_path))}",
                    path=asset_path,
                    owning_root="production_data",
                    evidence_path=academic_split_path,
                    repo_root=repo_root,
                )
            )

    required_roots.append(
        RequiredDataAssetRoot(
            root_id="production_data",
            path="production_data",
            discovered_assets=sorted(set(production_assets)),
            discovered_transforms=[],
        )
    )

    ops_root = repo_root / "tools/ops_runners/ukraine_data"
    ops_scripts = sorted(
        _repo_path(path, repo_root) for path in ops_root.glob("*.py") if path.name != "__init__.py"
    )
    data_assets.append(
        _data_asset_entry(
            asset_id="ukraine-ops-runner-root",
            path="tools/ops_runners/ukraine_data",
            owning_root="tools/ops_runners/ukraine_data",
            evidence_path=ops_root / "README.md",
            repo_root=repo_root,
        )
    )
    for script in ops_scripts:
        transforms.append(
            ProcessingTransformInventoryEntry(
                transform_id=f"ukraine-ops-{_slug(Path(script).stem)}",
                source_root="tools/ops_runners/ukraine_data",
                output_asset_refs=["tools/ops_runners/ukraine_data"],
                transform_script_refs=[script],
                owner_evidence_ref=_repo_ref(ops_root / "README.md", repo_root),
                replay_command_ref=f"uv run python {script}",
                contamination_risk_refs=[_repo_ref(ops_root / "README.md", repo_root)],
            )
        )
    required_roots.append(
        RequiredDataAssetRoot(
            root_id="ukraine_ops_runners",
            path="tools/ops_runners/ukraine_data",
            discovered_assets=["tools/ops_runners/ukraine_data"],
            discovered_transforms=ops_scripts,
        )
    )

    for root in _REQUIRED_DATA_ASSET_ROOTS[2:]:
        root_path = repo_root / root
        discovered = sorted(
            _repo_path(path, repo_root) for path in root_path.rglob("*") if path.is_file()
        )
        for asset_path in discovered:
            data_assets.append(
                _data_asset_entry(
                    asset_id=_bounded_id(_slug(root), asset_path),
                    path=asset_path,
                    owning_root=root,
                    evidence_path=root_path / "README.md"
                    if (root_path / "README.md").exists()
                    else root_path / "manifest.json"
                    if (root_path / "manifest.json").exists()
                    else root_path,
                    repo_root=repo_root,
                )
            )
        required_roots.append(
            RequiredDataAssetRoot(
                root_id=_slug(root),
                path=root,
                discovered_assets=discovered,
                discovered_transforms=[],
            )
        )

    summary = {
        "required_data_asset_root_count": len(_REQUIRED_DATA_ASSET_ROOTS),
        "data_asset_inventory_unclassified_discovered_count": 0,
        "processing_transform_inventory_unclassified_discovered_count": 0,
        "data_asset_count": len(data_assets),
        "processing_transform_count": len(transforms),
        "production_data_manifest_bundle_count": len(bundles)
        if isinstance(bundles, Mapping)
        else 0,
        "ukraine_simulation_manifest_file_count": len(ukraine_files)
        if isinstance(ukraine_files, Sequence) and not isinstance(ukraine_files, (str, bytes))
        else 0,
        "academic_runtime_slim_split_file_count": int(
            academic_split.get("file_count", len(included_paths))
        ),
        "universal_corpus_fixture_count": _universal_corpus_fixture_count(repo_root),
        "ukraine_ops_runner_script_count": len(ops_scripts),
    }
    return DataAssetInventory(
        required_roots=required_roots,
        data_assets=data_assets,
        processing_transforms=transforms,
        summary=summary,
    )


def build_port_map_from_cluster_map(cluster_map_path: Path) -> PortMap:
    """Derive G0 ports and publishes/consumes edges from the cluster map."""

    payload = _load_toml(cluster_map_path)
    graph = _mapping(payload.get("handshake_graph"))
    port_ids = [str(port_id) for port_id in _sequence(graph.get("ports"))]
    cells = _mapping(payload.get("cell"))
    publish_index: dict[str, list[str]] = {port_id: [] for port_id in port_ids}
    consume_index: dict[str, list[str]] = {port_id: [] for port_id in port_ids}
    for cluster, cluster_cells in cells.items():
        if not isinstance(cluster_cells, Mapping):
            continue
        for axis, cell in cluster_cells.items():
            if not isinstance(cell, Mapping):
                continue
            cell_ref = f"{cluster}.{axis}"
            for published in _sequence(cell.get("publishes")):
                if str(published) in publish_index:
                    publish_index[str(published)].append(cell_ref)
            for consumed in _sequence(cell.get("consumes")):
                if str(consumed) in consume_index:
                    consume_index[str(consumed)].append(cell_ref)

    ports = []
    for port_id in port_ids:
        cluster, _, facet = port_id.partition(".")
        ports.append(
            Port(
                port_id=port_id,
                cluster=cluster,
                facet=facet,
                publishes=sorted(publish_index[port_id]),
                consumes=sorted(consume_index[port_id]),
                source_line_ref=_line_ref(cluster_map_path, f'"{port_id}"'),
            )
        )

    return PortMap(
        ports=ports,
        portless_capability_open_questions=[
            PortlessCapabilityOpenQuestion(
                capability_id="lex_binary_status_candidate",
                missing_port_rationale=(
                    "Binary legal status is a projection risk, not a package-wide Layer 3 port."
                ),
                why_existing_ports_cannot_express_it=(
                    "Existing ports can carry legal authority only after graded "
                    "Lex authority and adapter-loss evidence are bound."
                ),
                proposed_waist_change_question=(
                    "Should a future Layer 3 slice add a legal-authority adapter "
                    "port after graded Lex evidence is proven?"
                ),
                owner="principal-governance",
                evidence_refs=[
                    "repo://src/polisyos/lex/legal_evaluation/backends/simple_v1.py#L15",
                    "repo://src/polisyos/lex/normpack/legal_authority.py#L303",
                ],
                status="governed_open_question",
            )
        ],
        summary={
            "port_count": len(ports),
            "source": _repo_path(cluster_map_path, _repo_root_from_artifact(cluster_map_path)),
        },
    )


def build_runtime_quality_touchpoint_inventory(
    repo_root: Path,
) -> RuntimeQualityTouchpointInventory:
    """AST-scan runtime/quality imports of subordinate source packages."""

    registrations: list[SourceTouchpointRegistration] = []
    quality_root = repo_root / "src/polisyos/runtime/quality"
    for path in sorted(quality_root.glob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            continue
        rel_file = _repo_path(path, repo_root)
        for node in ast.walk(tree):
            import_refs = _polisyos_import_refs(node)
            for import_root, source_module in import_refs:
                if import_root not in _RUNTIME_QUALITY_SOURCE_ROOTS:
                    continue
                touchpoint_id = f"{rel_file}:{node.lineno}:{import_root}"
                registrations.append(
                    SourceTouchpointRegistration(
                        touchpoint_id=touchpoint_id,
                        file=rel_file,
                        line=node.lineno,
                        import_root=import_root,
                        source_module=source_module,
                        registration_status="registered_pre_admission",
                        existing_source_truth_adapter_path_ref=None,
                        quarantine_check_result="not_blocked",
                        admission_allowed=False,
                    )
                )

    registrations.sort(key=lambda row: (row.file, row.line, row.import_root, row.source_module))
    return RuntimeQualityTouchpointInventory(
        registrations=registrations,
        summary={
            "runtime_quality_touchpoint_count": len(registrations),
            "runtime_quality_touchpoints_without_registration": 0,
            "runtime_quality_touchpoint_admission_allowed_without_contract_count": sum(
                1
                for row in registrations
                if row.admission_allowed and not row.existing_source_truth_adapter_path_ref
            ),
        },
    )


def build_import_firewall_report(repo_root: Path) -> ImportFirewallReport:
    """Scan pdc source files for non-waist imports forbidden by Layer 3 G0."""

    immediate_roots = _immediate_polisyos_roots(repo_root)
    forbidden = sorted(
        root for root in immediate_roots if root not in {"pdc", *PDC_IMPORT_ALLOWLIST_ROOTS}
    )
    violations: list[ImportFirewallViolation] = []
    for path in sorted((repo_root / "src/polisyos/pdc").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        rel_file = _repo_path(path, repo_root)
        for node in ast.walk(tree):
            for import_root, _source_module in _polisyos_import_refs(node):
                if import_root in forbidden:
                    violations.append(
                        ImportFirewallViolation(
                            file=rel_file,
                            line=node.lineno,
                            import_root=import_root,
                        )
                    )

    return ImportFirewallReport(
        forbidden_roots=forbidden,
        violations=violations,
        summary={
            "pdc_non_waist_import_count": len(violations),
            "allowlist_roots": list(PDC_IMPORT_ALLOWLIST_ROOTS),
        },
    )


def build_status_composition_matrix() -> StatusCompositionMatrix:
    """Build the exact four G0 status-composition rules."""

    return StatusCompositionMatrix(
        rules=[
            StatusCompositionRule(
                rule_id="quarantine_dominates_admission",
                inputs=["quarantine_check", "admission_state"],
                composed_result="blocked",
                issue_code="layer3_g0_quarantined_source_admitted",
                negative_fixture_ref=(
                    "tests/fixtures/layer3/g0/malformed_adapter_admission_quarantined_source.json"
                ),
            ),
            StatusCompositionRule(
                rule_id="pre_adapter_conformance_cannot_admit_authority",
                inputs=["conformance_status", "admitted"],
                composed_result="candidate_shadow_only",
                issue_code="layer3_g0_status_composition_missing",
                negative_fixture_ref=(
                    "tests/fixtures/layer3/g0/malformed_adapter_admission_quarantined_source.json"
                ),
            ),
            StatusCompositionRule(
                rule_id="maturity_cannot_exceed_evidence",
                inputs=["maturity", "conformance_status"],
                composed_result="fail_closed",
                issue_code="layer3_g0_adapter_maturity_overclaim",
                negative_fixture_ref=(
                    "tests/fixtures/layer3/g0/malformed_adapter_admission_quarantined_source.json"
                ),
            ),
            StatusCompositionRule(
                rule_id="promotion_blocked_before_g4",
                inputs=["promotion_state", "slice"],
                composed_result="promotion_blocked",
                issue_code="layer3_g0_status_composition_missing",
                negative_fixture_ref=(
                    "tests/fixtures/layer3/g0/malformed_adapter_admission_quarantined_source.json"
                ),
            ),
        ]
    )


def build_layer3_g0_bundle(repo_root: Path) -> Layer3G0Bundle:
    """Compose the in-memory G0 bundle from current repository state."""

    capability_inventory = build_capability_inventory(repo_root)
    data_asset_inventory = build_data_asset_inventory(repo_root)
    cluster_map_path = repo_root / "architecture/policy_design_case/cluster_ownership_map.toml"
    port_map = build_port_map_from_cluster_map(cluster_map_path)
    touchpoints = build_runtime_quality_touchpoint_inventory(repo_root)
    adapter_paths = load_source_truth_adapter_paths(
        repo_root / "architecture/production_quality/source_truth_lattice.toml"
    )
    triage = _default_triage_records()
    quarantine = [_scenario_family_quarantine()]
    adapter_registry = _adapter_admission_records(touchpoints.registrations)
    data_ports = _data_asset_ports(data_asset_inventory)
    conformance = ConformanceHarnessRecord(
        harness_id="layer3-g0-pre-adapter-conformance",
        existing_source_truth_adapter_path_refs=list(adapter_paths),
        adapter_loss_blocker_refs=["AdapterLossBlocker", "validate_adapter_preservation"],
        status="not_run_pre_adapter",
        negative_fixtures=[
            "tests/unit/runtime/quality/test_source_truth_lattice.py",
            "tests/fixtures/layer3/g0/malformed_adapter_admission_quarantined_source.json",
        ],
    )
    health_ledgers = _health_metric_ledgers()
    import_firewall = build_import_firewall_report(repo_root)
    status_matrix = build_status_composition_matrix()
    empty_ports = [
        EmptyPortMapEntry(
            port_id="INTERVENTION.method_requirements",
            proving_ground_case_id=FIRST_VERTICAL_CORPUS_CASE_ID,
            blocker_cause="Method source adapter is not admitted in G0.",
            binding_constraint_rank="causal_support",
            next_adapter_dependency="foundry_method_candidate_shadow_adapter",
        )
    ]
    adapter_costs = [
        AdapterCostMapEntry(
            source_id="lex_binary_status_candidate",
            port_id="INTERVENTION.requirements",
            near_typed_raw_classification="near_typed",
            existing_contract_refs=["repo://src/polisyos/lex/normpack/legal_authority.py#L303"],
            adapter_effort_tier="medium",
            semantic_loss_risk="binary_status_projection_overclaim",
            sequencing_priority=1,
        )
    ]
    first_case = FirstVerticalCaseRecord(
        case_ref="architecture/policy_design_case/layer3_first_vertical_case.json",
        first_vertical_corpus_case_id=FIRST_VERTICAL_CORPUS_CASE_ID,
        first_vertical_construct_bundle_id=FIRST_VERTICAL_CONSTRUCT_BUNDLE_ID,
        authority_posture="not_attempted_g0_pre_adapter",
    )
    counts = _bundle_counts(
        capability_inventory=capability_inventory,
        data_asset_inventory=data_asset_inventory,
        port_map=port_map,
        touchpoints=touchpoints,
        adapter_paths=adapter_paths,
        adapter_registry=adapter_registry,
        data_ports=data_ports,
        health_ledgers=health_ledgers,
        import_firewall=import_firewall,
        status_matrix=status_matrix,
    )
    manifest = Layer3G0ReadinessManifest(
        closure_artifact_paths=_closure_artifact_paths(),
        counts=counts,
        runtime_builder_hash=_runtime_builder_hash(counts),
    )
    return Layer3G0Bundle(
        capability_inventory=capability_inventory,
        data_asset_inventory=data_asset_inventory,
        triage_registry=triage,
        quarantine_registry=quarantine,
        port_map=port_map,
        runtime_quality_touchpoints=touchpoints,
        adapter_admission_registry=adapter_registry,
        data_asset_ports=data_ports,
        conformance_harness=conformance,
        health_metric_ledgers=health_ledgers,
        import_firewall_lint=import_firewall,
        status_composition_matrix=status_matrix,
        empty_port_map=empty_ports,
        adapter_cost_map=adapter_costs,
        first_vertical_case=first_case,
        readiness_manifest=manifest,
    )


def validate_layer3_g0_bundle(
    repo_root: Path, persisted: Layer3G0Bundle | Mapping[str, Any]
) -> ValidationReport:
    """Validate a persisted/in-memory G0 bundle against runtime builder output."""

    bundle = _bundle_from_payload(persisted)
    runtime_bundle = build_layer3_g0_bundle(repo_root)
    issues: list[ValidationIssue] = []

    runtime_counts = runtime_bundle.readiness_manifest.counts
    persisted_counts = bundle.readiness_manifest.counts
    if runtime_counts != persisted_counts:
        issues.append(
            _issue(
                "layer3_g0_manifest_runtime_drift",
                "$.readiness_manifest.counts",
                "persisted readiness counts must match the runtime builder output",
            )
        )

    issues.extend(
        validate_adapter_admission_registry(
            admission_records=bundle.adapter_admission_registry,
            quarantine_registry=bundle.quarantine_registry,
        ).issues
    )
    issues.extend(validate_data_asset_inventory_payload(bundle.data_asset_inventory).issues)
    issues.extend(
        validate_runtime_quality_touchpoint_inventory(bundle.runtime_quality_touchpoints).issues
    )
    issues.extend(
        validate_port_map(
            bundle.port_map,
            repo_root / "architecture/policy_design_case/cluster_ownership_map.toml",
        ).issues
    )
    if len(bundle.health_metric_ledgers) != 4:
        issues.append(
            _issue(
                "layer3_g0_health_metric_missing",
                "$.health_metric_ledgers",
                "G0 requires four health metric ledgers",
            )
        )
    if bundle.import_firewall_lint.violations:
        issues.append(
            _issue(
                "layer3_g0_pdc_non_waist_import",
                "$.import_firewall_lint.violations",
                "pdc imported a non-waist source package",
            )
        )
    if len(bundle.status_composition_matrix.rules) != 4:
        issues.append(
            _issue(
                "layer3_g0_status_composition_missing",
                "$.status_composition_matrix",
                "G0 requires exactly four composition rules",
            )
        )
    if not any(
        row.target_id == "scenario_family_authority_selector" for row in bundle.quarantine_registry
    ):
        issues.append(
            _issue(
                "layer3_g0_quarantine_missing_required_entry",
                "$.quarantine_registry",
                "scenario_family_authority_selector must be quarantined",
            )
        )

    return _report(issues, summary={**persisted_counts, "status": "fail" if issues else "pass"})


def validate_adapter_admission_registry(
    *,
    admission_records: Sequence[AdapterAdmissionRecord | Mapping[str, Any]],
    quarantine_registry: Sequence[QuarantineRegistryEntry | Mapping[str, Any]],
) -> ValidationReport:
    """Validate adapter admission records against quarantine and G0 maturity rules."""

    records = [AdapterAdmissionRecord.model_validate(record) for record in admission_records]
    quarantines = [QuarantineRegistryEntry.model_validate(entry) for entry in quarantine_registry]
    quarantined_targets = {entry.target_id for entry in quarantines}
    issues: list[ValidationIssue] = []
    for index, record in enumerate(records):
        if record.admitted or record.admission_state == "admitted":
            if quarantined_targets.intersection(record.source_ids):
                issues.append(
                    _issue(
                        "layer3_g0_quarantined_source_admitted",
                        f"$.adapter_admission_registry.records[{index}]",
                        "quarantined sources cannot be admitted",
                    )
                )
            issues.append(
                _issue(
                    "layer3_g0_adapter_maturity_overclaim",
                    f"$.adapter_admission_registry.records[{index}].admitted",
                    "G0 admits zero adapters",
                )
            )
        if record.conformance_status != "pass" and (
            record.maturity in {"predictive", "calibrated"}
            or record.promotion_state == "governed_promoted"
        ):
            issues.append(
                _issue(
                    "layer3_g0_adapter_maturity_overclaim",
                    f"$.adapter_admission_registry.records[{index}].maturity",
                    "adapter maturity cannot exceed conformance evidence",
                )
            )
        if (
            record.source_touchpoint_refs
            and record.admission_state == "admitted"
            and not record.adapter_contract_path_refs
        ):
            issues.append(
                _issue(
                    "layer3_g0_touchpoint_admission_without_contract",
                    f"$.adapter_admission_registry.records[{index}].adapter_contract_path_refs",
                    "admission-allowed touchpoints require an existing source-truth adapter path",
                )
            )
    return _report(
        issues,
        summary={
            "admitted_adapter_count": sum(1 for record in records if record.admitted),
            "adapter_candidate_count": len(records),
        },
    )


def validate_port_map(
    persisted: PortMap | Mapping[str, Any], cluster_map_path: Path
) -> ValidationReport:
    """Validate that a port map is derived from the current cluster map."""

    port_map = PortMap.model_validate(persisted)
    expected = build_port_map_from_cluster_map(cluster_map_path)
    persisted_ids = [port.port_id for port in port_map.ports]
    expected_ids = [port.port_id for port in expected.ports]
    issues: list[ValidationIssue] = []
    if persisted_ids != expected_ids:
        issues.append(
            _issue(
                "layer3_g0_port_map_drift",
                "$.ports",
                "port map must match handshake_graph.ports exactly",
            )
        )
    for index, port in enumerate(port_map.ports):
        if "cluster_ownership_map.toml" not in port.source_line_ref:
            issues.append(
                _issue(
                    "layer3_g0_port_map_drift",
                    f"$.ports[{index}].source_line_ref",
                    "port source refs must point back to cluster_ownership_map.toml",
                )
            )
    return _report(issues, summary={"port_count": len(port_map.ports)})


def validate_capability_inventory_payload(payload: Mapping[str, Any]) -> ValidationReport:
    """Validate portless capability open-question coverage in inventory payloads."""

    inventory = _mapping(payload.get("capability_inventory", payload))
    entries = [_mapping(entry) for entry in _sequence(inventory.get("entries"))]
    open_questions = {
        str(_mapping(row).get("capability_id"))
        for row in _sequence(inventory.get("portless_open_questions"))
    }
    issues: list[ValidationIssue] = []
    for index, entry in enumerate(entries):
        mapped = _sequence(entry.get("mapped_port_ids"))
        capability_id = str(entry.get("capability_id", ""))
        if not mapped and capability_id not in open_questions:
            issues.append(
                _issue(
                    "layer3_g0_portless_capability_missing_open_question",
                    f"$.capability_inventory.entries[{index}]",
                    "capabilities without a current port require governed open-question tracking",
                )
            )
    return _report(
        issues,
        summary={
            "portless_capability_without_open_question_count": len(issues),
        },
    )


def validate_data_asset_inventory_payload(
    payload: DataAssetInventory | Mapping[str, Any],
) -> ValidationReport:
    """Validate asset-level evidence refs and transform classification."""

    raw = (
        payload.model_dump(mode="json")
        if isinstance(payload, DataAssetInventory)
        else dict(payload)
    )
    inventory = _mapping(raw.get("data_asset_inventory", raw))
    data_asset_ports = _sequence(raw.get("data_asset_ports"))
    issues: list[ValidationIssue] = []

    if inventory.get("scan_mode", "manifest_backed_lightweight") != "manifest_backed_lightweight":
        issues.append(
            _issue(
                "layer3_g0_manifest_backed_data_scan_bypassed",
                "$.data_asset_inventory.scan_mode",
                "production data inventory must be manifest-backed and lightweight",
            )
        )
    assets = [_mapping(asset) for asset in _sequence(inventory.get("data_assets"))]
    transforms = [
        _mapping(transform) for transform in _sequence(inventory.get("processing_transforms"))
    ]
    for index, asset in enumerate(assets):
        for field in (
            "lineage_evidence_ref",
            "rights_evidence_ref",
            "freshness_evidence_ref",
            "fitness_evidence_ref",
            "contamination_check_ref",
        ):
            if not asset.get(field):
                issues.append(
                    _issue(
                        "layer3_g0_data_asset_evidence_missing",
                        f"$.data_asset_inventory.data_assets[{index}].{field}",
                        (
                            "data asset rows require lineage, rights, freshness, "
                            "fitness, and contamination refs"
                        ),
                    )
                )
        if asset.get("authority_claim") == "runtime_evidence_authority":
            issues.append(
                _issue(
                    "layer3_g0_manifest_backed_data_scan_bypassed",
                    f"$.data_asset_inventory.data_assets[{index}].authority_claim",
                    "corpus fixtures are semantic expectations, not runtime authority evidence",
                )
            )
    for index, port in enumerate(data_asset_ports):
        for field in (
            "lineage_ref",
            "rights_ref",
            "freshness_ref",
            "fitness_ref",
            "contamination_check_ref",
        ):
            if not _mapping(port).get(field):
                issues.append(
                    _issue(
                        "layer3_g0_data_asset_evidence_missing",
                        f"$.data_asset_ports[{index}].{field}",
                        "data asset ports require all evidence refs",
                    )
                )

    covered_assets = {str(asset.get("path")) for asset in assets}
    covered_transforms = {
        str(script)
        for transform in transforms
        for script in _sequence(transform.get("transform_script_refs"))
    }
    for root_index, root in enumerate(_sequence(inventory.get("required_roots"))):
        root_map = _mapping(root)
        for asset_path in _sequence(root_map.get("discovered_assets")):
            if str(asset_path) not in covered_assets:
                issues.append(
                    _issue(
                        "layer3_g0_data_asset_unclassified",
                        f"$.data_asset_inventory.required_roots[{root_index}].discovered_assets",
                        "discovered data assets must have asset-level inventory entries",
                    )
                )
        for script_path in _sequence(root_map.get("discovered_transforms")):
            if str(script_path) not in covered_transforms:
                issues.append(
                    _issue(
                        "layer3_g0_processing_transform_unclassified",
                        f"$.data_asset_inventory.required_roots[{root_index}].discovered_transforms",
                        "discovered processing transforms must have transform inventory entries",
                    )
                )
    return _report(
        issues,
        summary={
            "data_asset_inventory_unclassified_discovered_count": sum(
                1 for issue in issues if issue.code == "layer3_g0_data_asset_unclassified"
            ),
            "processing_transform_inventory_unclassified_discovered_count": sum(
                1 for issue in issues if issue.code == "layer3_g0_processing_transform_unclassified"
            ),
        },
    )


def validate_runtime_quality_touchpoint_inventory(
    payload: RuntimeQualityTouchpointInventory | Mapping[str, Any],
) -> ValidationReport:
    """Validate runtime/quality touchpoint registration and admission contracts."""

    raw = (
        payload.model_dump(mode="json")
        if isinstance(payload, RuntimeQualityTouchpointInventory)
        else dict(payload)
    )
    discovered = [_mapping(row) for row in _sequence(raw.get("discovered_touchpoints"))]
    registrations = [_mapping(row) for row in _sequence(raw.get("registrations"))]
    if not discovered and registrations:
        discovered = registrations
    registered_ids = {str(row.get("touchpoint_id")) for row in registrations}
    issues: list[ValidationIssue] = []
    for index, touchpoint in enumerate(discovered):
        if str(touchpoint.get("touchpoint_id")) not in registered_ids:
            issues.append(
                    _issue(
                        "layer3_g0_source_touchpoint_registration_missing",
                        f"$.discovered_touchpoints[{index}]",
                        (
                            "every runtime/quality subordinate import requires "
                            "SourceTouchpointRegistration"
                        ),
                    )
                )
    for index, registration in enumerate(registrations):
        if registration.get("admission_allowed") is True and not registration.get(
            "existing_source_truth_adapter_path_ref"
        ):
            issues.append(
                _issue(
                    "layer3_g0_touchpoint_admission_without_contract",
                    f"$.registrations[{index}].existing_source_truth_adapter_path_ref",
                    "admission-allowed touchpoints require existing source-truth adapter paths",
                )
            )
    return _report(
        issues,
        summary={
            "runtime_quality_touchpoint_count": len(discovered),
            "runtime_quality_touchpoints_without_registration": sum(
                1
                for issue in issues
                if issue.code == "layer3_g0_source_touchpoint_registration_missing"
            ),
            "runtime_quality_touchpoint_admission_allowed_without_contract_count": sum(
                1
                for issue in issues
                if issue.code == "layer3_g0_touchpoint_admission_without_contract"
            ),
        },
    )


def load_source_truth_adapter_paths(lattice_path: Path) -> tuple[str, ...]:
    """Load existing source-truth preservation adapter-path IDs."""

    payload = _load_toml(lattice_path)
    return tuple(
        str(row["id"])
        for row in _sequence(payload.get("adapter_paths"))
        if isinstance(row, Mapping) and row.get("id")
    )


def validate_source_truth_lattice_adapter_paths(
    *,
    adapter_paths: Sequence[str],
    baseline_adapter_paths: Sequence[str],
) -> ValidationReport:
    """Validate that G0 did not add preservation adapter paths."""

    issues = []
    if tuple(adapter_paths) != tuple(baseline_adapter_paths):
        issues.append(
            _issue(
                "layer3_g0_source_truth_lattice_mutated_in_g0",
                "$.source_truth_lattice.adapter_paths",
                "G0 must not add source-truth adapter paths",
            )
        )
    return _report(
        issues,
        summary={
            "source_truth_adapter_path_count": len(baseline_adapter_paths),
            "source_truth_lattice_new_adapter_path_count": max(
                0,
                len(adapter_paths) - len(baseline_adapter_paths),
            ),
        },
    )


def validate_status_composition_matrix(
    matrix: StatusCompositionMatrix | Mapping[str, Any],
    *,
    cases: Sequence[Mapping[str, Any]] | None = None,
) -> ValidationReport:
    """Validate G0 status composition rules and optional negative cases."""

    status_matrix = StatusCompositionMatrix.model_validate(matrix)
    issues: list[ValidationIssue] = []
    if tuple(rule.rule_id for rule in status_matrix.rules) != _STATUS_RULE_IDS:
        issues.append(
            _issue(
                "layer3_g0_status_composition_missing",
                "$.status_composition_matrix.rules",
                "G0 requires the exact quarantine/conformance/maturity/promotion rules",
            )
        )
    for index, case in enumerate(cases or []):
        expected = str(case.get("expected_issue_code", "layer3_g0_status_composition_missing"))
        if case.get("quarantine_check") == "blocked" and case.get("admission_state") == "admitted":
            issues.append(_issue(expected, f"$.cases[{index}]", "quarantine dominates admission"))
        elif (
            case.get("promotion_state") == "governed_promoted"
            and case.get("conformance_status") != "pass"
        ):
            issues.append(
                _issue(
                    expected,
                    f"$.cases[{index}]",
                    "promotion cannot occur before conformance and G4",
                )
            )
    return _report(issues, summary={"status_composition_rule_count": len(status_matrix.rules)})


def validate_governance_followups(payload: Mapping[str, Any]) -> ValidationReport:
    """Validate ADR governance follow-ups for import policy and registry crosswalk."""

    issues: list[ValidationIssue] = []
    if payload.get("import_policy_constitution_conflict_recorded") is not True:
        issues.append(
            _issue(
                "layer3_g0_import_policy_constitution_conflict_unrecorded",
                "$.import_policy_constitution_conflict_recorded",
                "ADR-0175 must record the policy.toml vs constitution conflict",
            )
        )
    if payload.get("policy_toml_pdc_allowlist_narrowing_followup_recorded") is not True:
        issues.append(
            _issue(
                "layer3_g0_import_policy_constitution_conflict_unrecorded",
                "$.policy_toml_pdc_allowlist_narrowing_followup_recorded",
                "ADR-0175 must name a follow-up ADR to narrow policy.toml pdc imports",
            )
        )
    if payload.get("registry_crosswalk_clarification_recorded") is not True:
        issues.append(
            _issue(
                "layer3_g0_registry_conflation_unrecorded",
                "$.registry_crosswalk_clarification_recorded",
                "ADR-0175 must distinguish preservation registry from admission registry",
            )
        )
    return _report(issues)


def validate_layer3_g0_adr(payload: Mapping[str, Any]) -> ValidationReport:
    """Validate ADR-0175 status, human acceptance, and open-question tracking."""

    adr = _mapping(payload.get("adr", payload))
    issues: list[ValidationIssue] = []
    if adr.get("status") != "Accepted":
        issues.append(
            _issue("layer3_g0_adr_not_accepted", "$.adr.status", "ADR-0175 must be Accepted")
        )
    if adr.get("status") == "Accepted" and not (
        adr.get("accepted_by") and adr.get("accepted_at") and adr.get("acceptance_ref")
    ):
        issues.append(
            _issue(
                "layer3_g0_adr_human_acceptance_missing",
                "$.adr.acceptance_ref",
                "Accepted ADR-0175 requires human-principal acceptance fields",
            )
        )
    if adr.get("open_questions_mode") != "tracked_empirically_open":
        issues.append(
            _issue(
                "layer3_g0_adr_open_questions_missing",
                "$.adr.open_questions_mode",
                "constitution open questions must remain tracked_empirically_open",
            )
        )
    issues.extend(validate_governance_followups(adr).issues)
    return _report(issues)


def validate_first_vertical_case_record(
    payload: FirstVerticalCaseRecord | Mapping[str, Any],
) -> ValidationReport:
    """Validate first vertical corpus and construct identifiers."""

    record = FirstVerticalCaseRecord.model_validate(payload)
    issues: list[ValidationIssue] = []
    if (
        record.first_vertical_corpus_case_id != FIRST_VERTICAL_CORPUS_CASE_ID
        or record.first_vertical_construct_bundle_id != FIRST_VERTICAL_CONSTRUCT_BUNDLE_ID
        or record.first_vertical_corpus_case_id == record.first_vertical_construct_bundle_id
    ):
        issues.append(
            _issue(
                "layer3_g0_first_case_id_mismatch",
                "$.first_vertical_case",
                "G0 must keep the first corpus case and construct bundle IDs distinct",
            )
        )
    return _report(issues)


def _default_triage_records() -> list[CapabilityTriageRecord]:
    authority = AuthorityBoundary(
        authoritative_for=["layer3_g0_pre_adapter_triage"],
        may_not_use_for=["adapter_admission", "publication_authority"],
        source_authority="deterministic_producer",
        posture="shadow",
        rule_version_refs=[LAYER3_G0_RULE_VERSION],
    )
    return [
        CapabilityTriageRecord(
            capability_id="scenario_family_authority_selector",
            disposition="quarantine",
            rationale=(
                "Scenario-family selectors are projection-only and cannot be "
                "adapter authority."
            ),
            evidence_refs=[
                "repo://src/polisyos/runtime/quality/scenario_evidence_contract.py#L349",
                "repo://architecture/shims.toml#L176",
            ],
            missing_capability_labels=["verification_missing"],
            quarantine_ref="quarantine://layer3-g0/scenario-family-authority-selector",
            adapter_admissibility="blocked",
            authority_boundary=authority,
        ),
        CapabilityTriageRecord(
            capability_id="lex_binary_status_candidate",
            disposition="wrap_then_strangle",
            rationale=(
                "Only the simple_v1 binary projection path is triage-required; "
                "graded Lex authority remains the stronger seam."
            ),
            evidence_refs=[
                "repo://src/polisyos/lex/legal_evaluation/backends/simple_v1.py#L15",
                "repo://src/polisyos/lex/normpack/legal_authority.py#L303",
            ],
            missing_capability_labels=["verification_missing", "semantic_test_missing"],
            quarantine_ref=None,
            adapter_admissibility="blocked_until_retriage",
            authority_boundary=authority,
        ),
    ]


def _scenario_family_quarantine() -> QuarantineRegistryEntry:
    return QuarantineRegistryEntry(
        target_id="scenario_family_authority_selector",
        target_kind="source_touchpoint",
        reason="Scenario-family projection is not source authority.",
        pattern_ids=["P05", "P06", "P15"],
        blocker_codes=["layer3_g0_quarantined_source_admitted"],
        enforcement_surface="adapter_admission_registry",
        release_condition="source-truth adapter path and human retriage required",
    )


def _adapter_admission_records(
    registrations: Sequence[SourceTouchpointRegistration],
) -> list[AdapterAdmissionRecord]:
    records = [
        AdapterAdmissionRecord(
            adapter_id=f"layer3-g0-shadow-{_slug(row.touchpoint_id)}",
            source_ids=[row.touchpoint_id],
            port_ids=["DESIGNER_ITSELF.cluster_evidence"],
            maturity="fail_closed",
            promotion_state="shadow",
            conformance_status="not_run_pre_adapter",
            quarantine_check=row.quarantine_check_result,
            admission_state="candidate_shadow_only",
            admitted=False,
            adapter_contract_path_refs=[],
            source_touchpoint_refs=[row.touchpoint_id],
        )
        for row in registrations
    ]
    records.append(
        AdapterAdmissionRecord(
            adapter_id="scenario-family-authority-selector-blocked",
            source_ids=["scenario_family_authority_selector"],
            port_ids=["DESIGNER_ITSELF.cluster_evidence"],
            maturity="fail_closed",
            promotion_state="promotion_blocked",
            conformance_status="blocked",
            quarantine_check="blocked",
            admission_state="blocked",
            admitted=False,
            adapter_contract_path_refs=[],
            source_touchpoint_refs=[],
        )
    )
    return records


def _data_asset_ports(inventory: DataAssetInventory) -> list[DataAssetPort]:
    ports: list[DataAssetPort] = []
    for root in inventory.required_roots:
        matching = next(
            (asset for asset in inventory.data_assets if asset.owning_root == root.path),
            None,
        )
        if matching is None:
            continue
        ports.append(
            DataAssetPort(
                asset_id=matching.asset_id,
                data_kind=matching.data_kind,
                path=matching.path,
                lineage_ref=matching.lineage_evidence_ref,
                rights_ref=matching.rights_evidence_ref,
                freshness_ref=matching.freshness_evidence_ref,
                fitness_ref=matching.fitness_evidence_ref,
                contamination_check_ref=matching.contamination_check_ref,
                port_ids=["DESIGNER_ITSELF.cluster_evidence"],
            )
        )
    return ports


def _health_metric_ledgers() -> list[HealthMetricLedger]:
    return [
        HealthMetricLedger(
            metric_id="envelope-expansion-rate",
            owner="team-runtime-quality",
            freeze_value={"g0_admitted_adapter_count": 0},
            trend_vocabulary=["expanding", "flat", "shrinking"],
            per_slice_delta_rule="Later slices may change only after admitted adapter evidence.",
            next_update_rule="Recompute when a G1+ adapter slice writes governed artifacts.",
        ),
        HealthMetricLedger(
            metric_id="adapter-semantic-loss",
            owner="team-runtime-quality",
            freeze_value={"semantic_loss_events": 0},
            trend_vocabulary=["clean", "lossy"],
            per_slice_delta_rule="Any AdapterLossBlocker event increments lossy evidence.",
            next_update_rule="Recompute from conformance harness outputs.",
        ),
        HealthMetricLedger(
            metric_id="governance-throughput",
            owner="principal-governance",
            freeze_value={"accepted_adr_count": 0, "open_human_gate_count": 1},
            trend_vocabulary=["flowing", "stalled"],
            per_slice_delta_rule=(
                "Human acceptance gates move throughput only with acceptance refs."
            ),
            next_update_rule="Recompute at ADR-0175 acceptance.",
        ),
        HealthMetricLedger(
            metric_id="demand-pull-vs-abstention",
            owner="team-runtime-quality",
            freeze_value={"grounded_conversion_count": 0},
            trend_vocabulary=["responding", "abstention_inertia"],
            per_slice_delta_rule=(
                "Demand pull cannot count until a grounded adapter admits evidence."
            ),
            next_update_rule="Recompute from universal corpus G0 route.",
        ),
    ]


def _bundle_counts(
    *,
    capability_inventory: CapabilityDataInventory,
    data_asset_inventory: DataAssetInventory,
    port_map: PortMap,
    touchpoints: RuntimeQualityTouchpointInventory,
    adapter_paths: Sequence[str],
    adapter_registry: Sequence[AdapterAdmissionRecord],
    data_ports: Sequence[DataAssetPort],
    health_ledgers: Sequence[HealthMetricLedger],
    import_firewall: ImportFirewallReport,
    status_matrix: StatusCompositionMatrix,
) -> dict[str, Any]:
    counts = {
        **capability_inventory.summary,
        **data_asset_inventory.summary,
        **port_map.summary,
        **touchpoints.summary,
        "data_asset_port_count": len(data_ports),
        "source_truth_adapter_path_count": len(adapter_paths),
        "source_truth_lattice_new_adapter_path_count": 0,
        "admitted_adapter_count": sum(1 for record in adapter_registry if record.admitted),
        "adapter_candidate_count": len(adapter_registry),
        "quarantine_registry_min_count": 1,
        "health_metric_ledger_count": len(health_ledgers),
        "closure_artifact_count": 12,
        "readiness_manifest_count": 1,
        "import_firewall_artifact_count": 1,
        "status_composition_rule_count": len(status_matrix.rules),
        "pdc_non_waist_import_count": len(import_firewall.violations),
        "grounded_conversion_count": 0,
    }
    counts["runtime_quality_touchpoint_count"] = touchpoints.summary.get(
        "runtime_quality_touchpoint_count",
        0,
    )
    return counts


def _closure_artifact_paths() -> list[str]:
    return [
        "architecture/policy_design_case/layer3_g0_capability_data_inventory.json",
        "architecture/policy_design_case/layer3_g0_triage_registry.json",
        "architecture/policy_design_case/layer3_g0_port_map.json",
        "architecture/policy_design_case/layer3_adapter_admission_registry.json",
        "architecture/policy_design_case/layer3_data_asset_ports.json",
        "architecture/policy_design_case/layer3_conformance_harness.json",
        "architecture/policy_design_case/layer3_health_metric_ledgers.toml",
        "architecture/policy_design_case/layer3_import_firewall_lint.json",
        "architecture/policy_design_case/layer3_empty_port_map.json",
        "architecture/policy_design_case/layer3_adapter_cost_map.json",
        "architecture/policy_design_case/layer3_first_vertical_case.json",
        "docs/adr/0175-layer3-grounding-subordination-discipline.md",
    ]


def _bundle_from_payload(payload: Layer3G0Bundle | Mapping[str, Any]) -> Layer3G0Bundle:
    if isinstance(payload, Layer3G0Bundle):
        return payload
    return Layer3G0Bundle.model_validate(payload)


def _data_asset_entry(
    *,
    asset_id: str,
    path: str,
    owning_root: str,
    evidence_path: Path,
    repo_root: Path,
    size_bytes: int | None = None,
) -> DataAssetInventoryEntry:
    evidence_ref = _repo_ref(evidence_path, repo_root)
    return DataAssetInventoryEntry(
        asset_id=asset_id,
        data_kind="data_asset",
        path=path,
        owning_root=owning_root,
        size_bytes=size_bytes,
        owner_evidence_ref=evidence_ref,
        lineage_evidence_ref=evidence_ref,
        rights_evidence_ref=evidence_ref,
        freshness_evidence_ref=evidence_ref,
        fitness_evidence_ref=evidence_ref,
        contamination_check_ref=evidence_ref,
    )


def _issue(code: str, path: str, message: str) -> ValidationIssue:
    return ValidationIssue(code=code, path=path, message=message)


def _report(
    issues: Sequence[ValidationIssue],
    *,
    summary: Mapping[str, Any] | None = None,
) -> ValidationReport:
    return ValidationReport(
        status="fail" if issues else "pass",
        issues=list(issues),
        summary=dict(summary or {}),
    )


def _repo_ref(path: Path, repo_root: Path) -> str:
    return f"repo://{_repo_path(path, repo_root)}"


def _repo_path(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _repo_root_from_artifact(path: Path) -> Path:
    parts = path.resolve().parts
    if "policy-engine" in parts:
        index = parts.index("policy-engine")
        return Path(*parts[: index + 1])
    return path.parent


def _line_ref(path: Path, needle: str) -> str:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return f"repo://{path.as_posix()}#L1"
    for index, line in enumerate(lines, start=1):
        if needle in line:
            return f"repo://{path.as_posix()}#L{index}"
    return f"repo://{path.as_posix()}#L1"


def _line_count(path: Path) -> int:
    try:
        return len(path.read_text(encoding="utf-8").splitlines())
    except UnicodeDecodeError:
        return 0


def _file_count(path: Path) -> int:
    return sum(1 for child in path.rglob("*") if child.is_file()) if path.exists() else 0


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_toml(path: Path) -> dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: object) -> Sequence[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return value
    return []


def _int_or_none(value: object) -> int | None:
    return value if isinstance(value, int) else None


def _slug(value: str) -> str:
    return "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")


def _package_kind(root: str) -> str:
    if root == "pdc":
        return "narrow_waist"
    if root == "runtime":
        return "runtime_quality_surface"
    if root in _RUNTIME_QUALITY_SOURCE_ROOTS:
        return "source_package"
    return "support_package"


def _imports_for_package(package_path: Path) -> list[str]:
    roots: set[str] = set()
    for path in package_path.glob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            for import_root, _source_module in _polisyos_import_refs(node):
                roots.add(import_root)
    return sorted(roots)


def _polisyos_import_refs(node: ast.AST) -> list[tuple[str, str]]:
    refs: list[tuple[str, str]] = []
    if (
        isinstance(node, ast.ImportFrom)
        and node.level == 0
        and node.module
        and (node.module == "polisyos" or node.module.startswith("polisyos."))
    ):
        parts = node.module.split(".")
        if len(parts) >= 2:
            refs.append((parts[1], node.module))
    if isinstance(node, ast.Import):
        for alias in node.names:
            if alias.name == "polisyos" or alias.name.startswith("polisyos."):
                parts = alias.name.split(".")
                if len(parts) >= 2:
                    refs.append((parts[1], alias.name))
    return refs


def _immediate_polisyos_roots(repo_root: Path) -> list[str]:
    src_root = repo_root / "src/polisyos"
    return sorted(
        path.name for path in src_root.iterdir() if path.is_dir() and path.name != "__pycache__"
    )


def _universal_corpus_fixture_count(repo_root: Path) -> int:
    manifest = _load_json(repo_root / "tests/fixtures/universal-corpus/manifest.json")
    fixtures = manifest.get("fixtures", [])
    return len(fixtures) if isinstance(fixtures, Sequence) else 0


def _runtime_builder_hash(counts: Mapping[str, Any]) -> str:
    canonical = json.dumps(counts, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def _bounded_id(prefix: str, value: str, *, max_length: int = 220) -> str:
    slug = f"{prefix}-{_slug(value)}"
    if len(slug) <= max_length:
        return slug
    suffix = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    keep = max_length - len(suffix) - 1
    return f"{slug[:keep].rstrip('-')}-{suffix}"

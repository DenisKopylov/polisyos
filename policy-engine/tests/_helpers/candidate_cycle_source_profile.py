"""Portable owner-built fixtures for candidate cycle source-profile tests.

Every source artifact is created below the caller's temporary root by the same
owner APIs used by the runtime. The synthetic academic claim is explicitly
fixture-scoped; this fixture does not assert external authenticity, law, or
currentness.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb
import pytest

from polisyos.core.artifacts import ArtifactRef, FileSystemCAS
from polisyos.core.security import (
    AccessScope,
    reset_current_access_scope,
    set_current_access_scope,
    tenant_scope,
)
from polisyos.data_forge.domains.academic.batch.admitted_claim_adjudications import (
    load_verified_claim_adjudication_rows,
)
from polisyos.data_forge.domains.academic.batch.article_extractor import _to_work_record
from polisyos.data_forge.domains.academic.batch.claim_adjudication_verifier import (
    selected_artifact_ref_for_input,
)
from polisyos.data_forge.domains.academic.batch.claim_adjudicator import (
    materialize_claim_adjudication_result,
    produce_claim_adjudication_input,
)
from polisyos.data_forge.domains.academic.batch.config import AcademicBatchConfig
from polisyos.data_forge.domains.academic.batch.graph_builder import (
    build_graph as build_skg_graph,
)
from polisyos.data_forge.domains.academic.knowledge.types import WorkRecord
from polisyos.data_forge.read_api import academic
from polisyos.ir.analytics.literature import (
    ArticleExtractionResult,
    CausalClaim,
    CausalDirection,
    ClaimExplicitness,
    ClaimType,
    DesignFamily,
    EvidenceSpan,
)
from polisyos.runtime.quality.cycle_substrate import (
    CANDIDATE_CYCLE_SOURCE_PROFILE_ID,
    CYCLE_SUBSTRATE_CONTEXT_JOB_V5_SCHEMA,
    CandidateCycleSubstrateSourceProfile,
    CandidateCycleSubstrateSourceProfileSelection,
    CycleSubstrateContext,
    CycleSubstrateContextArtifactOwner,
    CycleSubstrateContextJobArtifactV5,
    build_candidate_cycle_substrate_context,
    build_cycle_substrate_context,
    cycle_job_design_problem_ref,
)
from polisyos.runtime.quality.design_problem import (
    DESIGN_PROBLEM_V3_SCHEMA_VERSION,
    DesignProblem,
)
from polisyos.runtime.quality.intervention_substrate import default_l6_bundle_paths
from polisyos.runtime.quality.substrate_registry import (
    DEFAULT_L2_SCHOLAR_KG_PATH,
    DEFAULT_L3_LEX_KG_PATH,
    CatalogServingSourcePaths,
    CatalogServingSourceSelection,
    SubstrateCoverage,
    SubstrateLayer,
    SubstrateRegistration,
    SubstrateRegistry,
    SubstrateSchemaRegime,
    SubstrateTrustTier,
    build_substrate_registry,
    build_substrate_registry_entry,
    resolve_catalog_serving_source,
)
from polisyos.runtime.quality.world_model_record import WorldModelRecord
from polisyos.scientist.methods.autotune import ChampionRegistry

_PROFILE_SELECTION_KEY = "cycle_substrate_source_profile"
_REQUIRED_N5_HINTS: dict[str, Any] = {
    "joint_simulation_resource": "ncm_parallel_worlds",
    "joint_simulation_budget_ref": "budget://controlled-refusal-probe",
    "joint_simulation_horizon": {"start": 0, "end": 0, "step": 1},
}


@dataclass(frozen=True)
class CandidateCycleSubstrateOwnerFixture:
    """One portable, owner-built source-profile and V5 handoff fixture."""

    root: Path
    problem: DesignProblem
    substrate_registry: SubstrateRegistry
    world_model_record: WorldModelRecord
    source_profile: CandidateCycleSubstrateSourceProfile
    context: CycleSubstrateContext
    artifact_store: FileSystemCAS
    context_job_ref: ArtifactRef
    resolved_context_job: CycleSubstrateContextJobArtifactV5


@dataclass(frozen=True)
class CandidateCycleSubstrateRouteInputs:
    """Portable controlled inputs for a normal selected-profile runtime route."""

    root: Path
    problem: DesignProblem
    substrate_registry: SubstrateRegistry
    selected_registry_entry_hashes: tuple[str, ...]
    world_model_record: WorldModelRecord
    seed_context: CycleSubstrateContext


@dataclass
class _FixtureControlJob:
    job_id: str
    run_id: str
    submitted_by: str = "candidate-source-profile-fixture"
    state: str = "running"
    lease_owner: str = "candidate-source-profile-worker"
    attempt: int = 1


class _FixtureCurrentJobOwner:
    def __init__(self, job_id: str, run_id: str) -> None:
        self._record = _FixtureControlJob(job_id=job_id, run_id=run_id)

    def current_execution_job_record(self) -> _FixtureControlJob:
        return self._record


@contextmanager
def _authenticated_fixture_scope(*, tenant_id: str, cell_id: str):
    access_scope = AccessScope.for_service(
        tenant_id=tenant_id,
        cell_id=cell_id,
        spiffe_id="spiffe://tests/policyos/candidate-source-profile-fixture",
    )
    token = set_current_access_scope(access_scope)
    try:
        with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
            yield
    finally:
        reset_current_access_scope(token)


def _problem(
    *,
    runtime_hints: Mapping[str, Any] | None,
    outcome_variable: str = "education.learning_outcomes",
) -> DesignProblem:
    hints = dict(runtime_hints or {})
    hints.update(_REQUIRED_N5_HINTS)
    hints[_PROFILE_SELECTION_KEY] = CandidateCycleSubstrateSourceProfileSelection(
        profile_id=CANDIDATE_CYCLE_SOURCE_PROFILE_ID,
        authority_purpose="cycle_input_candidate_only",
    ).model_dump(mode="json")
    return DesignProblem.model_validate(
        {
            "schema_version": DESIGN_PROBLEM_V3_SCHEMA_VERSION,
            "design_problem_id": "controlled_candidate_source_profile",
            "problem_statement": "Exercise candidate-only source binding in a controlled fixture.",
            "domain": "education",
            "nl_provenance": {
                "raw_request": "Controlled synthetic candidate source-profile fixture.",
                "source_surface": "runtime.control.nl_request",
            },
            "authority_profile": {
                "requester_authority": "research",
                "requested_authority_level": "research",
                "mandate": "Candidate-only engineering fixture; no source authority claimed.",
            },
            "jurisdiction_time": {
                "region": "UA",
                "valid_time": "2025",
                "as_of": "2025-12-31",
                "policy_time": "2025",
                "data_time": "2024/2025",
            },
            "objectives": [
                {
                    "objective_id": "improve_learning",
                    "description": "Exercise a candidate-only outcome path.",
                    "metric_id": outcome_variable.rsplit(".", 1)[-1],
                }
            ],
            "stakeholders": [{"stakeholder_id": "students", "name": "Students"}],
            "outcome_of_interest": {
                "target_variable": outcome_variable,
                "metric_id": outcome_variable.rsplit(".", 1)[-1],
                "estimand": f"P({outcome_variable} | do(education.teaching_method))",
                "direction": "maximize",
            },
            "candidate_lever_space": {
                "allowed_operator_kinds": ["teaching_method"],
                "candidate_levers": [
                    {
                        "lever_id": "teaching_method",
                        "operator_kind": "teaching_method",
                        "instrument": "education.teaching_method",
                        "target_slot": "education.teaching_method",
                    }
                ],
            },
            "evidence_acquisition_needs": {"needs": []},
            "runtime_hints": hints,
        }
    )


def _fixture_article() -> ArticleExtractionResult:
    return ArticleExtractionResult(
        openalex_id="W-CANDIDATE-SOURCE-PROFILE",
        title="Controlled synthetic causal candidate",
        methodology="synthetic test-only evidence",
        causal_claims=[
            CausalClaim(
                claim_id="candidate-source-profile-causal-claim",
                source_basis="fulltext",
                claim_extraction_confidence=0.9,
                cause_variable="education.teaching_method",
                effect_variable="education.learning_outcomes",
                direction=CausalDirection.NEGATIVE,
                claim_text=(
                    "Synthetic fixture claim: a teaching-method intervention changes learning."
                ),
                claim_type=ClaimType.CAUSAL_ASSERTION,
                claim_explicitness=ClaimExplicitness.EXPLICIT,
                design_family_hint=DesignFamily.RCT,
                supporting_spans=[
                    EvidenceSpan(text="Controlled synthetic fixture; not external evidence.")
                ],
                method_spans=[EvidenceSpan(text="Synthetic fixture method description.")],
            )
        ],
        extraction_model="controlled-fixture-v1",
        extraction_timestamp="2026-10-17T00:00:00+00:00",
        extraction_confidence=0.9,
    )


def _verified_synthetic_claim_rows(root: Path) -> tuple[WorkRecord, tuple[object, ...]]:
    from tests._helpers.academic_claim_evidence import (
        evidence_fixture,
        persist_batch,
    )

    config = AcademicBatchConfig(snapshot_root=root / "fixture-work" / "academic")
    article = _fixture_article()
    config.article_extraction_results_path.parent.mkdir(parents=True, exist_ok=True)
    config.article_extraction_results_path.write_text(
        article.model_dump_json() + "\n",
        encoding="utf-8",
    )
    store = FileSystemCAS(config.claim_adjudication_cas_root)
    raw_ref = produce_claim_adjudication_input(config, store=store)
    champion_registry = ChampionRegistry(
        root=config.claim_adjudication_registry_root,
        store=store,
    )
    evidence = evidence_fixture(
        store,
        champion_registry,
        config.claim_adjudication_registry_root,
        raw_ref,
        positive=True,
    )
    result_ref = persist_batch(evidence)
    selected_inputs = {
        edge.role: selected_artifact_ref_for_input(store, edge)
        for edge in store.get_manifest(result_ref).inputs
    }
    expected_roles = {
        "raw_input",
        "candidate",
        "evaluation",
        "evaluation_receipt",
        "execution_receipt",
        "benchmark_suite",
    }
    if set(selected_inputs) != expected_roles:
        raise ValueError("candidate_source_profile_adjudication_input_roles_invalid")
    if (
        selected_inputs["benchmark_suite"] != evidence.suite_ref
        or selected_inputs["candidate"] != evidence.candidate_ref
        or selected_inputs["evaluation"] != evidence.evaluation_ref
    ):
        raise ValueError("candidate_source_profile_adjudication_selected_input_mismatch")
    materialize_claim_adjudication_result(
        config,
        result_ref,
        store=store,
        verifier=evidence.verifier,
    )
    admitted_rows = load_verified_claim_adjudication_rows(
        config,
        verifier=evidence.verifier,
    )
    work_record = _to_work_record(
        result=article,
        raw_work={},
        topic_ids=[],
        topic_display_names=[],
        run_id="candidate-source-profile-fixture",
        pass_name="fulltext",  # noqa: S106 - pipeline stage name, not a credential.
    )
    metadata = dict(work_record.metadata)
    metadata.update(
        {
            "synthetic": True,
            "fixture_scope": "candidate_source_profile_controlled_synthetic_only",
        }
    )
    return work_record.model_copy(update={"metadata": metadata}), admitted_rows


def _build_l1_catalog(path: Path) -> None:
    from polisyos.data_forge.domains.catalog.batch.core_sources.schema import (
        create_alignment_review_basis_table,
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(path)) as connection:
        connection.execute(
            """
            CREATE TABLE ds_variable_alignments (
                dataset_id VARCHAR NOT NULL,
                raw_variable VARCHAR NOT NULL,
                canonical_var VARCHAR NOT NULL,
                method VARCHAR NOT NULL,
                confidence FLOAT NOT NULL,
                evidence VARCHAR NOT NULL,
                is_proxy BOOLEAN DEFAULT FALSE,
                proxy_penalty FLOAT DEFAULT 0.0,
                PRIMARY KEY (dataset_id, raw_variable, canonical_var)
            )
            """
        )
        create_alignment_review_basis_table(connection)


def _build_l3_fixture(path: Path) -> None:
    from polisyos.data_forge.domains.legal.batch.graph_builder import build_graph

    spo_results_dir = path.parent / "legal-fixture" / "spo"
    provisions_dir = path.parent / "legal-fixture" / "provisions"
    spo_results_dir.mkdir(parents=True, exist_ok=True)
    provisions_dir.mkdir(parents=True, exist_ok=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    build_graph(
        spo_results_dir=spo_results_dir,
        provisions_dir=provisions_dir,
        references_dir=None,
        domains_dir=None,
        doc_metadata={},
        db_path=path,
    )


def _build_source_files(
    root: Path, *, include_owner_slot_manifest: bool = False
) -> tuple[Path, str]:
    from polisyos.runtime.quality.credal_reference import (
        DEFAULT_DATA_FORGE_CATALOG_PATH,
    )

    skg_path = root / DEFAULT_L2_SCHOLAR_KG_PATH
    skg_path.parent.mkdir(parents=True, exist_ok=True)
    work_record, admitted_rows = _verified_synthetic_claim_rows(root)
    build_skg_graph(
        records=(work_record,),
        db_path=skg_path,
        admitted_claim_adjudications=admitted_rows,
    )
    query = academic.SKGQuery(db_path=skg_path, index_dir=skg_path.parent / "index")
    try:
        version_id = query.latest_skg_version_id()
    finally:
        query.close()
    if version_id is None:
        raise ValueError("candidate_source_profile_skg_version_missing")

    catalog_path = root / DEFAULT_DATA_FORGE_CATALOG_PATH
    _build_l1_catalog(catalog_path)
    _build_l3_fixture(root / DEFAULT_L3_LEX_KG_PATH)
    l6_paths = default_l6_bundle_paths(root)
    for name in (
        "intervention_knob_dictionary",
        "lex_intervention_map",
        "observation_to_contract_manifest",
    ):
        path = l6_paths[name]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n", encoding="utf-8")
    if include_owner_slot_manifest:
        # Declare only slots already used by the tracked mechanism owner.
        # This is structural candidate input, not a lever, law or permission.
        code_root = Path(__file__).resolve().parents[2]
        owner_path = default_l6_bundle_paths(code_root)["owner_authority_bindings"]
        owner = json.loads(owner_path.read_text(encoding="utf-8"))
        mechanisms = owner["world_mechanism_manifest"]["mechanisms"]
        slots = sorted(
            {
                slot
                for mechanism in mechanisms.values()
                for role in ("reads_slots", "writes_slots")
                for slot in mechanism[role]
            }
        )
        slot_manifest = {
            "synthetic": True,
            "fixture_scope": "candidate_source_owner_slots_only",
            "families": {"tracked_owner_mechanisms": {"slots": slots}},
        }
        path = l6_paths["slot_family_manifest"]
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(slot_manifest, sort_keys=True) + "\n")
    return skg_path, str(version_id)


def _build_registry(skg_path: Path, *, root: Path, version_id: str) -> SubstrateRegistry:
    relative_source = skg_path.resolve().relative_to(root.resolve()).as_posix()
    source_ref = f"repo://{relative_source}"
    registration = SubstrateRegistration(
        source_id="controlled_synthetic_academic_skg",
        family_id="l2_scholar_kg_causal_priors_transport",
        layer=SubstrateLayer.L2,
        coverage=SubstrateCoverage(
            coverage_score=0.0,
            coverage_kind="controlled_synthetic_fixture",
            coverage_rule_ref="fixture://candidate_source_profile/coverage_not_established",
        ),
        trust_tier=SubstrateTrustTier(
            tier="controlled_synthetic_only",
            trust_cap=0.0,
            trust_multiplier=0.0,
            authority_ref="fixture://candidate_source_profile/not_authority",
        ),
        identification_mode="not_established",
        schema_regime=SubstrateSchemaRegime(
            schema_regime_id="controlled_synthetic_not_established",
            authority_ref="fixture://candidate_source_profile/not_authority",
        ),
        data_version=version_id,
        snapshot_id=f"controlled-synthetic-skg-v{version_id}",
        source_snapshot_id=f"controlled-synthetic-skg-v{version_id}",
        provenance_refs=(source_ref,),
        authority_refs=("fixture://candidate_source_profile/not_authority",),
    )
    return build_substrate_registry(
        (build_substrate_registry_entry(registration),),
        producer_ref="tests._helpers.candidate_cycle_source_profile._build_registry",
        source_catalog_refs=(
            source_ref,
            "fixture://candidate_source_profile/controlled_synthetic_only",
        ),
    )


def build_candidate_cycle_substrate_route_inputs(
    tmp_path: Path,
    *,
    runtime_hints: Mapping[str, Any] | None = None,
    outcome_variable: str = "education.learning_outcomes",
    include_owner_slot_manifest: bool = False,
) -> CandidateCycleSubstrateRouteInputs:
    """Build only selected-profile source inputs beneath a caller-owned temp root.

    This fixture does not create a context-job artifact. The normal recursive
    runtime route owns source-profile persistence and fresh resolution.

    Args:
        tmp_path: Pytest-owned root for all controlled source files.
        runtime_hints: Additional problem hints; the candidate-only profile
            selector and N5 resource, budget and horizon bindings are retained.
        include_owner_slot_manifest: Declare the tracked mechanism owner's complete
            read/write slot set for a candidate-action fixture. The default keeps
            the empty source-only L6 input and its real linker refusal.

    Returns:
        Owner-built source data and an unprofiled seed context for the actual
        orchestration route to recompute.
    """

    root = (tmp_path / "policy-engine").resolve()
    root.mkdir(parents=True, exist_ok=False)
    problem = _problem(runtime_hints=runtime_hints, outcome_variable=outcome_variable)
    skg_path, version_id = _build_source_files(
        root, include_owner_slot_manifest=include_owner_slot_manifest
    )
    registry = _build_registry(skg_path, root=root, version_id=version_id)
    selected_entry_hashes = tuple(sorted(entry.entry_content_hash for entry in registry.entries))
    from polisyos.runtime.quality.generation_cycle import (
        _build_boundary_world_model_record,
    )

    slots = tuple(
        dict.fromkeys(
            (
                *(
                    str(lever.target_slot)
                    for lever in problem.candidate_lever_space.candidate_levers
                ),
                problem.outcome_of_interest.target_variable,
            )
        )
    )
    world_model_record = _build_boundary_world_model_record(
        repo_root=root,
        problem=problem,
        outcome=problem.outcome_of_interest.target_variable,
        policy_slot_ids=slots,
        substrate_registry=registry,
        selected_registry_entry_hashes=selected_entry_hashes,
    )
    seed_context = build_cycle_substrate_context(
        design_problem_ref=cycle_job_design_problem_ref(problem),
        domain=problem.domain,
        substrate_registry=registry,
        selected_registry_entry_hashes=selected_entry_hashes,
        world_model_record=world_model_record,
        intervention_substrate=None,
        candidate_levers=(),
        transport_context=None,
        source_pack_content_hash=None,
        substrate_input_content_hash=None,
    )
    return CandidateCycleSubstrateRouteInputs(
        root=root,
        problem=problem,
        substrate_registry=registry,
        selected_registry_entry_hashes=selected_entry_hashes,
        world_model_record=world_model_record,
        seed_context=seed_context,
    )


def build_candidate_cycle_substrate_owner_fixture(
    tmp_path: Path,
    *,
    runtime_hints: Mapping[str, Any] | None = None,
    outcome_variable: str = "education.learning_outcomes",
) -> CandidateCycleSubstrateOwnerFixture:
    """Build owner evidence, a typed profile, and a fresh V5 CAS round-trip.

    Args:
        tmp_path: Pytest-owned temporary root. Every generated source and CAS
            artifact remains below this path.
        runtime_hints: Extra hints to bind before source-profile selection and
            context creation. The supported N5 resource/budget/horizon hints
            are always included.

    Returns:
        A fully owner-built, candidate-only fixture whose academic rows are
        explicitly synthetic and whose L3/L6 limits remain not established.
    """

    inputs = build_candidate_cycle_substrate_route_inputs(
        tmp_path,
        runtime_hints=runtime_hints,
        outcome_variable=outcome_variable,
    )
    root = inputs.root
    problem = inputs.problem
    registry = inputs.substrate_registry
    seed_world_model_record = inputs.world_model_record
    context = build_candidate_cycle_substrate_context(
        root,
        problem=problem,
        world_model_record=seed_world_model_record,
        substrate_registry=registry,
    )
    profile = context.source_profile
    if profile is None:
        raise ValueError("candidate_source_profile_fixture_profile_missing")

    tenant_id = "tenant-candidate-source-profile-fixture"
    cell_id = "cell-candidate-source-profile-fixture"
    job_id = "job-candidate-source-profile-fixture"
    run_id = "run-candidate-source-profile-fixture"
    cas_root = tmp_path / "cycle-context-cas"
    first_store = FileSystemCAS(
        cas_root,
        ownership_enforced=True,
        ownership_requires_scope=True,
    )
    first_owner = CycleSubstrateContextArtifactOwner(
        store=first_store,
        control_store=_FixtureCurrentJobOwner(job_id, run_id),
    )
    with _authenticated_fixture_scope(tenant_id=tenant_id, cell_id=cell_id):
        context_job_ref = first_owner.persist_for_current_job(
            context,
            problem=problem,
            repo_root=root,
        )
    fresh_store = FileSystemCAS(
        cas_root,
        ownership_enforced=True,
        ownership_requires_scope=True,
    )
    fresh_owner = CycleSubstrateContextArtifactOwner(
        store=fresh_store,
        control_store=_FixtureCurrentJobOwner(job_id, run_id),
    )
    with _authenticated_fixture_scope(tenant_id=tenant_id, cell_id=cell_id):
        resolved = fresh_owner.resolve_for_current_job(
            context_job_ref,
            problem=problem,
            repo_root=root,
        )
    if type(resolved) is not CycleSubstrateContextJobArtifactV5:
        raise ValueError("candidate_source_profile_fixture_v5_not_emitted")
    if resolved.schema_version != CYCLE_SUBSTRATE_CONTEXT_JOB_V5_SCHEMA:
        raise ValueError("candidate_source_profile_fixture_v5_schema_mismatch")
    return CandidateCycleSubstrateOwnerFixture(
        root=root,
        problem=problem,
        substrate_registry=registry,
        world_model_record=context.world_model_record,
        source_profile=profile,
        context=resolved.context,
        artifact_store=fresh_store,
        context_job_ref=context_job_ref,
        resolved_context_job=resolved,
    )


def build_candidate_cycle_catalog_serving_source(
    repo_root: Path,
) -> tuple[CatalogServingSourceSelection, CatalogServingSourcePaths]:
    """Build and resolve one owner-built, candidate-only selected Catalog input.

    The graph builder writes the fixed-layout fixture database. The same owner
    artifact is renamed into the typed selector's required filename; no source
    rows, database bytes, or production inputs are copied or rewritten.
    """
    from polisyos.data_forge.read_api import catalog as catalog_api

    root = Path(repo_root).resolve(strict=True)
    snapshot_root = root / "retrieval-catalog"
    graph_root = snapshot_root / "datasets" / "graph"
    graph = catalog_api.build_slice0_fixture_catalog_graph(graph_root)
    graph.close()
    owner_database = graph_root / "catalog.duckdb"
    selected_database = graph_root / "dataset_catalog.duckdb"
    if not owner_database.is_file() or selected_database.exists() or selected_database.is_symlink():
        raise AssertionError("candidate_catalog_owner_output_not_unique")
    owner_database.replace(selected_database)
    selection = CatalogServingSourceSelection(
        snapshot_root=snapshot_root,
        catalog_run_profile="preflight_core",
    )
    source = resolve_catalog_serving_source(
        root,
        selection=selection,
        requested_profile=selection.catalog_run_profile,
    )
    if (
        source.selection_basis != "explicit_path_candidate_only"
        or source.repo_root != root
        or source.snapshot_root != snapshot_root.resolve(strict=True)
        or source.database_path != selected_database.resolve(strict=True)
    ):
        raise AssertionError("candidate_catalog_owner_selection_readback_mismatch")
    return selection, source


def candidate_cycle_catalog_source_readback(database_path: Path) -> dict[str, Any]:
    """Recompute the exact owner version and full K_ref alignment basis of one DB."""
    from polisyos.data_forge.read_api import catalog as catalog_api
    from polisyos.runtime.quality import credal_reference

    path = Path(database_path).resolve(strict=True)
    reader = catalog_api.DatasetRegistry(path)
    with reader._prepare_kref_alignment_read() as prepared:
        row_count, rows_sha256 = credal_reference._profile_data_forge_alignment_rows(
            prepared.iter_rows()
        )
    return {
        "source_database_path": str(path),
        "source_database_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "source_version": credal_reference._data_forge_catalog_version(path),
        "alignment_row_count": row_count,
        "alignment_rows_sha256": rows_sha256,
    }


def candidate_cycle_l6_source_witness(
    *,
    code_root: Path,
    source_owner_root: Path,
    bundle: Any,
) -> dict[str, Any]:
    """Bind real L6 bundle source refs/hashes to their selected owner paths."""
    import json

    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.quality.intervention_substrate import default_l6_bundle_paths

    code = Path(code_root).resolve(strict=True)
    owner = Path(source_owner_root).resolve(strict=True)
    paths = default_l6_bundle_paths(code, source_owner_root=owner)
    expected_refs: dict[str, str] = {}
    expected_hashes: dict[str, str] = {}
    file_sha256: dict[str, str] = {}
    for name, raw_path in paths.items():
        if raw_path.is_symlink():
            raise AssertionError("candidate_l6_source_path_is_symlink:" + name)
        path = raw_path.resolve(strict=False)
        if not path.is_file():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise AssertionError("candidate_l6_source_payload_not_object:" + name)
        ref_root = code if name == "owner_authority_bindings" else owner
        expected_refs[name] = "repo://" + path.relative_to(ref_root).as_posix()
        expected_hashes[name] = gy_content_hash(payload)
        file_sha256[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    if dict(bundle.source_refs) != expected_refs:
        raise AssertionError("candidate_l6_bundle_source_refs_do_not_match_selected_paths")
    if dict(bundle.source_content_hashes) != expected_hashes:
        raise AssertionError("candidate_l6_bundle_content_hashes_do_not_match_selected_bytes")
    return {
        "code_root": str(code),
        "source_owner_root": str(owner),
        "paths": {name: str(path.resolve()) for name, path in paths.items()},
        "file_sha256": file_sha256,
        "bundle_content_hash": bundle.content_hash,
        "source_refs": dict(bundle.source_refs),
        "source_content_hashes": dict(bundle.source_content_hashes),
    }


def install_candidate_cycle_l6_source_root_reader(
    monkeypatch: Any,
    *,
    code_root: Path,
    source_owner_root: Path,
) -> tuple[list[dict[str, Any]], Any, Any]:
    """Route actual candidate readers through the real two-root L6 owner loader.

    The adapter changes only calls that name the selected fixture root without a
    code-root/owner-root pair. It delegates every selected read to the real owner
    loader with the documented code-root plus fixture-owner-root pair, and
    retains returned source refs, content hashes, exact paths, and file hashes.
    """
    from polisyos.runtime.quality import (
        credal_reference,
        design_generation,
        intervention_substrate,
    )

    code = Path(code_root).resolve(strict=True)
    owner = Path(source_owner_root).resolve(strict=True)
    base_loader = intervention_substrate.load_l6_intervention_substrate
    reads: list[dict[str, Any]] = []
    expected: dict[str, dict[str, Any]] = {}

    def selected_loader(repo_root: Path, *, source_owner_root: Path | None = None) -> Any:
        requested_root = Path(repo_root).resolve()
        requested_owner = (
            Path(source_owner_root).resolve() if source_owner_root is not None else None
        )
        selected_pair = (requested_root == owner and requested_owner is None) or (
            requested_root == code and requested_owner == owner
        )
        if not selected_pair:
            return base_loader(repo_root, source_owner_root=source_owner_root)
        bundle = base_loader(code, source_owner_root=owner)
        witness = candidate_cycle_l6_source_witness(
            code_root=code,
            source_owner_root=owner,
            bundle=bundle,
        )
        reads.append(
            {
                "requested_repo_root": str(requested_root),
                "requested_source_owner_root": (
                    str(requested_owner) if requested_owner is not None else None
                ),
                "bundle": witness,
            }
        )
        bound = expected.get("witness")
        if bound is not None and witness != bound:
            raise AssertionError("candidate_l6_actual_reader_source_mismatch")
        return bundle

    patched_modules = (intervention_substrate, credal_reference, design_generation)
    for module in patched_modules:
        monkeypatch.setattr(module, "load_l6_intervention_substrate", selected_loader)

    def bind_expected(bundle: Any) -> dict[str, Any]:
        witness = candidate_cycle_l6_source_witness(
            code_root=code,
            source_owner_root=owner,
            bundle=bundle,
        )
        expected["witness"] = witness
        if any(item["bundle"] != witness for item in reads):
            raise AssertionError("candidate_l6_profile_and_reader_source_mismatch")
        return witness

    def assert_installed() -> None:
        if any(
            getattr(module, "load_l6_intervention_substrate", None) is not selected_loader
            for module in patched_modules
        ):
            raise AssertionError("candidate_l6_actual_reader_adapter_removed")

    return reads, bind_expected, assert_installed


def bind_candidate_cycle_kref_builder_root(
    builder: Callable[..., Any],
    *,
    expected_repo_root: Path,
    observed_repo_roots: list[str] | None = None,
    mismatch_code: str = "candidate_kref_builder_repo_root_mismatch",
) -> Callable[..., Any]:
    """Bind actual K_ref builder calls to the selected candidate fixture root.

    The wrapper checks the actual builder argument immediately before delegation.
    Optional observations are appended only after the root matches.
    """
    selected_root = Path(expected_repo_root).resolve(strict=True)

    def selected_root_builder(
        repo_root: Path | str,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        actual_root = Path(repo_root).resolve(strict=True)
        if actual_root != selected_root:
            raise AssertionError(mismatch_code)
        if observed_repo_roots is not None:
            observed_repo_roots.append(str(actual_root))
        return builder(repo_root, *args, **kwargs)

    return selected_root_builder


def candidate_cycle_kref_source_witness(
    reference: Any,
    *,
    source_root: Path,
    expected_skg_ref: Any,
    catalog_source: CatalogServingSourcePaths,
    expected_catalog_readback: Mapping[str, Any],
    expected_l6_bundle: Any,
    expected_l6_witness: Mapping[str, Any],
    actual_l6_reads: list[dict[str, Any]],
) -> dict[str, Any]:
    """Reconcile the returned K_ref artifact to exact selected owner reads."""
    from polisyos.runtime.quality import credal_reference
    from polisyos.runtime.quality.substrate_registry import DEFAULT_L3_LEX_KG_PATH
    from polisyos.runtime.quality.world_model_record import _parse_skg_snapshot_ref

    root = Path(source_root).resolve(strict=True)
    catalog_profile = credal_reference.credal_reference_data_forge_catalog_source_profile(reference)
    if catalog_profile is None:
        raise AssertionError("candidate_kref_catalog_profile_missing")
    actual_catalog_path = Path(catalog_profile.source_database_path).resolve(strict=True)
    actual_catalog_readback = candidate_cycle_catalog_source_readback(actual_catalog_path)
    if (
        catalog_profile.selection_owner != "catalog_serving_source_paths"
        or catalog_profile.selection_basis != catalog_source.selection_basis
        or catalog_profile.catalog_run_profile != catalog_source.catalog_run_profile
        or Path(catalog_profile.source_repo_root).resolve(strict=True) != root
        or Path(catalog_profile.source_snapshot_root).resolve(strict=True)
        != catalog_source.snapshot_root.resolve(strict=True)
        or actual_catalog_path != catalog_source.database_path.resolve(strict=True)
        or actual_catalog_readback != dict(expected_catalog_readback)
        or catalog_profile.source_version != expected_catalog_readback["source_version"]
        or catalog_profile.alignment_row_count != expected_catalog_readback["alignment_row_count"]
        or catalog_profile.alignment_rows_sha256
        != expected_catalog_readback["alignment_rows_sha256"]
        or reference.component_versions.get("DATA_FORGE_CATALOG_SOURCE_PROFILE")
        != catalog_profile.content_hash
    ):
        raise AssertionError("candidate_kref_catalog_source_readback_mismatch")

    l2_profile = credal_reference.credal_reference_l2_source_profile(reference)
    if (
        l2_profile is None
        or l2_profile.selection_owner != "world_model_record.skg_causal_prior_ref"
        or l2_profile.skg_causal_prior_ref != expected_skg_ref
    ):
        raise AssertionError("candidate_kref_l2_source_profile_mismatch")
    parsed_skg = _parse_skg_snapshot_ref(expected_skg_ref.skg_snapshot_ref)
    l2_path = parsed_skg.db_path.resolve(strict=True)
    l2_sha256 = hashlib.sha256(l2_path.read_bytes()).hexdigest()
    if (
        not l2_path.is_relative_to(root)
        or l2_sha256 != l2_profile.source_snapshot_sha256
        or parsed_skg.version_id != int(expected_skg_ref.skg_version_id)
    ):
        raise AssertionError("candidate_kref_l2_source_bytes_mismatch")

    l3_path = (root / DEFAULT_L3_LEX_KG_PATH).resolve(strict=True)
    if not l3_path.is_relative_to(root):
        raise AssertionError("candidate_kref_l3_source_outside_selected_root")
    with duckdb.connect(str(l3_path), read_only=True) as connection:
        version_row = connection.execute(
            "SELECT MAX(effective_from) FROM lex_amendments"
        ).fetchone()
    l3_version = str(version_row[0] or l3_path.parent.name) if version_row else l3_path.parent.name
    l3_edge_versions = {
        str(edge.provenance["version"])
        for edge in reference.essential_edges.values()
        if edge.provenance.get("owner") == "L3" and edge.provenance.get("version") is not None
    }
    if l3_edge_versions and l3_edge_versions != {l3_version}:
        raise AssertionError("candidate_kref_l3_actual_version_mismatch")

    if not actual_l6_reads:
        raise AssertionError("candidate_kref_actual_l6_reader_not_observed")
    if any(item.get("bundle") != dict(expected_l6_witness) for item in actual_l6_reads):
        raise AssertionError("candidate_kref_actual_l6_source_mismatch")
    l6_edges = tuple(
        edge for edge in reference.essential_edges.values() if edge.modality.startswith("L6_")
    )
    l6_edge_versions_raw = tuple(edge.provenance.get("version") for edge in l6_edges)
    l6_edge_sources = tuple(edge.provenance.get("source") for edge in l6_edges)
    if l6_edges:
        if any(version is None for version in l6_edge_versions_raw):
            raise AssertionError("candidate_kref_l6_edge_version_missing")
        if any(edge.provenance.get("owner") != "L6" for edge in l6_edges):
            raise AssertionError("candidate_kref_l6_edge_owner_missing")
        if any(source not in expected_l6_bundle.source_refs for source in l6_edge_sources):
            raise AssertionError("candidate_kref_l6_edge_source_ref_missing")
        l6_edge_versions = {str(version) for version in l6_edge_versions_raw}
        if l6_edge_versions != {expected_l6_bundle.content_hash}:
            raise AssertionError("candidate_kref_l6_edge_source_profile_mismatch")
        l6_consumption = "projected_from_selected_owner_bundle"
    else:
        observation_routes = expected_l6_bundle.observation_manifest.get("routes", [])
        if (
            expected_l6_bundle.knob_dictionary
            or expected_l6_bundle.lex_intervention_map
            or observation_routes
            or reference.component_versions.get("L6") is not None
        ):
            raise AssertionError("candidate_kref_omitted_nonempty_l6_owner_basis")
        l6_edge_versions = set()
        l6_consumption = "empty_candidate_data_no_kref_l6_projection_not_established"

    return {
        "repo_root": str(root),
        "l1_catalog": {
            "selection_owner": catalog_profile.selection_owner,
            "selection_basis": catalog_profile.selection_basis,
            "catalog_run_profile": catalog_profile.catalog_run_profile,
            "source_repo_root": catalog_profile.source_repo_root,
            "source_snapshot_root": catalog_profile.source_snapshot_root,
            **actual_catalog_readback,
            "profile_content_hash": catalog_profile.content_hash,
        },
        "l2_skg": {
            "selection_owner": l2_profile.selection_owner,
            "skg_causal_prior_ref": l2_profile.skg_causal_prior_ref.model_dump(mode="json"),
            "source_snapshot_ref": l2_profile.source_snapshot_ref,
            "source_snapshot_path": str(l2_path),
            "source_snapshot_sha256": l2_sha256,
            "source_profile_content_hash": l2_profile.content_hash,
        },
        "l3_lex": {
            "source_path": str(l3_path),
            "source_sha256": hashlib.sha256(l3_path.read_bytes()).hexdigest(),
            "source_version": l3_version,
            "kref_component_version": reference.component_versions.get("L3"),
            "kref_edge_versions": sorted(l3_edge_versions),
        },
        "l6_intervention": {
            "profile_bundle_content_hash": expected_l6_bundle.content_hash,
            "profile_source_refs": dict(expected_l6_bundle.source_refs),
            "profile_source_content_hashes": dict(expected_l6_bundle.source_content_hashes),
            "actual_reader_witnesses": actual_l6_reads,
            "kref_component_version": reference.component_versions.get("L6"),
            "kref_edge_count": len(l6_edges),
            "kref_edge_versions": sorted(l6_edge_versions),
            "candidate_input_counts": {
                "knob_dictionary": len(expected_l6_bundle.knob_dictionary),
                "lex_intervention_map": len(expected_l6_bundle.lex_intervention_map),
                "observation_routes": len(
                    expected_l6_bundle.observation_manifest.get("routes", [])
                ),
            },
            "loaded_code_owner_authority": {
                "source_ref": expected_l6_bundle.source_refs.get("owner_authority_bindings"),
                "content_hash": expected_l6_bundle.source_content_hashes.get(
                    "owner_authority_bindings"
                ),
                "manifest_present": bool(expected_l6_bundle.owner_authority_manifest),
                "world_mechanism_manifest_present": bool(
                    expected_l6_bundle.world_mechanism_manifest
                ),
                "lex_authority_manifest_present": bool(expected_l6_bundle.lex_authority_manifest),
            },
            "consumption_status": l6_consumption,
        },
        "kref_component_versions": dict(reference.component_versions),
        "kref_reference_hash": reference.reference_hash,
    }


@contextmanager
def complete_candidate_cycle_catalog_source(
    source_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[CatalogServingSourceSelection, CatalogServingSourcePaths, SubstrateRegistry]]:
    """Publish and readmit complete test-owned input before a candidate profile.

    Existing candidate graph producers own L1/L2/L3 bytes. The existing registry
    fixture supplies its test-owned L5/root/epoch/L6 metadata and the complete
    published Catalog producer owns the selected L1 snapshot. No input becomes
    empirical evidence or policy authority through this composition.
    """
    from polisyos.runtime.quality import substrate_registry as registry_owner
    from tests.unit.runtime.http._published_catalog_fixture import (
        build_published_catalog_fixture,
    )
    from tests.unit.runtime.quality.test_substrate_registry import (
        _write_substrate_catalog_fixture,
    )

    root = Path(source_root).resolve(strict=True)
    if not root.is_dir() or root.is_symlink():
        raise AssertionError("complete_candidate_source_root_invalid")
    paths = registry_owner.default_substrate_catalog_paths(root)
    metadata = (
        paths.root_manifest_path,
        paths.measurement_registry_path,
        paths.identification_mode_registry_path,
        paths.schema_regime_registry_path,
        paths.epoch_schema_regime_registry_path,
        paths.epoch_schema_regime_scope_registry_path,
    )
    if any(path is None or path.exists() or path.is_symlink() for path in metadata):
        raise AssertionError("complete_candidate_metadata_owner_not_fresh")
    graph_paths = (
        paths.l1_dcat_path,
        root / DEFAULT_L2_SCHOLAR_KG_PATH,
        root / DEFAULT_L3_LEX_KG_PATH,
    )
    graph_bytes = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in graph_paths}
    _write_substrate_catalog_fixture(root, include_graphs=False)
    if {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in graph_paths} != graph_bytes:
        raise AssertionError("complete_candidate_existing_graph_replaced")
    published_root = root / "complete-cov-published-catalog"
    published_root.mkdir(exist_ok=False)
    monkeypatch.setenv("POLISYOS_CACHE_HOME", str(root / "complete-cov-cache"))
    published = build_published_catalog_fixture(published_root, monkeypatch)
    try:
        selection = CatalogServingSourceSelection(
            snapshot_root=published.snapshot_root,
            source_owner_root=root,
            catalog_run_profile="prod_full",
        )
        source = resolve_catalog_serving_source(
            root, selection=selection, requested_profile=selection.catalog_run_profile
        )
        with registry_owner.catalog_serving_source_scope(source):
            registry = registry_owner.build_substrate_registry_from_existing_catalogs(root)
            registry_owner.require_catalog_source_registry_binding(root, registry, source)
            yield selection, source, registry
    finally:
        try:
            published.producer_graph.close()
        finally:
            published.close()

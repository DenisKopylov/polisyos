"""Portable owner-built fixtures for candidate cycle source-profile tests.

Every source artifact is created below the caller's temporary root by the same
owner APIs used by the runtime. The synthetic academic claim is explicitly
fixture-scoped; this fixture does not assert external authenticity, law, or
currentness.
"""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb

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
    SubstrateCoverage,
    SubstrateLayer,
    SubstrateRegistration,
    SubstrateRegistry,
    SubstrateSchemaRegime,
    SubstrateTrustTier,
    build_substrate_registry,
    build_substrate_registry_entry,
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


def _problem(*, runtime_hints: Mapping[str, Any] | None) -> DesignProblem:
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
                    "metric_id": "learning_outcomes",
                }
            ],
            "stakeholders": [{"stakeholder_id": "students", "name": "Students"}],
            "outcome_of_interest": {
                "target_variable": "education.learning_outcomes",
                "metric_id": "learning_outcomes",
                "estimand": "P(education.learning_outcomes | do(education.teaching_method))",
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


def _build_source_files(root: Path) -> tuple[Path, str]:
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
) -> CandidateCycleSubstrateRouteInputs:
    """Build only selected-profile source inputs beneath a caller-owned temp root.

    This fixture does not create a context-job artifact. The normal recursive
    runtime route owns source-profile persistence and fresh resolution.

    Args:
        tmp_path: Pytest-owned root for all controlled source files.
        runtime_hints: Additional problem hints; the candidate-only profile
            selector and N5 resource, budget and horizon bindings are retained.

    Returns:
        Owner-built source data and an unprofiled seed context for the actual
        orchestration route to recompute.
    """

    root = (tmp_path / "policy-engine").resolve()
    root.mkdir(parents=True, exist_ok=False)
    problem = _problem(runtime_hints=runtime_hints)
    skg_path, version_id = _build_source_files(root)
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

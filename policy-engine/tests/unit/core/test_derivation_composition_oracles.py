"""Independent semantic oracles for bounded certified derivation composition."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from polisyos.core.artifacts import (
    ArtifactRef,
    FileSystemCAS,
    PutOptions,
    artifact_manifest_profile_sha256,
    load_core_json_artifact,
)
from polisyos.core.derivations import (
    ArithmeticExpression,
    AssumptionRule,
    AuthorityProjection,
    BasisAttribute,
    BasisSignature,
    CandidateDerivationInput,
    CandidateSourceSeries,
    CertifiedDerivedInput,
    DerivationContext,
    DerivationDagInput,
    DerivationDagNode,
    DerivationEvaluationLimits,
    DerivationRefusalError,
    SeriesPoint,
    SourceDerivationInput,
    SourceSeries,
    TransformFamily,
    TransformFamilyRegistry,
    TransformInputSpec,
    build_composition_recipe,
    materialize_composition,
    materialize_derivation_dag,
    persist_candidate_source_series,
    persist_source_series,
    persist_transform_family_registry,
    resolve_certified_composition,
)


def _selected(store: FileSystemCAS, ref: ArtifactRef) -> ArtifactRef:
    """Return a selected CAS reference bound to its exact manifest profile."""
    return ArtifactRef.model_validate(
        ref.model_dump(mode="python")
        | {"manifest_profile_sha256": artifact_manifest_profile_sha256(store.get_manifest(ref))}
    )


def _marker(store: FileSystemCAS, label: str, *, kind: str = "fixture.evidence") -> ArtifactRef:
    ref = store.put_bytes(label.encode(), PutOptions(kind=kind, media_type="text/plain"))
    return _selected(store, ref)


def _basis(quantity_kind: str, unit: str, *, release: str = "fixture-r1") -> BasisSignature:
    return BasisSignature(
        quantity_kind=quantity_kind,
        unit=unit,
        attributes=(
            BasisAttribute(name="period_basis", value="calendar_year"),
            BasisAttribute(name="release", value=release),
        ),
    )


def _candidate(
    store: FileSystemCAS,
    *,
    variable_id: str,
    basis: BasisSignature,
    value: Decimal,
    context_ref: ArtifactRef,
    scope_ref: ArtifactRef,
    year: int = 2024,
) -> ArtifactRef:
    occurrence = _marker(store, f"occurrence:{variable_id}", kind="fixture.occurrence")
    source = _marker(store, f"source:{variable_id}", kind="fixture.source")
    lineage = tuple(
        sorted(
            (occurrence, source),
            key=lambda ref: (str(ref.artifact_id), ref.manifest_profile_sha256 or ""),
        )
    )
    return persist_candidate_source_series(
        store,
        CandidateSourceSeries(
            variable_id=variable_id,
            basis=basis,
            points=(SeriesPoint(year=year, value=value),),
            source_occurrence_ref=occurrence,
            source_ref=source,
            context_ref=context_ref,
            scope_ref=scope_ref,
            lineage_refs=lineage,
        ),
    )


def _multiply_family(
    *, ratio_basis: BasisSignature, denominator_basis: BasisSignature, output_basis: BasisSignature
) -> TransformFamily:
    return TransformFamily(
        family_id="fixture.ratio_times_denominator.v1",
        method_id="fixture.ratio_times_denominator",
        method_version="1.0.0",
        input_specs=(
            TransformInputSpec(
                role="denominator",
                basis=denominator_basis,
                allowed_input_kinds=("candidate_source", "source"),
            ),
            TransformInputSpec(
                role="ratio",
                basis=ratio_basis,
                allowed_input_kinds=("candidate_source", "source"),
            ),
        ),
        output_basis=output_basis,
        year_domain_role="ratio",
        expression=ArithmeticExpression(
            operator="multiply",
            operands=(
                ArithmeticExpression(operator="current_value", role="ratio"),
                ArithmeticExpression(operator="current_value", role="denominator"),
            ),
        ),
        assumption_rules=(AssumptionRule(name="fixture_scope", literal_value="bounded-fixture"),),
    )


def _net_flow_family(*, flow_basis: BasisSignature) -> TransformFamily:
    return TransformFamily(
        family_id="fixture.net_flow.v1",
        method_id="fixture.net_flow",
        method_version="1.0.0",
        input_specs=(
            TransformInputSpec(
                role="expenditure",
                basis=flow_basis,
                allowed_input_kinds=("certified_derived",),
            ),
            TransformInputSpec(
                role="revenue",
                basis=flow_basis,
                allowed_input_kinds=("certified_derived",),
            ),
        ),
        output_basis=flow_basis,
        year_domain_role="revenue",
        expression=ArithmeticExpression(
            operator="subtract",
            operands=(
                ArithmeticExpression(operator="current_value", role="revenue"),
                ArithmeticExpression(operator="current_value", role="expenditure"),
            ),
        ),
        assumption_rules=(AssumptionRule(name="fixture_scope", literal_value="bounded-fixture"),),
    )


def _adjustment_family(*, flow_basis: BasisSignature) -> TransformFamily:
    return TransformFamily(
        family_id="fixture.add_candidate_adjustment.v1",
        method_id="fixture.add_candidate_adjustment",
        method_version="1.0.0",
        input_specs=(
            TransformInputSpec(
                role="adjustment",
                basis=flow_basis,
                allowed_input_kinds=("candidate_source",),
            ),
            TransformInputSpec(
                role="prior_flow",
                basis=flow_basis,
                allowed_input_kinds=("certified_derived",),
            ),
        ),
        output_basis=flow_basis,
        year_domain_role="prior_flow",
        expression=ArithmeticExpression(
            operator="add",
            operands=(
                ArithmeticExpression(operator="current_value", role="prior_flow"),
                ArithmeticExpression(operator="current_value", role="adjustment"),
            ),
        ),
        assumption_rules=(AssumptionRule(name="fixture_scope", literal_value="bounded-fixture"),),
    )


def _family_with_input_kinds(
    family: TransformFamily,
    *,
    family_id: str,
    method_id: str,
    input_kinds: tuple[str, ...],
) -> TransformFamily:
    """Build a distinct registered ABI over the same bases and expression."""
    payload = family.model_dump(mode="python")
    payload["family_id"] = family_id
    payload["method_id"] = method_id
    payload["input_specs"] = tuple(
        {**item, "allowed_input_kinds": input_kinds} for item in payload["input_specs"]
    )
    return TransformFamily.model_validate(payload)


def _fixture(tmp_path: Path):
    store = FileSystemCAS(tmp_path / "cas")
    context_ref = _marker(store, "candidate calculation context", kind="fixture.context")
    scope_ref = _marker(store, "bounded annual fixture scope", kind="fixture.scope")
    context = DerivationContext(context_ref=context_ref, scope_ref=scope_ref, years=(2024,))

    ratio_basis = _basis("ratio", "ratio")
    denominator_basis = _basis("flow", "usd")
    flow_basis = _basis("flow", "usd")
    registry = TransformFamilyRegistry(
        families=(
            _adjustment_family(flow_basis=flow_basis),
            _net_flow_family(flow_basis=flow_basis),
            _multiply_family(
                ratio_basis=ratio_basis,
                denominator_basis=denominator_basis,
                output_basis=flow_basis,
            ),
        )
    )
    registry_ref = _selected(store, persist_transform_family_registry(store, registry))

    gdp_ref = _candidate(
        store,
        variable_id="fixture.gdp",
        basis=denominator_basis,
        value=Decimal("200000000000"),
        context_ref=context_ref,
        scope_ref=scope_ref,
    )
    revenue_share_ref = _candidate(
        store,
        variable_id="fixture.revenue_share",
        basis=ratio_basis,
        value=Decimal("0.12"),
        context_ref=context_ref,
        scope_ref=scope_ref,
    )
    expenditure_share_ref = _candidate(
        store,
        variable_id="fixture.expenditure_share",
        basis=ratio_basis,
        value=Decimal("0.15"),
        context_ref=context_ref,
        scope_ref=scope_ref,
    )
    adjustment_ref = _candidate(
        store,
        variable_id="fixture.adjustment",
        basis=flow_basis,
        value=Decimal("0"),
        context_ref=context_ref,
        scope_ref=scope_ref,
    )
    return {
        "store": store,
        "context": context,
        "context_ref": context_ref,
        "scope_ref": scope_ref,
        "registry": registry,
        "registry_ref": registry_ref,
        "gdp_ref": gdp_ref,
        "revenue_share_ref": revenue_share_ref,
        "expenditure_share_ref": expenditure_share_ref,
        "adjustment_ref": adjustment_ref,
        "ratio_basis": ratio_basis,
        "denominator_basis": denominator_basis,
        "flow_basis": flow_basis,
    }


def _main_nodes(case: dict[str, object]) -> tuple[DerivationDagNode, ...]:
    return (
        DerivationDagNode(
            node_id="revenue",
            family_id="fixture.ratio_times_denominator.v1",
            method_version="1.0.0",
            output_variable_id="fixture.revenue_flow",
            inputs=(
                DerivationDagInput(
                    role="denominator",
                    selection=CandidateDerivationInput(artifact_ref=case["gdp_ref"]),
                ),
                DerivationDagInput(
                    role="ratio",
                    selection=CandidateDerivationInput(artifact_ref=case["revenue_share_ref"]),
                ),
            ),
        ),
        DerivationDagNode(
            node_id="expenditure",
            family_id="fixture.ratio_times_denominator.v1",
            method_version="1.0.0",
            output_variable_id="fixture.expenditure_flow",
            inputs=(
                DerivationDagInput(
                    role="denominator",
                    selection=CandidateDerivationInput(artifact_ref=case["gdp_ref"]),
                ),
                DerivationDagInput(
                    role="ratio",
                    selection=CandidateDerivationInput(artifact_ref=case["expenditure_share_ref"]),
                ),
            ),
        ),
        DerivationDagNode(
            node_id="net",
            family_id="fixture.net_flow.v1",
            method_version="1.0.0",
            output_variable_id="fixture.net_flow",
            inputs=(
                DerivationDagInput(role="expenditure", node_id="expenditure"),
                DerivationDagInput(role="revenue", node_id="revenue"),
            ),
        ),
    )


def _materialize_main(case: dict[str, object], *, limits=None):
    return materialize_derivation_dag(
        case["store"],
        registry=case["registry"],
        registry_ref=case["registry_ref"],
        nodes=_main_nodes(case),
        root_node_id="net",
        context=case["context"],
        limits=limits,
    )


class _MissingArtifactReader:
    """Read-only CAS wrapper that simulates a missing selected artifact."""

    def __init__(self, store: FileSystemCAS, missing_ref: ArtifactRef) -> None:
        self._store = store
        self._missing_id = missing_ref.artifact_id

    def __getattr__(self, name: str):
        return getattr(self._store, name)

    def get_bytes(self, artifact_id):
        selected_id = getattr(artifact_id, "artifact_id", artifact_id)
        if selected_id == self._missing_id:
            raise FileNotFoundError(str(self._missing_id))
        return self._store.get_bytes(artifact_id)


class _ReadCountingStore:
    """CAS facade that counts selected byte reads for one replay window."""

    def __init__(self, store: FileSystemCAS) -> None:
        self._store = store
        self.byte_reads: dict[object, int] = {}

    def __getattr__(self, name: str):
        return getattr(self._store, name)

    def get_bytes(self, artifact_id):
        selected_id = getattr(artifact_id, "artifact_id", artifact_id)
        key = str(selected_id)
        self.byte_reads[key] = self.byte_reads.get(key, 0) + 1
        return self._store.get_bytes(artifact_id)


def test_two_family_dag_composes_candidate_flows_with_shared_exact_source_and_fresh_replay(
    tmp_path: Path,
) -> None:
    """Two registered operators compose while unknown candidate status stays explicit."""
    case = _fixture(tmp_path)
    result = _materialize_main(case)

    root = result.root
    assert root.series.points == (SeriesPoint(year=2024, value=Decimal("-6000000000.00")),)
    assert root.series.observation_class == "derived"
    assert root.series.evidence_status == "not_established"
    assert root.series.effective_score is None
    assert "empirical_authority_not_established" in root.series.limitations
    assert "source_value_correspondence_not_established" in root.series.limitations

    # The two applications of A share exactly one selected GDP leaf. The net
    # result retains the three distinct source refs, not duplicate GDP entries.
    source_ids = [ref.artifact_id for ref in root.series.source_refs]
    assert len(source_ids) == 3
    assert source_ids.count(case["gdp_ref"].artifact_id) == 1
    assert set(result.node_ids) == {"revenue", "expenditure", "net"}

    replay = resolve_certified_composition(
        FileSystemCAS(case["store"].root),
        certificate_ref=root.certificate_artifact_ref,
        consumer_method_id="tests.independent.fresh_reader",
    )
    assert replay.series == root.series
    assert replay.certificate == root.certificate

    repeated = _materialize_main(case)
    assert repeated.root.derived_artifact_ref == root.derived_artifact_ref
    assert repeated.root.certificate_artifact_ref == root.certificate_artifact_ref
    assert all(item.cache_hit for item in repeated.materializations)


def test_changed_candidate_value_stays_not_established(tmp_path: Path) -> None:
    """Changing bytes under a selected occurrence does not create empirical authority."""
    case = _fixture(tmp_path)
    original_gdp = CandidateSourceSeries.model_validate(
        load_core_json_artifact(case["store"], case["gdp_ref"])
    )
    changed_gdp = persist_candidate_source_series(
        case["store"],
        original_gdp.model_copy(
            update={"points": (SeriesPoint(year=2024, value=Decimal("200000000001")),)}
        ),
    )
    revenue_node = _main_nodes(case)[0].model_copy(
        update={
            "inputs": tuple(
                item.model_copy(
                    update={"selection": CandidateDerivationInput(artifact_ref=changed_gdp)}
                )
                if item.role == "denominator"
                else item
                for item in _main_nodes(case)[0].inputs
            )
        }
    )
    result = materialize_derivation_dag(
        case["store"],
        registry=case["registry"],
        registry_ref=case["registry_ref"],
        nodes=(revenue_node,),
        root_node_id="revenue",
        context=case["context"],
    ).root

    assert result.series.points == (SeriesPoint(year=2024, value=Decimal("24000000000.12")),)
    assert result.series.evidence_status == "not_established"
    assert result.series.effective_score is None
    assert "source_value_correspondence_not_established" in result.series.limitations


def test_fresh_replay_memoizes_a_shared_certified_ancestor(tmp_path: Path) -> None:
    """Two branches referencing one ancestor do not replay its full chain twice."""
    case = _fixture(tmp_path)
    adjustment_two = _candidate(
        case["store"],
        variable_id="fixture.adjustment.two",
        basis=case["flow_basis"],
        value=Decimal("2"),
        context_ref=case["context_ref"],
        scope_ref=case["scope_ref"],
    )
    nodes = (
        _main_nodes(case)[0],
        DerivationDagNode(
            node_id="branch_one",
            family_id="fixture.add_candidate_adjustment.v1",
            method_version="1.0.0",
            output_variable_id="fixture.branch_one",
            inputs=(
                DerivationDagInput(
                    role="adjustment",
                    selection=CandidateDerivationInput(artifact_ref=case["adjustment_ref"]),
                ),
                DerivationDagInput(role="prior_flow", node_id="revenue"),
            ),
        ),
        DerivationDagNode(
            node_id="branch_two",
            family_id="fixture.add_candidate_adjustment.v1",
            method_version="1.0.0",
            output_variable_id="fixture.branch_two",
            inputs=(
                DerivationDagInput(
                    role="adjustment",
                    selection=CandidateDerivationInput(artifact_ref=adjustment_two),
                ),
                DerivationDagInput(role="prior_flow", node_id="revenue"),
            ),
        ),
        DerivationDagNode(
            node_id="net",
            family_id="fixture.net_flow.v1",
            method_version="1.0.0",
            output_variable_id="fixture.branch_difference",
            inputs=(
                DerivationDagInput(role="expenditure", node_id="branch_two"),
                DerivationDagInput(role="revenue", node_id="branch_one"),
            ),
        ),
    )
    counting = _ReadCountingStore(case["store"])
    result = materialize_derivation_dag(
        counting,
        registry=case["registry"],
        registry_ref=case["registry_ref"],
        nodes=nodes,
        root_node_id="net",
        context=case["context"],
    )
    assert result.root.series.points == (SeriesPoint(year=2024, value=Decimal("-2")),)
    ancestor = result.materializations[result.node_ids.index("revenue")]
    counting.byte_reads.clear()

    resolve_certified_composition(
        counting,
        certificate_ref=result.root.certificate_artifact_ref,
        consumer_method_id="tests.independent.shared_ancestor_replay",
    )
    # One certificate payload read and one byte-for-byte CAS reconciliation;
    # a second full path through either branch would double this count.
    assert counting.byte_reads[str(ancestor.certificate_artifact_ref.artifact_id)] == 2


def test_distinct_legacy_source_authority_refs_do_not_promote_composition(
    tmp_path: Path,
) -> None:
    """Resolvable legacy source/verifier refs remain ceilings, not verified evidence."""
    case = _fixture(tmp_path)
    authority_refs = (
        _marker(case["store"], "authority A", kind="fixture.authority"),
        _marker(case["store"], "authority B", kind="fixture.authority"),
    )
    verifier_refs = (
        _marker(case["store"], "verifier A", kind="fixture.verifier"),
        _marker(case["store"], "verifier B", kind="fixture.verifier"),
    )
    assert authority_refs[0].artifact_id != verifier_refs[0].artifact_id
    assert authority_refs[1].artifact_id != verifier_refs[1].artifact_id

    authority = AuthorityProjection(
        effective_score=Decimal("0.8"),
        authority_ref=authority_refs[0].artifact_id,
        verifier_provenance_ref=verifier_refs[0].artifact_id,
        authoritative_for="series_input",
    )
    ratio = SourceSeries(
        variable_id="fixture.legacy_ratio",
        basis=case["ratio_basis"],
        points=(SeriesPoint(year=2024, value=Decimal("0.12")),),
        authority=authority,
        observation_class="observed",
    )
    denominator_authority = AuthorityProjection(
        effective_score=Decimal("0.7"),
        authority_ref=authority_refs[1].artifact_id,
        verifier_provenance_ref=verifier_refs[1].artifact_id,
        authoritative_for="series_input",
    )
    denominator = SourceSeries(
        variable_id="fixture.legacy_gdp",
        basis=case["denominator_basis"],
        points=(SeriesPoint(year=2024, value=Decimal("200000000000")),),
        authority=denominator_authority,
        observation_class="observed",
    )
    ratio_ref = _selected(case["store"], persist_source_series(case["store"], ratio))
    denominator_ref = _selected(case["store"], persist_source_series(case["store"], denominator))
    recipe = build_composition_recipe(
        case["store"],
        registry=case["registry"],
        registry_ref=case["registry_ref"],
        input_refs={
            "ratio": SourceDerivationInput(artifact_ref=ratio_ref),
            "denominator": SourceDerivationInput(artifact_ref=denominator_ref),
        },
        context=case["context"],
        output_variable_id="fixture.legacy_source_candidate_flow",
        family_id="fixture.ratio_times_denominator.v1",
        method_version="1.0.0",
    )
    materialized = materialize_composition(case["store"], recipe)

    assert materialized.series.evidence_status == "not_established"
    assert materialized.series.effective_score is None
    assert len(materialized.certificate.input_contributions) == 2
    for contribution in materialized.certificate.input_contributions:
        assert contribution.kind == "source"
        assert contribution.evidence_status == "not_established"
        assert contribution.effective_score is None
        assert contribution.declared_ceiling in {Decimal("0.7"), Decimal("0.8")}
        assert contribution.authority_predicate_class == "consumer_asserted"


def test_family_selection_uses_input_kind_and_refuses_true_ambiguity(tmp_path: Path) -> None:
    """Equal bases do not erase a family's explicit source-origin ABI."""
    case = _fixture(tmp_path)
    base = next(
        family
        for family in case["registry"].families
        if family.family_id == "fixture.ratio_times_denominator.v1"
    )
    candidate_family = _family_with_input_kinds(
        base,
        family_id="fixture.ratio_candidate_only.v1",
        method_id="fixture.ratio_candidate_only",
        input_kinds=("candidate_source",),
    )
    source_family = _family_with_input_kinds(
        base,
        family_id="fixture.ratio_source_only.v1",
        method_id="fixture.ratio_source_only",
        input_kinds=("source",),
    )
    registry = TransformFamilyRegistry(
        families=tuple(sorted((candidate_family, source_family), key=lambda item: item.family_id))
    )
    candidate_selected = registry.resolve_for_inputs(
        input_bases={"denominator": case["denominator_basis"], "ratio": case["ratio_basis"]},
        input_kinds={"denominator": "candidate_source", "ratio": "candidate_source"},
    )
    source_selected = registry.resolve_for_inputs(
        input_bases={"denominator": case["denominator_basis"], "ratio": case["ratio_basis"]},
        input_kinds={"denominator": "source", "ratio": "source"},
    )
    assert candidate_selected.family_id == candidate_family.family_id
    assert source_selected.family_id == source_family.family_id

    ambiguous = _family_with_input_kinds(
        candidate_family,
        family_id="fixture.ratio_candidate_duplicate.v1",
        method_id="fixture.ratio_candidate_duplicate",
        input_kinds=("candidate_source",),
    )
    ambiguous_registry = TransformFamilyRegistry(
        families=tuple(sorted((candidate_family, ambiguous), key=lambda item: item.family_id))
    )
    with pytest.raises(DerivationRefusalError, match="ambiguous"):
        ambiguous_registry.resolve_for_inputs(
            input_bases={
                "denominator": case["denominator_basis"],
                "ratio": case["ratio_basis"],
            },
            input_kinds={
                "denominator": "candidate_source",
                "ratio": "candidate_source",
            },
        )


@pytest.mark.parametrize("wrong_dimension", ["release", "context", "scope", "year"])
def test_foreign_release_or_context_cannot_enter_the_selected_derivation(
    tmp_path: Path, wrong_dimension: str
) -> None:
    case = _fixture(tmp_path)
    if wrong_dimension == "release":
        foreign_gdp = _candidate(
            case["store"],
            variable_id="fixture.gdp.foreign_release",
            basis=_basis("flow", "usd", release="fixture-r2"),
            value=Decimal("200000000000"),
            context_ref=case["context_ref"],
            scope_ref=case["scope_ref"],
        )
        nodes = tuple(
            node.model_copy(
                update={
                    "inputs": tuple(
                        item.model_copy(
                            update={"selection": CandidateDerivationInput(artifact_ref=foreign_gdp)}
                        )
                        if node.node_id == "revenue" and item.role == "denominator"
                        else item
                        for item in node.inputs
                    )
                }
            )
            if node.node_id == "revenue"
            else node
            for node in _main_nodes(case)
        )
    elif wrong_dimension == "context":
        foreign_context = _marker(
            case["store"], "different observation context", kind="fixture.context"
        )
        foreign_gdp = _candidate(
            case["store"],
            variable_id="fixture.gdp.foreign_context",
            basis=case["denominator_basis"],
            value=Decimal("200000000000"),
            context_ref=foreign_context,
            scope_ref=case["scope_ref"],
        )
        nodes = tuple(
            node.model_copy(
                update={
                    "inputs": tuple(
                        item.model_copy(
                            update={"selection": CandidateDerivationInput(artifact_ref=foreign_gdp)}
                        )
                        if node.node_id == "revenue" and item.role == "denominator"
                        else item
                        for item in node.inputs
                    )
                }
            )
            if node.node_id == "revenue"
            else node
            for node in _main_nodes(case)
        )
    elif wrong_dimension == "scope":
        foreign_scope = _marker(case["store"], "different candidate scope", kind="fixture.scope")
        foreign_gdp = _candidate(
            case["store"],
            variable_id="fixture.gdp.foreign_scope",
            basis=case["denominator_basis"],
            value=Decimal("200000000000"),
            context_ref=case["context_ref"],
            scope_ref=foreign_scope,
        )
        nodes = tuple(
            node.model_copy(
                update={
                    "inputs": tuple(
                        item.model_copy(
                            update={"selection": CandidateDerivationInput(artifact_ref=foreign_gdp)}
                        )
                        if node.node_id == "revenue" and item.role == "denominator"
                        else item
                        for item in node.inputs
                    )
                }
            )
            if node.node_id == "revenue"
            else node
            for node in _main_nodes(case)
        )
    else:
        foreign_gdp = _candidate(
            case["store"],
            variable_id="fixture.gdp.foreign_year",
            basis=case["denominator_basis"],
            value=Decimal("200000000000"),
            context_ref=case["context_ref"],
            scope_ref=case["scope_ref"],
            year=2023,
        )
        nodes = tuple(
            node.model_copy(
                update={
                    "inputs": tuple(
                        item.model_copy(
                            update={"selection": CandidateDerivationInput(artifact_ref=foreign_gdp)}
                        )
                        if node.node_id == "revenue" and item.role == "denominator"
                        else item
                        for item in node.inputs
                    )
                }
            )
            if node.node_id == "revenue"
            else node
            for node in _main_nodes(case)
        )

    with pytest.raises(DerivationRefusalError):
        materialize_derivation_dag(
            case["store"],
            registry=case["registry"],
            registry_ref=case["registry_ref"],
            nodes=nodes,
            root_node_id="net",
            context=case["context"],
        )


def test_missing_and_role_cycle_and_node_budget_fail_before_any_materialization(
    tmp_path: Path,
) -> None:
    case = _fixture(tmp_path)
    main_nodes = _main_nodes(case)
    revenue = main_nodes[0]
    missing_role = revenue.model_copy(update={"inputs": (revenue.inputs[0],)})
    incomplete_nodes = (missing_role, *main_nodes[1:])
    with pytest.raises(DerivationRefusalError):
        materialize_derivation_dag(
            case["store"],
            registry=case["registry"],
            registry_ref=case["registry_ref"],
            nodes=incomplete_nodes,
            root_node_id="net",
            context=case["context"],
        )

    cycle_nodes = (
        DerivationDagNode(
            node_id="left",
            family_id="fixture.ratio_times_denominator.v1",
            method_version="1.0.0",
            output_variable_id="fixture.left",
            inputs=(DerivationDagInput(role="denominator", node_id="right"),),
        ),
        DerivationDagNode(
            node_id="right",
            family_id="fixture.ratio_times_denominator.v1",
            method_version="1.0.0",
            output_variable_id="fixture.right",
            inputs=(DerivationDagInput(role="ratio", node_id="left"),),
        ),
    )
    with pytest.raises(DerivationRefusalError, match="cycle"):
        materialize_derivation_dag(
            case["store"],
            registry=case["registry"],
            registry_ref=case["registry_ref"],
            nodes=cycle_nodes,
            root_node_id="left",
            context=case["context"],
        )

    with pytest.raises(DerivationRefusalError, match="budget"):
        _materialize_main(case, limits=DerivationEvaluationLimits(max_nodes=2))
    with pytest.raises(DerivationRefusalError, match="budget"):
        _materialize_main(case, limits=DerivationEvaluationLimits(max_selected_sources=2))
    with pytest.raises(DerivationRefusalError, match="budget"):
        _materialize_main(case, limits=DerivationEvaluationLimits(max_selected_sources=2))


def test_wrong_output_certificate_pair_is_rejected(tmp_path: Path) -> None:
    case = _fixture(tmp_path)
    result = _materialize_main(case)
    revenue = result.materializations[result.node_ids.index("revenue")]
    expenditure = result.materializations[result.node_ids.index("expenditure")]
    net_family = next(
        family for family in case["registry"].families if family.family_id == "fixture.net_flow.v1"
    )
    # Pairing one node's output bytes with another node's valid certificate is
    # a graft, even though both share the same basis and context.
    with pytest.raises(DerivationRefusalError):
        build_composition_recipe(
            case["store"],
            registry=case["registry"],
            registry_ref=case["registry_ref"],
            input_refs={
                "revenue": CertifiedDerivedInput(
                    artifact_ref=revenue.derived_artifact_ref,
                    certificate_ref=expenditure.certificate_artifact_ref,
                ),
                "expenditure": CertifiedDerivedInput(
                    artifact_ref=expenditure.derived_artifact_ref,
                    certificate_ref=expenditure.certificate_artifact_ref,
                ),
            },
            context=case["context"],
            output_variable_id="fixture.grafted_net",
            family_id=net_family.family_id,
            method_version=net_family.method_version,
        )


@pytest.mark.parametrize(
    "missing_member", ["root_output", "root_certificate", "deep_output", "deep_certificate"]
)
def test_fresh_replay_refuses_missing_output_or_certificate(
    tmp_path: Path, missing_member: str
) -> None:
    case = _fixture(tmp_path)
    result = _materialize_main(case)
    root = result.root
    deep = result.materializations[result.node_ids.index("revenue")]
    missing_ref = (
        root.derived_artifact_ref
        if missing_member == "root_output"
        else root.certificate_artifact_ref
        if missing_member == "root_certificate"
        else deep.derived_artifact_ref
        if missing_member == "deep_output"
        else deep.certificate_artifact_ref
    )
    reader = _MissingArtifactReader(case["store"], missing_ref)
    with pytest.raises(DerivationRefusalError):
        resolve_certified_composition(
            reader,
            certificate_ref=root.certificate_artifact_ref,
            consumer_method_id="tests.independent.removal_control",
        )


def test_external_prior_chain_counts_toward_total_node_budget(tmp_path: Path) -> None:
    """A two-node prior certificate plus two new nodes cannot fit a two-node cap."""
    case = _fixture(tmp_path)
    first_node = DerivationDagNode(
        node_id="revenue",
        family_id="fixture.ratio_times_denominator.v1",
        method_version="1.0.0",
        output_variable_id="fixture.revenue_flow",
        inputs=(
            DerivationDagInput(
                role="denominator",
                selection=CandidateDerivationInput(artifact_ref=case["gdp_ref"]),
            ),
            DerivationDagInput(
                role="ratio",
                selection=CandidateDerivationInput(artifact_ref=case["revenue_share_ref"]),
            ),
        ),
    )
    prior_root = DerivationDagNode(
        node_id="adjusted",
        family_id="fixture.add_candidate_adjustment.v1",
        method_version="1.0.0",
        output_variable_id="fixture.adjusted_revenue",
        inputs=(
            DerivationDagInput(
                role="adjustment",
                selection=CandidateDerivationInput(artifact_ref=case["adjustment_ref"]),
            ),
            DerivationDagInput(role="prior_flow", node_id="revenue"),
        ),
    )
    prior = materialize_derivation_dag(
        case["store"],
        registry=case["registry"],
        registry_ref=case["registry_ref"],
        nodes=(first_node, prior_root),
        root_node_id="adjusted",
        context=case["context"],
    ).root

    next_one = DerivationDagNode(
        node_id="next_one",
        family_id="fixture.add_candidate_adjustment.v1",
        method_version="1.0.0",
        output_variable_id="fixture.next_one",
        inputs=(
            DerivationDagInput(
                role="adjustment",
                selection=CandidateDerivationInput(artifact_ref=case["adjustment_ref"]),
            ),
            DerivationDagInput(
                role="prior_flow",
                selection=CertifiedDerivedInput(
                    artifact_ref=prior.derived_artifact_ref,
                    certificate_ref=prior.certificate_artifact_ref,
                ),
            ),
        ),
    )
    next_two = DerivationDagNode(
        node_id="next_two",
        family_id="fixture.add_candidate_adjustment.v1",
        method_version="1.0.0",
        output_variable_id="fixture.next_two",
        inputs=(
            DerivationDagInput(
                role="adjustment",
                selection=CandidateDerivationInput(artifact_ref=case["adjustment_ref"]),
            ),
            DerivationDagInput(role="prior_flow", node_id="next_one"),
        ),
    )
    with pytest.raises(DerivationRefusalError, match="budget"):
        materialize_derivation_dag(
            case["store"],
            registry=case["registry"],
            registry_ref=case["registry_ref"],
            nodes=(next_one, next_two),
            root_node_id="next_two",
            context=case["context"],
            limits=DerivationEvaluationLimits(max_nodes=2),
        )

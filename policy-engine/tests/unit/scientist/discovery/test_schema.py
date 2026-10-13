from typing import Any, cast, get_args

import pytest
from pydantic import BaseModel, ValidationError

import polisyos.scientist.methods.discovery.schema as discovery_schema
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.contracts.scientist import GraphHypothesisRef
from polisyos.ir.analytics.causal_discovery import (
    LATENT_CARDINALITY_EVIDENCE_KEY,
    LATENT_CARDINALITY_FAILURE_REASONS_KEY,
    AlgebraicConstraintFamily,
    AlgebraicConstraintReport,
    CausalDiscoveryReport,
    ConstraintEvaluationResult,
    ImpliedConstraintSpec,
    LatentAssumptionCard,
    LatentBlockEvidence,
    LatentBlockProposal,
    LatentBlockStatus,
    LatentCardinalityEvidencePayload,
    LatentCausalRole,
    LatentDiscoveryBundle,
    LatentGraphStatus,
    LatentPromotionEvidence,
    LatentTrustLevel,
)
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    EdgeMark,
    GraphProjectionStatus,
    GraphType,
    graph_projection_disposition,
)
from polisyos.ir.registry.refs import ArtifactRefModel, CausalDiscoveryReportRef
from polisyos.scientist.methods.causal.latent_separation import (
    SEPARATION_DIAGNOSTIC_INPUTS_KEY,
)
from polisyos.scientist.methods.discovery.schema import (
    GRAPH_HYPOTHESIS_SCHEMA_NAME,
    GRAPH_HYPOTHESIS_SCHEMA_VERSION,
    ComputeFootprint,
    DiscoveryAlgorithmFamily,
    DiscoveryMethod,
    GraphHypothesis,
    _revalidate_current_graph_hypothesis,
    edge_key_for_edge,
    graph_hypothesis_from_report,
    infer_algorithm_family,
    load_graph_hypothesis,
    persist_graph_hypothesis,
)


def _graph(
    *,
    graph_type: GraphType,
    edges: list[CausalEdge],
    nodes: list[str] | None = None,
    discovery_method: str = "",
) -> CausalGraphModel:
    resolved_nodes = nodes or sorted({node for edge in edges for node in (edge.src, edge.dst)})
    return CausalGraphModel(
        graph_type=graph_type,
        nodes=resolved_nodes,
        edges=edges,
        discovery_method=discovery_method,
    )


def _rich_current_graph_hypothesis() -> GraphHypothesis:
    """Build a current artifact with every declared nested model family populated."""
    graph = _graph(
        graph_type=GraphType.DAG,
        edges=[CausalEdge(src="X", dst="Y", combined_confidence=0.8)],
        nodes=["X", "Y"],
        discovery_method="dagma",
    )
    artifact_ref = ArtifactRefModel(
        artifact_id="sha256:" + "a" * 64,
        kind="ir.causal_discovery_report",
        media_type="application/json",
    )
    return GraphHypothesis(
        schema_version=GRAPH_HYPOTHESIS_SCHEMA_VERSION,
        hypothesis_id="rich-current",
        algorithm_family=DiscoveryAlgorithmFamily.SCORE_BASED,
        method=DiscoveryMethod.DAGMA,
        graph=graph,
        projection_disposition=graph_projection_disposition(
            graph, graph, status=GraphProjectionStatus.IDENTITY
        ),
        edge_confidence={"X->Y": 0.8},
        compute_footprint=ComputeFootprint(
            runtime_seconds=1.25,
            timeout_seconds=30.0,
            n_samples=50,
            n_variables=2,
            n_bootstrap=4,
            random_seed=7,
            backend="cpu",
            method_params={"alpha": 0.1},
            metadata={"profile": "complete"},
        ),
        algebraic_constraints=AlgebraicConstraintReport(
            implied_constraints_ref=artifact_ref,
            violated_constraints_ref=artifact_ref,
            implied_constraints_preview=[
                ImpliedConstraintSpec(
                    constraint_id="ci:X_Y",
                    family=AlgebraicConstraintFamily.CI,
                    statement="X independent of Y given the empty set",
                    variables=("X", "Y"),
                )
            ],
            violated_constraints_preview=[
                ConstraintEvaluationResult(
                    constraint_id="ci:X_Y",
                    family=AlgebraicConstraintFamily.CI,
                    status="violated",
                    p_value=0.01,
                )
            ],
        ),
        latent_discovery=LatentDiscoveryBundle(
            proposed_latent_nodes=["U_income"],
            assumption_cards=[
                LatentAssumptionCard(
                    assumption_id="latent-card",
                    title="Latent confounding is unresolved",
                    description="The candidate remains research-only.",
                    evidence_basis=["source_graph"],
                )
            ],
            promotion_evidence=LatentPromotionEvidence(
                observable_implication_refs=[artifact_ref],
                notes=["candidate evidence only"],
            ),
        ),
        source_discovery_report_ref=CausalDiscoveryReportRef(
            artifact_id="sha256:" + "b" * 64,
            kind="ir.causal_discovery_report",
            media_type="application/json",
        ),
        metadata={"source": "unit_test"},
    )


def _nested_model_types(annotation: object, seen: set[type[BaseModel]] | None = None) -> set[type[BaseModel]]:
    found = seen if seen is not None else set()
    try:
        is_model_type = isinstance(annotation, type) and issubclass(annotation, BaseModel)
    except TypeError:
        is_model_type = False
    if is_model_type:
        model_type = cast("type[BaseModel]", annotation)
        if model_type in found:
            return found
        found.add(model_type)
        for field in model_type.model_fields.values():
            _nested_model_types(field.annotation, found)
        return found
    for argument in get_args(annotation):
        _nested_model_types(argument, found)
    return found


def _nested_model_paths(value: object, path: tuple[object, ...] = ()) -> list[tuple[tuple[object, ...], BaseModel]]:
    if isinstance(value, BaseModel):
        found = [(path, value)]
        fields = object.__getattribute__(value, "__dict__")
        for name in type(value).model_fields:
            if name in fields:
                found.extend(_nested_model_paths(fields[name], (*path, ("field", name))))
        return found
    if isinstance(value, dict):
        found = []
        for key, item in dict.items(value):
            found.extend(_nested_model_paths(item, (*path, ("key", key))))
        return found
    if isinstance(value, list):
        found = []
        for index, item in enumerate(list.__iter__(value)):
            found.extend(_nested_model_paths(item, (*path, ("index", index))))
        return found
    if isinstance(value, tuple):
        found = []
        for index, item in enumerate(value):
            found.extend(_nested_model_paths(item, (*path, ("index", index))))
        return found
    if isinstance(value, (set, frozenset)):
        found = []
        for index, item in enumerate(value):
            found.extend(_nested_model_paths(item, (*path, ("index", index))))
        return found
    return []


def _nested_model_field_targets(
    value: object, path: tuple[object, ...] = ()
) -> list[tuple[tuple[object, ...], str, BaseModel]]:
    if isinstance(value, BaseModel):
        targets = [
            (path, name, value)
            for name, field in type(value).model_fields.items()
            if field.annotation is not Any
        ]
        fields = object.__getattribute__(value, "__dict__")
        for name in type(value).model_fields:
            if name in fields:
                targets.extend(
                    _nested_model_field_targets(
                        fields[name], (*path, ("field", name))
                    )
                )
        return targets
    if isinstance(value, dict):
        targets = []
        for key, item in dict.items(value):
            targets.extend(_nested_model_field_targets(item, (*path, ("key", key))))
        return targets
    if isinstance(value, list):
        targets = []
        for index, item in enumerate(list.__iter__(value)):
            targets.extend(_nested_model_field_targets(item, (*path, ("index", index))))
        return targets
    if isinstance(value, tuple):
        targets = []
        for index, item in enumerate(value):
            targets.extend(_nested_model_field_targets(item, (*path, ("index", index))))
        return targets
    if isinstance(value, (set, frozenset)):
        targets = []
        for item in value:
            targets.extend(_nested_model_field_targets(item, (*path, ("member", item))))
        return targets
    return []


def _nested_value_at_path(value: object, path: tuple[object, ...]) -> object:
    current = value
    for kind, key in path:
        if kind == "field":
            current = object.__getattribute__(current, "__dict__")[key]
        elif kind == "index":
            if isinstance(current, list):
                current = list.__getitem__(current, key)
            elif isinstance(current, tuple):
                current = tuple.__getitem__(current, key)
            else:
                raise AssertionError("index path does not reference a list or tuple")
        elif kind == "key":
            current = dict.__getitem__(current, key)
        elif kind == "member":
            matches = [item for item in current if item is key or item == key]
            if len(matches) != 1:
                raise AssertionError("set member path is not uniquely resolvable")
            current = matches[0]
        else:
            raise AssertionError(f"unsupported nested path component: {kind!r}")
    return current


def _replace_nested_value(
    value: object, path: tuple[object, ...], replacement: object
) -> Any:
    if not path:
        return replacement
    kind, key = path[0]
    child_path = path[1:]
    if kind == "field":
        child = object.__getattribute__(value, "__dict__")[key]
        return value.model_copy(
            update={key: _replace_nested_value(child, child_path, replacement)}
        )
    if kind == "index":
        items = list(list.__iter__(value))
        items[key] = _replace_nested_value(items[key], child_path, replacement)
        return items
    if kind == "key":
        items = dict(dict.items(value))
        items[key] = _replace_nested_value(items[key], child_path, replacement)
        return items
    raise AssertionError(f"unsupported nested path component: {kind!r}")


def test_graph_hypothesis_uses_shared_bootstrap_then_combined_then_data_confidence() -> None:
    edge = CausalEdge(
        src="X",
        dst="Y",
        lag=2,
        combined_confidence=0.81,
        data_confidence=0.37,
    )
    report = CausalDiscoveryReport(
        method="pc",
        graph=_graph(graph_type=GraphType.CPDAG, edges=[edge], discovery_method="pc"),
        bootstrap_stability={edge_key_for_edge(edge): 0.99},
    )

    hypothesis_with_shared = graph_hypothesis_from_report(
        report,
        hypothesis_id="shared",
        shared_bootstrap_stability={edge_key_for_edge(edge): 0.62},
    )
    hypothesis_without_shared = graph_hypothesis_from_report(
        report,
        hypothesis_id="local",
    )

    assert edge_key_for_edge(edge) == "X->Y@lag=2"
    assert hypothesis_with_shared.edge_confidence["X->Y@lag=2"] == 0.62
    assert hypothesis_without_shared.edge_confidence["X->Y@lag=2"] == 0.81


def test_graph_hypothesis_persists_and_loads_from_cas(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    graph = _graph(
        graph_type=GraphType.DAG,
        edges=[CausalEdge(src="X", dst="Y", combined_confidence=0.7)],
        discovery_method="dagma",
    )
    hypothesis = GraphHypothesis(
        schema_version=GRAPH_HYPOTHESIS_SCHEMA_VERSION,
        hypothesis_id="dagma_0",
        algorithm_family=DiscoveryAlgorithmFamily.SCORE_BASED,
        method=DiscoveryMethod.DAGMA,
        graph=graph,
        projection_disposition=graph_projection_disposition(
            graph,
            graph,
            status=GraphProjectionStatus.IDENTITY,
        ),
        edge_confidence={"X->Y": 0.7},
        assumptions=["continuous optimization over DAG structure"],
        compute_footprint=ComputeFootprint(
            runtime_seconds=1.25,
            timeout_seconds=30.0,
            n_samples=100,
            n_variables=2,
            n_bootstrap=0,
            random_seed=7,
            backend="optimizer=dagma",
            method_params={"alpha": 0.1},
            metadata={"report_method": "dagma"},
        ),
        metadata={"source": "unit_test"},
    )

    ref = persist_graph_hypothesis(store, hypothesis)
    manifest = store.get_manifest(ref)
    payload = from_canonical_bytes(store.get_bytes(ref))
    loaded = load_graph_hypothesis(store, ref)

    assert ref.kind == "scientist.graph_hypothesis"
    assert manifest.artifact_schema.name == GRAPH_HYPOTHESIS_SCHEMA_NAME
    assert manifest.artifact_schema.version == GRAPH_HYPOTHESIS_SCHEMA_VERSION
    assert payload["schema_version"] == GRAPH_HYPOTHESIS_SCHEMA_VERSION
    assert loaded == hypothesis


def test_graph_hypothesis_writer_revalidates_version_before_cas_write(tmp_path) -> None:
    graph = _graph(
        graph_type=GraphType.DAG,
        edges=[CausalEdge(src="X", dst="Y")],
        nodes=["X", "Y"],
    )
    hypothesis = GraphHypothesis(
        schema_version=GRAPH_HYPOTHESIS_SCHEMA_VERSION,
        hypothesis_id="dag-current",
        algorithm_family=DiscoveryAlgorithmFamily.SCORE_BASED,
        method=DiscoveryMethod.DAGMA,
        graph=graph,
        projection_disposition=graph_projection_disposition(
            graph,
            graph,
            status=GraphProjectionStatus.IDENTITY,
        ),
    )
    forged = hypothesis.model_copy(update={"schema_version": "1.0"})
    store = FileSystemCAS(tmp_path)
    before_files = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*") if path.is_file())

    with pytest.raises(ValidationError):
        persist_graph_hypothesis(store, forged)

    after_files = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*") if path.is_file())
    assert after_files == before_files


def test_writer_recursively_rebuilds_nested_models_and_reader_accepts_the_output(
    tmp_path,
) -> None:
    hypothesis = _rich_current_graph_hypothesis()
    graph_rows = (hypothesis.graph.kuzu_node_rows, hypothesis.graph.kuzu_edge_rows)
    assert len(graph_rows) == 2
    rebuilt = _revalidate_current_graph_hypothesis(hypothesis)
    original_models = dict(_nested_model_paths(hypothesis))
    rebuilt_models = dict(_nested_model_paths(rebuilt))

    assert original_models.keys() == rebuilt_models.keys()
    declared_types = _nested_model_types(GraphHypothesis)
    actual_types = {type(model) for model in original_models.values()}
    assert declared_types <= actual_types
    for path, original in original_models.items():
        current = rebuilt_models[path]
        assert type(current) is type(original), path
        assert current is not original, path

    store = FileSystemCAS(tmp_path)
    ref = persist_graph_hypothesis(store, hypothesis)
    loaded = load_graph_hypothesis(store, ref)
    assert loaded == rebuilt


def test_writer_revalidates_every_declared_nested_model_field_before_cas_write(
    tmp_path,
) -> None:
    hypothesis = _rich_current_graph_hypothesis()
    store = FileSystemCAS(tmp_path)
    before_files = sorted(
        path.relative_to(tmp_path) for path in tmp_path.rglob("*") if path.is_file()
    )
    targets = _nested_model_field_targets(hypothesis)
    assert targets

    for model_path, field_name, _model in targets:
        forged_hypothesis = hypothesis.model_copy(deep=True)
        forged_model = _nested_value_at_path(forged_hypothesis, model_path)
        object.__setattr__(forged_model, field_name, object())
        with pytest.raises(ValueError):
            persist_graph_hypothesis(store, forged_hypothesis)
        after_files = sorted(
            path.relative_to(tmp_path) for path in tmp_path.rglob("*") if path.is_file()
        )
        assert after_files == before_files, (model_path, field_name)


def test_writer_rejects_forged_nested_footprint_before_any_cas_write(tmp_path) -> None:
    hypothesis = _rich_current_graph_hypothesis()
    forged_footprint = hypothesis.compute_footprint.model_copy(
        update={"runtime_seconds": -1.0}
    )
    forged = hypothesis.model_copy(update={"compute_footprint": forged_footprint})
    store = FileSystemCAS(tmp_path)
    before_files = sorted(
        path.relative_to(tmp_path) for path in tmp_path.rglob("*") if path.is_file()
    )

    with pytest.raises(ValueError):
        persist_graph_hypothesis(store, forged)

    after_files = sorted(
        path.relative_to(tmp_path) for path in tmp_path.rglob("*") if path.is_file()
    )
    assert after_files == before_files


@pytest.mark.parametrize(
    "forgery",
    ["graph_edge", "disposition", "confidence", "nested_member"],
)
def test_writer_rejects_forged_graph_disposition_confidence_and_members(
    tmp_path, forgery: str
) -> None:
    hypothesis = _rich_current_graph_hypothesis()
    if forgery == "graph_edge":
        forged_edge = hypothesis.graph.edges[0].model_copy(
            update={"mark_src": EdgeMark.CIRCLE}
        )
        forged_graph = hypothesis.graph.model_copy(update={"edges": [forged_edge]})
        forged = hypothesis.model_copy(update={"graph": forged_graph})
    elif forgery == "disposition":
        forged_disposition = hypothesis.projection_disposition.model_copy(
            update={"source_graph_sha256": "not-a-content-hash"}
        )
        forged = hypothesis.model_copy(
            update={"projection_disposition": forged_disposition}
        )
    elif forgery == "confidence":
        forged = hypothesis.model_copy(update={"edge_confidence": {"X->Y": 1.1}})
    else:
        assert hypothesis.algebraic_constraints is not None
        forged_constraints = hypothesis.algebraic_constraints.model_copy(
            update={"violated_constraints_preview": [object()]}
        )
        forged = hypothesis.model_copy(
            update={"algebraic_constraints": forged_constraints}
        )

    store = FileSystemCAS(tmp_path)
    before_files = sorted(
        path.relative_to(tmp_path) for path in tmp_path.rglob("*") if path.is_file()
    )
    with pytest.raises(ValueError):
        persist_graph_hypothesis(store, forged)
    after_files = sorted(
        path.relative_to(tmp_path) for path in tmp_path.rglob("*") if path.is_file()
    )
    assert after_files == before_files


def test_writer_rejects_forged_nested_model_dump_without_trusting_it(
    tmp_path,
) -> None:
    class ForgedFootprint(ComputeFootprint):
        def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            payload = super().model_dump(*args, **kwargs)
            payload["runtime_seconds"] = 0.0
            return payload

    hypothesis = _rich_current_graph_hypothesis()
    forged_footprint = ForgedFootprint.model_construct(runtime_seconds=-1.0)
    forged = hypothesis.model_copy(update={"compute_footprint": forged_footprint})
    store = FileSystemCAS(tmp_path)
    before_files = sorted(
        path.relative_to(tmp_path) for path in tmp_path.rglob("*") if path.is_file()
    )

    with pytest.raises(ValueError):
        persist_graph_hypothesis(store, forged)

    after_files = sorted(
        path.relative_to(tmp_path) for path in tmp_path.rglob("*") if path.is_file()
    )
    assert after_files == before_files


def test_recursive_writer_removal_probe_keeps_markers_but_reopens_reader_failure(
    tmp_path, monkeypatch
) -> None:
    hypothesis = _rich_current_graph_hypothesis()
    forged_footprint = hypothesis.compute_footprint.model_copy(
        update={"runtime_seconds": -1.0}
    )
    forged = hypothesis.model_copy(update={"compute_footprint": forged_footprint})
    monkeypatch.setattr(
        discovery_schema,
        "_snapshot_graph_hypothesis_value",
        lambda value, annotation: value,
    )
    store = FileSystemCAS(tmp_path)

    ref = persist_graph_hypothesis(store, forged)
    manifest = store.get_manifest(ref)
    payload = from_canonical_bytes(store.get_bytes(ref))

    assert manifest.artifact_schema is not None
    assert manifest.artifact_schema.version == GRAPH_HYPOTHESIS_SCHEMA_VERSION
    assert payload["schema_version"] == GRAPH_HYPOTHESIS_SCHEMA_VERSION
    assert payload["compute_footprint"]["runtime_seconds"] == -1.0
    with pytest.raises(ValidationError):
        load_graph_hypothesis(store, ref)


def test_writer_rejects_undeclared_nested_model_storage_before_cas_write(
    tmp_path,
) -> None:
    hypothesis = _rich_current_graph_hypothesis()
    forged_footprint = hypothesis.compute_footprint.model_copy()
    object.__getattribute__(forged_footprint, "__dict__")["foreign_runtime_hint"] = 1
    forged = hypothesis.model_copy(update={"compute_footprint": forged_footprint})
    store = FileSystemCAS(tmp_path)
    before_files = sorted(
        path.relative_to(tmp_path) for path in tmp_path.rglob("*") if path.is_file()
    )

    with pytest.raises(ValueError):
        persist_graph_hypothesis(store, forged)

    after_files = sorted(
        path.relative_to(tmp_path) for path in tmp_path.rglob("*") if path.is_file()
    )
    assert after_files == before_files


def test_writer_accepts_a_valid_model_construct_after_recursive_revalidation(tmp_path) -> None:
    hypothesis = _rich_current_graph_hypothesis()
    fields = {
        name: object.__getattribute__(hypothesis, "__dict__")[name]
        for name in GraphHypothesis.model_fields
    }
    constructed = GraphHypothesis.model_construct(**fields)
    store = FileSystemCAS(tmp_path)

    ref = persist_graph_hypothesis(store, constructed)

    assert load_graph_hypothesis(store, ref) == _revalidate_current_graph_hypothesis(constructed)


def _put_raw_graph_hypothesis(
    store: FileSystemCAS,
    payload: dict[str, object],
    *,
    manifest_version: str | None,
    schema_name: str | None = GRAPH_HYPOTHESIS_SCHEMA_NAME,
) -> GraphHypothesisRef:
    schema = (
        SchemaInfo(name=schema_name, version=manifest_version)
        if schema_name is not None and manifest_version is not None
        else None
    )
    ref = store.put_json(
        payload,
        PutOptions(
            kind="scientist.graph_hypothesis",
            media_type="application/json",
            schema=schema,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return GraphHypothesisRef.model_validate(ref.model_dump(mode="json"))


@pytest.mark.parametrize(
    ("manifest_version", "payload_version", "include_disposition", "schema_name"),
    [
        ("1.0", "1.1", True, GRAPH_HYPOTHESIS_SCHEMA_NAME),
        ("1.1", "1.0", True, GRAPH_HYPOTHESIS_SCHEMA_NAME),
        ("1.1", None, True, GRAPH_HYPOTHESIS_SCHEMA_NAME),
        ("1.2", "1.2", True, GRAPH_HYPOTHESIS_SCHEMA_NAME),
        ("1.0", "1.0", True, GRAPH_HYPOTHESIS_SCHEMA_NAME),
        ("1.1", "1.1", False, GRAPH_HYPOTHESIS_SCHEMA_NAME),
        ("1.1", "1.1", True, "wrong.graph.hypothesis.schema"),
        ("1.1", "1.1", True, None),
        (None, "1.1", True, GRAPH_HYPOTHESIS_SCHEMA_NAME),
        ("not-a-version", "not-a-version", True, GRAPH_HYPOTHESIS_SCHEMA_NAME),
    ],
)
def test_graph_hypothesis_loader_rejects_unbound_schema_headers(
    tmp_path,
    manifest_version: str | None,
    payload_version: str | None,
    include_disposition: bool,
    schema_name: str | None,
) -> None:
    graph = _graph(
        graph_type=GraphType.DAG,
        edges=[CausalEdge(src="X", dst="Y")],
        nodes=["X", "Y"],
    )
    hypothesis = GraphHypothesis(
        schema_version=GRAPH_HYPOTHESIS_SCHEMA_VERSION,
        hypothesis_id="dag-current",
        algorithm_family=DiscoveryAlgorithmFamily.SCORE_BASED,
        method=DiscoveryMethod.DAGMA,
        graph=graph,
        projection_disposition=graph_projection_disposition(
            graph,
            graph,
            status=GraphProjectionStatus.IDENTITY,
        ),
    )
    payload = hypothesis.model_dump(mode="json")
    if payload_version is None:
        payload.pop("schema_version")
    else:
        payload["schema_version"] = payload_version
    if not include_disposition:
        payload.pop("projection_disposition")
    store = FileSystemCAS(tmp_path)
    ref = _put_raw_graph_hypothesis(
        store,
        payload,
        manifest_version=manifest_version,
        schema_name=schema_name,
    )

    with pytest.raises(ValueError, match="schema|historical"):
        load_graph_hypothesis(store, ref)


def test_graph_hypothesis_loader_adapts_only_manifest_bound_historical_10_partial(
    tmp_path,
) -> None:
    graph = _graph(
        graph_type=GraphType.PAG,
        edges=[CausalEdge(src="X", dst="Y", mark_src=EdgeMark.CIRCLE)],
        nodes=["X", "Y"],
        discovery_method="fci",
    )
    payload: dict[str, object] = {
        "schema_version": "1.0",
        "hypothesis_id": "fci-legacy-persisted",
        "algorithm_family": "constraint_based",
        "method": "fci",
        "graph": graph.model_dump(mode="json"),
    }
    store = FileSystemCAS(tmp_path)
    ref = _put_raw_graph_hypothesis(store, payload, manifest_version="1.0")

    loaded = load_graph_hypothesis(store, ref)

    assert loaded.schema_version == GRAPH_HYPOTHESIS_SCHEMA_VERSION
    assert loaded.graph.graph_type is GraphType.PAG
    assert loaded.projection_disposition.status is GraphProjectionStatus.UNSUPPORTED
    assert loaded.graph_for_analysis() is None


def test_graph_hypothesis_extracts_failure_reasons_from_report_warnings() -> None:
    report = CausalDiscoveryReport(
        method="fci",
        graph=_graph(
            graph_type=GraphType.PAG,
            edges=[CausalEdge(src="X", dst="Y", mark_src=EdgeMark.CIRCLE, mark_dst=EdgeMark.ARROW)],
            discovery_method="fci",
        ),
        warnings=[
            "algorithm_failed:TimeoutError: backend timed out",
            "soft warning that should remain informational",
        ],
        metadata={"backend": "optional"},
    )

    hypothesis = graph_hypothesis_from_report(report, hypothesis_id="fci_0")

    assert hypothesis.method is DiscoveryMethod.FCI
    assert hypothesis.algorithm_family is DiscoveryAlgorithmFamily.CONSTRAINT_BASED
    assert hypothesis.failure_reasons == ["algorithm_failed:TimeoutError: backend timed out"]
    assert "soft warning that should remain informational" in hypothesis.warnings


def test_graph_hypothesis_carries_typed_discovery_payloads_from_report() -> None:
    report = CausalDiscoveryReport(
        method="pc",
        graph=_graph(
            graph_type=GraphType.DAG,
            edges=[CausalEdge(src="X", dst="Y", combined_confidence=0.8)],
            discovery_method="pc",
        ),
        algebraic_constraints=AlgebraicConstraintReport(
            severity="warning",
            violated_constraints_preview=[
                ConstraintEvaluationResult(
                    constraint_id="ci:X_Y",
                    family=AlgebraicConstraintFamily.CI,
                    status="violated",
                    severity="blocker",
                )
            ],
        ),
        latent_discovery=LatentDiscoveryBundle(
            proposed_latent_nodes=["U_income"],
            inducing_environments=["region"],
            identification_conditions=["proxy_quality"],
            falsification_tests=["negative_control_outcome"],
            trust_level=LatentTrustLevel.RESEARCH,
            assumption_cards=[
                LatentAssumptionCard(
                    assumption_id="latent_card",
                    title="Latent confounding remains research-only",
                    description="Observed proxies may still mask latent confounding.",
                )
            ],
            no_promotion_reasons=["latent_discovery_proof_only"],
        ),
        metadata={"algebraic_constraint_severity": "warning"},
    )

    hypothesis = graph_hypothesis_from_report(report, hypothesis_id="pc_0")

    assert hypothesis.algebraic_constraints == report.algebraic_constraints
    assert hypothesis.latent_discovery == report.latent_discovery
    assert hypothesis.source_discovery_report_ref is None


def test_historical_partial_hypothesis_refusal_keeps_report_ref() -> None:
    graph = _graph(
        graph_type=GraphType.PAG,
        edges=[CausalEdge(src="X", dst="Y", mark_src=EdgeMark.CIRCLE)],
        nodes=["X", "Y"],
        discovery_method="fci",
    )
    ref = CausalDiscoveryReportRef(
        artifact_id="sha256:" + "a" * 64,
        kind="ir.causal_discovery_report",
        media_type="application/json",
    )
    legacy = GraphHypothesis.model_validate(
        {
            "schema_version": "1.0",
            "hypothesis_id": "fci-legacy",
            "algorithm_family": "constraint_based",
            "method": "fci",
            "graph": graph.model_dump(mode="json"),
            "source_discovery_report_ref": ref.model_dump(mode="json"),
        }
    )
    assert legacy.schema_version == "1.1"
    assert legacy.projection_disposition.status is GraphProjectionStatus.UNSUPPORTED
    assert legacy.source_discovery_report_ref == ref
    assert legacy.graph.graph_type is GraphType.PAG
    assert legacy.graph_for_analysis() is None


def test_explicit_null_hypothesis_disposition_is_not_legacy_absence(
) -> None:
    graph = _graph(
        graph_type=GraphType.PAG,
        edges=[CausalEdge(src="X", dst="Y", mark_src=EdgeMark.CIRCLE)],
        nodes=["X", "Y"],
    )
    with pytest.raises(ValueError):
        GraphHypothesis.model_validate(
            {
                "schema_version": "1.1",
                "hypothesis_id": "fci-null-status",
                "algorithm_family": "constraint_based",
                "method": "fci",
                "graph": graph.model_dump(mode="json"),
                "projection_disposition": None,
            }
        )


def test_infer_algorithm_family_supports_functional_methods() -> None:
    assert infer_algorithm_family(DiscoveryMethod.ANM) is DiscoveryAlgorithmFamily.FUNCTIONAL
    assert (
        infer_algorithm_family(DiscoveryMethod.PAIRWISE_HEURISTIC)
        is DiscoveryAlgorithmFamily.FUNCTIONAL
    )


def test_graph_hypothesis_auto_produces_latent_bundle_from_structured_evidence() -> None:
    report = CausalDiscoveryReport(
        method="pc",
        graph=_graph(
            graph_type=GraphType.DAG,
            edges=[
                CausalEdge(src="W_anchor", dst="X", combined_confidence=0.9),
                CausalEdge(src="W_anchor", dst="Y", combined_confidence=0.9),
                CausalEdge(src="X", dst="Y", combined_confidence=0.8),
            ],
            nodes=["W_anchor", "X", "Y", "R1", "R2", "R3", "W", "Z"],
            discovery_method="pc",
        ),
        metadata={
            LATENT_CARDINALITY_EVIDENCE_KEY: LatentCardinalityEvidencePayload(
                model_class="ME-LiNGLaH-S",
                treatment_variable="X",
                outcome_variable="Y",
                inducing_environments=["region_a", "region_b"],
                latent_blocks=[
                    LatentBlockProposal(
                        latent_id="U_01",
                        block_size=1,
                        role=LatentCausalRole.CONFOUNDER,
                        status=LatentBlockStatus.PARTIAL,
                        graph_status=LatentGraphStatus.PARTIAL,
                        anchor_variables=["W_anchor"],
                        informative_environment_contrasts=["region_a_vs_region_b"],
                        evidence=LatentBlockEvidence(
                            gin_supported=True,
                            atomic_structure_supported=True,
                            shift_localized=True,
                            minimal_decomposition_supported=True,
                            role_rule_supported=False,
                            pure_child_count=2,
                            neighbor_count=3,
                            rank=1,
                        ),
                    )
                ],
            ).model_dump(mode="json"),
            "latent_separation_measurement": {
                "status": "passed",
                "tetrad_test": "single_signal_tetrad_passed",
                "invariance_test": "measurement_invariance_passed",
                "repeated_indicator_blocks": ["R_block"],
                "repeated_indicator_block_variables": {"R_block": ["R1", "R2", "R3"]},
            },
            "latent_separation_proxy": {
                "status": "passed",
                "bridge_test": "proximal_bridge_solved",
                "bridge_stability": "cross_environment_stable",
                "proxy_blocks": ["W", "Z"],
                "proxy_block_variables": {"W": ["W"], "Z": ["Z"]},
            },
            "latent_separation_environment": {
                "status": "passed",
                "residual_invariance": "post_calibration_residual_invariance_failed",
                "post_calibration_shift": "not_restored",
                "environments": ["region_a", "region_b"],
                "n_env": 2,
                "route_to_latent_aware_discovery": True,
            },
            "latent_separation_design": {
                "environments": ["region_a", "region_b"],
                "proxy_blocks": ["W", "Z"],
                "repeated_indicator_blocks": ["R_block"],
            },
        },
    )

    hypothesis = graph_hypothesis_from_report(report, hypothesis_id="pc_latent_auto")

    assert hypothesis.latent_discovery is not None
    assert hypothesis.latent_discovery.readiness_cap == "proof_only"
    assert hypothesis.latent_discovery.promotion_allowed is False
    assert hypothesis.latent_discovery.trust_level is LatentTrustLevel.CONDITIONAL
    assert hypothesis.latent_discovery.proposed_latent_nodes == [
        "U_01|block_size=1|role=confounder|status=identified"
    ]
    assert LATENT_CARDINALITY_EVIDENCE_KEY in hypothesis.latent_discovery.metadata
    assert LATENT_CARDINALITY_FAILURE_REASONS_KEY in hypothesis.latent_discovery.metadata
    assert hypothesis.latent_discovery.metadata[LATENT_CARDINALITY_FAILURE_REASONS_KEY] == []
    assert SEPARATION_DIAGNOSTIC_INPUTS_KEY in hypothesis.latent_discovery.metadata
    assert hypothesis.latent_discovery.metadata["separation_diagnostics"]["resolution_label"] == (
        "latent_confounding"
    )


def test_graph_hypothesis_keeps_cardinality_bundle_fail_closed_when_prerequisites_missing() -> None:
    report = CausalDiscoveryReport(
        method="pc",
        graph=_graph(
            graph_type=GraphType.DAG,
            edges=[CausalEdge(src="W_anchor", dst="Y", combined_confidence=0.9)],
            nodes=["W_anchor", "X", "Y"],
            discovery_method="pc",
        ),
        metadata={
            LATENT_CARDINALITY_EVIDENCE_KEY: LatentCardinalityEvidencePayload(
                model_class="ME-LiNGLaH-S",
                treatment_variable="X",
                outcome_variable="Y",
                inducing_environments=["region_a", "region_b"],
                latent_blocks=[
                    LatentBlockProposal(
                        latent_id="U_weak",
                        block_size=1,
                        role=LatentCausalRole.CONFOUNDER,
                        status=LatentBlockStatus.PARTIAL,
                        graph_status=LatentGraphStatus.PARTIAL,
                        anchor_variables=["W_anchor"],
                        informative_environment_contrasts=["region_a_vs_region_b"],
                        evidence=LatentBlockEvidence(
                            gin_supported=True,
                            atomic_structure_supported=True,
                            shift_localized=False,
                            minimal_decomposition_supported=True,
                            role_rule_supported=False,
                            pure_child_count=1,
                            neighbor_count=2,
                            rank=1,
                        ),
                    )
                ],
            ).model_dump(mode="json")
        },
    )

    hypothesis = graph_hypothesis_from_report(report, hypothesis_id="pc_latent_fail_closed")

    assert hypothesis.latent_discovery is not None
    assert hypothesis.latent_discovery.trust_level is LatentTrustLevel.RESEARCH
    assert hypothesis.latent_discovery.readiness_cap == "proof_only"
    assert hypothesis.latent_discovery.promotion_allowed is False
    assert hypothesis.latent_discovery.metadata[LATENT_CARDINALITY_FAILURE_REASONS_KEY] == [
        "U_weak:neighbors",
        "U_weak:pure_children",
        "U_weak:role_rule_supported",
        "U_weak:shift_localized",
    ]
    assert "latent_discovery_proof_only" in hypothesis.latent_discovery.no_promotion_reasons


def test_current_hypothesis_schema_cannot_use_historical_absence_adapter() -> None:
    graph = _graph(
        graph_type=GraphType.DAG,
        edges=[CausalEdge(src="X", dst="Y")],
        nodes=["X", "Y"],
    )
    with pytest.raises(ValueError, match="projection_disposition"):
        GraphHypothesis.model_validate(
            {
                "schema_version": "1.1",
                "hypothesis_id": "current-schema-missing-disposition",
                "algorithm_family": "constraint_based",
                "method": "pc",
                "graph": graph.model_dump(mode="json"),
            }
        )


def test_unversioned_hypothesis_uses_the_bounded_legacy_absence_adapter() -> None:
    graph = _graph(
        graph_type=GraphType.PAG,
        edges=[
            CausalEdge(
                src="X",
                dst="Y",
                mark_src=EdgeMark.CIRCLE,
                mark_dst=EdgeMark.CIRCLE,
            )
        ],
        nodes=["X", "Y"],
        discovery_method="fci",
    )
    legacy = GraphHypothesis.model_validate(
        {
            "hypothesis_id": "fci-unversioned",
            "algorithm_family": "constraint_based",
            "method": "fci",
            "graph": graph.model_dump(mode="json"),
        }
    )

    assert legacy.schema_version == "1.1"
    assert legacy.projection_disposition.status is GraphProjectionStatus.UNSUPPORTED
    assert legacy.graph_for_analysis() is None


def test_hypothesis_accessor_revalidates_a_copied_projection_disposition() -> None:
    graph = _graph(
        graph_type=GraphType.PAG,
        edges=[
            CausalEdge(
                src="X",
                dst="Y",
                mark_src=EdgeMark.CIRCLE,
                mark_dst=EdgeMark.CIRCLE,
            )
        ],
        nodes=["X", "Y"],
        discovery_method="fci",
    )
    refusal = graph_projection_disposition(
        graph,
        None,
        status=GraphProjectionStatus.UNSUPPORTED,
        reason_code="partial_graph_profile_not_admitted",
    )
    hypothesis = GraphHypothesis(
        hypothesis_id="fci-partial",
        algorithm_family=DiscoveryAlgorithmFamily.CONSTRAINT_BASED,
        method=DiscoveryMethod.FCI,
        graph=graph,
        projection_disposition=refusal,
    )
    forged_identity = refusal.model_copy(
        update={"status": GraphProjectionStatus.IDENTITY}
    )
    copied_hypothesis = hypothesis.model_copy(
        update={"projection_disposition": forged_identity}
    )

    with pytest.raises(ValueError):
        copied_hypothesis.graph_for_analysis()

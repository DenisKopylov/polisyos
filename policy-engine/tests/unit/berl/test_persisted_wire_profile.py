"""Persisted ExplanationBundle wire admission through the real selected CAS reader."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

import pytest

from polisyos.berl import load_explanation_bundle, persist_explanation_bundle
from polisyos.berl.contracts.explanation_bundle import (
    EXPLANATION_BUNDLE_SCHEMA_VERSION,
    AuditReport,
    BackgroundData,
    DisagreementReport,
    ExplanationAssumptions,
    ExplanationBundle,
    FeatureAttribution,
    FeatureContext,
    FeatureDependencePolicy,
    GroupAttribution,
    InfidelityReport,
    MethodExplanation,
    ModelContext,
    PerturbationDistribution,
    PredictionContext,
    RedundancyClusterModel,
    RedundancyContext,
    RedundancyEvidenceModel,
    StabilityReport,
    SupportCheck,
    ValidityReport,
)
from polisyos.berl.contracts.schema import (
    explanation_bundle_schema_id,
    generated_explanation_bundle_schema,
)
from polisyos.core.artifacts import ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.ir import get_json_artifact
from polisyos.ir.registry.refs import ExplanationBundleRef


def _bundle() -> ExplanationBundle:
    return ExplanationBundle(
        bundle_id="wire-profile",
        created_at=datetime(2026, 10, 28, tzinfo=UTC),
        model=ModelContext(model_id="m", model_hash="sha256:m", model_class="linear"),
        prediction=PredictionContext(
            prediction_id="p", row_id="r", output_name="score", output_scale="score", raw_score=1.0
        ),
        feature_context=FeatureContext(
            feature_values_ref="inline://features",
            feature_schema_version="features-v1",
            missingness_policy="model_native",
        ),
        assumptions=ExplanationAssumptions(
            explanation_question="local_prediction_drivers",
            perturbation_distribution=PerturbationDistribution(name="empirical", radius=0.25),
            feature_dependence_policy=FeatureDependencePolicy(
                primary="marginal",
                alternatives_tested=["conditional"],
                causal_claim_made=False,
            ),
            background_data=BackgroundData(
                dataset_ref="synthetic://background",
                n=2,
                sampling_policy="fixed_synthetic_rows",
            ),
        ),
        redundancy=RedundancyContext(
            clusters=[
                RedundancyClusterModel(
                    cluster_id="cluster-1",
                    features=["feature-a", "feature-b"],
                    evidence=RedundancyEvidenceModel(
                        max_abs_corr=0.5,
                        max_predictability_r2=0.25,
                        domain_rule="synthetic-only",
                    ),
                    reporting_policy="group_first",
                )
            ]
        ),
        methods=[
            MethodExplanation(
                method_id="synthetic-lime",
                requested_method_id="synthetic-lime",
                effective_method_id="synthetic-lime",
                fallback=False,
                fallback_reason=None,
                library="synthetic",
                library_version="1",
                scope="local",
                params={"seed": 7},
                assumptions={"fixture": "synthetic"},
                attributions=[
                    FeatureAttribution(
                        feature="feature-a",
                        value=0.25,
                        standard_error=0.01,
                        confidence_interval=(0.2, 0.3),
                    )
                ],
                group_attributions=[
                    GroupAttribution(
                        cluster_id="cluster-1",
                        value=0.5,
                        confidence_interval=(0.4, 0.6),
                    )
                ],
                infidelity=InfidelityReport(
                    loss="squared_reconstruction_error",
                    point_estimate=0.1,
                    upper_bound=0.2,
                    confidence=0.95,
                    n_eval_perturbations=10,
                    residual_cap=0.3,
                    bound_type="synthetic-heldout",
                    evaluation_split="heldout",
                ),
                stability=StabilityReport(
                    bootstrap_runs=5,
                    seed_policy="fixed-synthetic-seed",
                    max_rank_shift_top5=0,
                ),
            )
        ],
        disagreement=DisagreementReport(
            methods_compared=["synthetic-lime"],
            top_k=1,
            top_k_jaccard_median=1.0,
            kendall_tau_median=1.0,
            magnitude_l1_median=0.0,
            sign_conflict_features=[],
            redundancy_adjusted_conflicts=[],
            uncertainty_summary="synthetic fixture",
            flags=[],
        ),
        validity=ValidityReport(
            support_check=SupportCheck(
                ood_rate_eval_perturbations=0.0,
                constraint_violation_rate=0.0,
            ),
            use_restrictions=["synthetic fixture only"],
        ),
        audit=AuditReport(code_version="test"),
    )


def _store_payload(
    tmp_path, payload: dict[str, object]
) -> tuple[FileSystemCAS, ExplanationBundleRef]:
    store = FileSystemCAS(tmp_path / "cas")
    stored = store.put_json(
        payload,
        PutOptions(
            kind="scientist.explanation_bundle",
            media_type="application/json",
            schema=SchemaInfo(
                name=explanation_bundle_schema_id(),
                version=EXPLANATION_BUNDLE_SCHEMA_VERSION,
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    assert stored.manifest_profile_sha256 is not None
    return store, ExplanationBundleRef(
        artifact_id=stored.artifact_id,
        manifest_profile_sha256=stored.manifest_profile_sha256,
    )


def _writer_wire_payload(
    tmp_path,
) -> tuple[ExplanationBundle, FileSystemCAS, ExplanationBundleRef, dict[str, Any]]:
    bundle = _bundle()
    store = FileSystemCAS(tmp_path / "cas")
    reference = persist_explanation_bundle(store, bundle)
    payload = get_json_artifact(ensure_ir_artifact_store(store), reference)
    if not isinstance(payload, dict):
        raise AssertionError("BERL writer selected payload is not a JSON object")
    assert reference.manifest_profile_sha256 is not None
    assert load_explanation_bundle(FileSystemCAS(store.root), reference) == bundle
    return bundle, store, reference, payload


SchemaPath = tuple[str | int, ...]


_UNHANDLED_SCHEMA_NAVIGATION = {
    "allOf",
    "not",
    "if",
    "then",
    "else",
    "dependentRequired",
    "dependentSchemas",
    "patternProperties",
    "unevaluatedProperties",
    "additionalItems",
    "unevaluatedItems",
    "contains",
    "propertyNames",
}


def _assert_supported_schema_navigation(node: dict[str, Any]) -> None:
    unhandled = _UNHANDLED_SCHEMA_NAVIGATION.intersection(node)
    if unhandled:
        raise AssertionError(
            f"owner schema uses unsupported corpus navigation keywords: {sorted(unhandled)}"
        )


def _resolve_local_ref(schema_root: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
    ref = node.get("$ref")
    if ref is None:
        _assert_supported_schema_navigation(node)
        return node
    if not isinstance(ref, str) or not ref.startswith("#/$defs/"):
        raise AssertionError(f"unexpected non-local schema reference: {ref!r}")
    definition_name = ref.removeprefix("#/$defs/").replace("~1", "/").replace("~0", "~")
    definitions = schema_root.get("$defs")
    if not isinstance(definitions, dict):
        raise AssertionError("generated schema has no local definitions table")
    target = definitions.get(definition_name)
    if not isinstance(target, dict):
        raise AssertionError(f"unresolved generated schema reference: {ref}")
    siblings = {key: value for key, value in node.items() if key != "$ref"}
    resolved = {**target, **siblings}
    _assert_supported_schema_navigation(resolved)
    return resolved


def _schema_matches_value(schema_root: dict[str, Any], node: dict[str, Any], value: object) -> bool:
    node = _resolve_local_ref(schema_root, node)
    branches = node.get("anyOf", node.get("oneOf"))
    if branches is not None:
        if not isinstance(branches, list):
            raise AssertionError("generated schema union is not a list")
        return any(
            isinstance(branch, dict) and _schema_matches_value(schema_root, branch, value)
            for branch in branches
        )

    expected = node.get("type")
    expected_types = expected if isinstance(expected, list) else [expected]
    if expected is None:
        if "properties" in node:
            return isinstance(value, dict)
        if "items" in node or "prefixItems" in node:
            return isinstance(value, list)
        return True
    for type_name in expected_types:
        if type_name == "object" and isinstance(value, dict):
            return True
        if type_name == "array" and isinstance(value, list):
            return True
        if type_name == "string" and isinstance(value, str):
            return True
        if type_name == "boolean" and isinstance(value, bool):
            return True
        if type_name == "integer" and isinstance(value, int) and not isinstance(value, bool):
            return True
        if (
            type_name == "number"
            and isinstance(value, (int, float))
            and not isinstance(value, bool)
        ):
            return True
        if type_name == "null" and value is None:
            return True
    return False


def _schema_for_value(
    schema_root: dict[str, Any], node: dict[str, Any], value: object
) -> dict[str, Any]:
    node = _resolve_local_ref(schema_root, node)
    for union_key in ("anyOf", "oneOf"):
        branches = node.get(union_key)
        if branches is None:
            continue
        if not isinstance(branches, list):
            raise AssertionError(f"generated schema {union_key} is not a list")
        matches = [
            branch
            for branch in branches
            if isinstance(branch, dict) and _schema_matches_value(schema_root, branch, value)
        ]
        if len(matches) != 1:
            raise AssertionError(
                f"expected one {union_key} branch for {type(value).__name__}, found {len(matches)}"
            )
        return _schema_for_value(schema_root, matches[0], value)
    return node


def _collect_schema_witnesses(
    schema_root: dict[str, Any], payload: dict[str, Any]
) -> tuple[
    list[SchemaPath],
    list[tuple[SchemaPath, dict[str, Any]]],
    list[tuple[SchemaPath, str]],
    list[tuple[SchemaPath, bool, object]],
]:
    """Derive reachable required and optional paths from the owner schema."""

    required_paths: list[SchemaPath] = []
    strict_object_paths: list[tuple[SchemaPath, dict[str, Any]]] = []
    scalar_paths: list[tuple[SchemaPath, str]] = []
    optional_paths: list[tuple[SchemaPath, bool, object]] = []

    def visit(node: dict[str, Any], value: object, path: SchemaPath) -> None:
        selected = _schema_for_value(schema_root, node, value)
        value_type = selected.get("type")
        if (
            isinstance(value_type, str)
            and value_type in {"string", "number", "integer", "boolean"}
            and value is not None
        ):
            scalar_paths.append((path, value_type))
        if isinstance(value, dict):
            properties = selected.get("properties", {})
            required = selected.get("required", [])
            if not isinstance(properties, dict) or not isinstance(required, list):
                raise AssertionError(f"invalid generated object schema at {path!r}")
            if selected.get("additionalProperties") is False:
                strict_object_paths.append((path, selected))
            for name in required:
                if not isinstance(name, str):
                    raise AssertionError(f"non-string required field at {path!r}")
                if name not in value:
                    raise AssertionError(
                        f"positive fixture omits owner-required path {(*path, name)!r}"
                    )
                required_paths.append((*path, name))
            for name, child_value in value.items():
                child_schema = properties.get(name)
                if not isinstance(child_schema, dict):
                    if selected.get("additionalProperties") is False:
                        raise AssertionError(
                            f"positive fixture has an unowned field at {(*path, name)!r}"
                        )
                    continue
                if name not in required:
                    has_schema_default = "default" in child_schema
                    optional_paths.append(
                        ((*path, name), has_schema_default, child_schema.get("default"))
                    )
                visit(child_schema, child_value, (*path, name))
            return

        if isinstance(value, list):
            prefix_items = selected.get("prefixItems")
            item_schema = selected.get("items")
            if prefix_items is not None and not isinstance(prefix_items, list):
                raise AssertionError(f"generated prefixItems is not a list at {path!r}")
            for index, item in enumerate(value):
                if isinstance(prefix_items, list) and index < len(prefix_items):
                    element_schema = prefix_items[index]
                else:
                    element_schema = item_schema
                if not isinstance(element_schema, dict):
                    raise AssertionError(
                        f"instantiated array has no owner item schema at {(*path, index)!r}"
                    )
                visit(element_schema, item, (*path, index))

    visit(schema_root, payload, ())
    if not required_paths or not strict_object_paths or not scalar_paths or not optional_paths:
        raise AssertionError("the populated fixture did not reach the expected owner-schema corpus")
    return required_paths, strict_object_paths, scalar_paths, optional_paths


def _value_at_path(value: object, path: SchemaPath) -> object:
    current = value
    for part in path:
        if isinstance(current, dict) or (isinstance(current, list) and isinstance(part, int)):
            current = current[part]
        else:
            raise AssertionError(f"cannot resolve fixture path {path!r}")
    return current


def _parent_at_path(value: object, path: SchemaPath) -> tuple[object, str | int]:
    if not path:
        raise AssertionError("the root has no parent path")
    parent = _value_at_path(value, path[:-1])
    return parent, path[-1]


def _delete_at_path(value: dict[str, Any], path: SchemaPath) -> None:
    parent, leaf = _parent_at_path(value, path)
    if not isinstance(parent, dict) or not isinstance(leaf, str):
        raise AssertionError(f"required coordinate is not an object property: {path!r}")
    del parent[leaf]


def _set_at_path(value: dict[str, Any], path: SchemaPath, replacement: object) -> None:
    if not path:
        raise AssertionError("replace the root payload directly for an empty-object case")
    parent, leaf = _parent_at_path(value, path)
    if isinstance(parent, dict) or (isinstance(parent, list) and isinstance(leaf, int)):
        parent[leaf] = replacement
    else:
        raise AssertionError(f"cannot assign fixture path {path!r}")


def _assert_rejected_with_positive_restored(
    tmp_path,
    payload: dict[str, Any],
    expected_error: str,
    baseline_store: FileSystemCAS,
    baseline_reference: ExplanationBundleRef,
    baseline: ExplanationBundle,
    label: object,
) -> None:
    store, reference = _store_payload(tmp_path, payload)
    with pytest.raises(ValueError) as error:
        load_explanation_bundle(FileSystemCAS(store.root), reference)
    assert str(error.value) == expected_error, f"wrong rejection for {label!r}"
    assert (
        load_explanation_bundle(FileSystemCAS(baseline_store.root), baseline_reference) == baseline
    ), f"baseline selected positive failed after {label!r}"


def _wrong_scalar(type_name: str) -> object:
    return {
        "string": True,
        "number": "not-a-number",
        "integer": 1.25,
        "boolean": "not-a-boolean",
    }[type_name]


def test_writer_output_reopens_from_fresh_selected_reader(tmp_path) -> None:
    root = tmp_path / "cas"
    reference = persist_explanation_bundle(FileSystemCAS(root), _bundle())
    assert load_explanation_bundle(FileSystemCAS(root), reference) == _bundle()


@pytest.mark.parametrize("wire_value", ["1.25", True])
def test_reader_refuses_coercible_non_numeric_raw_score(tmp_path, wire_value: object) -> None:
    bundle, baseline_store, baseline_reference, payload = _writer_wire_payload(tmp_path)
    payload = deepcopy(payload)
    payload["prediction"]["raw_score"] = wire_value
    store, reference = _store_payload(tmp_path, payload)

    with pytest.raises(ValueError, match="explanation_bundle_persisted_payload_invalid"):
        load_explanation_bundle(FileSystemCAS(store.root), reference)
    assert load_explanation_bundle(FileSystemCAS(baseline_store.root), baseline_reference) == bundle


def test_reader_rejects_every_reachable_owner_required_field_deletion(tmp_path) -> None:
    """Delete each instantiated required path derived from the owner schema."""

    bundle, baseline_store, baseline_reference, payload = _writer_wire_payload(tmp_path)
    schema = generated_explanation_bundle_schema()
    required_paths, strict_object_paths, scalar_paths, optional_paths = _collect_schema_witnesses(
        schema, payload
    )
    assert strict_object_paths and scalar_paths and optional_paths

    for path in required_paths:
        mutated = deepcopy(payload)
        _delete_at_path(mutated, path)
        expected_error = (
            "explanation_bundle_persisted_field_missing"
            if len(path) == 1
            else "explanation_bundle_persisted_payload_invalid"
        )
        _assert_rejected_with_positive_restored(
            tmp_path,
            mutated,
            expected_error,
            baseline_store,
            baseline_reference,
            bundle,
            ("required", path),
        )


def test_reader_rejects_empty_required_objects_and_nested_extras(tmp_path) -> None:
    """Exercise required object shape and extra-forbid across instantiated owners."""

    bundle, baseline_store, baseline_reference, payload = _writer_wire_payload(tmp_path)
    schema = generated_explanation_bundle_schema()
    _, strict_object_paths, _, _ = _collect_schema_witnesses(schema, payload)

    empty_required_paths = [
        path for path, object_schema in strict_object_paths if object_schema.get("required")
    ]
    assert empty_required_paths
    for path in empty_required_paths:
        mutated = deepcopy(payload)
        if path:
            _set_at_path(mutated, path, {})
            expected_error = "explanation_bundle_persisted_payload_invalid"
        else:
            mutated = {}
            expected_error = "explanation_bundle_persisted_field_missing"
        _assert_rejected_with_positive_restored(
            tmp_path,
            mutated,
            expected_error,
            baseline_store,
            baseline_reference,
            bundle,
            ("empty-object", path),
        )

    for path, _object_schema in strict_object_paths:
        mutated = deepcopy(payload)
        target = _value_at_path(mutated, path)
        if not isinstance(target, dict):
            raise AssertionError(f"owner object path is not an object: {path!r}")
        target["__c124_unowned_extra__"] = "synthetic"
        _assert_rejected_with_positive_restored(
            tmp_path,
            mutated,
            "explanation_bundle_persisted_payload_invalid",
            baseline_store,
            baseline_reference,
            bundle,
            ("extra", path),
        )


def test_reader_rejects_wrong_scalar_types_and_preserves_optional_defaults(tmp_path) -> None:
    """Select wrong-type probes by owner schema and keep schema-optional defaults valid."""

    bundle, baseline_store, baseline_reference, payload = _writer_wire_payload(tmp_path)
    schema = generated_explanation_bundle_schema()
    _, _, scalar_paths, optional_paths = _collect_schema_witnesses(schema, payload)
    assert any(
        "confidence_interval" in path and isinstance(path[-1], int)
        for path, _type_name in scalar_paths
    ), "tuple prefixItems confidence intervals were not traversed"

    for path, type_name in scalar_paths:
        mutated = deepcopy(payload)
        _set_at_path(mutated, path, _wrong_scalar(type_name))
        _assert_rejected_with_positive_restored(
            tmp_path,
            mutated,
            "explanation_bundle_persisted_payload_invalid",
            baseline_store,
            baseline_reference,
            bundle,
            ("wrong-scalar", type_name, path),
        )

    for path, has_schema_default, schema_default in optional_paths:
        mutated = deepcopy(payload)
        _delete_at_path(mutated, path)
        store, reference = _store_payload(tmp_path, mutated)
        reopened = load_explanation_bundle(FileSystemCAS(store.root), reference)
        reopened_wire = reopened.model_dump(mode="json", round_trip=True)
        restored_value = _value_at_path(reopened_wire, path)
        if has_schema_default:
            assert restored_value == schema_default, (
                f"owner schema default was not restored at {path!r}"
            )
        assert (
            load_explanation_bundle(FileSystemCAS(baseline_store.root), baseline_reference)
            == bundle
        ), f"baseline selected positive failed after default omission {path!r}"

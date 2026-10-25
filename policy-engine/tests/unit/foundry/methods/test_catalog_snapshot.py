from __future__ import annotations

import copy
import importlib.util
import subprocess
import tomllib
from dataclasses import replace
from pathlib import Path

import pytest

from polisyos.core.artifacts import resolve_manifest_by_profile
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.components import (
    DeclaredBuiltinLoader,
    DiscoveryDeclaredBuiltinLoaderIdentity,
)
from polisyos.core.components.discovery import _component_discovery_manifest_id
from polisyos.core.contracts.execution_plan import MethodCatalogSnapshot
from polisyos.foundry.extensions.discovery import (
    BUILTIN_LOADER,
    ENTRY_POINT_GROUP,
    _selected_foundry_builtin_loader_spec,
    discover_foundry_method_components,
)
from polisyos.foundry.extensions.registry import bootstrap_foundry_method_registry
from polisyos.foundry.methods.base import MethodMetadata
from polisyos.foundry.methods.catalog import ensure_all_methods_registered
from polisyos.foundry.methods.catalog import snapshot as snapshot_module
from polisyos.foundry.methods.catalog.bayesian.regression import (
    BayesianLinearRegressionEstimator,
)
from polisyos.foundry.methods.catalog.dependency_authority import (
    AbsoluteRequestPath,
    MethodCatalogDependencyAuthorityRequest,
    validate_negative_only_dependency_authority_abi,
)
from polisyos.foundry.methods.catalog.snapshot import (
    MethodCatalogDiscoveryProvenanceError,
    build_method_capability_matrix,
    build_method_catalog_provenance_manifest,
    build_method_catalog_runtime_identity,
    build_method_catalog_snapshot,
    method_catalog_provenance_id,
    persist_method_catalog_snapshot,
)
from polisyos.foundry.methods.selection import reachable_value_method_fqns
from polisyos.foundry.methods.selection.registry import MethodRegistry, registry_scope

_Y0_INSTALLED = importlib.util.find_spec("y0") is not None


def test_persist_method_catalog_snapshot_returns_exact_write_selected_profile(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    snapshot = MethodCatalogSnapshot(snapshot_id="catalog_selected_profile")

    ref = persist_method_catalog_snapshot(store, snapshot)

    assert ref.manifest_profile_sha256 is not None
    manifest = resolve_manifest_by_profile(store, ref.artifact_id, ref.manifest_profile_sha256)
    assert manifest.kind == "foundry.method_catalog_snapshot"
    assert manifest.artifact_schema is not None
    assert manifest.artifact_schema.name == "polisyos.core.MethodCatalogSnapshot"

    class MalformedSelectedWriter:
        def put_json(self, obj, opts, canon_spec=None, *, return_selected_profile=False):
            del obj, opts, canon_spec
            assert return_selected_profile is True
            return ref.model_copy(update={"manifest_profile_sha256": None})

    with pytest.raises(
        ValueError,
        match="method_catalog_snapshot_selected_write_ref_incomplete",
    ):
        persist_method_catalog_snapshot(MalformedSelectedWriter(), snapshot)  # type: ignore[arg-type]


def test_persist_method_catalog_snapshot_refuses_writer_without_selected_profile_api(
    tmp_path: Path,
) -> None:
    snapshot = MethodCatalogSnapshot(snapshot_id="catalog_profileless_writer")

    class ProfilelessWriter:
        def put_json(self, obj, opts, canon_spec=None):
            del obj, opts, canon_spec
            pytest.fail("selected-profile writer support must be checked before writing")

    with pytest.raises(
        NotImplementedError,
        match="artifact_store_return_selected_profile_unsupported",
    ):
        persist_method_catalog_snapshot(ProfilelessWriter(), snapshot)  # type: ignore[arg-type]


@pytest.fixture(autouse=True)
def _isolate_polisyos_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep catalog caches out of the appointed hermetic tooling home."""

    monkeypatch.setenv("POLISYOS_CACHE_HOME", (tmp_path / "polisyos-cache").as_posix())


def _dependency_request() -> MethodCatalogDependencyAuthorityRequest:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return MethodCatalogDependencyAuthorityRequest(
        authority_purpose="n8_method_catalog_reconstruction",
        expected_source_freeze_commit=head,
        production_data_root=AbsoluteRequestPath(value=Path("/tmp/production-data")),
        environment_root=AbsoluteRequestPath(value=Path("/tmp/environment")),
    )


def test_governed_snapshot_consumes_supplied_builtin_provenance_without_rediscovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with registry_scope() as registry:
        report = bootstrap_foundry_method_registry(
            registry,
            include_builtins=True,
            include_entry_points=False,
            include_dev_scan=False,
            require_bound_discovery_manifest=True,
        )
        monkeypatch.setattr(
            "polisyos.foundry.methods.catalog.snapshot.ensure_all_methods_registered",
            lambda _registry: pytest.fail("governed snapshot reran ambient discovery"),
        )

        snapshot = build_method_catalog_snapshot(
            registry=registry,
            registry_report=report,
            require_bound_discovery=True,
        )

    assert report.discovery_manifest is not None
    assert report.discovery_manifest.is_bound is True
    assert tuple(entry.fqn for entry in snapshot.entries) == report.registry_fqns


def test_value_method_denominator_consumes_controlled_snapshot_without_rediscovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with registry_scope() as registry:
        report = bootstrap_foundry_method_registry(
            registry,
            include_builtins=True,
            include_entry_points=False,
            include_dev_scan=False,
            require_bound_discovery_manifest=True,
        )
        snapshot = build_method_catalog_snapshot(
            registry=registry,
            registry_report=report,
            require_bound_discovery=True,
        )
        monkeypatch.setattr(
            "polisyos.foundry.methods.catalog.ensure_all_methods_registered",
            lambda _registry: pytest.fail("controlled denominator reran ambient discovery"),
        )

        methods = reachable_value_method_fqns(
            registry=registry,
            catalog_snapshot=snapshot,
        )

    assert methods
    assert set(methods) < set(report.registry_fqns)


def test_governed_snapshot_fails_closed_without_discovery_provenance() -> None:
    with (
        registry_scope() as registry,
        pytest.raises(
            MethodCatalogDiscoveryProvenanceError,
            match="catalog_discovery_provenance_missing",
        ),
    ):
        build_method_catalog_snapshot(
            registry=registry,
            require_bound_discovery=True,
        )


def test_governed_snapshot_rejects_registry_mutation_after_admission() -> None:
    with registry_scope() as registry:
        report = bootstrap_foundry_method_registry(
            registry,
            include_builtins=True,
            include_entry_points=False,
            include_dev_scan=False,
            require_bound_discovery_manifest=True,
        )
        registry.unregister(report.registry_fqns[0])

        with pytest.raises(
            MethodCatalogDiscoveryProvenanceError,
            match="catalog_registry_admission_membership_mismatch",
        ):
            build_method_catalog_snapshot(
                registry=registry,
                registry_report=report,
                require_bound_discovery=True,
            )


def test_governed_snapshot_rejects_same_fqn_override_after_admission() -> None:
    with registry_scope() as registry:
        report = bootstrap_foundry_method_registry(
            registry,
            include_builtins=True,
            include_entry_points=False,
            include_dev_scan=False,
            require_bound_discovery_manifest=True,
        )
        original = registry.get(report.registry_fqns[0])

        class AmbientOverride:
            signature = original.signature
            metadata = replace(
                original.metadata,
                description="ambient same-FQN override with markers intact",
            )

            @staticmethod
            def pure_step(state, params):
                return original.pure_step(state, params)

        registry.register(AmbientOverride, override=True)

        with pytest.raises(
            MethodCatalogDiscoveryProvenanceError,
            match="catalog_registry_admission_content_mismatch",
        ):
            build_method_catalog_snapshot(
                registry=registry,
                registry_report=report,
                require_bound_discovery=True,
            )


def test_governed_snapshot_rejects_same_fqn_override_during_build(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with registry_scope() as registry:
        report = bootstrap_foundry_method_registry(
            registry,
            include_builtins=True,
            include_entry_points=False,
            include_dev_scan=False,
            require_bound_discovery_manifest=True,
        )
        target_fqn = report.registry_fqns[0]
        original = registry.get(target_fqn)
        from polisyos.foundry.methods.catalog import snapshot as snapshot_module

        real_available_backends = snapshot_module._available_execution_backends

        def _override_after_admission() -> set[str]:
            class MidBuildOverride:
                signature = original.signature
                metadata = replace(
                    original.metadata,
                    description="same-FQN override injected after admission",
                )

                @staticmethod
                def pure_step(state, params):
                    return original.pure_step(state, params)

            registry.register(MidBuildOverride, override=True)
            return real_available_backends()

        monkeypatch.setattr(
            snapshot_module,
            "_available_execution_backends",
            _override_after_admission,
        )

        with pytest.raises(
            MethodCatalogDiscoveryProvenanceError,
            match="catalog_registry_admission_content_mismatch",
        ):
            build_method_catalog_snapshot(
                registry=registry,
                registry_report=report,
                require_bound_discovery=True,
            )


def test_catalog_provenance_rejects_false_ambient_policy_and_binds_registry() -> None:
    with registry_scope() as registry:
        report = bootstrap_foundry_method_registry(
            registry,
            include_builtins=True,
            include_entry_points=False,
            include_dev_scan=False,
            require_bound_discovery_manifest=True,
        )
        snapshot = build_method_catalog_snapshot(
            registry=registry,
            registry_report=report,
            require_bound_discovery=True,
        )

    assert report.discovery_manifest is not None
    with pytest.raises(
        MethodCatalogDiscoveryProvenanceError,
        match="catalog_ambient_source_policy_mismatch",
    ):
        snapshot_module._build_candidate_method_catalog_provenance_manifest(
            snapshot,
            registry_report=report,
            ambient_manifest=report.discovery_manifest,
        )

    ambient_report = discover_foundry_method_components(
        include_builtins=False,
        include_entry_points=True,
        include_dev_scan=True,
    )
    assert ambient_report.manifest is not None
    provenance = snapshot_module._build_candidate_method_catalog_provenance_manifest(
        snapshot,
        registry_report=report,
        ambient_manifest=ambient_report.manifest,
    )

    default_loader_target = report.discovery_manifest.builtin_loaders[0]
    assert provenance["schema_version"] == "policyos.method_catalog_provenance_manifest.v2"
    assert provenance["governed_discovery"]["declared_builtin_loaders"] == [
        {
            "name": default_loader_target,
            "target": default_loader_target,
            "group": ENTRY_POINT_GROUP,
        }
    ]
    assert provenance["ambient_discovery"]["declared_builtin_loaders"] == []
    assert provenance["governed_discovery"]["registry_binding_sha256"] == (
        report.registry_binding_sha256
    )
    assert provenance["provenance_id"] == method_catalog_provenance_id(provenance)


def test_foundry_default_loader_selection_matches_extension_point_config() -> None:
    architecture_root = Path(__file__).resolve().parents[4]
    extension_points = tomllib.loads(
        (architecture_root / "architecture/extension_points.toml").read_text()
    )["extension_point"]
    configured = next(row for row in extension_points if row["name"] == "polisyos.foundry_methods")

    selected = _selected_foundry_builtin_loader_spec()

    assert isinstance(BUILTIN_LOADER, tuple)
    assert configured["entry_point_group"] == ENTRY_POINT_GROUP
    assert BUILTIN_LOADER[0] == configured["builtin_loader"]
    assert selected == DeclaredBuiltinLoader(
        target=configured["builtin_loader"],
        group=configured["entry_point_group"],
    )


def test_default_foundry_builtin_identity_flows_into_catalog_provenance() -> None:
    assert isinstance(BUILTIN_LOADER, tuple)
    assert callable(BUILTIN_LOADER[1])
    target = BUILTIN_LOADER[0]

    with registry_scope() as registry:
        report = bootstrap_foundry_method_registry(
            registry,
            include_builtins=True,
            include_entry_points=False,
            include_dev_scan=False,
            require_bound_discovery_manifest=True,
        )
        snapshot = build_method_catalog_snapshot(
            registry=registry,
            registry_report=report,
            require_bound_discovery=True,
        )
    ambient_report = discover_foundry_method_components(
        include_builtins=False,
        include_entry_points=True,
        include_dev_scan=True,
    )
    assert report.discovery_manifest is not None
    assert ambient_report.manifest is not None
    assert report.discovery_manifest.builtin_loaders == (target,)
    assert report.discovery_manifest.declared_builtin_loaders == (
        DiscoveryDeclaredBuiltinLoaderIdentity(
            name=target,
            target=target,
            group=ENTRY_POINT_GROUP,
        ),
    )

    provenance = snapshot_module._build_candidate_method_catalog_provenance_manifest(
        snapshot,
        registry_report=report,
        ambient_manifest=ambient_report.manifest,
    )

    assert provenance["schema_version"] == "policyos.method_catalog_provenance_manifest.v2"
    assert provenance["governed_discovery"]["declared_builtin_loaders"] == [
        {"name": target, "target": target, "group": ENTRY_POINT_GROUP}
    ]
    assert provenance["ambient_discovery"]["declared_builtin_loaders"] == []
    assert provenance["provenance_id"] == method_catalog_provenance_id(provenance)

    original_manifest = report.discovery_manifest
    original_declaration = original_manifest.declared_builtin_loaders[0]
    mutations = (
        replace(original_declaration, name=original_declaration.name + ":altered"),
        replace(original_declaration, target=original_declaration.target + ":altered"),
        replace(original_declaration, group=original_declaration.group + ":altered"),
        None,
    )
    for changed_declaration in mutations:
        changed_rows = () if changed_declaration is None else (changed_declaration,)
        changed_manifest = replace(
            original_manifest,
            declared_builtin_loaders=changed_rows,
        )
        changed_manifest = replace(
            changed_manifest,
            manifest_id=_component_discovery_manifest_id(changed_manifest.content_payload()),
        )
        changed_report = replace(report, discovery_manifest=changed_manifest)

        assert changed_manifest.builtin_loaders == original_manifest.builtin_loaders
        assert changed_manifest.components == original_manifest.components
        assert changed_manifest.manifest_id != original_manifest.manifest_id
        with pytest.raises(
            MethodCatalogDiscoveryProvenanceError,
            match="catalog_governed_declared_builtin_loader_identity_mismatch",
        ):
            snapshot_module._build_candidate_method_catalog_provenance_manifest(
                snapshot,
                registry_report=changed_report,
                ambient_manifest=ambient_report.manifest,
            )


def test_replaced_foundry_builtin_loader_keeps_callable_tuple_compatibility(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.foundry.extensions import discovery as discovery_module

    original_loader = discovery_module.BUILTIN_LOADER
    equal_copy = (original_loader[0], original_loader[1])
    assert equal_copy == original_loader
    assert equal_copy is not original_loader
    monkeypatch.setattr(discovery_module, "BUILTIN_LOADER", equal_copy)
    assert _selected_foundry_builtin_loader_spec() is equal_copy

    calls: list[str] = []

    def empty_loader() -> tuple[object, ...]:
        calls.append("called")
        return ()

    target = "tests.unit.foundry.methods.test_catalog_snapshot:empty_loader"
    explicit_replacement = (target, empty_loader)
    monkeypatch.setattr(discovery_module, "BUILTIN_LOADER", explicit_replacement)
    assert _selected_foundry_builtin_loader_spec() is explicit_replacement

    with registry_scope() as registry:
        report = bootstrap_foundry_method_registry(
            registry,
            include_builtins=True,
            include_entry_points=False,
            include_dev_scan=False,
            require_bound_discovery_manifest=True,
        )
        snapshot = build_method_catalog_snapshot(
            registry=registry,
            registry_report=report,
            require_bound_discovery=True,
        )

    assert calls == ["called"]
    assert report.discovery_manifest is not None
    assert report.discovery_manifest.schema_version == ("policyos.component_discovery_manifest.v1")
    assert report.discovery_manifest.builtin_loaders == (target,)
    assert report.discovery_manifest.declared_builtin_loaders == ()

    ambient_report = discover_foundry_method_components(
        include_builtins=False,
        include_entry_points=True,
        include_dev_scan=True,
    )
    assert ambient_report.manifest is not None
    provenance = snapshot_module._build_candidate_method_catalog_provenance_manifest(
        snapshot,
        registry_report=report,
        ambient_manifest=ambient_report.manifest,
    )
    assert provenance["schema_version"] == "policyos.method_catalog_provenance_manifest.v1"
    assert "declared_builtin_loaders" not in provenance["governed_discovery"]


def test_governed_provenance_projection_keeps_ambient_custody_non_decisive() -> None:
    """Ambient observation drift must move raw custody but not governed identity."""

    with registry_scope() as registry:
        report = bootstrap_foundry_method_registry(
            registry,
            include_builtins=True,
            include_entry_points=False,
            include_dev_scan=False,
            require_bound_discovery_manifest=True,
        )
        snapshot = build_method_catalog_snapshot(
            registry=registry,
            registry_report=report,
            require_bound_discovery=True,
        )

    ambient_report = discover_foundry_method_components(
        include_builtins=False,
        include_entry_points=True,
        include_dev_scan=True,
    )
    assert ambient_report.manifest is not None
    recorded = snapshot_module._build_candidate_method_catalog_provenance_manifest(
        snapshot,
        registry_report=report,
        ambient_manifest=ambient_report.manifest,
    )
    changed = copy.deepcopy(recorded)
    changed["ambient_discovery"]["manifest_id"] = "component_discovery_manifest_ambient_other"
    changed["ambient_discovery"]["component_count"] += 1
    changed["ambient_discovery"]["unbound_inputs"].append(
        "discovery_error:entry_point:example.weighted_average:ModuleNotFoundError"
    )
    changed["ambient_discovery"]["admission"]["status"] = "declared_not_admitted"
    membership = next(
        row
        for row in changed["predicate_provenance"]
        if row["predicate"] == "ambient.discovered_component_membership"
    )
    membership["classification"] = (
        "not_established" if membership["classification"] == "recomputed" else "recomputed"
    )
    changed["provenance_id"] = method_catalog_provenance_id(changed)

    assert recorded["provenance_id"] != changed["provenance_id"]
    assert snapshot_module.method_catalog_governed_provenance_projection(
        recorded
    ) == snapshot_module.method_catalog_governed_provenance_projection(changed)
    assert snapshot_module.method_catalog_governed_provenance_id(
        recorded
    ) == snapshot_module.method_catalog_governed_provenance_id(changed)
    assert changed["ambient_discovery"]["unbound_inputs"]


@pytest.mark.parametrize(
    ("mutation", "expected_error"),
    (
        ("missing_parent_admission", "catalog_ambient_input_not_quarantined"),
        ("governing_parent_admission", "catalog_ambient_input_not_quarantined"),
        ("contradictory_predicate_admission", "catalog_predicate_provenance_invalid"),
    ),
)
def test_governed_provenance_projection_fails_closed_on_invalid_admission(
    mutation: str,
    expected_error: str,
) -> None:
    """Only a complete structural quarantine may remove ambient observations."""

    with registry_scope() as registry:
        report = bootstrap_foundry_method_registry(
            registry,
            include_builtins=True,
            include_entry_points=False,
            include_dev_scan=False,
            require_bound_discovery_manifest=True,
        )
        snapshot = build_method_catalog_snapshot(
            registry=registry,
            registry_report=report,
            require_bound_discovery=True,
        )

    ambient_report = discover_foundry_method_components(
        include_builtins=False,
        include_entry_points=True,
        include_dev_scan=True,
    )
    assert ambient_report.manifest is not None
    provenance = snapshot_module._build_candidate_method_catalog_provenance_manifest(
        snapshot,
        registry_report=report,
        ambient_manifest=ambient_report.manifest,
    )
    if mutation == "missing_parent_admission":
        provenance["ambient_discovery"].pop("admission")
    elif mutation == "governing_parent_admission":
        provenance["ambient_discovery"]["admission"]["included_in_governed_denominator"] = True
    else:
        predicate = next(
            row
            for row in provenance["predicate_provenance"]
            if row["predicate"] == "ambient.discovered_component_membership"
        )
        predicate["decisive"] = True

    with pytest.raises(MethodCatalogDiscoveryProvenanceError, match=expected_error):
        snapshot_module.method_catalog_governed_provenance_projection(provenance)


def test_catalog_runtime_identity_names_packages_and_backend_fingerprints() -> None:
    with registry_scope() as registry:
        report = bootstrap_foundry_method_registry(
            registry,
            include_builtins=True,
            include_entry_points=False,
            include_dev_scan=False,
            require_bound_discovery_manifest=True,
        )
        snapshot = build_method_catalog_snapshot(
            registry=registry,
            registry_report=report,
            require_bound_discovery=True,
        )

    identity = snapshot_module._build_candidate_method_catalog_runtime_identity(snapshot)

    assert identity["schema_version"] == "policyos.method_catalog_runtime_identity.v1"
    assert identity["identity_id"].startswith("method_catalog_runtime_identity_")
    assert identity["entry_runtime_binding_count"] == len(snapshot.entries)
    assert identity["backend_fingerprints"]
    runtime_packages = {row["name"]: row for row in identity["runtime_packages"]}
    assert runtime_packages["python"]["version"]
    assert runtime_packages["policy-engine"]["version"]
    expected_fingerprints = {
        (
            str(entry.capability_matrix["runtime_posture"]["backend"]),
            str(entry.capability_matrix["runtime_posture"]["fingerprint"]),
        )
        for entry in snapshot.entries
    }
    assert {
        (str(row["backend"]), str(row["fingerprint"])) for row in identity["backend_fingerprints"]
    } == expected_fingerprints


def test_catalog_runtime_identity_fails_closed_without_policy_engine_package(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with registry_scope() as registry:
        report = bootstrap_foundry_method_registry(
            registry,
            include_builtins=True,
            include_entry_points=False,
            include_dev_scan=False,
            require_bound_discovery_manifest=True,
        )
        snapshot = build_method_catalog_snapshot(
            registry=registry,
            registry_report=report,
            require_bound_discovery=True,
        )
    monkeypatch.setattr(
        "polisyos.foundry.methods.catalog.snapshot.safe_version",
        lambda package_name: None if package_name == "policy-engine" else "test-version",
    )

    with pytest.raises(
        MethodCatalogDiscoveryProvenanceError,
        match="catalog_runtime_package_identity_missing:policy-engine",
    ):
        snapshot_module._build_candidate_method_catalog_runtime_identity(snapshot)


def test_public_catalog_builders_and_all_callers_are_inside_negative_graph() -> None:
    validate_negative_only_dependency_authority_abi()
    request = _dependency_request()
    sentinel = object()

    runtime = build_method_catalog_runtime_identity(
        sentinel,  # type: ignore[arg-type]
        dependency_authority_request=request,
    )
    provenance = build_method_catalog_provenance_manifest(
        sentinel,  # type: ignore[arg-type]
        registry_report=sentinel,  # type: ignore[arg-type]
        ambient_manifest=sentinel,  # type: ignore[arg-type]
        dependency_authority_request=request,
    )

    assert runtime.status in {"rejected", "not_established"}
    assert provenance.status in {"rejected", "not_established"}
    assert runtime == provenance


def test_method_catalog_snapshot_contains_stable_entries() -> None:
    ensure_all_methods_registered()
    registered_fqns = tuple(
        sorted(entry.fqn for entry in MethodRegistry.get_instance().snapshot().entries())
    )
    first = build_method_catalog_snapshot(run_id="R_catalog")
    second = build_method_catalog_snapshot(run_id="R_catalog")

    first_fqns = [entry.fqn for entry in first.entries]
    second_fqns = [entry.fqn for entry in second.entries]

    assert first_fqns
    assert tuple(first_fqns) == registered_fqns
    assert first_fqns == second_fqns
    assert first.snapshot_id == second.snapshot_id
    assert first.schema_version == "2.0"
    first_value_capable = {
        entry.fqn
        for entry in first.entries
        if entry.capability_matrix.get("value_projection_contracts")
    }
    second_value_capable = {
        entry.fqn
        for entry in second.entries
        if entry.capability_matrix.get("value_projection_contracts")
    }
    assert len(first.entries) >= 382
    assert first_value_capable == second_value_capable
    assert len(first_value_capable) == 60


def test_value_projection_and_joint_simulation_output_axes_compose() -> None:
    class _ComposedOutputMethod:
        signature = replace(
            BayesianLinearRegressionEstimator.signature,
            name="composed_output_axes",
            namespace="tests.catalog",
        )
        metadata = MethodMetadata(
            description="Prove independent output-contract axes compose.",
            assumptions={
                "joint_simulation_output_shape": "time_series_trajectory",
                "joint_simulation_equilibrium_semantics": "dynamic_SCM",
            },
        )

        @staticmethod
        def pure_step(state, params):
            del params
            return state

    with registry_scope() as registry:
        registry.register(_ComposedOutputMethod)
        snapshot = build_method_catalog_snapshot(registry=registry)
        entry = next(
            item for item in snapshot.entries if item.fqn == _ComposedOutputMethod.signature.fqn
        )

    assert entry.capability_matrix["value_projection_contracts"]
    assert "joint_simulation_output_shape" in entry.assumptions
    assert "joint_simulation_equilibrium_semantics" in entry.assumptions
    assert (
        _ComposedOutputMethod.metadata.assumptions["joint_simulation_output_shape"]
        == "time_series_trajectory"
    )
    assert (
        _ComposedOutputMethod.metadata.assumptions["joint_simulation_equilibrium_semantics"]
        == "dynamic_SCM"
    )


@pytest.mark.skipif(
    _Y0_INSTALLED,
    reason="y0 is installed — symbolic_identify reports causal_available=True",
)
def test_method_catalog_snapshot_carries_causal_capability_posture() -> None:
    ensure_all_methods_registered()
    snapshot = build_method_catalog_snapshot(run_id="R_catalog")

    assert snapshot.causal_capability_hash
    assert snapshot.causal_runtime_posture

    symbolic_entry = next(
        entry for entry in snapshot.entries if "causal.transport.symbolic_identify@" in entry.fqn
    )
    assert symbolic_entry.causal_capability_requirements
    assert symbolic_entry.causal_available is False
    assert symbolic_entry.causal_disabled_reasons


def test_method_catalog_snapshot_includes_non_causal_families() -> None:
    ensure_all_methods_registered()
    snapshot = build_method_catalog_snapshot(run_id="R_catalog")

    fqns = {entry.fqn for entry in snapshot.entries}
    assert "econometrics.panel.fixed_effects@1.0.0" in fqns
    assert "econometrics.panel.difference_gmm@1.0.0" in fqns
    assert "econometrics.panel.system_gmm@1.0.0" in fqns
    assert "econometrics.timeseries.vecm@1.0.0" in fqns
    assert "optimization.linear.resource_lp@1.0.0" in fqns
    assert "optimization.integer.budget_milp@1.0.0" in fqns
    assert "optimization.io.leontief_io@1.0.0" in fqns
    assert "optimization.dynamic.dynamic_programming@1.0.0" in fqns
    assert "ml.regression.elastic_net@1.0.0" in fqns
    assert "ml.regression.gaussian_process@1.0.0" in fqns
    assert "ml.deep.tabular_transformer@1.0.0" in fqns
    assert "ml.deep.ft_transformer@1.0.0" in fqns
    assert "ml.deep.tabnet@1.0.0" in fqns
    assert "ml.graph.graph_conv@1.0.0" in fqns
    assert "ml.self_supervised.masked_autoencoder@1.0.0" in fqns
    assert "microsim.static.static_microsim@1.0.0" in fqns
    assert "microsim.policy.tax_benefit_calculator@1.0.0" in fqns
    assert "spatial.autocorrelation.moran_i@1.0.0" in fqns
    assert "network.community.community_detection@1.0.0" in fqns
    assert "bayesian.regression.linear_regression@1.0.0" in fqns
    assert "bayesian.timeseries.autoregression@1.0.0" in fqns
    assert "bayesian.regression.hierarchical@1.0.0" in fqns
    assert "bayesian.sampling.hmc@1.0.0" in fqns
    assert "bayesian.sampling.nuts@1.0.0" in fqns
    assert "bayesian.nonparametric.gaussian_mixture@1.0.0" in fqns
    assert "bayesian.nonparametric.dirichlet_process_mixture@1.0.0" in fqns
    assert "distributional.inequality.atkinson@1.0.0" in fqns
    assert "survey.weighting.horvitz_thompson@1.0.0" in fqns
    assert "forecasting.univariate.exponential_smoothing@1.0.0" in fqns
    assert "validation.probabilistic.normal_scores@1.0.0" in fqns
    assert "sensitivity.global.sobol_first_order@1.0.0" in fqns
    assert "spatial.interpolation.gaussian_process_kriging@1.0.0" in fqns
    assert "spatial.interpolation.idw@1.0.0" in fqns
    assert "spatial.panel.slx@1.0.0" in fqns
    assert "spatial.panel.sarar@1.0.0" in fqns
    assert "spatial.accessibility.two_step_fca@1.0.0" in fqns
    assert "spatial.microsim.smsm@1.0.0" in fqns
    assert "spatial.design.maup_profile@1.0.0" in fqns
    assert "spatial.design.zone_balance@1.0.0" in fqns
    assert "microsim.calibration.inverse_behavioral_calibration@1.0.0" in fqns

    # Phase 0: Policy domain
    assert "policy.welfare.cost_benefit_analysis@1.0.0" in fqns
    assert "policy.welfare.atkinson_swf@1.0.0" in fqns
    assert "policy.welfare.sufficient_statistics_welfare@1.0.0" in fqns
    assert "policy.mcda.topsis@1.0.0" in fqns
    assert "policy.mcda.rank_stability@1.0.0" in fqns
    assert "policy.mcda.robust_topsis@1.0.0" in fqns
    assert "policy.mcda.robust_ahp@1.0.0" in fqns
    assert "policy.mcda.robust_electre@1.0.0" in fqns
    assert "policy.evaluation.budget_impact@1.0.0" in fqns
    assert "policy.evaluation.foundation_model_policy_analysis@1.0.0" in fqns
    assert "policy.macro.fiscal_multiplier@1.0.0" in fqns
    assert "policy.macro.krusell_smith_lite@1.0.0" in fqns
    assert "policy.public_finance.optimal_linear_tax@1.0.0" in fqns
    assert "policy.agent_sim.mean_field_equilibrium@1.0.0" in fqns

    # Phase 1: Causal expansion
    assert "causal.treatment_effects.aipw@1.0.0" in fqns
    assert "causal.treatment_effects.tmle@1.0.0" in fqns
    assert "causal.treatment_effects.ipw@1.0.0" in fqns
    assert "causal.proximal.proximal_bridge@1.0.0" in fqns
    assert "causal.proximal.spatial_proximal_bridge@1.0.0" in fqns
    assert "causal.distributional.unconditional_qte@1.0.0" in fqns
    assert "causal.interference.network_cate@1.0.0" in fqns
    assert "causal.inference.did.callaway_santanna@1.0.0" in fqns
    assert "causal.inference.did.sun_abraham@1.0.0" in fqns
    assert "causal.bounds.manski@1.0.0" in fqns
    assert "causal.bounds.lee@1.0.0" in fqns
    assert "causal.mediation.causal_mediation@1.0.0" in fqns
    assert "causal.advanced.shift_share_iv@1.0.0" in fqns
    assert "causal.hte.dr_learner@1.0.0" in fqns

    # Phase 2: Econometrics expansion
    assert "econometrics.discrete_choice.logit@1.0.0" in fqns
    assert "econometrics.discrete_choice.probit@1.0.0" in fqns
    assert "econometrics.selection.heckman@1.0.0" in fqns
    assert "econometrics.count.poisson@1.0.0" in fqns
    assert "econometrics.semiparametric.robinson@1.0.0" in fqns
    assert "econometrics.high_dimensional.post_lasso@1.0.0" in fqns

    # Phase 3: Distributional expansion
    assert "distributional.inequality.theil@1.0.0" in fqns
    assert "distributional.inequality.palma_ratio@1.0.0" in fqns
    assert "distributional.mobility.transition_matrix@1.0.0" in fqns
    assert "distributional.mobility.transition_matrix_attrition_adjusted@1.0.0" in fqns
    assert "distributional.mobility.sequential_lifetime_transition_matrix@1.0.0" in fqns
    assert "distributional.mobility.refreshment_transition_matrix@1.0.0" in fqns
    assert "distributional.polarization.esteban_ray@1.0.0" in fqns

    # Phase 4: Sensitivity expansion
    assert "sensitivity.global.morris@1.0.0" in fqns
    assert "sensitivity.specification.specification_curve@1.0.0" in fqns
    assert "sensitivity.global.dependent_copula_sensitivity@1.0.0" in fqns

    # Phase 5: Survey expansion
    assert "survey.adaptive.adaptive_calibrated_ipw@1.0.0" in fqns
    assert "survey.adaptive.adaptive_augmented@1.0.0" in fqns
    assert "survey.estimation.causal_frontier_fay_herriot@1.0.0" in fqns
    assert "survey.estimation.fay_herriot@1.0.0" in fqns
    assert "survey.imputation.mice@1.0.0" in fqns
    assert "survey.design.complex_survey@1.0.0" in fqns
    assert "microsim.imputation.mnar_income_bounds@1.0.0" in fqns

    # Phase 6: Minor expansions
    assert "simulation.inference.bootstrap@1.0.0" in fqns
    assert "optimization.combinatorial.knapsack@1.0.0" in fqns
    assert "optimization.game_theory.nash_equilibrium@1.0.0" in fqns


def test_method_catalog_snapshot_exposes_v2_capability_matrix_fields() -> None:
    ensure_all_methods_registered()
    snapshot = build_method_catalog_snapshot(run_id="R_catalog")

    entry = next(
        item for item in snapshot.entries if item.fqn == "survey.weighting.horvitz_thompson@1.0.0"
    )

    assert entry.execution_backend == "numpy"
    assert entry.kind == "pure"
    assert entry.family == "survey.weighting"
    assert entry.variant == "horvitz_thompson"
    assert entry.fidelity_tier == "high"
    assert set(entry.data_modalities) == {"survey"}
    assert entry.runtime_stack == ["numpy"]
    assert entry.determinism_tier == "library_deterministic"
    assert entry.required_deps == ["numpy"]
    assert entry.optional_deps == []
    assert entry.fallback_policy == "none"
    assert entry.side_effect_profile == "none"
    assert entry.runnable is True
    assert entry.disabled_reasons == []
    assert entry.dependency_posture["all_required_available"] is True
    assert entry.capability_matrix["kind"] == "pure"
    assert entry.capability_matrix["execution_backend"] == "numpy"
    assert entry.capability_matrix["required_deps"] == ["numpy"]
    assert entry.capability_matrix["runnable"] is True
    assert entry.truthfulness_tier == "unverified"
    assert entry.implementation_depth_tier == "production_method"
    assert entry.effect_semantics["method_kind"] == "pure"
    assert entry.shape_semantics["input_arity"] >= 0
    assert entry.dependency_semantics["hard_requires"] == []
    assert entry.capability_matrix["declared_determinism_tier"] == "library_deterministic"
    assert entry.capability_matrix["runtime_determinism_tier"] == "library_deterministic"
    assert entry.capability_matrix["replay_semantics"]
    assert entry.capability_matrix["tolerance_budget"]["semantic_mode"] == "library_exact_cpu"
    assert entry.capability_matrix["runtime_posture"]["backend"] == "numpy"
    assert entry.capability_matrix["runtime_posture"]["available"] is True
    assert entry.capability_matrix["runtime_posture"]["fingerprint"]
    assert entry.capability_matrix["effective_truthfulness_tier"] == "unverified"
    assert entry.capability_matrix["implementation_depth_tier"] == "production_method"


def test_method_catalog_snapshot_uses_conservative_effective_determinism_tier() -> None:
    ensure_all_methods_registered()
    snapshot = build_method_catalog_snapshot(run_id="R_catalog")

    entry = next(
        item
        for item in snapshot.entries
        if item.fqn == "bayesian.regression.linear_regression@1.0.0"
    )

    assert entry.capability_matrix["declared_determinism_tier"] == "statistical"
    assert entry.capability_matrix["runtime_determinism_tier"] == "statistical"
    assert entry.determinism_tier == "statistical"
    assert entry.capability_matrix["replay_semantics"].startswith("Replay is seed-stable")


def test_method_catalog_snapshot_exposes_declared_truthfulness_scope_from_metadata() -> None:
    ensure_all_methods_registered()
    snapshot = build_method_catalog_snapshot(run_id="R_catalog")

    entry = next(
        item
        for item in snapshot.entries
        if item.fqn == "bayesian.regression.linear_regression@1.0.0"
    )

    assert entry.declared_truthfulness_tier == "asymptotic"
    assert entry.truthfulness_scope == "posterior"
    assert entry.truthfulness_tier == "asymptotic"
    assert entry.truthfulness_status == "catalog_only"


def test_method_catalog_snapshot_marks_hmc_and_nuts_as_catalog_only_asymptotic() -> None:
    ensure_all_methods_registered()
    snapshot = build_method_catalog_snapshot(run_id="R_catalog")

    for fqn in (
        "bayesian.sampling.hmc@1.0.0",
        "bayesian.sampling.nuts@1.0.0",
    ):
        entry = next(item for item in snapshot.entries if item.fqn == fqn)
        assert entry.declared_truthfulness_tier == "asymptotic"
        assert entry.truthfulness_scope == "posterior"
        assert entry.truthfulness_tier == "asymptotic"
        assert entry.truthfulness_status == "catalog_only"
        assert entry.capability_matrix["declared_truthfulness_tier"] == "asymptotic"
        assert entry.capability_matrix["truthfulness_tier"] == "asymptotic"
        assert entry.capability_matrix["truthfulness_status"] == "catalog_only"


def test_method_catalog_snapshot_marks_tabular_transformer_as_heuristic_baseline() -> None:
    ensure_all_methods_registered()
    snapshot = build_method_catalog_snapshot(run_id="R_catalog")

    entry = next(
        item for item in snapshot.entries if item.fqn == "ml.deep.tabular_transformer@1.0.0"
    )

    assert entry.truthfulness_tier == "unverified"
    assert entry.implementation_depth_tier == "heuristic_baseline"
    assert "baseline" in entry.implementation_depth_notes.lower()


def test_method_capability_matrix_exports_truthfulness_and_semantics() -> None:
    ensure_all_methods_registered()
    snapshot = build_method_catalog_snapshot(run_id="R_catalog")

    matrix = build_method_capability_matrix(snapshot, runnable_only=True)
    row = next(item for item in matrix if item["fqn"] == "survey.weighting.horvitz_thompson@1.0.0")

    assert row["truthfulness_tier"] == "unverified"
    assert row["implementation_depth_tier"] == "production_method"
    assert row["effect_semantics"]["method_kind"] == "pure"
    assert row["dependency_semantics"]["hard_requires"] == []


def test_symbolic_method_catalog_requires_its_actual_y0_trso_family() -> None:
    from polisyos.ir.analytics.causal_capabilities import (
        CausalBackendCapability,
        CausalBackendId,
        CausalCapabilityContract,
        CausalIdentificationFamily,
    )

    ensure_all_methods_registered()
    contract = CausalCapabilityContract(
        dependency_fingerprint="controlled-y0-catalog",
        full_backend_order=[CausalBackendId.Y0],
        degradation_policy="explicit_only",
        backends=[
            CausalBackendCapability(
                backend_id=CausalBackendId.Y0,
                available=True,
                supported_families=[
                    CausalIdentificationFamily.DIRECT,
                    CausalIdentificationFamily.TRSO,
                ],
            )
        ],
        supported_families=[CausalIdentificationFamily.DIRECT, CausalIdentificationFamily.TRSO],
        disabled_families={
            family.value: "symbolic_family_execution_not_established"
            for family in (
                CausalIdentificationFamily.FRONTDOOR,
                CausalIdentificationFamily.DO_CALCULUS_RULE2,
                CausalIdentificationFamily.DO_CALCULUS_RULE3,
                CausalIdentificationFamily.C_COMPONENT_FACTORIZATION,
            )
        },
        notes=[],
    )
    snapshot = build_method_catalog_snapshot(
        run_id="R_y0_trso_catalog", capability_contract=contract
    )
    symbolic = next(
        entry for entry in snapshot.entries if "causal.transport.symbolic_identify@" in entry.fqn
    )

    assert symbolic.causal_capability_requirements == [
        CausalIdentificationFamily.DIRECT.value,
        CausalIdentificationFamily.TRSO.value,
    ]
    assert symbolic.causal_available is True
    assert not any(
        family in symbolic.causal_capability_requirements
        for family in (
            CausalIdentificationFamily.FRONTDOOR.value,
            CausalIdentificationFamily.DO_CALCULUS_RULE2.value,
            CausalIdentificationFamily.DO_CALCULUS_RULE3.value,
            CausalIdentificationFamily.C_COMPONENT_FACTORIZATION.value,
        )
    )

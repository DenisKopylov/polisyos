"""Identity controls for exact Source50 routes and distinct IR contracts."""

import ast
from collections.abc import Mapping
from importlib import import_module
from importlib.util import resolve_name
from pathlib import Path

import pytest

import polisyos.fabric.ingestion as fabric_ingestion_facade
import polisyos.ir as ir_facade
import polisyos.scientist.policy_design as scientist_policy_design_facade
from polisyos.berl import ValidationThresholds as PublicValidationThresholds
from polisyos.berl.contracts.validation_rules import (
    ValidationThresholds as OwnerValidationThresholds,
)
from polisyos.data_forge.domains.catalog.knowledge.country_codes import (
    normalize_country_code as owner_normalize_country_code,
)
from polisyos.data_forge.domains.catalog.selection import (
    CatalogRunProfile as OwnerCatalogRunProfile,
)
from polisyos.data_forge.domains.ukraine.demography.source_inventory import (
    DemographySourceEvidence as OwnerDemographySourceEvidence,
)
from polisyos.data_forge.kernel.embeddings import (
    resolve_embedding_generation as owner_resolve_embedding_generation,
)
from polisyos.data_forge.read_api.catalog import (
    CatalogRunProfile as PublicCatalogRunProfile,
)
from polisyos.data_forge.read_api.catalog import (
    normalize_country_code as public_normalize_country_code,
)
from polisyos.data_forge.read_api.catalog import (
    resolve_embedding_generation as public_resolve_embedding_generation,
)
from polisyos.data_forge.read_api.ukraine import (
    DemographySourceEvidence as PublicDemographySourceEvidence,
)
from polisyos.fabric.connectors import (
    SourceProfileRegistry as PublicSourceProfileRegistry,
)
from polisyos.fabric.connectors.profiles.registry import (
    SourceProfileRegistry as OwnerSourceProfileRegistry,
)
from polisyos.fabric.ingestion import (
    ConnectorManifestSpec as PublicConnectorManifestSpec,
)
from polisyos.fabric.ingestion import (
    DatasetFetchSpec as PublicDatasetFetchSpec,
)
from polisyos.fabric.ingestion import (
    resolve_ingestion_dependencies as public_resolve_ingestion_dependencies,
)
from polisyos.foundry.execute import (
    resolve_execution_posture as public_resolve_execution_posture,
)
from polisyos.foundry.execute._internal.posture import (
    resolve_execution_posture as owner_resolve_execution_posture,
)
from polisyos.foundry.uncertainty import PropagationConfig as PublicPropagationConfig
from polisyos.foundry.uncertainty.config import (
    PropagationConfig as OwnerPropagationConfig,
)
from polisyos.ir import (
    DataViewRequest as LegacyDataViewRequest,
)
from polisyos.ir import (
    MechanismDesignFamily,
    ModelQueryDataViewRequest,
    get_json_artifact_with_bytes,
)
from polisyos.ir import (
    MechanismFamily as LegacyMechanismFamily,
)
from polisyos.ir.analytics.data_views import DataViewRequest as AnalyticsDataViewRequest
from polisyos.ir.analytics.mechanism_design import (
    MechanismFamily as OwnerMechanismDesignFamily,
)
from polisyos.ir.artifacts.io import (
    _get_json_artifact_with_bytes,
)
from polisyos.ir.artifacts.io import (
    get_json_artifact_with_bytes as public_get_json_artifact_with_bytes,
)
from polisyos.ir.model_layer.queries import (
    DataViewRequest as OwnerModelQueryDataViewRequest,
)
from polisyos.scientist.policy_design import (
    PolicyCandidateSchema as PublicPolicyCandidateSchema,
)
from polisyos.scientist.policy_design.schema import (
    PolicyCandidateSchema as OwnerPolicyCandidateSchema,
)


def test_exact_source50_facades_preserve_object_identity() -> None:
    assert PublicValidationThresholds is OwnerValidationThresholds
    assert PublicCatalogRunProfile is OwnerCatalogRunProfile
    assert public_normalize_country_code is owner_normalize_country_code
    assert public_resolve_embedding_generation is owner_resolve_embedding_generation
    assert PublicDemographySourceEvidence is OwnerDemographySourceEvidence
    assert PublicSourceProfileRegistry is OwnerSourceProfileRegistry
    assert public_resolve_execution_posture is owner_resolve_execution_posture
    assert PublicPropagationConfig is OwnerPropagationConfig


def test_existing_package_facades_resolve_exact_public_bindings() -> None:
    assert scientist_policy_design_facade.PolicyCandidateSchema is PublicPolicyCandidateSchema
    assert PublicPolicyCandidateSchema is OwnerPolicyCandidateSchema
    assert fabric_ingestion_facade.ConnectorManifestSpec is PublicConnectorManifestSpec
    assert fabric_ingestion_facade.DatasetFetchSpec is PublicDatasetFetchSpec
    assert (
        fabric_ingestion_facade.resolve_ingestion_dependencies
        is public_resolve_ingestion_dependencies
    )


def test_ir_same_name_contracts_remain_distinct_and_bytes_alias_is_exact() -> None:
    assert MechanismDesignFamily is OwnerMechanismDesignFamily
    assert LegacyMechanismFamily is not MechanismDesignFamily
    assert LegacyDataViewRequest is AnalyticsDataViewRequest
    assert ModelQueryDataViewRequest is OwnerModelQueryDataViewRequest
    assert LegacyDataViewRequest is not ModelQueryDataViewRequest
    assert get_json_artifact_with_bytes is public_get_json_artifact_with_bytes
    assert public_get_json_artifact_with_bytes is _get_json_artifact_with_bytes


def _eager_ir_owner_routes(declared: set[str]) -> dict[str, tuple[str, str]]:
    """Derive eager public bindings from the facade's actual import statements."""
    source_path = Path(ir_facade.__file__)
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    package = ir_facade.__package__
    assert package is not None
    routes: dict[str, tuple[str, str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.level:
            relative_name = "." * node.level + (node.module or "")
            owner_module = resolve_name(relative_name, package)
        else:
            owner_module = node.module
        if owner_module is None:
            continue
        for alias in node.names:
            local_name = alias.asname or alias.name
            if local_name in declared:
                routes[local_name] = (owner_module, alias.name)
    return routes


def _assert_complete_ir_lazy_owner_routes() -> None:
    """Recompute every public binding against its actual eager or lazy owner route."""
    exports = ir_facade._LAZY_IMPORTS
    assert isinstance(exports, Mapping)

    declared = set(ir_facade.__all__)
    lazy_names = set(exports)
    eager_names = set(vars(ir_facade))
    unresolved = declared - eager_names - lazy_names
    assert not unresolved, f"public IR exports have no eager or lazy binding: {sorted(unresolved)}"

    eager_routes = _eager_ir_owner_routes(declared)
    for public_name in sorted(declared):
        if public_name in exports:
            owner_ref = exports[public_name]
        else:
            assert public_name in eager_names
            owner_ref = eager_routes.get(public_name)
            assert owner_ref is not None, (
                f"eager public IR export has no static owner import: {public_name}"
            )
        assert isinstance(owner_ref, tuple) and len(owner_ref) == 2
        owner_module, owner_name = owner_ref
        assert isinstance(owner_module, str) and isinstance(owner_name, str)
        owner_value = getattr(import_module(owner_module), owner_name)
        assert getattr(ir_facade, public_name) is owner_value, public_name


def test_every_ir_lazy_export_is_the_actual_owner_object() -> None:
    """All lazy API exports follow their declared owner mapping, without a sample list."""
    _assert_complete_ir_lazy_owner_routes()


def test_removing_an_ir_route_while_keeping_its_public_marker_is_detected() -> None:
    """A missing owner route cannot pass because __all__ still names the export."""
    exports = ir_facade._LAZY_IMPORTS
    public_lazy_names = set(ir_facade.__all__).intersection(exports)
    public_name = sorted(public_lazy_names)[0]
    route = exports.pop(public_name)
    namespace = vars(ir_facade)
    sentinel = object()
    prior_global = namespace.pop(public_name, sentinel)
    try:
        assert public_name in ir_facade.__all__
        with pytest.raises(AssertionError, match="public IR exports"):
            _assert_complete_ir_lazy_owner_routes()
        with pytest.raises(AttributeError, match="no attribute"):
            getattr(ir_facade, public_name)
    finally:
        exports[public_name] = route
        if prior_global is not sentinel:
            setattr(ir_facade, public_name, prior_global)

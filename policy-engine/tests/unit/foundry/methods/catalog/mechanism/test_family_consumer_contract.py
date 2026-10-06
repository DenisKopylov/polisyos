"""Exercise original family/catalog and layout migration consumer contracts."""

from __future__ import annotations

import importlib
from decimal import Decimal

import jax.numpy as jnp
import numpy as np
import pytest

from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.foundry import PatchOp
from polisyos.core.contracts.ic_verification import ICVerificationRequest
from polisyos.foundry._registry import (
    MissingRuntimeMechanismSupportError,
    get_mechanism_descriptor,
    has_runtime_mechanism_support,
)
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.execute._internal.models import get_state_path, put_tensor
from polisyos.foundry.execute._internal.ops import apply_ops_to_state
from polisyos.foundry.execute.executor import load_state_snapshot, put_state_snapshot
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.catalog.mechanism import ensure_mechanism_methods_registered
from polisyos.foundry.methods.catalog.mechanism.families import (
    get_mechanism_family_spec,
    mechanism_family_catalog,
)
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.analytics import mechanism_design as certificates
from polisyos.ir.governance.game_design import (
    BayesianTypeSpec,
    MechanismConstraintType,
    MechanismDesignConstraint,
    MechanismDesignSpec,
    MechanismGameRepresentation,
)
from polisyos.ir.governance.policy_spec import InterventionSpec, MechanismBinding, PolicySpec
from polisyos.ir.kernel import DEFAULT_SLOT_REGISTRY
from polisyos.ir.kernel.merge_rules import DEFAULT_MERGE_RULE_REGISTRY
from polisyos.ir.registry.refs import IncentiveCompatibilityCertificateRef
from polisyos.scientist.validation.verification.ic import (
    load_ic_certificate,
    load_ic_negative_certificate,
    verify_incentive_compatibility,
)

FAMILY_IDS = (
    "bayes_tax_pl_v1",
    "bayes_tax_affine_v1",
    "license_scoring_reserve_v1",
    "license_myerson_score_v1",
)
RUNTIME_IDS = ("tax_subsidy", "income_tax", "labor_market", "queue", "adaptive_agent")


def _policy(family_id: str, *, wrong_payment: bool = False) -> PolicySpec:
    tax = family_id.startswith("bayes_tax_")
    if tax:
        params = {
            "type_grid": [Decimal("1"), Decimal("1.5"), Decimal("2")],
            "prior_weights": [Decimal("1"), Decimal("1"), Decimal("1")],
            "u0": Decimal("0"),
            "revenue_floor": Decimal("-1"),
        }
        if family_id == "bayes_tax_affine_v1":
            params["gamma"] = Decimal("0.8")
        else:
            params["earnings_schedule"] = [Decimal("0.8"), Decimal("1.2"), Decimal("1.6")]
    else:
        params = {
            "bid_grid": [Decimal("0"), Decimal("0.5"), Decimal("1")],
            "allocation_rule": [Decimal("0"), Decimal("1"), Decimal("1")],
            "payments": [Decimal("0"), Decimal("0.6" if wrong_payment else "0.5"), Decimal("0.5")],
            "reserve_price": Decimal("0.5"),
            "n_bidders": 5,
            "k_units": 2,
            "cdf_at_reserve": Decimal("0.5"),
        }
    return PolicySpec(
        policy_id="family_consumer",
        interventions=[
            InterventionSpec(
                intervention_id="instance",
                kind="income_tax_piecewise_linear" if tax else "license_scoring_auction",
                target={"kind": "predicate", "field": "income", "operator": ">=", "value": 0},
                schedule={"start_step": 0, "duration_steps": 1},
                params=params,
            )
        ],
        mechanism_bindings=[
            MechanismBinding(
                binding_id="family_binding",
                mechanism_id=family_id,
                intervention_ids=["instance"],
            )
        ],
        mechanism_design=MechanismDesignSpec(
            design_id="family_design",
            representation=MechanismGameRepresentation.BAYESIAN,
            players=("agent",),
            mechanism_ids=(family_id,),
            action_spaces={"agent": ("low", "middle", "high")},
            bayesian_types=[
                BayesianTypeSpec(
                    player_id="agent",
                    type_space=("low", "middle", "high"),
                    prior_probabilities={"low": 0.25, "middle": 0.50, "high": 0.25},
                )
            ],
            constraints=[
                MechanismDesignConstraint(
                    constraint_id="ic",
                    constraint_type=MechanismConstraintType.BAYESIAN_IC
                    if tax
                    else MechanismConstraintType.DOMINANT_STRATEGY_IC,
                    applies_to_players=("agent",),
                )
            ],
        ),
    )


@pytest.mark.parametrize("family_id", FAMILY_IDS)
def test_all_families_have_real_ic_service_and_fresh_certificate_consumers(tmp_path, family_id):
    """Catalog metadata alone cannot replace a concrete instance certificate."""
    family = get_mechanism_family_spec(family_id)
    store = FileSystemCAS(tmp_path / "cas")
    input_ref = store.put_json(
        _policy(family_id),
        PutOptions(kind="ir.policy_spec", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    request = ICVerificationRequest(
        property="bayesian_ic" if family_id.startswith("bayes_tax_") else "dominant_strategy_ic",
        input_ref=input_ref,
    )
    result = verify_incentive_compatibility(store, request)
    assert result.ok and result.verdict == "positive", result.notes
    certificate = load_ic_certificate(FileSystemCAS(tmp_path / "cas"), result.certificate_ref)
    assert certificate.witness["mechanism_id"] == family_id
    assert certificate.witness["family_assumptions"] == list(family.assumptions)
    concrete_ref = IncentiveCompatibilityCertificateRef.model_validate(
        certificate.witness["mechanism_ic_certificate_ref"]
    )
    concrete = certificates.load_incentive_compatibility_certificate(
        FileSystemCAS(tmp_path / "cas"), concrete_ref
    )
    assert concrete.mechanism_id == family_id
    assert concrete.family is family.family
    assert concrete.status is certificates.IncentiveCertificateStatus.CERTIFIED
    assert certificate.input_digest == str(input_ref.artifact_id)


@pytest.mark.parametrize("family_id", FAMILY_IDS[2:])
def test_catalog_membership_does_not_admit_wrong_threshold_payment(tmp_path, family_id):
    before = mechanism_family_catalog()
    store = FileSystemCAS(tmp_path / "cas")
    input_ref = store.put_json(
        _policy(family_id, wrong_payment=True),
        PutOptions(kind="ir.policy_spec", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    result = verify_incentive_compatibility(
        store, ICVerificationRequest(property="dominant_strategy_ic", input_ref=input_ref)
    )
    assert not result.ok and result.verdict == "negative", result.notes
    certificate = load_ic_negative_certificate(
        FileSystemCAS(tmp_path / "cas"), result.certificate_ref
    )
    assert certificate.input_digest == str(input_ref.artifact_id)
    assert mechanism_family_catalog() == before


def test_design_compatibility_helpers_are_ir_and_catalog_owned_actual_callers():
    design = importlib.import_module("polisyos.foundry.mechanisms.design")
    assert design.get_mechanism_family_spec is get_mechanism_family_spec
    assert design.mechanism_family_catalog() == mechanism_family_catalog()
    for name in (
        "certify_affine_tax",
        "certify_piecewise_linear_tax",
        "certify_license_scoring_auction",
        "build_reserve_auction_welfare_loss_bound",
    ):
        assert getattr(design, name) is getattr(certificates, name)
    certificate, bound = design.certify_affine_tax(
        mechanism_id="bayes_tax_affine_v1",
        type_grid=(1, 1.5, 2),
        gamma=0.8,
    )
    assert certificate.family is certificates.MechanismFamily.TAX_AFFINE
    assert bound.family is certificate.family
    with pytest.raises(ValueError, match="Unknown mechanism family"):
        design.get_mechanism_family_spec("unknown")


@pytest.mark.parametrize("mechanism_id", RUNTIME_IDS)
def test_existing_runtime_descriptor_loads_registered_method_and_real_kernel(mechanism_id):
    registry = MethodRegistry.get_instance()
    ensure_mechanism_methods_registered(registry)
    descriptor = get_mechanism_descriptor(mechanism_id)
    method = registry.get(descriptor.method_fqn)
    assert descriptor.method_fqn == f"mechanism.runtime.{mechanism_id}@1.0.0"
    assert method.runtime_mechanism_type == mechanism_id
    module, symbol = method.runtime_mechanism_class_path.split(":")
    assert descriptor.mechanism_class is getattr(importlib.import_module(module), symbol)


@pytest.mark.parametrize("family_id", FAMILY_IDS)
def test_declaration_and_executable_descriptor_identities_remain_distinct(family_id):
    assert get_mechanism_family_spec(family_id).mechanism_id == family_id
    assert not has_runtime_mechanism_support(family_id)
    with pytest.raises(MissingRuntimeMechanismSupportError) as error:
        get_mechanism_descriptor(family_id)
    assert error.value.mech_type == family_id


@pytest.mark.parametrize(
    "address",
    [
        "polisyos.ir.kernel.slots",
        "polisyos.foundry.methods.layout",
        "polisyos.foundry.methods.compiler.layout",
    ],
)
def test_native_registered_income_tax_patches_consume_layout_and_fresh_state(tmp_path, address):
    """Existing supported runtime methods use real slots; no family mapping is invented."""
    module = importlib.import_module(address)
    layout = module.build_slot_layout(DEFAULT_SLOT_REGISTRY)
    manifest = module.build_slot_family_manifest(DEFAULT_SLOT_REGISTRY)
    assert layout.layout["agents.income"] == "agents.income"
    assert "agents.income" in manifest.families["agents"].slots
    registry = MethodRegistry.get_instance()
    ensure_mechanism_methods_registered(registry)
    descriptor = get_mechanism_descriptor("income_tax")
    method = registry.get(descriptor.method_fqn)
    state = GlobalState.empty(n_agents=4, n_firms=0)
    state = state.replace(
        agents=state.agents.replace(
            active=jnp.array([True, False, True, True]),
            income=jnp.array([10.0, 20.0, 30.0, 40.0]),
            reported_income=jnp.array([10.0, 20.0, 30.0, 40.0]),
        )
    )
    result = MethodDispatcher.get_instance().dispatch(
        method_class=method,
        signature=method.signature,
        state=state,
        params={"rate": 0.2},
        seed=7,
    )
    patches = result.slot_outputs["result"]["patches"]
    assert set(patches) == {"agents.income", "government.balance"}
    store = FileSystemCAS(tmp_path / "cas")
    ops = [
        PatchOp(slot_id=slot_id, op="add", value_ref=put_tensor(store, jnp.asarray(patch["delta"])))
        for slot_id, entries in patches.items()
        for patch in entries
    ]
    changed = apply_ops_to_state(
        store,
        base_state=state,
        ops=ops,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
    )
    snapshot_ref = put_state_snapshot(store, state=changed)
    fresh = load_state_snapshot(FileSystemCAS(tmp_path / "cas"), snapshot_ref=snapshot_ref)
    np.testing.assert_allclose(
        get_state_path(fresh, layout.layout["agents.income"]), [8.0, 20.0, 24.0, 32.0]
    )
    assert float(get_state_path(fresh, layout.layout["government.balance"])) == pytest.approx(16.0)
    np.testing.assert_array_equal(state.agents.income, [10.0, 20.0, 30.0, 40.0])

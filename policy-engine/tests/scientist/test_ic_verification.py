from __future__ import annotations

from decimal import Decimal

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.ic_verification import ICVerificationRequest
from polisyos.core.contracts.trinity import TrinityBundleRef
from polisyos.ir.analytics.mechanism_design import (
    load_incentive_compatibility_certificate as load_mechanism_ic_certificate,
)
from polisyos.ir.analytics.mechanism_design import (
    load_mechanism_family_spec,
    load_mechanism_welfare_loss_bound,
)
from polisyos.ir.governance.game_design import (
    BayesianTypeSpec,
    MechanismConstraintType,
    MechanismDesignConstraint,
    MechanismDesignSpec,
    MechanismGameRepresentation,
)
from polisyos.ir.governance.mechanism_semantics import (
    CycMonAllocationPointSpec,
    CycMonGridSemanticsSpec,
    CycMonTypePointSpec,
    Envelope1DPointSpec,
    Envelope1DSemanticsSpec,
    ExactPlayerPriorSpec,
    FiniteOutcomeRuleEntry,
    FiniteOutcomeSpec,
    FiniteValueTableEntry,
    MechanismPriorKind,
    MechanismPriorSpec,
    MechanismSemanticFragment,
    MechanismSemanticsSpec,
    MechanismUtilityModelKind,
    MechanismUtilityModelSpec,
)
from polisyos.ir.governance.policy_spec import InterventionSpec, MechanismBinding, PolicySpec
from polisyos.ir.governance.problem_frame import (
    ObjectiveSpec,
    ProblemDomain,
    ProblemFrame,
)
from polisyos.ir.governance.schedule import ScheduleSpec
from polisyos.ir.governance.selector_expr import SelectorPredicate
from polisyos.ir.model_spec import FidelityLevel, ModelSpec
from polisyos.ir.refs import (
    IncentiveCompatibilityCertificateRef as MechanismICCertificateRef,
)
from polisyos.ir.refs import (
    MechanismFamilySpecRef,
    MechanismWelfareLossBoundRef,
)
from polisyos.ir.trinity import TrinityBundle
from polisyos.ir.types import OptimizationDirection
from polisyos.scientist.verification.ic import (
    load_ic_certificate,
    load_ic_negative_certificate,
    load_ic_report,
    verify_incentive_compatibility,
)


def _problem_frame() -> ProblemFrame:
    return ProblemFrame(
        problem_id="ic_problem",
        domain=ProblemDomain.FISCAL,
        objectives=[
            ObjectiveSpec(
                objective_id="welfare",
                metric_id="social_welfare",
                direction=OptimizationDirection.MAXIMIZE,
            )
        ],
    )


def _model_spec() -> ModelSpec:
    return ModelSpec(
        model_id="ic_model",
        data_snapshot_ref="sha256:0000000000000000000000000000000000000000000000000000000000000000",
        fidelity_level=FidelityLevel.HYBRID,
    )


def _policy_with_design(design: MechanismDesignSpec) -> PolicySpec:
    return PolicySpec(
        policy_id="ic_policy",
        interventions=[
            InterventionSpec(
                intervention_id="posted_price",
                kind="posted_price",
                target=SelectorPredicate(field="income", operator=">=", value=Decimal("0")),
                schedule=ScheduleSpec(start_step=0, duration_steps=1),
                params={"price": Decimal("5")},
            )
        ],
        mechanism_bindings=[
            MechanismBinding(
                binding_id="posted_price_binding",
                mechanism_id="posted_price",
                intervention_ids=["posted_price"],
            )
        ],
        mechanism_design=design,
    )


def _family_policy(
    *,
    mechanism_id: str,
    intervention_id: str,
    intervention_kind: str,
    player_id: str,
    type_labels: tuple[str, ...],
    params: dict[str, object],
    constraints: list[MechanismDesignConstraint],
) -> PolicySpec:
    return PolicySpec(
        policy_id="ic_policy",
        interventions=[
            InterventionSpec(
                intervention_id=intervention_id,
                kind=intervention_kind,
                target=SelectorPredicate(field="income", operator=">=", value=Decimal("0")),
                schedule=ScheduleSpec(start_step=0, duration_steps=1),
                params=params,
            )
        ],
        mechanism_bindings=[
            MechanismBinding(
                binding_id=f"{intervention_id}_binding",
                mechanism_id=mechanism_id,
                intervention_ids=[intervention_id],
            )
        ],
        mechanism_design=MechanismDesignSpec(
            design_id=f"{intervention_id}_design",
            representation=MechanismGameRepresentation.BAYESIAN,
            players=(player_id,),
            mechanism_ids=(mechanism_id,),
            action_spaces={player_id: type_labels},
            bayesian_types=[
                BayesianTypeSpec(
                    player_id=player_id,
                    type_space=type_labels,
                    prior_probabilities={label: 1 / len(type_labels) for label in type_labels},
                )
            ],
            constraints=constraints,
        ),
    )


def _multi_family_policy() -> PolicySpec:
    return PolicySpec(
        policy_id="ic_policy_multi",
        interventions=[
            InterventionSpec(
                intervention_id="income_tax",
                kind="income_tax_piecewise_linear",
                target=SelectorPredicate(field="income", operator=">=", value=Decimal("0")),
                schedule=ScheduleSpec(start_step=0, duration_steps=1),
                params={
                    "type_grid": [Decimal("1.0"), Decimal("1.5"), Decimal("2.0")],
                    "earnings_schedule": [Decimal("0.85"), Decimal("1.20"), Decimal("1.55")],
                    "prior_weights": [Decimal("0.25"), Decimal("0.50"), Decimal("0.25")],
                    "u0": Decimal("0"),
                    "revenue_floor": Decimal("-1"),
                },
            ),
            InterventionSpec(
                intervention_id="license_auction",
                kind="license_scoring_auction",
                target=SelectorPredicate(field="income", operator=">=", value=Decimal("0")),
                schedule=ScheduleSpec(start_step=0, duration_steps=1),
                params={
                    "bid_grid": [Decimal("0"), Decimal("0.5"), Decimal("1.0")],
                    "allocation_rule": [Decimal("0"), Decimal("1"), Decimal("1")],
                    "payments": [Decimal("0"), Decimal("0.5"), Decimal("0.5")],
                    "reserve_price": Decimal("0.5"),
                    "n_bidders": 5,
                    "k_units": 2,
                    "cdf_at_reserve": Decimal("0.5"),
                },
            ),
        ],
        mechanism_bindings=[
            MechanismBinding(
                binding_id="income_tax_binding",
                mechanism_id="bayes_tax_pl_v1",
                intervention_ids=["income_tax"],
            ),
            MechanismBinding(
                binding_id="license_binding",
                mechanism_id="license_scoring_reserve_v1",
                intervention_ids=["license_auction"],
            ),
        ],
        mechanism_design=MechanismDesignSpec(
            design_id="multi_family_design",
            representation=MechanismGameRepresentation.BAYESIAN,
            players=("agent",),
            mechanism_ids=("bayes_tax_pl_v1", "license_scoring_reserve_v1"),
            action_spaces={"agent": ("low", "middle", "high")},
            bayesian_types=[
                BayesianTypeSpec(
                    player_id="agent",
                    type_space=("low", "middle", "high"),
                    prior_probabilities={"low": 1 / 3, "middle": 1 / 3, "high": 1 / 3},
                )
            ],
            constraints=[
                MechanismDesignConstraint(
                    constraint_id="agent_dsic",
                    constraint_type=MechanismConstraintType.DOMINANT_STRATEGY_IC,
                    applies_to_players=("agent",),
                )
            ],
        ),
    )


def _persist_trinity(store: FileSystemCAS, bundle: TrinityBundle) -> TrinityBundleRef:
    artifact = store.put_json(
        bundle.model_dump(mode="json"),
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.TrinityBundle", version=str(bundle.schema_version)),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return TrinityBundleRef.model_validate(artifact.model_dump(mode="json"))


def _single_buyer_design(*, high_payment: str) -> MechanismDesignSpec:
    return MechanismDesignSpec(
        design_id="single_buyer",
        representation=MechanismGameRepresentation.BAYESIAN,
        players=("buyer",),
        mechanism_ids=("posted_price",),
        action_spaces={"buyer": ("low", "high")},
        bayesian_types=[
            BayesianTypeSpec(
                player_id="buyer",
                type_space=("low", "high"),
                prior_probabilities={"low": 0.5, "high": 0.5},
            )
        ],
        constraints=[
            MechanismDesignConstraint(
                constraint_id="buyer_dsic",
                constraint_type=MechanismConstraintType.DOMINANT_STRATEGY_IC,
                applies_to_players=("buyer",),
            )
        ],
        semantics=MechanismSemanticsSpec(
            semantics_id="single_buyer_semantics",
            finite_outcomes=[
                FiniteOutcomeSpec(outcome_id="lose", allocation_by_player={"buyer": "lose"}),
                FiniteOutcomeSpec(outcome_id="win", allocation_by_player={"buyer": "win"}),
            ],
            allocation_rule=[
                FiniteOutcomeRuleEntry(report_profile={"buyer": "low"}, outcome_id="lose"),
                FiniteOutcomeRuleEntry(
                    report_profile={"buyer": "high"},
                    outcome_id="win",
                    payments_by_player={"buyer": high_payment},
                ),
            ],
            utility_model=MechanismUtilityModelSpec(
                kind=MechanismUtilityModelKind.QUASI_LINEAR_SCALAR,
                value_table=[
                    FiniteValueTableEntry(
                        player_id="buyer",
                        type_label="low",
                        outcome_values={"lose": "0", "win": "1"},
                    ),
                    FiniteValueTableEntry(
                        player_id="buyer",
                        type_label="high",
                        outcome_values={"lose": "0", "win": "10"},
                    ),
                ],
            ),
        ),
    )


def _two_player_bic_design() -> MechanismDesignSpec:
    return MechanismDesignSpec(
        design_id="two_player_bic",
        representation=MechanismGameRepresentation.BAYESIAN,
        players=("buyer_1", "buyer_2"),
        mechanism_ids=("posted_price",),
        action_spaces={
            "buyer_1": ("low", "high"),
            "buyer_2": ("low", "high"),
        },
        bayesian_types=[
            BayesianTypeSpec(
                player_id="buyer_1",
                type_space=("low", "high"),
                prior_probabilities={"low": 0.5, "high": 0.5},
            ),
            BayesianTypeSpec(
                player_id="buyer_2",
                type_space=("low", "high"),
                prior_probabilities={"low": 0.5, "high": 0.5},
            ),
        ],
        constraints=[
            MechanismDesignConstraint(
                constraint_id="buyer_1_bic",
                constraint_type=MechanismConstraintType.BAYESIAN_IC,
                applies_to_players=("buyer_1",),
            )
        ],
        semantics=MechanismSemanticsSpec(
            semantics_id="two_player_bic_semantics",
            finite_outcomes=[
                FiniteOutcomeSpec(outcome_id="skip", allocation_by_player={"buyer_1": "lose"}),
                FiniteOutcomeSpec(outcome_id="grant", allocation_by_player={"buyer_1": "win"}),
            ],
            allocation_rule=[
                FiniteOutcomeRuleEntry(
                    report_profile={"buyer_1": "low", "buyer_2": "low"},
                    outcome_id="skip",
                ),
                FiniteOutcomeRuleEntry(
                    report_profile={"buyer_1": "low", "buyer_2": "high"},
                    outcome_id="skip",
                ),
                FiniteOutcomeRuleEntry(
                    report_profile={"buyer_1": "high", "buyer_2": "low"},
                    outcome_id="grant",
                ),
                FiniteOutcomeRuleEntry(
                    report_profile={"buyer_1": "high", "buyer_2": "high"},
                    outcome_id="grant",
                ),
            ],
            utility_model=MechanismUtilityModelSpec(
                kind=MechanismUtilityModelKind.QUASI_LINEAR_SCALAR,
                value_table=[
                    FiniteValueTableEntry(
                        player_id="buyer_1",
                        type_label="low",
                        outcome_values={"skip": "0", "grant": "1"},
                    ),
                    FiniteValueTableEntry(
                        player_id="buyer_1",
                        type_label="high",
                        outcome_values={"skip": "0", "grant": "2"},
                    ),
                    FiniteValueTableEntry(
                        player_id="buyer_2",
                        type_label="low",
                        outcome_values={"skip": "0", "grant": "0"},
                    ),
                    FiniteValueTableEntry(
                        player_id="buyer_2",
                        type_label="high",
                        outcome_values={"skip": "0", "grant": "0"},
                    ),
                ],
            ),
            prior=MechanismPriorSpec(
                kind=MechanismPriorKind.INDEPENDENT_EXACT,
                player_priors=[
                    ExactPlayerPriorSpec(
                        player_id="buyer_1",
                        probabilities={"low": "1/2", "high": "1/2"},
                    ),
                    ExactPlayerPriorSpec(
                        player_id="buyer_2",
                        probabilities={"low": "1/2", "high": "1/2"},
                    ),
                ],
            ),
        ),
    )


def _single_buyer_ir_design(*, high_payment: str) -> MechanismDesignSpec:
    return MechanismDesignSpec(
        design_id="single_buyer_ir",
        representation=MechanismGameRepresentation.BAYESIAN,
        players=("buyer",),
        mechanism_ids=("posted_price",),
        action_spaces={"buyer": ("low", "high")},
        bayesian_types=[
            BayesianTypeSpec(
                player_id="buyer",
                type_space=("low", "high"),
                prior_probabilities={"low": 0.5, "high": 0.5},
            )
        ],
        constraints=[
            MechanismDesignConstraint(
                constraint_id="buyer_ir",
                constraint_type=MechanismConstraintType.EX_POST_IR,
                applies_to_players=("buyer",),
            )
        ],
        semantics=MechanismSemanticsSpec(
            semantics_id="single_buyer_ir_semantics",
            finite_outcomes=[
                FiniteOutcomeSpec(outcome_id="lose", allocation_by_player={"buyer": "lose"}),
                FiniteOutcomeSpec(outcome_id="win", allocation_by_player={"buyer": "win"}),
            ],
            allocation_rule=[
                FiniteOutcomeRuleEntry(report_profile={"buyer": "low"}, outcome_id="lose"),
                FiniteOutcomeRuleEntry(
                    report_profile={"buyer": "high"},
                    outcome_id="win",
                    payments_by_player={"buyer": high_payment},
                ),
            ],
            utility_model=MechanismUtilityModelSpec(
                kind=MechanismUtilityModelKind.QUASI_LINEAR_SCALAR,
                value_table=[
                    FiniteValueTableEntry(
                        player_id="buyer",
                        type_label="low",
                        outcome_values={"lose": "0", "win": "1"},
                    ),
                    FiniteValueTableEntry(
                        player_id="buyer",
                        type_label="high",
                        outcome_values={"lose": "0", "win": "10"},
                    ),
                ],
            ),
        ),
    )


def _envelope_design(*, explicit_payment: str | None, monotone: bool) -> MechanismDesignSpec:
    points = [
        Envelope1DPointSpec(type_label="low", type_value="1", allocation="0"),
        Envelope1DPointSpec(
            type_label="high",
            type_value="3",
            allocation="1" if monotone else "0",
            payment=explicit_payment,
        ),
    ]
    if not monotone:
        points[0] = Envelope1DPointSpec(type_label="low", type_value="1", allocation="1")
    return MechanismDesignSpec(
        design_id="buyer_envelope",
        representation=MechanismGameRepresentation.BAYESIAN,
        players=("buyer",),
        mechanism_ids=("posted_price",),
        action_spaces={"buyer": ("low", "high")},
        bayesian_types=[
            BayesianTypeSpec(
                player_id="buyer",
                type_space=("low", "high"),
                prior_probabilities={"low": 0.5, "high": 0.5},
            )
        ],
        constraints=[
            MechanismDesignConstraint(
                constraint_id="buyer_dsic",
                constraint_type=MechanismConstraintType.DOMINANT_STRATEGY_IC,
                applies_to_players=("buyer",),
            )
        ],
        semantics=MechanismSemanticsSpec(
            semantics_id="buyer_envelope_semantics",
            fragment=MechanismSemanticFragment.ENVELOPE_1D,
            envelope_1d=Envelope1DSemanticsSpec(
                player_id="buyer",
                points=points,
            ),
        ),
    )


def _cycmon_design(*, feasible: bool) -> MechanismDesignSpec:
    if feasible:
        type_points = [
            CycMonTypePointSpec(type_label="t00", coords=("0", "0")),
            CycMonTypePointSpec(type_label="t10", coords=("1", "0")),
            CycMonTypePointSpec(type_label="t01", coords=("0", "1")),
            CycMonTypePointSpec(type_label="t11", coords=("1", "1")),
        ]
        allocation_points = [
            CycMonAllocationPointSpec(type_label="t00", allocation=("0", "0")),
            CycMonAllocationPointSpec(type_label="t10", allocation=("1", "0")),
            CycMonAllocationPointSpec(type_label="t01", allocation=("0", "1")),
            CycMonAllocationPointSpec(type_label="t11", allocation=("1", "1")),
        ]
        action_labels = ("t00", "t10", "t01", "t11")
        priors = dict.fromkeys(action_labels, 0.25)
    else:
        type_points = [
            CycMonTypePointSpec(type_label="t00", coords=("0", "0")),
            CycMonTypePointSpec(type_label="t10", coords=("1", "0")),
            CycMonTypePointSpec(type_label="t01", coords=("0", "1")),
        ]
        allocation_points = [
            CycMonAllocationPointSpec(type_label="t00", allocation=("1", "0")),
            CycMonAllocationPointSpec(type_label="t10", allocation=("0", "1")),
            CycMonAllocationPointSpec(type_label="t01", allocation=("0", "0")),
        ]
        action_labels = ("t00", "t10", "t01")
        priors = {"t00": 1 / 3, "t10": 1 / 3, "t01": 1 / 3}
    return MechanismDesignSpec(
        design_id="buyer_cycmon",
        representation=MechanismGameRepresentation.BAYESIAN,
        players=("buyer",),
        mechanism_ids=("posted_price",),
        action_spaces={"buyer": action_labels},
        bayesian_types=[
            BayesianTypeSpec(
                player_id="buyer",
                type_space=action_labels,
                prior_probabilities=priors,
            )
        ],
        constraints=[
            MechanismDesignConstraint(
                constraint_id="buyer_dsic",
                constraint_type=MechanismConstraintType.DOMINANT_STRATEGY_IC,
                applies_to_players=("buyer",),
            )
        ],
        semantics=MechanismSemanticsSpec(
            semantics_id="buyer_cycmon_semantics",
            fragment=MechanismSemanticFragment.CYCMON_GRID,
            cycmon_grid=CycMonGridSemanticsSpec(
                player_id="buyer",
                type_points=type_points,
                allocation_points=allocation_points,
            ),
        ),
    )


def test_verify_incentive_compatibility_persists_positive_dsic_certificate(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    bundle = TrinityBundle(
        problem_frame=_problem_frame(),
        policy_spec=_policy_with_design(_single_buyer_design(high_payment="5")),
        model_spec=_model_spec(),
    )
    input_ref = _persist_trinity(store, bundle)

    result = verify_incentive_compatibility(
        store,
        ICVerificationRequest(
            property="dominant_strategy_ic",
            input_ref=input_ref,
        ),
    )

    assert result.ok is True
    assert result.verdict == "positive"
    assert result.report_ref is not None
    assert result.certificate_ref is not None

    report = load_ic_report(store, result.report_ref)
    certificate = load_ic_certificate(store, result.certificate_ref)

    assert report.verdict == "positive"
    assert certificate.witness["kind"] == "zero_regret_exhaustive"
    assert certificate.witness["max_regret"] == "0"


def test_verify_incentive_compatibility_persists_negative_dsic_certificate(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    bundle = TrinityBundle(
        problem_frame=_problem_frame(),
        policy_spec=_policy_with_design(_single_buyer_design(high_payment="0")),
        model_spec=_model_spec(),
    )
    input_ref = _persist_trinity(store, bundle)

    result = verify_incentive_compatibility(
        store,
        ICVerificationRequest(
            property="dominant_strategy_ic",
            input_ref=input_ref,
        ),
    )

    assert result.ok is False
    assert result.verdict == "negative"
    assert result.report_ref is not None
    assert result.certificate_ref is not None

    report = load_ic_report(store, result.report_ref)
    certificate = load_ic_negative_certificate(store, result.certificate_ref)

    assert report.verdict == "negative"
    assert certificate.witness["kind"] == "profitable_deviation"
    assert certificate.witness["gain"] == "1"


def test_verify_incentive_compatibility_returns_bic_expectation_witness(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    bundle = TrinityBundle(
        problem_frame=_problem_frame(),
        policy_spec=_policy_with_design(_two_player_bic_design()),
        model_spec=_model_spec(),
    )
    input_ref = _persist_trinity(store, bundle)

    result = verify_incentive_compatibility(
        store,
        ICVerificationRequest(
            property="bayesian_ic",
            input_ref=input_ref,
        ),
    )

    certificate = load_ic_negative_certificate(store, result.certificate_ref)

    assert result.verdict == "negative"
    assert certificate.witness["kind"] == "profitable_deviation"
    assert certificate.witness["expected_gain"] == "1"
    assert len(certificate.witness["expectation_terms"]) == 2


def test_verify_incentive_compatibility_returns_ex_post_ir_violation(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    bundle = TrinityBundle(
        problem_frame=_problem_frame(),
        policy_spec=_policy_with_design(_single_buyer_ir_design(high_payment="12")),
        model_spec=_model_spec(),
    )
    input_ref = _persist_trinity(store, bundle)

    result = verify_incentive_compatibility(
        store,
        ICVerificationRequest(
            property="ex_post_ir",
            input_ref=input_ref,
        ),
    )

    certificate = load_ic_negative_certificate(store, result.certificate_ref)

    assert result.verdict == "negative"
    assert certificate.witness["kind"] == "ir_violation"
    assert certificate.witness["utility_truthful"] == "-2"


def test_verify_incentive_compatibility_routes_positive_envelope_backend(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    bundle = TrinityBundle(
        problem_frame=_problem_frame(),
        policy_spec=_policy_with_design(_envelope_design(explicit_payment=None, monotone=True)),
        model_spec=_model_spec(),
    )
    input_ref = _persist_trinity(store, bundle)

    result = verify_incentive_compatibility(
        store,
        ICVerificationRequest(
            property="dominant_strategy_ic",
            input_ref=input_ref,
        ),
    )

    certificate = load_ic_certificate(store, result.certificate_ref)

    assert result.verdict == "positive"
    assert certificate.backend == "envelope_1d"
    assert certificate.witness["kind"] == "envelope_identity"
    assert certificate.witness["payment_source"] == "synthesized"


def test_verify_incentive_compatibility_returns_envelope_impossibility_witness(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    bundle = TrinityBundle(
        problem_frame=_problem_frame(),
        policy_spec=_policy_with_design(_envelope_design(explicit_payment=None, monotone=False)),
        model_spec=_model_spec(),
    )
    input_ref = _persist_trinity(store, bundle)

    result = verify_incentive_compatibility(
        store,
        ICVerificationRequest(
            property="dominant_strategy_ic",
            input_ref=input_ref,
        ),
    )

    certificate = load_ic_negative_certificate(store, result.certificate_ref)

    assert result.verdict == "negative"
    assert certificate.backend == "envelope_1d"
    assert certificate.witness["kind"] == "allocation_impossibility"


def test_verify_incentive_compatibility_routes_positive_cycmon_backend(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    bundle = TrinityBundle(
        problem_frame=_problem_frame(),
        policy_spec=_policy_with_design(_cycmon_design(feasible=True)),
        model_spec=_model_spec(),
    )
    input_ref = _persist_trinity(store, bundle)

    result = verify_incentive_compatibility(
        store,
        ICVerificationRequest(
            property="dominant_strategy_ic",
            input_ref=input_ref,
        ),
    )

    certificate = load_ic_certificate(store, result.certificate_ref)

    assert result.verdict == "positive"
    assert certificate.backend == "cycmon_lp"
    assert certificate.witness["kind"] == "utility_potential"


def test_verify_incentive_compatibility_returns_cycmon_cycle_witness(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    bundle = TrinityBundle(
        problem_frame=_problem_frame(),
        policy_spec=_policy_with_design(_cycmon_design(feasible=False)),
        model_spec=_model_spec(),
    )
    input_ref = _persist_trinity(store, bundle)

    result = verify_incentive_compatibility(
        store,
        ICVerificationRequest(
            property="dominant_strategy_ic",
            input_ref=input_ref,
        ),
    )

    certificate = load_ic_negative_certificate(store, result.certificate_ref)

    assert result.verdict == "negative"
    assert certificate.backend == "cycmon_lp"
    assert certificate.witness["kind"] == "negative_cycle_impossibility"


def test_verify_incentive_compatibility_routes_bayesian_tax_family(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    policy = _family_policy(
        mechanism_id="bayes_tax_pl_v1",
        intervention_id="income_tax",
        intervention_kind="income_tax_piecewise_linear",
        player_id="taxpayer",
        type_labels=("low", "middle", "high"),
        params={
            "type_grid": [Decimal("1.0"), Decimal("1.5"), Decimal("2.0")],
            "earnings_schedule": [Decimal("0.85"), Decimal("1.20"), Decimal("1.55")],
            "prior_weights": [Decimal("0.25"), Decimal("0.50"), Decimal("0.25")],
            "u0": Decimal("0"),
            "revenue_floor": Decimal("-1"),
            "assumptions_hash": "tax_synthetic_v1",
        },
        constraints=[
            MechanismDesignConstraint(
                constraint_id="taxpayer_bic",
                constraint_type=MechanismConstraintType.BAYESIAN_IC,
                applies_to_players=("taxpayer",),
            )
        ],
    )
    bundle = TrinityBundle(
        problem_frame=_problem_frame(),
        policy_spec=policy,
        model_spec=_model_spec(),
    )
    input_ref = _persist_trinity(store, bundle)

    result = verify_incentive_compatibility(
        store,
        ICVerificationRequest(property="bayesian_ic", input_ref=input_ref),
    )

    assert result.verdict == "positive"
    certificate = load_ic_certificate(store, result.certificate_ref)
    assert certificate.backend == "mechanism_family"
    assert certificate.witness["mechanism_id"] == "bayes_tax_pl_v1"
    assert certificate.witness["certificate_type"] == "monotonicity_envelope_tax_v1"

    family_spec = load_mechanism_family_spec(
        store,
        MechanismFamilySpecRef.model_validate(certificate.witness["mechanism_family_spec_ref"]),
    )
    mechanism_certificate = load_mechanism_ic_certificate(
        store,
        MechanismICCertificateRef.model_validate(
            certificate.witness["mechanism_ic_certificate_ref"]
        ),
    )
    welfare_bound = load_mechanism_welfare_loss_bound(
        store,
        MechanismWelfareLossBoundRef.model_validate(
            certificate.witness["mechanism_welfare_loss_bound_ref"]
        ),
    )

    assert family_spec.mechanism_id == "bayes_tax_pl_v1"
    assert mechanism_certificate.status.value == "certified"
    assert welfare_bound.upper_bound >= 0
    assert {
        "ir.mechanism_family_spec",
        "ir.incentive_compatibility_certificate",
        "ir.mechanism_welfare_loss_bound",
    }.issubset({artifact.kind for artifact in certificate.proof_artifacts})


def test_verify_incentive_compatibility_rejects_nonmonotone_tax_family(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    policy = _family_policy(
        mechanism_id="bayes_tax_pl_v1",
        intervention_id="income_tax",
        intervention_kind="income_tax_piecewise_linear",
        player_id="taxpayer",
        type_labels=("low", "middle", "high"),
        params={
            "type_grid": [Decimal("1.0"), Decimal("1.5"), Decimal("2.0")],
            "earnings_schedule": [Decimal("1.0"), Decimal("0.8"), Decimal("1.4")],
            "u0": Decimal("0"),
        },
        constraints=[
            MechanismDesignConstraint(
                constraint_id="taxpayer_bic",
                constraint_type=MechanismConstraintType.BAYESIAN_IC,
                applies_to_players=("taxpayer",),
            )
        ],
    )
    bundle = TrinityBundle(
        problem_frame=_problem_frame(),
        policy_spec=policy,
        model_spec=_model_spec(),
    )
    input_ref = _persist_trinity(store, bundle)

    result = verify_incentive_compatibility(
        store,
        ICVerificationRequest(property="bayesian_ic", input_ref=input_ref),
    )

    assert result.verdict == "negative"
    certificate = load_ic_negative_certificate(store, result.certificate_ref)
    assert certificate.backend == "mechanism_family"
    assert certificate.witness["kind"] == "allocation_impossibility"
    assert certificate.witness["reason"] == "non_monotone_earnings_schedule"
    assert "mechanism_ic_certificate_ref" in certificate.witness


def test_verify_incentive_compatibility_routes_license_family_with_welfare_bound(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    policy = _family_policy(
        mechanism_id="license_scoring_reserve_v1",
        intervention_id="license_auction",
        intervention_kind="license_scoring_auction",
        player_id="bidder",
        type_labels=("v0", "v05", "v10"),
        params={
            "bid_grid": [Decimal("0"), Decimal("0.5"), Decimal("1.0")],
            "allocation_rule": [Decimal("0"), Decimal("1"), Decimal("1")],
            "payments": [Decimal("0"), Decimal("0.5"), Decimal("0.5")],
            "reserve_price": Decimal("0.5"),
            "n_bidders": 5,
            "k_units": 2,
            "cdf_at_reserve": Decimal("0.5"),
        },
        constraints=[
            MechanismDesignConstraint(
                constraint_id="license_dsic",
                constraint_type=MechanismConstraintType.DOMINANT_STRATEGY_IC,
                applies_to_players=("bidder",),
            )
        ],
    )
    bundle = TrinityBundle(
        problem_frame=_problem_frame(),
        policy_spec=policy,
        model_spec=_model_spec(),
    )
    input_ref = _persist_trinity(store, bundle)

    result = verify_incentive_compatibility(
        store,
        ICVerificationRequest(property="dominant_strategy_ic", input_ref=input_ref),
    )

    assert result.verdict == "positive"
    certificate = load_ic_certificate(store, result.certificate_ref)
    assert certificate.backend == "mechanism_family"
    assert certificate.witness["mechanism_id"] == "license_scoring_reserve_v1"
    assert certificate.witness["certificate_type"] == "monotone_threshold_license_v1"
    assert "mechanism_welfare_loss_bound_ref" in certificate.witness

    welfare_bound = load_mechanism_welfare_loss_bound(
        store,
        MechanismWelfareLossBoundRef.model_validate(
            certificate.witness["mechanism_welfare_loss_bound_ref"]
        ),
    )
    assert welfare_bound.bound_type == "reserve_binomial_tail_v1"


def test_verify_incentive_compatibility_packages_all_supported_mechanism_families(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    bundle = TrinityBundle(
        problem_frame=_problem_frame(),
        policy_spec=_multi_family_policy(),
        model_spec=_model_spec(),
    )
    input_ref = _persist_trinity(store, bundle)

    result = verify_incentive_compatibility(
        store,
        ICVerificationRequest(property="dominant_strategy_ic", input_ref=input_ref),
    )

    assert result.ok is True
    assert result.verdict == "positive"
    certificate = load_ic_certificate(store, result.certificate_ref)
    assert certificate.witness["kind"] == "mechanism_family_certificate_package"
    assert set(certificate.witness["covered_mechanism_ids"]) == {
        "bayes_tax_pl_v1",
        "license_scoring_reserve_v1",
    }
    assert set(certificate.witness["mechanism_ic_certificate_refs"]) == {
        "bayes_tax_pl_v1",
        "license_scoring_reserve_v1",
    }
    assert set(certificate.witness["mechanism_welfare_loss_bound_refs"]) == {
        "bayes_tax_pl_v1",
        "license_scoring_reserve_v1",
    }


def test_verify_incentive_compatibility_refuses_license_family_without_welfare_inputs(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    policy = _family_policy(
        mechanism_id="license_scoring_reserve_v1",
        intervention_id="license_auction",
        intervention_kind="license_scoring_auction",
        player_id="bidder",
        type_labels=("v0", "v05", "v10"),
        params={
            "bid_grid": [Decimal("0"), Decimal("0.5"), Decimal("1.0")],
            "allocation_rule": [Decimal("0"), Decimal("1"), Decimal("1")],
            "payments": [Decimal("0"), Decimal("0.5"), Decimal("0.5")],
            "reserve_price": Decimal("0.5"),
        },
        constraints=[
            MechanismDesignConstraint(
                constraint_id="license_dsic",
                constraint_type=MechanismConstraintType.DOMINANT_STRATEGY_IC,
                applies_to_players=("bidder",),
            )
        ],
    )
    bundle = TrinityBundle(
        problem_frame=_problem_frame(),
        policy_spec=policy,
        model_spec=_model_spec(),
    )
    input_ref = _persist_trinity(store, bundle)

    result = verify_incentive_compatibility(
        store,
        ICVerificationRequest(property="dominant_strategy_ic", input_ref=input_ref),
    )

    assert result.ok is False
    assert result.verdict == "semantic_validation_failure"
    assert result.certificate_ref is None
    assert any("n_bidders" in note for note in result.notes)

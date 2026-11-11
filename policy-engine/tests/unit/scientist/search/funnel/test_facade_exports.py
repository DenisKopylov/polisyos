from __future__ import annotations


def test_funnel_lazy_exports_are_canonical_owner_objects() -> None:
    from importlib import import_module

    from polisyos.scientist.methods.search import funnel

    owners = {
        "FunnelCorrelationTracker": (
            "polisyos.scientist.methods.search.funnel.correlation",
            "FunnelCorrelationTracker",
        ),
        "FunnelOrchestrator": (
            "polisyos.scientist.methods.search.funnel.orchestrator",
            "FunnelOrchestrator",
        ),
        "FunnelOutcome": (
            "polisyos.scientist.methods.search.funnel.orchestrator",
            "FunnelOutcome",
        ),
        "FunnelTicket": (
            "polisyos.scientist.methods.search.funnel.orchestrator",
            "FunnelTicket",
        ),
        "FunnelTraceStep": (
            "polisyos.scientist.methods.search.funnel.orchestrator",
            "FunnelTraceStep",
        ),
        "Level0StaticValidator": (
            "polisyos.scientist.methods.search.funnel.level0_static",
            "Level0StaticValidator",
        ),
        "Level1CheapHeuristic": (
            "polisyos.scientist.methods.search.funnel.level1_heuristic",
            "Level1CheapHeuristic",
        ),
        "Level2CausalPlausibility": (
            "polisyos.scientist.methods.search.funnel.level2_causal",
            "Level2CausalPlausibility",
        ),
        "Level3MediumFidelity": (
            "polisyos.scientist.methods.search.funnel.level3_medium",
            "Level3MediumFidelity",
        ),
        "Level4FullFidelity": (
            "polisyos.scientist.methods.search.funnel.level4_full",
            "Level4FullFidelity",
        ),
        "Level5RefutationGovernanceStage": (
            "polisyos.scientist.methods.search.funnel.level5_refutation_governance",
            "Level5RefutationGovernanceStage",
        ),
        "Level6PromotionStage": (
            "polisyos.scientist.methods.search.funnel.level6_promotion",
            "Level6PromotionStage",
        ),
    }

    for export, (module_name, attribute_name) in owners.items():
        owner = getattr(import_module(module_name), attribute_name)
        assert getattr(funnel, export) is owner


def test_funnel_facade_preserves_ir_failure_contract_exports() -> None:
    from polisyos.ir import TypedFailureCard as IRTypedFailureCard
    from polisyos.ir import UncertaintyType as IRUncertaintyType
    from polisyos.scientist.methods.search.funnel import TypedFailureCard, UncertaintyType

    assert TypedFailureCard is IRTypedFailureCard
    assert UncertaintyType is IRUncertaintyType


def test_funnel_public_class_annotations_resolve() -> None:
    import inspect
    from typing import get_type_hints

    from polisyos.scientist.methods.search import funnel

    public_annotated_classes = []
    for name in funnel.__all__:
        exported = getattr(funnel, name)
        if inspect.isclass(exported) and any(
            owner.__dict__.get("__annotations__") for owner in exported.__mro__
        ):
            public_annotated_classes.append((name, exported))

    assert public_annotated_classes
    for name, exported in public_annotated_classes:
        assert get_type_hints(exported), f"{name} has no resolvable annotations"

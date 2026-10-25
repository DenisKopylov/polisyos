from __future__ import annotations


def test_funnel_facade_preserves_ir_uncertainty_type_export() -> None:
    from polisyos.ir import UncertaintyType as IRUncertaintyType
    from polisyos.scientist.methods.search.funnel import UncertaintyType

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

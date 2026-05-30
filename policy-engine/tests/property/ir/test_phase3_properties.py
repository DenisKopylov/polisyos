from __future__ import annotations

from decimal import Decimal

import pytest
from polisyos.ir.model_layer.canon import CanonSpec, content_hash, from_canonical_bytes, to_canonical_bytes
from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.governance.schedule import ScheduleSpec
from polisyos.ir.governance.selector_expr import SelectorPredicate
from polisyos.ir.kernel import (
    DEFAULT_MERGE_RULE_REGISTRY,
    DEFAULT_METRIC_REGISTRY,
    DEFAULT_SELECTOR_FIELD_REGISTRY,
    DEFAULT_SLOT_REGISTRY,
    DEFAULT_UNITS_REGISTRY,
    ConstraintRegistry,
    MechanismTypeRegistry,
    MechanismTypeSpec,
)
from polisyos.ir.kernel.units import MoneyUnit, UnitsRegistry
from polisyos.ir.linker import link_trinity
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.registry.registry_fragments import (
    ComposePolicy,
    RegistryBundle,
    RegistryComposeRequest,
    RegistryFragmentMeta,
    UnitsFragment,
    compose_registry_fragments,
)
from polisyos.ir.trinity import TrinityBundle

try:
    from hypothesis import HealthCheck, given, settings
    from hypothesis import strategies as st
except ImportError:  # pragma: no cover - optional dependency
    pytest.skip("hypothesis not installed", allow_module_level=True)

_CANON_LEAVES = (
    st.none()
    | st.booleans()
    | st.integers(min_value=-10_000, max_value=10_000)
    | st.text(max_size=24)
    | st.binary(max_size=12)
    | st.decimals(
        allow_nan=False,
        allow_infinity=False,
        min_value=Decimal("-1000"),
        max_value=Decimal("1000"),
        places=4,
    )
)

_CANON_VALUES = st.recursive(
    _CANON_LEAVES,
    lambda children: st.lists(children, max_size=4)
    | st.dictionaries(st.text(min_size=1, max_size=12), children, max_size=4),
    max_leaves=12,
)


@settings(deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(payload=_CANON_VALUES)
def test_canonical_roundtrip_and_hash_stability(payload: object) -> None:
    spec = CanonSpec(forbid_floats=False)
    encoded = to_canonical_bytes(payload, spec)
    decoded = from_canonical_bytes(encoded)

    assert to_canonical_bytes(decoded, spec) == encoded
    assert content_hash(encoded, prefix=True) == content_hash(
        to_canonical_bytes(decoded, spec),
        prefix=True,
    )


def _units_fragment(fragment_id: str, currency: str, priority: int) -> UnitsFragment:
    return UnitsFragment(
        meta=RegistryFragmentMeta(
            fragment_id=fragment_id,
            namespace="phase3.audit",
            priority=priority,
        ),
        payload=UnitsRegistry(units={"usd": MoneyUnit(currency=currency)}),
    )


@settings(deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    fragments=st.lists(
        st.tuples(
            st.sampled_from(["USD", "EUR", "CAD", "GBP"]),
            st.integers(min_value=0, max_value=100),
        ),
        min_size=1,
        max_size=6,
    )
)
def test_registry_composition_is_deterministic_across_orderings(
    fragments: list[tuple[str, int]],
) -> None:
    left = [
        _units_fragment(f"frag_{idx}", currency, priority)
        for idx, (currency, priority) in enumerate(fragments)
    ]
    right = list(reversed(left))

    request_left = RegistryComposeRequest(
        fragments=left,
        policy=ComposePolicy(mode="prefer_higher_priority"),
    )
    request_right = RegistryComposeRequest(
        fragments=right,
        policy=ComposePolicy(mode="prefer_higher_priority"),
    )

    result_left = compose_registry_fragments(request_left)
    result_right = compose_registry_fragments(request_right)

    assert result_left.applied_fragments == result_right.applied_fragments
    assert result_left.deterministic_hash == result_right.deterministic_hash
    assert result_left.model_dump(mode="json") == result_right.model_dump(mode="json")


def _base_bundle(interventions: list[InterventionSpec]) -> TrinityBundle:
    return TrinityBundle(
        problem_frame=ProblemFrame(problem_id="problem_phase3", domain=ProblemDomain.FISCAL),
        policy_spec=PolicySpec(policy_id="policy_phase3", interventions=interventions),
        model_spec=ModelSpec(
            model_id="model_phase3",
            data_snapshot_ref="sha256:" + "0" * 64,
        ),
    )


def _linker_registries() -> tuple[MechanismTypeRegistry, ConstraintRegistry]:
    mechanisms = MechanismTypeRegistry(
        mechanisms={
            "custom": MechanismTypeSpec(
                mechanism_id="custom",
                writes_slots=["global.tax_rate"],
            )
        }
    )
    constraints = ConstraintRegistry(constraints={})
    return mechanisms, constraints


@settings(deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    intervention_specs=st.lists(
        st.tuples(
            st.sampled_from(["custom", "missing_mech"]),
            st.booleans(),
            st.integers(min_value=0, max_value=3),
            st.integers(min_value=1, max_value=3),
        ),
        min_size=1,
        max_size=5,
    )
)
def test_linker_is_idempotent_for_repeated_runs(
    intervention_specs: list[tuple[str, bool, int, int]],
) -> None:
    interventions = [
        InterventionSpec(
            intervention_id=f"int_{idx}",
            kind=kind,
            target=SelectorPredicate(
                field="id" if selector_ok else "ghost",
                operator="==",
                value="all",
            ),
            schedule=ScheduleSpec(start_step=start_step, duration_steps=duration_steps),
            params={},
        )
        for idx, (kind, selector_ok, start_step, duration_steps) in enumerate(intervention_specs)
    ]
    mechanisms, constraints = _linker_registries()
    registries = RegistryBundle(
        mechanisms=mechanisms,
        slots=DEFAULT_SLOT_REGISTRY,
        merge_rules=DEFAULT_MERGE_RULE_REGISTRY,
        selector_fields=DEFAULT_SELECTOR_FIELD_REGISTRY,
        units=DEFAULT_UNITS_REGISTRY,
        metrics=DEFAULT_METRIC_REGISTRY,
        constraints=constraints,
    )

    linked_left, report_left = link_trinity(
        _base_bundle(interventions),
        registries,
    )
    linked_right, report_right = link_trinity(
        _base_bundle(interventions),
        registries,
    )

    assert linked_left.model_dump(mode="json") == linked_right.model_dump(mode="json")
    assert report_left.model_dump(mode="json") == report_right.model_dump(mode="json")

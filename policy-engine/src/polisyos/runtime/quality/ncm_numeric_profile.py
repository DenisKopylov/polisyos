"""Bound scalar polynomial evaluation, excluding NCM abduction and inference error.

This profile covers separate IEEE-754 binary64 round-to-nearest operations on
finite scalar inputs. Input bounds refer to the exact values of their binary64
representations; they do not establish measurement accuracy or upstream solver
accuracy. Decimal literals denote exact decimal coefficients for the reference
polynomial. Bounds include their conversion to binary64 and every expression
operation, including intermediates hidden by cancellation at the output.
"""

from __future__ import annotations

import ast
import math
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations
from typing import Literal

NCM_NUMERIC_PROFILE_VERSION: Literal["ncm_scalar_polynomial_binary64.v1"] = (
    "ncm_scalar_polynomial_binary64.v1"
)
NCM_INTERACTION_NUMERIC_CONTRACT_VERSION = "policyos.runtime.ncm_interaction_numeric_contract.v1"
_UNIT_ROUNDOFF = Fraction(1, 2**53)
_HALF_MIN_SUBNORMAL = Fraction(1, 2**1075)
_MAX_BINARY64 = Fraction.from_float(sys.float_info.max)
_MAX_EXPRESSION_LENGTH = 4096
_MAX_AST_NODES = 512
_MAX_AST_DEPTH = 64


class NCMNumericProfileUnsupportedError(ValueError):
    """The requested arithmetic is outside the bounded numerical profile."""


def _finite_float(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise NCMNumericProfileUnsupportedError("numeric_profile_scalar_not_binary64")
    try:
        result = float(value)
    except (OverflowError, ValueError) as exc:
        raise NCMNumericProfileUnsupportedError("numeric_profile_scalar_not_finite") from exc
    if not math.isfinite(result):
        raise NCMNumericProfileUnsupportedError("numeric_profile_scalar_not_finite")
    if isinstance(value, int) and Fraction.from_float(result) != value:
        raise NCMNumericProfileUnsupportedError("numeric_profile_input_integer_not_exact")
    return result


def _upward_float(value: Fraction) -> float:
    result = float(value)
    if Fraction.from_float(result) < value:
        result = math.nextafter(result, math.inf)
    if not math.isfinite(result):
        raise NCMNumericProfileUnsupportedError("numeric_profile_bound_not_finite")
    return result


@dataclass(frozen=True, slots=True)
class Binary64RoundoffEnvelope:
    """Exact reference interval and a conservative absolute arithmetic error.

    Composing envelopes preserves upstream errors; deriving a new bound from
    rounded endpoint magnitudes alone would lose those errors. The interval
    endpoints and error are exact rationals in the same declared outcome units.
    """

    lower: Fraction
    upper: Fraction
    absolute_error: Fraction
    operation_count: int = 0

    def __post_init__(self) -> None:
        if (
            not all(
                isinstance(value, Fraction)
                for value in (self.lower, self.upper, self.absolute_error)
            )
            or self.lower > self.upper
            or self.absolute_error < 0
            or self.operation_count < 0
        ):
            raise NCMNumericProfileUnsupportedError("numeric_profile_envelope_invalid")
        if self.maximum_magnitude + self.absolute_error > _MAX_BINARY64:
            raise NCMNumericProfileUnsupportedError(
                "numeric_profile_intermediate_overflow_possible"
            )

    @property
    def maximum_magnitude(self) -> Fraction:
        """Return the largest reference magnitude in the interval."""
        return max(abs(self.lower), abs(self.upper))

    @property
    def absolute_roundoff_bound(self) -> float:
        """Return the absolute error rounded outward, never down to a weaker bound."""
        return _upward_float(self.absolute_error)

    def add(self, other: Binary64RoundoffEnvelope) -> Binary64RoundoffEnvelope:
        """Bound one binary64 addition, including both upstream errors."""
        return self._rounded(
            self.lower + other.lower,
            self.upper + other.upper,
            self.absolute_error + other.absolute_error,
            other,
        )

    def subtract(self, other: Binary64RoundoffEnvelope) -> Binary64RoundoffEnvelope:
        """Bound one binary64 subtraction, including both upstream errors."""
        return self._rounded(
            self.lower - other.upper,
            self.upper - other.lower,
            self.absolute_error + other.absolute_error,
            other,
        )

    def multiply(self, other: Binary64RoundoffEnvelope) -> Binary64RoundoffEnvelope:
        """Bound one binary64 product, including both upstream errors."""
        products = (
            self.lower * other.lower,
            self.lower * other.upper,
            self.upper * other.lower,
            self.upper * other.upper,
        )
        upstream = (
            self.maximum_magnitude * other.absolute_error
            + other.maximum_magnitude * self.absolute_error
            + self.absolute_error * other.absolute_error
        )
        return self._rounded(min(products), max(products), upstream, other)

    def _rounded(
        self,
        lower: Fraction,
        upper: Fraction,
        upstream: Fraction,
        other: Binary64RoundoffEnvelope,
    ) -> Binary64RoundoffEnvelope:
        magnitude = max(abs(lower), abs(upper)) + upstream
        error = upstream + _UNIT_ROUNDOFF * magnitude + _HALF_MIN_SUBNORMAL
        return Binary64RoundoffEnvelope(
            lower, upper, error, self.operation_count + other.operation_count + 1
        )


def _parse(expression: str) -> ast.Expression:
    if not isinstance(expression, str) or not expression.strip():
        raise NCMNumericProfileUnsupportedError("numeric_profile_expression_missing")
    if len(expression) > _MAX_EXPRESSION_LENGTH:
        raise NCMNumericProfileUnsupportedError("numeric_profile_expression_too_large")
    try:
        tree = ast.parse(expression, mode="eval")
    except (SyntaxError, RecursionError, ValueError) as exc:
        raise NCMNumericProfileUnsupportedError("numeric_profile_expression_invalid") from exc
    if sum(1 for _ in ast.walk(tree)) > _MAX_AST_NODES:
        raise NCMNumericProfileUnsupportedError("numeric_profile_expression_too_large")
    return tree


def _literal(node: ast.Constant, expression: str) -> tuple[Fraction, Fraction]:
    if isinstance(node.value, bool) or not isinstance(node.value, int | float):
        raise NCMNumericProfileUnsupportedError("numeric_profile_literal_unsupported")
    token = ast.get_source_segment(expression, node)
    if token is None or len(token) > 128:
        raise NCMNumericProfileUnsupportedError("numeric_profile_literal_unsupported")
    token = token.replace("_", "")
    mantissa, _, exponent = token.lower().partition("e")
    if not mantissa.replace(".", "", 1).isdigit() or (exponent and abs(int(exponent)) > 1024):
        raise NCMNumericProfileUnsupportedError("numeric_profile_literal_unsupported")
    try:
        exact = Fraction(token)
        represented = float(node.value)
    except (ValueError, OverflowError) as exc:
        raise NCMNumericProfileUnsupportedError("numeric_profile_literal_not_finite") from exc
    if not math.isfinite(represented):
        raise NCMNumericProfileUnsupportedError("numeric_profile_literal_not_finite")
    return exact, abs(Fraction.from_float(represented) - exact)


def _derive_node(
    node: ast.expr,
    expression: str,
    bounds: Mapping[str, Binary64RoundoffEnvelope],
    depth: int = 0,
) -> Binary64RoundoffEnvelope:
    if depth > _MAX_AST_DEPTH:
        raise NCMNumericProfileUnsupportedError("numeric_profile_expression_too_deep")
    if isinstance(node, ast.Constant):
        exact, error = _literal(node, expression)
        return Binary64RoundoffEnvelope(exact, exact, error)
    if isinstance(node, ast.Name):
        if node.id not in bounds:
            raise NCMNumericProfileUnsupportedError("numeric_profile_variable_unbounded")
        return bounds[node.id]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.UAdd | ast.USub):
        operand = _derive_node(node.operand, expression, bounds, depth + 1)
        if isinstance(node.op, ast.UAdd):
            return operand
        return Binary64RoundoffEnvelope(
            -operand.upper, -operand.lower, operand.absolute_error, operand.operation_count
        )
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add | ast.Sub | ast.Mult):
        left = _derive_node(node.left, expression, bounds, depth + 1)
        right = _derive_node(node.right, expression, bounds, depth + 1)
        if isinstance(node.op, ast.Add):
            return left.add(right)
        if isinstance(node.op, ast.Sub):
            return left.subtract(right)
        return left.multiply(right)
    raise NCMNumericProfileUnsupportedError("numeric_profile_expression_grammar_unsupported")


def _exact_node(node: ast.expr, expression: str, values: Mapping[str, Fraction]) -> Fraction:
    if isinstance(node, ast.Constant):
        return _literal(node, expression)[0]
    if isinstance(node, ast.Name):
        return values[node.id]
    if isinstance(node, ast.UnaryOp):
        operand = _exact_node(node.operand, expression, values)
        return -operand if isinstance(node.op, ast.USub) else operand
    if isinstance(node, ast.BinOp):
        left = _exact_node(node.left, expression, values)
        right = _exact_node(node.right, expression, values)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        return left * right
    raise NCMNumericProfileUnsupportedError("numeric_profile_expression_grammar_unsupported")


@dataclass(frozen=True, slots=True)
class NCMNumericProfile:
    """Expression-derived arithmetic envelope, with declared units and inputs.

    This is a calculation helper, not an NCM admissibility or inference receipt.
    A consumer must bind the actual expression, inputs, backend, and units and
    separately validate abduction, pairing, and the retained endpoint samples.
    """

    expression: str
    variable_bounds: tuple[tuple[str, float, float], ...]
    outcome_units: str
    outcome_scale: float
    envelope: Binary64RoundoffEnvelope
    profile_version: Literal["ncm_scalar_polynomial_binary64.v1"] = NCM_NUMERIC_PROFILE_VERSION

    @property
    def absolute_roundoff_bound(self) -> float:
        """Return an outward-rounded bound in the declared outcome units."""
        return self.envelope.absolute_roundoff_bound

    def exact_value(self, values: Mapping[str, float]) -> Fraction:
        """Evaluate the exact decimal polynomial at bounded binary64 input values.

        Args:
            values: All declared variables, with no undeclared values.

        Returns:
            An exact rational reference value, without binary64 roundoff.

        Raises:
            NCMNumericProfileUnsupportedError: Inputs differ from the declared scope.
        """
        if set(values) != {name for name, _, _ in self.variable_bounds}:
            raise NCMNumericProfileUnsupportedError("numeric_profile_input_scope_mismatch")
        exact: dict[str, Fraction] = {}
        for name, lower, upper in self.variable_bounds:
            value = _finite_float(values[name])
            if not lower <= value <= upper:
                raise NCMNumericProfileUnsupportedError("numeric_profile_input_outside_bounds")
            exact[name] = Fraction.from_float(value)
        tree = _parse(self.expression)
        # Revalidate even if this value object was constructed directly.
        _derive_node(
            tree.body,
            self.expression,
            {
                name: Binary64RoundoffEnvelope(value, value, Fraction())
                for name, value in exact.items()
            },
        )
        return _exact_node(tree.body, self.expression, exact)


def derive_ncm_numeric_profile(
    expression: str,
    *,
    variable_bounds: Mapping[str, tuple[float, float]],
    outcome_units: str,
    outcome_scale: float,
) -> NCMNumericProfile:
    """Derive a pre-execution scalar polynomial roundoff envelope.

    Args:
        expression: A scalar expression using decimal constants, names, unary
            signs, addition, subtraction, and multiplication only.
        variable_bounds: Finite closed intervals of exact represented binary64
            inputs. Unknown or upstream numerical input errors are not covered.
        outcome_units: Declared unit name; its external grounding is not proven.
        outcome_scale: Positive reference magnitude in those units. This is a
            binding declaration, never a substitute for expression intermediates.

    Returns:
        The fixed-version profile and its expression-derived arithmetic bound.

    Raises:
        NCMNumericProfileUnsupportedError: Grammar, inputs, backend, or a possible
            intermediate overflow fall outside this profile.
    """
    if (
        sys.float_info.radix != 2
        or sys.float_info.mant_dig != 53
        or sys.float_info.max_exp != 1024
        or sys.float_info.rounds != 1
    ):
        raise NCMNumericProfileUnsupportedError("numeric_profile_backend_unsupported")
    if not isinstance(outcome_units, str) or not outcome_units.strip():
        raise NCMNumericProfileUnsupportedError("numeric_profile_outcome_units_missing")
    scale = _finite_float(outcome_scale)
    if scale <= 0:
        raise NCMNumericProfileUnsupportedError("numeric_profile_outcome_scale_invalid")
    if not isinstance(variable_bounds, Mapping) or any(
        not isinstance(name, str) or not name.isidentifier() for name in variable_bounds
    ):
        raise NCMNumericProfileUnsupportedError("numeric_profile_variable_name_invalid")
    normalized: list[tuple[str, float, float]] = []
    envelopes: dict[str, Binary64RoundoffEnvelope] = {}
    for name, interval in sorted(variable_bounds.items()):
        if not isinstance(interval, tuple | list) or len(interval) != 2:
            raise NCMNumericProfileUnsupportedError("numeric_profile_variable_bounds_invalid")
        lower, upper = (_finite_float(value) for value in interval)
        if lower > upper:
            raise NCMNumericProfileUnsupportedError("numeric_profile_variable_bounds_invalid")
        normalized.append((name, lower, upper))
        envelopes[name] = Binary64RoundoffEnvelope(
            Fraction.from_float(lower), Fraction.from_float(upper), Fraction()
        )
    tree = _parse(expression)
    envelope = _derive_node(tree.body, expression, envelopes)
    return NCMNumericProfile(expression, tuple(normalized), outcome_units, scale, envelope)


def _union_envelopes(
    left: Binary64RoundoffEnvelope, right: Binary64RoundoffEnvelope
) -> Binary64RoundoffEnvelope:
    return Binary64RoundoffEnvelope(
        min(left.lower, right.lower),
        max(left.upper, right.upper),
        max(left.absolute_error, right.absolute_error),
        max(left.operation_count, right.operation_count),
    )


def _sum_envelopes(values: Sequence[Binary64RoundoffEnvelope]) -> Binary64RoundoffEnvelope:
    """Cover ordered CPython 3.14 float sum, including both compensation branches."""
    high = low = Binary64RoundoffEnvelope(Fraction(), Fraction(), Fraction())
    # CPython 3.14 Python/bltinmodule.c: cs_add / cs_to_double. Keep both
    # compensation branches rather than assert their data-dependent selection.
    # https://github.com/python/cpython/blob/v3.14.0/Python/bltinmodule.c#L2564-L2602
    for value in values:
        next_high = high.add(value)
        correction = _union_envelopes(
            high.subtract(next_high).add(value), value.subtract(next_high).add(high)
        )
        low = low.add(correction)
        high = next_high
    return _union_envelopes(high, high.add(low))


def _binary64_node(node: ast.expr, values: Mapping[str, float]) -> int | float:
    """Evaluate an already-vetted AST without eval, retaining its operation order."""
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return node.value
    if isinstance(node, ast.Name):
        return values[node.id]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.UAdd | ast.USub):
        value = _binary64_node(node.operand, values)
        return -value if isinstance(node.op, ast.USub) else value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add | ast.Sub | ast.Mult):
        left, right = _binary64_node(node.left, values), _binary64_node(node.right, values)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        return left * right
    raise NCMNumericProfileUnsupportedError("numeric_profile_expression_grammar_unsupported")


def _numeric_descriptor(envelope: Binary64RoundoffEnvelope) -> dict[str, object]:
    if envelope.lower != envelope.upper:
        raise NCMNumericProfileUnsupportedError("numeric_profile_reference_not_singleton")
    return {
        "ideal": {"numerator": envelope.lower.numerator, "denominator": envelope.lower.denominator},
        "absolute_roundoff_bound": envelope.absolute_roundoff_bound,
        "roundoff_operation_count_upper_bound": envelope.operation_count,
    }


def _validate_additive_noise_expression(tree: ast.Expression, parents: tuple[str, ...]) -> None:
    names = [node.id for node in ast.walk(tree) if isinstance(node, ast.Name)]
    if names.count("u") != 1 or set(names) - {"u", *parents}:
        raise NCMNumericProfileUnsupportedError("numeric_profile_additive_noise_unsupported")
    # Accept u + P and its existing left-associated u + P1 + P2 spelling,
    # without moving operations or permitting u inside products/subtractions.
    leading = tree.body
    while isinstance(leading, ast.BinOp) and isinstance(leading.op, ast.Add):
        leading = leading.left
    if not isinstance(leading, ast.Name) or leading.id != "u" or leading is tree.body:
        raise NCMNumericProfileUnsupportedError("numeric_profile_additive_noise_unsupported")


def _normalized_interaction_scopes(
    parents: tuple[str, ...],
    scopes: Sequence[
        tuple[Literal["individual", "pairwise", "joint"], tuple[str, ...], Mapping[str, float]]
    ],
) -> tuple[tuple[str, ...], list[tuple[str, tuple[str, ...], dict[str, float]]]]:
    if not isinstance(scopes, Sequence) or isinstance(scopes, str | bytes):
        raise NCMNumericProfileUnsupportedError("numeric_profile_scope_invalid")
    normalized: list[tuple[str, tuple[str, ...], dict[str, float]]] = []
    for scope in scopes:
        if not isinstance(scope, tuple | list) or len(scope) != 3:
            raise NCMNumericProfileUnsupportedError("numeric_profile_scope_invalid")
        role, raw_atoms, raw_interventions = scope
        if (
            role not in ("individual", "pairwise", "joint")
            or not isinstance(raw_atoms, tuple | list)
            or not raw_atoms
            or any(not isinstance(atom, str) or not atom.strip() for atom in raw_atoms)
            or len(set(raw_atoms)) != len(raw_atoms)
            or not isinstance(raw_interventions, Mapping)
            or set(raw_interventions) - set(parents)
        ):
            raise NCMNumericProfileUnsupportedError("numeric_profile_scope_invalid")
        atoms = tuple(raw_atoms)
        if (role == "individual" and len(atoms) != 1) or (role == "pairwise" and len(atoms) != 2):
            raise NCMNumericProfileUnsupportedError("numeric_profile_scope_invalid")
        interventions = {
            name: _finite_float(raw_interventions[name])
            for name in parents
            if name in raw_interventions
        }
        normalized.append((role, atoms, interventions))
    joints = [atoms for role, atoms, _ in normalized if role == "joint"]
    if len(joints) != 1:
        raise NCMNumericProfileUnsupportedError("numeric_profile_joint_scope_missing")
    atoms = joints[0]
    expected = {
        *(("individual", (atom,)) for atom in atoms),
        *(("pairwise", pair) for pair in combinations(atoms, 2)),
        ("joint", atoms),
    }
    if len(normalized) != len(expected) or {(role, ids) for role, ids, _ in normalized} != expected:
        raise NCMNumericProfileUnsupportedError("numeric_profile_scope_denominator_incomplete")
    individuals = {ids[0]: mapping for role, ids, mapping in normalized if role == "individual"}
    for _, ids, actual in normalized:
        composed: dict[str, float] = {}
        for atom in ids:
            for name, value in individuals[atom].items():
                if name in composed and composed[name] != value:
                    raise NCMNumericProfileUnsupportedError("numeric_profile_intervention_conflict")
                composed[name] = value
        if actual != composed:
            raise NCMNumericProfileUnsupportedError(
                "numeric_profile_intervention_composition_mismatch"
            )
    return atoms, normalized


def build_ncm_interaction_numeric_contract(
    *,
    expression: str,
    outcome_unit: str,
    observed_noise: float,
    parent_names: Sequence[str],
    scopes: Sequence[
        tuple[Literal["individual", "pairwise", "joint"], tuple[str, ...], Mapping[str, float]]
    ],
) -> dict[str, object]:
    """Build a deterministic pre-execution fixed-input interaction descriptor.

    Args:
        expression: Exactly one leading additive ``u`` plus a parent polynomial,
            using the restricted arithmetic grammar. Existing left-associated
            ``u + P1 + P2`` expressions retain their actual AST order.
        outcome_unit: Declared outcome unit, without external grounding claims.
        observed_noise: The finite represented noise value to verify separately
            against actual NCM evidence, abduction, and paired no-op output.
        parent_names: Ordered distinct roots with baseline zero. Reserved NCM
            context aliases are inadmissible parent names.
        scopes: Ordered (role, ordered atom IDs, interventions) triples, including
            every individual and pair, and exactly one full joint scope.

    Returns:
        A JSON-ready versioned descriptor with exact rational endpoints/effects,
        pair residuals, and a conservative joint-residual bound covering both
        runtime pair formulas and ordered CPython 3.14 float summation.

    Raises:
        NCMNumericProfileUnsupportedError: The fixed-input arithmetic profile,
            complete scope denominator, or intervention composition is unsupported.
    """
    if sys.implementation.name != "cpython" or sys.version_info[:2] != (3, 14):
        raise NCMNumericProfileUnsupportedError("numeric_profile_sum_backend_unsupported")
    if not isinstance(parent_names, Sequence) or isinstance(parent_names, str | bytes):
        raise NCMNumericProfileUnsupportedError("numeric_profile_parent_scope_invalid")
    parents = tuple(parent_names)
    if (
        not parents
        or any(not isinstance(name, str) or not name.isidentifier() for name in parents)
        or len(set(parents)) != len(parents)
        or set(parents) & {"u", "noise", "deterministic", "math", "np"}
    ):
        raise NCMNumericProfileUnsupportedError("numeric_profile_parent_scope_invalid")
    noise = _finite_float(observed_noise)
    tree = _parse(expression)
    _validate_additive_noise_expression(tree, parents)
    atoms, normalized = _normalized_interaction_scopes(parents, scopes)

    def endpoint(
        interventions: Mapping[str, float], *, u: float = noise
    ) -> Binary64RoundoffEnvelope:
        values = {"u": u, **dict.fromkeys(parents, 0.0), **interventions}
        return derive_ncm_numeric_profile(
            expression,
            variable_bounds={name: (value, value) for name, value in values.items()},
            outcome_units=outcome_unit,
            outcome_scale=1.0,
        ).envelope

    zero = endpoint({}, u=0.0)
    zero_values = {"u": 0.0, **dict.fromkeys(parents, 0.0)}
    if zero.lower != 0 or _binary64_node(tree.body, zero_values) != 0.0:
        raise NCMNumericProfileUnsupportedError("numeric_profile_baseline_polynomial_not_zero")
    baseline = endpoint({})
    baseline_values = {**zero_values, "u": noise}
    if _binary64_node(tree.body, baseline_values) != noise:
        raise NCMNumericProfileUnsupportedError("numeric_profile_baseline_noise_not_preserved")
    endpoints = {(role, ids): endpoint(mapping) for role, ids, mapping in normalized}
    effects = {key: value.subtract(baseline) for key, value in endpoints.items()}
    scope_descriptors: list[dict[str, object]] = [
        {
            "role": "baseline",
            "atom_ids": [],
            "interventions": {},
            "endpoint": _numeric_descriptor(baseline),
        }
    ]
    for role, ids, mapping in normalized:
        scope_descriptors.append(
            {
                "role": role,
                "atom_ids": list(ids),
                "interventions": mapping,
                "endpoint": _numeric_descriptor(endpoints[(role, ids)]),
                "effect": _numeric_descriptor(effects[(role, ids)]),
            }
        )
    residuals: list[dict[str, object]] = []
    pair_envelopes: list[Binary64RoundoffEnvelope] = []
    for pair in combinations(atoms, 2):
        left, right = (effects[("individual", (atom,))] for atom in pair)
        pair_effect = effects[("pairwise", pair)]
        residual = _union_envelopes(
            pair_effect.subtract(left).subtract(right),
            pair_effect.subtract(_sum_envelopes((left, right))),
        )
        residuals.append(
            {"kind": "pairwise", "atom_ids": list(pair), **_numeric_descriptor(residual)}
        )
        pair_envelopes.append(residual)
    if len(atoms) >= 3:
        individual_sum = _sum_envelopes(tuple(effects[("individual", (atom,))] for atom in atoms))
        joint_residual = (
            effects[("joint", atoms)]
            .subtract(individual_sum)
            .subtract(_sum_envelopes(pair_envelopes))
        )
        residuals.append(
            {
                "kind": "order_three" if len(atoms) == 3 else "aggregate_order_three_plus",
                "atom_ids": list(atoms),
                **_numeric_descriptor(joint_residual),
            }
        )
    return {
        "schema_version": NCM_INTERACTION_NUMERIC_CONTRACT_VERSION,
        "profile_version": NCM_NUMERIC_PROFILE_VERSION,
        "scope": "one_step_fixed_input_additive_noise_polynomial_arithmetic_only",
        "sum_backend": "cpython3.14_binary64_compensated_sum_both_branches",
        "expression": expression,
        "outcome_unit": outcome_unit,
        "outcome_units_status": "declared_not_independently_grounded",
        "abduction_error_status": "not_established",
        "observed_noise": noise,
        "parent_names": list(parents),
        "atom_ids": list(atoms),
        "scopes": scope_descriptors,
        "residuals": residuals,
        "operations": {
            "effect": "endpoint-baseline",
            "pairwise": "(pair-baseline)-(left-baseline)-(right-baseline)",
            "higher_order": (
                "joint_effect-sum(ordered_individual_effects)-sum(ordered_pair_interactions)"
            ),
            "pair_orders_covered": [
                "pair_effect-left_effect-right_effect",
                "pair_effect-sum(left_effect,right_effect)",
            ],
        },
        "limitations": [
            "abduction_requires_independent_verification",
            "external_units_not_grounded",
            "stochastic_inference_not_established",
            "not_a_run_or_authority_receipt",
        ],
    }


__all__ = [
    "NCM_INTERACTION_NUMERIC_CONTRACT_VERSION",
    "NCM_NUMERIC_PROFILE_VERSION",
    "Binary64RoundoffEnvelope",
    "NCMNumericProfile",
    "NCMNumericProfileUnsupportedError",
    "build_ncm_interaction_numeric_contract",
    "derive_ncm_numeric_profile",
]

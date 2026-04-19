"""Machine-checkable dual certificates for exact LP bounds."""

from __future__ import annotations

import hashlib
import json
from itertools import product
from typing import Annotated, Any, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.canon import CanonSpec
from polisyos.ir.refs import DualCertificateRef


class SparsePrimalEntry(BaseModel):
    """One non-zero component of a sparse primal LP solution."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    index: int = Field(ge=0)
    mass: float


class LPVerificationTolerances(BaseModel):
    """Numerical tolerances for certificate validation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    primal_feasibility: float = Field(default=1e-8, gt=0.0)
    dual_feasibility: float = Field(default=1e-8, gt=0.0)
    duality_gap: float = Field(default=1e-8, gt=0.0)
    stationarity: float = Field(default=1e-8, gt=0.0)


class ResponseFunctionLPProblemSpec(BaseModel):
    """Canonical LP problem description for response-function bounds."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    problem_kind: Literal["response_function_lp"] = "response_function_lp"
    joint: tuple[tuple[float, ...], ...]
    treatment_levels: tuple[float, ...]
    outcome_levels: tuple[float, ...]
    outcome_lower: tuple[float, ...]
    outcome_upper: tuple[float, ...]
    monotone: bool = False
    target_index: int = Field(default=1, ge=0)
    reference_index: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _validate_shapes(self) -> "ResponseFunctionLPProblemSpec":
        n_treatments = len(self.treatment_levels)
        n_outcomes = len(self.outcome_levels)
        if n_treatments < 2:
            raise ValueError("response-function LP certificate requires at least two treatment levels")
        if n_outcomes < 2:
            raise ValueError("response-function LP certificate requires at least two outcome levels")
        if len(self.joint) != n_treatments:
            raise ValueError("joint row count must match treatment_levels")
        if any(len(row) != n_outcomes for row in self.joint):
            raise ValueError("each joint row must match outcome_levels length")
        if len(self.outcome_lower) != n_outcomes:
            raise ValueError("outcome_lower length must match outcome_levels")
        if len(self.outcome_upper) != n_outcomes:
            raise ValueError("outcome_upper length must match outcome_levels")
        if self.target_index >= n_treatments:
            raise ValueError("target_index out of range")
        if self.reference_index >= n_treatments:
            raise ValueError("reference_index out of range")
        return self


class BinaryIVLPProblemSpec(BaseModel):
    """Canonical LP problem description for binary Balke-Pearl bounds."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    problem_kind: Literal["binary_iv_lp"] = "binary_iv_lp"
    joint: tuple[tuple[tuple[float, ...], ...], ...]

    @model_validator(mode="after")
    def _validate_shapes(self) -> "BinaryIVLPProblemSpec":
        if len(self.joint) != 2:
            raise ValueError("binary IV certificate requires exactly two outcome levels")
        for y_slice in self.joint:
            if len(y_slice) != 2:
                raise ValueError("binary IV certificate requires exactly two treatment levels")
            for x_slice in y_slice:
                if len(x_slice) != 2:
                    raise ValueError("binary IV certificate requires exactly two instrument levels")
        return self


class GeneralIVLPProblemSpec(BaseModel):
    """Canonical LP problem description for multi-valued Balke-Pearl bounds."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    problem_kind: Literal["general_iv_lp"] = "general_iv_lp"
    joint: tuple[tuple[tuple[float, ...], ...], ...]
    n_treatment_levels: int = Field(ge=2)
    n_outcome_levels: int = Field(ge=2)
    treatment_target: int = Field(default=1, ge=0)
    treatment_ref: int = Field(default=0, ge=0)
    outcome_scale: float = Field(default=1.0, gt=0.0)

    @model_validator(mode="after")
    def _validate_shapes(self) -> "GeneralIVLPProblemSpec":
        if len(self.joint) != self.n_outcome_levels:
            raise ValueError("joint outcome axis must match n_outcome_levels")
        for y_slice in self.joint:
            if len(y_slice) != self.n_treatment_levels:
                raise ValueError("joint treatment axis must match n_treatment_levels")
            for x_slice in y_slice:
                if len(x_slice) != 2:
                    raise ValueError("general IV certificate requires a binary instrument")
        if self.treatment_target >= self.n_treatment_levels:
            raise ValueError("treatment_target out of range")
        if self.treatment_ref >= self.n_treatment_levels:
            raise ValueError("treatment_ref out of range")
        return self


DualCertificateProblemSpec = Annotated[
    ResponseFunctionLPProblemSpec | BinaryIVLPProblemSpec | GeneralIVLPProblemSpec,
    Field(discriminator="problem_kind"),
]


class LPDualCertificate(BaseModel):
    """Primal/dual witness for one LP optimization."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    certificate_kind: Literal["lp_primal_dual"] = "lp_primal_dual"
    lp_form: Literal["min_cTx_s.t._Aeqx=beq_x>=0"] = "min_cTx_s.t._Aeqx=beq_x>=0"
    problem_fingerprint: str
    bound_direction: Literal["lower", "upper"]
    primal_solution_sparse: tuple[SparsePrimalEntry, ...]
    dual_eq_marginals: tuple[float, ...]
    dual_lower_marginals: tuple[float, ...]
    objective_primal: float
    objective_dual: float
    duality_gap: float = Field(ge=0.0)
    solver: str = "scipy.linprog.highs"
    solver_status: str = "optimal"
    tolerances: LPVerificationTolerances = Field(default_factory=LPVerificationTolerances)


class BoundsDualCertificateBundle(BaseModel):
    """Pair of exact LP certificates for lower and upper bounds."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    certificate_family: Literal[
        "response_function_lp_bounds",
        "binary_iv_lp_bounds",
        "general_iv_lp_bounds",
    ] = "response_function_lp_bounds"
    problem: DualCertificateProblemSpec
    lower_cert: LPDualCertificate
    upper_cert: LPDualCertificate

    @model_validator(mode="after")
    def _validate_family_matches_problem(self) -> "BoundsDualCertificateBundle":
        family_by_problem = {
            "response_function_lp": "response_function_lp_bounds",
            "binary_iv_lp": "binary_iv_lp_bounds",
            "general_iv_lp": "general_iv_lp_bounds",
        }
        expected = family_by_problem[self.problem.problem_kind]
        if self.certificate_family != expected:
            raise ValueError(
                "certificate_family must match problem_kind "
                f"({expected} expected for {self.problem.problem_kind})"
            )
        return self


class DualCertificateValidationResult(BaseModel):
    """Validation verdict for a dual certificate bundle."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ok: bool
    errors: tuple[str, ...] = ()
    max_primal_residual: float = 0.0
    max_dual_violation: float = 0.0
    max_stationarity_residual: float = 0.0
    max_complementary_slackness: float = 0.0
    max_duality_gap: float = 0.0


def _as_float_tuple(values: np.ndarray | tuple[float, ...] | list[float]) -> tuple[float, ...]:
    return tuple(float(v) for v in np.asarray(values, dtype=float).reshape(-1))


def _as_matrix_tuple(
    matrix: np.ndarray | tuple[tuple[float, ...], ...] | list[list[float]],
) -> tuple[tuple[float, ...], ...]:
    arr = np.asarray(matrix, dtype=float)
    return tuple(tuple(float(v) for v in row) for row in arr)


def _as_tensor3_tuple(
    tensor: np.ndarray | tuple[tuple[tuple[float, ...], ...], ...] | list[list[list[float]]],
) -> tuple[tuple[tuple[float, ...], ...], ...]:
    arr = np.asarray(tensor, dtype=float)
    return tuple(
        tuple(tuple(float(v) for v in row) for row in matrix)
        for matrix in arr
    )


def _problem_fingerprint(problem: DualCertificateProblemSpec) -> str:
    payload = problem.model_dump(mode="json")
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return f"sha256:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"


def _build_problem(
    *,
    joint: np.ndarray,
    treatment_levels: np.ndarray,
    outcome_levels: np.ndarray,
    outcome_lower: np.ndarray,
    outcome_upper: np.ndarray,
    monotone: bool,
    target_index: int,
    reference_index: int,
) -> ResponseFunctionLPProblemSpec:
    return ResponseFunctionLPProblemSpec(
        joint=_as_matrix_tuple(joint),
        treatment_levels=_as_float_tuple(treatment_levels),
        outcome_levels=_as_float_tuple(outcome_levels),
        outcome_lower=_as_float_tuple(outcome_lower),
        outcome_upper=_as_float_tuple(outcome_upper),
        monotone=bool(monotone),
        target_index=int(target_index),
        reference_index=int(reference_index),
    )


def _build_constraint_system(
    problem: ResponseFunctionLPProblemSpec,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    t_levels = np.asarray(problem.treatment_levels, dtype=float)
    y_levels = np.asarray(problem.outcome_levels, dtype=float)
    y_lower = np.asarray(problem.outcome_lower, dtype=float)
    y_upper = np.asarray(problem.outcome_upper, dtype=float)
    joint = np.asarray(problem.joint, dtype=float)

    response_types: list[tuple[int, tuple[int, ...]]] = []
    lower_effects: list[float] = []
    upper_effects: list[float] = []
    for t_obs in range(len(t_levels)):
        for response_vector in product(range(len(y_levels)), repeat=len(t_levels)):
            if problem.monotone and response_vector[problem.target_index] < response_vector[problem.reference_index]:
                continue
            response_types.append((t_obs, tuple(int(v) for v in response_vector)))
            lower_effects.append(
                float(
                    y_lower[response_vector[problem.target_index]]
                    - y_upper[response_vector[problem.reference_index]]
                )
            )
            upper_effects.append(
                float(
                    y_upper[response_vector[problem.target_index]]
                    - y_lower[response_vector[problem.reference_index]]
                )
            )

    n_types = len(response_types)
    rows: list[np.ndarray] = []
    rhs: list[float] = []
    for t_obs in range(len(t_levels)):
        for y_obs in range(len(y_levels)):
            row = np.zeros(n_types, dtype=float)
            for idx, (latent_t, response_vector) in enumerate(response_types):
                if latent_t == t_obs and response_vector[t_obs] == y_obs:
                    row[idx] = 1.0
            rows.append(row)
            rhs.append(float(joint[t_obs, y_obs]))
    rows.append(np.ones(n_types, dtype=float))
    rhs.append(1.0)
    return (
        np.asarray(rows, dtype=float),
        np.asarray(rhs, dtype=float),
        np.asarray(lower_effects, dtype=float),
        -np.asarray(upper_effects, dtype=float),
    )


def _build_binary_iv_constraint_system(
    problem: BinaryIVLPProblemSpec,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    joint = np.asarray(problem.joint, dtype=float)
    n_types = 16
    rows: list[np.ndarray] = []
    rhs: list[float] = []
    for z in range(2):
        for x in range(2):
            for y in range(2):
                row = np.zeros(n_types, dtype=float)
                for r in range(n_types):
                    x_z = (r >> z) & 1
                    y_xz = (r >> (2 + x_z)) & 1
                    if x_z == x and y_xz == y:
                        row[r] = 1.0
                rows.append(row)
                rhs.append(float(joint[y, x, z]))
    rows.append(np.ones(n_types, dtype=float))
    rhs.append(1.0)
    objective = np.asarray(
        [((r >> 3) & 1) - ((r >> 2) & 1) for r in range(n_types)],
        dtype=float,
    )
    return (
        np.asarray(rows, dtype=float),
        np.asarray(rhs, dtype=float),
        objective,
        -objective,
    )


def _build_general_iv_constraint_system(
    problem: GeneralIVLPProblemSpec,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    joint = np.asarray(problem.joint, dtype=float)
    x_responses = list(product(range(problem.n_treatment_levels), repeat=2))
    y_responses = list(product(range(problem.n_outcome_levels), repeat=problem.n_treatment_levels))
    all_rfs = [(xr, yr) for xr in x_responses for yr in y_responses]
    n_rf = len(all_rfs)

    rows: list[np.ndarray] = []
    rhs: list[float] = []
    for z in range(2):
        for x in range(problem.n_treatment_levels):
            for y in range(problem.n_outcome_levels):
                row = np.zeros(n_rf, dtype=float)
                for idx, (xr, yr) in enumerate(all_rfs):
                    x_when_z = xr[z]
                    y_when_x = yr[x_when_z]
                    if x_when_z == x and y_when_x == y:
                        row[idx] = 1.0
                rows.append(row)
                rhs.append(float(joint[y, x, z]))
    rows.append(np.ones(n_rf, dtype=float))
    rhs.append(1.0)

    scale = float(problem.n_outcome_levels - 1) if problem.n_outcome_levels > 1 else 1.0
    objective = np.asarray(
        [
            (
                (yr[problem.treatment_target] - yr[problem.treatment_ref]) / scale
            ) * float(problem.outcome_scale)
            for _, yr in all_rfs
        ],
        dtype=float,
    )
    return (
        np.asarray(rows, dtype=float),
        np.asarray(rhs, dtype=float),
        objective,
        -objective,
    )


def _reconstruct_problem_system(
    problem: DualCertificateProblemSpec,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    if isinstance(problem, ResponseFunctionLPProblemSpec):
        return _build_constraint_system(problem)
    if isinstance(problem, BinaryIVLPProblemSpec):
        return _build_binary_iv_constraint_system(problem)
    if isinstance(problem, GeneralIVLPProblemSpec):
        return _build_general_iv_constraint_system(problem)
    raise TypeError(f"unsupported dual certificate problem type: {type(problem)!r}")


def _build_single_certificate(
    *,
    problem_fingerprint: str,
    bound_direction: Literal["lower", "upper"],
    objective: np.ndarray,
    result: Any,
    b_eq: np.ndarray,
    sparse_tol: float = 1e-12,
) -> LPDualCertificate:
    x = np.asarray(result.x, dtype=float)
    y = np.asarray(result.eqlin.marginals, dtype=float)
    lower_marginals = np.asarray(result.lower.marginals, dtype=float)
    objective_primal = float(np.dot(objective, x))
    objective_dual = float(np.dot(b_eq, y))
    sparse_entries = tuple(
        SparsePrimalEntry(index=int(idx), mass=float(value))
        for idx, value in enumerate(x)
        if abs(float(value)) > sparse_tol
    )
    return LPDualCertificate(
        problem_fingerprint=problem_fingerprint,
        bound_direction=bound_direction,
        primal_solution_sparse=sparse_entries,
        dual_eq_marginals=tuple(float(v) for v in y),
        dual_lower_marginals=tuple(float(v) for v in lower_marginals),
        objective_primal=objective_primal,
        objective_dual=objective_dual,
        duality_gap=float(abs(objective_primal - objective_dual)),
        solver_status=str(getattr(result, "message", getattr(result, "status", "optimal"))),
    )


def build_response_function_dual_certificate_bundle(
    *,
    joint: np.ndarray,
    treatment_levels: np.ndarray,
    outcome_levels: np.ndarray,
    outcome_lower: np.ndarray,
    outcome_upper: np.ndarray,
    monotone: bool,
    target_index: int,
    reference_index: int,
    lower_result: Any,
    upper_result: Any,
) -> BoundsDualCertificateBundle:
    """Build a validated exact-LP certificate bundle from HiGHS results."""

    problem = _build_problem(
        joint=np.asarray(joint, dtype=float),
        treatment_levels=np.asarray(treatment_levels, dtype=float),
        outcome_levels=np.asarray(outcome_levels, dtype=float),
        outcome_lower=np.asarray(outcome_lower, dtype=float),
        outcome_upper=np.asarray(outcome_upper, dtype=float),
        monotone=bool(monotone),
        target_index=int(target_index),
        reference_index=int(reference_index),
    )
    return _build_certificate_bundle_from_problem(
        problem=problem,
        certificate_family="response_function_lp_bounds",
        lower_result=lower_result,
        upper_result=upper_result,
    )


def build_binary_iv_dual_certificate_bundle(
    *,
    joint: np.ndarray,
    lower_result: Any,
    upper_result: Any,
) -> BoundsDualCertificateBundle:
    """Build a validated exact-LP certificate bundle for binary Balke-Pearl bounds."""

    problem = BinaryIVLPProblemSpec(joint=_as_tensor3_tuple(joint))
    return _build_certificate_bundle_from_problem(
        problem=problem,
        certificate_family="binary_iv_lp_bounds",
        lower_result=lower_result,
        upper_result=upper_result,
    )


def build_general_iv_dual_certificate_bundle(
    *,
    joint: np.ndarray,
    n_treatment_levels: int,
    n_outcome_levels: int,
    treatment_target: int,
    treatment_ref: int,
    outcome_scale: float,
    lower_result: Any,
    upper_result: Any,
) -> BoundsDualCertificateBundle:
    """Build a validated exact-LP certificate bundle for multi-valued IV bounds."""

    problem = GeneralIVLPProblemSpec(
        joint=_as_tensor3_tuple(joint),
        n_treatment_levels=int(n_treatment_levels),
        n_outcome_levels=int(n_outcome_levels),
        treatment_target=int(treatment_target),
        treatment_ref=int(treatment_ref),
        outcome_scale=float(outcome_scale),
    )
    return _build_certificate_bundle_from_problem(
        problem=problem,
        certificate_family="general_iv_lp_bounds",
        lower_result=lower_result,
        upper_result=upper_result,
    )


def _build_certificate_bundle_from_problem(
    *,
    problem: DualCertificateProblemSpec,
    certificate_family: Literal[
        "response_function_lp_bounds",
        "binary_iv_lp_bounds",
        "general_iv_lp_bounds",
    ],
    lower_result: Any,
    upper_result: Any,
) -> BoundsDualCertificateBundle:
    if int(getattr(lower_result, "status", -1)) != 0:
        raise ValueError("lower_result must be optimal to build a dual certificate")
    if int(getattr(upper_result, "status", -1)) != 0:
        raise ValueError("upper_result must be optimal to build a dual certificate")

    fingerprint = _problem_fingerprint(problem)
    A_eq, b_eq, lower_objective, upper_objective = _reconstruct_problem_system(problem)
    bundle = BoundsDualCertificateBundle(
        certificate_family=certificate_family,
        problem=problem,
        lower_cert=_build_single_certificate(
            problem_fingerprint=fingerprint,
            bound_direction="lower",
            objective=lower_objective,
            result=lower_result,
            b_eq=b_eq,
        ),
        upper_cert=_build_single_certificate(
            problem_fingerprint=fingerprint,
            bound_direction="upper",
            objective=upper_objective,
            result=upper_result,
            b_eq=b_eq,
        ),
    )
    validation = validate_dual_certificate_bundle(bundle)
    if not validation.ok:
        raise ValueError(
            "dual certificate validation failed: "
            + "; ".join(validation.errors)
        )
    return bundle


def _validate_single_certificate(
    *,
    cert: LPDualCertificate,
    objective: np.ndarray,
    A_eq: np.ndarray,
    b_eq: np.ndarray,
    problem_fingerprint: str,
) -> tuple[list[str], float, float, float, float, float]:
    errors: list[str] = []
    n_vars = int(objective.shape[0])
    x = np.zeros(n_vars, dtype=float)
    seen: set[int] = set()
    for entry in cert.primal_solution_sparse:
        if entry.index >= n_vars:
            errors.append(f"{cert.bound_direction}: primal index {entry.index} out of range")
            continue
        if entry.index in seen:
            errors.append(f"{cert.bound_direction}: duplicate primal index {entry.index}")
            continue
        seen.add(entry.index)
        x[entry.index] = float(entry.mass)

    y = np.asarray(cert.dual_eq_marginals, dtype=float)
    d = np.asarray(cert.dual_lower_marginals, dtype=float)
    if y.shape[0] != A_eq.shape[0]:
        errors.append(
            f"{cert.bound_direction}: dual_eq_marginals length {y.shape[0]} != {A_eq.shape[0]}"
        )
        y = np.zeros(A_eq.shape[0], dtype=float)
    if d.shape[0] != n_vars:
        errors.append(
            f"{cert.bound_direction}: dual_lower_marginals length {d.shape[0]} != {n_vars}"
        )
        d = np.zeros(n_vars, dtype=float)

    if cert.problem_fingerprint != problem_fingerprint:
        errors.append(f"{cert.bound_direction}: problem_fingerprint mismatch")

    primal_residual = float(np.max(np.abs(A_eq @ x - b_eq)))
    nonneg_violation = float(max(0.0, -float(np.min(x))))
    reduced_costs = objective - (A_eq.T @ y)
    dual_violation = float(max(0.0, -float(np.min(reduced_costs))))
    stationarity_residual = float(np.max(np.abs(d - reduced_costs)))
    comp_slackness = float(np.max(np.abs(x * d)))
    primal_objective = float(np.dot(objective, x))
    dual_objective = float(np.dot(b_eq, y))
    duality_gap = float(abs(primal_objective - dual_objective))
    primal_objective_residual = float(abs(primal_objective - cert.objective_primal))
    dual_objective_residual = float(abs(dual_objective - cert.objective_dual))
    stored_gap_residual = float(abs(duality_gap - cert.duality_gap))

    tol = cert.tolerances
    if max(primal_residual, nonneg_violation) > tol.primal_feasibility:
        errors.append(
            f"{cert.bound_direction}: primal infeasible "
            f"(residual={primal_residual:.3e}, nonneg={nonneg_violation:.3e})"
        )
    if dual_violation > tol.dual_feasibility:
        errors.append(
            f"{cert.bound_direction}: dual infeasible (violation={dual_violation:.3e})"
        )
    if stationarity_residual > tol.stationarity:
        errors.append(
            f"{cert.bound_direction}: stationarity failed (residual={stationarity_residual:.3e})"
        )
    if comp_slackness > tol.stationarity:
        errors.append(
            f"{cert.bound_direction}: complementary slackness failed "
            f"(residual={comp_slackness:.3e})"
        )
    if max(
        duality_gap,
        primal_objective_residual,
        dual_objective_residual,
        stored_gap_residual,
    ) > tol.duality_gap:
        errors.append(
            f"{cert.bound_direction}: duality/objective mismatch "
            f"(gap={duality_gap:.3e}, primal_obj={primal_objective_residual:.3e}, "
            f"dual_obj={dual_objective_residual:.3e}, stored_gap={stored_gap_residual:.3e})"
        )

    return (
        errors,
        max(primal_residual, nonneg_violation),
        dual_violation,
        stationarity_residual,
        comp_slackness,
        duality_gap,
    )


def validate_dual_certificate_bundle(
    bundle: BoundsDualCertificateBundle,
) -> DualCertificateValidationResult:
    """Reconstruct the exact LP and validate the stored primal/dual witnesses."""

    problem_fingerprint = _problem_fingerprint(bundle.problem)
    A_eq, b_eq, lower_objective, upper_objective = _reconstruct_problem_system(bundle.problem)

    lower_errors, lower_primal, lower_dual, lower_stationarity, lower_slack, lower_gap = (
        _validate_single_certificate(
            cert=bundle.lower_cert,
            objective=lower_objective,
            A_eq=A_eq,
            b_eq=b_eq,
            problem_fingerprint=problem_fingerprint,
        )
    )
    upper_errors, upper_primal, upper_dual, upper_stationarity, upper_slack, upper_gap = (
        _validate_single_certificate(
            cert=bundle.upper_cert,
            objective=upper_objective,
            A_eq=A_eq,
            b_eq=b_eq,
            problem_fingerprint=problem_fingerprint,
        )
    )

    errors = tuple(lower_errors + upper_errors)
    return DualCertificateValidationResult(
        ok=not errors,
        errors=errors,
        max_primal_residual=max(lower_primal, upper_primal),
        max_dual_violation=max(lower_dual, upper_dual),
        max_stationarity_residual=max(lower_stationarity, upper_stationarity),
        max_complementary_slackness=max(lower_slack, upper_slack),
        max_duality_gap=max(lower_gap, upper_gap),
    )


def persist_dual_certificate_bundle(
    store: ArtifactStore,
    bundle: BoundsDualCertificateBundle,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.dual_certificate",
    schema_version: str = "1.0",
) -> DualCertificateRef:
    """Persist a dual-certificate bundle as a CAS-backed JSON artifact."""

    ref = put_json_artifact(
        store,
        bundle.model_dump(mode="json"),
        kind="ir.dual_certificate",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return DualCertificateRef.model_validate(ref)


def load_dual_certificate_bundle(
    store: ArtifactStore,
    ref: DualCertificateRef,
) -> BoundsDualCertificateBundle:
    """Load a persisted dual-certificate bundle."""

    payload = get_json_artifact(store, ref.artifact_id)
    return BoundsDualCertificateBundle.model_validate(payload)


def hydrate_bounds_bundle_with_dual_certificate(
    store: ArtifactStore,
    bundle: Any,
    certificate_payload: BoundsDualCertificateBundle | dict[str, Any] | None,
    *,
    inputs: list[InputRef] | None = None,
) -> tuple[Any, list[InputRef]]:
    """Validate, persist, and attach an optional dual certificate to a BoundsBundle."""

    from polisyos.ir.analytics.partial_identification import (  # noqa: PLC0415
        BoundsBundle,
        attach_dual_certificate_ref,
    )

    resolved_bundle = (
        bundle if isinstance(bundle, BoundsBundle) else BoundsBundle.model_validate(bundle)
    )
    resolved_inputs = list(inputs or [])
    bundle_warnings = list(resolved_bundle.warnings)
    if certificate_payload is None:
        return resolved_bundle, resolved_inputs

    try:
        cert_bundle = (
            certificate_payload
            if isinstance(certificate_payload, BoundsDualCertificateBundle)
            else BoundsDualCertificateBundle.model_validate(certificate_payload)
        )
        validation = validate_dual_certificate_bundle(cert_bundle)
        if validation.ok:
            cert_ref = persist_dual_certificate_bundle(
                store,
                cert_bundle,
                inputs=resolved_inputs,
            )
            resolved_bundle = attach_dual_certificate_ref(resolved_bundle, cert_ref)
            resolved_inputs.append(
                InputRef(
                    artifact_id=cert_ref.artifact_id,
                    role="dual_certificate",
                )
            )
        else:
            bundle_warnings.append("dual_certificate_validation_failed")
            bundle_warnings.extend(validation.errors)
    except Exception as exc:
        bundle_warnings.append(f"dual_certificate_error:{exc.__class__.__name__}: {exc}")

    if bundle_warnings != list(resolved_bundle.warnings):
        resolved_bundle = resolved_bundle.model_copy(update={"warnings": bundle_warnings})
    return resolved_bundle, resolved_inputs


__all__ = [
    "BinaryIVLPProblemSpec",
    "BoundsDualCertificateBundle",
    "DualCertificateValidationResult",
    "GeneralIVLPProblemSpec",
    "hydrate_bounds_bundle_with_dual_certificate",
    "LPDualCertificate",
    "LPVerificationTolerances",
    "ResponseFunctionLPProblemSpec",
    "SparsePrimalEntry",
    "build_binary_iv_dual_certificate_bundle",
    "build_general_iv_dual_certificate_bundle",
    "build_response_function_dual_certificate_bundle",
    "load_dual_certificate_bundle",
    "persist_dual_certificate_bundle",
    "validate_dual_certificate_bundle",
]

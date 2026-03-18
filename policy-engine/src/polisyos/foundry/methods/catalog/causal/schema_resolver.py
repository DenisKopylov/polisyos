"""SchemaResolver — binds DataFrame schema to EstimandAST variables.

Resolves variable names from a dataset to the variables required by an EstimandAST,
checks type compatibility, and validates support conditions.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SchemaResolutionReport(BaseModel):
    """Result of resolving DataFrame columns to EstimandAST variables."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    resolved_variables: dict[str, str] = Field(default_factory=dict)
    """Maps estimand variable name → matching DataFrame column name."""

    missing_variables: list[str] = Field(default_factory=list)
    """Estimand variables not found in the DataFrame columns."""

    type_mismatches: list[str] = Field(default_factory=list)
    """Columns whose dtype is incompatible with the expected role."""

    support_warnings: list[str] = Field(default_factory=list)
    """Warnings about potential support / positivity issues."""

    is_feasible: bool = True
    """True when all estimand variables are resolved with no type mismatches."""


_NUMERIC_DTYPES = frozenset(
    {"int8", "int16", "int32", "int64", "float16", "float32", "float64",
     "uint8", "uint16", "uint32", "uint64", "Int64", "Float64", "number"}
)

_BINARY_DTYPES = frozenset(
    {"int8", "int16", "int32", "int64", "uint8", "bool", "boolean",
     "Int8", "Int16", "Int32", "Int64"}
)


class SchemaResolver:
    """Resolves EstimandAST variable names to DataFrame columns."""

    def resolve(
        self,
        ast: object,   # EstimandAST — use object to avoid circular import
        df_columns: list[str],
        df_dtypes: dict[str, str],
        *,
        binary_treatment_min_prevalence: float = 0.05,
        treatment_prevalence_hint: dict[str, float] | None = None,
    ) -> SchemaResolutionReport:
        """Resolve estimand variables to DataFrame columns.

        Args:
            ast: EstimandAST instance.
            df_columns: List of column names available in the DataFrame.
            df_dtypes: Mapping {column_name: dtype_str}.
            binary_treatment_min_prevalence: Minimum acceptable treatment prevalence.
            treatment_prevalence_hint: Optional {variable_name: prevalence} for warnings.

        Returns:
            SchemaResolutionReport
        """
        from polisyos.ir.analytics.estimand import EstimandAST, SideConditionKind

        if not isinstance(ast, EstimandAST):
            return SchemaResolutionReport(
                missing_variables=[],
                type_mismatches=["ast is not an EstimandAST instance"],
                support_warnings=[],
                is_feasible=False,
            )

        # Collect all variable names needed by the estimand
        all_vars: set[str] = set()
        for dr in ast.collect_distribution_refs():
            all_vars.update(dr.variables)
            all_vars.update(dr.conditioning)
            all_vars.update(dr.intervention_set)

        col_lower = {c.lower(): c for c in df_columns}

        resolved: dict[str, str] = {}
        missing: list[str] = []
        type_issues: list[str] = []
        warnings: list[str] = []

        for var in sorted(all_vars):
            # Exact match first
            if var in df_columns:
                resolved[var] = var
            elif var.lower() in col_lower:
                resolved[var] = col_lower[var.lower()]
            else:
                missing.append(var)
                continue

            # Type check for resolved variables
            col = resolved[var]
            dtype = df_dtypes.get(col, "")

            # Check if we can determine the role from side conditions
            is_treatment_var = _is_treatment_var(ast, var)
            is_outcome_var = _is_outcome_var(ast, var)

            if is_outcome_var and dtype and not _is_numeric(dtype):
                type_issues.append(
                    f"Outcome variable '{var}' maps to column '{col}' with dtype '{dtype}' "
                    f"(expected numeric)"
                )
            if is_treatment_var:
                # Check side conditions for binary treatment
                for dr in ast.collect_distribution_refs():
                    for sc in dr.side_conditions:
                        if sc.kind == SideConditionKind.POSITIVITY:
                            if dtype and not _is_binary_compatible(dtype):
                                type_issues.append(
                                    f"Treatment variable '{var}' has POSITIVITY condition "
                                    f"but column '{col}' dtype '{dtype}' is not binary-compatible"
                                )
                            # Check prevalence
                            if treatment_prevalence_hint and var in treatment_prevalence_hint:
                                prev = treatment_prevalence_hint[var]
                                if prev < binary_treatment_min_prevalence:
                                    warnings.append(
                                        f"Treatment '{var}' prevalence {prev:.3f} is below "
                                        f"minimum {binary_treatment_min_prevalence:.3f} "
                                        f"(positivity concern)"
                                    )
                            break

        # General support warnings from side conditions
        for dr in ast.collect_distribution_refs():
            for sc in dr.side_conditions:
                if sc.kind == SideConditionKind.OVERLAP:
                    warnings.append(
                        f"OVERLAP assumption required for variables {list(dr.variables)}: "
                        "verify covariate support overlap between treatment and control groups"
                    )
                    break

        is_feasible = len(missing) == 0 and len(type_issues) == 0

        return SchemaResolutionReport(
            resolved_variables=resolved,
            missing_variables=missing,
            type_mismatches=type_issues,
            support_warnings=warnings,
            is_feasible=is_feasible,
        )

    def resolve_multi_domain(
        self,
        ast: object,
        source_columns: list[str],
        target_columns: list[str],
        source_dtypes: dict[str, str],
        target_dtypes: dict[str, str],
        **kwargs,
    ) -> SchemaResolutionReport:
        """Resolve for multi-domain setting (source + target datasets).

        Returns a merged SchemaResolutionReport combining issues from both domains.
        """
        from polisyos.ir.analytics.estimand import EstimandAST

        if not isinstance(ast, EstimandAST):
            return SchemaResolutionReport(is_feasible=False)

        # Resolve source distributions
        source_report = self.resolve(ast, source_columns, source_dtypes, **kwargs)

        # Resolve target distributions
        target_report = self.resolve(ast, target_columns, target_dtypes, **kwargs)

        # Merge: resolved = union, missing = those missing in EITHER
        merged_resolved = {**source_report.resolved_variables, **target_report.resolved_variables}
        source_missing = set(source_report.missing_variables)
        target_missing = set(target_report.missing_variables)
        merged_missing = sorted(source_missing | target_missing)

        merged_mismatches = source_report.type_mismatches + [
            f"[target] {m}" for m in target_report.type_mismatches
        ]
        merged_warnings = source_report.support_warnings + [
            f"[target] {w}" for w in target_report.support_warnings
        ]

        is_feasible = len(merged_missing) == 0 and len(merged_mismatches) == 0

        return SchemaResolutionReport(
            resolved_variables=merged_resolved,
            missing_variables=merged_missing,
            type_mismatches=merged_mismatches,
            support_warnings=merged_warnings,
            is_feasible=is_feasible,
        )


def _is_treatment_var(ast: object, var: str) -> bool:
    """Heuristic: check if var appears in treatment role of the estimand."""
    try:
        for dr in ast.collect_distribution_refs():
            if var in dr.intervention_set:
                return True
        # AST-level treatment attribute is a single string
        if hasattr(ast, "treatment") and ast.treatment == var:
            return True
    except Exception:
        pass
    return False


def _is_outcome_var(ast: object, var: str) -> bool:
    """Heuristic: check if var appears in outcome role of the estimand."""
    try:
        # AST-level outcome attribute is a single string
        if hasattr(ast, "outcome") and ast.outcome == var:
            return True
        for dr in ast.collect_distribution_refs():
            if var in dr.variables and var not in dr.conditioning and var not in dr.intervention_set:
                return True
    except Exception:
        pass
    return False


def _is_numeric(dtype: str) -> bool:
    dtype_lower = dtype.lower()
    return any(t in dtype_lower for t in ("int", "float", "num", "double", "decimal"))


def _is_binary_compatible(dtype: str) -> bool:
    dtype_lower = dtype.lower()
    # float dtypes can hold binary (0/1) values — allow them
    return any(t in dtype_lower for t in ("int", "bool", "uint", "float", "double"))


__all__ = ["SchemaResolutionReport", "SchemaResolver"]

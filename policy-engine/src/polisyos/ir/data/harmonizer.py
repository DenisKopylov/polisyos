"""DomainHarmonizer — align source/target DataFrames for causal transportability.

Maps source DataFrame columns to canonical target variables, detects type
mismatches, and applies strategies for missing variables.  The result is a
frozen :class:`HarmonizationReport` consumed by downstream components
(notably :meth:`DataKnowledgeBase.from_harmonized`).

Design
------
- All IR models are frozen Pydantic (``extra="forbid"``) — project standard.
- ``DomainHarmonizer.align()`` is a pure static function; no mutable state.
- pandas is imported lazily inside ``align()`` so that the module is safe to
  import in environments that only have pandas as an optional dependency.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    import pandas as pd


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class MissingVariableStrategy(str, Enum):
    """Strategy applied when a target variable is absent from the source dataset."""

    IMPUTE_MEAN = "impute_mean"
    """Fill with the mean of the closest available numeric source column (or 0.0
    if none exists).  Records the imputed value in :attr:`MissingVariableRecord.imputed_value`."""

    IMPUTE_MODEL = "impute_model"
    """Reserved for model-based imputation.  Raises :exc:`NotImplementedError`
    until a concrete implementation is provided."""

    EXCLUDE_UNIT = "exclude_unit"
    """Drop the variable from the harmonized schema.  Records the variable in
    :attr:`HarmonizationReport.excluded_variables`."""

    RAISE_ERROR = "raise_error"
    """Append an error message to :attr:`HarmonizationReport.errors`, making
    :attr:`HarmonizationReport.is_compatible` return ``False``."""


# ---------------------------------------------------------------------------
# Dtype helpers
# ---------------------------------------------------------------------------

_NUMERIC_KINDS = frozenset("iufcb")  # int, uint, float, complex, bool


def _is_numeric_dtype(dtype_str: str) -> bool:
    """Return True if the dtype kind character is numeric (numpy convention)."""
    # dtype_str is something like "int64", "float32", "object", "bool"
    import numpy as np  # noqa: PLC0415

    try:
        kind = np.dtype(dtype_str).kind
    except TypeError:
        return False
    return kind in _NUMERIC_KINDS


def _coercibility(src: str, tgt: str) -> tuple[bool, str | None]:
    """Return (is_coercible, coercion_description_or_None).

    Rules:
    - identical dtypes         → (True, None)           [no coercion needed]
    - numeric ↔ numeric        → (True, "src→tgt")
    - non-numeric ↔ numeric    → (False, None)
    - non-numeric ↔ non-numeric → (True, None)           [both string-like, treat as pass]
    """
    if src == tgt:
        return True, None
    src_num = _is_numeric_dtype(src)
    tgt_num = _is_numeric_dtype(tgt)
    if src_num and tgt_num:
        return True, f"{src}→{tgt}"
    if src_num != tgt_num:
        # one numeric, one not
        return False, None
    # both non-numeric (object ↔ object variants)
    return True, None


# ---------------------------------------------------------------------------
# Report models
# ---------------------------------------------------------------------------


class ResolvedMapping(BaseModel):
    """A source column successfully mapped to a target variable."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_column: str
    """Column name in the source DataFrame."""

    target_variable: str
    """Variable name in the target schema."""

    source_dtype: str
    """dtype string of the source column (e.g. ``"int64"``)."""

    target_dtype: str
    """dtype string of the target column (e.g. ``"float64"``)."""

    type_coercion: str | None = None
    """Human-readable coercion description (e.g. ``"int64→float64"``).
    ``None`` when source and target dtypes are identical."""


class TypeMismatch(BaseModel):
    """A type incompatibility detected between source and target."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    target_variable: str
    source_dtype: str
    target_dtype: str
    is_coercible: bool
    """``True`` for numeric↔numeric mismatches that can be safely cast."""
    coercion_applied: str | None = None
    """Description of the coercion if ``is_coercible`` and auto-coercion was
    recorded (e.g. ``"int64→float64"``)."""


class MissingVariableRecord(BaseModel):
    """A target variable absent from the source dataset, with its resolution."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    target_variable: str
    strategy_applied: MissingVariableStrategy
    imputed_value: float | None = None
    """Mean value used when ``strategy_applied == IMPUTE_MEAN``."""


class HarmonizationReport(BaseModel):
    """Frozen audit record produced by :meth:`DomainHarmonizer.align`.

    Downstream consumers use this to:
    - Determine which target variables are ready for causal analysis
      (:attr:`harmonized_variables`).
    - Detect data quality issues (:attr:`type_mismatches`, :attr:`warnings`).
    - Gate on data compatibility (:attr:`is_compatible`).
    - Build a :class:`DataKnowledgeBase` via ``DataKnowledgeBase.from_harmonized()``.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_dataset_ref: str
    target_dataset_ref: str

    resolved_mappings: tuple[ResolvedMapping, ...]
    """Mappings that were successfully established (including coercible ones)."""

    type_mismatches: tuple[TypeMismatch, ...]
    """Type mismatches found during mapping.  Coercible mismatches are still
    included in :attr:`harmonized_variables`; non-coercible ones are excluded."""

    missing_variables: tuple[MissingVariableRecord, ...]
    """Target variables not covered by ``variable_mapping``."""

    harmonized_variables: tuple[str, ...]
    """Target variable names that are usable for analysis after harmonization."""

    excluded_variables: tuple[str, ...] = ()
    """Variables dropped due to :attr:`MissingVariableStrategy.EXCLUDE_UNIT` or
    non-coercible type mismatches."""

    n_source_obs: int | None = None
    n_target_obs: int | None = None

    warnings: tuple[str, ...] = ()
    """Non-fatal issues (e.g. unknown source columns in the mapping dict)."""

    errors: tuple[str, ...] = ()
    """Fatal issues — non-empty when :attr:`MissingVariableStrategy.RAISE_ERROR`
    was triggered."""

    @property
    def is_compatible(self) -> bool:
        """``True`` iff there are no fatal errors preventing harmonization."""
        return len(self.errors) == 0


# ---------------------------------------------------------------------------
# Harmonizer
# ---------------------------------------------------------------------------


class DomainHarmonizer:
    """Align a source DataFrame to a target variable schema.

    All logic is in the :meth:`align` static method; the class has no state.
    """

    @staticmethod
    def align(
        source_df: "pd.DataFrame",
        target_df: "pd.DataFrame",
        variable_mapping: dict[str, str],
        *,
        missing_strategy: MissingVariableStrategy = MissingVariableStrategy.RAISE_ERROR,
        source_dataset_ref: str = "source",
        target_dataset_ref: str = "target",
    ) -> HarmonizationReport:
        """Align *source_df* columns to the schema of *target_df*.

        Parameters
        ----------
        source_df:
            Source domain DataFrame.
        target_df:
            Target domain DataFrame that defines the canonical variable schema.
            Only its columns and dtypes are used — its rows are not inspected.
        variable_mapping:
            ``{source_column: target_variable}`` dict.  Every entry is
            validated: missing source columns produce warnings, unknown target
            variables produce warnings.
        missing_strategy:
            Strategy applied to target variables not covered by any mapping.
        source_dataset_ref, target_dataset_ref:
            Identifiers embedded in the returned report.

        Returns
        -------
        HarmonizationReport
            Frozen report describing what was resolved, what mismatched, and
            what variables are ready for causal analysis.
        """
        resolved: list[ResolvedMapping] = []
        mismatches: list[TypeMismatch] = []
        harmonized: list[str] = []          # target variable names
        excluded: list[str] = []
        warnings: list[str] = []
        errors: list[str] = []

        # Track which target variables are covered by an explicit mapping
        covered_targets: set[str] = set()

        # ------------------------------------------------------------------
        # Phase 1: process explicit variable_mapping
        # ------------------------------------------------------------------
        for src_col, tgt_var in variable_mapping.items():
            # Validate source column exists
            if src_col not in source_df.columns:
                warnings.append(
                    f"Source column '{src_col}' not found in source_df — skipped."
                )
                continue
            # Validate target variable exists
            if tgt_var not in target_df.columns:
                warnings.append(
                    f"Target variable '{tgt_var}' not found in target_df — skipped."
                )
                continue

            src_dtype = str(source_df[src_col].dtype)
            tgt_dtype = str(target_df[tgt_var].dtype)
            is_coercible, coercion = _coercibility(src_dtype, tgt_dtype)

            resolved.append(
                ResolvedMapping(
                    source_column=src_col,
                    target_variable=tgt_var,
                    source_dtype=src_dtype,
                    target_dtype=tgt_dtype,
                    type_coercion=coercion,
                )
            )

            if src_dtype != tgt_dtype:
                mismatches.append(
                    TypeMismatch(
                        target_variable=tgt_var,
                        source_dtype=src_dtype,
                        target_dtype=tgt_dtype,
                        is_coercible=is_coercible,
                        coercion_applied=coercion,
                    )
                )

            if is_coercible:
                harmonized.append(tgt_var)
            else:
                excluded.append(tgt_var)
                warnings.append(
                    f"Variable '{tgt_var}': dtype '{src_dtype}' cannot be "
                    f"coerced to '{tgt_dtype}' — excluded from harmonized_variables."
                )

            covered_targets.add(tgt_var)

        # ------------------------------------------------------------------
        # Phase 2: handle target variables not covered by the mapping
        # ------------------------------------------------------------------
        missing_records: list[MissingVariableRecord] = []

        for tgt_var in target_df.columns:
            if tgt_var in covered_targets:
                continue

            if missing_strategy is MissingVariableStrategy.IMPUTE_MEAN:
                # Use first available numeric source column as proxy; fall back to 0.0
                imputed_value: float | None = None
                tgt_dtype_str = str(target_df[tgt_var].dtype)
                if _is_numeric_dtype(tgt_dtype_str):
                    numeric_cols = [
                        c for c in source_df.columns
                        if _is_numeric_dtype(str(source_df[c].dtype))
                    ]
                    if numeric_cols:
                        imputed_value = float(source_df[numeric_cols[0]].mean())
                    else:
                        imputed_value = 0.0
                missing_records.append(
                    MissingVariableRecord(
                        target_variable=tgt_var,
                        strategy_applied=MissingVariableStrategy.IMPUTE_MEAN,
                        imputed_value=imputed_value,
                    )
                )
                harmonized.append(tgt_var)

            elif missing_strategy is MissingVariableStrategy.IMPUTE_MODEL:
                raise NotImplementedError(
                    "IMPUTE_MODEL strategy is reserved for future model-based imputation. "
                    "Use IMPUTE_MEAN, EXCLUDE_UNIT, or RAISE_ERROR instead."
                )

            elif missing_strategy is MissingVariableStrategy.EXCLUDE_UNIT:
                missing_records.append(
                    MissingVariableRecord(
                        target_variable=tgt_var,
                        strategy_applied=MissingVariableStrategy.EXCLUDE_UNIT,
                    )
                )
                excluded.append(tgt_var)

            elif missing_strategy is MissingVariableStrategy.RAISE_ERROR:
                missing_records.append(
                    MissingVariableRecord(
                        target_variable=tgt_var,
                        strategy_applied=MissingVariableStrategy.RAISE_ERROR,
                    )
                )
                errors.append(
                    f"Target variable '{tgt_var}' has no mapping in source_df "
                    f"and missing_strategy=RAISE_ERROR."
                )

        return HarmonizationReport(
            source_dataset_ref=source_dataset_ref,
            target_dataset_ref=target_dataset_ref,
            resolved_mappings=tuple(resolved),
            type_mismatches=tuple(mismatches),
            missing_variables=tuple(missing_records),
            harmonized_variables=tuple(dict.fromkeys(harmonized)),  # preserve order, deduplicate
            excluded_variables=tuple(dict.fromkeys(excluded)),
            n_source_obs=len(source_df),
            n_target_obs=len(target_df),
            warnings=tuple(warnings),
            errors=tuple(errors),
        )


__all__ = [
    "MissingVariableStrategy",
    "ResolvedMapping",
    "TypeMismatch",
    "MissingVariableRecord",
    "HarmonizationReport",
    "DomainHarmonizer",
]

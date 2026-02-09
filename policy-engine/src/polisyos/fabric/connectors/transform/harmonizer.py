"""
Code harmonization transformations for mapping between code systems.

Handles country codes, industry codes, and custom mappings with
vectorized pandas operations for performance.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from polisyos.fabric.connectors.transform._common import (
    build_lineage,
    copy_if_needed,
    stage_started_at,
)
from polisyos.fabric.connectors.transform.pipeline import (
    DataTransform,
    TransformContext,
    TransformError,
    TransformLineage,
)

__all__ = ["CodeHarmonizationTransform", "load_mapping_table"]


@dataclass
class CodeHarmonizationTransform(DataTransform):
    """
    Map codes between different classification systems.

    Unmapped codes can be:
    1. Kept as-is (warn_unmapped=True)
    2. Converted to NaN (drop_unmapped=True)
    3. Raise an error (strict=True)
    """

    dimension: str
    target_codelist: str
    mapping: dict[str, str] | None = None
    drop_unmapped: bool = False
    warn_unmapped: bool = True
    strict: bool = False

    def __post_init__(self) -> None:
        if self.strict and self.drop_unmapped:
            raise ValueError("Cannot have both strict=True and drop_unmapped=True")
        if self.mapping is None:
            self.mapping = {}

    @property
    def name(self) -> str:
        return f"harmonize_{self.dimension}"

    def apply(
        self,
        data: pd.DataFrame,
        context: TransformContext,
    ) -> tuple[pd.DataFrame, TransformLineage, list[str]]:
        start_time = stage_started_at()
        result, _ = copy_if_needed(data, context)

        if self.dimension not in result.columns:
            raise TransformError(f"Dimension '{self.dimension}' not found in data")

        series = result[self.dimension]
        null_mask = series.isna()

        # Map to string keys for consistency
        mapped = series.astype(str).map(self.mapping)
        mapped = mapped.where(~null_mask, series)

        unmapped_mask = mapped.isna() & ~null_mask
        unmapped_codes = sorted(series[unmapped_mask].astype(str).unique().tolist())

        if unmapped_codes and self.strict:
            raise TransformError(f"Unmapped codes in '{self.dimension}': {unmapped_codes}")

        if self.drop_unmapped:
            result[self.dimension] = mapped
        else:
            result[self.dimension] = mapped.where(~unmapped_mask, series)

        mapping_stats = {
            "mapped_count": int((~mapped.isna() & ~null_mask).sum()),
            "unmapped_count": int(unmapped_mask.sum()),
            "null_count": int(null_mask.sum()),
        }

        warnings: list[str] = []
        if unmapped_codes and self.warn_unmapped:
            preview = unmapped_codes[:10]
            suffix = "..." if len(unmapped_codes) > 10 else ""
            warnings.append(f"Found {len(unmapped_codes)} unmapped codes: {preview}{suffix}")

        lineage = build_lineage(
            stage_name=self.name,
            started_at=start_time,
            input_data=data,
            output_data=result,
            parameters={
                "dimension": self.dimension,
                "target_codelist": self.target_codelist,
                "mapping_size": len(self.mapping),
                "mapped_count": mapping_stats["mapped_count"],
                "unmapped_count": mapping_stats["unmapped_count"],
                "null_count": mapping_stats["null_count"],
                "unmapped_codes": unmapped_codes[:20],
            },
        )

        return result, lineage, warnings

    def validate_input(
        self,
        data: pd.DataFrame,
        context: TransformContext,
    ) -> list[str]:
        errors: list[str] = []
        if self.dimension not in data.columns:
            errors.append(f"Dimension '{self.dimension}' not found in data")
        return errors

    def validate_output(
        self,
        data: pd.DataFrame,
        context: TransformContext,
    ) -> list[str]:
        warnings: list[str] = []
        if self.dimension in data.columns:
            null_pct = data[self.dimension].isna().mean()
            if self.drop_unmapped and null_pct > 0.3:
                warnings.append(
                    f"High unmapped rate: {null_pct:.1%} of '{self.dimension}' "
                    f"codes could not be mapped to {self.target_codelist}"
                )
        return warnings


# =============================================================================
# Utility Functions
# =============================================================================


def load_mapping_table(
    path: str,
    source_col: str = "source",
    target_col: str = "target",
) -> dict[str, str]:
    """
    Load code mapping from CSV file.

    Expected CSV format:
        source,target
        US,USA
        GB,GBR
    """
    df = pd.read_csv(path)

    if source_col not in df.columns:
        raise ValueError(f"Source column '{source_col}' not found in {path}")
    if target_col not in df.columns:
        raise ValueError(f"Target column '{target_col}' not found in {path}")

    return dict(zip(df[source_col].astype(str), df[target_col].astype(str)))

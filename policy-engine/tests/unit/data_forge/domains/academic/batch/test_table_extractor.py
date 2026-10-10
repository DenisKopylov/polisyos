from __future__ import annotations

from polisyos.data_forge.domains.academic.batch.table_extractor import (
    _parse_numeric_cell,
    tables_to_parameters,
)


def test_numeric_table_cell_conversion_preserves_estimate_uncertainty_and_source() -> None:
    raw_cell = "0.21 (0.03)* [0.14, 0.28]"
    parsed = {
        "value": 0.21,
        "significance_stars": 1,
        "std_error": 0.03,
        "confidence_interval": [0.14, 0.28],
    }

    assert _parse_numeric_cell(raw_cell) == parsed
    assert _parse_numeric_cell(f"  {raw_cell}  ") == parsed
    assert _parse_numeric_cell("estimate not reported") is None

    parameters = tables_to_parameters(
        [
            {
                "numeric_cells": [
                    {"header": "Wage effect", **parsed},
                ]
            }
        ],
        openalex_id="W123",
    )

    assert len(parameters) == 1
    assert parameters[0] == {
        "name": "wage_effect",
        "display_name": "Wage effect",
        "parameter_type": "quantitative",
        "value": 0.21,
        "unit": "",
        "evidence_strength": "unknown",
        "source": "table_extraction",
        "openalex_id": "W123",
        "std_error": 0.03,
        "confidence_interval": [0.14, 0.28],
    }

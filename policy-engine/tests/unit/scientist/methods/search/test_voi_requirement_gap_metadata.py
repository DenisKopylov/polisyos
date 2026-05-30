from __future__ import annotations

# ruff: noqa: S101
from polisyos.scientist.methods.search.voi_models import acquisition_voi_metadata


def test_voi_metadata_names_compiled_requirement_gap_subject() -> None:
    metadata = acquisition_voi_metadata(
        requirement_gap_id="requirement-gap:data_requirement:data-requirement:claim",
        acquisition_strategy="source_contract_remediation",
        requirement_family="data_requirement",
    )

    assert metadata == {
        "requirement_gap_id": "requirement-gap:data_requirement:data-requirement:claim",
        "acquisition_strategy": "source_contract_remediation",
        "ranking_subject": "compiled_requirement_gap",
        "requirement_family": "data_requirement",
    }

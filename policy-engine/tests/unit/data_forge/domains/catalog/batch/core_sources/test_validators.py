from __future__ import annotations

from polisyos.data_forge.domains.catalog.batch import core_sources_ingest as facade
from polisyos.data_forge.domains.catalog.batch.core_sources import validators


def test_core_sources_validators_keep_year_window_behavior() -> None:
    assert validators._year_windows(2020, 2022, 2) == [(2020, 2021), (2022, 2022)]
    assert facade._year_windows(2020, 2020, 2) == [(2020, 2020)]


"""A concrete falsifier for the declared non-atomic filesystem custody limit.

A successful test completes a controlled diagnostic. Its JSON records whether
foreign rows were actually accepted; completion alone is not a custody verdict
or a grant of production/source authority.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from polisyos.data_forge.domains.catalog.knowledge import store as store_module
from tests.unit.data_forge.domains.catalog.knowledge.test_variable_availability import _catalog


def test_declared_native_open_aba_residual_observes_foreign_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "catalog.duckdb"
    foreign = tmp_path / "foreign.duckdb"
    retained = tmp_path / "retained-a.duckdb"
    _catalog(database, populated=True)
    _catalog(foreign, populated=False)
    expected_a = hashlib.sha256(database.read_bytes()).hexdigest()
    expected_b = hashlib.sha256(foreign.read_bytes()).hexdigest()
    control_a = store_module.DatasetCatalogStore(database, database.parent)
    control_b = store_module.DatasetCatalogStore(foreign, foreign.parent)
    try:
        before_a = control_a.variable_availability_counts("government.balance")
        before_b = control_b.variable_availability_counts("government.balance")
    finally:
        control_a.close()
        control_b.close()
    assert before_a == (2, 2, 1)
    assert before_b == (0, 0, 0)
    original_open = store_module.open_catalog_read_session

    def substitute_for_only_the_native_open(path: Path, *, overlay_path: Path | None = None):
        database.replace(retained)
        foreign.replace(database)
        try:
            connection = original_open(path, overlay_path=overlay_path)
        finally:
            database.replace(foreign)
            retained.replace(database)
        return connection

    monkeypatch.setattr(
        store_module, "open_catalog_read_session", substitute_for_only_the_native_open
    )
    reader = store_module.DatasetCatalogStore(database, database.parent)
    try:
        observed = reader.variable_availability_counts("government.balance")
        pinned = reader.database_identity.content_sha256
    finally:
        reader.close()
    assert expected_a != expected_b
    assert hashlib.sha256(database.read_bytes()).hexdigest() == expected_a
    assert pinned == "sha256:" + expected_a
    assert observed in (before_a, before_b)
    attack_observed = observed == before_b
    evidence = {
        "classification": (
            "observed_declared_unsupported_non_atomic_custody_case"
            if attack_observed
            else "controlled_attack_not_observed_no_general_custody_claim"
        ),
        "attack_observed": attack_observed,
        "pinned_source_sha256": expected_a,
        "opened_foreign_sha256": expected_b,
        "actual_count_tuple": observed,
        "control_a_counts": before_a,
        "control_b_counts": before_b,
        "source_after_sha256": hashlib.sha256(database.read_bytes()).hexdigest(),
        "atomic_custody": "not_established",
        "authority": "not_granted",
    }
    (tmp_path / "aba-residual-witness.json").write_text(json.dumps(evidence, indent=2) + "\n")

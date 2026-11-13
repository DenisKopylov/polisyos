"""Retained recovery refuses missing creation inputs before opening a Runtime."""

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from tests._helpers.candidate_experiment_retained_recovery import retained_candidate_runtime


@pytest.mark.parametrize(
    "fault", ["missing_job", "foreign_kind", "missing_creation", "duplicate_creation"]
)
def test_retained_runtime_refuses_incomplete_sql_selection_without_repair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    fixture = tmp_path / "retained"
    (fixture / ".polisyos").mkdir(parents=True)
    database = fixture / ".polisyos/control_plane.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE control_jobs (job_id TEXT, job_kind TEXT, payload_ref TEXT, run_id TEXT)"
        )
        connection.execute(
            "CREATE TABLE control_job_events (job_id TEXT, event_type TEXT, payload_json TEXT)"
        )
        if fault != "missing_job":
            connection.execute(
                "INSERT INTO control_jobs VALUES (?, ?, ?, ?)",
                (
                    "old",
                    "natural_language_run" if fault == "foreign_kind" else "acquisition",
                    "ref",
                    "run",
                ),
            )
        if fault == "duplicate_creation":
            connection.executemany(
                "INSERT INTO control_job_events VALUES (?, ?, ?)",
                [("old", "job_created", "{}"), ("old", "job_created", "{}")],
            )
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    expected = (
        "retained_candidate_acquisition_job_missing"
        if fault in {"missing_job", "foreign_kind"}
        else "retained_candidate_creation_scope_ambiguous"
    )

    with (
        pytest.raises(ValueError, match=expected),
        retained_candidate_runtime(
            fixture_root=fixture,
            job_id="old",
            output_root=tmp_path / "new",
            monkeypatch=monkeypatch,
        ),
    ):
        raise AssertionError("incomplete selection entered Runtime")

    assert hashlib.sha256(database.read_bytes()).hexdigest() == before
    assert not (fixture / "cas").exists()
    assert not (tmp_path / "new/public-reconstruction.json").exists()


@pytest.mark.parametrize("missing", ["registry", "provision", "l5", "baseline"])
def test_retained_runtime_refuses_absent_issuer_without_creating_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, missing: str
) -> None:
    from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
        DEFAULT_ACQUISITION_AUTHORITY_PROVISION,
        DEFAULT_ACQUISITION_AUTHORITY_REGISTRY,
        DEFAULT_L5_MEASUREMENT_REGISTRY,
    )

    fixture = tmp_path / "retained"
    (fixture / ".polisyos").mkdir(parents=True)
    database = fixture / ".polisyos/control_plane.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE control_jobs (job_id TEXT, job_kind TEXT, payload_ref TEXT, run_id TEXT)"
        )
        connection.execute(
            "CREATE TABLE control_job_events (job_id TEXT, event_type TEXT, payload_json TEXT)"
        )
        connection.execute("INSERT INTO control_jobs VALUES ('old', 'acquisition', 'ref', 'run')")
        connection.execute(
            "INSERT INTO control_job_events VALUES ('old', 'job_created', ?)",
            (json.dumps({"execution_scope": {"tenant_id": "tenant", "cell_id": "cell"}}),),
        )
    issuer = fixture / "candidate-issuer/repo"
    selected = {
        "registry": DEFAULT_ACQUISITION_AUTHORITY_REGISTRY,
        "provision": DEFAULT_ACQUISITION_AUTHORITY_PROVISION,
        "l5": DEFAULT_L5_MEASUREMENT_REGISTRY,
        "baseline": Path("catalog/catalog.duckdb"),
    }
    for name, relative in selected.items():
        if name != missing:
            path = issuer / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"retained input is never opened after a missing sibling")
    before = {str(p): p.read_bytes() for p in fixture.rglob("*") if p.is_file()}

    with (
        pytest.raises(ValueError, match="retained_candidate_issuer_inputs_missing"),
        retained_candidate_runtime(
            fixture_root=fixture,
            job_id="old",
            output_root=tmp_path / "new",
            monkeypatch=monkeypatch,
        ),
    ):
        raise AssertionError("missing issuer entered Runtime")

    assert {str(p): p.read_bytes() for p in fixture.rglob("*") if p.is_file()} == before
    assert not (fixture / "cas").exists()
    assert not (tmp_path / "new/public-reconstruction.json").exists()

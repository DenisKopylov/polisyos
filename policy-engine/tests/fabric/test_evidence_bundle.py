from pathlib import Path

import pytest

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.contracts.fabric import FabricResult
from polisyos.fabric.ingestion import run_ingestion


def test_fabric_result_requires_evidence() -> None:
    # evidence_ref теперь обязателен: отсутствие должно падать валидацией
    with pytest.raises(Exception):
        FabricResult(  # type: ignore[arg-type]
            request_ref={},  # missing
            plan_ref={},
            data_ref={},
        )


def test_run_ingestion_writes_evidence(tmp_path: Path) -> None:
    pytest.importorskip("kuzu")
    raw_dir = tmp_path / "raw"
    staging_dir = tmp_path / "staging"
    curated_dir = tmp_path / "curated"
    raw_dir.mkdir()
    staging_dir.mkdir()
    curated_dir.mkdir()

    # minimal raw CSVs
    (raw_dir / "macro.csv").write_text(
        "run_id,step,gdp,unemployment_rate,inflation_rate,avg_price,avg_income,government_balance\n"
        "demo_run,0,1,2,3,4,5,6\n",
        encoding="utf-8",
    )
    (raw_dir / "agents.csv").write_text(
        "agent_id,agent_type,age,income,savings,is_employed\n"
        "a,worker,30,1000,5000,True\n",
        encoding="utf-8",
    )
    (raw_dir / "interactions.csv").write_text(
        "from_id,to_id,step,amount,type\n"
        "a,a,0,1.0,transfer\n",
        encoding="utf-8",
    )

    db_path = tmp_path / "simulation.duckdb"
    kuzu_path = tmp_path / "graph.kuzu"
    cas_root = tmp_path / ".polisyos"

    evidence_ref = run_ingestion(
        raw_dir=raw_dir,
        staging_dir=staging_dir,
        curated_dir=curated_dir,
        db_path=db_path,
        kuzu_path=kuzu_path,
        source="test",
        license_name="test",
        clear_on_start=True,
        cas_root=cas_root,
    )
    assert evidence_ref is not None

    # evidence артефакт доступен через CAS
    from polisyos.core.artifacts.store import FileSystemCAS

    store = FileSystemCAS(cas_root)
    manifest = store.get_manifest(ArtifactID.model_validate(evidence_ref.artifact_id))
    assert manifest.kind == "fabric.evidence_bundle"

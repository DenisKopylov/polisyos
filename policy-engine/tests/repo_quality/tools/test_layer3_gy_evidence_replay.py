"""Replay/reproducibility guarantee for GY Task 0 evidence hashes.

The first census smokes baked wall-clock timing into the hashed blob, so re-runs
produced a different `output_hash` (presence evidence, not replay evidence).
`tools/quality/validation/gy_evidence_canon.canonical_evidence_hash` fixes this by
stripping volatile timing fields before hashing. These tests are CI-safe (no
production catalog required) and prove the methodology is now time-invariant and
deterministic. A catalog-backed re-derivation runs only when production_data is
present.
"""
from __future__ import annotations

import json
from importlib import import_module
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
CENSUS_PATH = (
    REPO_ROOT / "architecture" / "policy_design_case" / "layer3_gy_task0_audit"
    / "layer3_gy_engine_census.json"
)
PROD_CATALOG = (
    REPO_ROOT / "production_data" / "datasets_full_phase3full_20260327_183054"
    / "dataset_catalog.duckdb"
)


def _canon() -> Any:
    return import_module("tools.quality.validation.gy_evidence_canon")


def test_timing_does_not_affect_hash() -> None:
    h = _canon().canonical_evidence_hash
    a = {"returned": 8, "ms": 7247.2, "vector_ms": 0.0, "top": [{"id": "x", "sim": 1.0}]}
    b = {"returned": 8, "ms": 11.9, "vector_ms": 3.3, "top": [{"id": "x", "sim": 1.0}]}
    assert h(a) == h(b)


def test_timestamps_do_not_affect_hash() -> None:
    h = _canon().canonical_evidence_hash
    a = {"result": "ok", "generated_at": "2026-06-14T09:00:00Z", "duration_ms": 12}
    b = {"result": "ok", "generated_at": "2026-06-14T14:30:00Z", "duration_ms": 999}
    assert h(a) == h(b)


def test_hash_is_deterministic_and_prefixed() -> None:
    h = _canon().canonical_evidence_hash
    payload = {"results": {"q": ["a", "b", "c"]}}
    out = h(payload)
    assert out == h(payload)
    assert out.startswith("sha256:") and len(out) == len("sha256:") + 64


def test_content_change_does_change_hash() -> None:
    h = _canon().canonical_evidence_hash
    assert h({"results": {"q": ["a", "b"]}}) != h({"results": {"q": ["a", "c"]}})


def test_production_replay_proof_is_three_level_and_content_bound() -> None:
    from polisyos.runtime.quality.authority import build_outcome_replay_proof

    contract = {
        "terminal_state": {
            "kind": "search_ceiling_repair_required",
            "reason": "measured recall is below the governed threshold",
        },
        "search_ledger": {
            "invocations": [{"operation_id": "slice0.bind.catalog", "status": "completed"}],
            "events": [{"event_type": "terminal_state_selected"}],
        },
        "incompleteness_record": {"search_quality": {"recall_at_known_seeds": 0.0}},
        "artifact_envelopes": [],
        "authority_boundary": None,
    }
    proof = build_outcome_replay_proof(
        case_id="ua-msme-affordable-loans-2022",
        input_payloads={"sha256:" + "a" * 64: {"case_id": "ua-msme"}},
        search_exit_contract=contract,
        output_cas_refs=["sha256:" + "b" * 64],
    )

    assert proof.replay_levels == ["A", "B", "C"]
    assert [level.level for level in proof.level_proofs] == ["A", "B", "C"]
    assert all(level.status == "verified" for level in proof.level_proofs)
    assert proof.output_hash == _canon().canonical_evidence_hash(contract)
    assert proof.input_hashes


def test_production_replay_output_hash_is_time_invariant() -> None:
    from polisyos.runtime.quality.authority import build_outcome_replay_proof

    base = {
        "terminal_state": {"kind": "search_ceiling_repair_required"},
        "search_ledger": {"invocations": [], "events": []},
        "incompleteness_record": {},
        "artifact_envelopes": [],
        "authority_boundary": None,
        "generated_at": "2026-06-24T09:00:00Z",
    }
    replayed = {**base, "generated_at": "2031-01-01T00:00:00Z"}

    first = build_outcome_replay_proof(
        case_id="ua-msme-affordable-loans-2022",
        input_payloads={"input": {"created_at": "2026-01-01T00:00:00Z", "value": 1}},
        search_exit_contract=base,
        output_cas_refs=[],
    )
    second = build_outcome_replay_proof(
        case_id="ua-msme-affordable-loans-2022",
        input_payloads={"input": {"created_at": "2030-01-01T00:00:00Z", "value": 1}},
        search_exit_contract=replayed,
        output_cas_refs=[],
    )

    assert first.input_hashes == second.input_hashes
    assert first.output_hash == second.output_hash


def test_strip_volatile_drops_timing_keys() -> None:
    stripped = _canon().strip_volatile({"keep": 1, "ms": 2, "x_ms": 3, "created_at": "z", "top": [{"sim": 1, "took_ms": 9}]})
    assert stripped == {"keep": 1, "top": [{"sim": 1}]}


def test_census_search_rows_use_reproducible_hash() -> None:
    census = json.loads(CENSUS_PATH.read_text(encoding="utf-8"))
    search_rows = [
        r for r in census["rows"]
        if r["asset_id"].startswith("data_forge.DatasetCatalog")
        and (r.get("execution_evidence") or {}).get("output_hash")
    ]
    assert search_rows, "expected catalog search rows in the census"
    for r in search_rows:
        ev = r["execution_evidence"]
        assert ev.get("reproducible") is True, f"{r['asset_id']} not marked reproducible"
        assert str(ev["output_hash"]).startswith("sha256:")


@pytest.mark.skipif(not PROD_CATALOG.exists(), reason="production catalog not present")
def test_search_evidence_hash_replays_against_catalog() -> None:
    """When the catalog is present, the recorded search hash must re-derive identically."""
    import sys
    sys.path.insert(0, str(REPO_ROOT / "src"))
    try:
        from loguru import logger as _l  # type: ignore
        _l.remove()
    except Exception:
        pass
    from polisyos.data_forge.domains.catalog.knowledge.search import DatasetCatalogGraph

    base = PROD_CATALOG.parent
    qs = [
        "credit access affordable loans",
        "firm survival business continuity",
        "credit program enrollment loan participation",
    ]

    def proj() -> dict[str, Any]:
        g = DatasetCatalogGraph(base / "dataset_catalog.duckdb", base)
        return {
            "evidence_projection": "returned_dataset_ids_top8_time_and_score_stripped",
            "results": {q: [r.id for r in g.search_datasets(q, top_k=8)] for q in qs},
        }

    h = _canon().canonical_evidence_hash
    first = h(proj())
    assert first == h(proj()), "search evidence hash is not reproducible across runs"

    census = json.loads(CENSUS_PATH.read_text(encoding="utf-8"))
    recorded = {
        (r.get("execution_evidence") or {}).get("output_hash")
        for r in census["rows"]
        if r["asset_id"].startswith("data_forge.DatasetCatalog")
    }
    assert first in recorded, f"re-derived {first} not in recorded search hashes {recorded}"

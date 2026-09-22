"""CYC-05 witnesses for typed recursive limits and structural receipts."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from polisyos.pdc import gy_content_hash
from polisyos.runtime.http.services.control.generation_cycle import (
    _build_cycle_substrate_context_from_owner,
)
from polisyos.runtime.quality.generation_cycle import (
    GenerationCycleController,
    GenerationCycleError,
    StrangleReceipt,
    validate_generation_cycle_run,
)
from polisyos.runtime.quality.recursive_generation_cycle import (
    recompute_depth_n_strangle_receipt,
)
from tests.unit.runtime.quality.test_generation_cycle import (
    _CgfGenerationPort,
    _DataGapValuePort,
    _budget,
    _problem,
)


def _source_root(root: Path) -> Path:
    source = root / "src" / "polisyos"
    source.mkdir(parents=True)
    return source


def test_depth_n_strangle_receipt_fails_closed_when_source_is_missing(tmp_path: Path) -> None:
    """An absent controlled source slice cannot produce positive strangle evidence."""

    receipt = recompute_depth_n_strangle_receipt(tmp_path)

    assert receipt.status == "not_established"
    assert receipt.source_state == "missing"
    assert receipt.source_content_hash is None
    assert receipt.parse_errors == ()
    assert receipt.production_fixture_callers == ()
    assert receipt.production_default_routes == ()
    assert receipt.default_controller == "unresolved"


def test_generation_cycle_strangle_receipt_fails_closed_when_source_is_missing(
    tmp_path: Path,
) -> None:
    """The actual N6 owner must not promote an absent source denominator."""

    receipt = StrangleReceipt.recompute(tmp_path)

    assert receipt.status == "not_established"
    assert receipt.source_state == "missing"
    assert receipt.source_content_hash is None
    assert receipt.source_file_count == 0
    assert receipt.parse_errors == ()


def test_generation_cycle_strangle_receipt_separates_parse_error_from_caller(
    tmp_path: Path,
) -> None:
    """The actual N6 owner keeps parse failure distinct from caller drift."""

    source = _source_root(tmp_path)
    (source / "broken.py").write_text("def broken(:\n", encoding="utf-8")

    receipt = StrangleReceipt.recompute(tmp_path)

    assert receipt.status == "not_established"
    assert receipt.source_state == "parse_error"
    assert receipt.source_content_hash is None
    assert receipt.source_file_count == 1
    assert receipt.production_single_pass_callers == ()
    assert any("src/polisyos/broken.py" in item for item in receipt.parse_errors)


def test_generation_cycle_receipt_replay_requires_explicit_source_root(tmp_path: Path) -> None:
    """Receipt replay must not silently inspect the process working directory."""

    source = _source_root(tmp_path)
    (source / "owner.py").write_text("def owner():\n    return None\n", encoding="utf-8")
    receipt = StrangleReceipt.recompute(tmp_path)

    with pytest.raises(
        GenerationCycleError,
        match="generation_cycle_strangle_receipt_currentness_not_established",
    ):
        receipt.verify_current()


def test_generation_cycle_receipt_recompute_without_root_is_not_established() -> None:
    """Receipt production must not adopt the process cwd as a source checkout."""

    receipt = StrangleReceipt.recompute()

    assert receipt.status == "not_established"
    assert receipt.source_state == "not_established"
    assert receipt.source_content_hash is None


def test_generation_cycle_receipt_replay_binds_bounded_limitations(tmp_path: Path) -> None:
    """Replay must bind the declared bounded census limitations as well as bytes."""

    source = _source_root(tmp_path)
    (source / "owner.py").write_text("def owner():\n    return None\n", encoding="utf-8")
    receipt = StrangleReceipt.recompute(tmp_path)
    changed_limitations = receipt.model_copy(
        update={"limitation_refs": ("build_identity_unavailable",)}
    )

    with pytest.raises(GenerationCycleError, match="generation_cycle_strangle_receipt_stale"):
        changed_limitations.verify_current(tmp_path)


def test_http_owner_context_requires_explicit_source_root() -> None:
    """HTTP source-owner preparation must not inspect the process cwd."""

    problem = _problem("cyc_05_http_rootless_context")
    problem_ref = gy_content_hash(problem.model_dump(mode="json"))

    assert (
        _build_cycle_substrate_context_from_owner(
            problem=problem,
            problem_ref=problem_ref,
            repo_root=None,
        )
        is None
    )


@pytest.mark.asyncio
async def test_generation_cycle_consumer_keeps_missing_source_non_positive(
    tmp_path: Path,
) -> None:
    """The real N6 consumer must retain a missing-source refusal."""

    run = await GenerationCycleController(
        generation_port=_CgfGenerationPort(),
        value_port=_DataGapValuePort(),
        repo_root=tmp_path,
        authority_scope="contract_testing",
    ).run(
        _problem("cyc_05_missing_source_consumer"),
        budget_state=_budget(),
        max_cycles=1,
    )

    issues = validate_generation_cycle_run(run, repo_root=tmp_path)
    assert "strangle_receipt_currentness_not_established" in {
        issue["code"] for issue in issues
    }


@pytest.mark.asyncio
async def test_generation_cycle_consumer_keeps_parse_error_non_positive(
    tmp_path: Path,
) -> None:
    """The real N6 consumer must retain a parse-error refusal."""

    source = _source_root(tmp_path)
    (source / "broken.py").write_text("def broken(:\n", encoding="utf-8")
    run = await GenerationCycleController(
        generation_port=_CgfGenerationPort(),
        value_port=_DataGapValuePort(),
        repo_root=tmp_path,
        authority_scope="contract_testing",
    ).run(
        _problem("cyc_05_parse_error_consumer"),
        budget_state=_budget(),
        max_cycles=1,
    )

    issues = validate_generation_cycle_run(run, repo_root=tmp_path)
    assert "strangle_receipt_currentness_not_established" in {
        issue["code"] for issue in issues
    }


def test_depth_n_strangle_receipt_separates_parse_error_from_prohibited_caller(
    tmp_path: Path,
) -> None:
    """A syntax error is an unestablished denominator, not a caller finding."""

    source = _source_root(tmp_path)
    (source / "broken.py").write_text("def broken(:\n", encoding="utf-8")

    receipt = recompute_depth_n_strangle_receipt(tmp_path)

    assert receipt.status == "not_established"
    assert receipt.source_state == "parse_error"
    assert receipt.source_content_hash is None
    assert receipt.production_fixture_callers == ()
    assert any("src/polisyos/broken.py" in item for item in receipt.parse_errors)


def test_depth_n_strangle_receipt_binds_available_slice_and_invalidates_on_change(
    tmp_path: Path,
) -> None:
    """A real caller is drift, and any source-slice change yields a new receipt identity."""

    source = _source_root(tmp_path)
    (source / "route.py").write_text(
        "def route():\n"
        "    return build_default_recursive_generation_cycle_controller()\n",
        encoding="utf-8",
    )
    (source / "legacy.py").write_text(
        "def route():\n"
        "    return run_recursive_case()\n",
        encoding="utf-8",
    )

    receipt = recompute_depth_n_strangle_receipt(tmp_path)

    assert receipt.status == "drift"
    assert receipt.source_state == "available"
    assert receipt.source_content_hash is not None
    assert receipt.parse_errors == ()
    assert receipt.production_fixture_callers == (
        "src/polisyos/legacy.py:2:call:run_recursive_case",
    )
    assert receipt.production_default_routes == (
        "src/polisyos/route.py:2:call:build_default_recursive_generation_cycle_controller",
    )
    original_hash = receipt.source_content_hash

    (source / "route.py").write_text(
        "def route():\n"
        "    # meaningful source-slice change\n"
        "    return build_default_recursive_generation_cycle_controller()\n",
        encoding="utf-8",
    )
    changed = recompute_depth_n_strangle_receipt(tmp_path)

    assert changed.source_state == "available"
    assert changed.source_content_hash is not None
    assert changed.source_content_hash != original_hash


@pytest.mark.asyncio
async def test_generation_cycle_consumer_rejects_stale_source_receipt(tmp_path: Path) -> None:
    """The actual N6 run consumer must reject a receipt after source drift."""

    source = _source_root(tmp_path)
    (source / "owner.py").write_text("def owner():\n    return None\n", encoding="utf-8")
    controller = GenerationCycleController(
        generation_port=_CgfGenerationPort(),
        value_port=_DataGapValuePort(),
        repo_root=tmp_path,
        authority_scope="contract_testing",
    )

    run = await controller.run(
        _problem("cyc_05_source_bound_run"),
        budget_state=_budget(),
        max_cycles=1,
    )
    receipt = run.strangle_receipt
    source_files = {
        path.relative_to(tmp_path).as_posix(): "sha256:"
        + hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted((tmp_path / "src" / "polisyos").rglob("*.py"))
    }
    assert receipt.status == "strangled"
    assert receipt.source_state == "available"
    assert receipt.source_file_count == len(source_files)
    assert receipt.source_content_hash == gy_content_hash(
        {"scope": "src/polisyos", "files": source_files}
    )
    unchecked_issues = validate_generation_cycle_run(run)
    assert {
        "strangle_receipt_currentness_not_established"
    } <= {issue["code"] for issue in unchecked_issues}
    assert validate_generation_cycle_run(run, repo_root=tmp_path) == ()

    (source / "owner.py").write_text(
        "def owner():\n    return 'changed'\n",
        encoding="utf-8",
    )
    with pytest.raises(GenerationCycleError, match="generation_cycle_strangle_receipt_stale"):
        run.strangle_receipt.verify_current(tmp_path)
    issues = validate_generation_cycle_run(run, repo_root=tmp_path)
    assert {issue["code"] for issue in issues} >= {"strangle_receipt_stale"}

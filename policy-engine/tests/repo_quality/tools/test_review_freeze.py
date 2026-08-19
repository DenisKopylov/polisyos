from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tools.quality.testing import build_review_package as review_package
from tools.quality.testing import review_freeze

REVIEW_FREEZE_SCRIPT = Path(review_freeze.__file__).resolve()


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run Git in a temporary fixture repository."""

    return subprocess.run(  # noqa: S603 - controlled test argv.
        [
            "git",
            "-c",
            "user.name=PolicyOS Test",
            "-c",
            "user.email=policyos-test@example.invalid",
            *args,
        ],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


def _commit(repo: Path, message: str, *paths: str) -> str:
    """Commit explicit fixture paths and return the full commit identifier."""

    _git(repo, "add", *paths)
    _git(repo, "commit", "--no-gpg-sign", "-m", message)
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _init_repo(tmp_path: Path, *, name: str = "review-freeze-repo") -> tuple[Path, str, str]:
    """Create a real repository with a reviewed implementation commit."""

    repo = tmp_path / name
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    (repo / ".gitignore").write_text("/tmp/\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text("[project]\nname = 'fixture'\n", encoding="utf-8")
    base = _commit(repo, "initial", ".gitignore", "pyproject.toml")
    source = repo / "src" / "engine.py"
    source.parent.mkdir()
    source.write_text("import os\nimport json\n\nVALUE = 1\n", encoding="utf-8")
    head = _commit(repo, "complete implementation", "src/engine.py")
    return repo, base, head


def _ledger(repo: Path) -> Path:
    """Return the protocol-owned, commit-required ledger path for one fixture."""

    return repo / ".e11" / "gy-def6.ledger"


def _ledger_for(repo: Path, lane_id: str) -> Path:
    """Return the canonical per-lane transcript path enforced by the real gate."""

    return repo / ".e11" / f"{lane_id}.ledger"


def _commit_ledger(repo: Path, message: str) -> str:
    """Commit only the append-only marker, as the operational protocol requires."""

    return _commit(repo, message, ".e11/gy-def6.ledger")


def _review_base(repo: Path) -> str:
    """Return the prior reviewed fixture commit for the complete implementation at ``HEAD``."""

    return _git(repo, "rev-parse", "HEAD^").stdout.strip()


def _evidence(repo: Path, name: str, payload: bytes) -> Path:
    """Write ignored raw review evidence outside the frozen implementation scope."""

    path = repo / "tmp" / "e11" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


def _receipt(repo: Path, payload: bytes = b"replayed receipt\n") -> Path:
    """Write and commit one byte-bound governed receipt fixture outside E11 source scope."""

    path = repo / "architecture" / "policy_design_case" / "receipt.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    _commit(repo, "commit replay receipt", "architecture/policy_design_case/receipt.json")
    return path


def _open_and_freeze(
    repo: Path, *, required_reviews: tuple[str, ...] = ("independent-quality",)
) -> dict[str, object]:
    """Create and commit a source-bound freeze marker for the test lane."""

    ledger = _ledger(repo)
    review_freeze.open_lane(
        repo_root=repo,
        ledger_path=ledger,
        lane_id="gy-def6",
        receipt_chain_id="layer3-gy-confidence-chain",
        review_base_revision=_review_base(repo),
        required_reviews=required_reviews,
        recorded_at="2026-08-08T12:00:00Z",
    )
    freeze = review_freeze.freeze_lane(
        repo_root=repo,
        ledger_path=ledger,
        lane_id="gy-def6",
        receipt_chain_id="layer3-gy-confidence-chain",
        recorded_at="2026-08-08T12:01:00Z",
    )
    _commit_ledger(repo, "commit frozen boundary")
    return freeze


def _full_review(
    repo: Path,
    *,
    base: str,
    freeze: dict[str, object],
    reviewer_id: str = "independent-quality",
    result_payload: bytes = b"independent full review receipt\n",
) -> dict[str, object]:
    """Build a real full package, commit its binding, and bind opaque reviewer output."""

    package = review_freeze.build_full_review_package(
        repo_root=repo,
        ledger_path=_ledger(repo),
        lane_id="gy-def6",
        freeze_id=str(freeze["freeze_id"]),
        base_revision=base,
        head_revision=str(freeze["source_identity"]["source_commit"]),
        package_output="tmp/e11/full.review",
    )
    assert package
    _commit_ledger(repo, "commit full review package binding")
    result = review_freeze.record_review_result(
        repo_root=repo,
        ledger_path=_ledger(repo),
        lane_id="gy-def6",
        freeze_id=str(freeze["freeze_id"]),
        review_package_id=str(package["review_package_id"]),
        reviewer_id=reviewer_id,
        result_path=_evidence(repo, "full.result", result_payload),
        recorded_at="2026-08-08T12:02:00Z",
    )
    _commit_ledger(repo, "commit full review result")
    return result


def _admit_blocking(
    repo: Path,
    *,
    review_result_id: str,
    finding_id: str = "blocking-001",
    payload: bytes = b"producer proof is unsound\n",
) -> dict[str, object]:
    """Admit one exact blocking finding through the real frozen gate."""

    return review_freeze.disposition_finding(
        repo_root=repo,
        ledger_path=_ledger(repo),
        lane_id="gy-def6",
        finding_id=finding_id,
        finding_path=_evidence(repo, f"{finding_id}.review", payload),
        declared_classification="blocking",
        classification_provenance="institutionally_supplied",
        review_result_id=review_result_id,
        recorded_at="2026-08-08T12:03:00Z",
    )


def _section_payload(package: bytes, name: str) -> bytes:
    """Read one length-delimited package section without interpreting its payload."""

    marker = f"section={name}\n".encode("ascii")
    metadata_start = package.index(marker) + len(marker)
    payload_start = package.index(b"\n\n", metadata_start) + 2
    metadata = package[metadata_start : payload_start - 2].splitlines()
    length = int(next(line for line in metadata if line.startswith(b"length=")).split(b"=", 1)[1])
    return package[payload_start : payload_start + length]


def _canonical_resolution_bytes(
    *, finding_id: str, repair_freeze_id: str, result_sha256: str
) -> bytes:
    """Build one structural, content-bound institutional acceptance witness for a fixture."""

    return json.dumps(
        {
            "accepted": True,
            "finding_id": finding_id,
            "repair_freeze_id": repair_freeze_id,
            "review_result_sha256": result_sha256,
            "schema_version": "policyos.review_freeze.resolution.v1",
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def test_unfrozen_lane_returns_fix_now(tmp_path: Path) -> None:
    """An ordinary finding remains ordinary work before a committed freeze exists."""

    repo, _base, _head = _init_repo(tmp_path)

    decision = review_freeze.disposition_finding(
        repo_root=repo,
        ledger_path=_ledger(repo),
        lane_id="gy-def6",
        finding_id="unfrozen-001",
        finding_path=_evidence(repo, "unfrozen.review", b"ordinary review finding\n"),
        declared_classification="blocking",
        classification_provenance="institutionally_supplied",
        review_result_id=None,
        recorded_at="2026-08-08T12:00:00Z",
    )

    assert decision["disposition"] == "fix_now"


def test_frozen_blocking_finding_is_batched_and_blocks_replay(tmp_path: Path) -> None:
    """A committed frozen boundary batches a real blocking finding and refuses replay."""

    repo, base, _head = _init_repo(tmp_path)
    freeze = _open_and_freeze(repo)
    review = _full_review(repo, base=base, freeze=freeze)
    decision = _admit_blocking(repo, review_result_id=str(review["review_result_id"]))
    _commit_ledger(repo, "commit blocking batch member")

    assert decision["disposition"] == "batch"
    assert freeze["research_only"] is True
    assert freeze["authoritative_for"]
    assert "automatic amendment of any plan" in freeze["may_not_use_for"]
    with pytest.raises(review_freeze.ReviewFreezeError, match="open_batch_members"):
        review_freeze.record_replay(
            repo_root=repo,
            ledger_path=_ledger(repo),
            lane_id="gy-def6",
            freeze_id=str(freeze["freeze_id"]),
            receipt_path=_receipt(repo),
            recorded_at="2026-08-08T12:04:00Z",
        )


def test_frozen_recomputed_import_order_finding_becomes_debt_without_replay(tmp_path: Path) -> None:
    """Only exact, recomputed I001 evidence can defer a frozen finding as debt."""

    repo, _base, _head = _init_repo(tmp_path)
    freeze = _open_and_freeze(repo)
    finding = _evidence(repo, "ruff-i001.review", b"placeholder")
    review_freeze.write_ruff_i001_finding(
        repo_root=repo,
        source_path="src/engine.py",
        output_path=finding,
    )
    evidence = json.loads(finding.read_bytes())

    decision = review_freeze.admit_ruff_i001_finding(
        repo_root=repo,
        ledger_path=_ledger(repo),
        lane_id="gy-def6",
        finding_path=finding,
        review_result_id=None,
        recorded_at="2026-08-08T12:03:00Z",
    )
    state = review_freeze.lane_state(
        repo_root=repo,
        ledger_path=_ledger(repo),
        lane_id="gy-def6",
    )

    assert decision["disposition"] == "debt"
    assert state["state"] == "frozen"
    assert state["open_batch_member_ids"] == []
    assert evidence["research_only"] is True
    assert evidence["authoritative_for"]
    assert "implementation authorization" in evidence["may_not_use_for"]


def test_p37_false_cosmetic_declaration_is_batched(tmp_path: Path) -> None:
    """A blocking finding declared cosmetic cannot be laundered into debt."""

    repo, base, _head = _init_repo(tmp_path)
    freeze = _open_and_freeze(repo)
    review = _full_review(repo, base=base, freeze=freeze)

    decision = review_freeze.disposition_finding(
        repo_root=repo,
        ledger_path=_ledger(repo),
        lane_id="gy-def6",
        finding_id="false-cosmetic-001",
        finding_path=_evidence(repo, "false-cosmetic.review", b"delete authority gate\n"),
        declared_classification="cosmetic",
        classification_provenance="institutionally_supplied",
        review_result_id=str(review["review_result_id"]),
        recorded_at="2026-08-08T12:03:00Z",
    )

    assert decision["disposition"] == "batch"


def test_unestablished_classification_is_batched(tmp_path: Path) -> None:
    """A style synonym without a recomputed classifier takes the conservative branch."""

    repo, base, _head = _init_repo(tmp_path)
    freeze = _open_and_freeze(repo)
    review = _full_review(repo, base=base, freeze=freeze)

    decision = review_freeze.disposition_finding(
        repo_root=repo,
        ledger_path=_ledger(repo),
        lane_id="gy-def6",
        finding_id="unknown-001",
        finding_path=_evidence(repo, "unknown.review", b"ambiguous review observation\n"),
        declared_classification="style-synonym",
        classification_provenance="not_established",
        review_result_id=str(review["review_result_id"]),
        recorded_at="2026-08-08T12:03:00Z",
    )

    assert decision["disposition"] == "batch"


def test_uncommitted_freeze_cannot_authorize_debt(tmp_path: Path) -> None:
    """A rewriteable marker degrades a cosmetic-looking finding to a batch."""

    repo, _base, _head = _init_repo(tmp_path)
    review_freeze.open_lane(
        repo_root=repo,
        ledger_path=_ledger(repo),
        lane_id="gy-def6",
        receipt_chain_id="layer3-gy-confidence-chain",
        review_base_revision=_review_base(repo),
        required_reviews=("independent-quality",),
        recorded_at="2026-08-08T12:00:00Z",
    )
    review_freeze.freeze_lane(
        repo_root=repo,
        ledger_path=_ledger(repo),
        lane_id="gy-def6",
        receipt_chain_id="layer3-gy-confidence-chain",
        recorded_at="2026-08-08T12:01:00Z",
    )
    finding = _evidence(repo, "uncommitted-i001.review", b"placeholder")
    review_freeze.write_ruff_i001_finding(
        repo_root=repo,
        source_path="src/engine.py",
        output_path=finding,
    )

    decision = review_freeze.admit_ruff_i001_finding(
        repo_root=repo,
        ledger_path=_ledger(repo),
        lane_id="gy-def6",
        finding_path=finding,
        review_result_id=None,
        recorded_at="2026-08-08T12:02:00Z",
    )

    assert decision["disposition"] == "batch"
    assert "freeze_marker_not_committed" in decision["reasons"]


def test_source_or_config_move_after_freeze_is_reported_and_batched(tmp_path: Path) -> None:
    """Both implementation and runtime-configuration movement invalidate the source boundary."""

    repo, base, _head = _init_repo(tmp_path)
    freeze = _open_and_freeze(repo)
    review = _full_review(repo, base=base, freeze=freeze)
    (repo / "pyproject.toml").write_text("[project]\nname = 'moved'\n", encoding="utf-8")

    decision = review_freeze.disposition_finding(
        repo_root=repo,
        ledger_path=_ledger(repo),
        lane_id="gy-def6",
        finding_id="source-moved-001",
        finding_path=_evidence(repo, "after-move.review", b"review finding\n"),
        declared_classification="cosmetic",
        classification_provenance="recomputed",
        review_result_id=str(review["review_result_id"]),
        recorded_at="2026-08-08T12:03:00Z",
    )

    assert decision["disposition"] == "batch"
    assert decision["freeze_match"] is False
    assert "freeze_source_moved" in decision["reasons"]


def test_replay_requires_a_committed_review_round(tmp_path: Path) -> None:
    """A clean freeze cannot skip independent-review evidence and mark itself replayed."""

    repo, _base, _head = _init_repo(tmp_path)
    freeze = _open_and_freeze(repo)

    with pytest.raises(review_freeze.ReviewFreezeError, match="review_round_missing"):
        review_freeze.record_replay(
            repo_root=repo,
            ledger_path=_ledger(repo),
            lane_id="gy-def6",
            freeze_id=str(freeze["freeze_id"]),
            receipt_path=_receipt(repo),
            recorded_at="2026-08-08T12:03:00Z",
        )


def test_replay_requires_every_institutionally_declared_independent_review(tmp_path: Path) -> None:
    """Coverage is recomputed against the frozen roster rather than inferred from one receipt."""

    repo, base, _head = _init_repo(tmp_path)
    freeze = _open_and_freeze(repo, required_reviews=("review-a", "review-b"))
    _full_review(repo, base=base, freeze=freeze, reviewer_id="review-a")

    with pytest.raises(review_freeze.ReviewFreezeError, match="review_round_missing"):
        review_freeze.record_replay(
            repo_root=repo,
            ledger_path=_ledger(repo),
            lane_id="gy-def6",
            freeze_id=str(freeze["freeze_id"]),
            receipt_path=_receipt(repo),
            recorded_at="2026-08-08T12:03:00Z",
        )


def test_successor_replay_requires_the_entire_roster_to_consume_its_delta(tmp_path: Path) -> None:
    """A successor cannot combine one delta review with an unrelated full-review result."""

    repo, base, _head = _init_repo(tmp_path)
    first = _open_and_freeze(repo, required_reviews=("review-a", "review-b"))
    first_package = review_freeze.build_full_review_package(
        repo_root=repo,
        ledger_path=_ledger(repo),
        lane_id="gy-def6",
        freeze_id=str(first["freeze_id"]),
        base_revision=base,
        head_revision=str(first["source_identity"]["source_commit"]),
        package_output="tmp/e11/first.full.review",
    )
    _commit_ledger(repo, "commit first full package")
    first_result_a = review_freeze.record_review_result(
        repo_root=repo,
        ledger_path=_ledger(repo),
        lane_id="gy-def6",
        freeze_id=str(first["freeze_id"]),
        review_package_id=str(first_package["review_package_id"]),
        reviewer_id="review-a",
        result_path=_evidence(repo, "first-a.result", b"review a\n"),
        recorded_at="2026-08-08T12:02:00Z",
    )
    _commit_ledger(repo, "commit first review a")
    review_freeze.record_review_result(
        repo_root=repo,
        ledger_path=_ledger(repo),
        lane_id="gy-def6",
        freeze_id=str(first["freeze_id"]),
        review_package_id=str(first_package["review_package_id"]),
        reviewer_id="review-b",
        result_path=_evidence(repo, "first-b.result", b"review b\n"),
        recorded_at="2026-08-08T12:02:30Z",
    )
    _commit_ledger(repo, "commit first review b")
    _admit_blocking(repo, review_result_id=str(first_result_a["review_result_id"]))
    _commit_ledger(repo, "commit original batch")
    (repo / "src" / "engine.py").write_text("VALUE = 2\n", encoding="utf-8")
    repair = _commit(repo, "repair", "src/engine.py")
    second = review_freeze.freeze_lane(
        repo_root=repo,
        ledger_path=_ledger(repo),
        lane_id="gy-def6",
        receipt_chain_id="layer3-gy-confidence-chain",
        supersedes_freeze_id=str(first["freeze_id"]),
        recorded_at="2026-08-08T12:03:00Z",
    )
    _commit_ledger(repo, "commit successor")
    delta = review_freeze.build_batch_delta_review_package(
        repo_root=repo,
        ledger_path=_ledger(repo),
        lane_id="gy-def6",
        freeze_id=str(second["freeze_id"]),
        checklist_output="tmp/e11/successor.checklist",
        base_revision=str(first["source_identity"]["source_commit"]),
        head_revision=repair,
        package_output="tmp/e11/successor.delta.review",
    )
    _commit_ledger(repo, "commit successor delta")
    delta_result_a = review_freeze.record_review_result(
        repo_root=repo,
        ledger_path=_ledger(repo),
        lane_id="gy-def6",
        freeze_id=str(second["freeze_id"]),
        review_package_id=str(delta["review_package_id"]),
        reviewer_id="review-a",
        result_path=_evidence(repo, "successor-a.result", b"delta a\n"),
        recorded_at="2026-08-08T12:04:00Z",
    )
    _commit_ledger(repo, "commit successor delta review a")
    full = review_freeze.build_full_review_package(
        repo_root=repo,
        ledger_path=_ledger(repo),
        lane_id="gy-def6",
        freeze_id=str(second["freeze_id"]),
        base_revision=base,
        head_revision=repair,
        package_output="tmp/e11/successor.full.review",
    )
    _commit_ledger(repo, "commit successor full")
    review_freeze.record_review_result(
        repo_root=repo,
        ledger_path=_ledger(repo),
        lane_id="gy-def6",
        freeze_id=str(second["freeze_id"]),
        review_package_id=str(full["review_package_id"]),
        reviewer_id="review-b",
        result_path=_evidence(repo, "successor-b.result", b"full b\n"),
        recorded_at="2026-08-08T12:04:30Z",
    )
    _commit_ledger(repo, "commit successor full review b")
    resolution = _evidence(
        repo,
        "successor.resolution.json",
        _canonical_resolution_bytes(
            finding_id="blocking-001",
            repair_freeze_id=str(second["freeze_id"]),
            result_sha256=str(delta_result_a["result_sha256"]),
        ),
    )
    review_freeze.resolve_batch_member(
        repo_root=repo,
        ledger_path=_ledger(repo),
        lane_id="gy-def6",
        finding_id="blocking-001",
        review_result_id=str(delta_result_a["review_result_id"]),
        resolution_path=resolution,
        recorded_at="2026-08-08T12:05:00Z",
    )
    _commit_ledger(repo, "commit successor resolution")

    with pytest.raises(
        review_freeze.ReviewFreezeError, match="successor_delta_review_round_missing"
    ):
        review_freeze.record_replay(
            repo_root=repo,
            ledger_path=_ledger(repo),
            lane_id="gy-def6",
            freeze_id=str(second["freeze_id"]),
            receipt_path=_receipt(repo),
            recorded_at="2026-08-08T12:06:00Z",
        )


def test_present_but_empty_batch_cannot_be_exported(tmp_path: Path) -> None:
    """A freeze without blocking findings cannot manufacture an empty delta checklist."""

    repo, _base, _head = _init_repo(tmp_path)
    freeze = _open_and_freeze(repo)

    with pytest.raises(review_freeze.ReviewFreezeError, match="batch_empty"):
        review_freeze.export_batch_checklist(
            repo_root=repo,
            ledger_path=_ledger(repo),
            lane_id="gy-def6",
            freeze_id=str(freeze["freeze_id"]),
            output_path="tmp/e11/empty.checklist",
        )


def test_superseding_freeze_and_delta_carry_the_original_open_batch(tmp_path: Path) -> None:
    """A repaired source transfers its old batch into a real delta review exactly once."""

    repo, base, _head = _init_repo(tmp_path)
    first = _open_and_freeze(repo)
    first_review = _full_review(repo, base=base, freeze=first)
    original = b"blocking finding with \x00 exact bytes\n"
    decision = _admit_blocking(
        repo,
        review_result_id=str(first_review["review_result_id"]),
        finding_id="delta-001",
        payload=original,
    )
    _commit_ledger(repo, "commit original blocking batch")
    first_bytes = _ledger(repo).read_bytes()

    (repo / "src" / "engine.py").write_text(
        "import json\nimport os\n\nVALUE = 2\n", encoding="utf-8"
    )
    repair_commit = _commit(repo, "repair blocking source", "src/engine.py")
    second = review_freeze.freeze_lane(
        repo_root=repo,
        ledger_path=_ledger(repo),
        lane_id="gy-def6",
        receipt_chain_id="layer3-gy-confidence-chain",
        supersedes_freeze_id=str(first["freeze_id"]),
        recorded_at="2026-08-08T12:04:00Z",
    )
    _commit_ledger(repo, "commit superseding frozen boundary")

    package = review_freeze.build_batch_delta_review_package(
        repo_root=repo,
        ledger_path=_ledger(repo),
        lane_id="gy-def6",
        freeze_id=str(second["freeze_id"]),
        checklist_output="tmp/e11/batch.checklist",
        base_revision=str(first["source_identity"]["source_commit"]),
        head_revision=repair_commit,
        package_output="tmp/e11/delta.review",
    )
    _commit_ledger(repo, "commit delta review package binding")
    checklist = (repo / "tmp" / "e11" / "batch.checklist").read_bytes()

    assert decision["disposition"] == "batch"
    assert _ledger(repo).read_bytes().startswith(first_bytes)
    assert original in checklist
    assert (
        _section_payload((repo / "tmp" / "e11" / "delta.review").read_bytes(), "prior_findings")
        == checklist
    )
    assert package["head_commit"] == repair_commit


def test_resolution_requires_bound_delta_review_and_repaired_successor(tmp_path: Path) -> None:
    """A bare string cannot resolve a batch member or unlock a replay."""

    repo, base, _head = _init_repo(tmp_path)
    first = _open_and_freeze(repo)
    first_review = _full_review(repo, base=base, freeze=first)
    _admit_blocking(repo, review_result_id=str(first_review["review_result_id"]))
    _commit_ledger(repo, "commit original blocking batch")
    (repo / "src" / "engine.py").write_text("VALUE = 2\n", encoding="utf-8")
    repair = _commit(repo, "repair", "src/engine.py")
    second = review_freeze.freeze_lane(
        repo_root=repo,
        ledger_path=_ledger(repo),
        lane_id="gy-def6",
        receipt_chain_id="layer3-gy-confidence-chain",
        supersedes_freeze_id=str(first["freeze_id"]),
        recorded_at="2026-08-08T12:04:00Z",
    )
    _commit_ledger(repo, "commit repaired freeze")
    package = review_freeze.build_batch_delta_review_package(
        repo_root=repo,
        ledger_path=_ledger(repo),
        lane_id="gy-def6",
        freeze_id=str(second["freeze_id"]),
        checklist_output="tmp/e11/batch.checklist",
        base_revision=str(first["source_identity"]["source_commit"]),
        head_revision=repair,
        package_output="tmp/e11/delta.review",
    )
    _commit_ledger(repo, "commit delta package")
    result = review_freeze.record_review_result(
        repo_root=repo,
        ledger_path=_ledger(repo),
        lane_id="gy-def6",
        freeze_id=str(second["freeze_id"]),
        review_package_id=str(package["review_package_id"]),
        reviewer_id="independent-quality",
        result_path=_evidence(repo, "delta.result", b"independent delta review\n"),
        recorded_at="2026-08-08T12:05:00Z",
    )
    _commit_ledger(repo, "commit delta review result")

    with pytest.raises(review_freeze.ReviewFreezeError, match="resolution_evidence_invalid"):
        review_freeze.resolve_batch_member(
            repo_root=repo,
            ledger_path=_ledger(repo),
            lane_id="gy-def6",
            finding_id="blocking-001",
            review_result_id=str(result["review_result_id"]),
            resolution_path=_evidence(repo, "bare-resolution.review", b"done\n"),
            recorded_at="2026-08-08T12:06:00Z",
        )


def test_bound_resolution_then_replay_and_close_follow_real_state_machine(tmp_path: Path) -> None:
    """A repaired batch reaches replayed and closed only after exact delta evidence binds it."""

    repo, base, _head = _init_repo(tmp_path)
    first = _open_and_freeze(repo)
    first_review = _full_review(repo, base=base, freeze=first)
    _admit_blocking(repo, review_result_id=str(first_review["review_result_id"]))
    _commit_ledger(repo, "commit original blocking batch")
    (repo / "src" / "engine.py").write_text("VALUE = 2\n", encoding="utf-8")
    repair = _commit(repo, "repair", "src/engine.py")
    second = review_freeze.freeze_lane(
        repo_root=repo,
        ledger_path=_ledger(repo),
        lane_id="gy-def6",
        receipt_chain_id="layer3-gy-confidence-chain",
        supersedes_freeze_id=str(first["freeze_id"]),
        recorded_at="2026-08-08T12:04:00Z",
    )
    _commit_ledger(repo, "commit repaired freeze")
    package = review_freeze.build_batch_delta_review_package(
        repo_root=repo,
        ledger_path=_ledger(repo),
        lane_id="gy-def6",
        freeze_id=str(second["freeze_id"]),
        checklist_output="tmp/e11/batch.checklist",
        base_revision=str(first["source_identity"]["source_commit"]),
        head_revision=repair,
        package_output="tmp/e11/delta.review",
    )
    _commit_ledger(repo, "commit delta package")
    result = review_freeze.record_review_result(
        repo_root=repo,
        ledger_path=_ledger(repo),
        lane_id="gy-def6",
        freeze_id=str(second["freeze_id"]),
        review_package_id=str(package["review_package_id"]),
        reviewer_id="independent-quality",
        result_path=_evidence(repo, "delta.result", b"independent delta review\n"),
        recorded_at="2026-08-08T12:05:00Z",
    )
    _commit_ledger(repo, "commit delta result")
    resolution = _evidence(
        repo,
        "resolution.json",
        json.dumps(
            {
                "accepted": True,
                "finding_id": "blocking-001",
                "repair_freeze_id": second["freeze_id"],
                "review_result_sha256": result["result_sha256"],
                "schema_version": "policyos.review_freeze.resolution.v1",
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode(),
    )
    review_freeze.resolve_batch_member(
        repo_root=repo,
        ledger_path=_ledger(repo),
        lane_id="gy-def6",
        finding_id="blocking-001",
        review_result_id=str(result["review_result_id"]),
        resolution_path=resolution,
        recorded_at="2026-08-08T12:06:00Z",
    )
    _commit_ledger(repo, "commit bound batch resolution")

    replay = review_freeze.record_replay(
        repo_root=repo,
        ledger_path=_ledger(repo),
        lane_id="gy-def6",
        freeze_id=str(second["freeze_id"]),
        receipt_path=_receipt(repo),
        recorded_at="2026-08-08T12:07:00Z",
    )
    with pytest.raises(review_freeze.ReviewFreezeError, match="replay_event_not_committed"):
        review_freeze.close_lane(
            repo_root=repo,
            ledger_path=_ledger(repo),
            lane_id="gy-def6",
            freeze_id=str(second["freeze_id"]),
            recorded_at="2026-08-08T12:08:00Z",
        )
    _commit_ledger(repo, "commit replay record")
    closed = review_freeze.close_lane(
        repo_root=repo,
        ledger_path=_ledger(repo),
        lane_id="gy-def6",
        freeze_id=str(second["freeze_id"]),
        recorded_at="2026-08-08T12:08:00Z",
    )

    assert replay["state"] == "replayed"
    assert closed["state"] == "closed"


def test_dynamic_receipt_exclusions_are_refused_before_they_can_hide_source(tmp_path: Path) -> None:
    """A caller cannot declare a future root non-source and retain a permissive debt path."""

    repo, _base, _head = _init_repo(tmp_path)
    review_freeze.open_lane(
        repo_root=repo,
        ledger_path=_ledger(repo),
        lane_id="gy-def6",
        receipt_chain_id="layer3-gy-confidence-chain",
        review_base_revision=_review_base(repo),
        required_reviews=("independent-quality",),
        recorded_at="2026-08-08T12:00:00Z",
    )

    with pytest.raises(review_freeze.ReviewFreezeError, match="receipt_chain_paths_not_supported"):
        review_freeze.freeze_lane(
            repo_root=repo,
            ledger_path=_ledger(repo),
            lane_id="gy-def6",
            receipt_chain_id="layer3-gy-confidence-chain",
            receipt_chain_paths=("future_receipt",),
            recorded_at="2026-08-08T12:01:00Z",
        )


def test_tampered_present_i001_evidence_keeps_markers_but_batches(tmp_path: Path) -> None:
    """A cosmetic-looking JSON marker cannot replace the real recomputed Ruff property."""

    repo, base, _head = _init_repo(tmp_path)
    freeze = _open_and_freeze(repo)
    review = _full_review(repo, base=base, freeze=freeze)
    finding = _evidence(repo, "tampered-i001.review", b"placeholder")
    review_freeze.write_ruff_i001_finding(
        repo_root=repo,
        source_path="src/engine.py",
        output_path=finding,
    )
    finding.write_bytes(finding.read_bytes().replace(b'"I001"', b'"I001-tampered"'))

    decision = review_freeze.admit_ruff_i001_finding(
        repo_root=repo,
        ledger_path=_ledger(repo),
        lane_id="gy-def6",
        finding_path=finding,
        review_result_id=str(review["review_result_id"]),
        recorded_at="2026-08-08T12:03:00Z",
    )

    assert decision["disposition"] == "batch"


def test_local_ledger_rewrite_fails_current_head_prefix_validation(tmp_path: Path) -> None:
    """A self-consistent local rewrite cannot replace the committed ledger prefix."""

    repo, _base, _head = _init_repo(tmp_path)
    _open_and_freeze(repo)
    _ledger(repo).write_text('{"rewritten":true}\n', encoding="utf-8")
    rewritten = review_freeze.validate_ledger(repo_root=repo, ledger_path=_ledger(repo))

    assert rewritten["status"] == "fail"
    assert "ledger_current_not_append_only" in {issue["code"] for issue in rewritten["issues"]}


def test_malformed_unhashable_provenance_fails_closed_without_a_type_error(tmp_path: Path) -> None:
    """A malformed record has a typed failing receipt instead of an unchecked exception."""

    repo, _base, _head = _init_repo(tmp_path)
    malformed = repo / ".e11" / "malformed.ledger"
    malformed.parent.mkdir()
    malformed.write_text(
        json.dumps(
            {
                "entry_sha256": "sha256:not-real",
                "event_type": "open",
                "lane_id": "gy-def6",
                "predicate_provenance": {"bad": []},
                "previous_entry_sha256": None,
                "schema_version": review_freeze.SCHEMA_VERSION,
                "sequence": 1,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    malformed_report = review_freeze.validate_ledger(repo_root=repo, ledger_path=malformed)

    assert malformed_report["status"] == "fail"
    assert "ledger_predicate_provenance_invalid" in {
        issue["code"] for issue in malformed_report["issues"]
    }


def test_second_lane_remains_unfrozen(tmp_path: Path) -> None:
    """One lane's committed freeze cannot silently govern a different lane."""

    repo, _base, _head = _init_repo(tmp_path)
    _open_and_freeze(repo)
    second_ledger = _ledger_for(repo, "another-lane")
    ordinary = review_freeze.disposition_finding(
        repo_root=repo,
        ledger_path=second_ledger,
        lane_id="another-lane",
        finding_id="second-lane-001",
        finding_path=_evidence(repo, "second-lane.review", b"ordinary work\n"),
        declared_classification="blocking",
        classification_provenance="institutionally_supplied",
        review_result_id=None,
        recorded_at="2026-08-08T12:02:00Z",
    )
    assert ordinary["disposition"] == "fix_now"


def test_lane_cannot_start_a_second_transcript_to_escape_an_open_batch(tmp_path: Path) -> None:
    """The canonical ``.e11/<lane>.ledger`` path prevents an alternate-ledger bypass."""

    repo, _base, _head = _init_repo(tmp_path)
    _open_and_freeze(repo)

    with pytest.raises(review_freeze.ReviewFreezeError, match="lane_ledger_path_not_canonical"):
        review_freeze.disposition_finding(
            repo_root=repo,
            ledger_path=repo / ".e11" / "alternate.ledger",
            lane_id="gy-def6",
            finding_id="alternate-ledger-001",
            finding_path=_evidence(repo, "alternate-ledger.review", b"blocking\n"),
            declared_classification="blocking",
            classification_provenance="institutionally_supplied",
            review_result_id=None,
            recorded_at="2026-08-08T12:02:00Z",
        )


def test_nonexistent_frozen_commit_is_refused(tmp_path: Path) -> None:
    """A source commit must resolve in the anchored Git worktree before it can be frozen."""

    repo, _base, _head = _init_repo(tmp_path)
    lane_id = "missing-commit-lane"
    review_freeze.open_lane(
        repo_root=repo,
        ledger_path=_ledger_for(repo, lane_id),
        lane_id=lane_id,
        receipt_chain_id="layer3-gy-confidence-chain",
        review_base_revision=_review_base(repo),
        required_reviews=("independent-quality",),
        recorded_at="2026-08-08T12:02:00Z",
    )

    with pytest.raises(review_freeze.ReviewFreezeError, match="source_commit_unresolvable"):
        review_freeze.freeze_lane(
            repo_root=repo,
            ledger_path=_ledger_for(repo, lane_id),
            lane_id=lane_id,
            receipt_chain_id="layer3-gy-confidence-chain",
            source_commit="0" * 40,
            recorded_at="2026-08-08T12:03:00Z",
        )


def test_hardened_git_context_ignores_hostile_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Source identity stays anchored to the requested worktree under hostile Git variables."""

    repo, _base, _head = _init_repo(tmp_path)
    foreign, _foreign_base, _foreign_head = _init_repo(tmp_path, name="foreign-repo")
    freeze = _open_and_freeze(repo)
    monkeypatch.setenv("GIT_DIR", str(foreign / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(foreign))
    monkeypatch.setenv("GIT_INDEX_FILE", str(foreign / ".git" / "index"))

    state = review_freeze.lane_state(repo_root=repo, ledger_path=_ledger(repo), lane_id="gy-def6")
    assert state["active_freeze_id"] == freeze["freeze_id"]
    assert state["source_match"]["matches"] is True


def test_documented_direct_cli_invokes_the_real_gate(tmp_path: Path) -> None:
    """The README's direct-script command runs without package-import setup from the caller."""

    repo, base, _head = _init_repo(tmp_path)
    result = subprocess.run(  # noqa: S603 - exact documented direct-script argv.
        [
            sys.executable,
            str(REVIEW_FREEZE_SCRIPT),
            "--ledger",
            ".e11/direct-lane.ledger",
            "open",
            "--lane",
            "direct-lane",
            "--receipt-chain",
            "direct-chain",
            "--review-base",
            base,
            "--required-review",
            "independent-quality",
            "--at",
            "2026-08-08T12:00:00Z",
        ],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert json.loads(result.stdout)["event_type"] == "open"


def test_existing_packager_receives_exact_raw_batch_checklist(tmp_path: Path) -> None:
    """The gate delegates package rendering to the existing packager without retyping bytes."""

    repo, base, _head = _init_repo(tmp_path)
    first = _open_and_freeze(repo)
    review = _full_review(repo, base=base, freeze=first)
    raw = b"finding with \x00 opaque bytes\n"
    _admit_blocking(
        repo,
        review_result_id=str(review["review_result_id"]),
        finding_id="opaque-001",
        payload=raw,
    )
    _commit_ledger(repo, "commit opaque batch")
    (repo / "src" / "engine.py").write_text("VALUE = 2\n", encoding="utf-8")
    repair = _commit(repo, "repair", "src/engine.py")
    second = review_freeze.freeze_lane(
        repo_root=repo,
        ledger_path=_ledger(repo),
        lane_id="gy-def6",
        receipt_chain_id="layer3-gy-confidence-chain",
        supersedes_freeze_id=str(first["freeze_id"]),
        recorded_at="2026-08-08T12:04:00Z",
    )
    _commit_ledger(repo, "commit successor")

    package = review_freeze.build_batch_delta_review_package(
        repo_root=repo,
        ledger_path=_ledger(repo),
        lane_id="gy-def6",
        freeze_id=str(second["freeze_id"]),
        checklist_output="tmp/e11/opaque.checklist",
        base_revision=str(first["source_identity"]["source_commit"]),
        head_revision=repair,
        package_output="tmp/e11/opaque.delta",
    )
    checklist = (repo / "tmp" / "e11" / "opaque.checklist").read_bytes()
    package_bytes = (repo / "tmp" / "e11" / "opaque.delta").read_bytes()

    assert raw in checklist
    assert hashlib.sha256(checklist).hexdigest() in package_bytes.decode("utf-8", errors="replace")
    assert _section_payload(package_bytes, "prior_findings") == checklist
    assert package["package_sha256"] == f"sha256:{hashlib.sha256(package_bytes).hexdigest()}"
    assert review_package.PACKAGE_MAGIC in package_bytes


def test_self_hashed_delta_package_cannot_decouple_its_checklist_from_the_batch(
    tmp_path: Path,
) -> None:
    """Member metadata beside arbitrary opaque prior-findings bytes fails semantic reconstruction."""

    repo, base, _head = _init_repo(tmp_path)
    first = _open_and_freeze(repo)
    first_result = _full_review(repo, base=base, freeze=first)
    _admit_blocking(repo, review_result_id=str(first_result["review_result_id"]))
    _commit_ledger(repo, "commit original batch")
    (repo / "src" / "engine.py").write_text("VALUE = 2\n", encoding="utf-8")
    repair = _commit(repo, "repair", "src/engine.py")
    second = review_freeze.freeze_lane(
        repo_root=repo,
        ledger_path=_ledger(repo),
        lane_id="gy-def6",
        receipt_chain_id="layer3-gy-confidence-chain",
        supersedes_freeze_id=str(first["freeze_id"]),
        recorded_at="2026-08-08T12:04:00Z",
    )
    _commit_ledger(repo, "commit successor")
    forged_checklist = _evidence(repo, "forged.checklist", b"plausible but unrelated checklist\n")
    forged_package = repo / "tmp" / "e11" / "forged.delta.review"
    package_bytes = review_package.build_review_package(
        base_revision=str(first["source_identity"]["source_commit"]),
        head_revision=repair,
        output_path=forged_package,
        prior_findings_path=forged_checklist,
        invocation_cwd=repo,
    )
    members = review_freeze._open_members(
        review_freeze._load_events(_ledger(repo)),
        "gy-def6",
        active_freeze_id=str(second["freeze_id"]),
    )
    assert len(members) == 1
    member = members[0]
    _append_self_hashed_event(
        repo,
        {
            "event_type": "review_package",
            "lane_id": "gy-def6",
            "freeze_id": second["freeze_id"],
            "review_package_id": "gy-def6:package:forged-checklist",
            "package_kind": "delta",
            "package_ref": "tmp/e11/forged.delta.review",
            "package_sha256": review_freeze._sha256(package_bytes),
            "base_commit": first["source_identity"]["source_commit"],
            "head_commit": repair,
            "checklist_ref": "tmp/e11/forged.checklist",
            "checklist_sha256": review_freeze._sha256(forged_checklist.read_bytes()),
            "member_bindings": [
                {
                    "finding_id": member["finding_id"],
                    "finding_sha256": member["finding_sha256"],
                    "origin_freeze_id": member["freeze_id"],
                }
            ],
            "recorded_at": "2026-08-08T12:05:00Z",
            "predicate_provenance": {},
        },
        canonical_provenance=True,
    )
    _commit_ledger(repo, "commit forged delta bridge")

    report = review_freeze.validate_ledger(repo_root=repo, ledger_path=_ledger(repo))

    assert report["status"] == "fail"
    assert "ledger_semantic_delta_checklist_not_canonical" in {
        issue["code"] for issue in report["issues"]
    }


def _append_self_hashed_event(
    repo: Path, payload: dict[str, object], *, canonical_provenance: bool = False
) -> None:
    """Append a syntactically valid ledger event without invoking the E11 producer."""

    ledger = _ledger(repo)
    events, issues = review_freeze._parse_ledger(ledger.read_bytes())
    assert not issues
    event_payload = dict(payload)
    if canonical_provenance:
        expected = review_freeze._expected_predicate_provenance(event_payload)
        assert expected is not None
        event_payload["predicate_provenance"] = expected
    entry: dict[str, object] = {
        "schema_version": review_freeze.SCHEMA_VERSION,
        "sequence": len(events) + 1,
        "previous_entry_sha256": events[-1]["entry_sha256"] if events else None,
        **review_freeze._authority_fields("gy-def6"),
        **event_payload,
    }
    entry["entry_sha256"] = review_freeze._event_digest(entry)
    with ledger.open("ab") as handle:
        handle.write(review_freeze._canonical_json_bytes(entry) + b"\n")


def test_assume_unchanged_source_move_fails_the_freeze_predicate(tmp_path: Path) -> None:
    """An index bit cannot hide a modified implementation file from the source census."""

    repo, _base, _head = _init_repo(tmp_path)
    _open_and_freeze(repo)
    _git(repo, "update-index", "--assume-unchanged", "src/engine.py")
    (repo / "src" / "engine.py").write_text("VALUE = 999\n", encoding="utf-8")

    state = review_freeze.lane_state(repo_root=repo, ledger_path=_ledger(repo), lane_id="gy-def6")

    assert state["source_match"]["matches"] is False
    assert "freeze_worktree_changed" in state["source_match"]["reasons"]
    assert any(
        change.startswith("source_index_flagged:src/engine.py")
        for change in state["source_match"]["working_changes"]
    )


def test_filemode_disabled_cannot_hide_a_mode_only_source_move(tmp_path: Path) -> None:
    """A source identity that binds Git modes fails closed under an unreliable local filemode."""

    repo, _base, _head = _init_repo(tmp_path)
    _open_and_freeze(repo)
    _git(repo, "config", "core.filemode", "false")
    source = repo / "src" / "engine.py"
    os.chmod(source, source.stat().st_mode | 0o111)

    state = review_freeze.lane_state(repo_root=repo, ledger_path=_ledger(repo), lane_id="gy-def6")

    assert state["source_match"]["matches"] is False
    assert "freeze_worktree_changed" in state["source_match"]["reasons"]
    assert "source_filemode_unreliable" in state["source_match"]["working_changes"]


def test_git_boolean_synonym_cannot_weaken_the_source_stat_predicate(tmp_path: Path) -> None:
    """Git's ``no`` spelling is normalized before it can hide a same-stat source mutation."""

    repo, _base, _head = _init_repo(tmp_path)
    _open_and_freeze(repo)
    _git(repo, "config", "core.trustctime", "no")

    state = review_freeze.lane_state(repo_root=repo, ledger_path=_ledger(repo), lane_id="gy-def6")

    assert state["source_match"]["matches"] is False
    assert "freeze_worktree_changed" in state["source_match"]["reasons"]
    assert (
        "source_stat_cache_unreliable:core.trustctime=false"
        in state["source_match"]["working_changes"]
    )


def test_tampered_package_cannot_receive_a_reviewer_result(tmp_path: Path) -> None:
    """A review result must consume the exact canonical package that the ledger bound."""

    repo, base, _head = _init_repo(tmp_path)
    freeze = _open_and_freeze(repo)
    package = review_freeze.build_full_review_package(
        repo_root=repo,
        ledger_path=_ledger(repo),
        lane_id="gy-def6",
        freeze_id=str(freeze["freeze_id"]),
        base_revision=base,
        head_revision=str(freeze["source_identity"]["source_commit"]),
        package_output="tmp/e11/full.review",
    )
    _commit_ledger(repo, "commit full package")
    (repo / "tmp" / "e11" / "full.review").write_bytes(b"marker-looking but forged package\n")

    with pytest.raises(review_freeze.ReviewFreezeError, match="review_package_digest_drift"):
        review_freeze.record_review_result(
            repo_root=repo,
            ledger_path=_ledger(repo),
            lane_id="gy-def6",
            freeze_id=str(freeze["freeze_id"]),
            review_package_id=str(package["review_package_id"]),
            reviewer_id="independent-quality",
            result_path=_evidence(repo, "forged-package.result", b"review\n"),
            recorded_at="2026-08-08T12:03:00Z",
        )


def test_full_review_cannot_use_the_frozen_head_as_its_own_baseline(tmp_path: Path) -> None:
    """A canonical but empty full package cannot stand in for review of the implementation diff."""

    repo, _base, _head = _init_repo(tmp_path)
    freeze = _open_and_freeze(repo)

    with pytest.raises(review_freeze.ReviewFreezeError, match="full_review_base_not_frozen"):
        review_freeze.build_full_review_package(
            repo_root=repo,
            ledger_path=_ledger(repo),
            lane_id="gy-def6",
            freeze_id=str(freeze["freeze_id"]),
            base_revision=str(freeze["source_identity"]["source_commit"]),
            head_revision=str(freeze["source_identity"]["source_commit"]),
            package_output="tmp/e11/empty-full.review",
        )


def test_self_hashed_replay_cannot_bypass_the_committed_semantic_gate(tmp_path: Path) -> None:
    """A valid hash chain without review evidence never becomes a replayed lifecycle state."""

    repo, _base, _head = _init_repo(tmp_path)
    freeze = _open_and_freeze(repo)
    _append_self_hashed_event(
        repo,
        {
            "event_type": "replay_recorded",
            "lane_id": "gy-def6",
            "freeze_id": freeze["freeze_id"],
            "state": "replayed",
            "receipt_ref": "architecture/policy_design_case/forged.json",
            "receipt_sha256": "sha256:" + "0" * 64,
            "recorded_at": "2026-08-08T12:03:00Z",
            "predicate_provenance": {"ledger_hash_chain": "recomputed"},
        },
        canonical_provenance=True,
    )
    _commit_ledger(repo, "commit forged replay event")

    report = review_freeze.validate_ledger(repo_root=repo, ledger_path=_ledger(repo))

    assert report["status"] == "fail"
    assert "ledger_semantic_replay_review_round_missing" in {
        issue["code"] for issue in report["issues"]
    }
    with pytest.raises(review_freeze.ReviewFreezeError, match="ledger_history_invalid"):
        review_freeze.close_lane(
            repo_root=repo,
            ledger_path=_ledger(repo),
            lane_id="gy-def6",
            freeze_id=str(freeze["freeze_id"]),
            recorded_at="2026-08-08T12:04:00Z",
        )


def test_self_hashed_event_cannot_omit_its_predicate_provenance(tmp_path: Path) -> None:
    """A valid digest does not excuse a replay event from freezing every load-bearing label."""

    repo, _base, _head = _init_repo(tmp_path)
    freeze = _open_and_freeze(repo)
    _append_self_hashed_event(
        repo,
        {
            "event_type": "replay_recorded",
            "lane_id": "gy-def6",
            "freeze_id": freeze["freeze_id"],
            "state": "replayed",
            "receipt_ref": "architecture/policy_design_case/forged.json",
            "receipt_sha256": "sha256:" + "0" * 64,
            "recorded_at": "2026-08-08T12:03:00Z",
            "predicate_provenance": {},
        },
    )
    _commit_ledger(repo, "commit provenance-free replay")

    report = review_freeze.validate_ledger(repo_root=repo, ledger_path=_ledger(repo))

    assert report["status"] == "fail"
    assert "ledger_semantic_predicate_provenance_invalid" in {
        issue["code"] for issue in report["issues"]
    }


def test_uncommitted_replay_candidate_does_not_change_authoritative_lane_state(
    tmp_path: Path,
) -> None:
    """Only the committed transcript can derive a lifecycle state consumed by the gate."""

    repo, _base, _head = _init_repo(tmp_path)
    freeze = _open_and_freeze(repo)
    _append_self_hashed_event(
        repo,
        {
            "event_type": "replay_recorded",
            "lane_id": "gy-def6",
            "freeze_id": freeze["freeze_id"],
            "state": "replayed",
            "receipt_ref": "architecture/policy_design_case/forged.json",
            "receipt_sha256": "sha256:" + "0" * 64,
            "recorded_at": "2026-08-08T12:03:00Z",
            "predicate_provenance": {"ledger_hash_chain": "recomputed"},
        },
        canonical_provenance=True,
    )

    state = review_freeze.lane_state(repo_root=repo, ledger_path=_ledger(repo), lane_id="gy-def6")

    assert state["state"] == "frozen"
    assert state["pending_event_count"] == 1


def test_freeze_binds_one_opening_roster_and_chain(tmp_path: Path) -> None:
    """A second declaration or a changed receipt chain cannot be substituted mid-lane."""

    repo, _base, _head = _init_repo(tmp_path)
    review_freeze.open_lane(
        repo_root=repo,
        ledger_path=_ledger(repo),
        lane_id="gy-def6",
        receipt_chain_id="chain-a",
        review_base_revision=_review_base(repo),
        required_reviews=("review-a",),
        recorded_at="2026-08-08T12:00:00Z",
    )

    with pytest.raises(review_freeze.ReviewFreezeError, match="lane_already_open_or_frozen"):
        review_freeze.open_lane(
            repo_root=repo,
            ledger_path=_ledger(repo),
            lane_id="gy-def6",
            receipt_chain_id="chain-b",
            review_base_revision=_review_base(repo),
            required_reviews=("review-b",),
            recorded_at="2026-08-08T12:00:01Z",
        )
    with pytest.raises(
        review_freeze.ReviewFreezeError, match="receipt_chain_id_changed_during_lane"
    ):
        review_freeze.freeze_lane(
            repo_root=repo,
            ledger_path=_ledger(repo),
            lane_id="gy-def6",
            receipt_chain_id="chain-b",
            recorded_at="2026-08-08T12:01:00Z",
        )


def test_docs_only_successor_cannot_pose_as_a_source_repair(tmp_path: Path) -> None:
    """A new commit outside the source scope cannot create a repaired successor freeze."""

    repo, base, _head = _init_repo(tmp_path)
    first = _open_and_freeze(repo)
    review = _full_review(repo, base=base, freeze=first)
    _admit_blocking(repo, review_result_id=str(review["review_result_id"]))
    _commit_ledger(repo, "commit blocking batch")
    docs = repo / "docs" / "note.md"
    docs.parent.mkdir()
    docs.write_text("only documentation moved\n", encoding="utf-8")
    _commit(repo, "docs only", "docs/note.md")

    with pytest.raises(
        review_freeze.ReviewFreezeError, match="superseding_freeze_requires_source_repair"
    ):
        review_freeze.freeze_lane(
            repo_root=repo,
            ledger_path=_ledger(repo),
            lane_id="gy-def6",
            receipt_chain_id="layer3-gy-confidence-chain",
            supersedes_freeze_id=str(first["freeze_id"]),
            recorded_at="2026-08-08T12:04:00Z",
        )


def test_validate_cli_returns_nonzero_for_a_failed_ledger(tmp_path: Path) -> None:
    """A failing report is a failing shell gate, not merely a JSON warning for callers to ignore."""

    repo, _base, _head = _init_repo(tmp_path)
    _ledger(repo).parent.mkdir()
    _ledger(repo).write_text("not-json\n", encoding="utf-8")

    result = subprocess.run(  # noqa: S603 - exact documented direct-script argv.
        [
            sys.executable,
            str(REVIEW_FREEZE_SCRIPT),
            "--ledger",
            ".e11/gy-def6.ledger",
            "validate",
        ],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert json.loads(result.stdout)["status"] == "fail"


def test_self_hashed_debt_declaration_cannot_launder_a_blocking_finding(
    tmp_path: Path,
) -> None:
    """The persisted event must rerun I001, not trust a cosmetic-looking declaration."""

    repo, base, _head = _init_repo(tmp_path)
    freeze = _open_and_freeze(repo)
    result = _full_review(repo, base=base, freeze=freeze)
    finding = _evidence(repo, "forged-debt.review", b"remove the authority gate\n")
    _append_self_hashed_event(
        repo,
        {
            "event_type": "admit_finding",
            "lane_id": "gy-def6",
            "freeze_id": freeze["freeze_id"],
            "review_result_id": result["review_result_id"],
            "finding_id": "forged-debt-001",
            "finding_ref": "tmp/e11/forged-debt.review",
            "finding_sha256": review_freeze._sha256(finding.read_bytes()),
            "declared_classification": "cosmetic",
            "classification_provenance": "recomputed",
            "classifier": "ruff_i001_v1",
            "disposition": "debt",
            "reasons": ["recomputed_cosmetic_classifier"],
            "recorded_at": "2026-08-08T12:03:00Z",
            "predicate_provenance": {"classification": "recomputed"},
        },
        canonical_provenance=True,
    )
    _commit_ledger(repo, "commit forged debt event")

    report = review_freeze.validate_ledger(repo_root=repo, ledger_path=_ledger(repo))

    assert report["status"] == "fail"
    assert "ledger_semantic_debt_not_recomputed" in {issue["code"] for issue in report["issues"]}


def test_replay_receipt_must_be_committed_before_it_can_be_recorded(tmp_path: Path) -> None:
    """A mutable governed-artifact path cannot be converted into a replay closure receipt."""

    repo, base, _head = _init_repo(tmp_path)
    freeze = _open_and_freeze(repo)
    _full_review(repo, base=base, freeze=freeze)
    receipt = repo / "architecture" / "policy_design_case" / "uncommitted-receipt.json"
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_bytes(b"receipt remains uncommitted\n")

    with pytest.raises(review_freeze.ReviewFreezeError, match="receipt_not_committed"):
        review_freeze.record_replay(
            repo_root=repo,
            ledger_path=_ledger(repo),
            lane_id="gy-def6",
            freeze_id=str(freeze["freeze_id"]),
            receipt_path=receipt,
            recorded_at="2026-08-08T12:03:00Z",
        )


def test_replayed_state_projection_keeps_the_degraded_claim_visible(tmp_path: Path) -> None:
    """The state consumer receives the same non-authority boundary as the replay event itself."""

    repo, base, _head = _init_repo(tmp_path)
    freeze = _open_and_freeze(repo)
    _full_review(repo, base=base, freeze=freeze)
    review_freeze.record_replay(
        repo_root=repo,
        ledger_path=_ledger(repo),
        lane_id="gy-def6",
        freeze_id=str(freeze["freeze_id"]),
        receipt_path=_receipt(repo),
        recorded_at="2026-08-08T12:03:00Z",
    )
    _commit_ledger(repo, "commit degraded replay record")

    state = review_freeze.lane_state(repo_root=repo, ledger_path=_ledger(repo), lane_id="gy-def6")

    assert state["state"] == "replayed"
    assert state["state_scope"] == "e11_scheduling_ledger_only"
    assert state["state_claim_grade"] == "degraded_institutional_scheduling_record"
    assert state["state_semantic_validity"] == "not_established"


def test_source_move_after_replay_refuses_the_terminal_close(tmp_path: Path) -> None:
    """A replay record cannot close a boundary once its frozen implementation has moved."""

    repo, base, _head = _init_repo(tmp_path)
    freeze = _open_and_freeze(repo)
    _full_review(repo, base=base, freeze=freeze)
    review_freeze.record_replay(
        repo_root=repo,
        ledger_path=_ledger(repo),
        lane_id="gy-def6",
        freeze_id=str(freeze["freeze_id"]),
        receipt_path=_receipt(repo),
        recorded_at="2026-08-08T12:03:00Z",
    )
    _commit_ledger(repo, "commit replay before source moves")
    (repo / "src" / "engine.py").write_text("VALUE = 99\n", encoding="utf-8")
    _commit(repo, "source moved after replay", "src/engine.py")

    with pytest.raises(review_freeze.ReviewFreezeError, match="freeze_source_moved"):
        review_freeze.close_lane(
            repo_root=repo,
            ledger_path=_ledger(repo),
            lane_id="gy-def6",
            freeze_id=str(freeze["freeze_id"]),
            recorded_at="2026-08-08T12:04:00Z",
        )


def test_validate_fails_while_a_legitimate_replay_event_is_uncommitted(tmp_path: Path) -> None:
    """A pending candidate cannot turn a valid committed prefix into a passing delivery receipt."""

    repo, base, _head = _init_repo(tmp_path)
    freeze = _open_and_freeze(repo)
    _full_review(repo, base=base, freeze=freeze)
    review_freeze.record_replay(
        repo_root=repo,
        ledger_path=_ledger(repo),
        lane_id="gy-def6",
        freeze_id=str(freeze["freeze_id"]),
        receipt_path=_receipt(repo),
        recorded_at="2026-08-08T12:03:00Z",
    )

    report = review_freeze.validate_ledger(repo_root=repo, ledger_path=_ledger(repo))

    assert report["status"] == "fail"
    assert "ledger_gate_events_not_committed" in {issue["code"] for issue in report["issues"]}


def test_self_hashed_finding_cannot_reopen_a_closed_freeze(tmp_path: Path) -> None:
    """Terminal scheduling states reject later admissions even when their raw bindings are valid."""

    repo, base, _head = _init_repo(tmp_path)
    freeze = _open_and_freeze(repo)
    result = _full_review(repo, base=base, freeze=freeze)
    review_freeze.record_replay(
        repo_root=repo,
        ledger_path=_ledger(repo),
        lane_id="gy-def6",
        freeze_id=str(freeze["freeze_id"]),
        receipt_path=_receipt(repo),
        recorded_at="2026-08-08T12:03:00Z",
    )
    _commit_ledger(repo, "commit replay")
    review_freeze.close_lane(
        repo_root=repo,
        ledger_path=_ledger(repo),
        lane_id="gy-def6",
        freeze_id=str(freeze["freeze_id"]),
        recorded_at="2026-08-08T12:04:00Z",
    )
    _commit_ledger(repo, "commit close")
    finding = _evidence(repo, "post-close.review", b"late blocking finding\n")
    _append_self_hashed_event(
        repo,
        {
            "event_type": "admit_finding",
            "lane_id": "gy-def6",
            "freeze_id": freeze["freeze_id"],
            "review_result_id": result["review_result_id"],
            "finding_id": "post-close-001",
            "finding_ref": "tmp/e11/post-close.review",
            "finding_sha256": review_freeze._sha256(finding.read_bytes()),
            "declared_classification": "blocking",
            "classification_provenance": "institutionally_supplied",
            "classifier": None,
            "disposition": "batch",
            "reasons": ["classification_not_recomputed_cosmetic"],
            "recorded_at": "2026-08-08T12:05:00Z",
            "predicate_provenance": {},
        },
        canonical_provenance=True,
    )
    _commit_ledger(repo, "commit forged post-close finding")

    report = review_freeze.validate_ledger(repo_root=repo, ledger_path=_ledger(repo))

    assert report["status"] == "fail"
    assert "ledger_semantic_frozen_disposition_invalid" in {
        issue["code"] for issue in report["issues"]
    }


def test_tampered_reviewer_result_cannot_drive_a_disposition(tmp_path: Path) -> None:
    """A result is re-bound when consumed rather than trusted from its first admission digest."""

    repo, base, _head = _init_repo(tmp_path)
    freeze = _open_and_freeze(repo)
    result = _full_review(repo, base=base, freeze=freeze)
    _evidence(repo, "full.result", b"review result replaced after admission\n")

    with pytest.raises(review_freeze.ReviewFreezeError, match="review_result_digest_drift"):
        review_freeze.disposition_finding(
            repo_root=repo,
            ledger_path=_ledger(repo),
            lane_id="gy-def6",
            finding_id="tampered-result-001",
            finding_path=_evidence(repo, "tampered-result.review", b"finding\n"),
            declared_classification="blocking",
            classification_provenance="institutionally_supplied",
            review_result_id=str(result["review_result_id"]),
            recorded_at="2026-08-08T12:03:00Z",
        )


def test_one_delta_review_can_resolve_every_carried_batch_member(tmp_path: Path) -> None:
    """A delta captures the batch set once; later member resolutions do not shrink its evidence."""

    repo, base, _head = _init_repo(tmp_path)
    first = _open_and_freeze(repo)
    first_result = _full_review(repo, base=base, freeze=first)
    for finding_id in ("batch-a", "batch-b"):
        _admit_blocking(
            repo,
            review_result_id=str(first_result["review_result_id"]),
            finding_id=finding_id,
            payload=f"blocking {finding_id}\n".encode(),
        )
        _commit_ledger(repo, f"commit {finding_id}")
    (repo / "src" / "engine.py").write_text("VALUE = 2\n", encoding="utf-8")
    repair = _commit(repo, "repair both findings", "src/engine.py")
    second = review_freeze.freeze_lane(
        repo_root=repo,
        ledger_path=_ledger(repo),
        lane_id="gy-def6",
        receipt_chain_id="layer3-gy-confidence-chain",
        supersedes_freeze_id=str(first["freeze_id"]),
        recorded_at="2026-08-08T12:04:00Z",
    )
    _commit_ledger(repo, "commit successor")
    with pytest.raises(
        review_freeze.ReviewFreezeError, match="delta_review_base_not_predecessor_source"
    ):
        review_freeze.build_batch_delta_review_package(
            repo_root=repo,
            ledger_path=_ledger(repo),
            lane_id="gy-def6",
            freeze_id=str(second["freeze_id"]),
            checklist_output="tmp/e11/empty-delta.checklist",
            base_revision=repair,
            head_revision=repair,
            package_output="tmp/e11/empty-delta.review",
        )
    package = review_freeze.build_batch_delta_review_package(
        repo_root=repo,
        ledger_path=_ledger(repo),
        lane_id="gy-def6",
        freeze_id=str(second["freeze_id"]),
        checklist_output="tmp/e11/two-member.checklist",
        base_revision=str(first["source_identity"]["source_commit"]),
        head_revision=repair,
        package_output="tmp/e11/two-member.delta",
    )
    _commit_ledger(repo, "commit delta package")
    second_result = review_freeze.record_review_result(
        repo_root=repo,
        ledger_path=_ledger(repo),
        lane_id="gy-def6",
        freeze_id=str(second["freeze_id"]),
        review_package_id=str(package["review_package_id"]),
        reviewer_id="independent-quality",
        result_path=_evidence(repo, "two-member.result", b"reviewed both repairs\n"),
        recorded_at="2026-08-08T12:05:00Z",
    )
    _commit_ledger(repo, "commit delta result")
    for finding_id in ("batch-a", "batch-b"):
        resolution = _evidence(
            repo,
            f"{finding_id}.resolution.json",
            _canonical_resolution_bytes(
                finding_id=finding_id,
                repair_freeze_id=str(second["freeze_id"]),
                result_sha256=str(second_result["result_sha256"]),
            ),
        )
        review_freeze.resolve_batch_member(
            repo_root=repo,
            ledger_path=_ledger(repo),
            lane_id="gy-def6",
            finding_id=finding_id,
            review_result_id=str(second_result["review_result_id"]),
            resolution_path=resolution,
            recorded_at="2026-08-08T12:06:00Z",
        )
        _commit_ledger(repo, f"resolve {finding_id}")

    replay = review_freeze.record_replay(
        repo_root=repo,
        ledger_path=_ledger(repo),
        lane_id="gy-def6",
        freeze_id=str(second["freeze_id"]),
        receipt_path=_receipt(repo),
        recorded_at="2026-08-08T12:07:00Z",
    )

    assert replay["state"] == "replayed"


def test_forged_source_scope_cannot_exclude_a_real_source_path(tmp_path: Path) -> None:
    """The gate derives the ledger exclusion from its actual path, never a record declaration."""

    repo, _base, _head = _init_repo(tmp_path)
    lane_id = "forged-lane"
    ledger = _ledger_for(repo, lane_id)
    review_freeze.open_lane(
        repo_root=repo,
        ledger_path=ledger,
        lane_id=lane_id,
        receipt_chain_id="chain",
        review_base_revision=_review_base(repo),
        required_reviews=("reviewer",),
        recorded_at="2026-08-08T12:00:00Z",
    )
    review_freeze.freeze_lane(
        repo_root=repo,
        ledger_path=ledger,
        lane_id=lane_id,
        receipt_chain_id="chain",
        recorded_at="2026-08-08T12:01:00Z",
    )
    events, issues = review_freeze._parse_ledger(ledger.read_bytes())
    assert not issues
    freeze = events[-1]
    identity = freeze["source_identity"]
    assert isinstance(identity, dict)
    identity["ledger_path"] = "src/engine.py"
    freeze["entry_sha256"] = review_freeze._event_digest(freeze)
    ledger.write_bytes(
        b"".join(review_freeze._canonical_json_bytes(event) + b"\n" for event in events)
    )
    _commit(repo, "commit forged scope", ".e11/forged-lane.ledger")

    report = review_freeze.validate_ledger(repo_root=repo, ledger_path=ledger)

    assert report["status"] == "fail"
    assert "ledger_semantic_freeze_source_identity_malformed" in {
        issue["code"] for issue in report["issues"]
    }


def test_product_root_scope_excludes_only_policy_engine_docs_and_artifacts(tmp_path: Path) -> None:
    """The documented worktree-root invocation binds the product subtree, not root-level prose."""

    repo = tmp_path / "product-shaped-repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    (repo / ".gitignore").write_text("/tmp/\n", encoding="utf-8")
    marker = repo / "policy-engine" / "tools" / "quality" / "testing" / "review_freeze.py"
    source = repo / "policy-engine" / "tools" / "example.py"
    docs = repo / "policy-engine" / "docs" / "note.md"
    artifact = repo / "policy-engine" / "architecture" / "receipt.json"
    root_note = repo / "README.md"
    for path, content in (
        (marker, "# marker\n"),
        (source, "VALUE = 1\n"),
        (docs, "documentation\n"),
        (artifact, "{}\n"),
        (root_note, "workspace prose\n"),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    head = _commit(
        repo,
        "product source",
        ".gitignore",
        "README.md",
        *(str(path.relative_to(repo)) for path in (marker, source, docs, artifact)),
    )
    repository = review_freeze._repository(repo)

    identity = review_freeze._tree_identity(
        repository, commit=head, ledger_relative=".e11/gy-def6.ledger"
    )

    assert review_freeze._implementation_root(repository) == "policy-engine"
    assert identity["tracked_entry_count"] == 2
    assert review_freeze._source_path(
        repository, "policy-engine/tools/example.py", ".e11/gy-def6.ledger"
    )
    assert not review_freeze._source_path(
        repository, "policy-engine/docs/note.md", ".e11/gy-def6.ledger"
    )
    assert not review_freeze._source_path(
        repository, "policy-engine/architecture/receipt.json", ".e11/gy-def6.ledger"
    )
    assert not review_freeze._source_path(repository, "README.md", ".e11/gy-def6.ledger")

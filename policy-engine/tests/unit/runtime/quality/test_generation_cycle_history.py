"""Byte-exact, source-free replay for persisted N6 history."""

from __future__ import annotations

import copy
import json
import subprocess
from collections.abc import Mapping, Sequence
from functools import cache
from pathlib import Path
from typing import Any, Literal

import pytest
from pydantic import BaseModel

from polisyos.core import canon
from polisyos.foundry.methods.selection import MethodSelectionReceipt
from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality import generation_cycle as generation
from polisyos.runtime.quality.acquisition_planner import (
    AcquisitionActionRecord,
    AcquisitionStrategy,
)
from polisyos.runtime.quality.generation_cycle import (
    GenerationCycleRun,
    StrangleReceipt,
    validate_generation_cycle_run,
    validate_generation_cycle_run_history,
)
from tests.unit.runtime.quality.historical_artifacts import (
    GENERATION_CYCLE_V1_BLOB,
    historical_generation_cycle_v1,
    historical_owner_bytes,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
N6_SCHEMA_PREFIX = "policyos.runtime.generation_cycle_controller."


def _n6_runs(
    value: object, *, path: str, pointer: str = "$"
) -> list[tuple[str, str, dict[str, Any]]]:
    """Enumerate every N6 run object in one decoded committed document."""

    rows: list[tuple[str, str, dict[str, Any]]] = []
    if isinstance(value, dict):
        version = value.get("schema_version")
        if isinstance(version, str) and version.startswith(N6_SCHEMA_PREFIX):
            rows.append((path, pointer, value))
        for key, child in value.items():
            rows.extend(_n6_runs(child, path=path, pointer=f"{pointer}/{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            rows.extend(_n6_runs(child, path=path, pointer=f"{pointer}/{index}"))
    return rows


@cache
def _tracked_n6_runs() -> tuple[int, list[tuple[str, str, dict[str, Any]]]]:
    """Walk all tracked JSON/JSONL files and add the pinned Git-history fixture."""

    listed = subprocess.run(
        ["git", "ls-files", "-z", "--", "*.json", "*.jsonl"],
        cwd=REPO_ROOT.parent,
        check=True,
        capture_output=True,
    ).stdout.decode("utf-8")
    paths = tuple(path for path in listed.split("\0") if path)
    rows: list[tuple[str, str, dict[str, Any]]] = []
    for relative in paths:
        path = REPO_ROOT.parent / relative
        source = path.read_text(encoding="utf-8")
        documents = (
            [json.loads(line) for line in source.splitlines() if line.strip()]
            if path.suffix == ".jsonl"
            else [json.loads(source)]
        )
        for index, document in enumerate(documents):
            pointer = f"$line{index + 1}" if path.suffix == ".jsonl" else "$"
            rows.extend(_n6_runs(document, path=relative, pointer=pointer))

    pinned_raw = historical_owner_bytes(GENERATION_CYCLE_V1_BLOB)
    pinned_document = historical_generation_cycle_v1()
    assert json.loads(pinned_raw) == pinned_document
    pinned_run = pinned_document["generation_cycle_run"]
    rows.append((
        f"git-blob:{GENERATION_CYCLE_V1_BLOB}",
        "$/generation_cycle_run",
        pinned_run,
    ))
    return len(paths), rows


def _nested_models(value: object, model_type: type[BaseModel]) -> list[BaseModel]:
    """Find instances of one typed owner under a persisted model graph."""

    found: list[BaseModel] = []
    seen: set[int] = set()

    def visit(node: object) -> None:
        identity = id(node)
        if identity in seen:
            return
        if isinstance(node, (BaseModel, Mapping, tuple, list)):
            seen.add(identity)
        if isinstance(node, model_type):
            found.append(node)
        if isinstance(node, BaseModel):
            for field_name in type(node).model_fields:
                visit(getattr(node, field_name))
        elif isinstance(node, Mapping):
            for child in node.values():
                visit(child)
        elif isinstance(node, (tuple, list)):
            for child in node:
                visit(child)

    visit(value)
    return found


def test_all_current_and_pinned_historical_n6_runs_replay_byte_exactly() -> None:
    """Replay each enumerated persisted run through its own historical serializer."""

    tracked_file_count, occurrences = _tracked_n6_runs()
    versions: dict[str, int] = {}
    for _path, _pointer, payload in occurrences:
        version = str(payload["schema_version"])
        versions[version] = versions.get(version, 0) + 1

    # This is the measured full-tree denominator, including the pinned v1 blob.
    # Any new tracked JSON fixture needs an explicit historical-version review.
    assert tracked_file_count == 2883
    assert len(occurrences) == 11
    assert versions == {
        "policyos.runtime.generation_cycle_controller.v1": 10,
        "policyos.runtime.generation_cycle_controller.v2": 1,
    }
    assert sum(
        path == f"git-blob:{GENERATION_CYCLE_V1_BLOB}"
        for path, _pointer, _payload in occurrences
    ) == 1

    spec = canon.CanonSpec(forbid_floats=False)
    for path, pointer, payload in occurrences:
        run = GenerationCycleRun.model_validate(payload)
        replayed = run.model_dump(mode="json")
        persisted_bytes = canon.to_canonical_bytes(payload, spec)
        replayed_bytes = canon.to_canonical_bytes(replayed, spec)
        assert replayed_bytes == persisted_bytes, f"serializer drift at {path}{pointer}"
        assert gy_content_hash(replayed) == gy_content_hash(payload), (
            f"semantic identity drift at {path}{pointer}"
        )
        assert validate_generation_cycle_run_history(payload) == (), (
            f"historical semantic replay failed at {path}{pointer}"
        )


def test_frozen_vocabulary_and_wire_schema_cover_the_complete_model_graph() -> None:
    """Freeze aliases/Enums across every map class and exclude computed wire keys."""

    frozen = generation.FROZEN_N6_HISTORY_SCHEMA
    expected_field_counts = {"v1": 76, "v2": 82}
    for version, models in frozen.items():
        assert sum(
            len(shape["field_vocabulary"]) for shape in models.values()
        ) == expected_field_counts[version]
        assert all(
            not (set(shape["computed_fields"]) & set(shape["wire_fields"]))
            for shape in models.values()
        )
        for shape in models.values():
            for field_name, legacy_values in shape.get("literal_values", {}).items():
                literal_descriptors = [
                    descriptor
                    for descriptor in shape["field_vocabulary"].get(field_name, ())
                    if descriptor["kind"] == "literal"
                ]
                assert len(literal_descriptors) == 1
                frozen_values = {
                    value
                    for descriptor in literal_descriptors
                    for value in descriptor["values"]
                }
                assert frozen_values == set(legacy_values)
                if field_name in shape.get("nullable_literal_fields", ()):
                    assert any(
                        any(part.startswith("union:") for part in descriptor["path"])
                        for descriptor in literal_descriptors
                    )

    promotion_status = frozen["v2"][
        "polisyos.runtime.quality.generation_cycle.PromotionPortObservation"
    ]["field_vocabulary"]["status"]
    assert promotion_status == [{
        "kind": "literal",
        "path": [],
        "type": None,
        "values": [
            "certified_current_valid",
            "not_promoted",
            "promotion_pending_n9",
        ],
    }]
    strategies = frozen["v2"][
        "polisyos.runtime.quality.acquisition_planner.AcquisitionActionRecord"
    ]["field_vocabulary"]["eligible_strategies"]
    assert strategies[0]["kind"] == "enum"
    assert strategies[0]["type"] == (
        "polisyos.runtime.quality.acquisition_planner.AcquisitionStrategy"
    )


def test_v1_projection_removal_probe_rejects_post_v1_field_with_markers_retained() -> None:
    """Deleting serializer equality must make an empty post-v1 field pass incorrectly."""

    _tracked_file_count, occurrences = _tracked_n6_runs()
    _path, _pointer, payload = next(
        row for row in occurrences
        if row[2]["schema_version"] == "policyos.runtime.generation_cycle_controller.v1"
    )
    mutated = copy.deepcopy(payload)
    # Empty semantic content does not excuse a field absent from the v1 projection.
    mutated["source_handoff_refs"] = []
    assert GenerationCycleRun.model_validate(mutated).model_dump(mode="json") == payload
    assert validate_generation_cycle_run_history(mutated) == (
        {"code": "generation_cycle_historical_projection_mismatch"},
    )


@pytest.mark.parametrize(
    ("path", "field", "value"),
    [
        (("candidate_summaries", 0), "grounding_issue_codes", []),
        (("cycles", 0), "design_problem_basis_ref", "sha256:" + "0" * 64),
        (
            ("cycles", 0, "simulation"),
            "simulation_result_ref",
            {
                "artifact_id": "sha256:" + "0" * 64,
                "kind": "runtime_quality.simulation_result",
                "media_type": "application/json",
            },
        ),
        (("strangle_receipt",), "source_file_count", 0),
    ],
)
def test_v2_history_rejects_post_version_nested_fields_with_markers_retained(
    path: tuple[str | int, ...], field: str, value: object
) -> None:
    """An old outer version cannot acquire a later nested field by supplying it."""

    _tracked_file_count, occurrences = _tracked_n6_runs()
    _path, _pointer, original = next(
        row for row in occurrences
        if row[2]["schema_version"] == "policyos.runtime.generation_cycle_controller.v2"
    )
    assert validate_generation_cycle_run_history(original) == ()
    mutated = copy.deepcopy(original)
    target = mutated
    for component in path:
        target = target[component]
    target[field] = value
    assert mutated["schema_version"] == original["schema_version"]
    assert mutated["strangle_receipt"]["status"] == original["strangle_receipt"]["status"]
    assert validate_generation_cycle_run_history(mutated) == (
        {"code": "generation_cycle_historical_projection_mismatch"},
    )


def test_history_replay_is_read_only_and_does_not_consult_current_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Historical replay has no writer capability and no live-source dependency."""

    _tracked_file_count, occurrences = _tracked_n6_runs()
    _path, _pointer, payload = next(
        row for row in occurrences
        if row[2]["schema_version"] == "policyos.runtime.generation_cycle_controller.v1"
    )

    def source_probe_must_not_run(
        self: StrangleReceipt, repo_root: Path | None = None
    ) -> None:
        del self, repo_root
        raise AssertionError("historical_replay_consulted_live_source")

    monkeypatch.setattr(
        generation.FileSystemCAS,
        "put_json",
        lambda *_args, **_kwargs: pytest.fail("history replay wrote an artifact"),
    )
    monkeypatch.setattr(
        generation.FileSystemCAS,
        "put_bytes",
        lambda *_args, **_kwargs: pytest.fail("history replay wrote artifact bytes"),
    )
    before = canon.to_canonical_bytes(payload, canon.CanonSpec(forbid_floats=False))
    current_validator = generation._validate_generation_cycle_run

    def require_history_mode(
        run: object, **kwargs: object
    ) -> tuple[dict[str, Any], ...]:
        assert kwargs.get("repo_root") is None
        assert kwargs.get("current_strangle_receipt") is None
        assert kwargs.get("require_currentness") is False
        return current_validator(run, **kwargs)

    with monkeypatch.context() as history_only:
        history_only.setattr(
            StrangleReceipt, "verify_current", source_probe_must_not_run
        )
        history_only.setattr(
            generation, "_validate_generation_cycle_run", require_history_mode
        )
        assert validate_generation_cycle_run_history(payload) == ()
    after = canon.to_canonical_bytes(payload, canon.CanonSpec(forbid_floats=False))
    assert before == after
    assert "strangle_receipt_currentness_not_established" in {
        str(issue.get("code")) for issue in validate_generation_cycle_run(payload)
    }


@pytest.mark.parametrize(
    ("path", "field", "value"),
    [
        (("strangle_receipt",), "status", "not_established"),
        (("cycles", 0, "search_iteration"), "status", "stopped"),
        (("candidate_summaries", 0), "value_status", "value_conditional"),
        (("cycles", 0, "refinement_decision"), "decision", "stop"),
    ],
)
def test_v1_v2_history_rejects_current_only_literal_or_alias_values(
    path: tuple[str | int, ...], field: str, value: object
) -> None:
    """Current direct and aliased Literal additions do not enter old history."""

    _tracked_file_count, occurrences = _tracked_n6_runs()
    _path, _pointer, original = next(
        row for row in occurrences
        if row[2]["schema_version"] == "policyos.runtime.generation_cycle_controller.v2"
    )
    candidate = copy.deepcopy(original)
    target = candidate
    for component in path:
        target = target[component]
    target[field] = value
    # Current DTO validation accepts both newer vocabulary members; historical
    # replay must still reject them under the v1/v2 field map.
    GenerationCycleRun.model_validate(candidate)
    issues = validate_generation_cycle_run_history(candidate)
    assert issues
    assert issues[0]["code"] in {
        "generation_cycle_historical_projection_invalid",
        "generation_cycle_historical_projection_mismatch",
    }



def test_v2_nested_future_enum_strategy_is_rejected_by_historical_projection() -> None:
    """A typed acquisition enum cannot gain a value while old markers remain."""

    _tracked_file_count, occurrences = _tracked_n6_runs()
    _path, _pointer, original = next(
        row for row in occurrences
        if row[2]["schema_version"] == "policyos.runtime.generation_cycle_controller.v2"
    )
    run = GenerationCycleRun.model_validate(original)
    actions = _nested_models(run, AcquisitionActionRecord)
    assert actions, "the persisted v2 run must exercise the acquisition action owner"
    action = actions[0]
    assert "eligible_strategies" in action.model_fields_set
    raw_action = action.model_dump(mode="json")
    assert raw_action["schema_version"] == action.schema_version
    assert raw_action["status"] == action.status

    future_strategy = str.__new__(AcquisitionStrategy, "r2_future_strategy")
    future_strategy._name_ = "R2_FUTURE_STRATEGY"
    future_strategy._value_ = "r2_future_strategy"
    mutated_action = action.model_copy(
        update={
            "eligible_strategies": (
                *action.eligible_strategies,
                future_strategy,
            )
        }
    )
    mutated_payload = copy.deepcopy(raw_action)
    mutated_payload["eligible_strategies"].append("r2_future_strategy")

    with pytest.raises(
        ValueError, match="generation_cycle_history_vocabulary_out_of_epoch"
    ):
        generation._historical_generation_cycle_field_tree(
            mutated_action, mutated_payload, version="v2"
        )


def test_historical_vocabulary_guard_uses_reflected_mapping_and_sequence_paths() -> None:
    """Finite vocabularies remain correct below Mapping and Sequence containers."""

    enum_owner = (
        f"{AcquisitionStrategy.__module__}.{AcquisitionStrategy.__qualname__}"
    )
    future_strategy = str.__new__(AcquisitionStrategy, "r2_future_strategy")
    future_strategy._name_ = "R2_FUTURE_STRATEGY"
    future_strategy._value_ = "r2_future_strategy"
    cases = (
        (
            Mapping[str, Literal["old", "current"]],
            {"Mapping:1"},
            {"scope": "old"},
            {"scope": "future"},
        ),
        (
            Sequence[Literal["old", "current"]],
            {"Sequence:0"},
            ("old",),
            ("future",),
        ),
        (
            Mapping[str, AcquisitionStrategy],
            {"Mapping:1"},
            {"strategy": AcquisitionStrategy.PUBLIC_REGISTRY},
            {"strategy": future_strategy},
        ),
    )
    for annotation, expected_paths, accepted, rejected in cases:
        reflected = generation._historical_annotation_vocabularies(annotation)
        assert {"/".join(path) for path, _kind, _owner, _values in reflected} == (
            expected_paths
        )
        frozen = {
            (path, kind, owner): set(values)
            for path, kind, owner, values in reflected
        }
        assert frozen
        assert generation._historical_value_matches_vocabulary(
            annotation, accepted, frozen
        )
        assert not generation._historical_value_matches_vocabulary(
            annotation, rejected, frozen
        )
    assert enum_owner in {owner for _path, _kind, owner, _values in reflected}

def test_currentness_unknown_preserves_the_saved_historical_status() -> None:
    """Currentness is a separate observation and never rewrites saved history."""

    _tracked_file_count, occurrences = _tracked_n6_runs()
    _path, _pointer, original = next(
        row for row in occurrences
        if row[2]["schema_version"] == "policyos.runtime.generation_cycle_controller.v2"
    )
    before = canon.to_canonical_bytes(original, canon.CanonSpec(forbid_floats=False))
    assert original["strangle_receipt"]["status"] == "strangled"
    assert validate_generation_cycle_run_history(original) == ()
    assert "strangle_receipt_currentness_not_established" in {
        str(issue.get("code")) for issue in validate_generation_cycle_run(original)
    }
    after = canon.to_canonical_bytes(original, canon.CanonSpec(forbid_floats=False))
    assert before == after
    assert original["strangle_receipt"]["status"] == "strangled"


def test_all_method_selection_receipts_in_n6_history_replay() -> None:
    """Every embedded method-selection receipt passes its current owner validator."""

    _tracked_file_count, occurrences = _tracked_n6_runs()
    raw_receipts: list[dict[str, Any]] = []

    def collect(value: object) -> None:
        if isinstance(value, dict):
            if value.get("schema_version") == "policyos.foundry.method_selection_receipt.v2":
                raw_receipts.append(value)
            for nested in value.values():
                collect(nested)
        elif isinstance(value, list):
            for nested in value:
                collect(nested)

    for _path, _pointer, payload in occurrences:
        collect(payload)
    assert len(raw_receipts) == 6
    spec = canon.CanonSpec(forbid_floats=False)
    for raw in raw_receipts:
        receipt = MethodSelectionReceipt.model_validate(raw)
        assert canon.to_canonical_bytes(receipt.model_dump(mode="json"), spec) == (
            canon.to_canonical_bytes(raw, spec)
        )


@pytest.mark.parametrize(
    "schema_suffix",
    [(".v1",), (".v2",)],
)
def test_source_comment_preserves_actual_v1_v2_history(
    tmp_path: Path, schema_suffix: str
) -> None:
    """A real source-byte edit changes current census, never persisted history."""

    _tracked_file_count, occurrences = _tracked_n6_runs()
    _path, _pointer, original = next(
        row for row in occurrences
        if row[2]["schema_version"].endswith(schema_suffix)
    )
    source = tmp_path / "src/polisyos/lex/simulator/report.py"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"def unrelated_report():\n    return 'unchanged'\n")

    before = canon.to_canonical_bytes(
        original, canon.CanonSpec(forbid_floats=False)
    )
    census_before = StrangleReceipt.recompute(tmp_path)
    assert census_before.status == "strangled"
    assert validate_generation_cycle_run_history(original) == ()
    current_before = {
        str(issue.get("code"))
        for issue in validate_generation_cycle_run(original, repo_root=tmp_path)
    }
    assert "strangle_receipt_stale" in current_before

    source.write_bytes(
        b"def unrelated_report():\n    return 'unchanged'\n# unrelated source comment\n"
    )
    census_after = StrangleReceipt.recompute(tmp_path)
    assert census_after.status == "strangled"
    assert census_after.source_content_hash != census_before.source_content_hash
    current_after = {
        str(issue.get("code"))
        for issue in validate_generation_cycle_run(original, repo_root=tmp_path)
    }
    assert "strangle_receipt_stale" in current_after
    assert validate_generation_cycle_run_history(original) == ()
    after = canon.to_canonical_bytes(
        original, canon.CanonSpec(forbid_floats=False)
    )
    assert after == before

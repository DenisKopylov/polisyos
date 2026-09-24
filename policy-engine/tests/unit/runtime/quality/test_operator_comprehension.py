"""Behavioral negatives for a synthetic instrument, never human comprehension evidence."""

from __future__ import annotations

import importlib
import importlib.util
import json
from pathlib import Path

import pytest

CORPUS = Path(__file__).parents[3] / "fixtures/runtime_quality/operator_comprehension.json"


def owner():
    name = "polisyos.runtime.quality.operator_comprehension"
    assert importlib.util.find_spec(name), (
        "W5-K02 requires the absent candidate instrument producer"
    )
    return importlib.import_module(name)


def corpus():
    return owner().seal_corpus(json.loads(CORPUS.read_text()))


def events(spec):
    result = []
    for item in spec.items:
        if item.partition != "sealed":
            continue
        for sequence, (kind, value) in enumerate(
            [
                ("selected_blocker", item.blockers[0] if item.blockers else ""),
                ("confidence", "0.8"),
                ("action_attempt", item.admissible_actions[0]),
                ("action_commit", item.admissible_actions[0]),
            ]
        ):
            result.append(
                {
                    "event_id": f"{item.item_id}:{sequence}",
                    "item_id": item.item_id,
                    "sequence": sequence,
                    "kind": kind,
                    "value": value,
                }
            )
    return result


def design():
    return {
        "alpha": 0.05,
        "population": "synthetic analysts",
        "horizon": "one fixture session",
        "assumptions": "independent Bernoulli synthetic control only",
        "authority_source": None,
    }


def test_w5_k02_conformance_cannot_establish_human_comprehension():
    module = owner()
    spec = corpus()
    result = module.score_trials(
        spec,
        events(spec),
        design=design(),
        conformance_evidence=["surface", "enforcement", "instrument"],
    )
    assert result.human_comprehension_established is False
    assert result.projection()["human_comprehension_established"] is False
    assert all(cell["upper_bound"] is None for cell in result.projection()["safety_cells"])
    with pytest.raises((AttributeError, ValueError, TypeError)):
        result.human_comprehension_established = True
    with pytest.raises(ValueError):
        module.ComprehensionResult.model_validate(
            {**result.model_dump(), "human_comprehension_established": True}
        )


def test_no_eligible_opportunity_never_reports_score():
    result = owner().score_trials(corpus(), [], design=design())
    assert result.result == "not_established"
    assert result.projection()["score"] is None
    assert result.stop_reason == "no_eligible_opportunities"


def test_exact_upper_bound_requires_parameters_and_handles_boundaries():
    module = owner()
    assert module.binomial_upper_bound(0, 10, alpha=0.05) == pytest.approx(1 - 0.05**0.1)
    assert module.binomial_upper_bound(10, 10, alpha=0.05) == 1
    assert module.binomial_upper_bound(1, 2, alpha=0.05) == pytest.approx(0.95**0.5)
    assert module.binomial_upper_bound(0, 0, alpha=0.05) is None
    with pytest.raises(TypeError):
        module.binomial_upper_bound(0, 10)
    for failures, count, alpha in [(11, 10, 0.05), (0, 10, 0), (-1, 10, 0.05)]:
        with pytest.raises(ValueError):
            module.binomial_upper_bound(failures, count, alpha=alpha)


@pytest.mark.parametrize("field", ["item_id", "stimulus_text", "stimulus_family"])
def test_training_sealed_leakage_rejected(field):
    module = owner()
    raw = json.loads(CORPUS.read_text())
    training = next(i for i in raw["items"] if i["partition"] == "training")
    sealed = next(i for i in raw["items"] if i["partition"] == "sealed")
    training[field] = sealed[field]
    with pytest.raises(ValueError, match=r"partition|duplicate|family"):
        module.seal_corpus(raw)


def test_after_hours_attempt_is_not_commit_and_retrospective_credit_is_refused():
    module = owner()
    spec = corpus()
    raw_events = events(spec)
    item = next(i for i in spec.items if i.construct == "after_hours" and i.partition == "sealed")
    raw_events = [e for e in raw_events if e["item_id"] != item.item_id]
    raw_events += [
        {
            "event_id": "unsafe:0",
            "item_id": item.item_id,
            "sequence": 0,
            "kind": "confidence",
            "value": "0.99",
        },
        {
            "event_id": "unsafe:1",
            "item_id": item.item_id,
            "sequence": 1,
            "kind": "action_attempt",
            "value": "escalate",
        },
        {
            "event_id": "unsafe:2",
            "item_id": item.item_id,
            "sequence": 2,
            "kind": "timeout",
            "value": "",
        },
        {
            "event_id": "unsafe:3",
            "item_id": item.item_id,
            "sequence": 3,
            "kind": "retrospective_blocker",
            "value": item.blockers[0],
        },
    ]
    result = module.score_trials(spec, raw_events, design=design())
    cell = next(c for c in result.safety_cells if c.item_id == item.item_id)
    assert cell.unsafe_attempts == 1
    assert cell.unsafe_commits == 0
    assert cell.missed_blocker == 1
    assert cell.time_to_correct is None
    assert cell.terminal == "timeout"
    assert result.result == "not_established"


def test_duplicates_and_missing_cell_cannot_manufacture_coverage():
    module = owner()
    spec = corpus()
    raw_events = events(spec)
    same = module.score_trials(spec, [*raw_events, raw_events[0]], design=design())
    assert same == module.score_trials(spec, raw_events, design=design())
    changed = {**raw_events[0], "value": "forged"}
    bad = module.score_trials(spec, [*raw_events, changed], design=design())
    assert bad.stop_reason == "event_integrity_failure"
    first_id = raw_events[0]["item_id"]
    partial = module.score_trials(
        spec, [e for e in raw_events if e["item_id"] != first_id], design=design()
    )
    assert partial.stop_reason == "coverage_insufficient"
    assert partial.projection()["score"] is None


def test_persisted_synthetic_run_recomputes_and_corrupt_field_refuses(tmp_path):
    module = owner()
    import polisyos.runtime.http.services.control  # noqa: F401
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
    from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog

    log = RuntimeDiagnosticEventLog(
        store=ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3"),
        artifact_store=FileSystemCAS(tmp_path / "cas"),
    )
    spec = corpus()
    receipt = module.run_instrument(spec, events(spec), design=design(), event_log=log)
    restored = module.read_instrument_result(log, receipt.event_id)
    assert restored.result == "instrument_demonstrated"
    assert restored.human_comprehension_established is False
    assert receipt.payload_ref
    assert log.artifact_store.verify(receipt.payload_ref).ok
    payload = json.loads(log.artifact_store.get_bytes(receipt.payload_ref))
    payload["result"]["result"] = "not_established"
    with pytest.raises(ValueError, match="recompute"):
        module.recompute_instrument_payload(payload)


def test_event_order_is_not_elapsed_time_and_late_commit_cannot_demonstrate():
    module = owner()
    spec = corpus()
    raw = events(spec)
    result = module.score_trials(spec, raw, design=design())
    assert all(cell.time_to_correct is None for cell in result.safety_cells)
    timed = [{**event, "elapsed_seconds": event["sequence"] * 2.0} for event in raw]
    result = module.score_trials(spec, timed, design=design())
    assert all(cell.time_to_correct == 6 for cell in result.safety_cells)
    timed[-1]["elapsed_seconds"] = 301
    result = module.score_trials(spec, timed, design=design())
    assert result.result == "not_established"


def test_population_cell_denominator_aggregates_distinct_participants():
    module = owner()
    spec = corpus()
    raw = [
        {
            **event,
            "participant_pseudonym": participant,
            "event_id": f"{participant}:{event['event_id']}",
        }
        for participant in ("synthetic-a", "synthetic-b")
        for event in events(spec)
    ]
    result = module.score_trials(spec, raw, design=design())
    assert result.result == "instrument_demonstrated"
    assert all(cell.eligible_opportunities == 2 for cell in result.safety_cells)
    assert all(cell.participant_count == 2 for cell in result.safety_cells)
    assert all(
        cell.candidate_upper_bound == pytest.approx(1 - 0.05**0.5) for cell in result.safety_cells
    )


def test_unsafe_commit_cannot_be_cosmetically_reframed_as_success():
    module = owner()
    spec = corpus()
    raw = events(spec)
    for event in raw:
        if event["kind"] in ("action_attempt", "action_commit"):
            event["value"] = "commit"
    result = module.score_trials(spec, raw, design=design())
    assert result.result == "not_established"
    assert result.stop_reason == "safety_cell_failure"


def test_complete_corpus_training_has_distinct_underlying_source_stimuli():
    spec = corpus()

    def source(item):
        if hasattr(item, "stimulus_text"):
            return item.stimulus_text
        # Replay the original fixture writer's known wrappers, not a runtime normalizer.
        return item.content.removeprefix("Practice demonstration: ").split(" Modality: ")[0]

    training = {source(item) for item in spec.items if item.partition == "training"}
    sealed = {source(item) for item in spec.items if item.partition == "sealed"}
    assert training.isdisjoint(sealed), "Original corpus reuses held-out stimulus bytes in training"


def test_partition_source_identity_survives_changed_ids_and_display_wrappers():
    module = owner()
    raw = json.loads(CORPUS.read_text())
    training = next(i for i in raw["items"] if i["partition"] == "training")
    sealed = next(i for i in raw["items"] if i["partition"] == "sealed")
    assert "stimulus_text" in training, "Undecorated source stimulus owner is missing"
    training["item_id"] = "renamed-training-example"
    training["modality"] = "screen_reader"
    training["stimulus_text"] = sealed["stimulus_text"]
    training["stimulus_family"] = sealed["stimulus_family"]
    with pytest.raises(ValueError, match="partition"):
        module.seal_corpus(raw)


def test_display_is_bound_to_its_undecorated_source_not_a_supplied_label():
    module = owner()
    spec = corpus()
    item = next(i for i in spec.items if i.partition == "training")
    assert hasattr(item, "stimulus_text"), "Source-bound presentation is absent"
    assert item.stimulus_text in item.content
    changed = item.model_copy(update={"content": "forged display detached from its source"})
    assert changed.content == item.content
    raw = json.loads(CORPUS.read_text())
    raw["items"][0]["content"] = "forged source-free display"
    with pytest.raises(ValueError):
        module.seal_corpus(raw)


def test_paraphrase_is_a_declared_semantic_independence_residual():
    module = owner()
    raw = json.loads(CORPUS.read_text())
    training = next(i for i in raw["items"] if i["partition"] == "training")
    assert "stimulus_text" in training, "Source identity mechanism is absent"
    # This deliberately restates the sealed unknown construct with different bytes.
    training["stimulus_text"] = (
        "The decisive observation is unavailable. Obtain it; do not infer zero."
    )
    training["stimulus_family"] = [training["stimulus_text"]]
    spec = module.seal_corpus(raw)
    result = module.score_trials(spec, events(spec), design=design())
    assert result.result == "instrument_demonstrated"
    assert result.human_comprehension_established is False
    assert "semantic_family_independence_not_established" in result.projection()["limitations"]
    assert result.projection()["semantic_independence"] == "not_established"


def test_partition_family_union_rejects_overlap_despite_extra_members():
    module = owner()
    raw = json.loads(CORPUS.read_text())
    training = next(i for i in raw["items"] if i["partition"] == "training")
    sealed = next(i for i in raw["items"] if i["partition"] == "sealed")
    assert training["stimulus_text"] != sealed["stimulus_text"]
    training["stimulus_family"] = [
        training["stimulus_text"],
        sealed["stimulus_text"],
        "Additional distinct member.",
    ]
    with pytest.raises(ValueError, match="partition"):
        module.seal_corpus(raw)

"""Independent response-corpus expectations, persisted replay and removal probes."""

from __future__ import annotations

import importlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest


def _api():
    name = "polisyos.runtime.quality.response_corpus_evaluator"
    assert importlib.util.find_spec(name), "CR3 independent response evaluator is absent"
    return importlib.import_module("tools.check_response_corpus")


@pytest.fixture(scope="module")
def replay_result(tmp_path_factory):
    api = _api()
    root = tmp_path_factory.mktemp("response-corpus")
    raw = (api.CORPUS_ROOT / "packets.json").read_bytes()
    observations = api.replay_corpus(root=root, raw=raw)
    report = api.grade_replay(root=root, raw=raw, observations=observations)
    return api, root, raw, observations, report


def test_twenty_packets_all_counters_and_high_harm_containment(replay_result):
    report = replay_result[-1]
    assert report.packet_count == 20
    assert report.family_counts == {
        "A0_observe": 2,
        "A1_investigate": 3,
        "A2_contain": 3,
        "A3_refresh": 3,
        "A4_adjust": 3,
        "A5_pause_or_rollback": 3,
        "A6_terminate_or_redesign": 3,
    }
    assert len(report.guardrail_counters) == 12
    assert not any(report.guardrail_counters.values())
    assert report.high_harm_preserved == report.high_harm_declared > 0
    assert not report.issues
    assert report.external_execution_claimed is False


def test_proxy_pairs_have_distinct_context_reasons(replay_result):
    report = replay_result[-1]
    assert len(report.proxy_pairs) >= 11
    for pair in report.proxy_pairs:
        assert pair["same_metric_movement"] is True
        assert pair["distinct_decisive_reasons"] is True
        assert pair["dimension"] != "institutional_signer_not_established"


def test_independence_removal_and_decoder_poison_are_detected(tmp_path: Path):
    api = _api()
    from polisyos.runtime.quality import constrained_response as runtime
    from tools import response_transition_oracle as oracle

    original = oracle.decode_packet
    try:
        oracle.decode_packet = runtime.decode_packet
        with pytest.raises(ValueError, match="oracle_independence") as refusal:
            api.evaluate_corpus(root=tmp_path)
        sys.stdout.write(json.dumps({"independence_removal": str(refusal.value)}) + "\n")
    finally:
        oracle.decode_packet = original
    raw = (api.CORPUS_ROOT / "packets.json").read_bytes()
    expected = oracle.decode_packet(raw)
    runtime_original = runtime.decode_packet
    try:
        runtime.decode_packet = lambda _: {"wrong": True}
        assert oracle.decode_packet(raw) == expected
        with pytest.raises((ValueError, AttributeError), match=r"packet|decode|model|scenario"):
            api.evaluate_corpus(root=tmp_path / "poison")
    finally:
        runtime.decode_packet = runtime_original


def test_every_guardrail_mutant_has_its_own_red_counter(replay_result):
    api, root, raw, observations, _ = replay_result
    for counter in api.GUARDRAIL_COUNTERS:
        report = api.grade_replay(root=root, raw=raw, observations=observations, mutant=counter)
        sys.stdout.write(
            json.dumps(
                {"mutant": counter, "counters": report.guardrail_counters, "issues": report.issues}
            )
            + "\n"
        )
        assert report.guardrail_counters[counter] > 0, counter
        assert report.issues, counter


def test_corrupt_oracle_is_refused_and_valid_seal_wrong_content_fails(tmp_path: Path):
    api = _api()
    result = api.oracle_corruption_probe(tmp_path)
    sys.stdout.write(json.dumps({"corrupt_oracle_refusals": result}) + "\n")
    assert result == ("oracle_seal_mismatch", "oracle_recompute_mismatch")


def test_each_proxy_divergence_removal_is_local(replay_result):
    import copy

    api, root, raw, observations, baseline = replay_result
    for pair in baseline.proxy_pairs:
        altered = copy.deepcopy(observations)
        members = [row for row in altered if row["scenario_id"] == pair["scenario_id"]]
        if pair["dimension"] == "duplicate":
            members[1]["duplicate"] = False
        else:
            members[1]["assessment"] = copy.deepcopy(members[0]["assessment"])
        report = api.grade_replay(root=root, raw=raw, observations=altered)
        sys.stdout.write(
            json.dumps({"proxy_removal": pair["scenario_id"], "issues": report.issues}) + "\n"
        )
        assert f"{pair['scenario_id']}:proxy_pair_not_discriminated" in report.issues
        assert all(issue.startswith(pair["scenario_id"] + ":") for issue in report.issues)


def test_valid_shape_decoder_wrongness_diverges_from_independent_oracle():
    api = _api()
    from polisyos.runtime.quality import constrained_response as runtime
    from tools import response_transition_oracle as oracle

    raw = (api.CORPUS_ROOT / "packets.json").read_bytes()
    independent = oracle.expectation(oracle.decode_packet(raw)["packets"][0]["events"][0])
    event = runtime.decode_packet(raw).packets[0].events[0]
    altered = event.model_copy(
        update={"observation": event.observation.model_copy(update={"maturity": "mature"})}
    )
    actual = runtime.assess_response(altered).model_dump(mode="json")
    assert "observation_not_mature" in independent["reasons"]
    assert "observation_not_mature" not in actual["reasons"]
    assert actual != independent


def test_operation_coverage_rejects_effect_removal_with_labels_intact():
    api = _api()
    from tools import response_transition_oracle as oracle

    corpus = oracle.decode_packet((api.CORPUS_ROOT / "packets.json").read_bytes())
    assert api.check_operation_coverage(corpus) == api.OPERATIONS
    for packet in corpus["packets"]:
        for event in packet["events"]:
            event["requested"] = dict(event["current"])
    with pytest.raises(ValueError, match="operation_semantics_missing"):
        api.check_operation_coverage(corpus)

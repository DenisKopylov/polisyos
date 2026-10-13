from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from tools.quality.validation import check_layer3_gy_promotion_contract as checker

POLICY_ENGINE_ROOT = Path(__file__).resolve().parents[3]


def test_n9_contract_input_preserves_actual_cg2_producer_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A current proof input must be the real binder output, including refusals."""
    emitted: list[checker.GroundingDecisionCertificate] = []
    original = checker.GroundingBindGate.certificate_for

    def capture_actual(*args: Any, **kwargs: Any) -> checker.GroundingDecisionCertificate:
        result = original(*args, **kwargs)
        emitted.append(result)
        return result

    monkeypatch.setattr(checker.GroundingBindGate, "certificate_for", capture_actual)
    reference, returned = checker._cg2_contract_bind()

    assert len(emitted) == 1
    assert returned.model_dump(mode="json") == emitted[0].model_dump(mode="json"), (
        "n9_contract_input_was_authored_after_real_binder_returned"
    )
    from polisyos.runtime.quality.promotion_sequence import _CredalReferenceReplayRecord

    replay_record = _CredalReferenceReplayRecord.from_reference(reference)
    replay_payload = replay_record.model_dump(mode="json")
    assert _CredalReferenceReplayRecord.model_validate(replay_payload).to_reference() == reference
    assert reference.essential_edges
    assert all(edge.provenance["synthetic"] is True for edge in reference.essential_edges.values())
    assert returned.synthetic is True
    assert returned.production_promotable is False


def _historical_credal_v1_contract_bytes() -> bytes:
    recorded = (
        Path(__file__).parent / "fixtures/layer3_gy_promotion_contract_credal_v1.json"
    ).read_bytes()
    assert hashlib.sha256(recorded).hexdigest() == (
        "4825fd7adac74ef35a351d023dbd0069952b602b26b1c124c7795ef696f1a59a"
    )
    return recorded


def _historical_credal_v2_contract_bytes() -> bytes:
    """Read the pre-D1 custody from git; do not duplicate a committed artifact."""
    return subprocess.run(
        ["git", "show", f"504f995cd:policy-engine/{checker.OUTPUT_PATH}"],
        cwd=POLICY_ENGINE_ROOT,
        check=True,
        capture_output=True,
    ).stdout


def _synthetic_v6_v1_credal_contract_bytes() -> bytes:
    """Build a controlled v6/P0 vector with its registered v1 reference profile.

    The test vector is derived from pinned v6 custody but is explicitly synthetic;
    it is not evidence that the immutable historical bytes ever held v1 references.
    """
    from polisyos.runtime.quality import promotion_sequence as history_module

    payload = json.loads(_historical_credal_v2_contract_bytes())
    assert all(
        entry["owner_rule"] == checker.CANONICAL_PROMOTION_VERIFICATION_COMPARISON_V6_HISTORY_RULE
        for entry in payload["comparison_admission_manifest"]
    )
    changed = 0
    for entry in payload["comparison_admission_manifest"]:
        key = entry["json_pointer"].removeprefix("/")
        receipt = payload[key]
        parsed = checker.parse_canonical_promotion_history_receipt(receipt)
        assert type(parsed) is history_module._LegacyCanonicalPromotionReceiptV6
        reference = receipt["owner_projection"]["credal_reference"]
        if reference is None:
            continue
        assert reference["schema_version"] == "policyos.runtime.grounding_credal_reference.v2"
        reference["schema_version"] = "policyos.runtime.grounding_credal_reference.v1"
        owner = receipt["owner_projection"]
        owner["projection_hash"] = checker.gy_content_hash(
            {name: value for name, value in owner.items() if name != "projection_hash"}
        )
        parsed = checker.parse_canonical_promotion_history_receipt(receipt)
        assert type(parsed) is history_module._LegacyCanonicalPromotionReceiptV6
        assert parsed.historical_projection() == receipt
        changed += 1
    assert changed > 0
    historical_plan = checker.build_gy_comparison_projection_plan_from_manifest(
        payload,
        manifest=payload["comparison_admission_manifest"],
        owner_rule_registry=checker.canonical_promotion_verification_comparison_owner_rule_registry(),
    )
    checker._set_comparison_identity(payload, historical_plan)
    payload["contract_content_hash"] = checker._contract_content_hash(payload)
    return json.dumps(payload, sort_keys=True).encode("utf-8")


def _rebind_synthetic_v6_contract(payload: dict[str, Any]) -> None:
    for entry in payload["comparison_admission_manifest"]:
        owner = payload[entry["json_pointer"].removeprefix("/")]["owner_projection"]
        owner["projection_hash"] = checker.gy_content_hash(
            {name: value for name, value in owner.items() if name != "projection_hash"}
        )
    historical_plan = checker.build_gy_comparison_projection_plan_from_manifest(
        payload,
        manifest=payload["comparison_admission_manifest"],
        owner_rule_registry=checker.canonical_promotion_verification_comparison_owner_rule_registry(),
    )
    checker._set_comparison_identity(payload, historical_plan)
    payload["contract_content_hash"] = checker._contract_content_hash(payload)


@pytest.fixture(scope="module")
def live_credal_epoch_comparison() -> tuple[dict[str, Any], checker.GyComparisonProjectionPlan]:
    """Keep one actual live owner replay for the bounded reconciliation negatives."""
    return checker._build_payload_with_comparison_plan(POLICY_ENGINE_ROOT)


def _projected_leaf_delta(before: Any, after: Any) -> dict[str, Any]:
    """Independently enumerate terminal identities, including empty containers."""
    missing = object()

    def recursive(item: Any, path: str = "") -> dict[str, Any]:
        if isinstance(item, dict) and item:
            return {
                identity: value
                for key, child in item.items()
                for identity, value in recursive(child, f"{path}/{key}").items()
            }
        if isinstance(item, list) and item:
            return {
                identity: value
                for index, child in enumerate(item)
                for identity, value in recursive(child, f"{path}/{index}").items()
            }
        return {path: item}

    def iterative(value: Any) -> dict[str, Any]:
        stack = [("", value)]
        result = {}
        while stack:
            path, item = stack.pop()
            if isinstance(item, dict) and item:
                stack.extend((f"{path}/{key}", child) for key, child in item.items())
            elif isinstance(item, list) and item:
                stack.extend((f"{path}/{index}", child) for index, child in enumerate(item))
            else:
                result[path] = item
        return result

    previous, current = recursive(before), recursive(after)
    independent_previous, independent_current = iterative(before), iterative(after)
    assert previous == independent_previous and current == independent_current
    identities = set(previous) | set(current)
    independent_ids = set(independent_previous) | set(independent_current)
    assert identities == independent_ids
    delta = [
        {
            "identity": path,
            "before_present": path in previous,
            "after_present": path in current,
            **({"before": previous[path]} if path in previous else {}),
            **({"after": current[path]} if path in current else {}),
        }
        for path in sorted(identities)
        if previous.get(path, missing) != current.get(path, missing)
    ]
    independent_changes = {
        path
        for path in independent_ids
        if independent_previous.get(path, missing) != independent_current.get(path, missing)
    }
    assert independent_changes == {row["identity"] for row in delta}
    return {
        "projected_leaf_denominator": len(identities),
        "independent_projected_leaf_denominator": len(independent_ids),
        "changed_leaf_count": len(delta),
        "independent_changed_leaf_count": len(independent_changes),
        "governed_v6_v7_projected_delta": delta,
    }


@pytest.mark.parametrize(
    ("before", "after"),
    [({}, None), ([], None), ({}, []), ({}, {"ref": None}), ({"ref": []}, {}), ({"ref": {}}, {})],
)
def test_n9_reissue_leaf_census_distinguishes_absent_null_and_empty(before, after):
    result = _projected_leaf_delta(before, after)
    assert result["changed_leaf_count"] > 0
    assert result["changed_leaf_count"] == result["independent_changed_leaf_count"]


def test_n9_reissue_translation_refuses_missing_defaulted_custody_field():
    frozen = json.loads(_historical_credal_v2_contract_bytes())
    receipt = frozen["contract_lane_anytime_refusal"]
    assert receipt["owner_projection"]["certificate_offers"] == []
    del receipt["owner_projection"]["certificate_offers"]
    with pytest.raises(ValueError, match="promotion_reissue_historical_receipt_incomplete"):
        checker._translate_n9_v6_receipt_epoch(receipt)


def test_n9_writer_reissues_the_governed_v6_source_scope_epoch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    live_credal_epoch_comparison: tuple[dict[str, Any], checker.GyComparisonProjectionPlan],
) -> None:
    """Reconcile actual historical and replayed owners without a broad epoch bypass."""
    from polisyos.runtime.quality.promotion_sequence import (
        parse_canonical_promotion_history_receipt,
    )

    frozen_path = POLICY_ENGINE_ROOT / checker.OUTPUT_PATH
    original_canonical = frozen_path.read_bytes()
    historical = _historical_credal_v2_contract_bytes()
    frozen = json.loads(historical)
    for admission in frozen["comparison_admission_manifest"]:
        receipt = frozen[admission["json_pointer"].removeprefix("/")]
        assert receipt["schema_version"] == "policyos.policy_design_case.layer3_gy.n9_promotion.v6"
        assert parse_canonical_promotion_history_receipt(receipt).historical_projection() == receipt
    live, plan = live_credal_epoch_comparison
    prior_plan = checker.build_gy_comparison_projection_plan_from_manifest(
        frozen,
        manifest=frozen["comparison_admission_manifest"],
        owner_rule_registry=checker.canonical_promotion_verification_comparison_owner_rule_registry(),
    )
    excluded = checker._CONTENT_HASH_EXCLUDED_TOP_LEVEL | checker._COMPARISON_IDENTITY_FIELDS
    previous = prior_plan.project(
        {key: value for key, value in frozen.items() if key not in excluded}
    )
    current = plan.project({key: value for key, value in live.items() if key not in excluded})
    delta = _projected_leaf_delta(previous, current)
    sys.__stdout__.write(json.dumps(delta, indent=2) + "\n")
    output = tmp_path / "controlled_n9_reissue.json"
    output.write_bytes(historical)
    monkeypatch.setattr(checker, "OUTPUT_PATH", str(output))
    monkeypatch.setattr(
        checker, "_build_payload_with_comparison_plan", lambda _: (copy.deepcopy(live), plan)
    )
    checker.write(POLICY_ENGINE_ROOT)
    written = json.loads(output.read_bytes())
    assert checker.validate_payload(written)["status"] == "pass"
    assert frozen_path.read_bytes() == original_canonical
    assert written["comparison_admission_manifest"] == plan.manifest


def test_n9_writer_composes_v6_manifest_with_v1_credal_reference_epoch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    live_credal_epoch_comparison: tuple[dict[str, Any], checker.GyComparisonProjectionPlan],
) -> None:
    """Exercise both registered transitions from a typed, controlled v6 source."""
    historical = _synthetic_v6_v1_credal_contract_bytes()
    frozen = json.loads(historical)
    old_profiles = {
        frozen[entry["json_pointer"].removeprefix("/")]["owner_projection"]["credal_reference"][
            "schema_version"
        ]
        for entry in frozen["comparison_admission_manifest"]
        if frozen[entry["json_pointer"].removeprefix("/")]["owner_projection"]["credal_reference"]
        is not None
    }
    assert old_profiles == {"policyos.runtime.grounding_credal_reference.v1"}
    seen: list[set[str]] = []
    original = checker._is_authorized_credal_input_epoch_reissue

    def observe(
        prior: dict[str, Any], current: dict[str, Any], plan: checker.GyComparisonProjectionPlan
    ) -> bool:
        profiles = {
            prior[item["json_pointer"].removeprefix("/")]["owner_projection"]["credal_reference"][
                "schema_version"
            ]
            for item in prior["comparison_admission_manifest"]
            if prior[item["json_pointer"].removeprefix("/")]["owner_projection"]["credal_reference"]
            is not None
        }
        if "policyos.runtime.grounding_credal_reference.v1" in profiles:
            seen.append(profiles)
        return original(prior, current, plan)

    monkeypatch.setattr(checker, "_is_authorized_credal_input_epoch_reissue", observe)
    output = tmp_path / "controlled_v6_v1_reissue.json"
    output.write_bytes(historical)
    monkeypatch.setattr(checker, "OUTPUT_PATH", str(output))
    live, plan = live_credal_epoch_comparison
    monkeypatch.setattr(
        checker, "_build_payload_with_comparison_plan", lambda _: (copy.deepcopy(live), plan)
    )
    checker.write(POLICY_ENGINE_ROOT)
    written = json.loads(output.read_bytes())
    assert seen == [{"policyos.runtime.grounding_credal_reference.v1"}]
    assert checker.validate_payload(written)["status"] == "pass"
    assert written["comparison_admission_manifest"] == plan.manifest
    assert (
        json.loads(historical)["comparison_admission_manifest"]
        == frozen["comparison_admission_manifest"]
    )


@pytest.mark.parametrize("mutation", ["reference_hash", "profile"])
def test_n9_v6_v1_credal_source_mutation_fails_after_hashes_are_rebound(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mutation: str,
    live_credal_epoch_comparison: tuple[dict[str, Any], checker.GyComparisonProjectionPlan],
) -> None:
    frozen = json.loads(_synthetic_v6_v1_credal_contract_bytes())
    selected = next(
        frozen[item["json_pointer"].removeprefix("/")]["owner_projection"]["credal_reference"]
        for item in frozen["comparison_admission_manifest"]
        if frozen[item["json_pointer"].removeprefix("/")]["owner_projection"]["credal_reference"]
        is not None
    )
    if mutation == "reference_hash":
        selected["reference_hash"] = "sha256:" + "0" * 64
    else:
        selected["schema_version"] = "policyos.runtime.grounding_credal_reference.v0"
    _rebind_synthetic_v6_contract(frozen)
    output = tmp_path / "mutated_v6_v1_source.json"
    output.write_text(json.dumps(frozen, sort_keys=True), encoding="utf-8")
    before = output.read_bytes()
    monkeypatch.setattr(checker, "OUTPUT_PATH", str(output))
    live, plan = live_credal_epoch_comparison
    with pytest.raises(ValueError, match="promotion_comparison_admission_manifest_drift"):
        checker._reconcile_frozen_contract(POLICY_ENGINE_ROOT, copy.deepcopy(live), plan)
    assert output.read_bytes() == before


@pytest.mark.parametrize(
    "mutation",
    ["wrong_reason", "reference_hash", "profile", "source_module", "strangle", "comparison_hash"],
)
def test_n9_v6_v1_source_scope_reissue_refuses_one_unregistered_live_delta(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mutation: str,
    live_credal_epoch_comparison: tuple[dict[str, Any], checker.GyComparisonProjectionPlan],
) -> None:
    historical = _synthetic_v6_v1_credal_contract_bytes()
    frozen = json.loads(historical)
    live, plan = live_credal_epoch_comparison
    candidate = copy.deepcopy(live)
    if mutation == "wrong_reason":
        candidate["contract_lane_anytime_refusal"]["cg2_resolution_reason"] = "unregistered_reason"
    elif mutation == "reference_hash":
        candidate["contract_lane_anytime_refusal"]["owner_projection"]["credal_reference"][
            "reference_hash"
        ] = "sha256:" + "0" * 64
    elif mutation == "profile":
        candidate["contract_lane_anytime_refusal"]["owner_projection"]["credal_reference"][
            "schema_version"
        ] = "policyos.runtime.grounding_credal_reference.v1"
    elif mutation == "source_module":
        candidate["source_modules"].append("src/polisyos/runtime/quality/unregistered.py")
    elif mutation == "strangle":
        candidate["proof_input_strangle"]["default_flipped"] = False
    else:
        frozen["comparison_content_hash"] = "sha256:" + "0" * 64
        frozen["contract_content_hash"] = checker._contract_content_hash(frozen)
    path = tmp_path / "frozen_n9_contract.json"
    path.write_bytes(json.dumps(frozen, sort_keys=True).encode("utf-8"))
    monkeypatch.setattr(checker, "OUTPUT_PATH", str(path))
    with pytest.raises(ValueError, match="promotion_comparison_admission_manifest_drift"):
        checker._reconcile_frozen_contract(POLICY_ENGINE_ROOT, candidate, plan)
    assert json.loads(path.read_bytes()) == frozen


def test_n9_v6_v1_reissue_requires_corr_property_when_markers_remain(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    live_credal_epoch_comparison: tuple[dict[str, Any], checker.GyComparisonProjectionPlan],
) -> None:
    historical = _synthetic_v6_v1_credal_contract_bytes()
    path = tmp_path / "frozen_n9_contract.json"
    path.write_bytes(historical)
    monkeypatch.setattr(checker, "OUTPUT_PATH", str(path))
    monkeypatch.setattr(checker, "_is_authorized_corr_input_epoch_reissue", lambda *_: False)
    live, plan = live_credal_epoch_comparison
    with pytest.raises(ValueError, match="promotion_comparison_admission_manifest_drift"):
        checker._reconcile_frozen_contract(POLICY_ENGINE_ROOT, copy.deepcopy(live), plan)
    assert path.read_bytes() == historical


def test_current_n9_proof_recomputes_its_entire_consumed_input(
    live_credal_epoch_comparison: tuple[dict[str, Any], checker.GyComparisonProjectionPlan],
) -> None:
    payload, _ = live_credal_epoch_comparison
    packet = payload["proof_input_strangle"]
    assert packet["packet_type"] == "StrangleReceipt"
    assert packet["default_flipped"] is True
    assert packet["synthetic"] is True
    assert packet["consumed_content_hash"] == packet["recomputed_content_hash"]
    changed = copy.deepcopy(payload)
    changed["proof_input_strangle"]["default_flipped"] = False
    assert {"code": "proof_input_strangle_drift"} in checker.validate_payload(changed)["issues"]


def test_n9_writer_reissues_only_the_governed_credal_input_epoch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    live_credal_epoch_comparison: tuple[dict[str, Any], checker.GyComparisonProjectionPlan],
) -> None:
    from polisyos.runtime.quality.promotion_sequence import (
        CANONICAL_PROMOTION_SEQUENCE_SCHEMA_VERSION,
    )

    historical = _historical_credal_v1_contract_bytes()
    previous = json.loads(historical)
    for admission in previous["comparison_admission_manifest"]:
        key = admission["json_pointer"].removeprefix("/")
        assert (
            checker.parse_canonical_promotion_history_receipt(previous[key]).historical_projection()
            == previous[key]
        )
    output = tmp_path / "current_n9_contract.json"
    output.write_bytes(historical)
    monkeypatch.setattr(checker, "OUTPUT_PATH", str(output))
    live, plan = live_credal_epoch_comparison
    monkeypatch.setattr(
        checker, "_build_payload_with_comparison_plan", lambda _: (copy.deepcopy(live), plan)
    )

    checker.write(POLICY_ENGINE_ROOT)

    current = json.loads(output.read_bytes())
    report = checker.validate_payload(current)
    assert report["status"] == "pass", report
    assert report["issues"] == []
    assert _historical_credal_v1_contract_bytes() == historical
    expected = {
        "contract_lane_anytime_refusal": "policyos.runtime.grounding_credal_reference.v2",
        "production_honest_shadow": None,
        "non_promotable_contract_stamp": "policyos.runtime.grounding_credal_reference.v2",
    }
    actual = {}
    for admission in current["comparison_admission_manifest"]:
        key = admission["json_pointer"].removeprefix("/")
        receipt = current[key]
        reference = receipt["owner_projection"]["credal_reference"]
        actual[key] = reference["schema_version"] if reference is not None else None
        assert receipt["consumer_promotable"] is False
        assert receipt["promoted"] is False
        assert receipt["schema_version"] == CANONICAL_PROMOTION_SEQUENCE_SCHEMA_VERSION
        assert receipt["schema_version"] == checker.CANONICAL_PROMOTION_SEQUENCE_SCHEMA_VERSION
        certificate = receipt["owner_projection"]["grounding_decision_certificate"]
        if certificate is not None:
            assert (
                certificate["schema_version"]
                == "policyos.runtime.grounding_decision_certificate.v2"
            )
            assert certificate["synthetic"] is True
    assert actual == expected
    assert current["schema_version"] == checker._CONTRACT_SCHEMA_VERSION


@pytest.mark.parametrize(
    "mutation",
    [
        "status",
        "evidence",
        "risk",
        "order",
        "certificate",
        "candidate",
        "credal",
        "empty_to_null",
        "empty_to_absent",
        "empty_kind",
    ],
)
def test_n9_source_scope_reissue_refuses_governing_drift(
    monkeypatch, tmp_path, mutation, live_credal_epoch_comparison
):
    frozen = json.loads(_historical_credal_v2_contract_bytes())
    receipt = frozen["contract_lane_anytime_refusal"]
    if mutation == "status":
        receipt["status"] = "blocked"
    elif mutation == "evidence":
        receipt["obligations"][0]["evidence_refs"].append("forged-evidence")
    elif mutation == "risk":
        receipt["risk_spend"]["budget_delta"] = 0.02
    elif mutation == "order":
        receipt["obligations"].reverse()
    elif mutation == "certificate":
        receipt["owner_projection"]["grounding_decision_certificate"]["decisive_reason"] = "forged"
    elif mutation == "candidate":
        receipt["owner_projection"]["candidate_summary"]["proxy_score"] = 0.21
    elif mutation == "credal":
        receipt["owner_projection"]["credal_reference"]["as_of"] = "2026-06-30"
    elif mutation == "empty_to_null":
        receipt["owner_projection"]["certificate_offers"] = None
    elif mutation == "empty_to_absent":
        del receipt["owner_projection"]["certificate_offers"]
    else:
        receipt["owner_projection"]["certificate_offers"] = {}
    projection = receipt["owner_projection"]
    projection["projection_hash"] = checker.gy_content_hash(
        {key: item for key, item in projection.items() if key != "projection_hash"}
    )
    # Outer hashes alone cannot admit altered governing content. For well-typed
    # variants also recompute comparison custody, so refusal measures semantics.
    try:
        plan = checker.build_gy_comparison_projection_plan_from_manifest(
            frozen,
            manifest=frozen["comparison_admission_manifest"],
            owner_rule_registry=checker.canonical_promotion_verification_comparison_owner_rule_registry(),
        )
        checker._set_comparison_identity(frozen, plan)
    except ValueError:
        pass
    frozen["contract_content_hash"] = checker._contract_content_hash(frozen)
    output = tmp_path / "governing_drift.json"
    before = json.dumps(frozen)
    output.write_text(before)
    monkeypatch.setattr(checker, "OUTPUT_PATH", str(output))
    with pytest.raises(ValueError, match="promotion_comparison_admission_manifest_drift"):
        checker._reconcile_frozen_contract(POLICY_ENGINE_ROOT, *live_credal_epoch_comparison)
    assert output.read_text() == before


@pytest.mark.parametrize(
    "mutation",
    [
        "wrong_epoch",
        "governing_value",
        "governing_receipt",
        "comparison_epoch",
        "fake_inner_hash",
        "fake_old_hash",
    ],
)
def test_n9_credal_epoch_reissue_refuses_other_frozen_drift(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mutation: str,
    live_credal_epoch_comparison: tuple[dict[str, Any], checker.GyComparisonProjectionPlan],
) -> None:
    frozen: dict[str, Any] = json.loads(_historical_credal_v1_contract_bytes())
    if mutation == "wrong_epoch":
        frozen["contract_lane_anytime_refusal"]["owner_projection"]["credal_reference"][
            "schema_version"
        ] = "policyos.runtime.grounding_credal_reference.v0"
    elif mutation == "governing_value":
        frozen["scope_insufficient_promotion_policy"]["production"] += " hidden weakening"
    elif mutation == "governing_receipt":
        frozen["contract_lane_anytime_refusal"]["cg2_resolution_reason"] = "hidden weakening"
    elif mutation == "comparison_epoch":
        frozen["comparison_rule_version"] = "policyos.gy.non_authority_verification.v0"
    elif mutation == "fake_inner_hash":
        frozen["comparison_content_hash"] = "sha256:" + "0" * 64
    else:
        frozen["contract_content_hash"] = "sha256:" + "0" * 64
    if mutation not in {"fake_old_hash", "fake_inner_hash", "comparison_epoch"}:
        owner_projection = frozen["contract_lane_anytime_refusal"]["owner_projection"]
        owner_projection["projection_hash"] = checker.gy_content_hash(
            {key: value for key, value in owner_projection.items() if key != "projection_hash"}
        )
        comparison_plan = checker.build_gy_comparison_projection_plan_from_manifest(
            frozen,
            manifest=frozen["comparison_admission_manifest"],
            owner_rule_registry=(
                checker.canonical_promotion_verification_comparison_owner_rule_registry()
            ),
        )
        checker._set_comparison_identity(frozen, comparison_plan)
    if mutation != "fake_old_hash":
        frozen["contract_content_hash"] = checker._contract_content_hash(frozen)
    output = tmp_path / "refused_n9_contract.json"
    before = json.dumps(frozen, indent=2, sort_keys=True) + "\n"
    output.write_text(before, encoding="utf-8")
    monkeypatch.setattr(checker, "OUTPUT_PATH", str(output))

    expected = (
        "promotion_legacy_contract_content_hash_drift"
        if mutation == "fake_old_hash"
        else "promotion_comparison_admission_manifest_drift"
    )
    with pytest.raises(ValueError, match=expected):
        checker._reconcile_frozen_contract(POLICY_ENGINE_ROOT, *live_credal_epoch_comparison)

    assert output.read_text(encoding="utf-8") == before


@pytest.mark.parametrize("shape", ["absent", "null", "empty", "duplicate", "novel", "scalar"])
def test_n9_credal_reissue_requires_the_complete_admitted_identity_set(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    shape: str,
    live_credal_epoch_comparison: tuple[dict[str, Any], checker.GyComparisonProjectionPlan],
) -> None:
    frozen = json.loads(_historical_credal_v1_contract_bytes())
    manifest = frozen["comparison_admission_manifest"]
    if shape == "absent":
        del frozen["comparison_admission_manifest"]
    elif shape == "null":
        frozen["comparison_admission_manifest"] = None
    elif shape == "empty":
        frozen["comparison_admission_manifest"] = []
    elif shape == "duplicate":
        manifest.append(copy.deepcopy(manifest[0]))
    elif shape == "novel":
        manifest[0]["json_pointer"] = "/unadmitted_sibling"
    else:
        frozen["comparison_admission_manifest"] = "unresolved"
    frozen["contract_content_hash"] = checker._contract_content_hash(frozen)
    output = tmp_path / "unadmitted_n9_contract.json"
    output.write_text(json.dumps(frozen), encoding="utf-8")
    monkeypatch.setattr(checker, "OUTPUT_PATH", str(output))

    with pytest.raises(ValueError, match=r"promotion_.*(?:drift|mismatch)"):
        checker._reconcile_frozen_contract(POLICY_ENGINE_ROOT, *live_credal_epoch_comparison)


def test_n9_credal_epoch_reissue_removal_restores_governing_refusal(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    live_credal_epoch_comparison: tuple[dict[str, Any], checker.GyComparisonProjectionPlan],
) -> None:
    output = tmp_path / "historical_n9_contract.json"
    historical = _historical_credal_v1_contract_bytes()
    output.write_bytes(historical)
    monkeypatch.setattr(checker, "OUTPUT_PATH", str(output))
    monkeypatch.setattr(checker, "_is_authorized_credal_input_epoch_reissue", lambda *_: False)
    live, plan = live_credal_epoch_comparison
    monkeypatch.setattr(
        checker, "_build_payload_with_comparison_plan", lambda _: (copy.deepcopy(live), plan)
    )
    monkeypatch.setattr(checker, "_is_authorized_corr_input_epoch_reissue", lambda *_: False)

    with pytest.raises(ValueError, match="promotion_comparison_admission_manifest_drift"):
        checker.write(POLICY_ENGINE_ROOT)

    assert output.read_bytes() == historical


def test_n9_new_input_epoch_reissue_removal_keeps_the_ordinary_owner_strict(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    live_credal_epoch_comparison: tuple[dict[str, Any], checker.GyComparisonProjectionPlan],
) -> None:
    historical = _historical_credal_v1_contract_bytes()
    output = tmp_path / "current_n9_contract.json"
    output.write_bytes(historical)
    monkeypatch.setattr(checker, "OUTPUT_PATH", str(output))
    frozen = json.loads(historical)
    live, plan = live_credal_epoch_comparison
    assert checker._is_authorized_credal_input_epoch_reissue(frozen, live, plan) is False
    monkeypatch.setattr(checker, "_is_authorized_corr_input_epoch_reissue", lambda *_: False)
    with pytest.raises(ValueError, match="promotion_legacy_comparison_semantic_mismatch"):
        checker._reconcile_frozen_contract(POLICY_ENGINE_ROOT, live, plan)
    assert output.read_bytes() == historical


def test_n9_reissue_predicate_accepts_only_complete_v3_to_v6_transition() -> None:
    receipt_keys = (
        "contract_lane_anytime_refusal",
        "production_honest_shadow",
        "non_promotable_contract_stamp",
    )

    def manifest(owner_rule: str) -> list[dict[str, str]]:
        return [
            {
                "action": "project",
                "json_pointer": f"/{key}",
                "owner_rule": owner_rule,
                "predicate_provenance": "recomputed",
            }
            for key in receipt_keys
        ]

    frozen_manifest = manifest(checker.CANONICAL_PROMOTION_VERIFICATION_COMPARISON_HISTORY_RULE)
    live_manifest = manifest(checker.CANONICAL_PROMOTION_VERIFICATION_COMPARISON_V6_HISTORY_RULE)
    comparison_identity = {
        "comparison_projection_schema_version": checker.GY_COMPARISON_PROJECTION_SCHEMA_VERSION,
        "comparison_rule_version": checker.GY_VERIFICATION_COMPARISON_RULE_VERSION,
    }
    frozen = {
        **comparison_identity,
        "comparison_admission_manifest": frozen_manifest,
        **{
            key: {"schema_version": checker.GY_PROMOTION_SEQUENCE_SCHEMA_VERSION}
            for key in receipt_keys
        },
    }
    live = {
        **comparison_identity,
        "comparison_admission_manifest": live_manifest,
        **{
            key: {"schema_version": "policyos.policy_design_case.layer3_gy.n9_promotion.v6"}
            for key in receipt_keys
        },
    }
    assert checker._is_authorized_v3_to_v6_comparison_reissue(frozen, live, live_manifest)

    mixed_epoch = copy.deepcopy(frozen)
    mixed_epoch[receipt_keys[-1]]["schema_version"] = (
        "policyos.policy_design_case.layer3_gy.n9_promotion.v5"
    )
    assert not checker._is_authorized_v3_to_v6_comparison_reissue(
        mixed_epoch,
        live,
        live_manifest,
    )

    sibling_path = copy.deepcopy(frozen)
    sibling_path["comparison_admission_manifest"][0]["json_pointer"] = "/unowned_receipt"
    assert not checker._is_authorized_v3_to_v6_comparison_reissue(
        sibling_path,
        live,
        live_manifest,
    )


def test_rederived_n9_contract_accounts_fixed_time_refusal_through_n11() -> None:
    payload = checker.build_payload(POLICY_ENGINE_ROOT)

    receipt = payload["contract_lane_anytime_refusal"]
    projection = receipt["confidence_ledger_projection"]
    calibration = next(
        item for item in receipt["obligations"] if item["obligation_class"] == "calibration"
    )

    assert receipt["promoted"] is False
    assert receipt["authority_derivation_trace"] is None
    assert receipt["risk_spend"]["total_declared_delta"] == 0.0
    assert receipt["risk_spend"]["within_budget"] is True
    assert projection["projection_scope"] == "n9_promotion_certificate"
    assert projection["total_spend"] == {"denominator": 1, "numerator": 0}
    assert projection["maintained_assumptions"] == [
        "obligation_completeness",
        "validator_soundness",
    ]
    rows = {row["obligation_class"]: row for row in projection["promotion_rows"]}
    assert tuple(rows) == ("calibration", "data")
    assert rows["calibration"]["instrument_id"] == "fixed_time_confidence_interval"
    assert rows["data"]["instrument_id"] == "owner_verified_e_process"
    assert all(row["outcome"] == "preflight_refusal" for row in rows.values())
    assert all(row["anytime_valid"] is False for row in rows.values())
    assert all(row["eligible_for_promotion"] is False for row in rows.values())
    assert all(row["spend"] == {"denominator": 1, "numerator": 0} for row in rows.values())
    assert calibration["risk_spend"]["n11_confidence_ledger_ref"] == rows["calibration"]["check_id"]
    assert checker.validate_payload(payload) == {"status": "pass", "issues": []}


def test_n9_contract_persists_live_om01_authority_witness() -> None:
    payload = checker.build_payload(POLICY_ENGINE_ROOT)

    witness = payload["obligation_instance_mutation_witness"]

    assert witness["mutation_id"] == "om_01_decisive_obligation_omission"
    assert witness["removed_obligation_role"] == "decisive_predicate"
    assert witness["removed_source_obligation_ref"].endswith(
        "#transport_wmr_hash_equals_receipt_wmr_hash"
    )
    assert witness["removed_instance_count"] == 1
    assert witness["class_denominator_status"] == "green"
    assert witness["class_denominator_count"] == 15
    assert witness["authority_status"] == "red"
    assert witness["authority_issue_codes"] == ["decisive_obligation_omitted"]
    assert witness["verification_session_provenance"] == "verification"


def test_n9_contract_writer_is_byte_stable_without_canonical_ledger_namespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actual_owner = checker.ConfidenceLedgerSession
    verification_calls: list[object] = []

    class ObservedCheckerIntake:
        # Observe the checker seam without changing the runtime-attested owner.
        @staticmethod
        def _for_verification(*args: Any, **kwargs: Any) -> Any:
            result = actual_owner._for_verification(*args, **kwargs)
            verification_calls.append(result)
            return result

        @staticmethod
        def from_repo(*args: object, **kwargs: object) -> None:
            del args, kwargs
            raise AssertionError("N9 checker touched the checkout confidence ledger")

    monkeypatch.setattr(checker, "ConfidenceLedgerSession", ObservedCheckerIntake)

    first = checker.build_contract_json_for_write(POLICY_ENGINE_ROOT)
    second = checker.build_contract_json_for_write(POLICY_ENGINE_ROOT)

    assert verification_calls
    assert first == second
    assert "capture_wall_time_seconds" not in first
    payload = json.loads(first)
    receipt = payload["contract_lane_anytime_refusal"]
    assert receipt["confidence_ledger_projection"]["authority_provenance"] == ("verification")
    assert receipt["consumer_promotable"] is False
    assert receipt["non_promotable_reason"] == "verification_only_replay"


def test_n9_contract_rejects_deleted_projection_conditionality() -> None:
    payload = checker.build_payload(POLICY_ENGINE_ROOT)
    corrupted = copy.deepcopy(payload)
    del corrupted["contract_lane_anytime_refusal"]["confidence_ledger_projection"][
        "conditionality_clause"
    ]
    corrupted["contract_content_hash"] = checker._contract_content_hash(corrupted)

    report = checker.validate_payload(corrupted)

    assert report["status"] == "fail"
    assert "contract_lane_anytime_refusal_invalid" in {item["code"] for item in report["issues"]}


def test_n9_contract_separates_full_record_from_verified_comparison_identity() -> None:
    payload, plan = checker._build_payload_with_comparison_plan(POLICY_ENGINE_ROOT)
    projection = payload["contract_lane_anytime_refusal"]["confidence_ledger_projection"]
    shifted = copy.deepcopy(payload)
    shifted_projection = shifted["contract_lane_anytime_refusal"]["confidence_ledger_projection"]
    shifted_projection["deployment_identity"] = "policy-engine-deployment:sha256:" + "f" * 64
    shifted_projection["projection_hash"] = checker.gy_content_hash(
        {key: value for key, value in shifted_projection.items() if key != "projection_hash"}
    )
    checker._set_comparison_identity(shifted, plan)
    shifted["contract_content_hash"] = checker._contract_content_hash(shifted)

    assert projection == payload["contract_lane_anytime_refusal"]["confidence_ledger_projection"]
    assert checker._comparison_content_hash(payload, plan) == checker._comparison_content_hash(
        shifted, plan
    )
    assert checker._contract_content_hash(payload) != checker._contract_content_hash(shifted)
    assert checker.validate_payload(payload)["status"] == "pass"
    assert checker.validate_payload(shifted)["status"] == "pass"

    stale = copy.deepcopy(shifted)
    stale["contract_content_hash"] = payload["contract_content_hash"]
    report = checker.validate_payload(stale)
    assert report["status"] == "fail"
    assert "contract_content_hash_drift" in {item["code"] for item in report["issues"]}

    governing = copy.deepcopy(payload)
    governing["scope_insufficient_promotion_policy"]["production"] += " changed"
    assert checker._comparison_content_hash(payload, plan) != checker._comparison_content_hash(
        governing, plan
    )
    checker._set_comparison_identity(governing, plan)
    governing["contract_content_hash"] = checker._contract_content_hash(governing)
    governing_report = checker.validate_payload(governing)
    assert governing_report["status"] == "fail"
    assert "scope_insufficient_promotion_policy_drift" in {
        item["code"] for item in governing_report["issues"]
    }


def test_n9_source_flip_harness_targets_current_n11_guards_and_tests() -> None:
    cases = checker._source_flip_cases()

    assert "source_flip_non_anytime_preflight_guard" in {item.mutation_id for item in cases}
    assert "source_flip_confidence_projection_recompute_guard" in {
        item.mutation_id for item in cases
    }
    assert "source_flip_ledger_bypass_guard" in {item.mutation_id for item in cases}
    for case in cases:
        for replacement in case.replacements:
            source = (POLICY_ENGINE_ROOT / replacement.relative_path).read_text(encoding="utf-8")
            assert replacement.old in source, case.mutation_id
        for node_id in case.probe_command:
            if "::" not in node_id:
                continue
            relative_path, test_name = node_id.split("::", 1)
            test_source = (POLICY_ENGINE_ROOT / relative_path).read_text(encoding="utf-8")
            assert f"def {test_name}(" in test_source, case.mutation_id


def test_n9_credal_edge_replay_round_trips_nested_captured_provenance() -> None:
    """Nested frozen provenance survives the actual JSON replay DTO boundary."""
    from polisyos.runtime.quality.credal_reference import (
        AdmissibleCompletion,
        CredalReferenceEdge,
    )
    from polisyos.runtime.quality.promotion_sequence import _CredalEdgeReplayRecord

    class StatefulFallback:
        def __init__(self) -> None:
            self.calls = 0

        def __str__(self) -> str:
            self.calls += 1
            return f"fallback-{self.calls}"

    fallback = StatefulFallback()
    source_items = ["selected"]
    nested_source = {
        "items": source_items,
        "route": ("selected-route", {"scope": ["candidate"]}),
        "opaque": fallback,
    }
    provenance = {"owner": "controlled-test", "nested": nested_source}
    edge = CredalReferenceEdge(
        modality="L2_CAUSAL_EDGE",
        edge_id="nested-provenance-replay",
        status="incomplete",
        admissible_completions=(
            AdmissibleCompletion(
                completion_kind="partial",
                value={"candidate": {"values": [1, 2]}},
                reason="source basis remains incomplete",
            ),
        ),
        provenance=provenance,
    ).with_content_hash()
    expected_payload = edge.to_payload()

    assert expected_payload["provenance"]["nested"]["items"] == ["selected"]
    assert expected_payload["provenance"]["nested"]["route"] == [
        "selected-route",
        {"scope": ["candidate"]},
    ]
    assert expected_payload["provenance"]["nested"]["opaque"] == "fallback-1"
    assert fallback.calls == 1

    source_items.append("caller-change")
    nested_source["late"] = "caller-change"
    provenance["late"] = "caller-change"
    assert edge.to_payload() == expected_payload
    assert fallback.calls == 1

    captured_items = edge.provenance["nested"]["items"]
    assert captured_items == ["selected"]
    with pytest.raises(TypeError):
        list.append(captured_items, "base-list-mutation")
    assert edge.to_payload() == expected_payload

    record = _CredalEdgeReplayRecord.from_edge(edge)
    serialized_record = record.model_dump_json()
    assert json.loads(serialized_record) == expected_payload
    fresh_record = _CredalEdgeReplayRecord.model_validate_json(serialized_record)
    replayed_edge = fresh_record.to_edge()
    assert replayed_edge.to_payload() == expected_payload
    assert replayed_edge.content_hash == edge.content_hash
    assert fallback.calls == 1

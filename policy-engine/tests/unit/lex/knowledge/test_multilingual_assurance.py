"""MAEP candidate mechanism negatives, with no signed equivalence claim."""

from __future__ import annotations

import importlib
import importlib.util
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

CORPUS = Path(__file__).parents[3] / "fixtures/lex/multilingual_assurance.json"


def owner():
    name = "polisyos.lex.knowledge.multilingual_assurance"
    assert importlib.util.find_spec(name), "W5-K06 requires the absent bounded MAEP consumer"
    return importlib.import_module(name)


def packet(index=0):
    return json.loads(CORPUS.read_text())["cases"][index]


def test_w5_k06_certificate_cannot_be_read_outside_declared_denominator(tmp_path):
    module = owner()
    from polisyos.core.artifacts.store import FileSystemCAS

    cas = FileSystemCAS(tmp_path / "cas")
    receipt = module.run_assurance(packet(), cas=cas)
    for dimension, value in [
        ("proposition_id", "unseen"),
        ("purpose", "payment"),
        ("context_id", "unseen"),
        ("qualified_holder", "system"),
    ]:
        request = {
            "proposition_id": packet()["proposition_id"],
            "purpose": "planning",
            "context_id": "inside_interval",
            "qualified_holder": None,
        }
        request[dimension] = value
        with pytest.raises(ValueError, match="outside_declared"):
            module.read_assurance_result(cas, receipt.artifact_ref, **request)
    result = module.read_assurance_result(
        cas,
        receipt.artifact_ref,
        proposition_id=packet()["proposition_id"],
        purpose="planning",
        context_id="inside_interval",
        qualified_holder=None,
    )
    assert result.equivalence_established is False
    assert result.signer is None
    assert result.signature_status == "missing_signature"
    assert result.required_role == "multilingual_authority_adjudicator"
    assert not cas.has_signature(receipt.artifact_ref)


@pytest.mark.parametrize(
    ("index", "reason"),
    [(0, "status_profile_changed"), (1, "action_profile_changed"), (2, "status_profile_changed")],
)
def test_three_ratified_semantic_promotions_fail_and_adjacent_control_compares(index, reason):
    module = owner()
    raw = packet(index)
    assert module.compare_candidate(raw).comparison == "candidate_match"
    raw["target"] = raw["defective_target"]
    result = module.compare_candidate(raw)
    assert result.comparison == "refused"
    assert reason in result.reasons
    assert result.equivalence_established is False


def test_matching_structure_and_frames_never_launder_changed_modality():
    module = owner()
    raw = packet(1)
    raw["target"]["text"] = raw["defective_target"]["text"]
    result = module.compare_candidate(raw)
    assert result.comparison == "refused"
    assert "rendition_content_unbound" in result.reasons
    assert not result.equivalence_established


def test_empty_population_unknown_or_duplicate_context_refuses():
    module = owner()
    for contexts in [[], ["outside_unmodeled"], ["inside_interval", "inside_interval"]]:
        raw = packet()
        raw["contexts"] = contexts
        with pytest.raises(ValueError):
            module.compare_candidate(raw)


def test_source_tamper_expiry_revocation_and_recomputed_result(tmp_path):
    module = owner()
    from polisyos.core.artifacts.store import FileSystemCAS

    cas = FileSystemCAS(tmp_path / "cas")
    receipt = module.run_assurance(packet(), cas=cas)
    request = {
        "proposition_id": packet()["proposition_id"],
        "purpose": "planning",
        "context_id": "inside_interval",
        "qualified_holder": None,
    }
    payload = json.loads(cas.get_bytes(receipt.artifact_ref))
    payload["result"]["comparison"] = "refused"
    with pytest.raises(ValueError, match="recompute"):
        module.recompute_assurance_payload(payload)
    with pytest.raises(ValueError, match="expired"):
        module.read_assurance_result(
            cas, receipt.artifact_ref, **request, now=datetime.now(UTC) + timedelta(days=3650)
        )
    module.revoke_assurance(cas, receipt.artifact_ref, reason="source_changed")
    reopened = FileSystemCAS(tmp_path / "cas")
    with pytest.raises(ValueError, match="revoked"):
        module.read_assurance_result(reopened, receipt.artifact_ref, **request)
    assert (
        module.replay_assurance_result(reopened, receipt.artifact_ref).comparison
        == "candidate_match"
    )


def test_rtl_pack_has_typed_empty_ten_slots_and_never_admits_jurisdiction():
    pack = owner().rtl_source_pack()
    assert pack.jurisdiction == "IL-Hebr"
    assert len(pack.evidence_requirements) == 10
    assert set(pack.evidence_requirements.values()) == {None}
    assert pack.ui_locale_admitted is False
    assert pack.source_authority_established is False
    assert pack.withheld_propositions == ("WP-11", "WP-12")


def test_rtl_source_content_is_persisted_and_exact_scope_consumed(tmp_path):
    module = owner()
    from polisyos.core.artifacts.store import FileSystemCAS

    cas = FileSystemCAS(tmp_path / "cas")
    content = {
        "jurisdiction": "IL-Hebr",
        "language": "he",
        "script": "Hebr",
        "source_text": "טקסט מועמד בלבד \u2066claim-17\u2069: אין סמכות משפטית.",
    }
    assert hasattr(module, "run_source_content"), "RTL source-content producer is absent"
    receipt = module.run_source_content(content, cas=cas)
    result = module.read_source_content(
        cas, receipt.artifact_ref, jurisdiction="IL-Hebr", language="he", script="Hebr"
    )
    assert result["source_text"] == content["source_text"]
    assert result["source_authority_established"] is False
    assert result["ui_locale_admitted"] is False
    assert result["withheld_propositions"] == ["WP-11", "WP-12"]
    assert set(result["evidence_requirements"].values()) == {None}
    for key, value in [("jurisdiction", "UA"), ("language", "en"), ("script", "Latn")]:
        scope = {"jurisdiction": "IL-Hebr", "language": "he", "script": "Hebr", key: value}
        with pytest.raises(ValueError, match="scope"):
            module.read_source_content(cas, receipt.artifact_ref, **scope)
    for key in content:
        missing = {k: v for k, v in content.items() if k != key}
        with pytest.raises(ValueError):
            module.run_source_content(missing, cas=cas)
    raw = json.loads(cas.get_bytes(receipt.artifact_ref))
    raw["content"]["source_text"] += "changed"
    with pytest.raises(ValueError, match="content"):
        module.recompute_source_content(raw)


def test_positive_frame_comparison_exposes_unestablished_protocol_checks():
    result = owner().compare_candidate(packet()).projection()
    assert "check_standing" in result, "Full MAEP check plane is absent from the candidate output"
    for check in [
        "natural_language_frame_correspondence",
        "glossary_release",
        "institutional_adjudication",
        "source_legal_authority",
        "plain_language_adaptation",
        "bidi_and_accessibility",
    ]:
        assert result["check_standing"][check] == "not_established"

"""Exercise source-relative legal recognition through persisted owner artifacts."""

from datetime import date

import pytest

from polisyos.core import artifacts, canon


def _source(store, role, entries, *, producer=None, inputs=None):
    from polisyos.foundry.validation import legal_correspondence as owner

    source = owner.LegalSubjectMembershipSource(
        synthetic=True, source_role=role, producer_ref=producer or f"synthetic.{role}.annotation",
        memberships=[{
            "entity_ref": ref, "entity_content_hash": "sha256:" + digest * 64,
            "subject": {"namespace": "synthetic.subjects", "namespace_version": "1",
                        "subject_id": subject, "valid_from": "1990-01-01",
                        "valid_until": "2030-01-01"},
        } for ref, digest, subject in entries],
    )
    return owner.persist_legal_subject_membership_source(store, source, inputs=inputs)


def _spine(store):
    from polisyos.foundry.validation import legal_correspondence as owner

    # These independent input tables are frozen before any candidate proposal.
    levers = _source(store, "lever", [("lever:a", "a", "alpha"), ("lever:b", "b", "beta")])
    norms = _source(store, "norm", [("norm:a", "c", "alpha"), ("norm:b", "d", "beta")])
    return owner.produce_legal_subject_spine(store, lever_source_ref=levers, norm_source_ref=norms)


def _request(**changes):
    from polisyos.foundry.validation import legal_correspondence as owner

    return owner.LegalCorrespondenceRequest(**{
        "lever_ref": "lever:a", "lever_content_hash": "sha256:" + "a" * 64,
        "norm_ref": "norm:a", "norm_content_hash": "sha256:" + "c" * 64,
        "as_of": date(2000, 1, 1), "proposal_producer_ref": "synthetic.mapping.candidate",
        "proposal_content_hash": "sha256:" + "e" * 64, **changes,
    })


def test_persisted_source_distinguishes_correspondence_and_transposition(tmp_path):
    """Removing subject equality admits the wrong norm despite unchanged markers."""
    from polisyos.foundry.validation import legal_correspondence as owner

    store = artifacts.FileSystemCAS(tmp_path)
    spine = _spine(store)
    matched = owner.recognize_legal_correspondence(store, spine, _request())
    wrong = owner.recognize_legal_correspondence(store, spine, _request(
        norm_ref="norm:b", norm_content_hash="sha256:" + "d" * 64))
    assert matched.status == "passed"
    assert wrong.status == "rejected"
    assert wrong.reason_code == "legal_subject_mismatch"
    assert matched.synthetic is True
    assert matched.current_authority_status == "blocked"
    result_ref = owner.persist_legal_correspondence_result(store, matched)
    persisted = owner.LegalCorrespondenceResult.model_validate(
        canon.from_canonical_bytes(store.get_bytes(result_ref.artifact_id)))
    assert persisted == matched


@pytest.mark.parametrize("changes,reason", [
    ({"lever_ref": "lever:novel"}, "legal_subject_missing"),
    ({"lever_content_hash": "sha256:" + "f" * 64}, "legal_subject_entity_content_mismatch"),
    ({"as_of": date(2031, 1, 1)}, "legal_subject_scope_unresolved"),
    ({"proposal_producer_ref": "synthetic.lever.annotation"}, "legal_subject_source_circular"),
])
def test_source_bindings_and_time_are_decisive(tmp_path, changes, reason):
    from polisyos.foundry.validation import legal_correspondence as owner

    store = artifacts.FileSystemCAS(tmp_path)
    result = owner.recognize_legal_correspondence(store, _spine(store), _request(**changes))
    assert result.status != "passed"
    assert result.reason_code == reason


def test_fake_or_corrupt_source_cannot_look_like_absence(tmp_path):
    from polisyos.foundry.validation import legal_correspondence as owner

    store = artifacts.FileSystemCAS(tmp_path)
    absent = owner.recognize_legal_correspondence(store, None, _request())
    assert absent.status == "ambiguous"
    assert absent.reason_code == "legal_subject_source_missing"
    spine = _spine(store)
    blob, _ = store.get_paths(spine.artifact_id)
    blob.write_bytes(b"{}")
    result = owner.recognize_legal_correspondence(store, spine, _request())
    assert result.status == "ambiguous"
    assert result.reason_code == "legal_subject_source_invalid"


def test_common_source_ancestry_is_circular_even_with_different_producer_labels(tmp_path):
    from polisyos.foundry.validation import legal_correspondence as owner

    store = artifacts.FileSystemCAS(tmp_path)
    shared = store.put_json({"synthetic": True}, artifacts.PutOptions(
        kind="synthetic.shared_annotation", media_type="application/json"))
    inputs = [artifacts.InputRef(artifact_id=shared.artifact_id, role="annotation_input")]
    levers = _source(store, "lever", [("lever:a", "a", "alpha")], inputs=inputs)
    norms = _source(store, "norm", [("norm:a", "c", "alpha")], inputs=inputs)
    with pytest.raises(ValueError, match="legal_subject_source_circular"):
        owner.produce_legal_subject_spine(store, lever_source_ref=levers, norm_source_ref=norms)


def test_distinct_ancestor_artifacts_from_one_subject_producer_are_circular(tmp_path):
    from polisyos.foundry.validation import legal_correspondence as owner

    store = artifacts.FileSystemCAS(tmp_path)
    refs = {}
    for role, entity, digest in (("lever", "lever:a", "a"), ("norm", "norm:a", "c")):
        ancestor = store.put_json({"synthetic": True, "role": role}, artifacts.PutOptions(
            kind="synthetic.annotation", media_type="application/json",
            producer=artifacts.ProducerInfo(
                component="synthetic.same_subject_producer", version="1")))
        refs[role] = _source(store, role, [(entity, digest, "alpha")], inputs=[
            artifacts.InputRef(artifact_id=ancestor.artifact_id, role="source_annotation")])
    with pytest.raises(ValueError, match="legal_subject_source_circular"):
        owner.produce_legal_subject_spine(
            store, lever_source_ref=refs["lever"], norm_source_ref=refs["norm"])


def test_subject_vocabulary_grows_without_code_and_does_not_default_unknown(tmp_path):
    from polisyos.foundry.validation import legal_correspondence as owner

    store = artifacts.FileSystemCAS(tmp_path)
    levers = _source(store, "lever", [("lever:future", "a", "new_subject")])
    norms = _source(store, "norm", [("norm:future", "c", "new_subject"),
                                    ("norm:other", "d", "other_new_subject")])
    spine = owner.produce_legal_subject_spine(store, lever_source_ref=levers, norm_source_ref=norms)
    request = _request(lever_ref="lever:future", norm_ref="norm:future")
    assert owner.recognize_legal_correspondence(store, spine, request).status == "passed"
    assert owner.recognize_legal_correspondence(store, spine, _request(
        lever_ref="lever:future", norm_ref="norm:other",
        norm_content_hash="sha256:" + "d" * 64)).status == "rejected"


def test_frozen_annotations_bind_live_entity_content_without_a_mapping_input(tmp_path):
    from polisyos.foundry.validation import legal_correspondence as owner

    store = artifacts.FileSystemCAS(tmp_path)
    refs = {}
    for role, entity, digest in (("lever", "lever:a", "a"), ("norm", "norm:a", "c")):
        declaration = owner.LegalSubjectAnnotationSource(
            synthetic=True, declared_at="2026-09-08", source_role=role,
            producer_ref=f"synthetic.{role}.annotation",
            annotations=[{"entity_ref": entity, "subject": {
                "namespace": "synthetic.subjects", "namespace_version": "1",
                "subject_id": "alpha", "valid_from": "1990-01-01"}}],
        )
        declared_ref = owner.persist_legal_subject_annotations(store, declaration)
        refs[role] = owner.bind_legal_subject_annotations(
            store, declared_ref, {entity: "sha256:" + digest * 64})
    spine = owner.produce_legal_subject_spine(
        store, lever_source_ref=refs["lever"], norm_source_ref=refs["norm"])
    assert owner.recognize_legal_correspondence(store, spine, _request()).status == "passed"


def test_source_marker_or_unresolved_authority_ref_cannot_grant_governed_authority(tmp_path):
    from polisyos.foundry.validation import legal_correspondence as owner

    store = artifacts.FileSystemCAS(tmp_path)
    refs = {}
    for role, entity, digest in (("lever", "lever:a", "a"), ("norm", "norm:a", "c")):
        ref = _source(store, role, [(entity, digest, "alpha")])
        payload = canon.from_canonical_bytes(store.get_bytes(ref.artifact_id))
        payload["synthetic"] = False
        payload["source_authority_ref"] = {
            "artifact_id": "sha256:" + "0" * 64,
            "kind": "unresolved.authority", "media_type": "application/json"}
        refs[role] = owner.persist_legal_subject_membership_source(
            store, owner.LegalSubjectMembershipSource.model_validate(payload))
    spine = owner.produce_legal_subject_spine(
        store, lever_source_ref=refs["lever"], norm_source_ref=refs["norm"])
    result = owner.recognize_legal_correspondence(store, spine, _request())
    assert result.status == "passed"  # The declared source-relative equality is unchanged.
    assert result.synthetic is False
    assert result.legal_authority_predicate_provenance == "not_established"
    assert result.current_authority_status == "blocked"


def test_mutated_candidate_result_cannot_persist_an_authority_grant(tmp_path):
    from polisyos.foundry.validation import legal_correspondence as owner

    store = artifacts.FileSystemCAS(tmp_path)
    result = owner.recognize_legal_correspondence(store, _spine(store), _request())
    assert result.status == "passed"
    altered = result.model_copy(update={"current_authority_status": "admissible"})
    with pytest.raises(ValueError):
        owner.persist_legal_correspondence_result(store, altered)


def test_persisted_comparison_must_be_recomputed_from_the_actual_source(tmp_path):
    from polisyos.foundry.validation import legal_correspondence as owner

    store = artifacts.FileSystemCAS(tmp_path)
    spine = _spine(store)
    wrong = owner.recognize_legal_correspondence(store, spine, _request(
        norm_ref="norm:b", norm_content_hash="sha256:" + "d" * 64))
    assert wrong.status == "rejected"
    forged = wrong.model_copy(update={"status": "passed",
                                     "reason_code": "legal_subject_correspondence_recognized"})
    with pytest.raises(ValueError, match="legal_subject_result_recomputation_mismatch"):
        owner.persist_legal_correspondence_result(store, forged)
    genuine = owner.recognize_legal_correspondence(store, spine, _request())
    assert owner.persist_legal_correspondence_result(store, genuine).artifact_id


@pytest.mark.parametrize("source", [None, {}, {"artifact_id": "fake"}])
def test_refusal_persistence_replays_the_submitted_source_without_reason_inference(tmp_path, source):
    from polisyos.foundry.validation import legal_correspondence as owner

    store = artifacts.FileSystemCAS(tmp_path)
    result = owner.recognize_legal_correspondence(store, source, _request())
    assert result.status == "ambiguous"
    assert result.submitted_source == source
    ref = owner.persist_legal_correspondence_result(store, result)
    assert owner.LegalCorrespondenceResult.model_validate(
        canon.from_canonical_bytes(store.get_bytes(ref.artifact_id))) == result


@pytest.mark.parametrize("change", ["namespace", "namespace_version", "duplicate"])
def test_subject_scope_and_unique_membership_are_decisive(tmp_path, change):
    from polisyos.foundry.validation import legal_correspondence as owner

    store = artifacts.FileSystemCAS(tmp_path)
    lever = _source(store, "lever", [("lever:a", "a", "alpha")])
    norm = _source(store, "norm", [("norm:a", "c", "alpha")])
    payload = canon.from_canonical_bytes(store.get_bytes(norm.artifact_id))
    if change == "duplicate":
        payload["memberships"].append(payload["memberships"][0])
    else:
        payload["memberships"][0]["subject"][change] = "novel_scope"
    norm = owner.persist_legal_subject_membership_source(
        store, owner.LegalSubjectMembershipSource.model_validate(payload))
    spine = owner.produce_legal_subject_spine(store, lever_source_ref=lever, norm_source_ref=norm)
    result = owner.recognize_legal_correspondence(store, spine, _request())
    assert result.status == ("ambiguous" if change == "duplicate" else "rejected")


def test_false_child_marker_cannot_erase_synthetic_source_ancestry(tmp_path):
    from polisyos.foundry.validation import legal_correspondence as owner

    store = artifacts.FileSystemCAS(tmp_path)
    lever = _source(store, "lever", [("lever:a", "a", "alpha")])
    norm = _source(store, "norm", [("norm:a", "c", "alpha")])
    payload = canon.from_canonical_bytes(store.get_bytes(lever.artifact_id))
    payload["synthetic"] = False
    changed = owner.persist_legal_subject_membership_source(
        store, owner.LegalSubjectMembershipSource.model_validate(payload),
        inputs=[artifacts.InputRef(artifact_id=lever.artifact_id, role="source_annotation")])
    with pytest.raises(ValueError, match="legal_subject_synthetic_lineage_mismatch"):
        owner.produce_legal_subject_spine(store, lever_source_ref=changed, norm_source_ref=norm)


@pytest.mark.parametrize("nested_marker,reason", [
    (True, "legal_subject_synthetic_lineage_mismatch"),
    ("false", "legal_subject_synthetic_marker_invalid"),
])
def test_nested_source_markers_are_decisive_across_json_ancestry(tmp_path, nested_marker, reason):
    from polisyos.foundry.validation import legal_correspondence as owner

    store = artifacts.FileSystemCAS(tmp_path)
    ancestor = store.put_json({"rows": [{"metadata": {"source_provenance": {
        "synthetic": nested_marker}}}]}, artifacts.PutOptions(
            kind="synthetic.nested_source", media_type="application/json"))
    lever = _source(store, "lever", [("lever:a", "a", "alpha")])
    norm = _source(store, "norm", [("norm:a", "c", "alpha")])
    payload = canon.from_canonical_bytes(store.get_bytes(lever.artifact_id))
    payload["synthetic"] = False
    changed = owner.persist_legal_subject_membership_source(
        store, owner.LegalSubjectMembershipSource.model_validate(payload),
        inputs=[artifacts.InputRef(artifact_id=ancestor.artifact_id, role="source_annotation")])
    with pytest.raises(ValueError, match=reason):
        owner.produce_legal_subject_spine(store, lever_source_ref=changed, norm_source_ref=norm)

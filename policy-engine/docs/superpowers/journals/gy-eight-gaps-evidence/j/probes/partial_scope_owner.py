"""Actual owner refusal for a raw L1 context projection, never J rate evidence.

The complete already-enumerated requested-observation relation is reread from
the immutable source. Projection keeps raw indicator, country and time scope;
it is an in-memory candidate, not a new governed capability or source receipt.
"""
from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta
import hashlib
import itertools
import json
from pathlib import Path
from typing import get_args

import duckdb

from polisyos.core.contracts.capability_resolution import (
    AuthorityPosture, RequirementToCapabilityQuery, RequirementTimeWindow,
)
from polisyos.runtime.quality.capability_authority import compose_capability_authority
from polisyos.runtime.quality.capability_index import (
    AuthorityEnvelope, CapabilityScope, CapabilitySourceAsset, EvidenceCapability,
    FreshnessEnvelope, QualityScore, RightsEnvelope,
)
from polisyos.runtime.quality.capability_resolver import RequirementToCapabilityResolver
from polisyos.runtime.quality.graded_outcomes import (
    GradedOutcomeEvidenceInput, GradedOutcomeInputError,
    S1_GRADED_OUTCOME_SCHEMA_VERSION, compose_graded_outcome,
)

ROOT = Path.cwd()


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def rows(connection, sql, args=()):
    cursor = connection.execute(sql, args)
    names = [field[0] for field in cursor.description]
    return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]


def main() -> None:
    prior = json.loads(json.loads((ROOT / "_build/gy-gaps/j/substrate-census-complete.json").read_text())["stdout"])
    request_path = ROOT / prior["request"]["path"]
    request = json.loads(request_path.read_text())
    constructs = [row["construct_ref"] for row in request["requested_constructs"]]
    independent_constructs = set(prior["request"]["constructs"])
    assert set(constructs) == independent_constructs and len(constructs) == len(independent_constructs)
    fixture = next(row for row in json.loads((ROOT / "architecture/policy_design_case/layer3_gy_slice0_fixture_manifest.json").read_text())["fixtures"] if row["fixture_id"] == "ua_msme_credit_worldbank_measurement")
    time_bounds = tuple(int(value) for value in fixture["time_horizon"].split("-"))
    assert len(time_bounds) == 2
    source = ROOT / prior["source"]["path"]
    source_hash = digest(source)
    assert source_hash == prior["source"]["sha256"]
    publish_path = source.with_name("manifest.json")
    publish = json.loads(publish_path.read_text())
    declared_path = f"/data/output/{source.parent.name}/datasets/graph/{source.name}"
    declarations = [item for item in publish["artifacts"] if item["path"] == declared_path]
    assert len(declarations) == 1 and declarations[0]["sha256"] == source_hash
    with duckdb.connect(str(source), read_only=True) as connection:
        observed = rows(connection, "SELECT * FROM ds_observations WHERE canonical_var = ANY(?) ORDER BY observation_id", [constructs])
        identities = {row["observation_id"] for row in observed}
        independent_ids = {row[0] for row in connection.execute("SELECT observation_id FROM ds_observations WHERE canonical_var IN (SELECT UNNEST(?))", [constructs]).fetchall()}
        assert identities == independent_ids == {row["identity"] for row in prior["required_observation_rows"]}
        assert len(observed) == len(identities)
        selected = [row for row in observed if row["country_code"] == fixture["jurisdiction"] and time_bounds[0] <= row["year"] <= time_bounds[1]]
        independent_selected = {row[0] for row in connection.execute("SELECT observation_id FROM ds_observations WHERE canonical_var=ANY(?) AND country_code=? AND year BETWEEN ? AND ?", [constructs, fixture["jurisdiction"], *time_bounds]).fetchall()}
        assert {row["observation_id"] for row in selected} == independent_selected
        groups = {}
        for row in selected:
            groups.setdefault((row["dataset_id"], row["raw_variable"], row["country_code"]), []).append(row)
        independent_groups = {tuple(row) for row in connection.execute("SELECT DISTINCT dataset_id,raw_variable,country_code FROM ds_observations WHERE canonical_var=ANY(?) AND country_code=? AND year BETWEEN ? AND ?", [constructs, fixture["jurisdiction"], *time_bounds]).fetchall()}
        assert set(groups) == independent_groups
        candidates = []
        for (dataset_id, raw_variable, country), values in sorted(groups.items()):
            dataset, = rows(connection, "SELECT * FROM ds_datasets WHERE id=?", [dataset_id])
            audits = rows(connection, "SELECT audit_id,canonical_variable,reviewed,reviewer_override FROM ds_alignment_audit WHERE dataset_id=? AND raw_variable=?", [dataset_id, raw_variable])
            assert all(row["value"] is not None for row in values)
            source_ref = f"duckdb:sha256:{source_hash}:ds_observations:{dataset_id}:{raw_variable}:{country}"
            capability = EvidenceCapability(
                capability_id=f"candidate:recorded-macro-context:{dataset_id}:{raw_variable}:{country}",
                construct=raw_variable,
                modality=("fabric_data",), evidence_mode="context_only",
                scope=CapabilityScope(geography=country, jurisdiction=country,
                    time_start=str(min(row["year"] for row in values)),
                    time_end=str(max(row["year"] for row in values)),
                    entity_scope="country", population="private_sector_macro_aggregate",
                    temporal_granularity=dataset["update_frequency"]),
                identification_mode="context_only", trust_tier="catalog_metadata",
                # This copies existing owner metadata; it is not an accuracy,
                # construct validity, correspondence or calibration estimate.
                quality_score=QualityScore(composite=dataset["quality_execution_readiness_score"]),
                source_assets=(CapabilitySourceAsset(ref=source_ref, source_layer="L1",
                    asset_type="duckdb_table_rows", role="recorded_macro_context",
                    path=str(source.relative_to(ROOT)), table="ds_observations",
                    row_count=len(values), fields=tuple(sorted(values[0])),
                    metadata={"observation_ids": sorted(row["observation_id"] for row in values)}),),
                limitations=("Original MSME construct binding is not established.",
                    "Country macro credit/GDP observations do not identify individual MSME outcomes."),
                authority_envelope=AuthorityEnvelope(research="candidate_context",
                    governed_pilot="blocked_original_construct_binding_missing",
                    production="blocked_original_construct_binding_missing",
                    authoritative_for=(), may_not_use_for=("claim_evidence_closeout",)),
                lineage_refs=(source_ref,),
                freshness_envelope=FreshnessEnvelope(freshness_class="recorded_historical",
                    observed_through=str(max(row["year"] for row in values)),
                    source_release_ref=f"file:sha256:{digest(publish_path)}"),
                rights_envelope=RightsEnvelope(access_class="recorded_public_source",
                    license=dataset["license"], claim_evidence_use_allowed=False),
                metadata={"raw_indicator": raw_variable, "source_alignment_audits": audits,
                    "projection_authority": "candidate_only", "positive_correspondence": None},
            )
            candidates.append(capability)
    assert digest(source) == source_hash
    resolver = RequirementToCapabilityResolver(capabilities=candidates,
        capability_index_ref=f"candidate-projection:sha256:{source_hash}")
    postures = get_args(AuthorityPosture)
    actual = []
    for construct, posture in itertools.product(constructs, postures):
        result = resolver.resolve(RequirementToCapabilityQuery(
            requirement_id=f"original:{construct}", construct=construct,
            entity_scope="firm", population_filter={"type": fixture["population"]},
            geography=fixture["jurisdiction"],
            time_window=RequirementTimeWindow(start=str(time_bounds[0]), end=str(time_bounds[1])),
            authority_level=posture, claim_use="claim_evidence_closeout"))
        assert result.satisfies_claim_evidence is False
        actual.append({"identity": [construct, posture], "result": result.model_dump(mode="json", exclude={"factors", "minimum_factor"})})
    expected = {(construct, posture) for construct in independent_constructs for posture in postures}
    assert {tuple(row["identity"]) for row in actual} == expected and len(actual) == len(expected)
    context_controls = []
    for candidate, posture in itertools.product(candidates, postures):
        # Direct owner sees the actual context object, not a missing-candidate
        # placeholder; even recognizing it cannot satisfy claim closeout.
        result = compose_capability_authority(candidate, posture=posture, claim_use="claim_evidence_closeout")
        assert result.status == "selected_context_only" and not result.satisfies_claim_evidence
        assert "context_only_cannot_satisfy_claim_evidence_closeout" in result.limitations
        context_controls.append({"identity": [candidate.capability_id, posture], "status": result.status,
            "satisfies_claim_evidence": result.satisfies_claim_evidence, "limitations": result.limitations})
    authority_levels = get_args(GradedOutcomeEvidenceInput.model_fields["authority_level"].annotation)
    s1 = []
    for construct, level in itertools.product(constructs, authority_levels):
        eligible = [row["result"]["selected_capability_ref"] for row in actual if row["identity"][0] == construct and row["result"]["satisfies_claim_evidence"]]
        assert not eligible
        request_input = GradedOutcomeEvidenceInput(schema_version=S1_GRADED_OUTCOME_SCHEMA_VERSION,
            case_id=request["case_id"], claim_id=construct, authority_level=level,
            requested_outcome="publish_with_limitation", evidence_profile="unsupported",
            partial_evidence_refs=tuple(eligible), mandatory_gate_state="none",
            owner="team-runtime-quality", decision_owner_ref=None,
            authority_profile_ref="runtime-quality:graded-outcomes-current-rule",
            review_refs=(), ttl_expires_at=datetime.now(UTC) + timedelta(days=1),
            public_limitation_note="Original MSME obligations remain unsupported by the macro context.",
            rule_version_ref=S1_GRADED_OUTCOME_SCHEMA_VERSION)
        try:
            decision = compose_graded_outcome(request_input)
        except GradedOutcomeInputError as exc:
            output = {"status": "refused", "error": str(exc)}
        else:
            assert decision.outcome != "publish_with_limitation"
            output = {"status": decision.outcome, "decision": decision.model_dump(mode="json")}
        s1.append({"identity": [construct, level], "eligible_original_claim_refs": eligible, **output})
    expected_s1 = {(construct, level) for level in authority_levels for construct in independent_constructs}
    assert {tuple(row["identity"]) for row in s1} == expected_s1 and len(s1) == len(expected_s1)
    assert sum(Counter(row["status"] for row in s1).values()) == len(expected_s1)
    print(json.dumps({
        "source": {"path": str(source.relative_to(ROOT)), "sha256": source_hash,
            "manifest_sha256": digest(publish_path), "request_sha256": digest(request_path)},
        "denominators": {"original_constructs": len(constructs), "independent_original_constructs": len(independent_constructs),
            "complete_L1_observation_table": prior["denominators"]["ds_observations"]["row_denominator"],
            "requested_observations": len(observed), "independent_observation_ids": len(independent_ids),
            "selected_UA_period_observations": len(selected), "independent_selected_ids": len(independent_selected),
            "candidate_raw_source_groups": len(candidates), "independent_sql_groups": len(independent_groups),
            "capability_cases": len(actual), "independent_capability_cases": len(expected),
            "S1_cases": len(s1), "independent_S1_cases": len(expected_s1)},
        "actual_raw_context_projection": [candidate.model_dump(mode="json", exclude={"quality_score"}) for candidate in candidates],
        "original_obligation_owner_results": actual,
        "recognized_context_owner_controls": context_controls,
        "actual_S1_results": s1,
        "scope": "Bounded owner proof about this raw context projection only; not a complete governed capability-index census.",
        "finding": "No original obligation is satisfied by this projection; original S1 limitation requests are refused.",
        "missing_conjunct": "A truthful source and admitted construct/scope binding supporting at least part of an original MSME obligation; macro label/alignment confidence cannot provide it.",
        "not_claimed": ["J positive rate", "correspondence", "calibration", "accuracy", "publication authority", "governed source admission", "absence of relevant data from every corpus"],
    }, indent=2))


if __name__ == "__main__":
    main()

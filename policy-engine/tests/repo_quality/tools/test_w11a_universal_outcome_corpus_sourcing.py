# ruff: noqa: PT018, S101

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
CORPUS_ROOT = REPO_ROOT / "docs/research/universal-policy-design/outcome-corpus"
README_PATH = CORPUS_ROOT / "README.md"

MIN_CASES = 12
MIN_DOMAINS = 6
REQUIRED_AUTHORITY_LEVELS = {"research", "governed", "production"}
REQUIRED_DRAFT_FIELDS = {
    "case_id",
    "jurisdiction",
    "policy_time",
    "policy_instrument",
    "targeting",
    "claims",
    "obligations",
    "known_outcomes_or_failures",
}
REQUIRED_W11A_FIELDS = {
    "domain",
    "authority_level",
    "jurisdiction_authority_level",
    "expected_evidence_families",
    "raw_source_refs",
    "redacted_source_hashes",
    "known_failure_limitation_labels",
    "references",
}
FORBIDDEN_LOCAL_SOURCE_PATTERNS = (
    re.compile(r"(?<![A-Za-z0-9_./-])/Users/"),
    re.compile(r"(?<![A-Za-z0-9_./-])~/(Downloads|Desktop|Documents)\b"),
    re.compile(r"(?<![A-Za-z0-9_./-])(?:Downloads|Desktop|Documents)/"),
    re.compile(r"file://"),
)


def test_w11a_outcome_corpus_has_required_case_domain_and_authority_coverage() -> None:
    cases = _load_cases()

    assert len(cases) >= MIN_CASES
    assert {case["domain"] for case in cases.values()} >= {
        "msme_credit_grant",
        "public_health_intervention",
        "housing_rent_control",
        "tax_enforcement",
        "education_access",
        "climate_adaptation",
        "labour_activation",
        "migration_displacement",
        "public_safety",
        "digital_public_service",
        "infrastructure_prioritisation",
        "social_protection_targeting",
    }
    assert len({case["domain"] for case in cases.values()}) >= MIN_DOMAINS
    assert {case["authority_level"] for case in cases.values()} >= REQUIRED_AUTHORITY_LEVELS
    assert len({case["jurisdiction_authority_level"] for case in cases.values()}) >= 3


def test_w11a_case_frontmatter_matches_annotation_protocol_seed_shape() -> None:
    for path, payload in _load_cases().items():
        missing = (REQUIRED_DRAFT_FIELDS | REQUIRED_W11A_FIELDS) - set(payload)
        assert not missing, f"{path.relative_to(REPO_ROOT)} missing {sorted(missing)}"

        instrument = payload["policy_instrument"]
        assert isinstance(instrument, dict), path
        assert {"instrument_type", "delivery_channel", "funding_channel"} <= set(instrument), path

        targeting = payload["targeting"]
        assert isinstance(targeting, dict), path
        assert targeting["targeting_type"], path
        assert targeting["beneficiary_classes"], path
        assert targeting["affected_populations"], path

        claims = payload["claims"]
        assert isinstance(claims, list) and claims, path
        claim = claims[0]
        assert {
            "claim_id",
            "claim_type",
            "text_ref",
            "scope",
            "evidence_refs",
            "method_refs",
            "legal_refs",
            "participation_refs",
            "risks",
            "tradeoffs",
            "admissibility_label",
            "limitation_refs",
            "contestability_status",
        } <= set(claim), path

        obligations = payload["obligations"]
        assert isinstance(obligations, list) and obligations, path
        obligation = obligations[0]
        assert {
            "obligation_id",
            "generated_from_facets",
            "required_evidence_family",
            "status",
            "reviewer_notes",
        } <= set(obligation), path

        outcomes = payload["known_outcomes_or_failures"]
        assert isinstance(outcomes, list) and outcomes, path
        outcome = outcomes[0]
        assert {
            "finding_id",
            "source_ref",
            "would_prior_obligation_have_flagged",
        } <= set(outcome), path


def test_w11a_case_sources_are_raw_repo_admissible_and_reference_claim_refs() -> None:
    for path, payload in _load_cases().items():
        source_refs = payload["raw_source_refs"]
        source_hashes = payload["redacted_source_hashes"]
        assert source_refs or source_hashes, f"{path.relative_to(REPO_ROOT)} has no source refs"

        for ref in source_refs:
            assert isinstance(ref, str) and ref.startswith("https://"), (path, ref)
            for pattern in FORBIDDEN_LOCAL_SOURCE_PATTERNS:
                assert pattern.search(ref) is None, f"{path.relative_to(REPO_ROOT)} has local ref"

        for hash_ref in source_hashes:
            assert isinstance(hash_ref, str) and hash_ref.startswith("sha256:"), (path, hash_ref)

        references = payload["references"]
        assert isinstance(references, list) and references, path
        reference_ids = {ref["ref_id"] for ref in references}
        for ref in references:
            assert ref.get("title"), (path, ref)
            assert ref.get("source_ref") or ref.get("redacted_source_hash"), (path, ref)

        for claim in payload["claims"]:
            _assert_registered(reference_ids, path, claim["text_ref"])
            for key in (
                "evidence_refs",
                "method_refs",
                "legal_refs",
                "participation_refs",
                "risks",
                "tradeoffs",
                "limitation_refs",
            ):
                for ref in claim[key]:
                    _assert_registered(reference_ids, path, ref)
        for outcome in payload["known_outcomes_or_failures"]:
            _assert_registered(reference_ids, path, outcome["source_ref"])


def test_w11a_readme_indexes_all_cases_and_preserves_pattern_pass() -> None:
    readme = README_PATH.read_text(encoding="utf-8")
    cases = _load_cases()

    assert "W11.A Universal Outcome Corpus Sourcing" in readme
    assert "P01" in readme and "P10" in readme and "P15" in readme
    assert "artifact_missing" in readme
    assert "consumer_missing" in readme
    assert "semantic_test_missing" in readme

    for payload in cases.values():
        assert payload["case_id"] in readme
        assert payload["domain"] in readme
        assert payload["authority_level"] in readme


def _load_cases() -> dict[Path, dict[str, Any]]:
    assert CORPUS_ROOT.is_dir()
    paths = sorted(path for path in CORPUS_ROOT.glob("*.md") if path.name != "README.md")
    assert paths
    return {path: _load_frontmatter(path) for path in paths}


def _load_frontmatter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\n(?P<yaml>.*?)\n---\n", text, flags=re.DOTALL)
    assert match, f"{path.relative_to(REPO_ROOT)} missing YAML frontmatter"
    payload = yaml.safe_load(match.group("yaml"))
    assert isinstance(payload, dict), path
    return payload


def _assert_registered(reference_ids: set[str], path: Path, ref: object) -> None:
    assert isinstance(ref, str) and ref in reference_ids, (
        f"{path.relative_to(REPO_ROOT)} references unregistered annotation ref {ref!r}"
    )

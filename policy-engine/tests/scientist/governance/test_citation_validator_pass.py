"""Tests for CitationValidatorPass."""

from __future__ import annotations

import pytest

from polisyos.scientist.governance.passes.citation_validator_pass import CitationValidatorPass


class TestCitationValidatorPass:
    def test_pass_id(self):
        assert CitationValidatorPass().pass_id == "citation_validator"

    def test_valid_claims(self, pass_context_factory):
        ctx = pass_context_factory(state={
            "verified_claims": [
                {"source_ref": "ref1", "confidence": 0.8, "quote": "short quote"},
            ],
        })
        issues = CitationValidatorPass().validate(ctx)
        assert len(issues) == 0

    def test_missing_source_ref(self, pass_context_factory):
        ctx = pass_context_factory(state={
            "verified_claims": [{"confidence": 0.9}],
        })
        issues = CitationValidatorPass().validate(ctx)
        assert any(i.code == "CITATION_MISSING_REF" for i in issues)

    def test_invalid_confidence(self, pass_context_factory):
        ctx = pass_context_factory(state={
            "verified_claims": [{"source_ref": "r", "confidence": 1.5}],
        })
        issues = CitationValidatorPass().validate(ctx)
        assert any(i.code == "CITATION_INVALID_CONFIDENCE" for i in issues)

    def test_long_quote(self, pass_context_factory):
        ctx = pass_context_factory(state={
            "verified_claims": [{"source_ref": "r", "quote": "x" * 2001}],
        })
        issues = CitationValidatorPass().validate(ctx)
        assert any(i.code == "CITATION_LONG_QUOTE" for i in issues)

    def test_no_claims(self, pass_context_factory):
        ctx = pass_context_factory(state={})
        issues = CitationValidatorPass().validate(ctx)
        assert len(issues) == 0

# Citation Faithfulness Golden Cases

Owner: `team-quality`
Last updated: 2026-05-13

## Purpose

These hand-authored fixtures exercise the deterministic Phase 3.3 citation
faithfulness checker. They cover exact support, partial support, scope limits,
contradictions, irrelevant citations, fabricated refs, and unverifiable refs.

## Regeneration

Fixtures are reviewed inputs, not generated outputs. Update `cases.json`
together with `tests/unit/scientist/validation/test_citation_faithfulness.py`
when faithfulness policy changes.

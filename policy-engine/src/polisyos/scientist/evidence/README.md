# Scientist Evidence

Evidence owns source configuration, safe web evidence handling, claim support,
claim ledgers, and run provenance helpers for Scientist artifacts.

Use this hub for:

- `sources.py`: configured evidence source paths and source status payloads;
- `safe_fetch.py`, `source_quality.py`, `snippet_ledger.py`, and `verifier.py`:
  web evidence safety and validation;
- `claims/`: claim ledger, lifecycle, readiness, projections, and publication
  validators;
- `provenance/`: run-level provenance DAGs and PROV-JSON serialization.

Do not restore the retired `polisyos.scientist.evidence_sources` module, the
retired `polisyos.scientist.provenance` compatibility package, or the retired
`polisyos.scientist.claims` compatibility package.

Tests live under `tests/unit/scientist/evidence`, with nested claim and
provenance tests under `claims/` and `provenance/`.

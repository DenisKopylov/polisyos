# Evidence Authoring

- Keep evidence-source configuration in `sources.py`; do not reintroduce an
  `evidence_sources` implementation package.
- Keep claim-spine code under `claims/`. Persisted schema names may remain on
  legacy names for artifact compatibility, but imports should use
  `polisyos.scientist.evidence.claims.*`.
- Keep run provenance under `provenance/`. New first-party imports should use
  `polisyos.scientist.evidence.provenance.*`.
- Add new shim metadata in `compatibility.py` whenever a public import is moved.
- Add tests beside the concept: evidence safety in `tests/unit/scientist/evidence`,
  claim ledgers in `tests/unit/scientist/evidence/claims`, and provenance in
  `tests/unit/scientist/evidence/provenance`.

# Scientist Evidence

Evidence owns source configuration, safe web evidence handling, claim support,
claim ledgers, and run provenance helpers for Scientist artifacts.

Use this hub for:

- `sources.py`: configured evidence source paths and source status payloads;
- `safe_fetch.py`, `source_quality.py`, `snippet_ledger.py`, and `verifier.py`:
  web evidence safety and validation;
- `claims/`: claim ledger, lifecycle, readiness, projections, publication
  validators, and the internal strict trust-claim posture contract/calculus in
  `claims/posture.py`;
- `provenance/`: run-level provenance DAGs and PROV-JSON serialization.

Do not restore the retired `polisyos.scientist.evidence_sources` module, the
retired `polisyos.scientist.provenance` compatibility package, or the retired
`polisyos.scientist.claims` compatibility package.

Trust posture is compiled by quality tooling from complete source and
ratified-document walks. It is distinct from the per-run runtime claim registry:
neither artifact may discharge the other artifact's evidence requirements.
`claims/posture.py` is internal and is not a package-facade export.

The posture contract requires the exact eight-predicate authority basis and
content-bound evidence objects; authored predicate booleans are cross-checked
against source, purpose, owner, jurisdiction, review time, verifier provenance,
identity, and blocker facts. The checker also owns the generic C02 seams for a
strict accessibility projection index, the five-file historical page-a11y
receipt, the generated-family output probe, and the narrow generated-reference
writer. Those seams remain blocked or historical until their typed evidence and
purpose requirements are independently established.

The compiler always emits the fixed opening identity, custody, accessibility,
certification, current-conformance, and grounded-performance rows, including
blocked rows when a document basis is unavailable. Projection memberships are
recomputed from those rows. Evidence digests resolve against admitted source
bytes, and verifier references resolve against the closed verifier set derived
from the typed identity, document, and receipt bases; marker prefixes and
nonempty verifier names carry no authority.

Tests live under `tests/unit/scientist/evidence`, with nested claim and
provenance tests under `claims/` and `provenance/`.

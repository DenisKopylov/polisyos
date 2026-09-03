# Extraction-strength vocabulary split journal

## Task 1 — typed envelope and legacy absence adapter

### Capability state

This delivery is deliberately `contract_only`: it adds a strict, frozen v2
vocabulary envelope, an explicit one-way legacy-absence adapter, and semantic
contract tests. No v2 producer, persisted v2 artifact, orchestration bridge,
consumer migration, verification receipt, or external surface is present.

### RED evidence

From `policy-engine/`:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/src" /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest tests/unit/data_forge/domains/academic/batch/test_claim_vocabulary_contract.py tests/unit/ir/test_literature_contract.py -q
```

Result: collection failed with two expected `ImportError` failures because
`ClaimVocabularyAxisStatus` did not yet exist in
`polisyos.ir.analytics.literature`. This is the intended missing-contract
failure for C03--C06, rather than an environment or syntax failure.

### GREEN evidence

From `policy-engine/`:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/src" /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest tests/unit/data_forge/domains/academic/batch/test_claim_vocabulary_contract.py tests/unit/ir/test_literature_contract.py -q
```

Result: `17 passed`.

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/src" /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m ruff check src/polisyos/ir/analytics/literature.py tests/unit/data_forge/domains/academic/batch/test_claim_vocabulary_contract.py tests/unit/ir/test_literature_contract.py
```

Result: `All checks passed!`.

### C03--C06 coverage

- C03: a strict v2 payload rejects generic `strength`; the named adapter retains
  the raw legacy label and the envelope survives JSON round-trip validation.
- C04: legacy `moderate` retains only `legacy_strength_label`; all four typed
  axes are null and all four statuses are `not_established`.
- C05: the adapter accepts no parent-study-design or record-confidence argument,
  so neither can fill a claim-level axis.
- C06: design and evidence axes may be supplied independently only as explicit
  typed candidates; neither derives the other, and a shared `rct` spelling is
  still rejected under generic `strength`.

The unactivated-scope test also confirms that `WorkRecord.causal_claims` stays
`list[dict]` and `CausalClaim.from_payload()` remains on its existing v1 path.

### Exclusions held

No changes were made to lineage, adjudication authority types, Runtime,
producers, stores, graph code, `docs/plans/active/`, or `production_data`.
No production-data read, hash, migration, producer run, or bound debt-checker
run occurred.

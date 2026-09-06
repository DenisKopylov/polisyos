# Measuring instrument repair plan

**Goal:** Explain and remove station-dependent schema findings, then hand the
architect a pinned CI push candidate. The user task is the execution specification.

**Architecture:** Extend the existing generator and its tests. A schema check
must compare current runtime schemas and generated references with actual output
bytes; a defining-file hash is not a transitive schema identity. Preserve the
integration cache before probing it. No register edits or remote writes.

**Baseline:** `0373364448f766ecba871f3abae23a2b563e63ac`, branch
`codex/measuring-instrument`, worktree `.worktrees/measuring-instrument`.

## Pattern pass

- P29/P32/P38: the property is complete current artifact disagreement; the existing
  cache tests only the defining source file and trusts its stored derived payload.
  A nested model change is a concrete divergent case.
- P31/P33: cover false red, false green/undercount, regeneration, and optional
  early-return flags, using real model generation and changed dependency bytes.
- P35/P37: enumerate all selected ABI entries and all declared family tables;
  compare path sets and hashes. Receipts are recomputed; independent worktree
  agreement is independently reconciled. CI execution remains not_established.
- P41: attribute local gate findings only to an explicit station and base. Do not
  call a local replay a completed CI run.
- Missing capability: station reproducibility is `verification_missing` until
  the fresh-worktree set comparison; the CI witness is `semantic_test_missing`
  until a real run catches it.

## Execution

- [x] Preserve integration cache files, hashes, commit, cleanliness and provisioning.
- [x] Resolve every ABI entry; compare its persisted payload with fresh generation.
- [x] Compare unchanged integration with an empty-cache control and a fresh checkout.
- [x] Add behavioral regression tests in
  `tests/repo_quality/tools/test_schema_station_independence.py`; observe failure
  before editing `tools/quality/diagnostics/gen_schema.py`.
- [x] Remove stale payload/early-return authority without weakening drift checks.
  Preserve CLI compatibility where practical; document changed optimisation semantics.
- [x] Run focused diagnostics/importer tests, Ruff and architecture guardrails.
  Commit the source repair separately from journal findings.
  The focused tests and Ruff passed; architecture guardrails have no valid passing
  receipt because their generated-artifact probe rebound the caller's editable
  venv. Evidence was preserved, the task venv restored, and the defect assigned
  proposed owners in the journal. Independent review could not execute because
  its service returned an out-of-credits error.
- [x] Provision two separate worktrees at the repair commit. Run the declared
  check in each and compare the complete artifact path/hash and finding sets.
- [x] Trace the same cache class across every other declared `check_command`;
  record the full family denominator and both positive and negative results.
- [x] Inspect `abi.yml`, read the remote ref, run targeted local gate probes and
  name expected failures with proposed owners in the journal.
- [x] Prepare the journal and complete artifact evidence for the push handback.
  The architect decides the push. CI result reading and the deliberate witness
  commit/CI/revert cycle wait for that decision and a readable run.

Closeout record: `docs/superpowers/journals/2026-09-06-measuring-instrument.md`.
The prepared record is committed and read back as the final local delivery step;
it does not assert that the pending CI work is complete. The documentation replay
adds no docs-lifecycle findings. The last-mile scanner adds the journal and evidence
file themselves to LM-025 by matching a substring in valid evidence paths; that
owned delta is preserved in a separate finding with proposed owners.

Only contended resource: the preserved integration cache. Its control probes are
serial. Independent provisioning and read-only source inspections may run together.
No directory-wide pytest, full backend wave, history rewriting or delivery workaround.

# E02 Scientist search-state compatibility runbook

This is a source-version migration procedure for local Scientist state and CAS history.
It does not establish the state of any deployed or production environment.

## Before a writer upgrade

1. Identify the configured local CAS/store root and retain the exact existing VOI
   snapshot bytes under search_registry/voi/. Do not edit or relabel the snapshot.
2. Upgrade the reader and writer together before producing new state. The current
   VOIModelSnapshot may contain objective_source; an older strict extra=forbid model
   rejects that key. No cross-version VOI downgrade reader is provided.
3. Record the current release/version, snapshot path and SHA-256, and any selected
   CAS refs needed to replay the state. Do not copy broad production payloads.

## Validate the new reader

- Load a retained older VOI snapshot through the current reader. Missing selected
  source basis must remain unbound/not_established; the reader must not infer scores
  from old numeric values.
- Preserve search.transfer.history refs. Current readers may display schema 3/4
  histories as diagnostic history, but only source-bound schema 5 supports the new
  selected rule/unit replay. ObjectiveScoreAssessment schema 1 remains
  diagnostic-only; schema 2 carries the selected source-unit bindings.
- When transporting serialized JobResult between processes or versions, verify
  the receiving DTO accepts method_execution_capture. The pre-change strict DTO
  rejects the added field even when its value reports unavailable.

## Rollback boundary

Do not point an older reader at a snapshot written by the new writer. If rollback is
required, use the version-matched retained pre-upgrade snapshot and reader together.
No automatic conversion, downgrade writer, or compatibility shim is provided. If the
matching retained bytes are unavailable, stop the rollback at this boundary and
preserve the current snapshot and CAS refs for owner review; do not delete or rewrite
them to force loading.

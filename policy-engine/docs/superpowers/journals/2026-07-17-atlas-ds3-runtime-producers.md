# Atlas DS3 Runtime Producers & Export Infrastructure Journal

## 2026-07-17 — binding and red phase

- Created the fenced worktree `.worktrees/atlas-ds3` on
  `codex/atlas-ds3-runtime-producers` from `7b6933770`.
- Read the Revision-3 preamble, Phase-A rebaseline, DS3 master section, synthesis
  PI-01..PI-03, DS1 N021/N022, GY §3.5.10/§3.5.11, contributor rules, and the
  failure/repair register before design.
- Committed the binding plan as `9516d35cb`.
- Baseline runtime-fixture collection did not reach a test in three minutes: the
  existing eager `runtime.http.services -> runtime.quality -> scientist -> foundry`
  import chain was still loading the causal catalog. It was interrupted and recorded,
  not classified as a DS3 test failure. The DS3 service will remain import-lazy; final
  fixture verification must be rerun after implementation.

### Observed red receipts

All commands used plugin-autoload-disabled pytest only to isolate the new contract from
the unrelated eager startup chain; final verification uses the repository command.

1. `test_depth_n_projection_preserves_recorded_validator_outputs_without_rederiving`
   failed collection because
   `src/polisyos/runtime/http/services/governed_projections.py` did not exist.
2. `test_reference_shell_uses_only_shared_generated_client_home` failed because the
   package client had no `listGovernedProjections()` proof call.
3. `test_committed_openapi_preserves_lex_truth_fields` failed because the committed Lex
   result schema lacked the upstream grounding, authority, hallucination, document,
   temporal, provenance, and provision-anchor fields.
4. `test_committed_openapi_has_governed_export_contracts` failed because all three DS3
   export/channel paths were absent.

The failures match the missing producer/client/contract behavior. No positive runtime
implementation existed when they were captured.


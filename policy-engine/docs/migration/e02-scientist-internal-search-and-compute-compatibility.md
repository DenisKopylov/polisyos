# E02 Scientist internal search and compute compatibility

This guide describes the current source compatibility boundary for the E02 search and
compute changes. It does not expand the public namespace or declare G acceptance.

## Governed namespace

architecture/public_surface/contract.toml says that any polisyos module path not
listed in its manifest is internal by default. It lists polisyos.scientist and
polisyos.scientist.policy_design, but not polisyos.scientist.compute,
polisyos.scientist.methods.search, or polisyos.scientist.methods.autotune.
The root Scientist facade does not re-export the reviewed search or compute symbols.
policy_design does export ObjectiveChannelValue, PolicyEvaluationVector,
PolicyArtifactBuildInput, and PolicyArtifactBuilder; those rows remain public and
are not reclassified by this guide.

The unlisted package __all__ values, README headings, qualified importability, and
existing first-party callers do not override the governed namespace. Existing exports
and runtime behavior are retained. This reconciliation does not add the unlisted
packages to the contract. Expanding those packages would create new public compatibility
obligations, require a curated supported-entrypoint decision and inventory review, and
is not required by the current contract.

## Consumer migration

- **Stage A:** Internal FunnelOrchestrator.as_stage_a_callable callers read the
  EvaluationBundle fields (objective_value, score_status, score_assessment,
  is_promising, and stage_a_passed). SearchController continues to accept legacy
  tuple evaluators. This is an internal caller migration, not a public API guarantee.
- **Configured search:** Provide the selected metric, direction, canonical rule, and
  exact source unit identity where required. An unconfigured Bayesian optimizer remains
  candidate-only. Search/autotune imports remain available to first-party code, but
  are not supported external entrypoints.
- **VOI runtime state:** New predictive snapshots use VOIModelSnapshot schema 1.4
  and may persist the selected objective_source needed for recomputation. The current
  reader accepts older unbound snapshots as diagnostic/not_established; it does not
  infer a score from an old value. Older strict readers reject the added field.
- **Transfer history:** New search.transfer.history CAS payloads use
  history_schema_version=5; ObjectiveScoreAssessment payloads use schema 2.0.
  Current readers keep schema 3/4 histories diagnostic-only and do not backfill their
  selected rule or units from the old payload. Preserve old refs and regenerate a new
  candidate history through the current owner when a selected basis is available.
- **Legacy JobResult:** Successful run_job output includes method_execution_capture
  with an available, partial, or unavailable state, including when no capture roles
  exist. A pre-change strict extra=forbid reader rejects this new JSON key. Upgrade
  such readers before consuming the new producer output, or use an explicit field
  projection for a known older reader. No dual-format writer or supported external
  compute API is claimed.

Treat all described score and capture records as candidate diagnostic evidence. They
do not establish measurement authority, causal validity, external custody, calibration,
or policy publication authority.

# Layer 3 G8 Health-Metric Governance and Corpus Re-Basing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the five Layer 3 tradeoff metrics governed, replay-visible signals and add the D4.4 corpus re-basing rule/receipt layer so S14 cannot stale into gameability or leak sealed answers.

**Architecture:** Add one cross-cutting runtime-quality producer that reads existing G0-G7/S14 artifacts, normalizes the current metric dialects into canonical governed signals, diagnoses domain-ceiling versus search/governance/abstention ceilings, emits warning and metric-gaming firewalls, and produces D4.4 re-basing receipts. Keep G8 diagnostic and governance-only: it never creates production, recommendation, closeout, publication, scorecard, legal, or universal-claim authority.

**Tech Stack:** Python 3.14, Pydantic strict DTOs, JSON/TOML committed artifacts under `architecture/policy_design_case/`, existing runtime-quality replay/projection helpers, pytest unit and repo-quality checks, `tools/quality/validation/*` readiness validators.

---

## Source Documents Checked

- `docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER3_GROUNDING_SUBORDINATION_IMPLEMENTATION_PLAN.md` — G8 scope, closure contract, firewalls, health metrics, and done conditions.
- `docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md` — §8.2-§8.4 tradeoffs, five health signals, domain-ceiling/search-ceiling distinction, and open questions.
- `docs/system-design-decisions/universal-policy-design-target-architecture-and-gap.md` — D4.4 corpus re-basing rule and required re-annotation fields.
- `docs/reference/policy-design-case-failure-patterns.md` — capability reality labels, pattern pass, repair priority, and closeout check.
- Current G1-G7/S14 runtime artifacts under `architecture/policy_design_case/` — especially the health deltas, G1/G2/G3/GL search recall/freshness artifacts, flat and nested readiness manifests, `layer3_g4_governance_throughput_delta.json`, G5 effective-independence/useful-design sidecars, G6 agent authority/search/conformance sidecars, G7 authority/S14/feed artifacts, and `layer2_s14_universality_assurance_manifest.json`.

## Current Reality After G7

G8 starts from a working but intentionally uneven picture.

- G0 owns the canonical five metric names in `architecture/policy_design_case/layer3_health_metric_ledgers.toml`.
- G1/G2/G3/GL write `[health_metric_delta]` TOML with canonical metric ids and `readings`.
- G4 writes promotion-specific health metrics, not the canonical five, so G8 must treat it as a governance-throughput source through `layer3_g4_governance_throughput_delta.json` and readiness summaries.
- G1/G2/G3/GL readiness manifests are legacy-flat JSON payloads, while G5/G6/G7 use nested `summary` plus selected top-level drift keys, and G4 writes a mixed readiness manifest. G8 source parsing must support both shapes.
- G3 search recall/freshness uses `freshness_status`, `known_seed_count`, `recalled_seed_count`, and seed-specific status fields inside `search_recall_freshness`; GL uses a top-level legal-search report with `known_seed_status` and `index_freshness_status`.
- G4's canonical runtime owner is `src/polisyos/runtime/quality/layer3_promotion_gate.py`. The authoritative governance-throughput source is `layer3_g4_governance_throughput_delta.json`, with promotion-count TOML only as a secondary health snapshot.
- G5 writes `metric_statuses` and uses the search metric spelling `search-recall@known-seeds + index-staleness` with spaces around `+`.
- G5 also persists effective-independence and useful-design eligibility sidecars. G8 should read `layer3_g5_effective_evidence_independence.json`, `layer3_g5_grounded_result_evidence_set.json`, `layer3_g5_grounded_abstention_quality_record.json`, and `layer3_g5_useful_design_metric_eligibility_join.json` instead of recomputing evidence independence or useful-design credit.
- G6 writes rate fields in `layer3_g6_health_metric_delta.toml` and a richer JSON `layer3_g6_demand_pull_vs_abstention_delta.json`; the JSON is authoritative for the G6 demand-pull reading, and numeric `0.0`/`1.0` readings must be interpreted as signal semantics rather than blindly mapped to `pass`.
- G6 authority/firewall evidence is spread across `layer3_g6_conformance_report.json`, `layer3_g6_search_ledger.json`, `layer3_g6_orchestration_choice_audit.json`, and `layer3_g6_candidate_authority_firewall_report.json`; G8 can cite these for open-question answers without creating agent authority.
- G7 writes region-specific keys in `layer3_g7_health_metric_delta.toml`; current readiness is engineering `pass` but value closure is `blocked_by_current_g5_unchanged_blocker`, grounded region count is `0`, and S14 feed is `blocked_no_real_grounded_breadth`.
- G7's audit surface currently has `status = "fail"` with blocker issue codes; the canonical blocker values live in readiness summary and S14 feed/input manifests. G8 must not infer grounded breadth from the audit surface alone.
- S14 already has sealed-battery freeze-hash discipline in `architecture/policy_design_case/layer2_corpus_partition.json` and `architecture/policy_design_case/layer2_s14_universality_assurance_manifest.json`.
- G7 already added a non-mutating S14 runner hook through `--g7-grounded-breadth-input-manifest`; G8 should consume this state rather than rewrite the runner as its primary capability.

This means the central G8 risk is not missing data. The risk is normalizing inconsistent metric shapes into an overconfident score, or letting re-basing become a backdoor for threshold lowering or sealed answer leakage.

## Existing Code Patterns To Reuse

G8 should follow the established G5/G6/G7 shape rather than inventing a new validator style.

- Use the canonical module import path (`polisyos.runtime.quality.layer3_health_metric_governance`) and keep `src/polisyos/runtime/quality/__init__.py` unchanged, matching G0/G5/G6/G7.
- Mirror the G7 readiness validator structure: explicit artifact path constants, `EXPECTED_ARTIFACT_PATHS`, `EXPECTED_MANIFEST_DRIFT_KEYS`, `_build_runtime_bundle`/bundle builder, `_write_artifacts`, `_summary`, nested `readiness_manifest["summary"]` plus top-level drift keys, `_manifest_runtime_drift_keys`, `_validate_written_artifact_set`, registration/docs checks, and text/json CLI output.
- Reuse the existing validator helper idioms: `_resolve_repo_path`, `_json_dumps(... ensure_ascii=False ...)`, `_toml_value`, `_toml_key`, `_dump`, `_mapping`, `_sequence`, and issue dictionaries shaped as `{"code", "path", "message"}`. Do not create a third readiness-report dialect.
- Reuse G5/G7 authority-boundary patterns for closeout: G8 may expose a closeout consumer gate, but the gate must deny `closeout_authority` and `runtime_closeout_authority` at the consumer side rather than integrating with `core_runtime_closeout`.
- Reuse existing S14 manifest supporting records where they already satisfy D4.4 concepts (`D4CorpusTrackCoverage`, `UniversalityBreadthFloorConfig`, `GroundedAuthorityCoverageRecord`, `EvaluationStatusCompositionRecord`, `EnvelopeRevisionDynamicsRecord`, sealed-battery metadata). Only fields not covered by those records should be marked `required_for_next_rebase`.
- Normalize source manifest payloads through a helper that treats `payload["summary"]` as preferred when present and falls back to flat top-level readiness keys. Do not assume all slice readiness manifests have converged to the G5-G7 nested manifest shape.
- Treat G8 normalized signals as authority-boundary-owning artifacts. Several upstream sidecars are intentionally compact and do not carry `may_not_use_for`; G8 should cite their raw refs while applying G8's own `authoritative_for` and `may_not_use_for` on every emitted signal and surface.

## Workload Calibration

Strong existing pieces:

- G0 already owns the canonical five metric ids, owners, freeze values, and trend vocabularies.
- G1/G2/G3/GL already persist search recall/freshness artifacts; G8 can read them directly instead of reconstructing search tests.
- G4 already persists `layer3_g4_governance_throughput_delta.json`; G8 should not infer governance throughput from promotion health TOML.
- G5/G6/G7 already encode authority denials, projection-only public refs, and closeout/S14 consumer-gate patterns that G8 can mirror.
- G5 already persists effective-independence, grounded-result, grounded-abstention, and useful-design eligibility artifacts; G8 can surface those as governance readings rather than rebuilding evidence independence or useful-design logic.
- G6 already persists bounded-agent conformance, search ledger, orchestration choice audit, and candidate authority firewall artifacts; G8 can answer the §8.4 agent-authority question by citing those artifacts.
- S14 already records sealed-battery freeze hash and several D4-related supporting records; G8 should not re-run or inspect hidden S14 fixtures.

Weak or easy-to-underestimate pieces:

- Metric dialect drift is real: TOML `readings`, TOML `metric_statuses`, JSON top-level fields, nested `summary`, JSON `readings`, G7 region keys, and source-specific spelling all appear in current artifacts.
- Manifest dialect drift is real too: G1 uses `counts`, G2/G3/GL are flat readiness-manifest DTO dumps, G4 merges runtime `summary` with top-level drift keys, and G5-G7 use nested `summary`. G8 readers must support all of these without rewriting old slices.
- Search-recall dialect drift is broader than `search_recall_status`: G3 uses `freshness_status` and seed-count fields; GL uses legal KG statuses such as `known_seed_status`, `index_freshness_status`, and `search_ceiling_repair_required`.
- Numeric demand readings are semantic, not merely numeric telemetry. `abstention_or_blocker_rate = 1.0` and `grounded_result_rate = 0.0` must block domain-ceiling claims until a grounded response exists.
- G7 health delta does not carry search recall or governance throughput; relying on `layer3_g7_health_metric_delta.toml` alone would miss the most important T5/T7 evidence.
- Some source sidecars intentionally omit `may_not_use_for`. That is not a source bug, but G8 cannot treat absence as inherited authority; normalized G8 signals must declare their own denied uses.
- Readiness drift and registration checks should follow G7's nested-summary/top-level-drift style. A flat G8 readiness manifest would be a new dialect and make drift checks weaker.
- D4.4 coverage is not hard because there is no data; it is hard because the plan must distinguish already-covered S14 supporting records from fields that are genuinely pending the next rebase.

## Scope Boundaries

G8 owns:

- canonical metric registry and alias normalization for all five health metrics;
- normalized governed metric signals with raw source refs, provenance, rule versions, freshness and authority boundaries;
- cross-metric diagnosis that distinguishes domain ceiling, search ceiling, governance bottleneck, semantic-loss blocker, and abstention inertia;
- warning lifecycle for stale or degraded metric signals;
- metric-gaming firewall;
- first-class metric trend report so CI can report governed metric movement, not only a point-in-time snapshot;
- D4.4 corpus re-basing rule, field coverage matrix, trigger ledger, candidate-set, receipt, and sealed-battery integrity join;
- closeout signal consumer gate proving closeout/readiness can read G8 signals without gaining G8 authority;
- empirical answer ledger for the §8.4 open questions;
- EXPERT/MACHINE audit surface and projection-only public refs;
- readiness validator, exact generated artifact family, conformance report, route registry, and registry ratchet.

G8 does not own:

- changing S14 sealed fixtures or accessing hidden case payloads in development paths;
- lowering S14 breadth floors, thresholds, or gold-label expectations;
- converting G5/G7 current blockers into value closure;
- claiming a domain ceiling unless search, governance, demand-pull, semantic-loss, and grounded-breadth gates prove it;
- optimizing `useful_design_rate`;
- creating public recommendation, production, legal, publication, closeout, scorecard, or universal-claim authority.

## Capability Contract

Capability reality target: `implemented`.

Typed contract/artifact:

- `Layer3G8HealthMetricRegistry`
- `Layer3G8MetricSourceSnapshot`
- `Layer3G8NormalizedMetricSignals`
- `Layer3G8MetricTrendReport`
- `Layer3G8CrossMetricDiagnosis`
- `Layer3G8DomainVsSearchCeilingGate`
- `Layer3G8MetricGamingFirewall`
- `Layer3G8WarningLifecycleLedger`
- `Layer3G8D44CorpusRebasingRule`
- `Layer3G8D44ReannotationCoverageMatrix`
- `Layer3G8D44RebasingTriggerLedger`
- `Layer3G8D44RebasingCandidateSet`
- `Layer3G8D44RebasingReceipt`
- `Layer3G8SealedBatteryIntegrityJoin`
- `Layer3G8OpenQuestionAnswerLedger`
- `Layer3G8MetricGovernanceAuditSurface`
- `Layer3G8CloseoutSignalConsumerGate`
- `Layer3G8ConformanceReport`

Producer:

- `src/polisyos/runtime/quality/layer3_health_metric_governance.py`

Persisted artifacts:

- every artifact listed in `EXPECTED_ARTIFACT_PATHS` in the G8 readiness validator.

Bridge/consumer:

- `tools/quality/validation/check_policy_design_case_layer3_g8_readiness.py` reads existing G0-G7/S14 artifacts, builds the G8 bundle, writes committed artifacts, and fails on drift.
- `layer3_g8_closeout_signal_consumer_gate.json` is the explicit closeout-side consumer bridge: it proves G8 signals are visible to closeout/readiness while `closeout_authority` and `runtime_closeout_authority` remain denied uses.
- G8 reads the S14 assurance manifest and G7 S14 input manifest as consumers; it does not replace S14 as the universality gate.

Surface:

- EXPERT/MACHINE audit surface in `layer3_g8_metric_governance_audit_surface.json`.
- PUBLIC projection refs are `out_of_scope_reference_only` and deny authority uses.

Verification:

- unit tests for registry, normalization, trend reporting, diagnosis, warning lifecycle, metric-gaming, D4.4 coverage/triggers/receipts, closeout consumer visibility, and open-question answers;
- repo-quality tests for exact artifact set, registration/docs, readiness drift, and conformance negatives;
- existing S14 runner test continues to prove G7 input does not mutate freeze hashes.

Semantic negatives:

- metric "improvement" by threshold lowering is blocked;
- search recall miss cannot be reported as domain ceiling;
- flat expansion plus current G5/G7 blockers cannot be reported as domain ceiling;
- useful-design-rate optimization is blocked;
- re-basing cannot mutate sealed battery, leak gold/hidden payload refs, lower S14 floor, omit freeze-hash receipts, skip D4.4 re-annotation fields, or omit rebase trigger status;
- closeout can read G8 signals but cannot use them as closeout authority;
- public projection cannot mint metric authority.

## Pattern Pass

Relevant failure patterns:

- `P01` contract-only capability: G8 must persist artifacts, bridge through readiness, and prove consumer visibility.
- `P02` thin orchestration: G8 must read current G0-G7/S14 artifacts, not only define models.
- `P03` hidden internal richness: EXPERT/MACHINE surfaces must expose raw refs, diagnoses, receipts, and warnings.
- `P04` status lattice gap: `pass`, `blocked`, `flat`, `not_claimed_current_grounding_blocker`, `search_ceiling`, `domain_ceiling_candidate`, and `not_due` must compose explicitly.
- `P05` authority boundary leak: all G8 artifacts need `authoritative_for` and `may_not_use_for`.
- `P07` rule replay gap: re-basing receipts must carry rule/schema versions and freeze hashes.
- `P08` time-role conflation: metric freshness, source generation time, re-basing effective time, and sealed-battery freeze time must remain separate.
- `P09` warning lifecycle gap: stale or degraded metrics need owners, deadlines, aging policy, accepted-deficit policy, and closeout impact.
- `P10` semantic adequacy gap: tests must prove search/domain ceiling semantics and anti-gaming behavior, not only field presence.
- `P11` failure-only memory: the open-question ledger records current successes as well as blockers.
- `P13` governance gravity: G8 should normalize and govern existing artifacts; it should not require every slice to rewrite its historical metrics.
- `P14` evidence independence inflation: G8 must surface `effective_independence_inflated` from G5/G7 rather than averaging it away.
- `P15` LLM speculation laundering: G6 candidate/agent outputs remain candidate/audit only.
- `P25` search-control laundering: search frontiers and no-hit results cannot become domain-ceiling claims.
- `P26` responsibility-integrity laundering: demand-pull and re-basing governance need accountable owners.

Existing anti-patterns found:

- Metric dialect drift across G1-G7: different keys, TOML shapes, JSON sidecars, and region suffixes.
- G4 health delta does not carry the canonical five metrics, so governance-throughput must be read through G4 readiness/governance artifacts.
- Search-recall/freshness has richer artifacts than the health deltas; G8 must read those artifacts directly to avoid search-control laundering.
- G6 numeric demand readings can encode abstention inertia (`1.0` blocker/abstention, `0.0` grounded result), so numeric values must not default to `pass`.
- Current G7 has engineering readiness but zero grounded regional breadth; G8 must not convert that into domain ceiling or S14 breadth.
- G5/G6/G7 correctly deny downstream authority, including G8 authority in G7 denied uses; G8 must preserve that boundary.

Target correct pattern:

- Governed signals with explicit raw source refs, alias resolution, freshness, authority boundaries, metric trends, warnings, cross-metric diagnosis, anti-gaming checks, D4.4 coverage/triggers/re-basing receipts, closeout consumer visibility, and readiness/drift gates.

Acceptance signal:

- `uv run python tools/quality/validation/check_policy_design_case_layer3_g8_readiness.py --repo-root . --write --output-format json` writes all G8 artifacts.
- Running the same command without `--write` returns `status == "pass"` and `g8_manifest_runtime_drift_key_count == 0`.
- Current G8 summary says metric governance and trend reporting are `pass`, D4.4 coverage is `pass`, D4.4 trigger status is `pass_no_rebase_due`, D4.4 re-basing receipt is `pass_no_rebase_required`, closeout consumer status is `pass`, and domain ceiling is `not_claimed_current_grounding_blocker`.

## File Structure

Create:

- `src/polisyos/runtime/quality/layer3_health_metric_governance.py`
  G8 constants, strict models, readers, normalization, trend reporting, diagnosis, warning lifecycle, metric-gaming firewall, D4.4 coverage/trigger/re-basing builders, audit surface, closeout consumer gate, public projection refs, conformance helpers.

- `tools/quality/validation/check_policy_design_case_layer3_g8_readiness.py`
  G8 bundle builder/writer/checker, exact artifact set, manifest drift detection, registration/docs validation, CLI.

- `tests/unit/runtime/quality/test_layer3_g8_health_metric_governance.py`
  Unit and semantic tests for G8 producer logic.

- `tests/repo_quality/tools/test_policy_design_case_layer3_g8_readiness.py`
  Readiness, write-mode, artifact registration, drift, and conformance tests.

- `tests/repo_quality/tools/test_policy_design_case_layer3_g8_readiness_cli.py`
  CLI smoke tests for issue-code JSON output, exit codes, `--write`, and exact artifact path reporting.

- `policy-engine/docs/plans/active/layer3-slices/G8-health-metric-governance-and-corpus-rebasing.md`
  This plan.

Modify:

- `architecture/generated_artifacts.toml`
- `architecture/policy_design_case/inventory.json`
- `docs/reference/generated-artifacts.md`
- `docs/reference/public-surface.md`
- `docs/reference/documentation-inventory.md`
- `docs/reference/index.md`
- `src/polisyos/runtime/quality/README.md`

Do not modify:

- `tools/quality/validation/run_layer2_s14_universality_battery.py` unless a test proves G8 needs a new optional diagnostic field. The expected path is to read S14/G7 artifacts and keep the runner behavior unchanged.
- hidden S14 fixture payloads under `tests/fixtures/policy_design_case/semantic_evaluation_packs/hidden/`.
- previous G1-G7 artifacts except by re-running their own validators when a failing test proves a committed artifact is stale.

## Canonical Constants

Use these exact constants:

```python
G8_SCHEMA_VERSION = "policyos.policy_design_case.layer3_g8_health_metric_governance.v1"
G8_RULE_VERSION = "policyos.layer3.g8.health_metric_governance.v1"
G8_SURFACE_ID = "layer3_g8_health_metric_governance_surface"
G8_GENERATED_ARTIFACT_FAMILY_ID = (
    "policy-design-case-layer3-g8-health-metric-governance-artifacts"
)
G8_AUTHORITATIVE_FOR = (
    "layer3_g8_metric_governance_audit",
    "layer3_g8_d44_rebasing_integrity_reading",
    "layer3_g8_open_question_answer_reading",
)
G8_MAY_NOT_USE_FOR = (
    "production_authority",
    "production_claim_authority",
    "rollout_authority",
    "publication_authority",
    "approval_authority",
    "scorecard_authority",
    "closeout_authority",
    "runtime_closeout_authority",
    "public_recommendation",
    "policy_recommendation",
    "legal_advice",
    "claim_authority",
    "obligation_authority",
    "causal_effect_authority",
    "proof_authority",
    "legal_authority",
    "recommendation_authority",
    "universal_claim_authority",
    "universal_claim_authority_without_s14",
    "s14_universality_claim_without_s14_gate",
    "domain_ceiling_authority_without_gate",
    "metric_optimization_authority",
    "useful_design_rate_optimization",
    "threshold_lowering",
    "s14_battery_training",
    "hidden_fixture_access",
    "g7_region_widening_authority",
)
```

Canonical metric ids:

```python
G8_CANONICAL_METRIC_IDS = (
    "envelope-expansion-rate",
    "adapter-semantic-loss",
    "governance-throughput",
    "demand-pull-vs-abstention",
    "search-recall@known-seeds+index-staleness",
)
```

Alias map:

```python
G8_METRIC_ALIASES = {
    "envelope-expansion-rate": "envelope-expansion-rate",
    "envelope-expansion-rate(region)": "envelope-expansion-rate",
    "envelope_expansion_rate_region": "envelope-expansion-rate",
    "g5_envelope_expansion_status": "envelope-expansion-rate",
    "g7_region_envelope_expansion_rate": "envelope-expansion-rate",
    "adapter-semantic-loss": "adapter-semantic-loss",
    "adapter-semantic-loss(region)": "adapter-semantic-loss",
    "semantic_loss_status": "adapter-semantic-loss",
    "g7_region_semantic_loss_status": "adapter-semantic-loss",
    "governance-throughput": "governance-throughput",
    "governance-throughput(region)": "governance-throughput",
    "g4_governance_throughput_status": "governance-throughput",
    "g4-promotion-attempts": "governance-throughput",
    "g4-governed-promoted-count": "governance-throughput",
    "g4-promotion-blocked-count": "governance-throughput",
    "g4-promotion-stalled-count": "governance-throughput",
    "g4-human-decision-routed-count": "governance-throughput",
    "g4-hard-a-incompleteness-block-count": "governance-throughput",
    "g4-search-health-stall-count": "governance-throughput",
    "g4-stale-index-stall-count": "governance-throughput",
    "g4-legal-reissue-stall-count": "governance-throughput",
    "g4-human-decision-stall-count": "governance-throughput",
    "g7_governance_throughput_status": "governance-throughput",
    "demand-pull-vs-abstention": "demand-pull-vs-abstention",
    "demand-pull-vs-abstention(region)": "demand-pull-vs-abstention",
    "abstention_or_blocker_rate": "demand-pull-vs-abstention",
    "grounded_result_rate": "demand-pull-vs-abstention",
    "out_of_envelope_abstention_rate": "demand-pull-vs-abstention",
    "g6_demand_pull_vs_abstention_status": "demand-pull-vs-abstention",
    "g7_region_value_closure_status": "demand-pull-vs-abstention",
    "g7_region_grounded_case_count": "demand-pull-vs-abstention",
    "g7_s14_grounded_breadth_feed_status": "demand-pull-vs-abstention",
    "search-recall@known-seeds+index-staleness": "search-recall@known-seeds+index-staleness",
    "search-recall@known-seeds + index-staleness": "search-recall@known-seeds+index-staleness",
    "search-recall@known-seeds+index-staleness(region)": "search-recall@known-seeds+index-staleness",
    "search-recall.index_freshness_status": "search-recall@known-seeds+index-staleness",
    "search-recall.known_seed_status": "search-recall@known-seeds+index-staleness",
    "search_recall.status": "search-recall@known-seeds+index-staleness",
    "search_recall.freshness_status": "search-recall@known-seeds+index-staleness",
    "search_recall.certificate_resolution_seed_status": "search-recall@known-seeds+index-staleness",
    "search_recall.ir_catalog_seed_status": "search-recall@known-seeds+index-staleness",
    "search_recall.l2_skg_seed_status": "search-recall@known-seeds+index-staleness",
    "search_recall.known_seed_count": "search-recall@known-seeds+index-staleness",
    "search_recall.recalled_seed_count": "search-recall@known-seeds+index-staleness",
    "search_recall.missed_seed_count": "search-recall@known-seeds+index-staleness",
    "search_recall.search_ceiling_repair_required": "search-recall@known-seeds+index-staleness",
    "search_recall.domain_ceiling_allowed": "search-recall@known-seeds+index-staleness",
    "search_recall_status": "search-recall@known-seeds+index-staleness",
    "index_freshness_status": "search-recall@known-seeds+index-staleness",
    "known_seed_status": "search-recall@known-seeds+index-staleness",
    "g2_search_engineering_quality_status": "search-recall@known-seeds+index-staleness",
    "g3_search_recall_freshness_status": "search-recall@known-seeds+index-staleness",
    "gl_search_recall_freshness_status": "search-recall@known-seeds+index-staleness",
    "g1_search_recall_status": "search-recall@known-seeds+index-staleness",
    "g1_index_freshness_status": "search-recall@known-seeds+index-staleness",
    "g5_search_recall_status": "search-recall@known-seeds+index-staleness",
    "g5_index_freshness_status": "search-recall@known-seeds+index-staleness",
}
```

Issue dictionary:

```python
ALL_ISSUE_CODES = (
    "layer3_g8_health_metric_registry_missing",
    "layer3_g8_metric_alias_unresolved",
    "layer3_g8_metric_source_missing",
    "layer3_g8_metric_source_stale",
    "layer3_g8_metric_raw_ref_missing",
    "layer3_g8_metric_authority_boundary_missing",
    "layer3_g8_metric_used_as_closeout_authority",
    "layer3_g8_useful_design_rate_optimized",
    "layer3_g8_metric_improved_by_threshold_lowering",
    "layer3_g8_metric_improved_by_fixture_or_synthetic_breadth",
    "layer3_g8_flat_expansion_reported_as_domain_ceiling_without_search_health",
    "layer3_g8_search_recall_miss_reported_as_domain_ceiling",
    "layer3_g8_governance_stall_hidden_as_domain_ceiling",
    "layer3_g8_abstention_inertia_hidden_as_honesty",
    "layer3_g8_demand_numeric_inertia_hidden_as_pass",
    "layer3_g8_semantic_loss_hidden_by_metric_rollup",
    "layer3_g8_effective_independence_inflated",
    "layer3_g8_metric_trend_report_missing",
    "layer3_g8_warning_owner_missing",
    "layer3_g8_warning_aging_policy_missing",
    "layer3_g8_rebasing_rule_missing",
    "layer3_g8_d44_reannotation_coverage_missing",
    "layer3_g8_d44_rebasing_trigger_missing",
    "layer3_g8_rebasing_receipt_missing",
    "layer3_g8_rebasing_mutates_sealed_battery",
    "layer3_g8_rebasing_leaks_gold_or_hidden_payload",
    "layer3_g8_rebasing_lowers_s14_floor",
    "layer3_g8_rebasing_without_freeze_hash",
    "layer3_g8_open_question_answer_missing",
    "layer3_g8_closeout_signal_consumer_missing",
    "layer3_g8_public_projection_authority_leak",
    "layer3_g8_replay_manifest_missing",
    "layer3_g8_conformance_negative_missing",
    "layer3_g8_manifest_runtime_drift",
    "layer3_g8_generated_artifacts_family_missing",
    "layer3_g8_inventory_surface_missing",
    "layer3_g8_reference_docs_missing",
    "layer3_g8_route_contract_registry_missing",
    "layer3_g8_registry_ratchet_missing",
    "layer3_g8_persisted_artifact_missing",
)
```

Expected artifact paths:

```python
EXPECTED_ARTIFACT_PATHS = (
    Path("architecture/policy_design_case/layer3_g8_health_metric_registry.json"),
    Path("architecture/policy_design_case/layer3_g8_metric_source_snapshot.json"),
    Path("architecture/policy_design_case/layer3_g8_normalized_metric_signals.json"),
    Path("architecture/policy_design_case/layer3_g8_metric_trend_report.json"),
    Path("architecture/policy_design_case/layer3_g8_cross_metric_diagnosis.json"),
    Path("architecture/policy_design_case/layer3_g8_domain_vs_search_ceiling_gate.json"),
    Path("architecture/policy_design_case/layer3_g8_metric_gaming_firewall.json"),
    Path("architecture/policy_design_case/layer3_g8_warning_lifecycle_ledger.json"),
    Path("architecture/policy_design_case/layer3_g8_d44_corpus_rebasing_rule.json"),
    Path("architecture/policy_design_case/layer3_g8_d44_reannotation_coverage_matrix.json"),
    Path("architecture/policy_design_case/layer3_g8_d44_rebasing_trigger_ledger.json"),
    Path("architecture/policy_design_case/layer3_g8_d44_rebasing_candidate_set.json"),
    Path("architecture/policy_design_case/layer3_g8_d44_rebasing_receipt.json"),
    Path("architecture/policy_design_case/layer3_g8_sealed_battery_integrity_join.json"),
    Path("architecture/policy_design_case/layer3_g8_open_question_answer_ledger.json"),
    Path("architecture/policy_design_case/layer3_g8_metric_governance_audit_surface.json"),
    Path("architecture/policy_design_case/layer3_g8_closeout_signal_consumer_gate.json"),
    Path("architecture/policy_design_case/layer3_g8_public_export_projection_refs.json"),
    Path("architecture/policy_design_case/layer3_g8_replay_manifest.json"),
    Path("architecture/policy_design_case/layer3_g8_conformance_report.json"),
    Path("architecture/policy_design_case/layer3_g8_health_metric_governance_delta.toml"),
    Path("architecture/policy_design_case/layer3_g8_metric_governance_route_contract_registry.toml"),
    Path("architecture/policy_design_case/layer3_g8_registry_ratchet_delta.json"),
    Path("architecture/policy_design_case/layer3_g8_readiness_manifest.json"),
)
```

Expected manifest drift keys:

```python
EXPECTED_MANIFEST_DRIFT_KEYS = (
    "g8_metric_governance_status",
    "g8_canonical_metric_count",
    "g8_metric_alias_resolution_status",
    "g8_metric_source_snapshot_status",
    "g8_metric_source_count",
    "g8_normalized_metric_signal_status",
    "g8_metric_trend_report_status",
    "g8_effective_independence_status",
    "g8_effective_independent_evidence_count",
    "g8_domain_vs_search_ceiling_status",
    "g8_metric_gaming_firewall_status",
    "g8_warning_lifecycle_status",
    "g8_d44_rebasing_rule_status",
    "g8_d44_reannotation_coverage_status",
    "g8_d44_rebasing_trigger_status",
    "g8_d44_rebasing_receipt_status",
    "g8_sealed_battery_integrity_status",
    "g8_open_question_answer_status",
    "g8_expert_machine_surface_status",
    "g8_closeout_signal_consumer_status",
    "g8_public_projection_contract_status",
    "g8_replay_manifest_status",
    "g8_conformance_status",
    "g8_generated_artifacts_registration_status",
    "g8_inventory_surface_status",
    "g8_reference_docs_status",
    "g8_route_contract_registry_status",
    "g8_registry_ratchet_status",
)
```

## D4.4 Re-Basing Rule Fields

The D4.4 rule must include these re-annotation field ids. G8 may mark each field as `required_for_next_rebase` or `satisfied_by_existing_s14_record`; it must not silently drop a field.

```python
D44_REQUIRED_REANNOTATION_FIELDS = (
    "problem_framing_independent_of_existing_policy",
    "axis_position_vector",
    "per_axis_firewall_status",
    "claim_epistemic_regime_labels",
    "regime_conditional_design_strategy",
    "scale_class",
    "recursive_sub_design_graph",
    "coupling_graph",
    "decomposition_result",
    "interaction_residual_annotations",
    "expert_candidate_designs",
    "rejected_alternatives",
    "critical_path_annotations",
    "dependency_annotations",
    "system_dynamics_feedback_equilibrium_obligations",
    "expected_evidence_tier",
    "construct_demand_denominator",
    "available_source_contracts",
    "unavailable_source_contracts",
    "expected_graded_outcome_by_authority_posture",
    "certified_operation_envelope_status",
    "expected_abstention_limitation_boundary",
    "expected_counterexample_class",
    "valid_refinement_decision",
    "search_ledger_replay_surface",
    "human_decision_points",
    "accountable_actor",
    "mandate_boundary",
    "responsibility_integrity_requirements",
    "canonical_design_record_contents",
    "projection_requests",
    "redaction_access_posture",
    "lowering_requests_with_authority_gates",
    "bootstrap_role",
    "reuse_vs_bespoke_signal",
    "resource_economics_annotation",
    "universality_battery_metadata",
    "post_deploy_monitoring_hooks",
    "historical_outcomes_prediction_backtest_usability",
    "realized_regret_observability",
    "reviewer_disagreement",
    "value_choice_provenance",
)
```

## Task 1: Red Baseline Constants and Strict Models

**Files:**

- Create: `src/polisyos/runtime/quality/layer3_health_metric_governance.py`
- Test: `tests/unit/runtime/quality/test_layer3_g8_health_metric_governance.py`
- Test: `tests/repo_quality/tools/test_policy_design_case_layer3_g8_readiness.py`

- [ ] **Step 1: Write the failing unit test**

Add this to `tests/unit/runtime/quality/test_layer3_g8_health_metric_governance.py`:

```python
from __future__ import annotations

import pytest
from pydantic import ValidationError

import polisyos.runtime.quality.layer3_health_metric_governance as g8


def test_g8_declares_red_baseline_contract() -> None:
    assert g8.G8_SCHEMA_VERSION == (
        "policyos.policy_design_case.layer3_g8_health_metric_governance.v1"
    )
    assert g8.G8_RULE_VERSION == "policyos.layer3.g8.health_metric_governance.v1"
    assert g8.G8_SURFACE_ID == "layer3_g8_health_metric_governance_surface"
    assert g8.G8_GENERATED_ARTIFACT_FAMILY_ID == (
        "policy-design-case-layer3-g8-health-metric-governance-artifacts"
    )
    assert set(g8.G8_CANONICAL_METRIC_IDS) == {
        "envelope-expansion-rate",
        "adapter-semantic-loss",
        "governance-throughput",
        "demand-pull-vs-abstention",
        "search-recall@known-seeds+index-staleness",
    }
    assert "useful_design_rate_optimization" in g8.G8_MAY_NOT_USE_FOR
    assert "hidden_fixture_access" in g8.G8_MAY_NOT_USE_FOR
    assert "layer3_g8_metric_improved_by_threshold_lowering" in g8.ALL_ISSUE_CODES
    assert "layer3_g8_search_recall_miss_reported_as_domain_ceiling" in g8.ALL_ISSUE_CODES


def test_g8_models_are_strict_and_frozen() -> None:
    row = g8.Layer3G8Issue(
        issue_code="layer3_g8_metric_source_missing",
        ref="repo://missing",
        message="Metric source is missing.",
    )
    assert row.issue_code == "layer3_g8_metric_source_missing"
    with pytest.raises(ValidationError):
        g8.Layer3G8Issue(
            issue_code="layer3_g8_metric_source_missing",
            ref="repo://missing",
            message="Metric source is missing.",
            surprise=True,
        )
    with pytest.raises(ValidationError):
        row.ref = "repo://mutated"
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
cd policy-engine
uv run pytest tests/unit/runtime/quality/test_layer3_g8_health_metric_governance.py::test_g8_declares_red_baseline_contract -q
```

Expected: fail with `ModuleNotFoundError: No module named 'polisyos.runtime.quality.layer3_health_metric_governance'`.

- [ ] **Step 3: Add the minimal module baseline**

Create `src/polisyos/runtime/quality/layer3_health_metric_governance.py` with the constants from the "Canonical Constants" section plus this strict base:

```python
"""Layer 3 G8 health-metric governance and corpus re-basing contracts.

G8 governs diagnostic metric signals and D4.4 re-basing receipts. It never
mints production, recommendation, closeout, publication, scorecard, legal, or
universal-claim authority.
"""

from __future__ import annotations

import hashlib
import json
import tomllib
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[4]
POLICY_DESIGN_CASE_DIR = Path("architecture/policy_design_case")


class _G8Model(BaseModel):
    """Strict immutable model base for committed G8 artifacts."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class Layer3G8Issue(_G8Model):
    """Typed issue emitted by G8 validators and conformance checks."""

    issue_code: str
    ref: str
    message: str


def _dedupe(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value) for value in values if str(value)))


def _issue(issue_code: str, ref: str, message: str) -> Layer3G8Issue:
    return Layer3G8Issue(issue_code=issue_code, ref=ref, message=message)


def _text(value: object) -> str:
    return str(value) if value is not None else ""


def _text_list(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,) if value else ()
    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray):
        return tuple(str(item) for item in value if str(item))
    return ()


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return dict(payload) if isinstance(payload, Mapping) else {}


def _read_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        payload = tomllib.load(handle)
    return dict(payload) if isinstance(payload, Mapping) else {}


def _digest_payload(payload: Mapping[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(serialized.encode("utf-8")).hexdigest()
```

Keep `runtime.quality.__init__` unchanged. G8 follows the G0/G5/G6/G7 pattern of canonical module imports without eager package export.

- [ ] **Step 4: Run the baseline test**

Run:

```bash
cd policy-engine
uv run pytest tests/unit/runtime/quality/test_layer3_g8_health_metric_governance.py::test_g8_declares_red_baseline_contract tests/unit/runtime/quality/test_layer3_g8_health_metric_governance.py::test_g8_models_are_strict_and_frozen -q
```

Expected: both tests pass.

- [ ] **Step 5: Commit**

```bash
cd policy-engine
git add src/polisyos/runtime/quality/layer3_health_metric_governance.py tests/unit/runtime/quality/test_layer3_g8_health_metric_governance.py
git commit -m "feat: add layer3 g8 health metric governance baseline"
```

## Task 2: Metric Registry and Alias Normalization

**Files:**

- Modify: `src/polisyos/runtime/quality/layer3_health_metric_governance.py`
- Modify: `tests/unit/runtime/quality/test_layer3_g8_health_metric_governance.py`

- [ ] **Step 1: Write the failing registry tests**

Add:

```python
def test_g8_metric_registry_preserves_g0_ledger_semantics() -> None:
    registry = g8.build_g8_health_metric_registry()

    assert registry.status == "pass"
    assert len(registry.entries) == 5
    by_id = {entry.metric_id: entry for entry in registry.entries}
    assert by_id["envelope-expansion-rate"].owner == "team-runtime-quality"
    assert by_id["governance-throughput"].owner == "principal-governance"
    assert by_id["search-recall@known-seeds+index-staleness"].trend_vocabulary == (
        "fresh_recall_ok",
        "search_ceiling",
    )
    assert by_id["search-recall@known-seeds+index-staleness"].source_ledger_ref == (
        "repo://architecture/policy_design_case/layer3_health_metric_ledgers.toml"
        "#search-recall@known-seeds+index-staleness"
    )


def test_g8_alias_normalization_accepts_existing_g1_to_g7_spellings() -> None:
    assert g8.canonical_metric_id("search-recall@known-seeds + index-staleness") == (
        "search-recall@known-seeds+index-staleness"
    )
    assert g8.canonical_metric_id(
        "search-recall@known-seeds+index-staleness(region)"
    ) == "search-recall@known-seeds+index-staleness"
    assert g8.canonical_metric_id("envelope_expansion_rate_region") == (
        "envelope-expansion-rate"
    )
    assert g8.canonical_metric_id("g4-governed-promoted-count") == (
        "governance-throughput"
    )
    assert g8.canonical_metric_id("abstention_or_blocker_rate") == (
        "demand-pull-vs-abstention"
    )
    assert g8.canonical_metric_id("g7_s14_grounded_breadth_feed_status") == (
        "demand-pull-vs-abstention"
    )
    assert g8.canonical_metric_id("search_recall.freshness_status") == (
        "search-recall@known-seeds+index-staleness"
    )
    assert g8.canonical_metric_id("gl_search_recall_freshness_status") == (
        "search-recall@known-seeds+index-staleness"
    )
    assert g8.canonical_metric_id("unknown-local-metric") is None
```

- [ ] **Step 2: Run the failing tests**

```bash
cd policy-engine
uv run pytest tests/unit/runtime/quality/test_layer3_g8_health_metric_governance.py::test_g8_metric_registry_preserves_g0_ledger_semantics tests/unit/runtime/quality/test_layer3_g8_health_metric_governance.py::test_g8_alias_normalization_accepts_existing_g1_to_g7_spellings -q
```

Expected: fail because `build_g8_health_metric_registry` and `canonical_metric_id` do not exist.

- [ ] **Step 3: Implement registry models and builders**

Add:

```python
MetricRegistryStatus = Literal["pass", "blocked"]


class Layer3G8HealthMetricRegistryEntry(_G8Model):
    metric_id: str
    owner: str
    trend_vocabulary: tuple[str, ...]
    freeze_value: dict[str, Any]
    per_slice_delta_rule: str
    next_update_rule: str
    aliases: tuple[str, ...]
    source_ledger_ref: str
    authoritative_for: tuple[str, ...] = G8_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G8_MAY_NOT_USE_FOR


class Layer3G8HealthMetricRegistry(_G8Model):
    schema_version: str = G8_SCHEMA_VERSION
    rule_version: str = G8_RULE_VERSION
    registry_id: str = "layer3-g8://health-metric-registry"
    status: MetricRegistryStatus
    entries: tuple[Layer3G8HealthMetricRegistryEntry, ...]
    issue_codes: tuple[str, ...] = ()
    authoritative_for: tuple[str, ...] = G8_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G8_MAY_NOT_USE_FOR


_REGISTRY_ROWS: tuple[dict[str, Any], ...] = (
    {
        "metric_id": "envelope-expansion-rate",
        "owner": "team-runtime-quality",
        "trend_vocabulary": ("expanding", "flat", "shrinking"),
        "freeze_value": {"g0_admitted_adapter_count": 0},
        "per_slice_delta_rule": "Later slices may change only after admitted adapter evidence.",
        "next_update_rule": "Recompute when a G1+ adapter slice writes governed artifacts.",
    },
    {
        "metric_id": "adapter-semantic-loss",
        "owner": "team-runtime-quality",
        "trend_vocabulary": ("clean", "lossy"),
        "freeze_value": {"semantic_loss_events": 0},
        "per_slice_delta_rule": "Any AdapterLossBlocker event increments lossy evidence.",
        "next_update_rule": "Recompute from conformance harness outputs.",
    },
    {
        "metric_id": "governance-throughput",
        "owner": "principal-governance",
        "trend_vocabulary": ("flowing", "stalled"),
        "freeze_value": {"accepted_adr_count": 0, "open_human_gate_count": 1},
        "per_slice_delta_rule": "Human acceptance gates move throughput only with acceptance refs.",
        "next_update_rule": "Recompute at ADR-0175 acceptance.",
    },
    {
        "metric_id": "demand-pull-vs-abstention",
        "owner": "team-runtime-quality",
        "trend_vocabulary": ("responding", "abstention_inertia"),
        "freeze_value": {"grounded_conversion_count": 0},
        "per_slice_delta_rule": "Demand pull cannot count until a grounded adapter admits evidence.",
        "next_update_rule": "Recompute from universal corpus G0 route.",
    },
    {
        "metric_id": "search-recall@known-seeds+index-staleness",
        "owner": "team-runtime-quality",
        "trend_vocabulary": ("fresh_recall_ok", "search_ceiling"),
        "freeze_value": {
            "known_groundable_seed_miss_count": 0,
            "stale_required_index_count": 0,
        },
        "per_slice_delta_rule": (
            "Recall misses or stale required indexes block domain-ceiling and no-hit claims."
        ),
        "next_update_rule": (
            "Recompute from GroundingSearchDiscipline recall/freshness records."
        ),
    },
)


def canonical_metric_id(metric_id: str) -> str | None:
    return G8_METRIC_ALIASES.get(str(metric_id))


def _aliases_for(metric_id: str) -> tuple[str, ...]:
    return tuple(alias for alias, canonical in G8_METRIC_ALIASES.items() if canonical == metric_id)


def build_g8_health_metric_registry() -> Layer3G8HealthMetricRegistry:
    entries = tuple(
        Layer3G8HealthMetricRegistryEntry(
            **row,
            aliases=_aliases_for(str(row["metric_id"])),
            source_ledger_ref=(
                "repo://architecture/policy_design_case/layer3_health_metric_ledgers.toml"
                f"#{row['metric_id']}"
            ),
        )
        for row in _REGISTRY_ROWS
    )
    issue_codes: list[str] = []
    if {entry.metric_id for entry in entries} != set(G8_CANONICAL_METRIC_IDS):
        issue_codes.append("layer3_g8_health_metric_registry_missing")
    return Layer3G8HealthMetricRegistry(
        status="blocked" if issue_codes else "pass",
        entries=entries,
        issue_codes=_dedupe(issue_codes),
    )
```

- [ ] **Step 4: Run registry tests**

```bash
cd policy-engine
uv run pytest tests/unit/runtime/quality/test_layer3_g8_health_metric_governance.py::test_g8_metric_registry_preserves_g0_ledger_semantics tests/unit/runtime/quality/test_layer3_g8_health_metric_governance.py::test_g8_alias_normalization_accepts_existing_g1_to_g7_spellings -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
cd policy-engine
git add src/polisyos/runtime/quality/layer3_health_metric_governance.py tests/unit/runtime/quality/test_layer3_g8_health_metric_governance.py
git commit -m "feat: govern layer3 health metric registry"
```

## Task 3: Source Snapshot and Normalized Metric Signals

**Files:**

- Modify: `src/polisyos/runtime/quality/layer3_health_metric_governance.py`
- Modify: `tests/unit/runtime/quality/test_layer3_g8_health_metric_governance.py`

- [ ] **Step 1: Write the failing source, normalization, and trend tests**

Add:

```python
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]


def test_g8_source_snapshot_reads_current_g0_to_g7_and_s14_artifacts() -> None:
    snapshot = g8.build_g8_metric_source_snapshot(REPO_ROOT)

    assert snapshot.status == "pass"
    assert snapshot.source_count >= 44
    refs = {source.source_ref for source in snapshot.sources}
    assert "repo://architecture/policy_design_case/layer3_health_metric_ledgers.toml" in refs
    assert "repo://architecture/policy_design_case/layer3_g1_search_recall_freshness.json" in refs
    assert "repo://architecture/policy_design_case/layer3_g4_governance_throughput_delta.json" in refs
    assert "repo://architecture/policy_design_case/layer3_g5_health_metric_delta.toml" in refs
    assert "repo://architecture/policy_design_case/layer3_g5_dependency_health_metric_snapshot.json" in refs
    assert "repo://architecture/policy_design_case/layer3_g5_effective_evidence_independence.json" in refs
    assert "repo://architecture/policy_design_case/layer3_g5_useful_design_metric_eligibility_join.json" in refs
    assert "repo://architecture/policy_design_case/layer3_g6_demand_pull_vs_abstention_delta.json" in refs
    assert "repo://architecture/policy_design_case/layer3_g6_conformance_report.json" in refs
    assert "repo://architecture/policy_design_case/layer3_g6_orchestration_choice_audit.json" in refs
    assert "repo://architecture/policy_design_case/layer3_g7_search_recall_freshness_join.json" in refs
    assert "repo://architecture/policy_design_case/layer3_g7_health_metric_delta.toml" in refs
    assert "repo://architecture/policy_design_case/layer3_g7_g5_g6_authority_boundary_report.json" in refs
    assert "repo://architecture/policy_design_case/layer3_g7_region_widening_audit_surface.json" in refs
    assert "repo://architecture/policy_design_case/layer2_s14_universality_assurance_manifest.json" in refs


def test_g8_normalizes_current_metric_dialects_without_losing_raw_refs() -> None:
    registry = g8.build_g8_health_metric_registry()
    snapshot = g8.build_g8_metric_source_snapshot(REPO_ROOT)
    signals = g8.build_g8_normalized_metric_signals(
        registry=registry,
        source_snapshot=snapshot,
    )

    assert signals.status == "pass"
    by_metric = {metric_id: [] for metric_id in g8.G8_CANONICAL_METRIC_IDS}
    for signal in signals.signals:
        by_metric[signal.metric_id].append(signal)
        assert signal.raw_source_ref.startswith("repo://architecture/policy_design_case/")
        assert signal.authoritative_for == g8.G8_AUTHORITATIVE_FOR
        assert "closeout_authority" in signal.may_not_use_for

    assert all(by_metric.values())
    search_refs = {signal.raw_key for signal in by_metric["search-recall@known-seeds+index-staleness"]}
    assert "search-recall@known-seeds + index-staleness" in search_refs
    assert "search-recall@known-seeds+index-staleness(region)" in search_refs
    demand_readings = by_metric["demand-pull-vs-abstention"]
    assert any(signal.raw_key == "abstention_or_blocker_rate" for signal in demand_readings)
    assert any(
        signal.slice_id == "G6"
        and signal.raw_key == "abstention_or_blocker_rate"
        and signal.status == "abstention_inertia"
        for signal in demand_readings
    )
    assert any(
        signal.slice_id == "G6"
        and signal.raw_key == "grounded_result_rate"
        and signal.status == "no_grounded_response"
        for signal in demand_readings
    )
    assert any(
        signal.slice_id == "G3"
        and signal.raw_key == "search_recall.freshness_status"
        and signal.status == "pass"
        for signal in by_metric["search-recall@known-seeds+index-staleness"]
    )
    assert any(
        signal.slice_id == "GL"
        and signal.raw_key == "known_seed_status"
        and signal.status == "pass"
        for signal in by_metric["search-recall@known-seeds+index-staleness"]
    )
    assert any(
        signal.slice_id == "G7"
        and signal.raw_key == "g7_s14_grounded_breadth_feed_status"
        and signal.status == "blocked_no_real_grounded_breadth"
        for signal in demand_readings
    )


def test_g8_metric_trend_report_exposes_all_five_ci_visible_metrics() -> None:
    registry = g8.build_g8_health_metric_registry()
    snapshot = g8.build_g8_metric_source_snapshot(REPO_ROOT)
    signals = g8.build_g8_normalized_metric_signals(
        registry=registry,
        source_snapshot=snapshot,
    )
    report = g8.build_g8_metric_trend_report(registry=registry, signals=signals)

    assert report.status == "pass"
    assert {row.metric_id for row in report.metric_trends} == set(g8.G8_CANONICAL_METRIC_IDS)
    by_metric = {row.metric_id: row for row in report.metric_trends}
    assert by_metric["demand-pull-vs-abstention"].latest_status in {
        "abstention_inertia",
        "blocked_by_current_g5_unchanged_blocker",
        "blocked_no_real_grounded_breadth",
        "no_grounded_response",
        "pass",
    }
    assert by_metric["search-recall@known-seeds+index-staleness"].source_refs
    assert report.ci_report_status == "first_class_metric_trends_visible"
```

- [ ] **Step 2: Run the failing tests**

```bash
cd policy-engine
uv run pytest tests/unit/runtime/quality/test_layer3_g8_health_metric_governance.py::test_g8_source_snapshot_reads_current_g0_to_g7_and_s14_artifacts tests/unit/runtime/quality/test_layer3_g8_health_metric_governance.py::test_g8_normalizes_current_metric_dialects_without_losing_raw_refs tests/unit/runtime/quality/test_layer3_g8_health_metric_governance.py::test_g8_metric_trend_report_exposes_all_five_ci_visible_metrics -q
```

Expected: fail because source snapshot, normalized signal, and metric trend builders do not exist.

- [ ] **Step 3: Implement source refs, snapshot, normalized signals, and metric trends**

Add:

```python
class Layer3G8MetricSourceRef(_G8Model):
    slice_id: str
    path: str
    source_ref: str
    format: Literal["json", "toml"]
    status: Literal["present", "missing", "unreadable"]
    digest: str = ""
    schema_version: str = ""
    rule_version: str = ""
    generated_at: str = ""
    issue_codes: tuple[str, ...] = ()


class Layer3G8MetricSourceSnapshot(_G8Model):
    schema_version: str = G8_SCHEMA_VERSION
    rule_version: str = G8_RULE_VERSION
    snapshot_id: str = "layer3-g8://metric-source-snapshot"
    status: Literal["pass", "blocked"]
    sources: tuple[Layer3G8MetricSourceRef, ...]
    source_count: int
    issue_codes: tuple[str, ...] = ()
    authoritative_for: tuple[str, ...] = G8_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G8_MAY_NOT_USE_FOR


class Layer3G8NormalizedMetricSignal(_G8Model):
    signal_id: str
    slice_id: str
    metric_id: str
    raw_key: str
    raw_value: Any
    status: str
    raw_source_ref: str
    source_digest: str
    freshness_status: Literal["fresh_committed", "missing", "unknown_time"]
    authority_boundary_status: Literal["pass", "missing"]
    observed_at: str
    issue_codes: tuple[str, ...] = ()
    authoritative_for: tuple[str, ...] = G8_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G8_MAY_NOT_USE_FOR


class Layer3G8NormalizedMetricSignals(_G8Model):
    schema_version: str = G8_SCHEMA_VERSION
    rule_version: str = G8_RULE_VERSION
    signal_set_id: str = "layer3-g8://normalized-metric-signals"
    status: Literal["pass", "blocked"]
    signals: tuple[Layer3G8NormalizedMetricSignal, ...]
    issue_codes: tuple[str, ...] = ()
    authoritative_for: tuple[str, ...] = G8_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G8_MAY_NOT_USE_FOR


class Layer3G8MetricTrendRow(_G8Model):
    metric_id: str
    latest_status: str
    signal_count: int
    source_refs: tuple[str, ...]
    trend_vocabulary: tuple[str, ...]
    trend_status: Literal["reported", "missing"]


class Layer3G8MetricTrendReport(_G8Model):
    schema_version: str = G8_SCHEMA_VERSION
    rule_version: str = G8_RULE_VERSION
    report_id: str = "layer3-g8://metric-trend-report"
    status: Literal["pass", "blocked"]
    ci_report_status: Literal["first_class_metric_trends_visible", "blocked"]
    metric_trends: tuple[Layer3G8MetricTrendRow, ...]
    issue_codes: tuple[str, ...] = ()
    authoritative_for: tuple[str, ...] = G8_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G8_MAY_NOT_USE_FOR


_G8_SOURCE_PATHS: tuple[tuple[str, Path, str], ...] = (
    ("G0", POLICY_DESIGN_CASE_DIR / "layer3_health_metric_ledgers.toml", "toml"),
    ("G1", POLICY_DESIGN_CASE_DIR / "layer3_g1_health_metric_delta.toml", "toml"),
    ("G1", POLICY_DESIGN_CASE_DIR / "layer3_g1_search_recall_freshness.json", "json"),
    ("G1", POLICY_DESIGN_CASE_DIR / "layer3_g1_readiness_manifest.json", "json"),
    ("G2", POLICY_DESIGN_CASE_DIR / "layer3_g2_health_metric_delta.toml", "toml"),
    ("G2", POLICY_DESIGN_CASE_DIR / "layer3_g2_search_recall_freshness.json", "json"),
    ("G2", POLICY_DESIGN_CASE_DIR / "layer3_g2_readiness_manifest.json", "json"),
    ("G3", POLICY_DESIGN_CASE_DIR / "layer3_g3_health_metric_delta.toml", "toml"),
    ("G3", POLICY_DESIGN_CASE_DIR / "layer3_g3_search_recall_freshness.json", "json"),
    ("G3", POLICY_DESIGN_CASE_DIR / "layer3_g3_readiness_manifest.json", "json"),
    ("GL", POLICY_DESIGN_CASE_DIR / "layer3_gl_health_metric_delta.toml", "toml"),
    ("GL", POLICY_DESIGN_CASE_DIR / "layer3_gl_search_recall_freshness.json", "json"),
    ("GL", POLICY_DESIGN_CASE_DIR / "layer3_gl_readiness_manifest.json", "json"),
    ("G4", POLICY_DESIGN_CASE_DIR / "layer3_g4_health_metric_delta.toml", "toml"),
    ("G4", POLICY_DESIGN_CASE_DIR / "layer3_g4_governance_throughput_delta.json", "json"),
    ("G4", POLICY_DESIGN_CASE_DIR / "layer3_g4_readiness_manifest.json", "json"),
    ("G5", POLICY_DESIGN_CASE_DIR / "layer3_g5_health_metric_delta.toml", "toml"),
    ("G5", POLICY_DESIGN_CASE_DIR / "layer3_g5_dependency_health_metric_snapshot.json", "json"),
    ("G5", POLICY_DESIGN_CASE_DIR / "layer3_g5_grounded_result_evidence_set.json", "json"),
    ("G5", POLICY_DESIGN_CASE_DIR / "layer3_g5_effective_evidence_independence.json", "json"),
    ("G5", POLICY_DESIGN_CASE_DIR / "layer3_g5_grounded_abstention_quality_record.json", "json"),
    ("G5", POLICY_DESIGN_CASE_DIR / "layer3_g5_useful_design_metric_eligibility_join.json", "json"),
    ("G5", POLICY_DESIGN_CASE_DIR / "layer3_g5_demand_pull_attempt_record.json", "json"),
    ("G5", POLICY_DESIGN_CASE_DIR / "layer3_g5_readiness_manifest.json", "json"),
    ("G6", POLICY_DESIGN_CASE_DIR / "layer3_g6_health_metric_delta.toml", "toml"),
    ("G6", POLICY_DESIGN_CASE_DIR / "layer3_g6_demand_pull_vs_abstention_delta.json", "json"),
    ("G6", POLICY_DESIGN_CASE_DIR / "layer3_g6_grounding_demand_record.json", "json"),
    ("G6", POLICY_DESIGN_CASE_DIR / "layer3_g6_search_ledger.json", "json"),
    ("G6", POLICY_DESIGN_CASE_DIR / "layer3_g6_orchestration_choice_audit.json", "json"),
    ("G6", POLICY_DESIGN_CASE_DIR / "layer3_g6_candidate_authority_firewall_report.json", "json"),
    ("G6", POLICY_DESIGN_CASE_DIR / "layer3_g6_conformance_report.json", "json"),
    ("G6", POLICY_DESIGN_CASE_DIR / "layer3_g6_readiness_manifest.json", "json"),
    ("G7", POLICY_DESIGN_CASE_DIR / "layer3_g7_health_metric_delta.toml", "toml"),
    ("G7", POLICY_DESIGN_CASE_DIR / "layer3_g7_dependency_readiness_snapshot.json", "json"),
    ("G7", POLICY_DESIGN_CASE_DIR / "layer3_g7_search_recall_freshness_join.json", "json"),
    ("G7", POLICY_DESIGN_CASE_DIR / "layer3_g7_region_conversion_status_matrix.json", "json"),
    ("G7", POLICY_DESIGN_CASE_DIR / "layer3_g7_g5_g6_authority_boundary_report.json", "json"),
    ("G7", POLICY_DESIGN_CASE_DIR / "layer3_g7_s14_grounded_breadth_feed.json", "json"),
    ("G7", POLICY_DESIGN_CASE_DIR / "layer3_g7_region_scorecard.json", "json"),
    ("G7", POLICY_DESIGN_CASE_DIR / "layer3_g7_region_widening_audit_surface.json", "json"),
    ("G7", POLICY_DESIGN_CASE_DIR / "layer3_g7_readiness_manifest.json", "json"),
    ("G7", POLICY_DESIGN_CASE_DIR / "layer3_g7_s14_battery_input_manifest.json", "json"),
    ("S14", POLICY_DESIGN_CASE_DIR / "layer2_corpus_partition.json", "json"),
    ("S14", POLICY_DESIGN_CASE_DIR / "layer2_s14_universality_assurance_manifest.json", "json"),
)


def build_g8_metric_source_snapshot(repo_root: str | Path = DEFAULT_REPO_ROOT) -> Layer3G8MetricSourceSnapshot:
    root = Path(repo_root).resolve()
    sources: list[Layer3G8MetricSourceRef] = []
    issues: list[str] = []
    for slice_id, relative_path, source_format in _G8_SOURCE_PATHS:
        path = root / relative_path
        source_ref = f"repo://{relative_path.as_posix()}"
        if not path.exists():
            issues.append("layer3_g8_metric_source_missing")
            sources.append(
                Layer3G8MetricSourceRef(
                    slice_id=slice_id,
                    path=relative_path.as_posix(),
                    source_ref=source_ref,
                    format=source_format,  # type: ignore[arg-type]
                    status="missing",
                    issue_codes=("layer3_g8_metric_source_missing",),
                )
            )
            continue
        try:
            payload = _read_toml(path) if source_format == "toml" else _read_json(path)
        except (OSError, json.JSONDecodeError, tomllib.TOMLDecodeError):
            issues.append("layer3_g8_metric_source_missing")
            sources.append(
                Layer3G8MetricSourceRef(
                    slice_id=slice_id,
                    path=relative_path.as_posix(),
                    source_ref=source_ref,
                    format=source_format,  # type: ignore[arg-type]
                    status="unreadable",
                    issue_codes=("layer3_g8_metric_source_missing",),
                )
            )
            continue
        sources.append(
            Layer3G8MetricSourceRef(
                slice_id=slice_id,
                path=relative_path.as_posix(),
                source_ref=source_ref,
                format=source_format,  # type: ignore[arg-type]
                status="present",
                digest=_digest_payload(payload),
                schema_version=_text(payload.get("schema_version")),
                rule_version=_text(payload.get("rule_version")),
                generated_at=_text(payload.get("generated_at")),
            )
        )
    return Layer3G8MetricSourceSnapshot(
        status="blocked" if issues else "pass",
        sources=tuple(sources),
        source_count=len(sources),
        issue_codes=_dedupe(issues),
    )


def build_g8_normalized_metric_signals(
    *,
    registry: Layer3G8HealthMetricRegistry,
    source_snapshot: Layer3G8MetricSourceSnapshot,
    repo_root: str | Path = DEFAULT_REPO_ROOT,
    observed_at: str = "2026-06-10T00:00:00Z",
) -> Layer3G8NormalizedMetricSignals:
    root = Path(repo_root).resolve()
    registry_ids = {entry.metric_id for entry in registry.entries}
    signals: list[Layer3G8NormalizedMetricSignal] = []
    issues: list[str] = []
    for source in source_snapshot.sources:
        if source.status != "present":
            issues.extend(source.issue_codes)
            continue
        path = root / source.path
        payload = _read_toml(path) if source.format == "toml" else _read_json(path)
        for raw_key, raw_value in _metric_items_from_payload(source.slice_id, payload):
            canonical = canonical_metric_id(raw_key)
            if canonical is None:
                continue
            if canonical not in registry_ids:
                issues.append("layer3_g8_metric_alias_unresolved")
                continue
            status = _status_from_metric_value(raw_key, raw_value)
            signal_issues = _signal_issue_codes(
                metric_id=canonical,
                raw_key=raw_key,
                status=status,
                raw_value=raw_value,
            )
            issues.extend(signal_issues)
            signals.append(
                Layer3G8NormalizedMetricSignal(
                    signal_id=(
                        "layer3-g8://normalized-metric/"
                        f"{source.slice_id.lower()}/{_slug(canonical)}/{_slug(raw_key)}"
                    ),
                    slice_id=source.slice_id,
                    metric_id=canonical,
                    raw_key=raw_key,
                    raw_value=raw_value,
                    status=status,
                    raw_source_ref=f"{source.source_ref}#{raw_key}",
                    source_digest=source.digest,
                    freshness_status="fresh_committed",
                    authority_boundary_status="pass",
                    observed_at=observed_at,
                    issue_codes=signal_issues,
                )
            )
    missing_metrics = set(G8_CANONICAL_METRIC_IDS) - {signal.metric_id for signal in signals}
    if missing_metrics:
        issues.append("layer3_g8_metric_source_missing")
    return Layer3G8NormalizedMetricSignals(
        status="blocked" if _blocking_signal_issues(issues) else "pass",
        signals=tuple(signals),
        issue_codes=_dedupe(issues),
    )


def build_g8_metric_trend_report(
    *,
    registry: Layer3G8HealthMetricRegistry,
    signals: Layer3G8NormalizedMetricSignals,
) -> Layer3G8MetricTrendReport:
    rows: list[Layer3G8MetricTrendRow] = []
    issues: list[str] = []
    registry_by_metric = {entry.metric_id: entry for entry in registry.entries}
    for metric_id in G8_CANONICAL_METRIC_IDS:
        metric_signals = tuple(signal for signal in signals.signals if signal.metric_id == metric_id)
        if not metric_signals:
            issues.append("layer3_g8_metric_trend_report_missing")
            rows.append(
                Layer3G8MetricTrendRow(
                    metric_id=metric_id,
                    latest_status="missing",
                    signal_count=0,
                    source_refs=(),
                    trend_vocabulary=registry_by_metric[metric_id].trend_vocabulary,
                    trend_status="missing",
                )
            )
            continue
        rows.append(
            Layer3G8MetricTrendRow(
                metric_id=metric_id,
                latest_status=_latest_metric_status(signals, metric_id),
                signal_count=len(metric_signals),
                source_refs=_dedupe(signal.raw_source_ref for signal in metric_signals),
                trend_vocabulary=registry_by_metric[metric_id].trend_vocabulary,
                trend_status="reported",
            )
        )
    return Layer3G8MetricTrendReport(
        status="blocked" if issues else "pass",
        ci_report_status="blocked" if issues else "first_class_metric_trends_visible",
        metric_trends=tuple(rows),
        issue_codes=_dedupe(issues),
    )
```

Also add helpers:

```python
def _metric_items_from_payload(slice_id: str, payload: Mapping[str, Any]) -> tuple[tuple[str, Any], ...]:
    items: list[tuple[str, Any]] = []
    health_delta = _mapping(payload.get("health_metric_delta"))
    for key, value in _mapping(health_delta.get("readings")).items():
        items.append((str(key), value))
    for key, value in _mapping(health_delta.get("metric_statuses")).items():
        items.append((str(key), value))
    for key, value in _mapping(payload.get("metrics")).items():
        items.append((str(key), value))

    search_recall = _mapping(payload.get("search_recall_freshness"))
    for key in (
        "status",
        "freshness_status",
        "certificate_resolution_seed_status",
        "ir_catalog_seed_status",
        "l2_skg_seed_status",
        "known_seed_count",
        "recalled_seed_count",
        "missed_seed_count",
        "search_ceiling_repair_required",
        "domain_ceiling_allowed",
    ):
        if key in search_recall:
            items.append((f"search_recall.{key}", search_recall[key]))
    for key in (
        "search_recall_status",
        "index_freshness_status",
        "known_seed_status",
        "g1_search_recall_status",
        "g1_index_freshness_status",
    ):
        if key in search_recall:
            items.append((key, search_recall[key]))
        if key in payload:
            items.append((key, payload[key]))

    for key in (
        "abstention_or_blocker_rate",
        "demand_reached_g5_rate",
        "g5_grounded_abstention_rate",
        "grounded_result_rate",
        "out_of_envelope_abstention_rate",
    ):
        readings = _mapping(payload.get("readings"))
        if key in readings:
            items.append((key, readings[key]))
        if key in payload:
            items.append((key, payload[key]))

    manifest = _manifest_fields(payload)
    for key in (
        "g2_search_engineering_quality_status",
        "g3_search_recall_freshness_status",
        "gl_search_recall_freshness_status",
        "g4_governance_throughput_status",
        "g5_envelope_expansion_status",
        "g5_search_recall_status",
        "g5_index_freshness_status",
        "g5_governance_throughput_status",
        "g6_demand_pull_vs_abstention_status",
        "g7_region_envelope_expansion_rate",
        "g7_region_semantic_loss_status",
        "g7_governance_throughput_status",
        "g7_region_value_closure_status",
        "g7_region_grounded_case_count",
        "g7_s14_grounded_breadth_feed_status",
    ):
        if key in manifest:
            items.append((key, manifest[key]))

    if slice_id == "G4":
        for key in ("status", "stalled_count", "human_review_routed_count"):
            if key in payload:
                items.append(("governance-throughput", payload[key]))
        for key, value in _mapping(payload.get("readings")).items():
            if str(key).startswith("g4-"):
                items.append(("governance-throughput", value))
    return tuple(items)


def _manifest_fields(payload: Mapping[str, Any]) -> dict[str, Any]:
    summary = _mapping(payload.get("summary"))
    if summary:
        return {**dict(payload), **summary}
    counts = _mapping(payload.get("counts"))
    if counts:
        return {**dict(payload), **counts}
    return dict(payload)


def _status_from_metric_value(raw_key: str, value: object) -> str:
    if isinstance(value, Mapping):
        for key in ("status", "search_recall_status", "index_freshness_status"):
            if key in value:
                return _text(value.get(key))
        return "present"
    if isinstance(value, bool):
        if raw_key in {"search_recall.search_ceiling_repair_required"} and value:
            return "search_ceiling"
        if raw_key in {"search_recall.domain_ceiling_allowed"} and not value:
            return "search_ceiling_not_claimed"
        return "pass" if value else "fail"
    if isinstance(value, int | float):
        numeric = float(value)
        if raw_key in {
            "abstention_or_blocker_rate",
            "out_of_envelope_abstention_rate",
            "g5_grounded_abstention_rate",
        } and numeric >= 0.8:
            return "abstention_inertia"
        if raw_key == "grounded_result_rate" and numeric == 0.0:
            return "no_grounded_response"
        if raw_key in {"stalled_count", "g4-promotion-stalled-count"} and numeric > 0:
            return "stalled"
        if raw_key == "g7_region_grounded_case_count" and numeric == 0.0:
            return "no_grounded_response"
        if raw_key == "search_recall.missed_seed_count" and numeric > 0:
            return "search_ceiling"
        return "numeric_reading"
    return _text(value) or "present"


def _signal_issue_codes(
    *,
    metric_id: str,
    raw_key: str,
    status: str,
    raw_value: object,
) -> tuple[str, ...]:
    issues: list[str] = []
    lowered = status.casefold()
    if metric_id == "search-recall@known-seeds+index-staleness" and lowered in {
        "stale",
        "fail",
        "miss",
        "search_ceiling",
    }:
        issues.append("layer3_g8_search_recall_miss_reported_as_domain_ceiling")
    if metric_id == "adapter-semantic-loss" and lowered in {"lossy", "blocked", "fail"}:
        issues.append("layer3_g8_semantic_loss_hidden_by_metric_rollup")
    if metric_id == "demand-pull-vs-abstention" and lowered in {
        "abstention_inertia",
        "no_grounded_response",
        "blocked_no_real_grounded_breadth",
        "blocked_by_current_g5_unchanged_blocker",
    }:
        issues.append("layer3_g8_demand_numeric_inertia_hidden_as_pass")
    if raw_key in {"threshold_lowered", "floor_relaxed"} or lowered == "threshold_lowered":
        issues.append("layer3_g8_metric_improved_by_threshold_lowering")
    return tuple(issues)


def _blocking_signal_issues(issue_codes: Iterable[str]) -> tuple[str, ...]:
    return tuple(
        code
        for code in _dedupe(issue_codes)
        if code
        in {
            "layer3_g8_metric_source_missing",
            "layer3_g8_metric_alias_unresolved",
            "layer3_g8_metric_raw_ref_missing",
            "layer3_g8_metric_authority_boundary_missing",
        }
    )


def _latest_metric_status(signals: Layer3G8NormalizedMetricSignals, metric_id: str) -> str:
    matching = [signal for signal in signals.signals if signal.metric_id == metric_id]
    if not matching:
        return "missing"
    semantic_blockers = {
        "abstention_inertia",
        "no_grounded_response",
        "blocked_no_real_grounded_breadth",
        "blocked_by_current_g5_unchanged_blocker",
        "search_ceiling",
        "stale",
        "miss",
        "stalled",
        "lossy",
        "blocked",
        "fail",
    }
    for signal in matching:
        if signal.status.casefold() in semantic_blockers:
            return signal.status
    rank = {
        "G8": 8.0,
        "G7": 7.0,
        "G6": 6.0,
        "G5": 5.0,
        "G4": 4.0,
        "GL": 3.5,
        "G3": 3.0,
        "G2": 2.0,
        "G1": 1.0,
        "G0": 0.0,
    }
    latest = sorted(matching, key=lambda signal: rank.get(signal.slice_id, -1))[-1]
    return latest.status


def _slug(value: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in value.lower()).strip("-")
```

- [ ] **Step 4: Run source/normalization tests**

```bash
cd policy-engine
uv run pytest tests/unit/runtime/quality/test_layer3_g8_health_metric_governance.py::test_g8_source_snapshot_reads_current_g0_to_g7_and_s14_artifacts tests/unit/runtime/quality/test_layer3_g8_health_metric_governance.py::test_g8_normalizes_current_metric_dialects_without_losing_raw_refs tests/unit/runtime/quality/test_layer3_g8_health_metric_governance.py::test_g8_metric_trend_report_exposes_all_five_ci_visible_metrics -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
cd policy-engine
git add src/polisyos/runtime/quality/layer3_health_metric_governance.py tests/unit/runtime/quality/test_layer3_g8_health_metric_governance.py
git commit -m "feat: normalize layer3 health metric signals"
```

## Task 4: Cross-Metric Diagnosis and Domain/Search Ceiling Gate

**Files:**

- Modify: `src/polisyos/runtime/quality/layer3_health_metric_governance.py`
- Modify: `tests/unit/runtime/quality/test_layer3_g8_health_metric_governance.py`

- [ ] **Step 1: Write failing diagnosis tests**

Add:

```python
def test_g8_current_state_does_not_claim_domain_ceiling() -> None:
    registry = g8.build_g8_health_metric_registry()
    snapshot = g8.build_g8_metric_source_snapshot(REPO_ROOT)
    signals = g8.build_g8_normalized_metric_signals(
        registry=registry,
        source_snapshot=snapshot,
    )
    diagnosis = g8.build_g8_cross_metric_diagnosis(signals=signals, repo_root=REPO_ROOT)
    gate = g8.build_g8_domain_vs_search_ceiling_gate(diagnosis=diagnosis)

    assert diagnosis.status == "pass"
    assert gate.status == "not_claimed_current_grounding_blocker"
    assert gate.domain_ceiling_claim_allowed is False
    assert "layer3_g8_flat_expansion_reported_as_domain_ceiling_without_search_health" not in gate.issue_codes
    assert gate.current_blocker_refs
    assert diagnosis.effective_independence_status == "sufficient"
    assert diagnosis.effective_independent_evidence_count == 2
    assert diagnosis.effective_independence_source_ref == (
        "repo://architecture/policy_design_case/layer3_g5_effective_evidence_independence.json"
        "#independence_map_payload.effective_mass_report"
    )


def test_g8_search_recall_miss_blocks_domain_ceiling() -> None:
    signals = g8.Layer3G8NormalizedMetricSignals(
        status="pass",
        signals=(
            _signal("envelope-expansion-rate", "G5", "g5_envelope_expansion_status", "flat"),
            _signal("governance-throughput", "G5", "g5_governance_throughput_status", "pass"),
            _signal("demand-pull-vs-abstention", "G6", "grounded_result_rate", 0.0),
            _signal("adapter-semantic-loss", "G7", "semantic_loss_status", "pass"),
            _signal(
                "search-recall@known-seeds+index-staleness",
                "G1",
                "search-recall@known-seeds+index-staleness",
                "search_ceiling",
            ),
        ),
    )
    diagnosis = g8.build_g8_cross_metric_diagnosis(signals=signals, repo_root=REPO_ROOT)
    gate = g8.build_g8_domain_vs_search_ceiling_gate(diagnosis=diagnosis)

    assert gate.status == "search_ceiling_repair_required"
    assert gate.domain_ceiling_claim_allowed is False
    assert "layer3_g8_search_recall_miss_reported_as_domain_ceiling" in gate.issue_codes


def test_g8_zero_grounded_response_blocks_domain_ceiling_as_abstention_inertia() -> None:
    signals = g8.Layer3G8NormalizedMetricSignals(
        status="pass",
        signals=(
            _signal("envelope-expansion-rate", "G5", "g5_envelope_expansion_status", "flat"),
            _signal("governance-throughput", "G4", "g4_governance_throughput_status", "pass"),
            _signal("demand-pull-vs-abstention", "G6", "abstention_or_blocker_rate", "abstention_inertia"),
            _signal("adapter-semantic-loss", "G7", "semantic_loss_status", "pass"),
            _signal("search-recall@known-seeds+index-staleness", "G7", "g1_search_recall_status", "pass"),
        ),
    )
    diagnosis = g8.build_g8_cross_metric_diagnosis(signals=signals, repo_root=REPO_ROOT)
    gate = g8.build_g8_domain_vs_search_ceiling_gate(diagnosis=diagnosis)

    assert "abstention_inertia" in diagnosis.diagnoses
    assert gate.status == "abstention_inertia_repair_required"
    assert gate.domain_ceiling_claim_allowed is False
    assert "layer3_g8_abstention_inertia_hidden_as_honesty" in gate.issue_codes


def _signal(metric_id: str, slice_id: str, raw_key: str, value: object) -> g8.Layer3G8NormalizedMetricSignal:
    return g8.Layer3G8NormalizedMetricSignal(
        signal_id=f"test://{metric_id}/{slice_id}/{raw_key}",
        slice_id=slice_id,
        metric_id=metric_id,
        raw_key=raw_key,
        raw_value=value,
        status=str(value),
        raw_source_ref=f"repo://test#{raw_key}",
        source_digest="sha256:" + "1" * 64,
        freshness_status="fresh_committed",
        authority_boundary_status="pass",
        observed_at="2026-06-10T00:00:00Z",
    )
```

- [ ] **Step 2: Run failing diagnosis tests**

```bash
cd policy-engine
uv run pytest tests/unit/runtime/quality/test_layer3_g8_health_metric_governance.py::test_g8_current_state_does_not_claim_domain_ceiling tests/unit/runtime/quality/test_layer3_g8_health_metric_governance.py::test_g8_search_recall_miss_blocks_domain_ceiling -q
uv run pytest tests/unit/runtime/quality/test_layer3_g8_health_metric_governance.py::test_g8_zero_grounded_response_blocks_domain_ceiling_as_abstention_inertia -q
```

Expected: fail because diagnosis and gate builders do not exist.

- [ ] **Step 3: Implement diagnosis and gate**

Add:

```python
class Layer3G8CrossMetricDiagnosis(_G8Model):
    schema_version: str = G8_SCHEMA_VERSION
    rule_version: str = G8_RULE_VERSION
    diagnosis_id: str = "layer3-g8://cross-metric-diagnosis"
    status: Literal["pass", "blocked"]
    envelope_expansion_status: str
    semantic_loss_status: str
    governance_throughput_status: str
    demand_pull_status: str
    search_recall_freshness_status: str
    effective_independence_status: str
    effective_independent_evidence_count: int
    effective_independence_source_ref: str
    current_blocker_refs: tuple[str, ...]
    diagnoses: tuple[str, ...]
    issue_codes: tuple[str, ...] = ()
    authoritative_for: tuple[str, ...] = G8_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G8_MAY_NOT_USE_FOR


class Layer3G8DomainVsSearchCeilingGate(_G8Model):
    schema_version: str = G8_SCHEMA_VERSION
    rule_version: str = G8_RULE_VERSION
    gate_id: str = "layer3-g8://domain-vs-search-ceiling-gate"
    status: Literal[
        "domain_ceiling_candidate",
        "search_ceiling_repair_required",
        "governance_stall_repair_required",
        "abstention_inertia_repair_required",
        "semantic_loss_repair_required",
        "not_claimed_current_grounding_blocker",
        "blocked",
    ]
    domain_ceiling_claim_allowed: bool
    current_blocker_refs: tuple[str, ...]
    issue_codes: tuple[str, ...] = ()
    authoritative_for: tuple[str, ...] = G8_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G8_MAY_NOT_USE_FOR


def build_g8_cross_metric_diagnosis(
    *,
    signals: Layer3G8NormalizedMetricSignals,
    repo_root: str | Path = DEFAULT_REPO_ROOT,
) -> Layer3G8CrossMetricDiagnosis:
    root = Path(repo_root).resolve()
    g5 = _read_optional_json(root / POLICY_DESIGN_CASE_DIR / "layer3_g5_readiness_manifest.json")
    g7 = _read_optional_json(root / POLICY_DESIGN_CASE_DIR / "layer3_g7_readiness_manifest.json")
    g5_independence = _read_optional_json(
        root / POLICY_DESIGN_CASE_DIR / "layer3_g5_effective_evidence_independence.json"
    )
    effective_mass = _mapping(
        _mapping(g5_independence.get("independence_map_payload")).get("effective_mass_report")
    )
    statuses = {
        metric_id: _latest_metric_status(signals, metric_id)
        for metric_id in G8_CANONICAL_METRIC_IDS
    }
    current_blockers: list[str] = []
    if _text(g5.get("g5_conversion_outcome") or _mapping(g5.get("summary")).get("g5_conversion_outcome")) == "unchanged_blocker":
        current_blockers.append("repo://architecture/policy_design_case/layer3_g5_readiness_manifest.json#g5_conversion_outcome")
    g7_summary = _mapping(g7.get("summary"))
    if _text(g7.get("g7_region_value_closure_status") or g7_summary.get("g7_region_value_closure_status")).startswith("blocked"):
        current_blockers.append("repo://architecture/policy_design_case/layer3_g7_readiness_manifest.json#g7_region_value_closure_status")
    if int(g7.get("g7_region_grounded_case_count") or g7_summary.get("g7_region_grounded_case_count") or 0) == 0:
        current_blockers.append("repo://architecture/policy_design_case/layer3_g7_readiness_manifest.json#g7_region_grounded_case_count")

    diagnoses: list[str] = []
    issues: list[str] = [*signals.issue_codes]
    effective_independence_status = _text(effective_mass.get("independence_status")) or "missing"
    effective_independent_evidence_count = int(
        effective_mass.get("effective_independent_evidence_count") or 0
    )
    if effective_independence_status in {"inflated", "unknown", "missing"}:
        issues.append("layer3_g8_effective_independence_inflated")
    if _is_search_ceiling(statuses["search-recall@known-seeds+index-staleness"]):
        diagnoses.append("search_ceiling")
        issues.append("layer3_g8_search_recall_miss_reported_as_domain_ceiling")
    if _is_governance_stall(statuses["governance-throughput"]):
        diagnoses.append("governance_bottleneck")
        issues.append("layer3_g8_governance_stall_hidden_as_domain_ceiling")
    if _is_abstention_inertia(statuses["demand-pull-vs-abstention"]):
        diagnoses.append("abstention_inertia")
        issues.append("layer3_g8_abstention_inertia_hidden_as_honesty")
    if _is_semantic_loss(statuses["adapter-semantic-loss"]):
        diagnoses.append("semantic_loss")
        issues.append("layer3_g8_semantic_loss_hidden_by_metric_rollup")
    if current_blockers:
        diagnoses.append("current_grounding_blocker")
    if not diagnoses:
        diagnoses.append("healthy_metric_watch")

    blocking = {
        "layer3_g8_metric_source_missing",
        "layer3_g8_metric_alias_unresolved",
        "layer3_g8_metric_raw_ref_missing",
        "layer3_g8_metric_authority_boundary_missing",
    }
    return Layer3G8CrossMetricDiagnosis(
        status="blocked" if blocking.intersection(issues) else "pass",
        envelope_expansion_status=statuses["envelope-expansion-rate"],
        semantic_loss_status=statuses["adapter-semantic-loss"],
        governance_throughput_status=statuses["governance-throughput"],
        demand_pull_status=statuses["demand-pull-vs-abstention"],
        search_recall_freshness_status=statuses["search-recall@known-seeds+index-staleness"],
        effective_independence_status=effective_independence_status,
        effective_independent_evidence_count=effective_independent_evidence_count,
        effective_independence_source_ref=(
            "repo://architecture/policy_design_case/layer3_g5_effective_evidence_independence.json"
            "#independence_map_payload.effective_mass_report"
        ),
        current_blocker_refs=_dedupe(current_blockers),
        diagnoses=_dedupe(diagnoses),
        issue_codes=_dedupe(issues),
    )


def build_g8_domain_vs_search_ceiling_gate(
    *,
    diagnosis: Layer3G8CrossMetricDiagnosis,
) -> Layer3G8DomainVsSearchCeilingGate:
    if diagnosis.status == "blocked":
        return Layer3G8DomainVsSearchCeilingGate(
            status="blocked",
            domain_ceiling_claim_allowed=False,
            current_blocker_refs=diagnosis.current_blocker_refs,
            issue_codes=diagnosis.issue_codes,
        )
    if "search_ceiling" in diagnosis.diagnoses:
        return Layer3G8DomainVsSearchCeilingGate(
            status="search_ceiling_repair_required",
            domain_ceiling_claim_allowed=False,
            current_blocker_refs=diagnosis.current_blocker_refs,
            issue_codes=_dedupe((*diagnosis.issue_codes, "layer3_g8_search_recall_miss_reported_as_domain_ceiling")),
        )
    if "governance_bottleneck" in diagnosis.diagnoses:
        return Layer3G8DomainVsSearchCeilingGate(
            status="governance_stall_repair_required",
            domain_ceiling_claim_allowed=False,
            current_blocker_refs=diagnosis.current_blocker_refs,
            issue_codes=_dedupe((*diagnosis.issue_codes, "layer3_g8_governance_stall_hidden_as_domain_ceiling")),
        )
    if "abstention_inertia" in diagnosis.diagnoses:
        return Layer3G8DomainVsSearchCeilingGate(
            status="abstention_inertia_repair_required",
            domain_ceiling_claim_allowed=False,
            current_blocker_refs=diagnosis.current_blocker_refs,
            issue_codes=_dedupe((*diagnosis.issue_codes, "layer3_g8_abstention_inertia_hidden_as_honesty")),
        )
    if "semantic_loss" in diagnosis.diagnoses:
        return Layer3G8DomainVsSearchCeilingGate(
            status="semantic_loss_repair_required",
            domain_ceiling_claim_allowed=False,
            current_blocker_refs=diagnosis.current_blocker_refs,
            issue_codes=diagnosis.issue_codes,
        )
    if diagnosis.current_blocker_refs:
        return Layer3G8DomainVsSearchCeilingGate(
            status="not_claimed_current_grounding_blocker",
            domain_ceiling_claim_allowed=False,
            current_blocker_refs=diagnosis.current_blocker_refs,
            issue_codes=diagnosis.issue_codes,
        )
    return Layer3G8DomainVsSearchCeilingGate(
        status="domain_ceiling_candidate",
        domain_ceiling_claim_allowed=True,
        current_blocker_refs=(),
        issue_codes=diagnosis.issue_codes,
    )


def domain_ceiling_claim_issue_codes(
    *,
    diagnosis: Layer3G8CrossMetricDiagnosis,
    claimed_domain_ceiling: bool,
) -> tuple[str, ...]:
    if not claimed_domain_ceiling:
        return ()
    issues: list[str] = []
    if "search_ceiling" in diagnosis.diagnoses:
        issues.append("layer3_g8_search_recall_miss_reported_as_domain_ceiling")
    if "governance_bottleneck" in diagnosis.diagnoses:
        issues.append("layer3_g8_governance_stall_hidden_as_domain_ceiling")
    if "abstention_inertia" in diagnosis.diagnoses:
        issues.append("layer3_g8_abstention_inertia_hidden_as_honesty")
    if "semantic_loss" in diagnosis.diagnoses:
        issues.append("layer3_g8_semantic_loss_hidden_by_metric_rollup")
    if diagnosis.current_blocker_refs or diagnosis.envelope_expansion_status == "flat":
        issues.append("layer3_g8_flat_expansion_reported_as_domain_ceiling_without_search_health")
    return _dedupe(issues)
```

Add helpers:

```python
def _read_optional_json(path: Path) -> dict[str, Any]:
    try:
        return _read_json(path)
    except (OSError, json.JSONDecodeError):
        return {}


def _is_search_ceiling(status: str) -> bool:
    return status.casefold() in {"search_ceiling", "stale", "fail", "miss", "blocked_search_control_plane_only"}


def _is_governance_stall(status: str) -> bool:
    return status.casefold() in {"stalled", "missing", "blocked", "fail"}


def _is_abstention_inertia(status: str) -> bool:
    return status.casefold() in {
        "abstention_inertia",
        "cheap_refusal",
        "blocked_no_demand_response",
        "no_grounded_response",
        "blocked_no_real_grounded_breadth",
        "blocked_by_current_g5_unchanged_blocker",
    }


def _is_semantic_loss(status: str) -> bool:
    return status.casefold() in {"lossy", "blocked", "fail"}
```

- [ ] **Step 4: Run diagnosis tests**

```bash
cd policy-engine
uv run pytest tests/unit/runtime/quality/test_layer3_g8_health_metric_governance.py::test_g8_current_state_does_not_claim_domain_ceiling tests/unit/runtime/quality/test_layer3_g8_health_metric_governance.py::test_g8_search_recall_miss_blocks_domain_ceiling -q
uv run pytest tests/unit/runtime/quality/test_layer3_g8_health_metric_governance.py::test_g8_zero_grounded_response_blocks_domain_ceiling_as_abstention_inertia -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
cd policy-engine
git add src/polisyos/runtime/quality/layer3_health_metric_governance.py tests/unit/runtime/quality/test_layer3_g8_health_metric_governance.py
git commit -m "feat: diagnose layer3 metric ceilings"
```

## Task 5: Metric-Gaming Firewall and Warning Lifecycle

**Files:**

- Modify: `src/polisyos/runtime/quality/layer3_health_metric_governance.py`
- Modify: `tests/unit/runtime/quality/test_layer3_g8_health_metric_governance.py`

- [ ] **Step 1: Write failing firewall and warning tests**

Add:

```python
def test_g8_metric_gaming_firewall_blocks_threshold_lowering_and_useful_design_optimization() -> None:
    firewall = g8.build_g8_metric_gaming_firewall(
        metric_changes=[
            {
                "metric_id": "demand-pull-vs-abstention",
                "claimed_improvement": True,
                "change_class": "threshold_lowered",
                "target_metric": "useful_design_rate",
                "source_ref": "test://threshold-lowering",
            }
        ]
    )

    assert firewall.status == "blocked"
    assert "layer3_g8_metric_improved_by_threshold_lowering" in firewall.issue_codes
    assert "layer3_g8_useful_design_rate_optimized" in firewall.issue_codes


def test_g8_warning_lifecycle_requires_owner_and_aging_policy() -> None:
    ledger = g8.build_g8_warning_lifecycle_ledger(
        warnings=[
            {
                "warning_id": "metric-stale",
                "metric_id": "search-recall@known-seeds+index-staleness",
                "severity": "warn",
                "owner": "",
                "deadline": "2026-06-17",
                "aging_policy": "",
                "source_ref": "repo://architecture/policy_design_case/layer3_g1_health_metric_delta.toml",
            }
        ]
    )

    assert ledger.status == "blocked"
    assert "layer3_g8_warning_owner_missing" in ledger.issue_codes
    assert "layer3_g8_warning_aging_policy_missing" in ledger.issue_codes
```

- [ ] **Step 2: Run the failing tests**

```bash
cd policy-engine
uv run pytest tests/unit/runtime/quality/test_layer3_g8_health_metric_governance.py::test_g8_metric_gaming_firewall_blocks_threshold_lowering_and_useful_design_optimization tests/unit/runtime/quality/test_layer3_g8_health_metric_governance.py::test_g8_warning_lifecycle_requires_owner_and_aging_policy -q
```

Expected: fail because firewall and warning builders do not exist.

- [ ] **Step 3: Implement firewall and warning lifecycle**

Add:

```python
class Layer3G8MetricGamingFirewall(_G8Model):
    schema_version: str = G8_SCHEMA_VERSION
    rule_version: str = G8_RULE_VERSION
    firewall_id: str = "layer3-g8://metric-gaming-firewall"
    status: Literal["pass", "blocked"]
    checked_change_count: int
    blocked_change_refs: tuple[str, ...]
    issue_codes: tuple[str, ...] = ()
    authoritative_for: tuple[str, ...] = G8_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G8_MAY_NOT_USE_FOR


class Layer3G8WarningLifecycleRow(_G8Model):
    warning_id: str
    metric_id: str
    severity: Literal["info", "warn", "blocked"]
    owner: str
    deadline: str
    aging_policy: str
    accepted_deficit_policy: str
    source_ref: str
    issue_codes: tuple[str, ...] = ()


class Layer3G8WarningLifecycleLedger(_G8Model):
    schema_version: str = G8_SCHEMA_VERSION
    rule_version: str = G8_RULE_VERSION
    ledger_id: str = "layer3-g8://warning-lifecycle-ledger"
    status: Literal["pass", "blocked"]
    warnings: tuple[Layer3G8WarningLifecycleRow, ...]
    issue_codes: tuple[str, ...] = ()
    authoritative_for: tuple[str, ...] = G8_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G8_MAY_NOT_USE_FOR


def build_g8_metric_gaming_firewall(
    *,
    metric_changes: Sequence[Mapping[str, Any]],
) -> Layer3G8MetricGamingFirewall:
    issues: list[str] = []
    blocked_refs: list[str] = []
    for change in metric_changes:
        change_class = _text(change.get("change_class")).casefold()
        target_metric = _text(change.get("target_metric")).casefold()
        source_ref = _text(change.get("source_ref")) or "unknown://metric-change"
        if change.get("claimed_improvement") and change_class in {
            "threshold_lowered",
            "floor_relaxed",
            "hidden_fixture_added",
            "synthetic_breadth",
        }:
            blocked_refs.append(source_ref)
            if change_class in {"threshold_lowered", "floor_relaxed"}:
                issues.append("layer3_g8_metric_improved_by_threshold_lowering")
            else:
                issues.append("layer3_g8_metric_improved_by_fixture_or_synthetic_breadth")
        if target_metric == "useful_design_rate":
            blocked_refs.append(source_ref)
            issues.append("layer3_g8_useful_design_rate_optimized")
    return Layer3G8MetricGamingFirewall(
        status="blocked" if issues else "pass",
        checked_change_count=len(metric_changes),
        blocked_change_refs=_dedupe(blocked_refs),
        issue_codes=_dedupe(issues),
    )


def build_g8_warning_lifecycle_ledger(
    *,
    warnings: Sequence[Mapping[str, Any]],
) -> Layer3G8WarningLifecycleLedger:
    rows: list[Layer3G8WarningLifecycleRow] = []
    issues: list[str] = []
    for raw in warnings:
        row_issues: list[str] = []
        if not _text(raw.get("owner")):
            row_issues.append("layer3_g8_warning_owner_missing")
        if not _text(raw.get("aging_policy")):
            row_issues.append("layer3_g8_warning_aging_policy_missing")
        issues.extend(row_issues)
        rows.append(
            Layer3G8WarningLifecycleRow(
                warning_id=_text(raw.get("warning_id")) or "layer3-g8-warning",
                metric_id=canonical_metric_id(_text(raw.get("metric_id"))) or _text(raw.get("metric_id")),
                severity=_text(raw.get("severity")) or "warn",  # type: ignore[arg-type]
                owner=_text(raw.get("owner")),
                deadline=_text(raw.get("deadline")),
                aging_policy=_text(raw.get("aging_policy")),
                accepted_deficit_policy=_text(raw.get("accepted_deficit_policy")) or "blocks_closeout_authority",
                source_ref=_text(raw.get("source_ref")),
                issue_codes=_dedupe(row_issues),
            )
        )
    return Layer3G8WarningLifecycleLedger(
        status="blocked" if issues else "pass",
        warnings=tuple(rows),
        issue_codes=_dedupe(issues),
    )
```

- [ ] **Step 4: Add the default warning builder**

Add:

```python
def build_g8_default_warning_lifecycle_ledger(
    *,
    diagnosis: Layer3G8CrossMetricDiagnosis,
) -> Layer3G8WarningLifecycleLedger:
    warnings: list[dict[str, Any]] = []
    if "current_grounding_blocker" in diagnosis.diagnoses:
        warnings.append(
            {
                "warning_id": "layer3-g8-current-grounding-blocker",
                "metric_id": "envelope-expansion-rate",
                "severity": "warn",
                "owner": "team-runtime-quality",
                "deadline": "2026-06-17",
                "aging_policy": "escalate_if_unchanged_after_next_g_slice",
                "accepted_deficit_policy": "may_pass_engineering_readiness_but_blocks_domain_ceiling_claim",
                "source_ref": "repo://architecture/policy_design_case/layer3_g7_readiness_manifest.json",
            }
        )
    return build_g8_warning_lifecycle_ledger(warnings=warnings)
```

- [ ] **Step 5: Run firewall and warning tests**

```bash
cd policy-engine
uv run pytest tests/unit/runtime/quality/test_layer3_g8_health_metric_governance.py::test_g8_metric_gaming_firewall_blocks_threshold_lowering_and_useful_design_optimization tests/unit/runtime/quality/test_layer3_g8_health_metric_governance.py::test_g8_warning_lifecycle_requires_owner_and_aging_policy -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
cd policy-engine
git add src/polisyos/runtime/quality/layer3_health_metric_governance.py tests/unit/runtime/quality/test_layer3_g8_health_metric_governance.py
git commit -m "feat: block layer3 metric gaming"
```

## Task 6: D4.4 Corpus Re-Basing Rule and Sealed-Battery Integrity

**Files:**

- Modify: `src/polisyos/runtime/quality/layer3_health_metric_governance.py`
- Modify: `tests/unit/runtime/quality/test_layer3_g8_health_metric_governance.py`

- [ ] **Step 1: Write failing D4.4 tests**

Add:

```python
def test_g8_d44_rebasing_receipt_uses_freeze_hashes_without_hidden_payload_refs() -> None:
    rule = g8.build_g8_d44_corpus_rebasing_rule(repo_root=REPO_ROOT)
    coverage = g8.build_g8_d44_reannotation_coverage_matrix(rule=rule, repo_root=REPO_ROOT)
    trigger_ledger = g8.build_g8_d44_rebasing_trigger_ledger(repo_root=REPO_ROOT)
    candidate_set = g8.build_g8_d44_rebasing_candidate_set(repo_root=REPO_ROOT)
    integrity_join = g8.build_g8_sealed_battery_integrity_join(repo_root=REPO_ROOT)
    receipt = g8.build_g8_d44_rebasing_receipt(
        rule=rule,
        candidate_set=candidate_set,
        repo_root=REPO_ROOT,
    )

    serialized = receipt.model_dump_json()
    assert rule.status == "pass"
    assert len(rule.required_reannotation_fields) == len(g8.D44_REQUIRED_REANNOTATION_FIELDS)
    assert coverage.status == "pass"
    assert {row.field_id for row in coverage.field_rows} == set(g8.D44_REQUIRED_REANNOTATION_FIELDS)
    assert {row.coverage_status for row in coverage.field_rows} <= {
        "required_for_next_rebase",
        "satisfied_by_existing_s14_record",
    }
    assert any(
        row.coverage_status == "satisfied_by_existing_s14_record"
        for row in coverage.field_rows
    )
    assert any(
        row.coverage_status == "required_for_next_rebase"
        for row in coverage.field_rows
    )
    assert trigger_ledger.status == "pass_no_rebase_due"
    assert trigger_ledger.current_action == "no_rebase_required_current_g7_has_no_real_grounded_breadth"
    assert receipt.status == "pass_no_rebase_required"
    assert integrity_join.status == "pass"
    assert integrity_join.hidden_payload_access_status == "not_accessed_by_g7"
    assert receipt.pre_rebase_freeze_hash.startswith("sha256:")
    assert receipt.post_rebase_freeze_hash == receipt.pre_rebase_freeze_hash
    assert "sealed_gold_label_ref" not in serialized
    assert "expected_boundary_disposition" not in serialized
    assert "input_condition_ref" not in serialized
    assert receipt.hidden_payload_access_status == "not_accessed_by_g8"


def test_g8_sealed_battery_join_blocks_mutation_or_floor_lowering() -> None:
    join = g8.build_g8_sealed_battery_integrity_join(
        repo_root=REPO_ROOT,
        rebasing_attempt={
            "post_rebase_freeze_hash": "sha256:" + "2" * 64,
            "pre_rebase_freeze_hash": "sha256:" + "1" * 64,
            "floor_change": "lowered",
            "hidden_payload_ref": "sealed_gold_label_ref://leak",
        },
    )

    assert join.status == "blocked"
    assert "layer3_g8_rebasing_mutates_sealed_battery" in join.issue_codes
    assert "layer3_g8_rebasing_lowers_s14_floor" in join.issue_codes
    assert "layer3_g8_rebasing_leaks_gold_or_hidden_payload" in join.issue_codes
```

- [ ] **Step 2: Run failing D4.4 tests**

```bash
cd policy-engine
uv run pytest tests/unit/runtime/quality/test_layer3_g8_health_metric_governance.py::test_g8_d44_rebasing_receipt_uses_freeze_hashes_without_hidden_payload_refs tests/unit/runtime/quality/test_layer3_g8_health_metric_governance.py::test_g8_sealed_battery_join_blocks_mutation_or_floor_lowering -q
```

Expected: fail because D4.4 builders do not exist.

- [ ] **Step 3: Implement D4.4 models and builders**

Add:

```python
class Layer3G8D44CorpusRebasingRule(_G8Model):
    schema_version: str = G8_SCHEMA_VERSION
    rule_version: str = G8_RULE_VERSION
    rule_id: str = "layer3-g8://d44-corpus-rebasing-rule"
    status: Literal["pass", "blocked"]
    required_reannotation_fields: tuple[str, ...]
    freeze_hash_discipline: str
    hidden_access_rule: str
    issue_codes: tuple[str, ...] = ()
    authoritative_for: tuple[str, ...] = G8_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G8_MAY_NOT_USE_FOR


class Layer3G8D44ReannotationCoverageRow(_G8Model):
    field_id: str
    coverage_status: Literal["required_for_next_rebase", "satisfied_by_existing_s14_record"]
    source_ref: str
    issue_codes: tuple[str, ...] = ()


class Layer3G8D44ReannotationCoverageMatrix(_G8Model):
    schema_version: str = G8_SCHEMA_VERSION
    rule_version: str = G8_RULE_VERSION
    matrix_id: str = "layer3-g8://d44-reannotation-coverage-matrix"
    status: Literal["pass", "blocked"]
    field_rows: tuple[Layer3G8D44ReannotationCoverageRow, ...]
    issue_codes: tuple[str, ...] = ()
    authoritative_for: tuple[str, ...] = G8_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G8_MAY_NOT_USE_FOR


class Layer3G8D44RebasingTriggerRow(_G8Model):
    trigger_id: str
    trigger_status: Literal["not_due", "due", "blocked"]
    source_ref: str
    reason: str


class Layer3G8D44RebasingTriggerLedger(_G8Model):
    schema_version: str = G8_SCHEMA_VERSION
    rule_version: str = G8_RULE_VERSION
    ledger_id: str = "layer3-g8://d44-rebasing-trigger-ledger"
    status: Literal["pass_no_rebase_due", "rebase_due", "blocked"]
    current_action: str
    trigger_rows: tuple[Layer3G8D44RebasingTriggerRow, ...]
    issue_codes: tuple[str, ...] = ()
    authoritative_for: tuple[str, ...] = G8_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G8_MAY_NOT_USE_FOR


class Layer3G8D44RebasingCandidateSet(_G8Model):
    schema_version: str = G8_SCHEMA_VERSION
    rule_version: str = G8_RULE_VERSION
    candidate_set_id: str = "layer3-g8://d44-rebasing-candidate-set"
    status: Literal["pass", "blocked"]
    candidate_refs: tuple[str, ...]
    source_refs: tuple[str, ...]
    issue_codes: tuple[str, ...] = ()
    authoritative_for: tuple[str, ...] = G8_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G8_MAY_NOT_USE_FOR


class Layer3G8D44RebasingReceipt(_G8Model):
    schema_version: str = G8_SCHEMA_VERSION
    rule_version: str = G8_RULE_VERSION
    receipt_id: str = "layer3-g8://d44-rebasing-receipt/current"
    status: Literal["pass_no_rebase_required", "blocked", "rebased_with_new_freeze_hash"]
    action: str
    pre_rebase_freeze_hash: str
    post_rebase_freeze_hash: str
    corpus_partition_ref: str
    s14_assurance_manifest_ref: str
    candidate_set_ref: str
    hidden_payload_access_status: Literal["not_accessed_by_g8", "blocked"]
    issue_codes: tuple[str, ...] = ()
    authoritative_for: tuple[str, ...] = G8_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G8_MAY_NOT_USE_FOR


class Layer3G8SealedBatteryIntegrityJoin(_G8Model):
    schema_version: str = G8_SCHEMA_VERSION
    rule_version: str = G8_RULE_VERSION
    join_id: str = "layer3-g8://sealed-battery-integrity-join"
    status: Literal["pass", "blocked"]
    partition_freeze_hash: str
    s14_manifest_freeze_hash: str
    g7_mutation_status: str
    hidden_payload_access_status: str
    issue_codes: tuple[str, ...] = ()
    authoritative_for: tuple[str, ...] = G8_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G8_MAY_NOT_USE_FOR


def build_g8_d44_corpus_rebasing_rule(
    *,
    repo_root: str | Path = DEFAULT_REPO_ROOT,
) -> Layer3G8D44CorpusRebasingRule:
    return Layer3G8D44CorpusRebasingRule(
        status="pass",
        required_reannotation_fields=D44_REQUIRED_REANNOTATION_FIELDS,
        freeze_hash_discipline=(
            "Any re-basing that changes sealed battery membership, labels, thresholds, "
            "or expected dispositions requires a new governance-approved freeze hash "
            "and replay receipt."
        ),
        hidden_access_rule=(
            "G8 may read committed partition and S14 assurance manifests; it must not "
            "read hidden sealed case payloads or gold labels in development paths."
        ),
    )


_D44_EXISTING_S14_FIELD_REFS: dict[str, str] = {
    "expected_evidence_tier": (
        "repo://architecture/policy_design_case/layer2_s14_universality_assurance_manifest.json"
        "#supporting_records.UniversalityBreadthFloorConfig"
    ),
    "available_source_contracts": (
        "repo://architecture/policy_design_case/layer2_s14_universality_assurance_manifest.json"
        "#grounded_authority_coverage_ref"
    ),
    "expected_graded_outcome_by_authority_posture": (
        "repo://architecture/policy_design_case/layer2_s14_universality_assurance_manifest.json"
        "#supporting_records.EvaluationStatusCompositionRecord"
    ),
    "certified_operation_envelope_status": (
        "repo://architecture/policy_design_case/layer2_s14_universality_assurance_manifest.json"
        "#declared_operation_envelope_ref"
    ),
    "expected_abstention_limitation_boundary": (
        "repo://architecture/policy_design_case/layer2_s14_universality_assurance_manifest.json"
        "#universal_claim_gate_status"
    ),
    "expected_counterexample_class": (
        "repo://architecture/policy_design_case/layer2_s14_universality_assurance_manifest.json"
        "#skeptic_defeater_mapping"
    ),
    "bootstrap_role": (
        "repo://architecture/policy_design_case/layer2_s14_universality_assurance_manifest.json"
        "#supporting_records.ExpertOracleBootstrapRecord"
    ),
    "universality_battery_metadata": (
        "repo://architecture/policy_design_case/layer2_s14_universality_assurance_manifest.json"
        "#artifact_records.SealedUniversalityBatteryRun"
    ),
    "post_deploy_monitoring_hooks": (
        "repo://architecture/policy_design_case/layer2_s14_universality_assurance_manifest.json"
        "#supporting_records.EnvelopeRevisionDynamicsRecord"
    ),
    "historical_outcomes_prediction_backtest_usability": (
        "repo://architecture/policy_design_case/layer2_s14_universality_assurance_manifest.json"
        "#baseline_comparison_ref"
    ),
    "realized_regret_observability": (
        "repo://architecture/policy_design_case/layer2_s14_universality_assurance_manifest.json"
        "#supporting_records.EvaluationStatusCompositionRecord"
    ),
}


def build_g8_d44_reannotation_coverage_matrix(
    *,
    rule: Layer3G8D44CorpusRebasingRule,
    repo_root: str | Path = DEFAULT_REPO_ROOT,
) -> Layer3G8D44ReannotationCoverageMatrix:
    rows: list[Layer3G8D44ReannotationCoverageRow] = []
    for field_id in rule.required_reannotation_fields:
        source_ref = _D44_EXISTING_S14_FIELD_REFS.get(
            field_id,
            (
                "repo://docs/system-design-decisions/"
                "universal-policy-design-target-architecture-and-gap.md#D4.4"
            ),
        )
        rows.append(
            Layer3G8D44ReannotationCoverageRow(
                field_id=field_id,
                coverage_status=(
                    "satisfied_by_existing_s14_record"
                    if field_id in _D44_EXISTING_S14_FIELD_REFS
                    else "required_for_next_rebase"
                ),
                source_ref=source_ref,
            )
        )
    missing = sorted(set(D44_REQUIRED_REANNOTATION_FIELDS) - {row.field_id for row in rows})
    stale_existing_refs = sorted(
        set(_D44_EXISTING_S14_FIELD_REFS) - set(D44_REQUIRED_REANNOTATION_FIELDS)
    )
    issues = (
        ("layer3_g8_d44_reannotation_coverage_missing",)
        if missing or stale_existing_refs
        else ()
    )
    return Layer3G8D44ReannotationCoverageMatrix(
        status="blocked" if issues else "pass",
        field_rows=tuple(rows),
        issue_codes=issues,
    )


def build_g8_d44_rebasing_trigger_ledger(
    *,
    repo_root: str | Path = DEFAULT_REPO_ROOT,
) -> Layer3G8D44RebasingTriggerLedger:
    root = Path(repo_root).resolve()
    g7_feed = _read_optional_json(root / POLICY_DESIGN_CASE_DIR / "layer3_g7_s14_grounded_breadth_feed.json")
    feed_status = _text(g7_feed.get("status")) or "blocked_no_real_grounded_breadth"
    new_breadth_due = bool(feed_status and not feed_status.startswith("blocked"))
    trigger_rows = (
        Layer3G8D44RebasingTriggerRow(
            trigger_id="new_real_grounded_breadth",
            trigger_status="due" if new_breadth_due else "not_due",
            source_ref="repo://architecture/policy_design_case/layer3_g7_s14_grounded_breadth_feed.json#status",
            reason=feed_status,
        ),
        Layer3G8D44RebasingTriggerRow(
            trigger_id="s14_floor_or_threshold_change",
            trigger_status="not_due",
            source_ref="repo://architecture/policy_design_case/layer2_s14_universality_assurance_manifest.json",
            reason="no_floor_or_threshold_change_requested_by_g8",
        ),
        Layer3G8D44RebasingTriggerRow(
            trigger_id="sealed_battery_membership_change",
            trigger_status="not_due",
            source_ref="repo://architecture/policy_design_case/layer2_corpus_partition.json#sealed_universality_battery.freeze_hash",
            reason="sealed_battery_membership_not_mutated_by_g8",
        ),
        Layer3G8D44RebasingTriggerRow(
            trigger_id="d44_reannotation_schema_change",
            trigger_status="not_due",
            source_ref="layer3-g8://d44-corpus-rebasing-rule",
            reason="initial_g8_rule_version",
        ),
        Layer3G8D44RebasingTriggerRow(
            trigger_id="post_deploy_monitoring_update",
            trigger_status="not_due",
            source_ref="layer3-g8://d44-rebasing-trigger-ledger/post-deploy-monitoring",
            reason="no_post_deploy_monitoring_signal_for_current_s14_seed",
        ),
    )
    due = [row.trigger_id for row in trigger_rows if row.trigger_status == "due"]
    return Layer3G8D44RebasingTriggerLedger(
        status="rebase_due" if due else "pass_no_rebase_due",
        current_action=(
            "prepare_rebase_receipt_for_new_grounded_breadth"
            if due
            else "no_rebase_required_current_g7_has_no_real_grounded_breadth"
        ),
        trigger_rows=trigger_rows,
        issue_codes=(),
    )


def build_g8_d44_rebasing_candidate_set(
    *,
    repo_root: str | Path = DEFAULT_REPO_ROOT,
) -> Layer3G8D44RebasingCandidateSet:
    return Layer3G8D44RebasingCandidateSet(
        status="pass",
        candidate_refs=(
            "repo://architecture/policy_design_case/layer2_s14_universality_assurance_manifest.json#d4_corpus_track_coverage_ref",
            "repo://architecture/policy_design_case/layer3_g7_s14_grounded_breadth_feed.json",
        ),
        source_refs=(
            "repo://architecture/policy_design_case/layer2_corpus_partition.json",
            "repo://architecture/policy_design_case/layer2_s14_universality_assurance_manifest.json",
            "repo://architecture/policy_design_case/layer3_g7_s14_battery_input_manifest.json",
        ),
    )


def build_g8_d44_rebasing_receipt(
    *,
    rule: Layer3G8D44CorpusRebasingRule,
    candidate_set: Layer3G8D44RebasingCandidateSet,
    repo_root: str | Path = DEFAULT_REPO_ROOT,
) -> Layer3G8D44RebasingReceipt:
    root = Path(repo_root).resolve()
    partition = _read_json(root / POLICY_DESIGN_CASE_DIR / "layer2_corpus_partition.json")
    s14 = _read_json(root / POLICY_DESIGN_CASE_DIR / "layer2_s14_universality_assurance_manifest.json")
    sealed = _mapping(partition.get("sealed_universality_battery"))
    partition_hash = _text(sealed.get("freeze_hash"))
    s14_hash = _text(s14.get("sealed_battery_freeze_hash"))
    issues: list[str] = []
    if not partition_hash or not s14_hash or partition_hash != s14_hash:
        issues.append("layer3_g8_rebasing_without_freeze_hash")
    return Layer3G8D44RebasingReceipt(
        status="blocked" if issues else "pass_no_rebase_required",
        action="no_rebase_required_current_g7_has_no_real_grounded_breadth",
        pre_rebase_freeze_hash=partition_hash or s14_hash,
        post_rebase_freeze_hash=s14_hash or partition_hash,
        corpus_partition_ref="repo://architecture/policy_design_case/layer2_corpus_partition.json",
        s14_assurance_manifest_ref="repo://architecture/policy_design_case/layer2_s14_universality_assurance_manifest.json",
        candidate_set_ref=candidate_set.candidate_set_id,
        hidden_payload_access_status="not_accessed_by_g8",
        issue_codes=_dedupe(issues),
    )


def build_g8_sealed_battery_integrity_join(
    *,
    repo_root: str | Path = DEFAULT_REPO_ROOT,
    rebasing_attempt: Mapping[str, Any] | None = None,
) -> Layer3G8SealedBatteryIntegrityJoin:
    root = Path(repo_root).resolve()
    partition = _read_json(root / POLICY_DESIGN_CASE_DIR / "layer2_corpus_partition.json")
    s14 = _read_json(root / POLICY_DESIGN_CASE_DIR / "layer2_s14_universality_assurance_manifest.json")
    g7_manifest = _read_optional_json(root / POLICY_DESIGN_CASE_DIR / "layer3_g7_s14_battery_input_manifest.json")
    sealed = _mapping(partition.get("sealed_universality_battery"))
    partition_hash = _text(sealed.get("freeze_hash"))
    s14_hash = _text(s14.get("sealed_battery_freeze_hash"))
    attempt = dict(rebasing_attempt or {})
    issues: list[str] = []
    hidden_status = _text(g7_manifest.get("hidden_case_access_status")) or "not_observed"
    if partition_hash != s14_hash:
        issues.append("layer3_g8_rebasing_without_freeze_hash")
    if hidden_status not in {"not_accessed_by_g7", "not_observed"}:
        issues.append("layer3_g8_rebasing_leaks_gold_or_hidden_payload")
    if attempt:
        if _text(attempt.get("pre_rebase_freeze_hash")) != _text(attempt.get("post_rebase_freeze_hash")):
            issues.append("layer3_g8_rebasing_mutates_sealed_battery")
        if _text(attempt.get("floor_change")) == "lowered":
            issues.append("layer3_g8_rebasing_lowers_s14_floor")
        if "hidden" in _text(attempt.get("hidden_payload_ref")) or "gold" in _text(attempt.get("hidden_payload_ref")):
            hidden_status = "blocked"
            issues.append("layer3_g8_rebasing_leaks_gold_or_hidden_payload")
    if _text(g7_manifest.get("sealed_battery_mutation_status")) not in {"", "not_mutated"}:
        issues.append("layer3_g8_rebasing_mutates_sealed_battery")
    return Layer3G8SealedBatteryIntegrityJoin(
        status="blocked" if issues else "pass",
        partition_freeze_hash=partition_hash,
        s14_manifest_freeze_hash=s14_hash,
        g7_mutation_status=_text(g7_manifest.get("sealed_battery_mutation_status")) or "not_observed",
        hidden_payload_access_status=hidden_status,
        issue_codes=_dedupe(issues),
    )
```

- [ ] **Step 4: Run D4.4 tests**

```bash
cd policy-engine
uv run pytest tests/unit/runtime/quality/test_layer3_g8_health_metric_governance.py::test_g8_d44_rebasing_receipt_uses_freeze_hashes_without_hidden_payload_refs tests/unit/runtime/quality/test_layer3_g8_health_metric_governance.py::test_g8_sealed_battery_join_blocks_mutation_or_floor_lowering -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
cd policy-engine
git add src/polisyos/runtime/quality/layer3_health_metric_governance.py tests/unit/runtime/quality/test_layer3_g8_health_metric_governance.py
git commit -m "feat: add d44 corpus rebasing coverage and receipts"
```

## Task 7: Empirical Answers to §8.4 Open Questions

**Files:**

- Modify: `src/polisyos/runtime/quality/layer3_health_metric_governance.py`
- Modify: `tests/unit/runtime/quality/test_layer3_g8_health_metric_governance.py`

- [ ] **Step 1: Write the failing open-question test**

Add:

```python
def test_g8_open_question_ledger_answers_every_vision_question_with_current_evidence() -> None:
    registry = g8.build_g8_health_metric_registry()
    snapshot = g8.build_g8_metric_source_snapshot(REPO_ROOT)
    signals = g8.build_g8_normalized_metric_signals(
        registry=registry,
        source_snapshot=snapshot,
    )
    diagnosis = g8.build_g8_cross_metric_diagnosis(signals=signals, repo_root=REPO_ROOT)
    gate = g8.build_g8_domain_vs_search_ceiling_gate(diagnosis=diagnosis)
    ledger = g8.build_g8_open_question_answer_ledger(
        diagnosis=diagnosis,
        ceiling_gate=gate,
        repo_root=REPO_ROOT,
    )

    assert ledger.status == "pass"
    assert {row.question_id for row in ledger.answers} == {
        "8.4-waist-altitude",
        "8.4-real-grounding-cost",
        "8.4-demand-pull-strength",
        "8.4-search-recall-freshness",
        "8.4-agent-orchestration-authority-leak",
    }
    answers = {row.question_id: row for row in ledger.answers}
    assert answers["8.4-real-grounding-cost"].answer_status == "provisional_insufficient_data"
    assert answers["8.4-demand-pull-strength"].answer_status == "provisional_insufficient_data"
    assert answers["8.4-search-recall-freshness"].answer_status == "answered_currently_healthy"
    assert "recommendation_authority" in ledger.may_not_use_for
```

- [ ] **Step 2: Run the failing test**

```bash
cd policy-engine
uv run pytest tests/unit/runtime/quality/test_layer3_g8_health_metric_governance.py::test_g8_open_question_ledger_answers_every_vision_question_with_current_evidence -q
```

Expected: fail because the open-question ledger builder does not exist.

- [ ] **Step 3: Implement open-question answer models and builder**

Add:

```python
class Layer3G8OpenQuestionAnswerRow(_G8Model):
    question_id: str
    question: str
    answer_status: Literal[
        "answered_currently_healthy",
        "answered_currently_blocked",
        "provisional_insufficient_data",
    ]
    current_answer: str
    evidence_refs: tuple[str, ...]
    authority_boundary: str = "empirical_governance_reading_only"


class Layer3G8OpenQuestionAnswerLedger(_G8Model):
    schema_version: str = G8_SCHEMA_VERSION
    rule_version: str = G8_RULE_VERSION
    ledger_id: str = "layer3-g8://open-question-answer-ledger"
    status: Literal["pass", "blocked"]
    answers: tuple[Layer3G8OpenQuestionAnswerRow, ...]
    issue_codes: tuple[str, ...] = ()
    authoritative_for: tuple[str, ...] = G8_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G8_MAY_NOT_USE_FOR


def build_g8_open_question_answer_ledger(
    *,
    diagnosis: Layer3G8CrossMetricDiagnosis,
    ceiling_gate: Layer3G8DomainVsSearchCeilingGate,
    repo_root: str | Path = DEFAULT_REPO_ROOT,
) -> Layer3G8OpenQuestionAnswerLedger:
    rows = (
        Layer3G8OpenQuestionAnswerRow(
            question_id="8.4-waist-altitude",
            question=(
                "Is the waist vocabulary at the right altitude, or does it need "
                "a first-class dimension it currently encodes only as status?"
            ),
            answer_status=(
                "answered_currently_healthy"
                if diagnosis.semantic_loss_status in {"pass", "clean", "0"}
                else "answered_currently_blocked"
            ),
            current_answer=(
                "No forced waist change is justified by current G8 readings; semantic-loss "
                "watch remains active and any future waist change requires highest-governance rule replay."
            ),
            evidence_refs=(
                "repo://architecture/policy_design_case/layer3_health_metric_ledgers.toml#adapter-semantic-loss",
                "repo://architecture/policy_design_case/layer3_g7_health_metric_delta.toml#semantic_loss_status",
            ),
        ),
        Layer3G8OpenQuestionAnswerRow(
            question_id="8.4-real-grounding-cost",
            question=(
                "Is real grounding achievable at acceptable cost in the target domains, "
                "or is the honest equilibrium mostly abstention?"
            ),
            answer_status="provisional_insufficient_data",
            current_answer=(
                "Current G5/G7 readings prove engineering readiness and honest blockers, "
                "not a domain ceiling: G5 remains an unchanged blocker and G7 has zero "
                "grounded regional breadth."
            ),
            evidence_refs=diagnosis.current_blocker_refs,
        ),
        Layer3G8OpenQuestionAnswerRow(
            question_id="8.4-demand-pull-strength",
            question=(
                "Is demand-pull strong enough to overcome abstention inertia?"
            ),
            answer_status="provisional_insufficient_data",
            current_answer=(
                "G6 demand reaches the G5 bridge, but grounded result rate is still zero "
                "because current G5/G7 blockers remain. This is not an honesty success claim."
            ),
            evidence_refs=(
                "repo://architecture/policy_design_case/layer3_g6_demand_pull_vs_abstention_delta.json",
                "repo://architecture/policy_design_case/layer3_g6_readiness_manifest.json",
            ),
        ),
        Layer3G8OpenQuestionAnswerRow(
            question_id="8.4-search-recall-freshness",
            question=(
                "Does capability search have enough recall and freshness to distinguish "
                "honest abstention from a missed grounding path?"
            ),
            answer_status=(
                "answered_currently_healthy"
                if ceiling_gate.status != "search_ceiling_repair_required"
                else "answered_currently_blocked"
            ),
            current_answer=(
                "Current search-recall/freshness signals do not identify a search ceiling; "
                "future recall miss or stale index readings block domain-ceiling claims."
            ),
            evidence_refs=(
                "repo://architecture/policy_design_case/layer3_g1_search_recall_freshness.json",
                "repo://architecture/policy_design_case/layer3_g2_search_recall_freshness.json",
                "repo://architecture/policy_design_case/layer3_g3_search_recall_freshness.json",
                "repo://architecture/policy_design_case/layer3_gl_search_recall_freshness.json",
                "repo://architecture/policy_design_case/layer3_g7_search_recall_freshness_join.json",
            ),
        ),
        Layer3G8OpenQuestionAnswerRow(
            question_id="8.4-agent-orchestration-authority-leak",
            question=(
                "Does the bounded agent leak authority through orchestration choices in "
                "ways the current search ledger does not capture?"
            ),
            answer_status="answered_currently_healthy",
            current_answer=(
                "Current G6 conformance and public projection checks pass; G8 preserves "
                "G6 candidate and orchestration outputs as audit signals only."
            ),
            evidence_refs=(
                "repo://architecture/policy_design_case/layer3_g6_conformance_report.json",
                "repo://architecture/policy_design_case/layer3_g6_orchestration_choice_audit.json",
                "repo://architecture/policy_design_case/layer3_g6_search_ledger.json",
            ),
        ),
    )
    missing = [row.question_id for row in rows if not row.evidence_refs]
    return Layer3G8OpenQuestionAnswerLedger(
        status="blocked" if missing else "pass",
        answers=rows,
        issue_codes=("layer3_g8_open_question_answer_missing",) if missing else (),
    )
```

- [ ] **Step 4: Run the open-question test**

```bash
cd policy-engine
uv run pytest tests/unit/runtime/quality/test_layer3_g8_health_metric_governance.py::test_g8_open_question_ledger_answers_every_vision_question_with_current_evidence -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
cd policy-engine
git add src/polisyos/runtime/quality/layer3_health_metric_governance.py tests/unit/runtime/quality/test_layer3_g8_health_metric_governance.py
git commit -m "feat: answer layer3 g8 open questions"
```

## Task 8: Audit Surface, Closeout Consumer Gate, Public Projection Refs, Replay, and Conformance

**Files:**

- Modify: `src/polisyos/runtime/quality/layer3_health_metric_governance.py`
- Modify: `tests/unit/runtime/quality/test_layer3_g8_health_metric_governance.py`

- [ ] **Step 1: Write failing surface and conformance tests**

Add:

```python
def test_g8_audit_surface_is_expert_machine_and_public_projection_is_reference_only() -> None:
    bundle = g8.build_layer3_g8_bundle(REPO_ROOT)

    assert bundle.audit_surface.status == "pass"
    assert bundle.audit_surface.surface_audiences == ("EXPERT", "MACHINE")
    assert bundle.audit_surface.domain_vs_search_ceiling_status == (
        "not_claimed_current_grounding_blocker"
    )
    assert bundle.audit_surface.metric_trend_report_status == "pass"
    assert bundle.audit_surface.d44_reannotation_coverage_status == "pass"
    assert bundle.audit_surface.sealed_battery_integrity_status == "pass"
    assert bundle.closeout_signal_consumer_gate.status == "pass"
    assert bundle.closeout_signal_consumer_gate.closeout_consumption_status == (
        "readiness_visible_no_authority"
    )
    assert "closeout_authority" in bundle.closeout_signal_consumer_gate.denied_uses
    assert bundle.public_export_projection_refs.public_projection_status == (
        "out_of_scope_reference_only"
    )
    assert "recommendation_authority" in bundle.public_export_projection_refs.denied_uses
    assert bundle.replay_manifest["manifest_id"] == "layer3-g8-health-metric-governance-replay"


def test_g8_conformance_report_covers_required_negatives() -> None:
    bundle = g8.build_layer3_g8_bundle(REPO_ROOT)

    assert bundle.conformance_report.status == "pass"
    required = set(g8.G8_CONFORMANCE_NEGATIVE_EXPECTED_ISSUE_CODES)
    observed = {result["negative_id"] for result in bundle.conformance_report.negative_results}
    assert observed == required
    assert bundle.conformance_report.missing_negative_ids == ()
    assert not bundle.conformance_report.failing_negative_ids
```

- [ ] **Step 2: Run the failing tests**

```bash
cd policy-engine
uv run pytest tests/unit/runtime/quality/test_layer3_g8_health_metric_governance.py::test_g8_audit_surface_is_expert_machine_and_public_projection_is_reference_only tests/unit/runtime/quality/test_layer3_g8_health_metric_governance.py::test_g8_conformance_report_covers_required_negatives -q
```

Expected: fail because bundle/surface/closeout-consumer/conformance builders do not exist.

- [ ] **Step 3: Implement bundle, audit surface, projection refs, replay, and conformance models**

Add:

```python
G8_CONFORMANCE_NEGATIVE_EXPECTED_ISSUE_CODES: dict[str, tuple[str, ...]] = {
    "metric_improved_by_threshold_lowering": ("layer3_g8_metric_improved_by_threshold_lowering",),
    "useful_design_rate_optimization": ("layer3_g8_useful_design_rate_optimized",),
    "search_recall_miss_as_domain_ceiling": ("layer3_g8_search_recall_miss_reported_as_domain_ceiling",),
    "flat_expansion_with_current_blocker_as_domain_ceiling": ("layer3_g8_flat_expansion_reported_as_domain_ceiling_without_search_health",),
    "governance_stall_as_domain_ceiling": ("layer3_g8_governance_stall_hidden_as_domain_ceiling",),
    "abstention_inertia_as_honesty": ("layer3_g8_abstention_inertia_hidden_as_honesty",),
    "semantic_loss_hidden_by_metric_rollup": ("layer3_g8_semantic_loss_hidden_by_metric_rollup",),
    "rebasing_mutates_sealed_battery": ("layer3_g8_rebasing_mutates_sealed_battery",),
    "rebasing_leaks_gold_or_hidden_payload": ("layer3_g8_rebasing_leaks_gold_or_hidden_payload",),
    "rebasing_lowers_s14_floor": ("layer3_g8_rebasing_lowers_s14_floor",),
    "closeout_signal_used_as_authority": ("layer3_g8_metric_used_as_closeout_authority",),
    "public_projection_authority_leak": ("layer3_g8_public_projection_authority_leak",),
}


class Layer3G8MetricGovernanceAuditSurface(_G8Model):
    schema_version: str = G8_SCHEMA_VERSION
    rule_version: str = G8_RULE_VERSION
    surface_id: str = G8_SURFACE_ID
    status: Literal["pass", "blocked"]
    surface_audiences: tuple[str, ...] = ("EXPERT", "MACHINE")
    metric_registry_ref: str
    normalized_metric_signals_ref: str
    metric_trend_report_status: str
    domain_vs_search_ceiling_status: str
    d44_reannotation_coverage_status: str
    d44_rebasing_trigger_status: str
    d44_rebasing_receipt_status: str
    sealed_battery_integrity_status: str
    open_question_answer_status: str
    warning_lifecycle_status: str
    metric_gaming_firewall_status: str
    issue_codes: tuple[str, ...] = ()
    authoritative_for: tuple[str, ...] = G8_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G8_MAY_NOT_USE_FOR


class Layer3G8CloseoutSignalConsumerGate(_G8Model):
    schema_version: str = G8_SCHEMA_VERSION
    rule_version: str = G8_RULE_VERSION
    gate_id: str = "layer3-g8://closeout-signal-consumer-gate"
    status: Literal["pass", "blocked"]
    closeout_consumption_status: Literal[
        "readiness_visible_no_authority",
        "blocked_authority_leak",
    ]
    consumed_signal_refs: tuple[str, ...]
    denied_uses: tuple[str, ...] = G8_MAY_NOT_USE_FOR
    issue_codes: tuple[str, ...] = ()
    authoritative_for: tuple[str, ...] = ("layer3_g8_metric_governance_audit",)
    may_not_use_for: tuple[str, ...] = G8_MAY_NOT_USE_FOR


class Layer3G8PublicExportProjectionRefs(_G8Model):
    schema_version: str = G8_SCHEMA_VERSION
    rule_version: str = G8_RULE_VERSION
    projection_ref_id: str = "layer3-g8://public-export-projection-refs"
    public_projection_status: Literal["out_of_scope_reference_only", "blocked"]
    source_surface: str = G8_SURFACE_ID
    denied_uses: tuple[str, ...] = G8_MAY_NOT_USE_FOR
    issue_codes: tuple[str, ...] = ()


class Layer3G8ConformanceReport(_G8Model):
    schema_version: str = G8_SCHEMA_VERSION
    rule_version: str = G8_RULE_VERSION
    report_id: str = "layer3-g8://conformance-report"
    status: Literal["pass", "blocked"]
    negative_results: tuple[dict[str, Any], ...]
    missing_negative_ids: tuple[str, ...]
    failing_negative_ids: tuple[str, ...]
    issue_codes: tuple[str, ...] = ()
    authoritative_for: tuple[str, ...] = ("layer3_g8_metric_governance_audit",)
    may_not_use_for: tuple[str, ...] = G8_MAY_NOT_USE_FOR


class Layer3G8Bundle(_G8Model):
    registry: Layer3G8HealthMetricRegistry
    source_snapshot: Layer3G8MetricSourceSnapshot
    normalized_signals: Layer3G8NormalizedMetricSignals
    metric_trend_report: Layer3G8MetricTrendReport
    cross_metric_diagnosis: Layer3G8CrossMetricDiagnosis
    ceiling_gate: Layer3G8DomainVsSearchCeilingGate
    metric_gaming_firewall: Layer3G8MetricGamingFirewall
    warning_lifecycle_ledger: Layer3G8WarningLifecycleLedger
    d44_rebasing_rule: Layer3G8D44CorpusRebasingRule
    d44_reannotation_coverage_matrix: Layer3G8D44ReannotationCoverageMatrix
    d44_rebasing_trigger_ledger: Layer3G8D44RebasingTriggerLedger
    d44_rebasing_candidate_set: Layer3G8D44RebasingCandidateSet
    d44_rebasing_receipt: Layer3G8D44RebasingReceipt
    sealed_battery_integrity_join: Layer3G8SealedBatteryIntegrityJoin
    open_question_answer_ledger: Layer3G8OpenQuestionAnswerLedger
    audit_surface: Layer3G8MetricGovernanceAuditSurface
    closeout_signal_consumer_gate: Layer3G8CloseoutSignalConsumerGate
    public_export_projection_refs: Layer3G8PublicExportProjectionRefs
    replay_manifest: dict[str, Any]
    conformance_report: Layer3G8ConformanceReport
    health_metric_governance_delta: dict[str, Any]
    route_contract_registry: dict[str, Any]
    registry_ratchet_delta: dict[str, Any]


def build_layer3_g8_bundle(repo_root: str | Path = DEFAULT_REPO_ROOT) -> Layer3G8Bundle:
    registry = build_g8_health_metric_registry()
    source_snapshot = build_g8_metric_source_snapshot(repo_root)
    signals = build_g8_normalized_metric_signals(
        registry=registry,
        source_snapshot=source_snapshot,
        repo_root=repo_root,
    )
    trend_report = build_g8_metric_trend_report(registry=registry, signals=signals)
    diagnosis = build_g8_cross_metric_diagnosis(signals=signals, repo_root=repo_root)
    ceiling_gate = build_g8_domain_vs_search_ceiling_gate(diagnosis=diagnosis)
    metric_gaming = build_g8_metric_gaming_firewall(metric_changes=[])
    warnings = build_g8_default_warning_lifecycle_ledger(diagnosis=diagnosis)
    rebasing_rule = build_g8_d44_corpus_rebasing_rule(repo_root=repo_root)
    coverage_matrix = build_g8_d44_reannotation_coverage_matrix(
        rule=rebasing_rule,
        repo_root=repo_root,
    )
    trigger_ledger = build_g8_d44_rebasing_trigger_ledger(repo_root=repo_root)
    candidate_set = build_g8_d44_rebasing_candidate_set(repo_root=repo_root)
    receipt = build_g8_d44_rebasing_receipt(
        rule=rebasing_rule,
        candidate_set=candidate_set,
        repo_root=repo_root,
    )
    sealed_join = build_g8_sealed_battery_integrity_join(repo_root=repo_root)
    open_questions = build_g8_open_question_answer_ledger(
        diagnosis=diagnosis,
        ceiling_gate=ceiling_gate,
        repo_root=repo_root,
    )
    audit_surface = build_g8_metric_governance_audit_surface(
        registry=registry,
        signals=signals,
        trend_report=trend_report,
        ceiling_gate=ceiling_gate,
        metric_gaming_firewall=metric_gaming,
        warning_lifecycle_ledger=warnings,
        d44_reannotation_coverage_matrix=coverage_matrix,
        d44_rebasing_trigger_ledger=trigger_ledger,
        rebasing_receipt=receipt,
        sealed_battery_integrity_join=sealed_join,
        open_question_ledger=open_questions,
    )
    closeout_gate = build_g8_closeout_signal_consumer_gate(audit_surface=audit_surface)
    public_refs = build_g8_public_export_projection_refs(audit_surface=audit_surface)
    replay_manifest = build_g8_replay_manifest(audit_surface=audit_surface)
    conformance = build_g8_conformance_report(repo_root=repo_root)
    return Layer3G8Bundle(
        registry=registry,
        source_snapshot=source_snapshot,
        normalized_signals=signals,
        metric_trend_report=trend_report,
        cross_metric_diagnosis=diagnosis,
        ceiling_gate=ceiling_gate,
        metric_gaming_firewall=metric_gaming,
        warning_lifecycle_ledger=warnings,
        d44_rebasing_rule=rebasing_rule,
        d44_reannotation_coverage_matrix=coverage_matrix,
        d44_rebasing_trigger_ledger=trigger_ledger,
        d44_rebasing_candidate_set=candidate_set,
        d44_rebasing_receipt=receipt,
        sealed_battery_integrity_join=sealed_join,
        open_question_answer_ledger=open_questions,
        audit_surface=audit_surface,
        closeout_signal_consumer_gate=closeout_gate,
        public_export_projection_refs=public_refs,
        replay_manifest=replay_manifest,
        conformance_report=conformance,
        health_metric_governance_delta=_g8_health_metric_governance_delta(
            registry=registry,
            trend_report=trend_report,
            ceiling_gate=ceiling_gate,
        ),
        route_contract_registry=_g8_route_contract_registry(audit_surface),
        registry_ratchet_delta=_g8_registry_ratchet_delta(conformance),
    )
```

Add builders:

```python
def build_g8_metric_governance_audit_surface(
    *,
    registry: Layer3G8HealthMetricRegistry,
    signals: Layer3G8NormalizedMetricSignals,
    trend_report: Layer3G8MetricTrendReport,
    ceiling_gate: Layer3G8DomainVsSearchCeilingGate,
    metric_gaming_firewall: Layer3G8MetricGamingFirewall,
    warning_lifecycle_ledger: Layer3G8WarningLifecycleLedger,
    d44_reannotation_coverage_matrix: Layer3G8D44ReannotationCoverageMatrix,
    d44_rebasing_trigger_ledger: Layer3G8D44RebasingTriggerLedger,
    rebasing_receipt: Layer3G8D44RebasingReceipt,
    sealed_battery_integrity_join: Layer3G8SealedBatteryIntegrityJoin,
    open_question_ledger: Layer3G8OpenQuestionAnswerLedger,
) -> Layer3G8MetricGovernanceAuditSurface:
    issues = _dedupe(
        (
            *registry.issue_codes,
            *signals.issue_codes,
            *trend_report.issue_codes,
            *metric_gaming_firewall.issue_codes,
            *warning_lifecycle_ledger.issue_codes,
            *d44_reannotation_coverage_matrix.issue_codes,
            *d44_rebasing_trigger_ledger.issue_codes,
            *rebasing_receipt.issue_codes,
            *sealed_battery_integrity_join.issue_codes,
            *open_question_ledger.issue_codes,
        )
    )
    blocking = set(issues).intersection(
        {
            "layer3_g8_metric_source_missing",
            "layer3_g8_metric_alias_unresolved",
            "layer3_g8_metric_trend_report_missing",
            "layer3_g8_metric_improved_by_threshold_lowering",
            "layer3_g8_d44_reannotation_coverage_missing",
            "layer3_g8_d44_rebasing_trigger_missing",
            "layer3_g8_rebasing_mutates_sealed_battery",
            "layer3_g8_rebasing_leaks_gold_or_hidden_payload",
            "layer3_g8_rebasing_lowers_s14_floor",
            "layer3_g8_rebasing_without_freeze_hash",
        }
    )
    return Layer3G8MetricGovernanceAuditSurface(
        status="blocked" if blocking else "pass",
        metric_registry_ref="repo://architecture/policy_design_case/layer3_g8_health_metric_registry.json",
        normalized_metric_signals_ref="repo://architecture/policy_design_case/layer3_g8_normalized_metric_signals.json",
        metric_trend_report_status=trend_report.status,
        domain_vs_search_ceiling_status=ceiling_gate.status,
        d44_reannotation_coverage_status=d44_reannotation_coverage_matrix.status,
        d44_rebasing_trigger_status=d44_rebasing_trigger_ledger.status,
        d44_rebasing_receipt_status=rebasing_receipt.status,
        sealed_battery_integrity_status=sealed_battery_integrity_join.status,
        open_question_answer_status=open_question_ledger.status,
        warning_lifecycle_status=warning_lifecycle_ledger.status,
        metric_gaming_firewall_status=metric_gaming_firewall.status,
        issue_codes=issues,
    )


def build_g8_closeout_signal_consumer_gate(
    *,
    audit_surface: Layer3G8MetricGovernanceAuditSurface,
    authority_role: str = "readiness_visibility_only",
) -> Layer3G8CloseoutSignalConsumerGate:
    issues: list[str] = []
    if authority_role != "readiness_visibility_only":
        issues.append("layer3_g8_metric_used_as_closeout_authority")
    if "closeout_authority" not in audit_surface.may_not_use_for:
        issues.append("layer3_g8_metric_used_as_closeout_authority")
    return Layer3G8CloseoutSignalConsumerGate(
        status="blocked" if issues else "pass",
        closeout_consumption_status=(
            "blocked_authority_leak" if issues else "readiness_visible_no_authority"
        ),
        consumed_signal_refs=(
            "repo://architecture/policy_design_case/layer3_g8_metric_governance_audit_surface.json",
            "repo://architecture/policy_design_case/layer3_g8_domain_vs_search_ceiling_gate.json",
            "repo://architecture/policy_design_case/layer3_g8_warning_lifecycle_ledger.json",
        ),
        issue_codes=_dedupe(issues),
    )


def build_g8_public_export_projection_refs(
    *,
    audit_surface: Layer3G8MetricGovernanceAuditSurface,
    authority_role: str = "projection_only",
) -> Layer3G8PublicExportProjectionRefs:
    issues: list[str] = []
    if authority_role != "projection_only":
        issues.append("layer3_g8_public_projection_authority_leak")
    return Layer3G8PublicExportProjectionRefs(
        public_projection_status="blocked" if issues else "out_of_scope_reference_only",
        issue_codes=_dedupe(issues),
    )


def build_g8_replay_manifest(
    *,
    audit_surface: Layer3G8MetricGovernanceAuditSurface,
) -> dict[str, Any]:
    return {
        "schema_version": G8_SCHEMA_VERSION,
        "rule_version": G8_RULE_VERSION,
        "manifest_id": "layer3-g8-health-metric-governance-replay",
        "status": "pass" if audit_surface.status in {"pass", "blocked"} else "blocked",
        "source_refs": [
            "repo://architecture/policy_design_case/layer3_health_metric_ledgers.toml",
            "repo://architecture/policy_design_case/layer3_g1_search_recall_freshness.json",
            "repo://architecture/policy_design_case/layer3_g2_search_recall_freshness.json",
            "repo://architecture/policy_design_case/layer3_g3_search_recall_freshness.json",
            "repo://architecture/policy_design_case/layer3_gl_search_recall_freshness.json",
            "repo://architecture/policy_design_case/layer3_g4_governance_throughput_delta.json",
            "repo://architecture/policy_design_case/layer3_g5_readiness_manifest.json",
            "repo://architecture/policy_design_case/layer3_g5_dependency_health_metric_snapshot.json",
            "repo://architecture/policy_design_case/layer3_g6_demand_pull_vs_abstention_delta.json",
            "repo://architecture/policy_design_case/layer3_g6_readiness_manifest.json",
            "repo://architecture/policy_design_case/layer3_g7_search_recall_freshness_join.json",
            "repo://architecture/policy_design_case/layer3_g7_readiness_manifest.json",
            "repo://architecture/policy_design_case/layer2_s14_universality_assurance_manifest.json",
        ],
        "audit_surface_ref": "repo://architecture/policy_design_case/layer3_g8_metric_governance_audit_surface.json",
        "issue_codes": [],
        "authoritative_for": list(G8_AUTHORITATIVE_FOR),
        "may_not_use_for": list(G8_MAY_NOT_USE_FOR),
    }
```

Add conformance:

```python
def build_g8_conformance_report(
    *,
    repo_root: str | Path = DEFAULT_REPO_ROOT,
) -> Layer3G8ConformanceReport:
    negative_results: list[dict[str, Any]] = []
    for negative_id, expected in G8_CONFORMANCE_NEGATIVE_EXPECTED_ISSUE_CODES.items():
        observed = _observed_g8_negative_issue_codes(negative_id)
        missing = sorted(set(expected) - set(observed))
        negative_results.append(
            {
                "negative_id": negative_id,
                "expected_issue_codes": list(expected),
                "observed_issue_codes": list(observed),
                "missing_issue_codes": missing,
                "status": "fail" if missing else "pass",
                "probe_ref": f"layer3-g8://conformance/negative/{negative_id}",
            }
        )
    observed_ids = {str(result["negative_id"]) for result in negative_results}
    missing_negative_ids = tuple(
        sorted(set(G8_CONFORMANCE_NEGATIVE_EXPECTED_ISSUE_CODES) - observed_ids)
    )
    failing = tuple(
        str(result["negative_id"])
        for result in negative_results
        if result["status"] != "pass"
    )
    issue_codes = tuple(
        sorted(
            {
                code
                for result in negative_results
                for code in result["missing_issue_codes"]
            }
        )
    )
    return Layer3G8ConformanceReport(
        status="blocked" if missing_negative_ids or failing else "pass",
        negative_results=tuple(negative_results),
        missing_negative_ids=missing_negative_ids,
        failing_negative_ids=failing,
        issue_codes=(
            issue_codes
            or (("layer3_g8_conformance_negative_missing",) if missing_negative_ids else ())
        ),
    )


def _observed_g8_negative_issue_codes(negative_id: str) -> tuple[str, ...]:
    if negative_id == "metric_improved_by_threshold_lowering":
        return build_g8_metric_gaming_firewall(
            metric_changes=[
                {
                    "metric_id": "demand-pull-vs-abstention",
                    "claimed_improvement": True,
                    "change_class": "threshold_lowered",
                    "source_ref": "layer3-g8://negative/threshold-lowering",
                }
            ]
        ).issue_codes
    if negative_id == "useful_design_rate_optimization":
        return build_g8_metric_gaming_firewall(
            metric_changes=[
                {
                    "metric_id": "envelope-expansion-rate",
                    "claimed_improvement": True,
                    "change_class": "metric_target_changed",
                    "target_metric": "useful_design_rate",
                    "source_ref": "layer3-g8://negative/useful-design-rate",
                }
            ]
        ).issue_codes
    if negative_id == "search_recall_miss_as_domain_ceiling":
        diagnosis = build_g8_cross_metric_diagnosis(
            signals=_negative_signal_set(
                search_status="search_ceiling",
                governance_status="pass",
                demand_status="pass",
                semantic_status="pass",
                expansion_status="flat",
            )
        )
        return domain_ceiling_claim_issue_codes(
            diagnosis=diagnosis,
            claimed_domain_ceiling=True,
        )
    if negative_id == "flat_expansion_with_current_blocker_as_domain_ceiling":
        diagnosis = Layer3G8CrossMetricDiagnosis(
            status="pass",
            envelope_expansion_status="flat",
            semantic_loss_status="pass",
            governance_throughput_status="pass",
            demand_pull_status="pass",
            search_recall_freshness_status="pass",
            effective_independence_status="sufficient",
            effective_independent_evidence_count=2,
            effective_independence_source_ref=(
                "repo://architecture/policy_design_case/layer3_g5_effective_evidence_independence.json"
                "#independence_map_payload.effective_mass_report"
            ),
            current_blocker_refs=("repo://architecture/policy_design_case/layer3_g7_readiness_manifest.json#g7_region_grounded_case_count",),
            diagnoses=("current_grounding_blocker",),
        )
        return domain_ceiling_claim_issue_codes(
            diagnosis=diagnosis,
            claimed_domain_ceiling=True,
        )
    if negative_id == "governance_stall_as_domain_ceiling":
        diagnosis = build_g8_cross_metric_diagnosis(
            signals=_negative_signal_set(
                search_status="pass",
                governance_status="stalled",
                demand_status="pass",
                semantic_status="pass",
                expansion_status="flat",
            )
        )
        return domain_ceiling_claim_issue_codes(
            diagnosis=diagnosis,
            claimed_domain_ceiling=True,
        )
    if negative_id == "abstention_inertia_as_honesty":
        diagnosis = build_g8_cross_metric_diagnosis(
            signals=_negative_signal_set(
                search_status="pass",
                governance_status="pass",
                demand_status="abstention_inertia",
                semantic_status="pass",
                expansion_status="flat",
            )
        )
        return domain_ceiling_claim_issue_codes(
            diagnosis=diagnosis,
            claimed_domain_ceiling=True,
        )
    if negative_id == "semantic_loss_hidden_by_metric_rollup":
        diagnosis = build_g8_cross_metric_diagnosis(
            signals=_negative_signal_set(
                search_status="pass",
                governance_status="pass",
                demand_status="pass",
                semantic_status="lossy",
                expansion_status="flat",
            )
        )
        return diagnosis.issue_codes
    if negative_id in {
        "rebasing_mutates_sealed_battery",
        "rebasing_leaks_gold_or_hidden_payload",
        "rebasing_lowers_s14_floor",
    }:
        return build_g8_sealed_battery_integrity_join(
            rebasing_attempt={
                "pre_rebase_freeze_hash": "sha256:" + "1" * 64,
                "post_rebase_freeze_hash": "sha256:" + "2" * 64,
                "floor_change": "lowered",
                "hidden_payload_ref": "sealed_gold_label_ref://leak",
            }
        ).issue_codes
    if negative_id == "closeout_signal_used_as_authority":
        return build_g8_closeout_signal_consumer_gate(
            audit_surface=Layer3G8MetricGovernanceAuditSurface(
                status="pass",
                metric_registry_ref="repo://test/registry",
                normalized_metric_signals_ref="repo://test/signals",
                metric_trend_report_status="pass",
                domain_vs_search_ceiling_status="not_claimed_current_grounding_blocker",
                d44_reannotation_coverage_status="pass",
                d44_rebasing_trigger_status="pass_no_rebase_due",
                d44_rebasing_receipt_status="pass_no_rebase_required",
                sealed_battery_integrity_status="pass",
                open_question_answer_status="pass",
                warning_lifecycle_status="pass",
                metric_gaming_firewall_status="pass",
            ),
            authority_role="closeout_authority",
        ).issue_codes
    if negative_id == "public_projection_authority_leak":
        return build_g8_public_export_projection_refs(
            audit_surface=Layer3G8MetricGovernanceAuditSurface(
                status="pass",
                metric_registry_ref="repo://test/registry",
                normalized_metric_signals_ref="repo://test/signals",
                metric_trend_report_status="pass",
                domain_vs_search_ceiling_status="not_claimed_current_grounding_blocker",
                d44_reannotation_coverage_status="pass",
                d44_rebasing_trigger_status="pass_no_rebase_due",
                d44_rebasing_receipt_status="pass_no_rebase_required",
                sealed_battery_integrity_status="pass",
                open_question_answer_status="pass",
                warning_lifecycle_status="pass",
                metric_gaming_firewall_status="pass",
            ),
            authority_role="claim_authority",
        ).issue_codes
    return ()


def _negative_signal_set(
    *,
    search_status: str,
    governance_status: str,
    demand_status: str,
    semantic_status: str,
    expansion_status: str,
) -> Layer3G8NormalizedMetricSignals:
    return Layer3G8NormalizedMetricSignals(
        status="pass",
        signals=(
            Layer3G8NormalizedMetricSignal(
                signal_id="negative://envelope",
                slice_id="G8",
                metric_id="envelope-expansion-rate",
                raw_key="envelope-expansion-rate",
                raw_value=expansion_status,
                status=expansion_status,
                raw_source_ref="repo://negative#envelope",
                source_digest="sha256:" + "1" * 64,
                freshness_status="fresh_committed",
                authority_boundary_status="pass",
                observed_at="2026-06-10T00:00:00Z",
            ),
            Layer3G8NormalizedMetricSignal(
                signal_id="negative://semantic-loss",
                slice_id="G8",
                metric_id="adapter-semantic-loss",
                raw_key="adapter-semantic-loss",
                raw_value=semantic_status,
                status=semantic_status,
                raw_source_ref="repo://negative#semantic",
                source_digest="sha256:" + "1" * 64,
                freshness_status="fresh_committed",
                authority_boundary_status="pass",
                observed_at="2026-06-10T00:00:00Z",
            ),
            Layer3G8NormalizedMetricSignal(
                signal_id="negative://governance",
                slice_id="G8",
                metric_id="governance-throughput",
                raw_key="governance-throughput",
                raw_value=governance_status,
                status=governance_status,
                raw_source_ref="repo://negative#governance",
                source_digest="sha256:" + "1" * 64,
                freshness_status="fresh_committed",
                authority_boundary_status="pass",
                observed_at="2026-06-10T00:00:00Z",
            ),
            Layer3G8NormalizedMetricSignal(
                signal_id="negative://demand",
                slice_id="G8",
                metric_id="demand-pull-vs-abstention",
                raw_key="demand-pull-vs-abstention",
                raw_value=demand_status,
                status=demand_status,
                raw_source_ref="repo://negative#demand",
                source_digest="sha256:" + "1" * 64,
                freshness_status="fresh_committed",
                authority_boundary_status="pass",
                observed_at="2026-06-10T00:00:00Z",
            ),
            Layer3G8NormalizedMetricSignal(
                signal_id="negative://search",
                slice_id="G8",
                metric_id="search-recall@known-seeds+index-staleness",
                raw_key="search-recall@known-seeds+index-staleness",
                raw_value=search_status,
                status=search_status,
                raw_source_ref="repo://negative#search",
                source_digest="sha256:" + "1" * 64,
                freshness_status="fresh_committed",
                authority_boundary_status="pass",
                observed_at="2026-06-10T00:00:00Z",
            ),
        ),
    )


def _g8_health_metric_governance_delta(
    *,
    registry: Layer3G8HealthMetricRegistry,
    trend_report: Layer3G8MetricTrendReport,
    ceiling_gate: Layer3G8DomainVsSearchCeilingGate,
) -> dict[str, Any]:
    return {
        "schema_version": G8_SCHEMA_VERSION,
        "rule_version": G8_RULE_VERSION,
        "health_metric_governance_delta": {
            "metric_ids": list(G8_CANONICAL_METRIC_IDS),
            "metric_governance_status": registry.status,
            "metric_trend_report_status": trend_report.status,
            "metric_trend_refs": [
                "repo://architecture/policy_design_case/layer3_g8_metric_trend_report.json"
            ],
            "domain_vs_search_ceiling_status": ceiling_gate.status,
            "authority_boundary": "governed_signal_never_authority",
        },
    }


def _g8_route_contract_registry(
    audit_surface: Layer3G8MetricGovernanceAuditSurface,
) -> dict[str, Any]:
    return {
        "schema_version": G8_SCHEMA_VERSION,
        "rule_version": G8_RULE_VERSION,
        "route_contract_registry_kind": "generated_metric_governance_route_contract_registry",
        "surface_id": audit_surface.surface_id,
        "producer": "src/polisyos/runtime/quality/layer3_health_metric_governance.py",
        "validator": "tools/quality/validation/check_policy_design_case_layer3_g8_readiness.py",
        "metric_trend_report": "architecture/policy_design_case/layer3_g8_metric_trend_report.json",
        "closeout_consumer_gate": "architecture/policy_design_case/layer3_g8_closeout_signal_consumer_gate.json",
        "may_not_use_for": list(G8_MAY_NOT_USE_FOR),
    }


def _g8_registry_ratchet_delta(
    conformance_report: Layer3G8ConformanceReport,
) -> dict[str, Any]:
    return {
        "schema_version": G8_SCHEMA_VERSION,
        "rule_version": G8_RULE_VERSION,
        "ratchet_id": "layer3_g8_registry_ratchet_delta",
        "status": "pass" if conformance_report.status == "pass" else "blocked",
        "negative_count": len(conformance_report.negative_results),
        "missing_negative_ids": list(conformance_report.missing_negative_ids),
        "failing_negative_ids": list(conformance_report.failing_negative_ids),
    }
```

- [ ] **Step 4: Run surface/conformance tests**

```bash
cd policy-engine
uv run pytest tests/unit/runtime/quality/test_layer3_g8_health_metric_governance.py::test_g8_audit_surface_is_expert_machine_and_public_projection_is_reference_only tests/unit/runtime/quality/test_layer3_g8_health_metric_governance.py::test_g8_conformance_report_covers_required_negatives -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
cd policy-engine
git add src/polisyos/runtime/quality/layer3_health_metric_governance.py tests/unit/runtime/quality/test_layer3_g8_health_metric_governance.py
git commit -m "feat: surface layer3 g8 metric governance gates"
```

## Task 9: Readiness Validator, Artifact Writer, and Registrations

**Files:**

- Create: `tools/quality/validation/check_policy_design_case_layer3_g8_readiness.py`
- Modify: `tests/repo_quality/tools/test_policy_design_case_layer3_g8_readiness.py`
- Create: `tests/repo_quality/tools/test_policy_design_case_layer3_g8_readiness_cli.py`
- Modify: `architecture/generated_artifacts.toml`
- Modify: `architecture/policy_design_case/inventory.json`
- Modify: `docs/reference/generated-artifacts.md`
- Modify: `docs/reference/public-surface.md`
- Modify: `docs/reference/documentation-inventory.md`
- Modify: `docs/reference/index.md`
- Modify: `src/polisyos/runtime/quality/README.md`

- [ ] **Step 1: Write failing readiness tests**

Add to `tests/repo_quality/tools/test_policy_design_case_layer3_g8_readiness.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

import polisyos.runtime.quality.layer3_health_metric_governance as g8
from tools.quality.validation import check_policy_design_case_layer3_g8_readiness as validator

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_layer3_g8_readiness_declares_exact_artifact_contract() -> None:
    assert validator.G8_SCHEMA_VERSION == g8.G8_SCHEMA_VERSION
    assert validator.G8_RULE_VERSION == g8.G8_RULE_VERSION
    assert validator.G8_GENERATED_ARTIFACT_FAMILY_ID == g8.G8_GENERATED_ARTIFACT_FAMILY_ID
    assert {path.as_posix() for path in validator.EXPECTED_ARTIFACT_PATHS} == {
        "architecture/policy_design_case/layer3_g8_health_metric_registry.json",
        "architecture/policy_design_case/layer3_g8_metric_source_snapshot.json",
        "architecture/policy_design_case/layer3_g8_normalized_metric_signals.json",
        "architecture/policy_design_case/layer3_g8_metric_trend_report.json",
        "architecture/policy_design_case/layer3_g8_cross_metric_diagnosis.json",
        "architecture/policy_design_case/layer3_g8_domain_vs_search_ceiling_gate.json",
        "architecture/policy_design_case/layer3_g8_metric_gaming_firewall.json",
        "architecture/policy_design_case/layer3_g8_warning_lifecycle_ledger.json",
        "architecture/policy_design_case/layer3_g8_d44_corpus_rebasing_rule.json",
        "architecture/policy_design_case/layer3_g8_d44_reannotation_coverage_matrix.json",
        "architecture/policy_design_case/layer3_g8_d44_rebasing_trigger_ledger.json",
        "architecture/policy_design_case/layer3_g8_d44_rebasing_candidate_set.json",
        "architecture/policy_design_case/layer3_g8_d44_rebasing_receipt.json",
        "architecture/policy_design_case/layer3_g8_sealed_battery_integrity_join.json",
        "architecture/policy_design_case/layer3_g8_open_question_answer_ledger.json",
        "architecture/policy_design_case/layer3_g8_metric_governance_audit_surface.json",
        "architecture/policy_design_case/layer3_g8_closeout_signal_consumer_gate.json",
        "architecture/policy_design_case/layer3_g8_public_export_projection_refs.json",
        "architecture/policy_design_case/layer3_g8_replay_manifest.json",
        "architecture/policy_design_case/layer3_g8_conformance_report.json",
        "architecture/policy_design_case/layer3_g8_health_metric_governance_delta.toml",
        "architecture/policy_design_case/layer3_g8_metric_governance_route_contract_registry.toml",
        "architecture/policy_design_case/layer3_g8_registry_ratchet_delta.json",
        "architecture/policy_design_case/layer3_g8_readiness_manifest.json",
    }
    assert set(validator.EXPECTED_MANIFEST_DRIFT_KEYS) == set(g8.EXPECTED_MANIFEST_DRIFT_KEYS)


def test_layer3_g8_readiness_writes_and_passes_current_blocked_value_state() -> None:
    write_report = validator.validate_layer3_g8_readiness(REPO_ROOT, write=True)
    validation = validator.validate_layer3_g8_readiness(REPO_ROOT)

    assert write_report["status"] == "pass"
    assert validation["status"] == "pass"
    assert validation["artifacts"]["missing_persisted_artifact_paths"] == []
    summary = validation["summary"]
    assert summary["g8_metric_governance_status"] == "pass"
    assert summary["g8_canonical_metric_count"] == 5
    assert summary["g8_metric_source_count"] >= 44
    assert summary["g8_metric_trend_report_status"] == "pass"
    assert summary["g8_effective_independence_status"] == "sufficient"
    assert summary["g8_effective_independent_evidence_count"] == 2
    assert summary["g8_domain_vs_search_ceiling_status"] == (
        "not_claimed_current_grounding_blocker"
    )
    assert summary["g8_d44_reannotation_coverage_status"] == "pass"
    assert summary["g8_d44_rebasing_trigger_status"] == "pass_no_rebase_due"
    assert summary["g8_d44_rebasing_receipt_status"] == "pass_no_rebase_required"
    assert summary["g8_sealed_battery_integrity_status"] == "pass"
    assert summary["g8_closeout_signal_consumer_status"] == "pass"
    assert summary["g8_open_question_answer_status"] == "pass"
    assert summary["g8_manifest_runtime_drift_key_count"] == 0
    assert summary["expected_artifact_count"] == len(validator.EXPECTED_ARTIFACT_PATHS)


def test_layer3_g8_readiness_requires_registration_inventory_and_docs() -> None:
    validation = validator.validate_layer3_g8_readiness(REPO_ROOT)

    assert validation["status"] == "pass"
    assert validation["summary"]["g8_generated_artifacts_registration_status"] == "pass"
    assert validation["summary"]["g8_inventory_surface_status"] == "pass"
    assert validation["summary"]["g8_reference_docs_status"] == "pass"
    assert validation["summary"]["g8_route_contract_registry_status"] == "pass"
    assert validation["summary"]["g8_registry_ratchet_status"] == "pass"


def test_layer3_g8_write_path_must_include_every_expected_artifact(monkeypatch: Any) -> None:
    omitted = Path("architecture/policy_design_case/layer3_g8_replay_manifest.json")
    expected_paths = tuple(
        Path(path) for path in sorted({p.as_posix() for p in validator.EXPECTED_ARTIFACT_PATHS})
    )
    monkeypatch.setattr(validator, "EXPECTED_ARTIFACT_PATHS", expected_paths)
    monkeypatch.setattr(
        validator,
        "_write_artifacts",
        lambda _repo_root, _bundle: [
            path.as_posix() for path in expected_paths if path != omitted
        ],
    )

    validation = validator.validate_layer3_g8_readiness(REPO_ROOT, write=True)

    assert validation["status"] == "fail"
    assert "layer3_g8_persisted_artifact_missing" in {
        issue["code"] for issue in validation["issues"]
    }


def test_layer3_g8_readiness_fails_when_conformance_negative_is_missing(
    monkeypatch: Any,
) -> None:
    def failing_conformance_report(**_kwargs: Any) -> g8.Layer3G8ConformanceReport:
        return g8.Layer3G8ConformanceReport(
            status="blocked",
            negative_results=(),
            missing_negative_ids=("public_projection_authority_leak",),
            failing_negative_ids=(),
            issue_codes=("layer3_g8_conformance_negative_missing",),
        )

    monkeypatch.setattr(g8, "build_g8_conformance_report", failing_conformance_report)
    validation = validator.validate_layer3_g8_readiness(REPO_ROOT, write=True)

    assert validation["status"] == "fail"
    assert validation["summary"]["g8_conformance_status"] == "blocked"
    assert "layer3_g8_conformance_negative_missing" in {
        issue["code"] for issue in validation["issues"]
    }
```

Add to `tests/repo_quality/tools/test_policy_design_case_layer3_g8_readiness_cli.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import polisyos.runtime.quality.layer3_health_metric_governance as g8
from tools.quality.validation import check_policy_design_case_layer3_g8_readiness as validator

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_layer3_g8_readiness_cli_delegates_to_validator_and_reports_issue_codes(
    monkeypatch: Any,
    tmp_path: Path,
    capsys: Any,
) -> None:
    calls: list[tuple[Path, bool]] = []

    def fake_validate_layer3_g8_readiness(
        repo_root: Path,
        *,
        write: bool = False,
    ) -> dict[str, Any]:
        calls.append((Path(repo_root), write))
        return {
            "schema_version": g8.G8_SCHEMA_VERSION,
            "status": "fail",
            "issues": [
                {
                    "code": "layer3_g8_conformance_negative_missing",
                    "path": "architecture/policy_design_case/layer3_g8_conformance_report.json",
                    "message": "G8 conformance report must pass all required negative probes.",
                }
            ],
            "summary": {
                "schema_version": g8.G8_SCHEMA_VERSION,
                "g8_conformance_status": "blocked",
            },
            "artifacts": {},
            "write": write,
        }

    monkeypatch.setattr(
        validator,
        "validate_layer3_g8_readiness",
        fake_validate_layer3_g8_readiness,
    )
    output = tmp_path / "layer3-g8-readiness.json"

    exit_code = validator.main(
        [
            "--repo-root",
            str(REPO_ROOT),
            "--output",
            str(output),
            "--output-format",
            "json",
        ]
    )
    stdout = capsys.readouterr().out
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert exit_code == 1
    assert calls == [(REPO_ROOT, False)]
    assert payload["status"] == "fail"
    assert payload["issues"][0]["code"] == "layer3_g8_conformance_negative_missing"
    assert "layer3_g8_conformance_negative_missing" in stdout


def test_layer3_g8_readiness_cli_write_mode_reports_exact_artifact_paths(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    expected = sorted(path.as_posix() for path in validator.EXPECTED_ARTIFACT_PATHS)

    monkeypatch.setattr(
        validator,
        "validate_layer3_g8_readiness",
        lambda repo_root, *, write=False: {
            "schema_version": g8.G8_SCHEMA_VERSION,
            "status": "pass",
            "issues": [],
            "summary": {"schema_version": g8.G8_SCHEMA_VERSION},
            "artifacts": {"written_artifact_paths": expected},
            "write": write,
        },
    )
    output = tmp_path / "layer3-g8-write.json"

    exit_code = validator.main(
        [
            "--repo-root",
            str(REPO_ROOT),
            "--write",
            "--output",
            str(output),
            "--output-format",
            "json",
        ]
    )
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["write"] is True
    assert sorted(payload["artifacts"]["written_artifact_paths"]) == expected
```

- [ ] **Step 2: Run failing readiness tests**

```bash
cd policy-engine
uv run pytest tests/repo_quality/tools/test_policy_design_case_layer3_g8_readiness.py tests/repo_quality/tools/test_policy_design_case_layer3_g8_readiness_cli.py -q
```

Expected: fail because the validator module and registrations do not exist.

- [ ] **Step 3: Implement the readiness validator**

Create `tools/quality/validation/check_policy_design_case_layer3_g8_readiness.py`:

```python
#!/usr/bin/env python3
"""Validate and optionally persist the Layer 3 G8 health-metric governance bundle."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from tools.lib.fs import atomic_write_text

import polisyos.runtime.quality.layer3_health_metric_governance as g8

REPO_ROOT = Path(__file__).resolve().parents[3]
POLICY_DESIGN_CASE_DIR = Path("architecture/policy_design_case")

G8_SCHEMA_VERSION = g8.G8_SCHEMA_VERSION
G8_RULE_VERSION = g8.G8_RULE_VERSION
G8_GENERATED_ARTIFACT_FAMILY_ID = g8.G8_GENERATED_ARTIFACT_FAMILY_ID
EXPECTED_ARTIFACT_PATHS = g8.EXPECTED_ARTIFACT_PATHS
EXPECTED_MANIFEST_DRIFT_KEYS = g8.EXPECTED_MANIFEST_DRIFT_KEYS

READINESS_MANIFEST_PATH = POLICY_DESIGN_CASE_DIR / "layer3_g8_readiness_manifest.json"
GENERATED_ARTIFACTS_TOML_PATH = Path("architecture/generated_artifacts.toml")
INVENTORY_PATH = POLICY_DESIGN_CASE_DIR / "inventory.json"
GENERATED_ARTIFACTS_DOC_PATH = Path("docs/reference/generated-artifacts.md")
PUBLIC_SURFACE_DOC_PATH = Path("docs/reference/public-surface.md")
DOCUMENTATION_INVENTORY_PATH = Path("docs/reference/documentation-inventory.md")
REFERENCE_INDEX_PATH = Path("docs/reference/index.md")
RUNTIME_QUALITY_README_PATH = Path("src/polisyos/runtime/quality/README.md")


def validate_layer3_g8_readiness(repo_root: Path, *, write: bool = False) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    bundle = g8.build_layer3_g8_bundle(root)
    written_paths = _write_artifacts(root, bundle) if write else []
    registration_statuses = _registration_statuses(root)
    readiness_manifest = _readiness_manifest(
        bundle=bundle,
        drift_keys=(),
        registration_statuses=registration_statuses,
    )
    if write:
        _write_json(_resolve_repo_path(root, READINESS_MANIFEST_PATH), readiness_manifest)
        written_paths.append(READINESS_MANIFEST_PATH.as_posix())
    drift_keys = _manifest_runtime_drift_keys(root, readiness_manifest)
    issues: list[dict[str, str]] = []
    issues.extend(_validate_persisted_artifacts(root))
    issues.extend(_validate_written_artifact_set(written_paths) if write else [])
    issues.extend(_manifest_runtime_drift_issues(drift_keys))
    issues.extend(_registration_issues(registration_statuses))
    issues.extend(_validate_runtime_surfaces(bundle))
    normalized = _dedupe_issues(issues)
    summary = _summary(
        bundle=bundle,
        drift_keys=drift_keys,
        registration_statuses=registration_statuses,
    )
    return {
        "schema_version": G8_SCHEMA_VERSION,
        "rule_version": G8_RULE_VERSION,
        "status": "fail" if normalized else "pass",
        "issues": normalized,
        "summary": summary,
        "artifacts": {
            "expected_artifact_paths": [path.as_posix() for path in EXPECTED_ARTIFACT_PATHS],
            "written_artifact_paths": written_paths,
            "missing_persisted_artifact_paths": [
                path.as_posix()
                for path in EXPECTED_ARTIFACT_PATHS
                if not _resolve_repo_path(root, path).exists()
            ],
        },
        "write": write,
        "issue_code_dictionary": list(g8.ALL_ISSUE_CODES),
    }
```

Add writer helpers:

```python
def _write_artifacts(repo_root: Path, bundle: g8.Layer3G8Bundle) -> list[str]:
    payloads: dict[Path, Any] = {
        POLICY_DESIGN_CASE_DIR / "layer3_g8_health_metric_registry.json": bundle.registry,
        POLICY_DESIGN_CASE_DIR / "layer3_g8_metric_source_snapshot.json": bundle.source_snapshot,
        POLICY_DESIGN_CASE_DIR / "layer3_g8_normalized_metric_signals.json": bundle.normalized_signals,
        POLICY_DESIGN_CASE_DIR / "layer3_g8_metric_trend_report.json": bundle.metric_trend_report,
        POLICY_DESIGN_CASE_DIR / "layer3_g8_cross_metric_diagnosis.json": bundle.cross_metric_diagnosis,
        POLICY_DESIGN_CASE_DIR / "layer3_g8_domain_vs_search_ceiling_gate.json": bundle.ceiling_gate,
        POLICY_DESIGN_CASE_DIR / "layer3_g8_metric_gaming_firewall.json": bundle.metric_gaming_firewall,
        POLICY_DESIGN_CASE_DIR / "layer3_g8_warning_lifecycle_ledger.json": bundle.warning_lifecycle_ledger,
        POLICY_DESIGN_CASE_DIR / "layer3_g8_d44_corpus_rebasing_rule.json": bundle.d44_rebasing_rule,
        POLICY_DESIGN_CASE_DIR / "layer3_g8_d44_reannotation_coverage_matrix.json": bundle.d44_reannotation_coverage_matrix,
        POLICY_DESIGN_CASE_DIR / "layer3_g8_d44_rebasing_trigger_ledger.json": bundle.d44_rebasing_trigger_ledger,
        POLICY_DESIGN_CASE_DIR / "layer3_g8_d44_rebasing_candidate_set.json": bundle.d44_rebasing_candidate_set,
        POLICY_DESIGN_CASE_DIR / "layer3_g8_d44_rebasing_receipt.json": bundle.d44_rebasing_receipt,
        POLICY_DESIGN_CASE_DIR / "layer3_g8_sealed_battery_integrity_join.json": bundle.sealed_battery_integrity_join,
        POLICY_DESIGN_CASE_DIR / "layer3_g8_open_question_answer_ledger.json": bundle.open_question_answer_ledger,
        POLICY_DESIGN_CASE_DIR / "layer3_g8_metric_governance_audit_surface.json": bundle.audit_surface,
        POLICY_DESIGN_CASE_DIR / "layer3_g8_closeout_signal_consumer_gate.json": bundle.closeout_signal_consumer_gate,
        POLICY_DESIGN_CASE_DIR / "layer3_g8_public_export_projection_refs.json": bundle.public_export_projection_refs,
        POLICY_DESIGN_CASE_DIR / "layer3_g8_replay_manifest.json": bundle.replay_manifest,
        POLICY_DESIGN_CASE_DIR / "layer3_g8_conformance_report.json": bundle.conformance_report,
        POLICY_DESIGN_CASE_DIR / "layer3_g8_registry_ratchet_delta.json": bundle.registry_ratchet_delta,
    }
    written: list[str] = []
    for path in EXPECTED_ARTIFACT_PATHS:
        resolved = _resolve_repo_path(repo_root, path)
        if path.name == "layer3_g8_health_metric_governance_delta.toml":
            _write_health_metric_governance_delta(
                resolved,
                bundle.health_metric_governance_delta,
            )
        elif path.name == "layer3_g8_metric_governance_route_contract_registry.toml":
            _write_route_contract_registry(resolved, bundle.route_contract_registry)
        elif path.name == "layer3_g8_readiness_manifest.json":
            continue
        else:
            _write_json(resolved, payloads[path])
        written.append(path.as_posix())
    return written


def _write_json(path: Path, payload: Any) -> None:
    atomic_write_text(path, _json_dumps(_dump(payload)))


def _write_health_metric_governance_delta(path: Path, payload: Mapping[str, Any]) -> None:
    lines = [
        f"schema_version = {_toml_value(payload['schema_version'])}",
        f"rule_version = {_toml_value(payload['rule_version'])}",
        "",
        "[health_metric_governance_delta]",
    ]
    delta = dict(payload["health_metric_governance_delta"])
    for key, value in delta.items():
        lines.append(f"{_toml_key(str(key))} = {_toml_value(value)}")
    atomic_write_text(path, "\n".join(lines) + "\n")


def _write_route_contract_registry(path: Path, payload: Mapping[str, Any]) -> None:
    lines = [
        f"schema_version = {_toml_value(payload['schema_version'])}",
        f"rule_version = {_toml_value(payload['rule_version'])}",
        f"route_contract_registry_kind = {_toml_value(payload['route_contract_registry_kind'])}",
        f"surface_id = {_toml_value(payload['surface_id'])}",
        f"producer = {_toml_value(payload['producer'])}",
        f"validator = {_toml_value(payload['validator'])}",
        f"metric_trend_report = {_toml_value(payload['metric_trend_report'])}",
        f"closeout_consumer_gate = {_toml_value(payload['closeout_consumer_gate'])}",
        f"may_not_use_for = {_toml_value(payload['may_not_use_for'])}",
    ]
    atomic_write_text(path, "\n".join(lines) + "\n")
```

Add summary, drift, registration, and issue helpers:

```python
def _summary(
    *,
    bundle: g8.Layer3G8Bundle,
    drift_keys: Sequence[str],
    registration_statuses: Mapping[str, str],
) -> dict[str, Any]:
    return {
        "schema_version": G8_SCHEMA_VERSION,
        "rule_version": G8_RULE_VERSION,
        "status": "pass",
        "surface_id": g8.G8_SURFACE_ID,
        "expected_artifact_count": len(EXPECTED_ARTIFACT_PATHS),
        "g8_metric_governance_status": bundle.audit_surface.status,
        "g8_canonical_metric_count": len(bundle.registry.entries),
        "g8_metric_alias_resolution_status": "pass" if not bundle.registry.issue_codes else "blocked",
        "g8_metric_source_snapshot_status": bundle.source_snapshot.status,
        "g8_metric_source_count": bundle.source_snapshot.source_count,
        "g8_normalized_metric_signal_status": bundle.normalized_signals.status,
        "g8_metric_trend_report_status": bundle.metric_trend_report.status,
        "g8_effective_independence_status": bundle.cross_metric_diagnosis.effective_independence_status,
        "g8_effective_independent_evidence_count": bundle.cross_metric_diagnosis.effective_independent_evidence_count,
        "g8_domain_vs_search_ceiling_status": bundle.ceiling_gate.status,
        "g8_metric_gaming_firewall_status": bundle.metric_gaming_firewall.status,
        "g8_warning_lifecycle_status": bundle.warning_lifecycle_ledger.status,
        "g8_d44_rebasing_rule_status": bundle.d44_rebasing_rule.status,
        "g8_d44_reannotation_coverage_status": bundle.d44_reannotation_coverage_matrix.status,
        "g8_d44_rebasing_trigger_status": bundle.d44_rebasing_trigger_ledger.status,
        "g8_d44_rebasing_receipt_status": bundle.d44_rebasing_receipt.status,
        "g8_sealed_battery_integrity_status": bundle.sealed_battery_integrity_join.status,
        "g8_open_question_answer_status": bundle.open_question_answer_ledger.status,
        "g8_expert_machine_surface_status": "pass" if bundle.audit_surface.surface_audiences == ("EXPERT", "MACHINE") else "blocked",
        "g8_closeout_signal_consumer_status": bundle.closeout_signal_consumer_gate.status,
        "g8_public_projection_contract_status": bundle.public_export_projection_refs.public_projection_status,
        "g8_replay_manifest_status": bundle.replay_manifest.get("status"),
        "g8_conformance_status": bundle.conformance_report.status,
        "g8_generated_artifacts_registration_status": registration_statuses["generated_artifacts"],
        "g8_inventory_surface_status": registration_statuses["inventory"],
        "g8_reference_docs_status": registration_statuses["docs"],
        "g8_route_contract_registry_status": registration_statuses["route_contract_registry"],
        "g8_registry_ratchet_status": registration_statuses["registry_ratchet"],
        "g8_manifest_runtime_drift_key_count": len(drift_keys),
        "may_not_use_for": list(g8.G8_MAY_NOT_USE_FOR),
    }


def _readiness_manifest(
    *,
    bundle: g8.Layer3G8Bundle,
    drift_keys: Sequence[str],
    registration_statuses: Mapping[str, str],
) -> dict[str, Any]:
    summary = _summary(
        bundle=bundle,
        drift_keys=drift_keys,
        registration_statuses=registration_statuses,
    )
    return {
        "schema_version": G8_SCHEMA_VERSION,
        "rule_version": G8_RULE_VERSION,
        "status": "pass",
        "surface_id": g8.G8_SURFACE_ID,
        "summary": summary,
        **{key: summary[key] for key in EXPECTED_MANIFEST_DRIFT_KEYS},
        "issue_codes": [],
    }


def _manifest_runtime_drift_keys(repo_root: Path, runtime_manifest: Mapping[str, Any]) -> list[str]:
    path = _resolve_repo_path(repo_root, READINESS_MANIFEST_PATH)
    if not path.exists():
        return []
    try:
        persisted = _read_json(path)
    except (OSError, json.JSONDecodeError):
        return ["readiness_manifest_unreadable"]
    persisted_summary = {
        **_mapping(persisted.get("summary")),
        **{
            key: persisted.get(key)
            for key in EXPECTED_MANIFEST_DRIFT_KEYS
            if key in persisted
        },
    }
    runtime_summary = {
        **_mapping(runtime_manifest.get("summary")),
        **{
            key: runtime_manifest.get(key)
            for key in EXPECTED_MANIFEST_DRIFT_KEYS
            if key in runtime_manifest
        },
    }
    return [
        key
        for key in EXPECTED_MANIFEST_DRIFT_KEYS
        if persisted_summary.get(key) != runtime_summary.get(key)
    ]


def _registration_statuses(repo_root: Path) -> dict[str, str]:
    generated_text = _read_text_or_empty(repo_root, GENERATED_ARTIFACTS_TOML_PATH)
    inventory_text = _read_text_or_empty(repo_root, INVENTORY_PATH)
    generated_ok = (
        G8_GENERATED_ARTIFACT_FAMILY_ID in generated_text
        and "source_of_truth =" in generated_text
        and "check_command =" in generated_text
        and "stale_output_behavior = \"fail\"" in generated_text
        and all(path.as_posix() in generated_text for path in EXPECTED_ARTIFACT_PATHS)
    )
    inventory_ok = (
        g8.G8_SURFACE_ID in inventory_text
        and "src/polisyos/runtime/quality/layer3_health_metric_governance.py" in inventory_text
        and "tools/quality/validation/check_policy_design_case_layer3_g8_readiness.py" in inventory_text
        and all(path.as_posix() in inventory_text for path in EXPECTED_ARTIFACT_PATHS)
    )
    docs_checks = (
        (GENERATED_ARTIFACTS_DOC_PATH, "Policy Design Case Layer 3 G8 health-metric governance artifacts"),
        (GENERATED_ARTIFACTS_DOC_PATH, "layer3_g8_readiness_manifest.json"),
        (PUBLIC_SURFACE_DOC_PATH, g8.G8_SURFACE_ID),
        (PUBLIC_SURFACE_DOC_PATH, "EXPERT/MACHINE"),
        (PUBLIC_SURFACE_DOC_PATH, "out_of_scope_reference_only"),
        (PUBLIC_SURFACE_DOC_PATH, "layer3_g8_closeout_signal_consumer_gate.json"),
        (DOCUMENTATION_INVENTORY_PATH, g8.G8_SURFACE_ID),
        (REFERENCE_INDEX_PATH, "Policy Design Case Layer 3 Health-Metric Governance"),
        (RUNTIME_QUALITY_README_PATH, "layer3_health_metric_governance.py"),
    )
    docs_ok = all(needle in _read_text_or_empty(repo_root, path) for path, needle in docs_checks)
    route_text = _read_text_or_empty(
        repo_root,
        POLICY_DESIGN_CASE_DIR / "layer3_g8_metric_governance_route_contract_registry.toml",
    )
    registry_text = _read_text_or_empty(
        repo_root,
        POLICY_DESIGN_CASE_DIR / "layer3_g8_registry_ratchet_delta.json",
    )
    return {
        "generated_artifacts": "pass" if generated_ok else "fail",
        "inventory": "pass" if inventory_ok else "fail",
        "docs": "pass" if docs_ok else "fail",
        "route_contract_registry": (
            "pass"
            if "route_contract_registry_kind = \"generated_metric_governance_route_contract_registry\"" in route_text
            and "closeout_consumer_gate = \"architecture/policy_design_case/layer3_g8_closeout_signal_consumer_gate.json\"" in route_text
            else "fail"
        ),
        "registry_ratchet": "pass" if "layer3_g8_registry_ratchet_delta" in registry_text else "fail",
    }


def _validate_persisted_artifacts(repo_root: Path) -> list[dict[str, str]]:
    return [
        _issue(
            "layer3_g8_persisted_artifact_missing",
            path.as_posix(),
            "Layer 3 G8 readiness requires persisted metric-governance artifacts.",
        )
        for path in EXPECTED_ARTIFACT_PATHS
        if not _resolve_repo_path(repo_root, path).exists()
    ]


def _validate_written_artifact_set(written_paths: Sequence[str]) -> list[dict[str, str]]:
    expected = {path.as_posix() for path in EXPECTED_ARTIFACT_PATHS}
    written = {str(path) for path in written_paths}
    return [
        *[
            _issue(
                "layer3_g8_persisted_artifact_missing",
                path,
                "G8 --write omitted an expected artifact.",
            )
            for path in sorted(expected - written)
        ],
        *[
            _issue(
                "layer3_g8_persisted_artifact_missing",
                path,
                "G8 --write emitted an unexpected artifact path.",
            )
            for path in sorted(written - expected)
        ],
    ]


def _manifest_runtime_drift_issues(drift_keys: Sequence[str]) -> list[dict[str, str]]:
    if not drift_keys:
        return []
    return [
        _issue(
            "layer3_g8_manifest_runtime_drift",
            READINESS_MANIFEST_PATH.as_posix(),
            f"Persisted G8 readiness manifest drifted from runtime keys: {sorted(drift_keys)}",
        )
    ]


def _registration_issues(statuses: Mapping[str, str]) -> list[dict[str, str]]:
    issue_by_key = {
        "generated_artifacts": "layer3_g8_generated_artifacts_family_missing",
        "inventory": "layer3_g8_inventory_surface_missing",
        "docs": "layer3_g8_reference_docs_missing",
        "route_contract_registry": "layer3_g8_route_contract_registry_missing",
        "registry_ratchet": "layer3_g8_registry_ratchet_missing",
    }
    return [
        _issue(
            issue_by_key[key],
            key,
            f"G8 registration check failed for {key}.",
        )
        for key, status in statuses.items()
        if status != "pass"
    ]


def _validate_runtime_surfaces(bundle: g8.Layer3G8Bundle) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if bundle.conformance_report.status != "pass":
        issue_codes = bundle.conformance_report.issue_codes or (
            "layer3_g8_conformance_negative_missing",
        )
        issues.extend(
            _issue(
                code,
                "architecture/policy_design_case/layer3_g8_conformance_report.json",
                "G8 conformance report must pass all required negative probes.",
            )
            for code in issue_codes
        )
    return issues


def _issue(code: str, path: str, message: str) -> dict[str, str]:
    return {"code": code, "path": path, "message": message}


def _dedupe_issues(issues: Sequence[Mapping[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str, str]] = set()
    result: list[dict[str, str]] = []
    for issue in issues:
        item = (
            str(issue.get("code", "")),
            str(issue.get("path", "")),
            str(issue.get("message", "")),
        )
        if item in seen:
            continue
        seen.add(item)
        result.append({"code": item[0], "path": item[1], "message": item[2]})
    return result


def _read_text_or_empty(repo_root: Path, path: Path) -> str:
    try:
        return _resolve_repo_path(repo_root, path).read_text(encoding="utf-8")
    except OSError:
        return ""


def _resolve_repo_path(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return dict(payload) if isinstance(payload, Mapping) else {}


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True, default=str) + "\n"


def _dump(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): _dump(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [_dump(item) for item in value]
    return value


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _toml_key(value: str) -> str:
    if value and value.replace("_", "").isalnum() and value[0].isalpha():
        return value
    return json.dumps(value)


def _toml_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    return json.dumps(str(value))


def _render_text_report(report: Mapping[str, Any]) -> str:
    summary = dict(report.get("summary") or {})
    lines = [
        f"Layer 3 G8 readiness: {report.get('status')}",
        f"metric governance: {summary.get('g8_metric_governance_status')}",
        f"domain/search ceiling: {summary.get('g8_domain_vs_search_ceiling_status')}",
        f"D4.4 rebasing: {summary.get('g8_d44_rebasing_receipt_status')}",
        f"issues: {len(report.get('issues') or [])}",
    ]
    return "\n".join(lines) + "\n"
```

Add CLI:

```python
def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--output-format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    report = validate_layer3_g8_readiness(args.repo_root, write=args.write)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        atomic_write_text(Path(args.output), rendered)
    sys.stdout.write(rendered if args.output_format == "json" else _render_text_report(report))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Add registrations and docs**

Append a family to `architecture/generated_artifacts.toml` with label `Policy Design Case Layer 3 G8 health-metric governance artifacts`, source of truth `src/polisyos/runtime/quality/layer3_health_metric_governance.py and tools/quality/validation/check_policy_design_case_layer3_g8_readiness.py`, all `EXPECTED_ARTIFACT_PATHS`, regenerate command:

```bash
uv run python tools/quality/validation/check_policy_design_case_layer3_g8_readiness.py --repo-root . --write --output-format json
```

check command:

```bash
uv run python tools/quality/validation/check_policy_design_case_layer3_g8_readiness.py --repo-root . --output-format json
```

Add an inventory entry in `architecture/policy_design_case/inventory.json`:

- `id`: `layer3_g8_health_metric_governance_surface`
- `kind`: `layer3_g8_metric_governance_audit_surface`
- `schema_version`: `policyos.policy_design_case.layer3_g8_health_metric_governance.v1`
- `rule_version`: `policyos.layer3.g8.health_metric_governance.v1`
- `authority_scope`: `layer3_g8_metric_governance_audit`, `layer3_g8_d44_rebasing_integrity_reading`, `layer3_g8_open_question_answer_reading`
- `may_not_use_for`: `G8_MAY_NOT_USE_FOR`
- `surface_audiences`: `EXPERT`, `MACHINE`
- `surface_out_of_scope`: `PUBLIC` and `REVIEWER` as projection-only references
- `metric_trend_report`: `architecture/policy_design_case/layer3_g8_metric_trend_report.json`
- `closeout_consumer_gate`: `architecture/policy_design_case/layer3_g8_closeout_signal_consumer_gate.json`
- `producer`: `src/polisyos/runtime/quality/layer3_health_metric_governance.py`
- `validator`: `tools/quality/validation/check_policy_design_case_layer3_g8_readiness.py`
- `readiness_manifest`: `architecture/policy_design_case/layer3_g8_readiness_manifest.json`
- `closure_artifact_paths`: all `EXPECTED_ARTIFACT_PATHS`

Update docs with these exact phrases so registration checks can be direct:

- `docs/reference/generated-artifacts.md`: `Policy Design Case Layer 3 G8 health-metric governance artifacts`
- `docs/reference/public-surface.md`: `layer3_g8_health_metric_governance_surface`, `EXPERT/MACHINE`, `out_of_scope_reference_only`, and `layer3_g8_closeout_signal_consumer_gate.json`
- `docs/reference/documentation-inventory.md`: `layer3_g8_health_metric_governance_surface`
- `docs/reference/index.md`: `Policy Design Case Layer 3 Health-Metric Governance`
- `src/polisyos/runtime/quality/README.md`: `layer3_health_metric_governance.py`

- [ ] **Step 5: Run write-mode readiness**

```bash
cd policy-engine
uv run python tools/quality/validation/check_policy_design_case_layer3_g8_readiness.py --repo-root . --write --output-format json
```

Expected: `status` is `pass`; 24 G8 output artifacts are written, including the readiness manifest.

- [ ] **Step 6: Run readiness tests**

```bash
cd policy-engine
uv run pytest tests/repo_quality/tools/test_policy_design_case_layer3_g8_readiness.py -q
```

Expected: pass.

- [ ] **Step 7: Run readiness CLI tests**

```bash
cd policy-engine
uv run pytest tests/repo_quality/tools/test_policy_design_case_layer3_g8_readiness_cli.py -q
```

Expected: pass.

- [ ] **Step 8: Commit**

```bash
cd policy-engine
git add \
  tools/quality/validation/check_policy_design_case_layer3_g8_readiness.py \
  tests/repo_quality/tools/test_policy_design_case_layer3_g8_readiness.py \
  tests/repo_quality/tools/test_policy_design_case_layer3_g8_readiness_cli.py \
  architecture/generated_artifacts.toml \
  architecture/policy_design_case/inventory.json \
  architecture/policy_design_case/layer3_g8_*.json \
  architecture/policy_design_case/layer3_g8_*.toml \
  docs/reference/generated-artifacts.md \
  docs/reference/public-surface.md \
  docs/reference/documentation-inventory.md \
  docs/reference/index.md \
  src/polisyos/runtime/quality/README.md
git commit -m "feat: persist layer3 g8 readiness artifacts"
```

## Task 10: Final Verification and Guardrails

**Files:**

- Modify only files touched in previous tasks if verification finds a G8 bug.

- [ ] **Step 1: Run the focused G8 unit tests**

```bash
cd policy-engine
uv run pytest tests/unit/runtime/quality/test_layer3_g8_health_metric_governance.py -q
```

Expected: pass.

- [ ] **Step 2: Run the focused G8 readiness tests**

```bash
cd policy-engine
uv run pytest tests/repo_quality/tools/test_policy_design_case_layer3_g8_readiness.py -q
```

Expected: pass.

- [ ] **Step 3: Run the focused G8 readiness CLI tests**

```bash
cd policy-engine
uv run pytest tests/repo_quality/tools/test_policy_design_case_layer3_g8_readiness_cli.py -q
```

Expected: pass.

- [ ] **Step 4: Re-run G8 readiness without write mode**

```bash
cd policy-engine
uv run python tools/quality/validation/check_policy_design_case_layer3_g8_readiness.py --repo-root . --output-format json
```

Expected summary values:

```json
{
  "g8_metric_governance_status": "pass",
  "g8_canonical_metric_count": 5,
  "g8_metric_source_count": 44,
  "g8_metric_trend_report_status": "pass",
  "g8_effective_independence_status": "sufficient",
  "g8_effective_independent_evidence_count": 2,
  "g8_domain_vs_search_ceiling_status": "not_claimed_current_grounding_blocker",
  "g8_d44_reannotation_coverage_status": "pass",
  "g8_d44_rebasing_trigger_status": "pass_no_rebase_due",
  "g8_d44_rebasing_receipt_status": "pass_no_rebase_required",
  "g8_sealed_battery_integrity_status": "pass",
  "g8_closeout_signal_consumer_status": "pass",
  "g8_open_question_answer_status": "pass",
  "g8_manifest_runtime_drift_key_count": 0
}
```

- [ ] **Step 5: Preserve S14 non-mutating behavior**

Run:

```bash
cd policy-engine
uv run pytest tests/repo_quality/tools/test_layer2_s14_universality_battery.py::test_s14_battery_runner_reads_g7_manifest_without_mutating_freeze_hash -q
```

Expected: pass. This proves the existing G7/S14 hook still preserves sealed-battery freeze hashes and does not expose hidden payloads.

- [ ] **Step 6: Run architecture guardrails**

```bash
cd policy-engine
uv run polisyos-tools architecture guardrails check
```

Expected: pass.

- [ ] **Step 7: Run fast backend verification**

```bash
cd policy-engine
python3 -m tools.cli workspace verify --backend-only
```

Expected: pass. If unrelated dirty-worktree failures appear, record the failing test names and confirm the focused G8 tests still pass.

- [ ] **Step 8: Final pattern closeout check**

Open `docs/reference/policy-design-case-failure-patterns.md` again and confirm final implementation still satisfies:

- `P01`: producer, persisted artifacts, validator, surface, and negative tests are wired;
- `P02`: G8 reads richer G1-G7/S14 source artifacts and closeout/readiness consumes the persisted gate;
- `P03`: EXPERT/MACHINE surfaces expose the five metrics, D4.4 receipts, and sealed-battery integrity status;
- `P05`: every G8 artifact carries authority boundaries;
- `P07`: re-basing receipts carry freeze hashes and rule versions;
- `P09`: warnings carry owner, deadline, aging, and accepted-deficit policy;
- `P10`: semantic negatives prove anti-gaming, demand-inertia, D4.4 coverage, and search/domain ceiling behavior;
- `P13`: historical G1-G7 metric dialects are normalized instead of forcing a rewrite;
- `P14`: effective independent evidence count and collapse status remain visible in readiness summary;
- `P25`: search recall/freshness artifacts remain replay-visible and cannot become a domain-ceiling shortcut;
- `P26`: demand-pull and closeout consumer gates preserve accountable-principal and authority boundaries.

- [ ] **Step 9: Commit verification fixes**

If verification required edits:

```bash
cd policy-engine
git add \
  src/polisyos/runtime/quality/layer3_health_metric_governance.py \
  tools/quality/validation/check_policy_design_case_layer3_g8_readiness.py \
  tests/unit/runtime/quality/test_layer3_g8_health_metric_governance.py \
  tests/repo_quality/tools/test_policy_design_case_layer3_g8_readiness.py \
  architecture/generated_artifacts.toml \
  architecture/policy_design_case/inventory.json \
  architecture/policy_design_case/layer3_g8_*.json \
  architecture/policy_design_case/layer3_g8_*.toml \
  docs/reference/generated-artifacts.md \
  docs/reference/public-surface.md \
  docs/reference/documentation-inventory.md \
  docs/reference/index.md \
  src/polisyos/runtime/quality/README.md
git commit -m "fix: verify layer3 g8 metric governance"
```

If no edits were required, do not create an empty commit.

## Implementation Notes

- Treat G8 `status == "pass"` as engineering/readiness pass. It does not mean the current PolicyOS system has achieved grounded regional value closure.
- Current expected value-state remains blocked: `g8_domain_vs_search_ceiling_status == "not_claimed_current_grounding_blocker"`.
- `pass_no_rebase_required` is the correct current D4.4 receipt because G7 has no real grounded breadth to re-base into S14 yet.
- Do not average metric statuses. G8 should preserve per-metric and per-source signals, then emit a diagnosis.
- Do not treat numeric demand-pull readings as automatic pass. `grounded_result_rate == 0.0` and high abstention/blocker rates are evidence for abstention inertia until a grounded response exists.
- Do not turn warnings into passes. Warnings with owner/deadline may allow G8 readiness to pass, but they block authority claims named in `accepted_deficit_policy`.
- Do not satisfy D4.4 by listing fields only. Each required re-annotation field must appear in the coverage matrix with a status and source ref.
- Do not claim closeout integration by denial alone. The closeout consumer gate must read persisted G8 signals and deny closeout authority at the consumer side.
- Do not import hidden S14 case payloads. G8 reads committed partition and assurance manifests; S14 runner remains responsible for sealed-battery integrity computation.
- Do not add `layer3_health_metric_governance.py` to eager exports in `src/polisyos/runtime/quality/__init__.py`.

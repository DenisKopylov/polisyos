# Policy Design Case Layer 3 Promotion Gate

Owner: `team-runtime-quality`

Source of truth: `src/polisyos/runtime/quality/proving_ground/governed_promotion_gate.py`,
`tools/quality/validation/check_policy_design_case_layer3_g4_readiness.py`,
and `architecture/policy_design_case/layer3_g4_readiness_manifest.json`.

G4 is the shadow-to-governed promotion gate for Layer 3 Policy Design Case
outputs. It reads persisted upstream G1/G2/G3/GL contract artifacts, checks
A-completeness for the declared promotion scope, applies weakest-boundary
composition, routes high-stakes or value-laden promotion through P26/S7 human
decision integrity, and emits `PromotionRecord` states of
`governed_promoted` or `promotion_blocked`.

G4 does not grant production, rollout, publication, approval, scorecard,
closeout, claim, policy recommendation, or useful-design authority. Its
authority is limited to promotion decision replay, governed promotion state for
the declared scope, and reference-only downstream input refs for closeout, the
PDC compiler, and G5.

## Artifacts

- `layer3_g4_dependency_readiness_snapshot.json`
- `layer3_g4_promotion_input_set.json`
- `layer3_g4_grounded_contract_set.json`
- `layer3_g4_a_completeness_ledger.json`
- `layer3_g4_human_decision_integrity_gate.json`
- `layer3_g4_weakest_boundary_composition.json`
- `layer3_g4_promotion_records.json`
- `layer3_g4_closeout_consumer_gate.json`
- `layer3_g4_pdc_compiler_consumer_gate.json`
- `layer3_g4_g5_promotion_handoff.json`
- `layer3_g4_governance_throughput_delta.json`
- `layer3_g4_promotion_audit_surface.json`
- `layer3_g4_public_export_projection_refs.json`
- `layer3_g4_conformance_report.json`
- `layer3_g4_health_metric_delta.toml`
- `layer3_g4_adapter_contract_registry.toml`
- `layer3_g4_registry_ratchet_delta.json`
- `layer3_g4_readiness_manifest.json`

Canonical regeneration command:

```bash
uv run python tools/quality/validation/check_policy_design_case_layer3_g4_readiness.py --repo-root . --write --output-format json
```

## Surface

The audit surface id is `layer3_g4_shadow_to_governed_promotion_surface`.
The persisted audit artifact is `layer3_g4_promotion_audit_surface.json`.

Audience contract: `PUBLIC/REVIEWER/EXPERT/MACHINE`.

PUBLIC may see promotion state, declared scope/envelope, high-level blocker
codes, limitation codes, and safe evidence refs only. It must not expose raw
upstream payloads, raw legal/proof/search payloads, source-data truth authority,
claim authority, or policy recommendation authority.

REVIEWER may see promotion record refs, blocker refs, limitation refs, and
reference-only consumer-gate status.

EXPERT and MACHINE may see upstream contract refs, conformance refs, replay refs,
weakest-boundary reasons, and P26/S7 routing refs. They still must not receive
raw sensitive upstream payloads through the G4 public projection.

`layer3_g4_public_export_projection_refs.json` is projection-only. Its
`public_export_hook_status` is `out_of_scope_reference_only` because this slice
does not wire G4 directly into `build_public_export_bundle`.

## Denied Uses

G4 artifacts preserve `may_not_use_for` boundaries, including
`production_authority`, `production_claim_authority`, `rollout_authority`,
`publication_authority`, `approval_authority`, `scorecard_authority`,
`closeout_authority`, `runtime_closeout_authority`, `closeout_verdict`,
`claim_authority`, `source_data_truth_authority`, `public_recommendation`,
`policy_recommendation`, `useful_design_credit_before_g5`,
`causal_effect_authority_without_g2`, `proof_authority_without_g3`,
`legal_authority_without_gl`, and `human_override_of_a_incompleteness`.

## Validation

Readiness passes only when the runtime bundle validates, all 18 generated
artifacts are persisted at the registered paths, the write set is exact, the
manifest drift keys match runtime output, docs/TOML/inventory registrations are
present, and public projection checks find no raw-payload leak or authority
overclaim.

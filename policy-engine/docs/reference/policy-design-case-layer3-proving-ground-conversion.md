# Policy Design Case Layer 3 Proving-Ground Conversion

G5 is the first proving-ground conversion surface for a pinned Policy Design Case.
It answers whether a governed G4 promotion handoff can become a useful grounded
conversion signal, an unchanged blocker, or a grounded abstention signal without
minting publication, claim, closeout, or policy-recommendation authority.

Surface id: `layer3_g5_first_proving_ground_conversion_surface`

Readiness CLI:

```bash
uv run python tools/quality/validation/check_policy_design_case_layer3_g5_readiness.py --repo-root . --write --output-format json
```

## Authority Boundary

The G5 audit surface is authoritative only for:

- `layer3_g5_proving_ground_conversion_classification`
- `layer3_g5_envelope_expansion_reading`
- `w12d_layer3_conversion_gate`

It is not authoritative for production authority, rollout authority,
publication authority, approval authority, scorecard authority, closeout
authority, runtime closeout authority, public recommendation, policy
recommendation, legal advice, unsupported claim authority, G6 arbitrary request
orchestration, or G7 region widening.

## Audience Surface

The generated audit surface is exposed to `PUBLIC/REVIEWER/EXPERT/MACHINE`:

- `PUBLIC` receives conversion status, outcome, blocker/limitation refs, denied
  uses, and projection-only public refs. It does not receive raw upstream
  payloads.
- `REVIEWER` receives conversion record refs, W12.D gate status, G4 handoff
  status, and limitation refs for audit.
- `EXPERT` receives dependency readiness, upstream join, evidence independence,
  conformance, route-registry, and health metric refs.
- `MACHINE` receives persisted JSON/TOML artifacts for drift, replay, write-set
  completeness, and projection authority checks.

## Generated Artifacts

Generated artifact family:
`policy-design-case-layer3-g5-proving-ground-conversion-artifacts`

The family is registered in `architecture/generated_artifacts.toml` with
`stale_output_behavior = "fail"` and `drift_gate = "automated"`.

Primary persisted artifacts:

- `architecture/policy_design_case/layer3_g5_pinned_case_input_bundle.json`
- `architecture/policy_design_case/layer3_g5_g4_handoff_resolution.json`
- `architecture/policy_design_case/layer3_g5_upstream_scope_join_matrix.json`
- `architecture/policy_design_case/layer3_g5_grounded_result_evidence_set.json`
- `architecture/policy_design_case/layer3_g5_effective_evidence_independence.json`
- `architecture/policy_design_case/layer3_g5_conversion_eligibility_ledger.json`
- `architecture/policy_design_case/layer3_g5_status_composition_ledger.json`
- `architecture/policy_design_case/layer3_g5_envelope_expansion_delta.json`
- `architecture/policy_design_case/layer3_g5_conversion_records.json`
- `architecture/policy_design_case/layer3_g5_w12d_consumer_gate.json`
- `architecture/policy_design_case/layer3_g5_conversion_audit_surface.json`
- `architecture/policy_design_case/layer3_g5_public_export_projection_refs.json`
- `architecture/policy_design_case/layer3_g5_conformance_report.json`
- `architecture/policy_design_case/layer3_g5_conversion_route_contract_registry.toml`
- `architecture/policy_design_case/layer3_g5_readiness_manifest.json`

## Public Projection Boundary

`layer3_g5_public_export_projection_refs.json` is projection-only. Its
`public_export_hook_status` is `out_of_scope_reference_only`, and
`public_export_bundle_route_registered` is false.

The projection refs reuse the runtime Policy Design Case projection boundary
checks and the S12/S14 projection consumer-contract checks. Public projections
must preserve denied uses such as `claim_authority`, `policy_recommendation`,
`runtime_closeout_authority`, and `recommendation_authority`; they may not carry
`raw_upstream_payload` or allocation/recommendation text.

## Readiness Signal

Task 6 closes when `--write` refreshes every expected G5 artifact, the
persisted readiness manifest has no runtime drift, generated artifacts and
inventory are registered, the conversion-route registry is present, and the
W12.D consumer gate reads the conversion record without treating an unchanged
blocker as useful design credit.

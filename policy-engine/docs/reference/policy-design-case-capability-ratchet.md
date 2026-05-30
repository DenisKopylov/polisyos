# Policy Design Case Capability Ratchet

Owner: `team-runtime-quality`
Backup owner: `team-quality-closeout`
Source of truth: `architecture/policy_design_case/capability_reality_report.json`

The Policy Design Case capability ratchet is the release/readiness vocabulary
for incomplete Policy Design Case work across waves. It makes missing states
visible without calling them implemented. A capability can be useful evidence
while it is `contract_only`, `bridge_missing`, `surface_missing`, or
`semantic_test_missing`; it just cannot graduate until the missing chain link is
closed.

## Pattern Pass

Relevant failure patterns: `P01`, `P02`, `P03`, `P07`, `P08`, `P09`, `P10`,
`P11`, `P12`, `P13`, and `P15`.

Target correct pattern: every capability claim carries a typed reality state,
owner, hold reason, next target, debt points, purpose multiplier, readiness
band, and burn-down template. Projections, dashboards, docs, or reports do not
mint missing producer, bridge, consumer, surface, verification, or semantic-test
authority.

Missing capability labels are first-class: `contract_only`, `producer_missing`,
`artifact_missing`, `bridge_missing`, `consumer_missing`,
`verification_missing`, `implemented_but_not_orchestrated`, `surface_missing`,
`surface_out_of_scope`, and `semantic_test_missing`.

## Report

Committed report:

```text
architecture/policy_design_case/capability_reality_report.json
```

Validation command:

```bash
uv run python tools/quality/validation/check_policy_design_case_capability_ratchet.py --repo-root .
```

Regeneration command:

```bash
uv run python tools/quality/validation/check_policy_design_case_capability_ratchet.py --repo-root . --write
```

The checker validates both report integrity and the current wave closure
claims. `ratchet_integrity_status: pass` means the report is internally honest
and recomputable. The committed report is expected to be green only after the
closed wave capabilities each carry a complete capability evidence chain.

Every `implemented` claim must also carry the plan-level traceability row
required by the implementation plan: `research_refs`, ADR refs or
`no_adr_required`, `reuse_classification`, and `rollout_refs`. The checker
fails closed if an implemented claim is green on chain evidence but missing
that research/decision/reuse/rollout spine. Wave 2 extends the report with
W2.A-F and W2.I2 closure rows.

## Debt Algebra

Base debt points and purpose multipliers are emitted in the report under
`debt_algebra`. The local score follows:

```text
base_state_points * purpose_factor
  + serious_profile_premium
  + sole_path_premium
  + ownerless_or_expired_premium
  + chain_cluster_premium
  - mitigation_credit
```

`surface_out_of_scope` is valid only with rationale, owner, review date, and an
inspection path. If that governance is missing, the checker reclassifies it as
`surface_missing`.

`semantic_test_missing` never graduates to `implemented`. On serious closeout or
authority paths it is a release blocker until a content-level adequacy test or
authority-semantics negative test exists.

## Ratchet Templates

Every missing-state label has a burn-down template in
`ratchet_templates`. The template names the evidence field that moves the
capability forward, such as `producer_ref`, `bridge_ref`, `surface_ref`, or
`semantic_test_ref`.

The ratchet is directional: future plans and PRs should reduce open labels
toward `implemented` or a governed `surface_out_of_scope`. New
`contract_only`, `bridge_missing`, or `semantic_test_missing` entries need an
owner, hold reason, expiry, and next target.

# tools/quality/validation

Validation ratchets for docs, benchmark contours, CI policies, and quality
baselines.

Use the unified entry point:

```bash
polisyos-tools validation --help
```

Operational rules:

- Ratchets should distinguish failed, skipped, and degraded checks in their
  output.

- Allowlist changes must remain explicit files reviewed with the code change
  that needs them.

- Generated evidence should be deterministic and safe for CI diffing.

## Policy Design Case Local Validation Ladder

Wave 12.A re-executes the original W6.A local ladder over the compiled
universal PDC while preserving the W6 manifest path for compatibility. The
runner records unit, repo-quality, semantic, local production-debug, and
universal-compilation-smoke command evidence. It reports closeout honesty,
useful-design capability, and W11.E compilation truthfulness separately.
Typed blockers are useful diagnostics and block cloud validation, but they
never count as useful-design outcomes.

Quick local smoke:

```bash
uv run python tools/quality/validation/run_policy_design_case_local_validation_ladder.py \
  --repo-root . \
  --profile quick \
  --output _build/.tmp/production-quality/universal_pdc_local_validation_ladder.json
```

Full W12.A closeout ladder:

```bash
uv run python tools/quality/validation/run_policy_design_case_local_validation_ladder.py \
  --repo-root . \
  --profile full \
  --output _build/.tmp/production-quality/universal_pdc_local_validation_ladder.json
```

## W11.B Claim/Evidence Decomposition Annotations

Wave 11.B validates repo-owned claim/evidence decomposition annotations for
universal outcome corpus cases. The checker rejects structural-only case files
before they can feed fixture loaders or compilation-truthfulness audits.

```bash
uv run python tools/quality/validation/check_universal_corpus_annotations.py \
  --repo-root . \
  --check
```

## W11.C Expert Adjudication Labels

Wave 11.C validates C30 expert adjudication label manifests for the universal
outcome corpus. The checker enforces reviewer topology, claim coverage,
gold-card fields for rejected structural passes, and the negative rule that a
structurally complete case without adjudication cannot enter the useful-design
metric.

```bash
uv run python tools/quality/validation/check_expert_adjudication_labels.py \
  --repo-root .
```

## W11.E Compilation Truthfulness

Wave 11.E runs W6 universal compilation and the W7 producer pipeline over W11
outcome-corpus fixtures, then compares compiled frontier obligations against
W11.B annotations and W11.C expert adjudication.

Built-in smoke:

```bash
uv run python tools/quality/validation/check_compilation_truthfulness.py \
  --self-test \
  --output _build/.tmp/production-quality/compilation_truthfulness_self_test.json
```

Corpus run:

```bash
uv run python tools/quality/validation/check_compilation_truthfulness.py \
  --corpus tests/fixtures/universal-corpus \
  --output _build/.tmp/production-quality/compilation_truthfulness_report.json
```

## W12.B Compilation Truthfulness Audit Run

Wave 12.B executes the W11.E audit against the universal outcome corpus and
adds rollout-posture floor semantics. A case below the posture floor becomes a
typed compilation blocker; it does not count as useful design and it is not a
closeout-honesty failure.

```bash
uv run python tools/quality/validation/run_compilation_truthfulness_audit.py \
  --repo-root . \
  --corpus tests/fixtures/universal-corpus \
  --rollout-posture governed-pilot \
  --raw-report-output _build/.tmp/production-quality/w12b_compilation_truthfulness_report.json \
  --output _build/.tmp/production-quality/w12b_compilation_truthfulness_audit.json
```

## W12.C Domain Coverage And Critic Diversity Audit Run

Wave 12.C executes the W11.F domain coverage breadth and critic ensemble
diversity tools, then adds rollout-posture semantics. The report contains a
domain x authority-level useful-design matrix, typed domain-coverage blockers
for committed slices with zero useful-design outcomes, and a
`critic_monoculture` warning that caps rollout at governed pilot or below.

```bash
uv run python tools/quality/validation/run_domain_coverage_critic_diversity_audit.py \
  --repo-root . \
  --corpus tests/fixtures/universal-corpus \
  --rollout-posture governed-pilot \
  --raw-domain-report-output _build/.tmp/production-quality/w12c_domain_coverage_breadth_report.json \
  --raw-critic-report-output _build/.tmp/production-quality/w12c_critic_ensemble_diversity_report.json \
  --output _build/.tmp/production-quality/w12c_domain_coverage_critic_diversity_audit.json
```

## W12.D Universal Outcome Corpus Run

Wave 12.D is the canonical real-corpus evidence run. It runs each W11 corpus
case through W6 universal compilation, W7 producer pipeline orchestration, and
W8.A RuntimePolicyDesignCase graph assembly. The report records per-case
outcome, evidence-bound graph artifact refs, W11.C expert-adjudication deltas,
and authority-level metric stratification. Synthetic fixtures do not substitute
for this command.

```bash
uv run python tools/quality/validation/run_universal_outcome_corpus.py \
  --repo-root . \
  --corpus tests/fixtures/universal-corpus \
  --graph-output-dir _build/.tmp/production-quality/w12d-runtime-pdc-graphs \
  --output _build/.tmp/production-quality/w12d_universal_outcome_corpus_run.json
```

## W12.E Bundle, Replay, And Inspection

Wave 12.E consumes W12.D evidence, assembles the required bundle component
inventory, compares replay graph refs with the live runtime graph, and blocks
any package summary that claims producer, claim, closeout, or public projection
authority.

```bash
uv run python tools/quality/validation/run_policy_design_case_bundle_replay_inspection.py \
  --repo-root . \
  --w12d-report _build/.tmp/production-quality/w12d_universal_outcome_corpus_run.json \
  --output _build/.tmp/production-quality/w12e_bundle_replay_inspection.json
```

## W12.F Cloud One-Lane Revalidation

Wave 12.F consumes the frozen one-lane canary matrix output plus W12.B-E
reports. Missing cloud evidence, source-truth/provenance collapse, W12.E
blockers, or metric-floor misses become typed blockers instead of silent
rollout permission.

```bash
uv run python tools/quality/validation/run_policy_design_case_cloud_one_lane_revalidation.py \
  --repo-root . \
  --matrix-run-report _build/.tmp/production-quality/cloud_wave12/canary_matrix.json \
  --output _build/.tmp/production-quality/w12f_cloud_one_lane_revalidation.json
```

## W12.G Rollout Decision

Wave 12.G consumes W12.A-F, cites closeout honesty, runtime useful design, and
compilation truthfulness separately, then emits a promotion or typed remediation
hold with frozen revision/config refs and rollback/kill-switch instructions.
Corpus-stub evidence can support governed-pilot validation only and never
satisfies production-capable authority.

```bash
uv run python tools/quality/validation/run_policy_design_case_rollout_decision.py \
  --repo-root . \
  --requested-posture governed-pilot \
  --output _build/.tmp/production-quality/w12g_rollout_decision.json
```

## W11.F Domain Coverage Breadth

Wave 11.F measures how many committed domains have an actual W6.C frontier
graph that is non-trivial under the configured family-layer thresholds. The
checker does not count `expected_obligation_graph` fixture slices as producer
evidence; cases without W6.C compile inputs are reported as blocked/warned
instead of being laundered into coverage.

Built-in smoke:

```bash
uv run python tools/quality/validation/check_domain_coverage_breadth.py \
  --self-test \
  --output _build/.tmp/production-quality/domain_coverage_breadth_self_test.json
```

Corpus run:

```bash
uv run python tools/quality/validation/check_domain_coverage_breadth.py \
  --corpus tests/fixtures/universal-corpus \
  --output _build/.tmp/production-quality/domain_coverage_breadth_report.json
```

## W11.F Critic Ensemble Diversity

Wave 11.F measures per-case Jaccard diversity over the unique failure modes
flagged by each critic. The report exposes both pairwise Jaccard similarity and
`1 - similarity` diversity; low diversity emits `critic_monoculture` /
`critic_diversity_below_floor` warnings without turning critic output into
authority.

Built-in smoke:

```bash
uv run python tools/quality/validation/check_critic_ensemble_diversity.py \
  --self-test \
  --output _build/.tmp/production-quality/critic_ensemble_diversity_self_test.json
```

Report run:

```bash
uv run python tools/quality/validation/check_critic_ensemble_diversity.py \
  --input tests/fixtures/universal-corpus \
  --output _build/.tmp/production-quality/critic_ensemble_diversity_report.json
```

## Repository Structure Remediation

Repository structure gates live in
`tools/quality/validation/repository_structure_phase0.py` and are wired by
`architecture/gates/structure_remediation.toml`.

Regenerate the Phase 0 inventory:

```bash
uv run python tools/quality/validation/repository_structure_phase0.py inventory \
  --markdown-output docs/archive/reports/REPOSITORY_STRUCTURE_REMEDIATION_PHASE_0_INVENTORY.md \
  --baseline-dir architecture/baselines/structure_remediation
```

Run all report-only gates:

```bash
uv run python tools/quality/validation/repository_structure_phase0.py gate \
  --gate all \
  --mode report-only
```

Individual gates accept either the short CLI name or the plan gate id:
`empty_namespace`/`empty_namespace_gate`, `loose_files`/`loose_files_gate`,
`name_collision`/`name_collision_gate`, `pyproject_size`/`pyproject_size_gate`,
`cache_dir`/`cache_dir_gate`, and `build_output`/`build_output_gate`.

Phase 1C promotes the cross-package name collision check to fail-closed:

```bash
uv run python tools/quality/validation/name_collision_gate.py
```

Phase 1A promotes the Foundry methods namespace cutover to fail-closed. The
wrapper fails on empty placeholder packages and on real deep imports below
`polisyos.foundry.methods.<domain>`, while preserving an inventory of flat
facade importers:

```bash
uv run python tools/quality/validation/empty_namespace_gate.py \
  --inventory-output architecture/baselines/structure_remediation/foundry_methods_external_importers.json
```

## Repository Best-In-Class Verification Inventory

Repository Best-In-Class Phase 0.4 verification baselines live in
`tools/quality/validation/repository_verification_inventory.py`. The generator
measures mirror ratios, fixture/data layout, product-contract versus
repository-quality tests, property coverage, benchmark topology, and pytest
root/conftest layering without moving tests or changing pytest configuration.

Regenerate the Phase 0.4 baseline and archived report:

```bash
uv run python tools/quality/validation/repository_verification_inventory.py \
  --update \
  --check
```

## Repository Best-In-Class Directory And Asset Inventory

Repository Best-In-Class Phase 0.7 directory, documentation, extension, and
asset inventory lives in
`tools/quality/validation/repository_best_in_class_phase0_7_inventory.py`.
It is read-only and records docs lifecycle, ADR metadata, extension-point
candidates, examples, directory-contract inputs, non-product Python roots, and
local residue.

Refresh the archived Phase 0.7 decision brief:

```bash
uv run python tools/quality/validation/repository_best_in_class_phase0_7_inventory.py \
  --markdown-output docs/archive/reports/REPOSITORY_BEST_IN_CLASS_PHASE_0_7_DECISION_BRIEF.md
uv run python tools/quality/validation/repository_best_in_class_phase0_7_inventory.py \
  --check
```

## Directory Hygiene And Asset Placement

Repository Best-In-Class Phase 2.9 is backed by
`architecture/asset_placement.toml` and the report-only validator in
`tools/quality/validation/directory_hygiene_assets.py`.

Run the contract check:

```bash
uv run polisyos-tools validation directory-hygiene-assets --fail-on-contract-errors
```

The paired cleanup command is dry-run by default for stale local reports. Add
`--apply` only after reviewing the candidate list:

```bash
uv run polisyos-tools workspace clean-local-reports --stale-days 30 --dry-run
```

## Directory Health

Repository Best-In-Class Phase 6.2 is backed by
`architecture/policies/directory_health.toml` and the dashboard/ratchet validator in
`tools/quality/validation/directory_health.py`.

Run the regression gate:

```bash
uv run polisyos-tools validation directory-health --fail-on-regression
```

Top-level directory fail-closed conversion remains guarded while active
top-level path moves are still landing; all other directory-health metrics are
ratcheted from the committed baseline unless an explicit health exception is
recorded.

The paired test ratchet contract is active in Phase 6.2. Mirror-ratio,
strict-mirror, and property-test regressions are enforced through:

```bash
uv run python tools/quality/testing/report_test_ratchets.py --fail-on-regression
```

## Control-Plane And Supply-Chain Contracts

Repository Best-In-Class Phases 1.7 and 2.8 use
`architecture/control_plane_supply_chain.toml` as the active target for
CODEOWNERS coverage, ruleset tiers, workflow permissions, OIDC usage, Renovate
placement, release SBOM/provenance/signing, and Scorecard/SLSA-style reporting.

Run the contract check:

```bash
uv run python tools/quality/validation/control_plane_supply_chain_contracts.py
```

The default mode fails on contract blockers, missing current CODEOWNERS target
patterns, and any retired CODEOWNERS path prefix that re-enters the active
control plane.

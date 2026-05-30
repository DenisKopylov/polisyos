---
title: Policy Design Case Operator Guide
status: active
owner: team-policyos-runtime
created: 2026-05-23
implementation_phase: W5.E
implementation_plan: ../plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_IMPLEMENTATION_PLAN.md
failure_patterns: policy-design-case-failure-patterns.md
evidence_paths: policy-design-case-evidence-paths.md
source_ownership: policy-design-case-source-ownership.md
structural_adr_registry: policy-design-case-structural-adr-registry.md
rollout_runbook: ../runbooks/policy-design-case-rollout-rollback.md
triage_runbook: ../runbooks/policy-design-case-operator-triage.md
---

# Policy Design Case Operator Guide

This page is the W5.E operator surface for E23 in the universal Policy Design
Case program. It tells an operator who did not participate in the research
thread where to find ADR authority, public evidence paths, tuned-parameter
owners, validation ladders, capability evidence, and rollout or rollback
procedures.

This document is operational guidance only. It can route an operator to
runtime evidence, accepted ADRs, command evidence, and closeout notes; it
cannot substitute for producer evidence, closeout authority, API contract
verification, dashboard truth preservation, or semantic evaluation.

## Start Here

| Need | Canonical path | Owner | Verification |
| --- | --- | --- | --- |
| ADR authority for a structural C-row | `docs/reference/policy-design-case-structural-adr-registry.md`, `docs/adr/index.md`, `docs/adr/by-topic.md`, `docs/adr/index.toml` | `team-policyos-runtime` and ADR owners | `uv run pytest tests/repo_quality/tools/test_policy_design_case_structural_adr_registry.py -q` |
| System-design decision context | `docs/system-design-decisions/README.md`, `docs/system-design-decisions/policy-design-best-in-class-operating-model.md`, `docs/system-design-decisions/policy-design-case-decision-log.md` | `team-architecture` and `docs-adr-integrator` | `uv run pytest tests/repo_quality/tools/test_policy_design_case_decision_log.py -q` |
| Public evidence and command paths | `docs/reference/policy-design-case-evidence-paths.md` | `team-policyos-runtime` | `uv run pytest tests/repo_quality/tools/test_policy_design_case_documentation_paths.py -q` |
| Capability evidence and missing labels | `architecture/policy_design_case/capability_reality_report.json`, `docs/reference/policy-design-case-capability-ratchet.md` | `team-runtime-quality` | `uv run python tools/quality/validation/check_policy_design_case_capability_ratchet.py --repo-root .` |
| Operator triage for failed closeout | `docs/runbooks/policy-design-case-operator-triage.md` | `@platform-owners` with runtime and producer owners | Run the failing row's verifier from the triage table. |
| Rollout, hold, rollback, or kill switch | `docs/runbooks/policy-design-case-rollout-rollback.md` | `@platform-owners` with `team-policyos-runtime` | W5/W6 validation ladder in this guide and the rollout runbook. |
| Active implementation sequencing | `docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_IMPLEMENTATION_PLAN.md` | `team-policyos-runtime` | Plan validation commands plus wave closeout manifests. |
| Accepted wave summaries | `docs/archive/reports/YYYY-MM-DD-policy-design-case-<wave-or-phase>-closeout.md` | phase or wave owner | Closeout note minimum in `docs/reference/policy-design-case-evidence-paths.md`. |

## ADR And Decision Index

Use the structural ADR registry first when the question is "may this C0-C41
decision be implemented as architecture?" The registry names accepted ADRs,
fast-track ADRs, `new_adr_required` blockers, and `no_adr_required`
rationales. A row marked `new_adr_required` blocks structural implementation
until the named ADR is accepted and indexed.

Use the generated ADR index when the operator needs status, topic, package, or
supersession navigation:

- `docs/adr/index.md` is the status index.
- `docs/adr/by-topic.md` is the topic index.
- `docs/adr/index.toml` is the machine-readable source for the generated
  indexes.

Use the system-design decision directory when the question is still broader
than one ADR or is a reversible implementation-time decision. The decision log
is append-only and cannot narrow an accepted ADR. If a decision changes
cross-component contract semantics, case authority, producer duties, public
evidence semantics, or compatibility guarantees, promote it to a formal ADR.

## Public Evidence Path Discipline

Accepted evidence must be reconstructable from repo-owned paths, runtime
artifact refs, CAS refs, or accepted closeout notes. A chat note, hidden
terminal scrollback, workstation-only artifact, or temporary build output is
not durable evidence.

Use `docs/reference/policy-design-case-evidence-paths.md` for:

- raw research, synthesis, research-plan, implementation-plan, ADR, and
  closeout-note paths;
- transient command-output conventions under
  `_build/.tmp/policy-design-case/<phase-or-wave>/`;
- runtime-emitted evidence under `quality_evidence/*.json` or bundle paths;
- accepted phase and wave summaries under `docs/archive/reports/`;
- the minimum fields a closeout note must include.

If an operator needs to cite an output produced during a local run, cite the
runtime artifact ref or promote a human-readable conclusion into an accepted
closeout note. Do not move large runtime bundles into docs as a substitute for
runtime provenance.

## Tuned Parameter Owner Ledger

These rows are the W5.E operator view over the implementation plan's feature
flags and tuned config. A row is not final policy by being listed here. Every
runtime-facing tuned config still needs owner, version, default source, status,
feature or advisory posture, promotion evidence, rollback path, health
telemetry, and cleanup or revalidation condition.

| Control | Owner | Current posture | ADR or source | Promotion evidence | Rollback or safe disable |
| --- | --- | --- | --- | --- | --- |
| Universal PDC projection | `team-runtime-quality` with external-surface owners | Feature flag until public, dashboard, API, export, reviewer, expert, and machine truth tests pass. | ADR-0150, ADR-0162, W4.E, W5.A | I5 external consumer truth check plus public/export omission and blocker preservation tests. | Disable public projection and quarantine public/dashboard/API/export views; keep closeout reader and audit refs. |
| Effective-independence graded weights | `team-science-quality` | Feature flag plus governed config; strict hard-collapse can ship first. | ADR-0160, C13, C29 | Independence maps, semantic benchmark false-pass coverage, and corpus adjudication evidence. | Revert to strict hard-collapse and expose raw count only beside effective-independence limitations. |
| Acquisition planner commit | `team-domain-producers` with governance reviewers | Advisory/recommendation mode until human or governed commit path exists. | ADR-0166, E17 | Eligible strategy matrix, mandatory-gate dominance tests, and governed commit evidence. | Keep acquisition output as recommendation only; emit typed action or deficit records without automatic commit. |
| Review-effectiveness consequences | `team-quality-closeout` | Advisory only until longitudinal evidence supports gates. | ADR-0171, E19 | Mature review telemetry, owner-approved policy ref, and negative test that immature telemetry cannot block. | Disable blocking consequences; retain warning, review-intensity, and monitoring rows. |
| Calibration blocking | `team-science-quality` with `team-ddm` | Warning/review mode until mature-history thresholds are met. | ADR-0163, ADR-0171, C35, C41 | Calibration ledger maturity evidence and anti-laundering claim-registry tests. | Disable calibration blocking and keep historical calibration as future influence only. |
| Complexity budget closeout effect | `team-quality-closeout` | Advisory for existing runs; may gate growth of new controls when telemetry proves marginal value. | ADR-0164, C32 | Complexity telemetry, Net-MAV review, and pruning or merge decision evidence. | Remove hard closeout effect and keep complexity report as advisory telemetry. |
| Prompt/tool repair FMEA | `team-runtime-ops` | Advisory machinery-failure surface; missing FMEA refs fail prompt/tool authority validation. | C24, E19, W10.F | `prompt_tool_ledger.json` repair decisions with `failure_mode`, `severity`, `cause`, `recommended_mitigation`, and `residual_risk`, plus `operator_machinery_failures` and closeout limitation projection. | Keep repair output candidate-only or rerun the model/tool step; annotated repair failures cannot mint producer, evidence, or closeout authority. |
| Participation thresholds | `team-domain-producers` with governance reviewers | Governed config; matrix structure is fixed and numeric thresholds are provisional. | ADR-0167, C19, C34 | Participation semantic fixtures, affected-population provenance, dissent handling, and thin-consultation laundering tests. | Downgrade to limitation or review-required posture; never promote thin participation to prevalence authority. |
| Rare-domain scarcity path | `team-science-quality` | Explicit deficit and public limitation; no support inflation. | ADR-0160, E13, E22 | Portfolio scarcity report, effective support collapse reasons, and semantic false-pass fixtures. | Remove support uplift; publish scarcity as limitation, accepted deficit, or typed blocker. |
| Run-cost and degradation thresholds | `team-science-quality` with `@platform-owners` | Warning/limitation first; hard block only by authority-level policy. | ADR-0164, W2.C | Cost/degradation telemetry with owner, TTL, evidence ref, and closeout effect. | Disable hard gate and keep warning rows; cost alone cannot waive evidence authority. |
| Legal fallback tables | `team-domain-producers` with `@lex-owners` and governance reviewers | Governed namespace config; no universal hardcoded fallback. | ADR-0168, C7, C11 | Lex legal authority tests proving generic jurisdiction matches do not satisfy serious authority. | Disable fallback table, emit no-authority or limited-authority blocker, and require jurisdiction-specific owner review. |

## Validation Ladder

Run commands from `policy-engine/`. Preserve command output under
`_build/.tmp/policy-design-case/<phase-or-wave>/` while active, then promote
accepted conclusions to `docs/archive/reports/` or cite runtime artifact refs.

| Stage | Purpose | Command |
| --- | --- | --- |
| W5.E docs/runbook path check | Prove ADRs, evidence paths, tuned owners, validation ladders, capability evidence, and rollout runbooks are discoverable. | `uv run pytest tests/repo_quality/tools/test_policy_design_case_w5e_docs_runbooks.py -q` |
| W0/W1 docs source chain | Prove source ownership, structural ADR registry, and command evidence paths remain repo-owned. | `uv run pytest tests/repo_quality/tools/test_policy_design_case_source_ownership.py tests/repo_quality/tools/test_policy_design_case_structural_adr_registry.py tests/repo_quality/tools/test_policy_design_case_documentation_paths.py -q` |
| Docs lifecycle and navigation | Prove ADR index, plan lifecycle, nav, and docs gate behavior remain current. | `uv run pytest tests/repo_quality/tools/test_docs_lifecycle.py tests/repo_quality/tools/test_docs_gate.py -q` |
| MkDocs config and published docs | Prove nav fragments and generated MkDocs config do not drift. | `uv run polisyos-tools workspace tool-configs --check` and `uv run --extra docs python -m mkdocs build --strict` |
| W5 external surfaces | Prove public/export/dashboard/API consumers preserve closeout truth. | `uv run pytest tests/repo_quality/tools/test_policy_design_case_public_export.py -q` |
| Capability ratchet | Prove capability labels, evidence refs, and missing-state labels are honest. | `uv run python tools/quality/validation/check_policy_design_case_capability_ratchet.py --repo-root .` |
| W12.A local quick path | Re-execute the local ladder over the compiled universal PDC and report closeout honesty, useful design, and compilation truthfulness separately before live lanes. | `uv run python tools/quality/validation/run_policy_design_case_local_validation_ladder.py --repo-root . --profile quick --output _build/.tmp/production-quality/universal_pdc_local_validation_ladder.json` |
| W12.B compilation truthfulness audit | Execute W11.E over the universal outcome corpus and report rollout-posture compilation blockers without counting them as useful design or closeout-honesty failures. | `uv run python tools/quality/validation/run_compilation_truthfulness_audit.py --repo-root . --corpus tests/fixtures/universal-corpus --rollout-posture governed-pilot --output _build/.tmp/production-quality/w12b_compilation_truthfulness_audit.json` |
| W12.C domain coverage and critic diversity audit | Execute W11.F over the universal outcome corpus and report domain x authority useful-design coverage plus critic-diversity rollout caps. | `uv run python tools/quality/validation/run_domain_coverage_critic_diversity_audit.py --repo-root . --corpus tests/fixtures/universal-corpus --rollout-posture governed-pilot --output _build/.tmp/production-quality/w12c_domain_coverage_critic_diversity_audit.json` |
| W12.D universal outcome corpus run | Run every universal outcome corpus case through W6, W7, and W8.A and record per-case outcomes, graph artifact refs, adjudication deltas, and authority-level metric stratification. | `uv run python tools/quality/validation/run_universal_outcome_corpus.py --repo-root . --corpus tests/fixtures/universal-corpus --output _build/.tmp/production-quality/w12d_universal_outcome_corpus_run.json` |
| W12.D corpus-stub validation mode | Run the same W6/W7/W8.A path with W11.C-derived producer stubs so synthetic environments can prove non-blocked useful-design behavior without claiming production evidence authority. | `uv run python tools/quality/validation/run_universal_outcome_corpus.py --repo-root . --corpus tests/fixtures/universal-corpus --mode corpus_stub --producer-stub-dir tests/fixtures/universal-corpus/producer_stubs --allow-typed-blockers --output _build/.tmp/production-quality/w12d_universal_outcome_corpus_stub_run.json` |
| I7-bis integration realism check | Prove W6/W7 components are invoked through the runtime path, and surface typed blockers for missing producer bindings, graph edges, or warrant structures. | `uv run python tools/quality/validation/run_universal_compilation_integration_realism_check.py --repo-root . --allow-typed-blockers --output _build/.tmp/production-quality/i7bis_integration_realism_check.json` |
| Cloud one-lane rehearsal | Prove frozen revision/config behaves under the live canary path. | Commands in the implementation plan's W6 cloud one-lane path. |

Passing docs checks does not prove universal policy-design capability. It proves
operators can find the evidence and commands needed to make or reject that
claim.

## Corpus Stub Mode

Corpus-stub mode is a W12.D validation surface, not a producer replacement. It
loads `tests/fixtures/universal-corpus/producer_stubs/<case_id>.producer_stubs.json`
and returns adapter-shaped Fabric, Lex, Foundry, Scholar, and participation
responses derived from W11.C expert adjudication.

Authority boundary:

- authoritative for `corpus_validation_fixture` and
  `compiler_path_useful_design_probe`;
- may not be used for `production_closeout_authority`,
  `producer_domain_truth`, `claim_evidence_authority`, or
  `public_projection_authority`;
- maximum posture is `governed-pilot`;
- surface state is `surface_out_of_scope` for production authority.

Use `--mode real_producer` when evaluating production-adjacent producer
availability. Use `--mode corpus_stub` only to answer whether the universal
compiler, RequirementSpec bridge, producer pipeline, and Runtime PDC graph can
produce useful-design outcomes when the expert-adjudicated evidence response is
available.

## Capability Evidence

A capability claim may graduate only when the capability reality chain is
complete:

```text
typed contract/artifact
+ producer
+ persisted artifact/event
+ orchestration bridge
+ consumer
+ verification
+ external/audit/API/dashboard surface or explicit out_of_scope
+ negative/e2e semantic test
```

Use this path order:

1. Read `architecture/policy_design_case/capability_reality_report.json`.
2. Use `docs/reference/policy-design-case-capability-ratchet.md` to interpret
   maturity labels, debt points, readiness bands, and burn-down templates.
3. Open the latest accepted wave closeout under `docs/archive/reports/`.
4. Confirm each `repo://` evidence ref exists or is a runtime artifact ref that
   the run bundle can inspect.
5. If any label remains `contract_only`, `producer_missing`,
   `artifact_missing`, `bridge_missing`, `consumer_missing`,
   `verification_missing`, `implemented_but_not_orchestrated`,
   `surface_missing`, or `semantic_test_missing`, do not call the capability
   implemented.

When the surface is intentionally absent, record `surface_out_of_scope` with
owner, rationale, review date, and inspection path. Otherwise W5.E treats the
operator surface as incomplete.

## Rollout And Rollback

Use `docs/runbooks/policy-design-case-rollout-rollback.md` for the executable
rollout path. The short rule is:

1. Freeze git revision, scenario inputs, feature flags, tuned config versions,
   and validation command set.
2. Run the docs, external-surface, capability-ratchet, local validation,
   bundle-inspection, and canary commands required by the declared rollout
   posture.
3. Promote only if closeout honesty and useful-design evidence meet the
   declared posture. Typed blockers and accepted deficits count for honesty,
   not useful-design capability.
4. If rollback is needed, stop promotion, disable or downgrade the affected
   feature flags and tuned configs, quarantine public/dashboard/API/export
   projections, preserve the original bundle and CAS refs, and record a
   closeout note with owner and next action.

Rollback must never delete the evidence that explains why the rollout failed.

## Pattern Pass

Relevant patterns: `P03`, `P06`, and `P13`.

Existing anti-pattern found: W0.G and W1.E made source ownership and evidence
paths durable, but W5 operators still needed one discoverable page that joined
ADR lookup, system-design decision logs, tuned-parameter owners, validation
ladders, capability evidence, and rollout/rollback procedures. Without that,
the program could still depend on research-thread memory.

Target correct pattern: a proportional operator surface that links to existing
runtime, docs, ADR, closeout, and runbook owners instead of creating a parallel
authority source.

Capability reality for `W5.E` docs/runbook operations:

| Capability element | W5.E proof |
| --- | --- |
| Typed artifact/contract | This guide defines the operator lookup contract and tuned-parameter owner ledger. |
| Producer | Docs, ADR, runtime-quality, platform, and phase owners update this guide when command paths, ADR posture, tuned configs, or rollout controls move. |
| Persisted artifact/event | The guide is persisted at `docs/reference/policy-design-case-operator-guide.md`; rollout procedure is persisted at `docs/runbooks/policy-design-case-rollout-rollback.md`. |
| Orchestration bridge | Evidence paths, source ownership, structural ADR registry, ADR index, SDD index, implementation plan, runbook index, MkDocs nav, and docs inventory cross-link this guide. |
| Consumer | Operators, wave closeout authors, release reviewers, docs reviewers, ADR authors, and future agents use it to find authoritative evidence. |
| Verification | `tests/repo_quality/tools/test_policy_design_case_w5e_docs_runbooks.py` checks required sections, links, owners, validation commands, discoverability, and local-path rejection. |
| Surface | `docs/reference/index.md`, `docs/reference/documentation-inventory.md`, MkDocs reference nav, `docs/runbooks/index.md`, and the PDC triage runbook expose this guide and rollout runbook. |
| Negative/e2e semantic test | The W5.E regression fails if tuned thresholds lack owners/rollback paths, if rollout evidence is not repo-owned, or if local-only paths appear in the operator surfaces. |

Missing capability labels after this phase: none for W5.E operator docs and
runbook discoverability. Runtime Policy Design Case capabilities remain
governed by their own producer, artifact, bridge, consumer, surface,
verification, and semantic-test chains.

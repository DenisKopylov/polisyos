---
title: Policy Design Case Evidence Paths
status: active
owner: team-policyos-runtime
created: 2026-05-22
source_ownership: policy-design-case-source-ownership.md
structural_adr_registry: policy-design-case-structural-adr-registry.md
implementation_plan: ../plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_IMPLEMENTATION_PLAN.md
failure_patterns: policy-design-case-failure-patterns.md
operator_guide: policy-design-case-operator-guide.md
rollout_runbook: ../runbooks/policy-design-case-rollout-rollback.md
---

# Policy Design Case Evidence Paths

Owner: `team-policyos-runtime`
Source of truth: `docs/reference/policy-design-case-source-ownership.md`, `docs/reference/policy-design-case-structural-adr-registry.md`, `docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_IMPLEMENTATION_PLAN.md`, and `docs/reference/policy-design-case-failure-patterns.md`

This page is the W1.E documentation-path contract for E23 in the universal
Policy Design Case program. It extends the W0.G source-ownership ledger with
the operational paths future agents and operators use for raw sources,
synthesis, ADRs, validation commands, and closeout notes.

The rule is intentionally small: implementation evidence may be generated in a
local run, but durable claims must be traceable to repo-owned paths, runtime
artifact refs, or an explicit out-of-scope decision. A chat note, local
notebook, workstation download, or hidden terminal scrollback is not
implementation evidence.

## Canonical Path Matrix

| Evidence family | Canonical path | Owner | Authority boundary | Required consumer |
| --- | --- | --- | --- | --- |
| Raw research source detail | `docs/research/universal-policy-design/deep-research-reports-105-146-combined.md` | `team-policy-design-research` | Historical source detail only. Raw findings do not become runtime authority until normalized or ratified. | Synthesis authors, audit readers. |
| Normalized synthesis | `docs/backlog/universal-policy-design-case-research-results-consolidation.md` | `team-policyos` | Normalized C0-C41 research summary and decision backlog. | Research plan, implementation plan, ADR authors. |
| Research task contract | `docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_RESEARCH_PLAN.md` | `team-policy-design-research` | C/E task intent and conceptual gate map, not runtime code authority. | Implementation planning, research closeout. |
| Engineering wave plan | `docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_IMPLEMENTATION_PLAN.md` | `team-policyos-runtime` | Sequencing, wave gates, validation ladder, and phase ownership. | Wave implementers, integration barriers, reviewers. |
| Failure-pattern and missing-state labels | `docs/reference/policy-design-case-failure-patterns.md` | `team-policyos-runtime` | Pattern vocabulary and capability reality labels. | Plans, PRs, closeout notes, docs reviews. |
| Capability reality report | `architecture/policy_design_case/capability_reality_report.json` and `docs/reference/policy-design-case-capability-ratchet.md` | `team-runtime-quality` | Release/readiness vocabulary for complete and incomplete capability chains. | Release reviewers, wave implementers, integration barriers. |
| Policy Evidence Capability Graph Phase 2 construct registry | `architecture/policy_design_case/construct_registry_v1.yaml` and `src/polisyos/runtime/quality/construct_registry.py` | `team-runtime-quality` | Governed construct semantics, posture-specific authority requirements, deprecated scenario-family aliases, and corpus coverage blockers. It is construct authority metadata, not producer evidence authority. | W6.B obligation rules, Phase 4 resolver implementers, audit reviewers, universal-corpus coverage tests. |
| Wave 4 I4 runtime closeout manifest | `architecture/policy_design_case/wave4_i4_runtime_closeout_manifest.json` and `docs/archive/reports/2026-05-23-policy-design-case-wave4-closeout.md` | `team-runtime-quality` | Accepted Wave 4 transition evidence; records W4.A-W4.E/I4 capability states, produced runtime artifacts, I4 happy-path closeout, and scoped lifecycle typed-blocker behavior. | Wave 5 implementers, release reviewers, closeout owners. |
| Wave 5 I5 external consumer truth manifest | `architecture/policy_design_case/wave5_i5_external_consumer_truth_manifest.json` and `docs/archive/reports/2026-05-23-policy-design-case-wave5-closeout.md` | `team-runtime-quality` | Accepted Wave 5 transition evidence; records W5.A-W5.E/I5 capability states, public/reviewer/expert/machine contract fixtures, semantic pack coverage, and calibration/memory influence boundaries. | Wave 6 implementers, release reviewers, external-surface owners, operator runbook owners. |
| Wave 1 baseline smoke corpus | `architecture/policy_design_case/wave1_baseline_smoke_corpus.json` | `team-policyos-runtime` | Pre-implementation behavior record; not domain authority. | Runtime-quality tests, future wave regressions, closeout notes. |
| Wave 1 closeout reader smoke | `architecture/policy_design_case/wave1_closeout_reader_smoke.json` | `team-quality-closeout` | Closeout-only typed incomplete verdict; cannot substitute for domain, dashboard, readiness, packaging, or public-export authority. | Closeout reader tests, operator triage, Wave 2 closeout integration. |
| Source ownership ledger | `docs/reference/policy-design-case-source-ownership.md` | `team-policyos-runtime` | Repo-owned source chain and local-path rejection rule. | Future agents, ADR authors, W1.E/W5.E docs gates. |
| Structural decision sources | `docs/reference/policy-design-case-structural-adr-registry.md` | `team-policyos-runtime` | C0-C41 decision-source map; blocks structural implementation where ADR authority is missing. | Implementers, code reviewers, ADR owners. |
| ADR authority | `docs/adr/index.md`, `docs/adr/index.toml`, `docs/adr/**` | `team-policyos-runtime` | Ratified structural decisions. ADRs do not replace producer evidence. | Runtime implementers, docs and architecture reviewers. |
| Operator guide | `docs/reference/policy-design-case-operator-guide.md` | `team-policyos-runtime` with `@platform-owners` | W5.E operator lookup for ADRs, public evidence paths, tuned-parameter owners, validation ladders, capability evidence, and rollout/rollback procedures. | Operators, release reviewers, wave closeout authors, future agents. |
| Operator triage runbook | `docs/runbooks/policy-design-case-operator-triage.md` | `@platform-owners` with runtime and producer owners | Operational routing when closeout or publication fails. | Operators, incident commanders, closeout owners. |
| Rollout and rollback runbook | `docs/runbooks/policy-design-case-rollout-rollback.md` | `@platform-owners` with `team-policyos-runtime` | W5.E procedure for promoting, holding, rolling back, or disabling PDC surfaces, feature flags, and tuned configs. | Release owners, operators, governance reviewers. |
| System-design decision index | `docs/system-design-decisions/README.md`, `docs/system-design-decisions/policy-design-best-in-class-operating-model.md`, and `docs/system-design-decisions/policy-design-case-decision-log.md` | `team-architecture` and `docs-adr-integrator` | Design-review context and reversible implementation-time decision log; not accepted ADR authority. | ADR authors, operator guide, implementation reviewers. |
| Validation command map | `docs/reference/quality-gates.md` and this page | `@platform-owners` with `team-policyos-runtime` | Commands that prove docs/path ownership and broader docs gates. Shell history is not evidence. | PR authors, docs reviewers, integration barriers. |
| Phase closeout notes | `docs/archive/reports/YYYY-MM-DD-policy-design-case-<wave-or-phase>-closeout.md` and optional sibling `.json` | Phase owner with `team-policyos-runtime` | Accepted summary of command evidence, capability labels, residual blockers, and next actions. | Future waves, W5.E operator docs, release/acceptance reviewers. |

## Command Evidence Convention

Use these locations consistently:

| Evidence state | Path convention | Use | Promotion rule |
| --- | --- | --- | --- |
| In-progress command output | `_build/.tmp/policy-design-case/<phase-or-wave>/` | Scratch output, command logs, generated inspection files, and local diagnostics while a task is active. | May be cited only as transient command evidence. Promote the conclusion to a closeout note before it becomes durable. |
| Runtime-emitted evidence | `quality_evidence/*.json`, CAS refs, or run bundle paths printed by runtime tools | Run-specific artifacts produced by the system under test. | Keep the emitted artifact immutable; cite it from a closeout note or operator runbook rather than moving it into docs. |
| Wave-owned smoke evidence | `architecture/policy_design_case/wave<id>_<name>_smoke*.json` | Small repo-owned smoke artifacts that establish baseline behavior or typed blockers. | Keep these artifacts as bounded fixtures; they cannot stand in for producer-owned runtime evidence. |
| Accepted closeout summary | `docs/archive/reports/YYYY-MM-DD-policy-design-case-<wave-or-phase>-closeout.md` | Human-readable record of what was proven, which commands ran, and which labels remain open. | Required when a wave or phase claims durable completion. |
| Accepted machine closeout snapshot | `docs/archive/reports/YYYY-MM-DD-policy-design-case-<wave-or-phase>-closeout.json` | Machine-readable companion when a validator or closeout command emits structured evidence. | Optional for docs-only phases; required when generated tooling consumes the snapshot. |
| Validation command reference | `docs/reference/policy-design-case-evidence-paths.md`, `docs/reference/quality-gates.md`, and the phase section in the active plan | Canonical command list and expected evidence location. | Update in the same change that changes the command surface. |

Do not use workstation-local paths, home-directory downloads, browser-tab
notes, or temporary notebook locations as accepted evidence. `_build/.tmp/` is
allowed for working output only; a later reader must be able to reconstruct the
claim from the repo path, runtime artifact ref, or closeout note.

## W1.E And W5.E Validation

Run from `policy-engine/`:

```bash
uv run pytest \
  tests/repo_quality/tools/test_policy_design_case_source_ownership.py \
  tests/repo_quality/tools/test_policy_design_case_structural_adr_registry.py \
  tests/repo_quality/tools/test_policy_design_case_w5e_docs_runbooks.py \
  tests/repo_quality/tools/test_policy_design_case_documentation_paths.py \
  -q
```

When nav, published reference pages, or generated docs config changes, also run:

```bash
uv run polisyos-tools workspace tool-configs --check
uv run --extra docs python -m mkdocs build --strict
```

Broader docs-sensitive PRs should use the path-aware docs gate:

```bash
uv run polisyos-tools validation check-docs-gate --repo-root .
```

## W5.E Operator Extensions

W5.E extends this W1.E path ledger with an operator-facing guide and rollout
runbook:

- `docs/reference/policy-design-case-operator-guide.md` is the durable lookup
  path for ADR authority, system-design decision context, tuned-parameter
  owners, validation ladders, capability evidence, and rollout/rollback
  routing.
- `docs/runbooks/policy-design-case-rollout-rollback.md` is the executable
  operator path for promotion, hold, rollback, kill-switch, tuned-config
  downgrade, evidence preservation, and closeout-note recording.

Those pages do not become runtime authority. They are the W5.E bridge from
operator action to repo-owned evidence and runtime artifact refs.

## Policy Evidence Capability Graph Phase 2

Phase 2 adds the governed construct registry at
`architecture/policy_design_case/construct_registry_v1.yaml`, with the runtime
loader and semantic checks in `src/polisyos/runtime/quality/construct_registry.py`.
The registry is the owner of construct IDs, aliases, domains, entity scopes,
Concept Spine refs, time-role requirements, evidence modes, posture-specific
authority requirements, construct-validity floors, proxy-validation rules,
method contracts, legal patterns, Scholar patterns, and corpus bindings.

The old scenario families `production_msme_panel`,
`credit_program_registry`, and `regional_displacement_indicators` are
compatibility aliases only. They resolve to construct refs for migration, but a
family name alone cannot satisfy production authority.

Phase 2 verification is:

```bash
uv run pytest tests/unit/runtime/quality/test_construct_registry.py -q
uv run pytest tests/unit/runtime/quality/test_concept_spine.py -q
uv run pytest tests/unit/obligation_rules -q
uv run pytest tests/repo_quality/tools/test_universal_corpus_annotations.py -q
```

## Closeout Note Minimum

Every Policy Design Case phase or wave closeout note should record:

- phase or wave id, date, owner, and status;
- relevant `C*`, `E*`, `P*`, ADR, and implementation-plan refs;
- capability reality state and any missing labels;
- repo-owned evidence paths and runtime artifact refs;
- validation commands run, with pass/fail/blocked status;
- residual blockers, explicit out-of-scope surfaces, and next owner;
- whether any evidence is transient `_build/.tmp/` output that still needs a
  durable summary.

## Pattern Pass

Relevant patterns: `P03`, `P06`, and `P13`.

Existing anti-pattern found: W0.G and W0.H made source and ADR ownership
discoverable, but command evidence and closeout notes still needed one
operator-readable convention. Without that convention, future work could pass
review by pointing at local files, hidden notebooks, or remembered terminal
output.

Target correct pattern: keep the path contract small, publish it in the
reference surface, and validate that every required source family remains
repo-owned and discoverable.

Capability reality for `W1.E` and `W5.E` documentation operations:

| Capability element | W1.E proof |
| --- | --- |
| Typed artifact/contract | This reference page defines the canonical evidence families, command-evidence states, closeout-note minimum, and W5.E operator extension paths. |
| Producer | Phase owners and docs/runtime owners update the path matrix when evidence surfaces, operator guide sections, or rollout runbooks move. |
| Persisted artifact/event | The path contract is persisted at `docs/reference/policy-design-case-evidence-paths.md`; closeout notes persist under `docs/archive/reports/`. |
| Orchestration bridge | Source ownership, structural ADR registry, implementation plan, quality gates, docs inventory, operator guide, rollout runbook, and operator triage runbook cross-link this page. |
| Consumer | Future agents, PR authors, docs reviewers, operators, integration-barrier owners, W5.E runbook authors, and release reviewers. |
| Verification | `tests/repo_quality/tools/test_policy_design_case_documentation_paths.py` and `tests/repo_quality/tools/test_policy_design_case_w5e_docs_runbooks.py` check required paths, discoverability links, validation commands, closeout-note convention, tuned-owner/rollback coverage, and local-path rejection. |
| Surface | `docs/reference/index.md`, `docs/reference/documentation-inventory.md`, MkDocs reference nav, `docs/reference/policy-design-case-operator-guide.md`, `docs/runbooks/index.md`, and `docs/runbooks/policy-design-case-operator-triage.md` expose this page. |
| Negative/e2e semantic test | The regression test rejects local workstation paths and fails if the evidence ledger lacks raw source, synthesis, ADR, validation-command, or closeout-note paths. |

Missing capability labels after this phase: none for documentation path
ownership. W1.E must not leave a `contract_only`, `surface_missing`, or
`verification_missing` docs claim. Runtime Policy Design Case capabilities
remain governed by their own producer, artifact, bridge, consumer, surface,
verification, and semantic-test chains.

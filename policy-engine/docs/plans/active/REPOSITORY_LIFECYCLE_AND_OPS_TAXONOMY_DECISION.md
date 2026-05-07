---
title: Repository Lifecycle And Ops Taxonomy Decision
status: active
owner: team-ops
created: 2026-05-05
last_verified: 2026-05-05
stability: decision
related:
  - ../archive/2026-05-07-repository-best-in-class-remediation-master-plan.md
  - ../../how-to/manage-generated-artifacts.md
  - ../../how-to/release-policy.md
  - ../../how-to/deploy-runtime.md
  - ../../../architecture/generated_artifacts.toml
  - ../../../architecture/local_runtime_state.toml
  - ../../../ops/README.md
---

# Repository Lifecycle And Ops Taxonomy Decision

Phase 1.2 decision record for the best-in-class repository remediation
program.

This is a decision artifact. It defines lifecycle semantics, release/build
ownership, retention defaults, generated-artifact contract fields, and the
selected `ops/**` versus runner split. Phase 1.2 did not move files, rewrite
imports, delete local output, or relocate the legacy runner tree; Phase 2.2 now
records the physical runner relocation.

## Decision Summary

- Use five lifecycle classes: `source_committed`, `generated_committed`,
  `generated_ignored`, `runtime_ignored`, and `scratch_ignored`.
- Treat `release/**` as committed release input and evidence templates.
- Treat `_build/release/**` as ignored generated release output only.
- Treat `release-fragments/unreleased/**` as committed release-note input.
- Treat `_build/release-fragments/**` as ignored generated/archive output.
- Use default retention of 7 days for `_build/scratch/<run-id>`, 30 days for
  `_cache/**`, and 90 days for `_build/release/**` unless output is promoted to
  committed release evidence.
- Extend generated-artifact contracts around the fields `lifecycle`,
  `generator`, `verifier`, `owner`, `promotion_target`, and
  `stale_output_behavior`.
- Select the split ops layout: `ops/**` owns declarative operational artifacts
  and production contracts, while executable operational runners live in
  `tools/ops_runners/**`.

## Lifecycle Classes

Every path has exactly one lifecycle class. A directory may contain multiple
classes only when narrower child paths are explicitly declared.

| Lifecycle | Commit contract | Meaning | Cleanup and stale behavior |
| --- | --- | --- | --- |
| `source_committed` | Tracked by git. | Human-authored source, docs, policy, release inputs, templates, and production contracts. | Never removed by generated-output cleanup. Staleness is reviewed as source correctness. |
| `generated_committed` | Tracked by git with a registered generator and verifier. | Generated or recorded output that reviewers intentionally keep as a contract, snapshot, fixture, or durable evidence artifact. | Drift fails or requires manual review according to its verifier. It is updated only through the source of truth and generator. |
| `generated_ignored` | Ignored by git. | Recomputable generated output, build output, local reports, rendered release assets, local SBOM output, and generated archive output. | Cleanup eligible after the owning retention window. Promotion requires copying or moving to a committed target in a reviewed PR. |
| `runtime_ignored` | Ignored by git. | Local runtime state, run ledgers, CAS-like local stores, queues, and stateful operator/debug data. | Governed by `architecture/local_runtime_state.toml` and runtime-state cleanup rules, not generic build cleanup. |
| `scratch_ignored` | Ignored by git. | Temporary run directories, probes, experiments, and disposable intermediate files. | Default cleanup eligible after 7 days unless a run lock, owner note, or promotion record says otherwise. |

## Release And Build Path Rules

| Path | Lifecycle | Decision |
| --- | --- | --- |
| `release/**` | `source_committed` | Committed release input, release policy references, evidence templates, durable release ledgers, and promotion targets explicitly accepted by the release owner. |
| `_build/release/**` | `generated_ignored` | Generated release output only, including local SBOMs, rendered bundles, release-candidate staging output, and verification byproducts. No release source file may live here. |
| `release-fragments/template.toml` | `source_committed` | Committed authoring template for release-note fragments. |
| `release-fragments/README.md` and `release-fragments/unreleased/README.md` | `source_committed` | Committed contributor instructions for release-note input. |
| `release-fragments/unreleased/**` | `source_committed` | Committed unreleased release-note input. |
| `_build/release-fragments/**` | `generated_ignored` | Generated frozen/archive output created during release preparation and ignored by git. |
| `_cache/**` | `generated_ignored` | Recomputable tool caches. Default cleanup retention is 30 days. |
| `_build/scratch/<run-id>` | `scratch_ignored` | Per-run scratch area. Default cleanup retention is 7 days. |
| `.polisyos/**` | `runtime_ignored` | Local runtime state governed by the local runtime-state contract. |

The hard rule is that `_build/**` is never a source or template root. If a
generated release artifact becomes durable evidence, the promotion target is a
committed path such as `release/**` for structured release evidence or
`docs/archive/reports/**` for narrative evidence. The promoted artifact must
carry owner and verifier context in the PR.

## Retention Policy

| Path class | Default retention | Rationale | Promotion rule |
| --- | ---: | --- | --- |
| `_build/scratch/<run-id>` | 7 days | Scratch is short-lived and should not become hidden state. | Promote only the reviewed evidence subset to a committed target; leave run scratch ignored. |
| `_cache/**` | 30 days | Cache content is recomputable and should not affect source review. | No promotion target by default. If a cache-derived baseline is needed, regenerate it through a committed artifact family. |
| `_build/release/**` | 90 days | Release-candidate output may be useful for short-term audit, rollback, and comparison. | Durable evidence must move out of `_build/**` into a committed evidence target before the retention window expires. |
| `_build/release-fragments/**` | 90 days | Frozen release-note snapshots are release-candidate output, not authored source. | Published notes or durable evidence move to the release evidence target chosen by the release owner. |
| `.polisyos/**` | Local runtime-state policy | Runtime state may need component-specific backup or replay semantics. | Promotion follows `architecture/local_runtime_state.toml` and the owning runbook. |

Cleanup tools may use manifest timestamps when available and filesystem mtime
otherwise. Active locks, explicit owner notes, and promotion records must be
honored before deleting ignored runtime or release-candidate output.

## Generated-Artifact Contract Fields

Wave 1 records the following contract fields in
`architecture/generated_artifacts.toml` for every generated artifact family.
Wave 2 may split mixed families into narrower output-class families during
cleanup, but it must not invent new lifecycle semantics while moving files.

| Field | Required value |
| --- | --- |
| `lifecycle` | One of the five lifecycle classes in this decision. |
| `generator` | Canonical command, tool, workflow, or documented manual capture process that creates the output. |
| `verifier` | Command, CI gate, manual-review rule, or evidence requirement that proves the output is fresh enough to use. |
| `owner` | Accountable team that approves changes, retention exceptions, and promotion. |
| `promotion_target` | Committed path or release channel where ignored output may be promoted, or `none` when promotion is not allowed. |
| `stale_output_behavior` | One of `fail`, `warn`, `cleanup_eligible`, `ignored_by_policy`, or `block_release`. |

Existing fields remain valid during the transition:

| Existing field | Transitional meaning |
| --- | --- |
| `commit_policy = "committed"` | Usually `generated_committed`; Wave 2 may split a family if some outputs are actually source or ignored evidence. |
| `commit_policy = "mixed"` | Has an explicit family-level lifecycle and promotion target in Wave 1; Wave 2 may split it into narrower output classes when cleanup needs path-level precision. |
| `commit_policy = "local_ignored"` | Usually `generated_ignored`, unless the path is runtime state and must become `runtime_ignored`. |
| `regenerate_commands` | Initial value for `generator`. |
| `check_command`, `drift_gate`, `workflow` | Initial value for `verifier`. |
| `freshness_rule` | Human-readable bridge until `stale_output_behavior` is explicit. |

No generated artifact family may rely only on "this file looks generated" as
its contract. The generator, verifier, owner, promotion target, and stale-output
behavior must be explicit before Wave 2 cleanup can delete, warn on, or promote
its outputs.

## Ops And Runner Taxonomy

The selected repository layout is the split layout:

```text
ops/
  components/
  migrations/
  release/
  security/
  observability/
tools/
  ops_runners/
  devx/
  quality/
  research/
```

`ops/**` owns declarative operational artifacts and production contracts:
policies, release gates, deployment topology, observability rules, dashboards,
SLOs, migration contracts, component operation bundles, security baselines,
infrastructure templates, and runbook-linked operator contracts.

`tools/ops_runners/**` owns executable operational runners: scripts, CLIs,
wrappers, preflight checks, generators, deploy helpers, release helpers, and
other imperative code that acts on the declarative contracts.

Phase 2.2 completed the physical relocation into `tools/ops_runners/**`. New
operational runner work targets this namespace directly.

The co-located alternative remains a recognized fallback pattern:

```text
ops/
  declarative/
  runners/
```

It is not selected for the current Wave 2 move. Switching to that fallback
requires an explicit follow-up decision because it changes the contributor
answer for deploy policy versus deploy runner changes.

## Contributor Placement Rules

Use these rules after the Phase 2.2 relocation:

| Change | Source of truth |
| --- | --- |
| Deploy authorization policy | `ops/policy/policies/**` and the packaged policy copy under `ops/cloud/helm/**` when chart packaging is affected. |
| Deploy promotion gates and release policy | `ops/release/**`, `ops/security/**`, and release inputs under `release/**` or `release-fragments/unreleased/**`. |
| Deployment topology, environment contracts, and runtime operation contracts | `ops/deploy/**`, `ops/cloud/**`, `ops/runtime/**`, and future `ops/components/**`. |
| Observability, dashboards, alerts, and SLOs | `ops/observability/**`. |
| SQL or runtime-state migration contracts | `ops/migrations/**` until Wave 2 introduces narrower migration classes. |
| Deploy or release runner implementation | `tools/ops_runners/**`. |
| Contributor tooling, quality gates, and research helpers | `tools/devx/**`, `tools/quality/**`, and `tools/research/**`. |

Do not add new executable runners directly under `ops/**` unless a follow-up
decision selects the co-located `ops/declarative` plus `ops/runners` layout.

## Acceptance Check

- Lifecycle classes are defined with commit, cleanup, and stale-output
  semantics.
- Release, build, cache, scratch, and release-fragment paths have explicit
  lifecycle decisions.
- Retention defaults are defined for `_build/scratch/<run-id>`, `_cache/**`,
  `_build/release/**`, and `_build/release-fragments/**`.
- Generated-artifact contract fields are named and mapped from current
  `architecture/generated_artifacts.toml` fields.
- The selected ops runner target is `tools/ops_runners/**`.
- Contributor-facing docs can answer where to change deploy policy versus
  deploy runner code.
- No physical path relocation or cleanup was performed in Phase 1.2; the Phase
  2.2 patch implements the selected runner namespace.

---
title: Infrastructure SOTA Plan
status: active
owner: team-infrastructure
created: 2026-04-03
last_verified: 2026-05-05
stability: draft
---

# Infrastructure SOTA Plan

> Bringing the engineering platform around PolicyOS code and architecture to
> industry-leading level.
> Created: 2026-04-03

> Repository-topology supersession: the illustrative product-root `scripts/`
> layout below is historical planning context. Current placement rules are
> governed by `docs/reference/repository-topology.md` and
> `docs/plans/accepted/REPOSITORY_SOTA_PHASE_5_CLOSEOUT.md`.

---

## Scope and Assumption

This plan covers the infrastructure **around** the codebase and architecture:

- repository topology and source-of-truth rules;
- toolchain and environment reproducibility;
- ownership, review, and release governance;
- dependency management and upgrade policy;
- CI/CD, quality gates, and supply-chain integrity;
- test infrastructure and fixture strategy;
- developer ergonomics, onboarding, and operational readiness.

Working assumption for this plan:

- `policy-engine/` remains the **canonical product root**;
- the repository root remains a workspace wrapper / research perimeter, not the
  primary source of truth for product engineering workflows.

Important exception:

- GitHub-native repository control-plane files may still need to live at
  repository root or under root-level `.github/` due to platform constraints.
  Examples: Actions workflows, `CODEOWNERS`, issue templates, Dependabot /
  Renovate configuration, and merge-governance metadata.

If that assumption changes later, it should happen through a dedicated ADR and
topology migration, not ad hoc drift.

---

## Current State Summary

| Asset                            | Current state                                                                         | Quality                             |
| -------------------------------- | ------------------------------------------------------------------------------------- | ----------------------------------- |
| Python source                    | `1568` files / `477,977` LOC                                                          | Very large; strong modular layering |
| Python tests                     | `1005` files / `177,277` LOC                                                          | Strong depth and breadth            |
| Frontend source                  | `356` TS/TSX files / `52,373` LOC                                                     | Strong product-grade contour        |
| Architecture boundaries          | import policy + exceptions + CI enforcement                                           | Excellent                           |
| ABI / schema compatibility       | semantic snapshot gate exists                                                         | Excellent                           |
| Docs site                        | MkDocs Material + Diataxis structure + Pages publish                                  | Strong                              |
| Docs accuracy                    | `0` violations across `185` published markdown files                                  | Excellent                           |
| Public-surface docstrings        | `100%` semantic coverage on inspected public surface                                  | Excellent                           |
| Frontend quality                 | typecheck, lint, format, a11y, e2e, visual, Storybook, bundle gates                   | Excellent                           |
| Supply-chain base                | SBOM, vuln scan, signing workflow present                                             | Good foundation                     |
| Changelog discipline             | `CHANGELOG.md` exists and backfilled                                                  | Good start                          |
| Pre-commit hooks                 | backend pre-commit exists; frontend uses lefthook                                     | Good but split                      |
| Canonical Python baseline        | split across `pyproject`, `.python-version`, CI, docs                                 | Critical gap                        |
| Canonical repo root              | split between repository root and `policy-engine/`                                    | Critical gap                        |
| Ownership files                  | no `CODEOWNERS`, `SECURITY.md`, `SUPPORT.md`, `CODE_OF_CONDUCT.md`                    | Critical gap                        |
| Repository merge governance      | no explicit ruleset / merge-queue / stale-review policy                               | Significant gap                     |
| Dependency automation            | no Renovate / Dependabot config                                                       | Significant gap                     |
| Release policy                   | partial; versioning and release semantics still mixed                                 | Significant gap                     |
| Workflow identity hardening      | no explicit pinned-actions / OIDC / runner-trust policy                               | Significant gap                     |
| Secrets and config governance    | env vars are documented, but no unified taxonomy / rotation / injection policy        | Significant gap                     |
| Migration and rollout governance | SQL / schema / infra migration surfaces exist, but no unified rollout-class policy    | Significant gap                     |
| Generated artifact lifecycle     | multiple generated contracts/clients/fixtures exist, but no single lifecycle contract | Significant gap                     |
| Observability ownership          | metrics, dashboards, and alerts exist, but no explicit signal taxonomy and owner map  | Significant gap                     |
| Retention / backup / recovery    | archives and cold-tier hints exist, but no unified retention and restore policy       | Significant gap                     |
| Onboarding for outsiders         | strong reference/docs, weak role-based platform onboarding                            | Significant gap                     |
| Delivery-performance loop        | no explicit DORA-style platform KPI review                                            | Moderate gap                        |

### High-confidence strengths already present

- Architecture is not merely documented; it is actively enforced.
- Quality gates are unusually rich for both backend and frontend.
- Docs are already treated as a first-class artifact with CI validation.
- Contract compatibility is guarded with schema snapshots and semantic diffing.
- The codebase is large enough that investment in platform coherence will pay off
  immediately.

### Core diagnosis

PolicyOS is already strong in **internal engineering depth**, but not yet fully
SOTA in **platform coherence**.

The biggest remaining gaps are:

1. one canonical source of truth for product root, Python baseline, and toolchain;
2. formal ownership and review routing at package and platform boundaries;
3. release engineering and dependency governance as repeatable systems;
4. configuration, secrets, and generated artifacts treated as governed surfaces;
5. one-command developer bootstrap and environment diagnosis;
6. migration, retention, and recovery policy for stateful and generated assets;
7. role-based onboarding and runbook-quality operational documentation.

---

## Target State: Product-Grade Engineering Platform

The target is not "more tooling" by itself. The target is a repo where
hundreds of thousands of lines remain easy to grow, test, reason about, and
hand off because the engineering platform is predictable.

### Properties of the target state

- **One root of truth:** product workflows, docs, CI, and release logic agree on
  one canonical product root and one version/toolchain policy.

- **Explicit repo control plane:** GitHub-native governance files are treated as
  a deliberate repository control plane, not accidental competition with the
  product root.

- **One baseline per runtime:** Python, Node, lockfiles, CI images, and local
  bootstrap all converge on the same supported versions.

- **One contract per boundary:** architecture rules, public APIs, schema
  compatibility, ownership, and release semantics are explicit and enforced.

- **Configuration as code:** environment variables, secrets, profiles, and
  runtime modes are classified, documented, and governed by lifecycle rules.

- **One-command bootstrap:** a new machine can go from zero to green local
  verification through a short, documented bootstrap path.

- **One-command diagnosis:** environment drift, missing binaries, unsupported
  Python, broken locks, and stale generated artifacts fail early through a
  `doctor` path instead of surfacing during random tasks.

- **Structured ownership:** every package and critical workflow has a visible
  owner path, review path, and escalation path.

- **Governance by ruleset:** critical merge and review policy lives in GitHub
  rulesets / repository settings, not only in docs or team habit.

- **Short-lived machine identity:** CI/CD prefers OIDC or equivalent short-lived
  credentials over long-lived cloud secrets wherever the platform supports it.

- **Generated artifacts are first-class:** OpenAPI snapshots, schema snapshots,
  generated clients, fixture recordings, bundle stats, and similar outputs have
  authoritative sources, regeneration commands, and freshness gates.

- **Tiered quality gates:** fast PR gates, deeper nightly gates, and release
  gates are separated cleanly by cost and intent.

- **Progressive delivery:** risky runtime, config, and migration changes use
  canaries or equivalent staged rollout semantics with explicit abort signals.

- **Measured delivery performance:** platform reviews track deployment
  throughput and instability, not only anecdotal CI pain.

- **Operational memory:** incidents, replay, key rotation, dependency upgrades,
  benchmark regressions, and environment issues have runbooks rather than tribal
  knowledge.

- **Correlated observability:** logs, metrics, and traces are linked through a
  consistent context model so alerts lead to diagnosis rather than log hunting.

- **Recovery posture:** artifact retention, backup expectations, and restore
  procedures are defined instead of being implicit in local folders or CI
  artifacts.

### Representative target layout

```text
repo-root/
  .github/
    workflows/
    CODEOWNERS
    dependabot.yml
  SECURITY.md
  SUPPORT.md
  CODE_OF_CONDUCT.md

  policy-engine/
    pyproject.toml
    uv.lock
    .python-version
    .nvmrc
    .editorconfig
    .pre-commit-config.yaml
    .devcontainer/
    scripts/
      bootstrap.*
      doctor.*
      verify.*
      release.*
    docs/
      INFRASTRUCTURE_SOTA_PLAN.md
      explanation/platform-model.md
      how-to/setup-dev-environment.md
      how-to/respond-to-ci-failure.md
      how-to/release-policy.md
      how-to/manage-generated-artifacts.md
      reference/environment-matrix.md
      reference/ownership.md
      reference/quality-gates.md
      reference/configuration-profiles.md
      runbooks/
        dependency-upgrade.md
        runtime-incident.md
        artifact-signing.md
        replay-recovery.md
        backup-restore.md
        migration-rollout.md
```

### Canonical command surface

```bash
make bootstrap
make doctor
make test-fast
make verify
make docs
make run-runtime
make run-dashboard
make smoke
```

The exact task runner can be `make`, `just`, or a thin Python CLI wrapper. The
important part is not the tool itself, but the existence of a **small,
predictable command surface** that hides platform complexity.

---

## Industry Alignment Anchors

This plan is intentionally aligned with a small set of authoritative external
practice models, so that "SOTA" here means more than internal preference.

### Repository and workflow governance

- GitHub CODEOWNERS and rulesets / branch protection:
  - CODEOWNERS location precedence and self-protection for `.github/`;
  - required code-owner review;
  - stale review dismissal and "most recent reviewable push" semantics;
  - merge queue for busy protected branches;
  - required status checks sourced from a specific GitHub App.

### CI/CD and supply-chain security

- GitHub Actions secure use guidance:
  - least-privilege `GITHUB_TOKEN`;
  - pin third-party actions to full commit SHAs;
  - avoid risky inline-script interpolation of untrusted data;
  - prefer short-lived OIDC-based cloud auth over long-lived cloud secrets;
  - treat self-hosted runners as a high-trust surface, not a default.
- GitHub dependency review action and repository rulesets.
- OpenSSF Scorecard as a machine-checkable external lens on branch protection,
  code review, workflow safety, token permissions, pinned dependencies, and
  signed releases.

- SLSA for source/build provenance and two-party review expectations.
- NIST SSDF for a risk-based secure-development crosswalk.
- CISA SBOM guidance for release-frequency and dependency-coverage expectations.

### Configuration, versioning, and release communication

- Twelve-Factor config guidance:
  - config in environment variables;
  - env vars as granular orthogonal controls;
  - avoid brittle grouped "environment bundles" as the primary scaling model.
- Semantic Versioning:
  - public API must be declared, precise, and comprehensive;
  - released versions are immutable;
  - deprecations and breaking changes have explicit version semantics.
- Keep a Changelog:
  - human-curated release notes;
  - explicit deprecations / removals / security entries;
  - `Unreleased` as the staging area for the next release narrative.

### Reliability and operations

- Google SRE practices:
  - SLOs and error budgets;
  - blameless postmortems;
  - four golden signals for monitoring;
  - alerting and monitoring validation;
  - canarying and safe release progression;
  - release engineering as a first-class platform function.

---

## Execution Phases

This rollout follows a strict topology:

1. `Phase 0` is the only prerequisite phase. It establishes the baseline,
   source-of-truth rules, and bootstrap/doctor path that unlock every later
   phase.
2. `Phase 1` through `Phase 6` begin only after `Phase 0` is complete, but
   after that they are treated as a **fully parallel execution set**. None of
   these phases is conceptually "after" another.
3. `Phase 7` is the single final integration and acceptance phase. It is where
   we land cross-phase glue work, implement items that depend on outputs from
   earlier phases, and run final platform acceptance.

Within each phase, work streams should still run with non-overlapping ownership
windows and clear write scopes.

### Phase topology at a glance

```text
Phase 0
  -> unlocks Phase 1, Phase 2, Phase 3, Phase 4, Phase 5, Phase 6

Phase 1 \
Phase 2  \
Phase 3   \
Phase 4    > run fully in parallel after Phase 0
Phase 5   /
Phase 6  /

Phase 7
  -> integrates outputs from Phase 1-6
  -> implements deferred cross-phase items
  -> runs final acceptance and ratchet closeout
```

---

### Phase 0 — Source of Truth and Baselines (prerequisite)

**Duration:** 1 focused session. **Blockers:** none. **Must complete before
Phase 1-6.**

#### WS-0A: Canonical Product Root and Repository Topology

Goal: eliminate ambiguity between repository root and `policy-engine/`.

Deliverables:

- one ADR declaring `policy-engine/` as canonical product root;
- product README documents the collapsed product/workspace root;
- explicit `repo control plane` section describes what necessarily stays at the
  outer Git root for GitHub/platform reasons;

- explicit policy for what may live at repository root:
  - research materials;
  - workspace-only helper files;
  - repo-native GitHub governance files;
- explicit policy for what **must** live under `policy-engine/`:
  - product code;
  - product docs;
  - packaging and lockfiles;
  - release logic.

Done means:

- no contradictory product metadata across root and package entry points;
- a newcomer can tell in under 30 seconds where the actual product starts.
- engineers can also tell in under 30 seconds which files are root-level by
  platform constraint rather than by architectural drift.

#### WS-0B: Toolchain Baseline Unification

Goal: establish one coherent Python/Node baseline across local, CI, docs, and
automation.

Required actions:

- choose one supported Python baseline and enforce it everywhere;
- align:
  - `pyproject.toml`;
  - `.python-version`;
  - CI workflows;
  - `README.md`;
  - `CONTRIBUTING.md`;
  - local bootstrap docs;
- declare one supported Node baseline for frontend workflows;
- declare `uv` as canonical Python environment manager or deliberately keep a
  dual-mode story with documented guarantees.

Done means:

- `uv sync`, local pre-commit hooks, docs checks, and CI all target the same
  Python reality;

- there is no version split-brain left in published docs or tooling.

#### WS-0C: Bootstrap and Doctor Path

Goal: replace implicit setup knowledge with deterministic machine setup and
preflight diagnosis.

Deliverables:

- `bootstrap` command to install/verify all local prerequisites;
- `doctor` command to validate:
  - Python version;
  - Node version;
  - `uv` presence;
  - Playwright browsers;
  - lockfile freshness;
  - generated contract artifacts;
  - required environment variables for optional surfaces;
- `verify` command that runs the standard fast local gate.

Done means:

- a clean machine can become contributor-ready in one documented path;
- most "works on my machine" failures are caught before the first test run.

---

### Phase 1 — Governance, Ownership, and Review Routing

**Parallel work streams:** 5

#### WS-1A: CODEOWNERS and Package Ownership Map

Goal: make human ownership as explicit as architectural ownership.

Deliverables:

- `CODEOWNERS` covering:
  - `src/polisyos/core/**`
  - `src/polisyos/ir/**`
  - `src/polisyos/fabric/**`
  - `src/polisyos/foundry/**`
  - `src/polisyos/scientist/**`
  - `src/polisyos/lex/**`
  - `src/polisyos/runtime/**`
  - `apps/**`
  - `packages/**`
  - `docs/**`
  - `ops/**`
- `docs/reference/ownership.md` explaining:
  - subsystem owners;
  - fallback owners;
  - who approves boundary-crossing changes;
  - who owns release, docs platform, and incident response.

Minimal template:

```text
/src/polisyos/core/        @core-owners
/src/polisyos/ir/          @ir-owners
/src/polisyos/fabric/      @fabric-owners
/src/polisyos/foundry/     @foundry-owners
/src/polisyos/scientist/   @scientist-owners
/src/polisyos/runtime/     @runtime-owners
/apps/                     @frontend-owners
/packages/                 @frontend-owners
/docs/                     @docs-owners
/ops/                      @platform-owners
```

#### WS-1B: Platform Governance Files

Goal: fill the missing governance surface expected of a serious engineering
system.

Create:

- `SECURITY.md`
- `SUPPORT.md`
- `CODE_OF_CONDUCT.md`

Required contents:

- security reporting channel and SLA;
- supported versions / branches policy;
- support boundaries for internal vs external users;
- expected response mode for incidents, vuln reports, and operational outages.

#### WS-1C: PR and Change Taxonomy

Goal: standardize what kinds of changes exist and what gates they require.

Deliverables:

- PR template with change categories:
  - architecture;
  - contract / schema;
  - runtime behavior;
  - frontend;
  - docs;
  - ops / security;
  - dependency upgrade;
- required checklist per category;
- label taxonomy aligned with quality gates and release notes;
- "breaking / additive / internal" classification rules.

#### WS-1D: Versioning and Deprecation Policy

Goal: make version semantics intelligible and enforceable.

Deliverables:

- one versioning policy for:
  - package version;
  - architecture version language in docs;
  - schema versions;
  - runtime API versions;
  - frontend contract generation;
- deprecation window policy:
  - how long old schema/runtime fields stay supported;
  - how deprecation is announced;
  - what requires a migration guide.

Done means:

- there is no ambiguity between "architecture milestone", "schema version",
  "runtime API version", and package release version.

#### WS-1E: Repository Rulesets and Merge Governance

Goal: encode critical review and merge policy in the hosting platform, not just
in contributor memory.

Deliverables:

- repository ruleset for the default branch requiring pull requests;
- required code-owner review on owned paths;
- stale-approval dismissal and "approve the most recent reviewable push"
  semantics;

- required checks sourced from the expected GitHub App / workflow origin where
  supported;

- merge queue enabled for busy protected branches, or a documented rationale for
  not using it yet;

- `.github/` and `CODEOWNERS` self-protected by designated repository owners;
- explicit policy for signed tags and whether verified commit signatures are
  enforced on release-critical branches.

Done means:

- governance drift cannot quietly weaken review quality;
- reviewers and automation share the same merge contract.

---

### Phase 2 — Build, Dependency, and Environment Platform

**Parallel work streams:** 5

#### WS-2A: Dependency Governance and Extras Rationalization

Goal: keep optional capability surface large without making installation and
resolution unpredictable.

Deliverables:

- documented dependency tiers:
  - minimal contributor;
  - docs contributor;
  - runtime contributor;
  - full research / causal contributor;
  - frontend contributor;
- rationalized extras so overlapping umbrellas do not create resolver chaos;
- compatibility notes for heavyweight or platform-sensitive extras;
- explicit policy for when a dependency belongs in:
  - base install;
  - optional extra;
  - dev-only extra;
  - external system prerequisite.

#### WS-2B: Automated Dependency Upgrades

Goal: move upgrades from ad hoc work into a managed flow.

Deliverables:

- Renovate or Dependabot configuration with grouped PRs for:
  - Python tooling;
  - frontend tooling;
  - Playwright / Storybook stack;
  - security-sensitive runtime libraries;
  - GitHub Actions;
- upgrade cadence:
  - weekly for tooling;
  - biweekly for product dependencies;
  - immediate for critical vulns.

Done means:

- dependency freshness becomes a steady rhythm instead of a future "cleanup
  sprint".

#### WS-2C: Hermetic Build Environments

Goal: reduce hidden local variance across machines and CI.

Deliverables:

- devcontainer or equivalent reproducible local environment;
- documented cache strategy for:
  - `uv`;
  - npm;
  - Playwright browsers;
  - benchmark artifacts;
- pinned CI install flow matching local bootstrap;
- optional "CI parity" command for local validation.

#### WS-2D: Environment Matrix

Goal: make supported environments explicit instead of inferred.

Create `docs/reference/environment-matrix.md` with:

- supported OSes;
- supported Python versions;
- supported Node versions;
- CPU/GPU expectations;
- optional external binaries;
- what is "supported", "best effort", and "unsupported".

This document should be the reference point for contributor setup, CI design,
and bug triage.

#### WS-2E: Configuration Profiles and Secrets Governance

Goal: treat configuration and secret handling as governed infrastructure rather
than scattered env-var folklore.

Deliverables:

- env-var taxonomy:
  - public config;
  - sensitive runtime config;
  - CI-only secrets;
  - local developer-only toggles;
  - deprecated variables;
- Twelve-Factor-aligned rule that deploy-varying config lives outside code and
  that env vars are composed as orthogonal controls, not as brittle named
  bundles;

- canonical source for environment reference and profile examples;
- secret lifecycle policy:
  - where secrets are injected locally, in CI, and in production;
  - which secrets may never be stored in `.env`;
  - rotation expectations and owner;
- policy preferring short-lived machine credentials such as OIDC-based cloud
  auth over long-lived CI secrets when supported by the target platform;

- policy discouraging structured secret blobs in favor of individually scoped
  secret values where practical;

- use of protected deployment environments / reviewers for high-risk deploy
  secrets and production promotions;

- policy for generated security artifacts such as hidden sourcemaps, signing
  bundles, and audit exports;

- alignment with existing key rotation and auth/security docs.

Done means:

- contributors can answer "where should this value live?" without guesswork;
- production-only secrets do not leak into casual local workflows.

---

### Phase 3 — CI/CD, Release, and Supply-Chain Platform

**Parallel work streams:** 6

#### WS-3A: Workflow Consolidation

Goal: reduce duplicated and legacy workflow surfaces into one coherent model.

Required actions:

- inventory root-level and package-level workflows;
- decide which workflows are canonical and which are legacy or archival;
- consolidate docs, ABI, perf, and platform workflows into one maintained set;
- add `actionlint` validation to prevent YAML drift and workflow dead paths.

Done means:

- engineers know which workflows matter now;
- no critical process depends on legacy duplicates.

#### WS-3B: Tiered Quality Gates

Goal: separate fast PR confidence from slower platform-level assurance.

Target gate tiers:

| Tier        | Trigger    | Budget      | Purpose                                       |
| ----------- | ---------- | ----------: | --------------------------------------------- |
| Fast PR     | every PR   | `< 10 min`  | lint, imports, contract drift, fast tests     |
| Standard PR | every PR   | `< 25 min`  | runtime/frontend suites, a11y, smoke          |
| Nightly     | schedule   | `30-90 min` | integration, broader benchmarks, heavy extras |
| Release     | tag/manual | variable    | signed artifacts, SBOM, release packaging     |

Required outputs:

- explicit required-check matrix in docs;
- branch protection mapped to that matrix;
- no accidental coupling of fast and slow lanes.

#### WS-3C: Release Engineering

Goal: make releases reproducible, signed, and explainable.

Deliverables:

- tag-driven release workflow;
- automated changelog cut from structured labels or release fragments, but
  curated into Keep-a-Changelog-style human release notes;

- signed release artifacts;
- explicit rule that a published release version is immutable; fixes ship as a
  new version, not a mutated artifact;

- progressive delivery path for runtime-bearing releases:
  - canary or staged exposure step;
  - abort thresholds;
  - promotion checkpoints;
- published release notes with:
  - compatibility notes;
  - migration notes;
  - schema/runtime/API changes;
  - known limitations.

#### WS-3D: Security and Supply-Chain Ratchet

Goal: move existing SBOM/signing work from good foundation to policy-backed
release gate.

Required additions:

- release-time SBOM + vuln gate becomes part of release policy, not just an
  isolated workflow;

- each release or materially updated build publishes a fresh SBOM, with an
  explicit expectation of transitive dependency coverage where tooling permits;

- policy for tolerated CVEs and exception expiry;
- repository default `GITHUB_TOKEN` posture is read-only, with per-job
  permission escalation only where justified;

- third-party actions pinned to full commit SHAs;
- dependency review action required for manifest, lockfile, and workflow
  changes;

- secret scanning and workflow-permission review;
- policy for script-injection-safe workflow patterns when handling untrusted PR
  data;

- cloud deployment auth uses OIDC or equivalent short-lived credentials where
  supported;

- GitHub-hosted runners are the default trust model; self-hosted runners
  require an owner, isolation boundary, secret minimization, and preferably a
  just-in-time / ephemeral story;

- OpenSSF Scorecard run on a schedule and reviewed as an external security lens;
- artifact attestations / build provenance are generated for release artifacts
  and are verifiable by consumers or downstream automation;

- maintained SSDF / SLSA / Scorecard crosswalk showing which controls are
  enforced in repo policy versus by process;

- scheduled dependency / action audit;
- provenance artifacts retained with clear retention policy.

#### WS-3E: Benchmark and Cost Platform

Goal: performance regressions and platform cost regressions should be visible,
repeatable, and attributable.

Deliverables:

- benchmark taxonomy:
  - unit microbench;
  - workflow throughput;
  - frontend bundle and lighthouse;
  - selected infra-cost checks where useful;
- threshold ratchets with documented owner;
- benchmark result retention and summary format;
- policy for adding / retiring benchmark baselines.

#### WS-3F: Migration and Rollout Governance

Goal: unify how schema, SQL, OpenAPI, generated-client, and infra changes are
rolled out, validated, and, when needed, reversed safely.

Deliverables:

- migration classes:
  - additive safe;
  - additive with consumer sync;
  - destructive / freeze-window required;
  - forward-only operational migrations;
- rollout checklist covering:
  - schema snapshots;
  - runtime OpenAPI export;
  - generated clients;
  - SQL / RLS migrations;
  - Helm / Terraform changes;
  - feature flags or staged exposure plan where relevant;
  - canary / shadow / phased rollout stance for high-risk changes;
  - docs and runbooks;
- rollback / mitigation stance per migration class;
- explicit "migration owner" field for cross-boundary rollout PRs.

Done means:

- a reviewer can tell whether a change is just code, or a coordinated rollout.

---

### Phase 4 — Test Infrastructure and Reproducibility

**Parallel work streams:** 4

#### WS-4A: Test Taxonomy and Marker Policy

Goal: make the test surface understandable at repo scale.

Deliverables:

- documented test classes:
  - unit;
  - contract;
  - property;
  - integration;
  - performance;
  - frontend component;
  - frontend journey;
  - visual;
- marker policy aligned with that taxonomy;
- consistent naming for smoke, slow, flaky, and quarantine semantics.

#### WS-4B: Fixture and Seed Data Platform

Goal: make fixtures reusable, discoverable, and cheap to reason about.

Deliverables:

- fixture catalog describing canonical fixture families;
- policy for:
  - generated fixtures;
  - golden records;
  - snapshot refresh;
  - minimal seed datasets;
- separation of committed seed data vs large local research datasets;
- deterministic data builders where static fixtures are too brittle.

#### WS-4C: Local Integration Stack

Goal: turn multi-service confidence into a repeatable local smoke path.

Deliverables:

- one command to run backend + dashboard + required local dependencies;
- smoke profile for runtime/control-plane/front-end interaction;
- optional lightweight demo data load;
- explicit local ports, health checks, and shutdown behavior.

#### WS-4D: Flake Management and Test Economics

Goal: keep trust in CI high as the suite grows.

Deliverables:

- flaky test policy:
  - quarantine label;
  - owner;
  - expiry date;
  - criteria for re-entry;
- retry policy only where justified;
- reporting for top slowest suites and unstable tests;
- CI sharding strategy for large suites.

---

### Phase 5 — Architecture Guardrails and Developer Ergonomics

**Parallel work streams:** 5

#### WS-5A: Boundary Enforcement Expansion

Goal: preserve architectural quality as package count and team size grow.

Deliverables:

- existing import policy retained as core guardrail;
- additional checks for:
  - public facade drift;
  - deep-import creep across package boundaries;
  - generated artifact freshness;
  - workflow/config drift where appropriate;
- clear exception process with owner + expiry.

#### WS-5B: Public API and Compatibility Surface

Goal: make "supported surface" explicit for engineers and outsiders.

Deliverables:

- public-surface inventory per package;
- policy for `__all__`, lazy facades, and stable entrypoints;
- compatibility classification:
  - public stable;
  - public experimental;
  - internal;
- release and docs linkage to that classification.

#### WS-5C: Scaffolding and Templates

Goal: new subsystems should start from house style instead of improvisation.

Add generators or templates for:

- new package / module README;
- new connector;
- new governance pass;
- new runtime route;
- new benchmark;
- new ADR;
- new runbook.

Done means:

- architecture is easier to extend because the repository supplies its own
  golden path.

#### WS-5D: High-Signal Developer Surface

Goal: optimize for navigation and comprehension speed in a large repo.

Deliverables:

- short contributor command map in root package README;
- package-level README freshness policy;
- standard "where to start" section for major subsystems;
- consistent generated/reference artifact locations;
- contributor-facing "if you need to change X, start here" index.

#### WS-5E: Generated Artifacts and Codegen Lifecycle

Goal: make generated files predictable, reviewable, and non-mystical.

Covered surfaces:

- ABI schema snapshots;
- runtime OpenAPI snapshot;
- frontend generated API types / runtime clients;
- recorded contract fixtures;
- benchmark summaries and bundle stats where committed;
- audit or evidence artifacts that are intentionally checked in.

Deliverables:

- authoritative-source map for each generated artifact family;
- canonical regeneration command per family;
- rule for when generated outputs are committed vs ignored;
- drift gates aligned with that rule;
- ownership for approving generated diffs and regenerations.

Done means:

- no generated file is "magic";
- every committed generated artifact has a source, a command, and a freshness
  rule.

---

### Phase 6 — Operational Readiness and Onboarding

**Parallel work streams:** 6

#### WS-6A: Runbooks and Incident Surface

Goal: move critical operational knowledge out of heads and chat history.

Create runbooks for:

- dependency upgrade regression;
- runtime API outage;
- broken contract generation;
- artifact signing or SBOM failure;
- canary rollback or failed production promotion;
- replay / restore workflow;
- docs publication failure;
- benchmark regression triage.

Each runbook should include:

- symptom;
- likely causes;
- timeline capture expectations;
- first triage steps;
- rollback / mitigation;
- escalation owner;
- follow-up checklist;
- blameless postmortem section:
  - what went well;
  - what went poorly;
  - concrete action items with owners and dates.

#### WS-6B: SLO, Error Budget, and Reliability Language

Goal: give platform conversations a shared operational vocabulary.

Deliverables:

- service-level view for the runtime/control-plane surface;
- practical SLO definitions tied to measurable signals;
- error budget response policy;
- release-freeze policy when the budget is exhausted, with explicit carve-outs
  for security fixes and P0 restoration work;

- default postmortem trigger threshold for a single incident spending a large
  fraction of the rolling error budget, to be tuned per service;

- ownership for alerts and dashboard interpretation.

This does not require a giant SRE program. It requires a shared, explicit
language for when reliability is "good enough" and when feature work pauses.

#### WS-6C: Observability Topology and Alert Ownership

Goal: turn existing telemetry surfaces into an owned operational signal system.

Deliverables:

- signal taxonomy:
  - traces;
  - metrics;
  - logs;
  - security events;
  - frontend UX telemetry;
- golden-signal coverage for user-facing/runtime services and critical
  dependencies:

  - latency;
  - traffic;
  - errors;
  - saturation;
- dashboard and alert inventory with owner per dashboard/alert family;
- route from alert -> dashboard -> trace/log investigation -> runbook;
- trace/log correlation policy so incident responders can pivot between metrics,
  traces, and logs with shared identifiers;

- alert validation strategy using synthetic checks or known-good signal emitters
  for critical alerts;

- policy for high-cardinality metrics and telemetry cost discipline;
- explicit ownership for silent failures in docs publishing, codegen drift,
  replay failures, and control-plane degradation.

Done means:

- observability is not just "data exists", but "someone knows what signal to
  trust and who responds to it".

#### WS-6D: Role-Based Onboarding Tracks

Goal: make the system teachable to non-authors.

Create explicit onboarding tracks for:

- domain / policy reader;
- backend engineer;
- frontend engineer;
- platform / ops engineer;
- security / compliance reviewer.

Each track should answer:

- what this person needs to understand first;
- what they can safely ignore at first;
- which commands and docs they should use;
- what a first productive task looks like.

#### WS-6E: Backup, Retention, and Recovery Policy

Goal: define lifecycle rules for artifacts, runs, audit packages, CI artifacts,
snapshots, and operational data.

Deliverables:

- retention classes for:
  - CI artifacts;
  - benchmark outputs;
  - replay/state artifacts;
  - audit packages;
  - local snapshots;
  - cold-tier archives;
- policy for what is reproducible and may be discarded vs what must be retained;
- documented restore drills for key operational surfaces;
- recovery runbook for the main retained artifact families.

Done means:

- storage growth, artifact sprawl, and restore expectations are governed rather
  than accidental.

#### WS-6F: Handoff and Knowledge Capture

Goal: make ownership portable across time and people.

Deliverables:

- handoff template for subsystem changes;
- "why now" section for large refactors and infrastructure migrations;
- retirement checklist when deleting or superseding a workflow/tool/surface;
- quarterly platform review ritual;
- platform scorecard that includes delivery throughput / instability indicators,
  not only static policy compliance.

---

### Phase 7 — Integration, Acceptance, and Ratchet Closeout

**Starts only after Phase 1-6 are complete. This is the single sequential
closeout phase.**

#### WS-7A: Cross-Phase Integration and Deferred Closeout

Goal: land the work that should only happen once the outputs of parallel phases
exist together.

Typical scope:

- wiring together ownership docs, rulesets, and release flows so the final
  governance story is coherent end to end;

- aligning bootstrap / doctor / environment matrix / onboarding tracks into one
  contributor journey;

- implementing release/runbook/observability glue that depends on completed
  gates, runbooks, and signal inventories;

- landing any remaining docs, templates, or automation that depend on the final
  shapes of parallel-phase outputs;

- removing temporary compatibility shims or rollout notes that existed only to
  let Phases 1-6 proceed independently.

Done means:

- the platform reads and behaves like one integrated system rather than a set
  of independently improved surfaces;

- all intentionally deferred cross-phase tasks are closed or explicitly tracked
  as post-SOTA follow-up.

#### WS-7B: Platform Acceptance and End-to-End Quality Audit

Run one end-to-end audit and acceptance pass of:

- toolchain consistency;
- repo root coherence;
- ownership coverage;
- repository ruleset and merge-governance enforcement;
- required checks;
- release path;
- runbook presence;
- bootstrap and doctor quality;
- dependency freshness process;
- workflow identity hardening and runner trust model;
- config/secrets governance;
- generated artifact lifecycle;
- external security signals such as Scorecard findings and provenance
  completeness;

- delivery-performance signals such as lead time, deployment frequency, failed
  deployment recovery time, change fail rate, and deployment rework rate;

- retention and restore posture;
- observability ownership.

This acceptance pass should include:

- a clean-machine bootstrap rehearsal;
- representative contributor-path walkthroughs for at least backend, frontend,
  and platform roles;

- one release rehearsal or release-candidate dry run;
- one incident/runbook tabletop or equivalent quality check for critical
  operational paths.

The audit should produce a gap list with only:

- true misses;
- threshold values that need ratcheting;
- cleanup items required to simplify the platform.

#### WS-7C: Ratchet Policy

After closeout, no new subsystem or major surface should merge without:

- owner;
- docs entry point;
- test strategy;
- compatibility classification;
- review / merge governance implications considered;
- bootstrap/doctor implications considered;
- config/secrets implications considered;
- generated-artifact implications considered;
- observability and rollout implications considered;
- release/runbook implications considered when relevant.

This is the main difference between a one-time cleanup and an actually
SOTA engineering platform.

---

## Ongoing Maintenance Policy

After SOTA closeout:

- Baselines are changed deliberately, never implicitly.
- Each dependency exception has an owner and expiry date.
- Each architecture exception has an owner and expiry date.
- Each flaky-test quarantine has an owner and expiry date.
- Each config/secret exception has an owner and expiry date.
- Each workflow/security exception has an owner and expiry date.
- Each postmortem action item has an owner, due date, and closeout check.
- Each new package must ship with:
  - README;
  - ownership mapping;
  - public-surface stance;
  - test placement;
  - docs impact reviewed.
- Each quarter, run one platform review covering:
  - CI cost and duration;
  - dependency freshness;
  - release quality;
  - DORA-style throughput / instability metrics;
  - observability noise and alert quality;
  - generated artifact drift burden;
  - retention footprint and recovery drills;
  - postmortem action closure rate;
  - external supply-chain posture drift;
  - onboarding friction;
  - top recurring local environment failures.

---

## Effort Estimation

| Phase   | Scope                                                                              | Effort   |
| ------- | ---------------------------------------------------------------------------------- | -------: |
| Phase 0 | root-of-truth, baseline, bootstrap/doctor                                          | 3-5 days |
| Phase 1 | ownership, governance files, review taxonomy                                       | 2-4 days |
| Phase 2 | dependency platform, environment matrix, hermetic setup, secrets/config governance | 5-8 days |
| Phase 3 | workflow consolidation, release, supply-chain ratchet, migration governance        | 6-9 days |
| Phase 4 | test infra cleanup and reproducibility                                             | 4-6 days |
| Phase 5 | scaffolding, guardrails, developer surface, generated-artifact governance          | 4-6 days |
| Phase 6 | runbooks, observability, retention/recovery, onboarding, SLO language              | 6-9 days |
| Phase 7 | integration, acceptance, deferred cross-phase closeout, ratchet                    | 3-4 days |

Total: **31-49 focused engineering days**, depending on whether topology and
release changes require cross-cutting cleanup.

Expected wall-clock on the intended topology:

- `Phase 0`;
- then `Phase 1-6` in parallel;
- then `Phase 7`.

That gives an approximate critical-path duration of **12-18 focused working
days**, depending on staffing and how much deferred integration lands in
Phase 7.

---

## Priority Matrix

| Priority | Work stream           | Why it is high leverage                                                   |
| -------- | --------------------- | ------------------------------------------------------------------------- |
| P0       | WS-0A / WS-0B         | Removes split-brain around root, Python, CI, and docs                     |
| P0       | WS-0C                 | Converts setup pain into deterministic bootstrap + diagnosis              |
| P0       | WS-1A / WS-1B         | Makes ownership, security, and support explicit                           |
| P0       | WS-2E                 | Makes secrets/config a governed surface instead of folklore               |
| P1       | WS-2A / WS-2B         | Prevents dependency sprawl and stale upgrades                             |
| P1       | WS-3A / WS-3B         | Turns many good checks into a coherent quality system                     |
| P1       | WS-3C / WS-3D / WS-3F | Makes releases, supply-chain, and coordinated rollouts production-grade   |
| P1       | WS-4C                 | Gives contributors and reviewers a reliable local smoke path              |
| P2       | WS-5C / WS-5E         | Lowers the cost of extending architecture and managing generated surfaces |
| P2       | WS-6C / WS-6E         | Converts telemetry and retained state into operationally usable systems   |
| P2       | WS-6D                 | Improves onboarding for engineers and non-engineers alike                 |
| P2       | WS-6A / WS-6B / WS-6F | Reduces operational fragility and handoff risk                            |

---

## Tooling Requirements

Core:

```bash
python3.14
uv
node 22
npm
docker
```

Recommended:

```bash
pre-commit
playwright
mkdocs-material
actionlint
shellcheck
hadolint
```

Optional but high-value:

```bash
devcontainer
renovate or dependabot
ossf-scorecard
cosign
syft
grype
gitleaks
```

---

## Success Criteria

The platform reaches SOTA-closeout when the following are true:

1. Product root and toolchain baseline are unambiguous in code, docs, and CI.
2. A clean contributor machine reaches green local verification in under
   20 minutes through one documented bootstrap path.
3. `doctor` catches baseline drift before routine development starts.
4. `CODEOWNERS` covers 100% of critical product paths.
5. `SECURITY.md`, `SUPPORT.md`, and conduct/support expectations exist and are
   current.
6. Repository rulesets enforce pull-request-based changes, owned reviews, and
   stable merge semantics on the main branch.
7. Secrets and environment profiles have a documented taxonomy, injection path,
   and rotation ownership.
8. CI/CD uses a hardened identity model:

   - default read-only `GITHUB_TOKEN`;
   - pinned third-party actions;
   - dependency review on dependency-bearing changes;
   - OIDC or equivalent short-lived cloud auth where supported;
   - documented runner trust policy.
9. Dependency updates run on a fixed cadence through automation.
10. Required PR gates are documented, enforced, and separated by cost tier.
11. Releases produce signed artifacts, attestations/provenance, changelog
    entries, compatibility notes, and rollout classification when migrations are
    involved.
12. Generated artifacts have authoritative sources, regeneration commands, and
    freshness rules.
13. Local smoke verification exists for the main runtime + dashboard path.
14. Every major subsystem has a visible onboarding path for a new engineer.
15. Critical platform operations have runbooks.
16. Reliability policy is explicit:

    - SLOs exist for key surfaces;
    - error-budget response is defined;
    - rollout freezes and postmortem triggers are documented.
17. Retention and restore expectations exist for key artifact families.
18. Observability has named owners, golden-signal coverage, and clear
    alert-to-runbook routes.
19. Quarterly platform review includes delivery-performance metrics and
    postmortem-action follow-through.
20. No contributor has to infer:

- which root is canonical;
- which files are root-level by GitHub/platform constraint;
- which Python version is real;
- who owns a package;
- where a secret or env var belongs;
- how to regenerate a committed artifact;
- how to release safely;
- where to start when CI fails.

---

## Final Note

PolicyOS does **not** need a generic enterprise-process layer. It already has a
rare amount of architectural discipline and technical depth. The goal of this
plan is to complete the missing outer shell so that the existing code quality is
matched by equally strong repository governance, release engineering, developer
ergonomics, and operational clarity.

That is the step from "very strong codebase" to "SOTA engineering platform".

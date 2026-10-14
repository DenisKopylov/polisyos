# How-to Guides

Task-focused procedures for work you have already scoped. If you are new to the
repository, start with [Contributor Start Here](../reference/contributor-start-here.md).
For the product's goals and boundaries, follow the architecture pages linked
from the contributor guide; this section covers steps for a selected task.

For an initial reading route, use [Contributor Start Here](../reference/contributor-start-here.md)
→ [Getting Started](../tutorials/getting-started.md) → [Onboarding Tracks](onboarding/index.md)
→ the relevant recipe below → the nearest reference or package README. Tutorials
demonstrate individual surfaces; they do not prove a functional end-to-end policy
flow or a recommendation ready for publication.

Repository documentation is authored in English as its sole official language.
See the [Documentation Language Policy](../reference/documentation-language.md)
for translation and localization rules, the [Reader Vocabulary and Search
Routes](../reference/reader-vocabulary.md) for canonical destinations, and
[Evaluate Documentation Usability](evaluate-documentation-usability.md) for a
human-study protocol. The protocol has not yet been run with human participants.

## Prepare the environment and choose a path

| Task | Guide | Coverage |
| --- | --- | --- |
| Install the Python, documentation, or frontend toolchain | [Installation](install.md) | Bootstrap profiles, prerequisites, and troubleshooting |
| Choose a path for your role | [Onboarding Tracks](onboarding/index.md) | Backend, frontend, platform, security, and domain/policy tracks |
| Migrate an older branch to current contracts | [Post-Refactor Migration](post-refactor-migration.md) | Trinity, public surface, runtime contracts, and path-aware documentation checks |

## Add or change a product surface

| Task | Guide | Coverage |
| --- | --- | --- |
| Add a runtime endpoint | [Add Runtime Route](add-runtime-route.md) | Scaffold, app wiring, OpenAPI, and client checks |
| Add a supported Python import path | [Add Public Facade](add-public-facade.md) | `__all__`, facade ownership, and public-surface guardrails |
| Add an IR type with a schema lifecycle | [Add Schema-Backed IR Type](add-schema-backed-ir-type.md) | Model/enum, schema catalog, and ABI snapshot |
| Connect a data source or Fabric connector | [Add Data Source](add-data-source.md) | Connector registration and profile |
| Update the dashboard API client | [Update Runtime Dashboard API Client](update-runtime-dashboard-api-client.md) | OpenAPI → generated client → dashboard types |
| Add a Scientist governance pass | [Write Governance Pass](write-governance-pass.md) | Pass registration and blocker/warning semantics |
| Update schemas and API snapshots | [Manage Schemas](manage-schemas.md) | ABI snapshots, OpenAPI export, and drift checks |

## Run and operate the system

| Task | Guide | Coverage |
| --- | --- | --- |
| Deploy the Runtime API | [Deploy Runtime](deploy-runtime.md) | App factory, configuration, dashboard, and production notes |
| Run or ingest through the control plane | [Use Control Plane](use-control-plane.md) | Run/ingest/Lex operations, jobs, workers, and outbox |
| Diagnose a failed run | [Debug Failed Run](debug-failed-run.md) | Timeline, lineage, and control-plane state |
| Perform causal analysis | [Run Causal Analysis](run-causal-analysis.md) | Discovery, identification, bounds, sensitivity, and strategic response |
| Configure the Lex pipeline | [Configure Lex Pipeline](configure-lex-pipeline.md) | Stage-level and control-plane procedures |
| Run benchmarks | [Run Benchmarks](run-benchmarks.md) | Benchmark registry and report artifacts |

## Verify and release a change

| Task | Guide | Coverage |
| --- | --- | --- |
| Change CI/CD or a release workflow | [Operate the CI/CD Platform](operate-ci-cd-platform.md) | Canonical workflows, required checks, and supply-chain policy |
| Review a migration or rollout | [Review Migrations and Rollouts](review-rollouts.md) | Migration class, rollout checklist, rollback, and owner |
| Change a committed generated output | [Manage Generated Artifacts](manage-generated-artifacts.md) | Lifecycle map, regeneration, and approval owners |
| Change versioning or deprecation policy | [Release, Versioning, and Deprecation Policy](release-policy.md) | Version namespaces, deprecation windows, and migration guides |
| Apply GitHub labels and branch rules | [Apply GitHub Governance](apply-github-governance.md) | Manual UI checklist for tracked governance |

For documentation changes, use the [Documentation Style Guide](../style-guide.md)
and the documentation-only workflow in [Contributor Start Here](../reference/contributor-start-here.md).
That page also identifies the `docs` profile, targeted Markdown lint, strict
MkDocs build, and documentation-accuracy check; the path-aware
`check-docs-gate` selects additional checks based on changed paths.

# Reference

Related explanation: [Architecture](../explanation/architecture.md).

Owner: `@docs-owners`
Backup owner: `@platform-owners`
Source of truth: `mkdocs.yml`, `docs/reference/**`, and the generated/manual reference pages linked from this index

> Полная справка по API, типам, эндпоинтам и конфигурации PolicyOS.

This page is a high-level navigation map only. Subsystem-specific behavioral
claims live in the linked child reference pages.

## Modules

| Module                          | Exports                                                                                            | Description                                                              |
| ------------------------------- | -------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| [IR](ir/index.md)               | 171 types                                                                                          | Canonical contract layer — schemas for policies, analytics, observations |
| [Foundry](foundry/index.md)     | 3 exports                                                                                          | Computation engine — `compile()`, `compile_program()`, and `execute()`   |
| [Scientist](scientist/index.md) | 4 exports                                                                                          | Orchestration — workflows, governance passes, experiment state           |
| [Lex](lex/index.md)             | 58 types                                                                                           | Legal text processing — norm packs, interventions, knowledge             |
| [Fabric](fabric/index.md)       | 9 connectors                                                                                       | Data fabric — connectors, profiles, world queries                        |
| Frontend consumer surfaces      | `apps/runtime-dashboard/`, `packages/runtime-api-client/`, `apps/runtime-reference-shell/` | Dashboard, generated runtime client, and static reference shell          |

## Other

| Page                                                                 | Description                                                                                            |
| -------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| [REST API](api/index.md)                                             | 53 HTTP endpoints — runs, control plane, artifacts                                                     |
| [CLI](cli.md)                                                        | 4 command-line tools — polisy, polisyos, polisyos-foundry, polisyos-causal-capabilities                |
| [Schemas](schemas.md)                                                | 82 JSON schemas with ABI versioning                                                                    |
| [Public Surface](public-surface.md)                                  | Explicit supported package entrypoints and compatibility classes                                       |
| [Generated Artifacts](generated-artifacts.md)                        | Authoritative source map, regeneration commands, and freshness rules                                   |
| [Repository Topology](repository-topology.md)                         | Final clean-cut product-root, docs, tools, tests, ops, data, and local-state placement map             |
| [Documentation Inventory](documentation-inventory.md)                | Docs control ledger: source plans, owners, current QA evidence, and coordination conflicts             |
| [Contributor Start Here](contributor-start-here.md)                  | “If you need to change X, start here” navigation index                                                 |
| [Configuration](configuration.md)                                    | Variable-by-variable environment reference                                                             |
| [Dependency Platform](dependency-platform.md)                        | Dependency tiers, extras policy, compatibility notes                                                   |
| [Environment Matrix](environment-matrix.md)                          | Supported OS/Python/Node/runtime surfaces                                                              |
| [Configuration Environment Registry](configuration-env-registry.md)  | Ownership, defaults, validation, and conflict rules for bootstrap env vars                             |
| [Configuration Profiles](configuration-profiles.md)                  | Env taxonomy, profile examples, secret governance                                                      |
| [Logging and Trace Context](logging.md)                              | Explicit bootstrap model, trace correlation fields, and operator logging posture                       |
| [Security and Compliance Operations](security-compliance.md)         | Key rotation, CSRF cookie-mode posture, audit retention/export, and compliance query workflow          |
| [Platform Acceptance Audit](operations/platform-acceptance-audit.md) | Cross-surface evidence map for acceptance, contributor-path rehearsals, and retained operational proof |
| [Ownership](ownership.md)                                            | Subsystem owners, fallback owners, and boundary approval rules                                         |
| [Quality Gates](quality-gates.md)                                    | PR taxonomy, labels, compatibility classes, and review expectations                                    |
| [Tools Reference](tools.md)                                          | Generated command registry for `polisyos-tools` and related workspace tooling                          |
| [Merge Governance](merge-governance.md)                              | Default-branch merge contract, required checks, and ruleset policy                                     |
| [Ratchet Policy](ratchet-policy.md)                                  | Required evidence for any new subsystem or major surface after Phase 7 closeout                        |
| [Operations](operations/index.md)                                    | SLOs, observability, retention/recovery, handoff and scorecard policy                                  |
| [Scientist Evidence and Acceptance](scientist/remediation-status.md) | Machine-readable workstream closure plus published Phase 0/1/3/4 acceptance anchors                    |
| [Platform Changelog](changelog.md)                                   | Operator-facing summary of major platform-contract changes across remediation waves                    |

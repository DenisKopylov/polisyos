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
| [Policy Design Case Failure And Repair Patterns](policy-design-case-failure-patterns.md) | Agent-facing anti-pattern and correct-pattern register for governance, evidence, runtime-quality, and PDC closeout |
| [Policy Design Case Capability Ratchet](policy-design-case-capability-ratchet.md) | W1.A capability reality report, debt algebra, purpose multipliers, readiness bands, and burn-down templates |
| [Policy Design Case Layer 3 Grounding Inventory](policy-design-case-layer3-grounding-inventory.md) | G0 pre-adapter audit surface for v2 discovery/search readiness, zero adapter admission, health metrics, no-hardcode gates, and ADR-0175 |
| [Policy Design Case Layer 3 Substrate Grounding](policy-design-case-layer3-substrate-grounding.md) | G1 EXPERT/MACHINE audit surface for substrate grounding, SourceContract v2 binding, L1/L5/L6 search health, and acquisition gap routing |
| [Policy Design Case Layer 3 Causal Forecast](policy-design-case-layer3-causal-forecast.md) | G2 all-audience causal forecast tier surface for L2 SKG search, Foundry validity, S10 ForecastSupport, W12D routing, uncertainty, and denied uses |
| [Policy Design Case Layer 3 Analytics Search](policy-design-case-layer3-analytics-search.md) | G3 proof-carrying analytics search surface for L2/SKG and IR catalog coverage, artifact certificate resolution, S11 predictive posture binding, W12D routing, and denied uses |
| [Policy Design Case Layer 3 Legal Mandate Search](policy-design-case-layer3-legal-mandate-search.md) | GL EXPERT/MACHINE legal mandate search surface for L3 Legal KG search, false-abstention recall, claim-level legal authority, mandate handoffs, consumer gates, and public reference-only projection |
| [Policy Design Case Layer 3 Promotion Gate](policy-design-case-layer3-promotion-gate.md) | G4 PUBLIC/REVIEWER/EXPERT/MACHINE shadow-to-governed promotion surface for A-completeness, weakest-boundary composition, P26/S7 human-decision integrity, consumer gates, and public projection refs |
| [Policy Design Case Layer 3 Proving-Ground Conversion](policy-design-case-layer3-proving-ground-conversion.md) | G5 PUBLIC/REVIEWER/EXPERT/MACHINE first proving-ground conversion surface for pinned W12.D inputs, G4 handoff resolution, conversion eligibility, envelope health, W12.D consumer gate, and projection-only public refs |
| [Policy Design Case Layer 3 Bounded Agent](policy-design-case-layer3-bounded-agent.md) | G6 PUBLIC/REVIEWER/EXPERT/MACHINE bounded arbitrary-request adapter for policy-grammar projection, allowlisted agent/tool audit, G5 bridge, replay continuity, grounded result or abstention, and projection-only public refs |
| [Policy Design Case Layer 3 Health-Metric Governance](public-surface.md#policy-design-case-generated-audit-surfaces) | G8 EXPERT/MACHINE health-metric governance surface for metric registry normalization, cross-metric diagnosis, D4.4 corpus re-basing receipts, closeout signal consumer gate, replay manifest, and projection-only public refs |
| [Policy Design Case Source Ownership](policy-design-case-source-ownership.md) | W0.G repo-owned source chain from raw research to synthesis, C/E/P ids, ADRs, and implementation gates |
| [Policy Design Case Evidence Paths](policy-design-case-evidence-paths.md) | W1.E canonical paths for raw sources, synthesis, ADRs, validation commands, command evidence, and closeout notes |
| [Policy Design Case Structural ADR Registry](policy-design-case-structural-adr-registry.md) | W0.H `docs/reference/policy-design-case-structural-adr-registry.md` map from C0-C41 structural decisions to ADRs, blockers, or explicit no-ADR rationales |
| [Policy Design Case Operator Guide](policy-design-case-operator-guide.md) | W5.E operator lookup for ADRs, system-design decision indexes, public evidence paths, tuned-parameter owners, validation ladders, capability evidence, and rollout/rollback procedures in `docs/runbooks/policy-design-case-rollout-rollback.md` |
| [Run-Cost Enforcement Gate](runtime/run-cost-enforcement-gate.md) | W10.D authority-level cost enforcement over provider calls, tokens, compute spend, embeddings/searches, wall-clock, retry, and acquisition budgets |
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

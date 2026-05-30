# ADR-0174: Policy Evidence Capability Graph

## Status

Accepted

## Date

2026-05-25

## Owner And Review

Owner: `team-runtime-quality`
Integration spine owner: `team-integration-spine`
Review date: `2026-06-30`

The integration spine owner accepts the relationship-to-existing-waves mapping
below for Phase 0. Any later change that changes the mapping must update this
ADR or supersede it before implementation continues.

## Context

Wave 12 exposed that runtime evidence authority still exact-matches legacy
scenario-family strings while the production-data estate already contains the
real capability infrastructure:

- L1 Dataset Catalog with DCAT-shaped dataset, distribution, metric binding,
  schema profile, observation, and variable-alignment tables.
- L2 Scholar KG with causal claims, transport scores, contested edges,
  parameters, boundary conditions, and adjudications.
- L3 Lex KG with normative facts, thresholds, amendments, temporal audit,
  references, provisions, and legal entities.
- L4 Ukraine normalized administrative panels.
- L5 measurement, identification, trust-tier, schema-regime, proxy, and
  governance registries.
- L6 Foundry method-contract and simulation bundles.

The architectural defect is not missing data. It is that runtime authority sees
L7 legacy curated contracts and scenario-family strings while L1-L6 already
hold the production evidence capability surface. A new data lake or new catalog
would repeat P01/P02/P03: contract-only capability, thin orchestration, and
hidden internal richness.

This ADR locks the authority semantics before code changes begin for the
Policy Evidence Capability Graph plan.

## Decision

C1, C2, and C3 remain one ADR. They are split into named commitments for test
and review, but they are not independent decisions: construct selection,
release-time replay, and authority composition are one authority boundary.

### C1 - Construct Is The Primary Semantic Axis

Runtime evidence selection must resolve from construct requirements, not from
`source_family`, `metric_id`, folder names, producer bundle names, or legacy
scenario-family strings. `source_family` may remain only as a compatibility
projection during migration.

Scenario-family strings such as `production_msme_panel`,
`credit_program_registry`, and `regional_displacement_indicators` are
compatibility projections. They are not authority selectors.

### C2 - Capability Index Is Release-Time Compiled, Signed, And Replayable

Each production-data release emits exactly one capability-index reference set:
DuckDB primary store, manifest, sha256, summary, DCAT JSON-LD projection, and
PROV-O lineage projection.

Closed Policy Design Cases must store the frozen capability index ref,
construct registry ref, authority composition rule ref, and production data
release ref. Replay uses those refs, not the current mutable filesystem.

L1-L6 are existing infrastructure. They must be wired into the capability
compiler and resolver before any new catalog is built. L7 curated contracts may
serve as compatibility fixtures and smoke coverage only.

### C3 - Authority Envelope Is Composed, Not Averaged

Authority is a minimum across load-bearing dimensions: trust tier,
identification mode, construct validity, schema-regime alignment, time-scope
alignment, legal authority, rights/access, effective independence, and
historical-prior effect.

High confidence in one dimension cannot compensate for a missing or blocked
dimension in another. Scholar confidence cannot compensate for missing legal
authority. Administrative data cannot compensate for rights that forbid claim
evidence use.

Simulation outputs are never production claim evidence unless separately
validated by producer authority and re-emitted under an admissible authority
envelope.

Historical PDC priors can cap confidence, route review, trigger acquisition, or
shape warnings, but they cannot satisfy current claim evidence under the C41
historical-prior firewall.

## Relationship To Existing Implementation Waves

This ADR accepts the relationship table from
`docs/plans/active/POLICYOS_POLICY_EVIDENCE_CAPABILITY_GRAPH_PLAN.md`.

| This plan phase | Existing wave or phase it extends or replaces | Coexistence semantics |
| --- | --- | --- |
| Phase 1 - Capability Index Compiler | New artifact consumed by W6.B obligation rules, W7.A-E RequirementSpec compilers, W8.E/W8.F graph inspection, W11.E truthfulness audit, and W12 validation. | Parallel release artifact. It does not replace the source catalogs; it promotes them into authority-aware runtime metadata. |
| Phase 2 - Construct Registry | Extends W2.A Concept Spine and cross-references W6.B Governed Obligation Rule Catalog. | `Construct` is a policy-decision-bearing subset of the concept spine. Vertical obligation rules emit obligations whose required evidence references constructs, not source-family strings. |
| Phase 3 - Authority Composition | Extends W8.F Effective Independence Graph and W8.E conflict materialization. | Authority composition reads W8.F independence factors and W8.E conflict markers before a capability can satisfy a claim. |
| Phase 4 - Data Resolver | Replaces the W7.A `_required_data_families` heuristic and closes the A1 feature-flag shim. | Data requirements resolve construct -> capability -> binding status; legacy family fallback remains only during deprecation. |
| Phase 5 - Multi-modal Consumers | Replaces or extends W7.B Legal, W7.C Method, W7.D Scholar, W7.E Participation, and W6.F HypothesisLedger/critic integration internals. | Each producer consumes capability refs through its own authority boundary. LLM and historical prior paths remain advisory/capping signals unless admitted by producer authority. |
| Phase 6 - Acquisition Planner | Extends W3.G and W7.G acquisition planning. | Acquisition strategies become construct-aware, owned, costed, and linked to first-class failure-mode nodes. |
| Phase 7 - Audit, Export, Replay, And Sunset | Extends I7-bis, W11.E truthfulness tools, W12.A-D validation, and W9.F replay. | Shims are sunset in `architecture/shims.toml`; replay uses frozen capability-index refs or a frozen legacy reader for old PDCs. |

## Structural Commitment

The accepted owner boundary is:

- `policy_evidence_capability_graph`: a release-time compiled graph over L1-L7,
  with L7 marked compatibility-only.
- `construct_registry`: a governed subset of the existing concept spine, not a
  competing vocabulary.
- `requirement_to_capability_resolver`: the runtime bridge from
  `RequirementSpec` to capability binding results.
- `architecture/shims.toml`: the owner of the scenario-family-authority sunset.
- `architecture/policy_design_case/capability_reality_report.json`: the owner
  of Phase 0 baseline labels and later phase transitions.

## Authority Boundary

The capability graph may be authoritative for:

- capability metadata compiled from production-data releases;
- construct-to-capability binding status;
- authority-envelope admissibility decisions;
- replay refs for closed cases;
- audit, DCAT, PROV-O, card, and white-space projections derived from the
  typed index.

It may not be authoritative for:

- raw file presence as evidence authority;
- LLM-generated constructs, requirements, legal readings, or summaries;
- simulation-only outcomes as production claim evidence;
- historical PDC priors as current claim evidence;
- legacy scenario-family strings as final selectors.

## Negative Laundering Tests

| Commitment | Test ID | Laundering blocked |
| --- | --- | --- |
| C1 | `tests/unit/data_requirement/test_compiler.py::test_source_family_list_is_derived_from_compiled_requirements_not_legacy_fixture` | Legacy scenario fixture families cannot override compiled requirement families. |
| C2 | `tests/unit/runtime/quality/test_replay.py::test_policy_evidence_replay_refs_fail_closed_for_missing_or_mutable_refs` | Closed PDC replay cannot use missing refs, `latest`, `current`, or mutable production-data filesystem paths instead of frozen capability refs. |
| C3 | `tests/unit/runtime/quality/test_calibration_ledger.py::test_historical_prior_refs_fail_claim_registry_evidence_slots` | Historical-prior refs cannot satisfy current claim evidence slots under C41. |

Additional authority-boundary guards:

- `tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py::test_w12d_corpus_stub_mode_can_produce_useful_design_without_production_authority`
  proves corpus stubs can support useful-design scoring without production
  closeout authority.
- `tests/unit/runtime/quality/test_hypothesis_ledger_candidate_firewall.py::test_unverified_llm_candidate_cannot_satisfy_legal_authority_slot`
  proves LLM candidates cannot satisfy authority slots without producer
  validation.

## Feature Flag / Advisory Posture

`POLISYOS_DATA_REQ_FAMILY_FALLBACK_FROM_HARDCODED` remains default `true` until
Phase 4 flips it. The flag is a compatibility bridge only. It preserves current
runtime behavior while the construct registry and resolver are wired, and it
does not make scenario-family strings authoritative.

The Phase 0 regression test is:

- `tests/unit/data_requirement/test_compiler.py::test_family_fallback_flag_default_keeps_hardcoded_heuristic_until_phase4`

## Revision Path

Supersede this ADR before any implementation:

- makes `source_family` or scenario-family strings authority selectors again;
- treats new catalog construction as a prerequisite before wiring L1-L6;
- allows current mutable files to determine closed-case replay;
- averages authority dimensions so a strong factor compensates for a blocked
  factor;
- lets simulation, LLM, corpus stub, or historical-prior artifacts satisfy
  production claim evidence without producer authority.

## Related Decisions

- Related: ADR-0147 Production Evidence Authority Ordering.
- Related: ADR-0152 Semantic Binding, Lineage, And Claim Evidence.
- Related: ADR-0156 Policy Design Case Runtime Quality Assurance Profile.
- Related: ADR-0158 Concept Spine And Multi-Jurisdiction Reconciliation.
- Related: ADR-0159 Production Evidence Producer Contracts For Lex, Fabric,
  Scholar, And Data Forge.
- Related: ADR-0160 Evidence Portfolio, Independence Map, Multiverse, And
  Synthesis.
- Related: ADR-0166 Evidence Acquisition Decision Boundaries.
- Related: ADR-0168 Legal Hierarchy And Competence Boundaries.
- Related: ADR-0172 Balanced Memory Influence Ledger.
- Related: ADR-0173 Obligation Frontier And Bundle Control.

## Validation

Phase 0 validation:

```bash
uv run pytest tests/repo_quality/tools/test_docs_lifecycle.py -q
uv run pytest tests/repo_quality/tools/test_policy_design_case_capability_ratchet.py -q
uv run pytest tests/unit/data_requirement/test_compiler.py::test_family_fallback_flag_default_keeps_hardcoded_heuristic_until_phase4 -q
rg -n "POLISYOS_DATA_REQ_FAMILY_FALLBACK_FROM_HARDCODED.*true|scenario-family-authority" architecture/shims.toml src/polisyos/data_requirement/compiler.py tests -S
```

## Capability Reality And Pattern Pass

Relevant patterns: P01, P02, P03, P04, P05, P06, P07, P08, P09, P10, P12,
P14, and P15.

Existing anti-patterns found:

- P06: scenario-family strings are still runtime compatibility projections.
- P02: L1-L6 have mature producer assets but no shared requirement-to-capability
  bridge.
- P03: dataset, Lex, Scholar, Foundry, and simulation richness is not yet
  visible as a single audit surface.
- P15/P05: LLM, simulation, corpus stub, and historical-prior artifacts need
  explicit non-authority boundaries.

Target correct pattern: compile an authority-scoped capability graph from
existing L1-L6 assets, keep L7 as compatibility-only, resolve requirements by
construct, and freeze replay refs on closeout.

Phase 0 baseline labels:

- `policy_evidence_capability_graph`: `contract_only`
- `construct_registry`: `producer_missing`
- `requirement_to_capability_resolver`: `producer_missing`

Acceptance signal: ADR-0174 is accepted, indexes include it, the shim registry
records `scenario-family-authority`, the capability ratchet records the Phase 0
baseline labels, and the fallback regression proves current behavior remains
stable before Phase 4 sunset.

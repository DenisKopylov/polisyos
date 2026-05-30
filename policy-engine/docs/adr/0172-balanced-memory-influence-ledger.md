# ADR-0172: Balanced Memory Influence Ledger

## Status

Accepted

## Date

2026-05-22

## Context

Universal Policy Design Case work needs cross-run learning without turning
historical cases into current-run evidence. Existing Scientist memory already
records scoped failure lessons, contamination checks, revocation events, and
warning-only retrieval. That is useful but incomplete: learning only from
failures recreates P11 by making the system conservative while omitting
successful search/review patterns and unresolved opportunities.

The missing decision is not whether memory may influence later work. ADR-0163
already allows historical priors to influence future routing, budget, review,
uncertainty, and authority caps while forbidding current-run evidence closure.
The missing decision is the balanced memory shape for success, failure, and
opportunity records, and the runtime influence boundary that prevents P15
historical-prior or LLM speculation laundering.

This ADR unblocks C25/E21 for W2.F Balanced Memory Schema. It does not promote
Wave 5 retrieval behavior or any calibrated blocking threshold.

Source traceability is repo-owned:

- raw ledger:
  `docs/research/universal-policy-design/deep-research-reports-105-146-combined.md`
- normalized synthesis:
  `docs/backlog/universal-policy-design-case-research-results-consolidation.md`
- research plan:
  `docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_RESEARCH_PLAN.md`
- implementation plan:
  `docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_IMPLEMENTATION_PLAN.md`
- failure-pattern register:
  `docs/reference/policy-design-case-failure-patterns.md`
- structural ADR registry:
  `docs/reference/policy-design-case-structural-adr-registry.md`

## Decision

1. Balanced memory records have exactly three semantic kinds:
   `failure`, `success`, and `opportunity`.
2. Balanced memory records must carry scope, expiry, revocation state,
   contamination controls, source classification, and an authority boundary.
3. The canonical persisted Scientist memory surface remains the existing
   CAS-backed lesson registry. W2.F extends it instead of creating a parallel
   memory store.
4. Runtime quality influence records are the only current-run handoff shape for
   memory influence. They may authorize future search, future review, routing,
   or acquisition suggestions, but never current claim evidence.
5. Failure memories may warn about anti-patterns and guide review. Success
   memories may guide future search and review. Opportunity memories may guide
   review and acquisition planning.
6. No memory kind can close, support, refute, or block a current claim. Claim
   support and refutation still require current producer evidence bound through
   the claim registry.
7. LLM-originated memories are recordable only as `candidate_unverified` or
   `rejected_speculation`. They cannot emit active influence records until a
   non-LLM producer or human-review owner emits a separate verified record.
8. Hidden-eval, canary, private benchmark, and sentinel contamination blocks
   memory persistence and influence.

## Structural Commitment

W2.F introduces:

- `BalancedMemoryRecord` in Scientist orchestration memory;
- `BalancedMemoryScope` with visibility, tenant/domain/workflow/method/task
  scope, and expiry;
- `BalancedMemoryAuthorityBoundary` with `authoritative_for` and
  `may_not_use_for`;
- `MemoryInfluenceRecord` in runtime quality;
- claim-registry validation that rejects memory influence refs in current
  evidence slots;
- conversion helpers between balanced memory records and existing
  `LessonCard` artifacts.

The implementation must be `extend_existing` over:

- `polisyos.scientist.orchestration.memory.failure_lessons`;
- `polisyos.scientist.orchestration.memory.applicability`;
- `polisyos.scientist.orchestration.memory.contamination`;
- `polisyos.scientist.methods.search.lessons`;
- runtime quality authority-boundary conventions.

## Authority Boundary

Balanced memory may be authoritative for:

- future search guidance;
- future review guidance;
- future routing posture;
- future acquisition suggestions;
- historical learning traceability;
- memory lifecycle and revocation facts.

Balanced memory may not be authoritative for:

- current claim evidence;
- current claim closure;
- claim support;
- claim refutation;
- legal authority;
- data authority;
- method authority;
- closeout verdicts;
- replacing producer evidence;
- replacing claim-bound registry refs.

The runtime influence record must fail validation if it carries evidence-slot
refs, claim-closure refs, claim-support refs, or claim-refutation refs.

## Tuned Parameter

These values are governed configuration, not structural truth:

- default memory TTL by domain, tenant, workflow, method, or authority level;
- confidence cutoffs for future retrieval ranking;
- influence ranking weights;
- opportunity prioritization weights;
- review-intensity adjustments;
- mature-history thresholds for future authority caps.

Changing these values does not require a new ADR if the no-current-evidence
boundary remains intact. Allowing memory to close, support, or refute current
claims requires a new ADR and is disallowed by default.

## Negative Laundering Tests

Implementation must include negative tests proving:

- success memory cannot enter a current claim evidence slot;
- LLM-candidate memory cannot emit active influence;
- contaminated memory cannot be persisted or influence a run;
- revoked or expired memory cannot influence a run;
- success and opportunity memories persist alongside failure memories without
  being demoted into failure-only semantics.

## Affected E Tasks

This ADR unblocks:

- E21 Balanced Memory for W2.F schema and influence-record boundaries.

It constrains:

- E20 Calibration Ledger, because calibration and memory share the historical
  priors firewall;
- E22 Semantic Evaluation, because false-pass packs must include memory
  laundering attempts;
- E5 external surfaces, because future Wave 5 projections must show memory as
  influence, never evidence.

## Validation

Runtime behavior is validated by:

```bash
uv run pytest \
  tests/unit/scientist/orchestration/memory/test_balanced_memory.py \
  tests/unit/runtime/quality/test_memory_influence_records.py \
  -q
```

ADR and registry discoverability are validated by:

```bash
uv run pytest tests/repo_quality/tools/test_policy_design_case_structural_adr_registry.py -q
```

## Capability Reality And Pattern Pass

Reuse classification: `extend_existing`. The existing Scientist lesson
registry, scope checks, contamination checks, revocation helpers, and memory
authority records are the right foundation. W2.F extends those contracts with
success and opportunity memory plus runtime influence records.

Relevant anti-patterns:

- P11 failure-only memory: memory must represent success and opportunity
  patterns where failure lessons already exist.
- P15 LLM speculation laundering: LLM-originated memories remain candidate or
  rejected speculation and cannot emit active influence.
- P05 authority dilution: memory influence records declare forbidden current
  uses and fail closed when evidence-slot refs appear.
- P10 semantic adequacy gap: negative tests prove no-current-evidence behavior,
  not only constructor validity.

Capability state after W2.F schema:

- typed contract/artifact: `BalancedMemoryRecord` and `MemoryInfluenceRecord`;
- producer: `ReflexiveMemoryFacade.record_balanced_memory(...)`;
- persisted artifact/event: existing CAS-backed `LessonRegistry` `LessonCard`
  artifacts and indexes;
- orchestration bridge: runtime `MemoryInfluenceRecord`;
- consumer: future search/review/routing consumers through influence records;
- current-run claim-registry consumers fail closed if memory influence refs are
  placed in evidence slots;
- verification: unit tests named above;
- surface: runtime quality influence record payloads, with external projection
  deferred to W5.D/W5.A;
- semantic test: no-current-evidence, LLM-candidate, contamination, revocation,
  success/opportunity persistence tests.

Missing capability labels after W2.F schema:

- `surface_out_of_scope` for public/dashboard/API exposure until W5.D/W5.A,
  owned by `team-policyos-runtime`, review date 2026-06-30, inspection path
  `docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_IMPLEMENTATION_PLAN.md`.

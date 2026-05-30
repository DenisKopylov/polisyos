# ADR-0173: Obligation Frontier And Bundle Control

## Status

Accepted

## Date

2026-05-23

## Context

Universal Policy Design Case compilation needs rich obligation discovery without
turning every generated concern into an unbounded closeout gate. C38 identifies
this as the obligation-explosion problem: W6.A facets, W6.B governed rules,
deterministic critics, producer blockers, historical memory, reviewers, public
contestation, and LLM formulators can all emit plausible obligations, but they
do not carry the same authority.

The source chain is repo-owned:

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

This ADR unblocks C38 for W6.C. It preserves the authority boundaries from
ADR-0147, ADR-0156, ADR-0160, ADR-0164, ADR-0166, ADR-0168, ADR-0169,
ADR-0171, and ADR-0172.

## Decision

1. Obligation control uses exactly three runtime layers:
   candidate ledger, bundle ledger, and blocking frontier.
2. The candidate ledger is append-only, unbounded, and never blocks closeout
   directly. Every row preserves its raw `source_class`.
3. The bundle ledger is canonicalized by
   `(family, scope, authority_profile, temporal_window, remedy_path)`.
   There may be at most one active bundle per key.
4. The blocking frontier contains only bundles that pass authority allowance,
   legal/privacy admissibility, current-run relevance, and material public-risk
   gates.
5. Frontier promotion is lexicographic: authority allowance, admissibility,
   current-run relevance, material public risk, priority ceiling, marginal
   assurance value, cost/degradation/reviewer burden, then complexity budget.
6. Deferred and rejected bundles remain visible with reason, owner, timestamp,
   candidate refs, and reopen trigger.
7. Raw LLM candidates cannot enter the blocking frontier. They may stay in the
   candidate ledger or a non-blocking bundle until producer validation re-emits
   a non-LLM source class.
8. Historical failures may influence review and future routing, but they do not
   close current-run evidence and do not become mandatory current blockers by
   count alone.

## Structural Commitment

W6.C introduces `polisyos.obligation_graph` as the canonical owner for:

- `FacetSnapshot`, the field-level W6.A input contract used by W6.C;
- `GovernedObligationRule`, the field-level W6.B input contract used by W6.C;
- `ObligationCandidateInput`, preserving raw source classification;
- `CandidateLedgerEntry`;
- `ObligationBundle` and `BundleKey`;
- `FrontierItem`;
- `DeferredObligationRecord`;
- `ObligationGraph`;
- `compile_obligation_graph(...)`;
- `write_obligation_graph_artifact(...)`;
- `obligation_graph_audit_surface(...)`.

The implementation is `build_new` only for the C38 compiler owner. Reuse was
checked first: existing runtime quality, acquisition, soft-gate, memory, and
scorecard modules provide surrounding governance patterns, but none owns the
three-tier obligation ledger or source-ceiling promotion semantics.

## Tuned Parameter

These values are governed configuration, not structural truth:

- `max_frontier_items`;
- total complexity-cost budget;
- reviewer-burden budget;
- marginal assurance value weights;
- cost/degradation tradeoff weights;
- family-specific escalation deadlines;
- domain-specific reopen windows.

Changing these values does not require a new ADR if the three-tier ledger,
source ceilings, LLM firewall, visibility, and authority boundary remain intact.

## Authority Boundary

The obligation graph may be authoritative for:

- obligation candidate visibility;
- canonical bundle deduplication;
- source-ceiling application;
- blocking-frontier selection;
- frontier/deferred/rejected audit inspection.

It may not be authoritative for:

- domain evidence;
- legal authority without Lex validation;
- claim support;
- method validity;
- participation legitimacy;
- projection authority;
- closeout evidence not backed by producer artifacts.

The graph can block or cap closeout only through promoted frontier items. Raw
candidate-ledger rows cannot be read as closeout blockers.

## Negative Laundering Test

Implementation must include semantic tests proving:

- no facets means no obligation graph;
- an LLM candidate burst remains candidate-only and cannot create raw hard
  gates;
- the bundle ledger has only one active bundle per C38 key;
- a legal requirement cannot become authority-level mandatory without
  competence/time/scope proof;
- deferred or rejected bundles keep reason, owner, time, and reopen trigger;
- inadmissible or authority-disallowed candidates remain visible but do not
  reach the frontier.

## Feature Flag / Advisory Posture

The structural compiler is enabled for local W6.C compilation tests. Numeric
frontier budgets and Net-MAV weights remain governed config. Downstream
closeout enforcement waits for Wave 7 producer pipeline integration and Wave 12
end-to-end revalidation.

## Revision Path

Any future change that lets raw candidate rows directly block closeout, lets
LLM candidates enter the frontier without producer re-emission, removes
deferred/rejected visibility, or changes the bundle key requires a superseding
ADR.

Budget tuning, family-specific owner routing, and deadline values can evolve
through governed config with replay evidence.

## Affected E Tasks

This ADR unblocks:

- E17 acquisition planning refactor, because RequirementSpec gaps must be
  bounded by compiled obligations;
- E19 complexity budget governance, because the blocking frontier is the
  denominator for obligation burden;
- W6.C obligation graph compiler implementation.

It constrains:

- W6.E/W6.F LLM formulator and firewall, because LLM candidates must retain raw
  source classification;
- W7 requirement compilers, because they cannot emit bindings that exceed the
  obligation frontier;
- W8 PDC graph compilation, because obligation refs must point to bundle or
  frontier ids rather than raw hidden candidates.

## Validation

Runtime behavior is validated by:

```bash
uv run pytest tests/unit/obligation_graph/test_compiler.py -q
```

ADR and registry discoverability are validated by:

```bash
uv run pytest tests/repo_quality/tools/test_policy_design_case_structural_adr_registry.py -q
```

## Capability Reality And Pattern Pass

Reuse classification: `build_new`, with rejected-reuse evidence above. The
new owner is narrow and internal: it does not duplicate acquisition planning,
soft-gate telemetry, scorecard closeout, Lex authority, or evidence
independence logic.

Relevant anti-patterns:

- P02 thin orchestration: the graph is an explicit intent-to-requirement bridge
  for later producer orchestration.
- P13 contract gravity well: raw candidates are cheap, but frontier blockers are
  bounded by complexity budget and Net-MAV posture.
- P14 raw count inflation: bundle/frontier counts become the honest denominator
  for evidence and obligation burden.
- P15 LLM speculation laundering: raw LLM candidates are candidate-only and
  cannot become hard gates.

Capability state after W6.C:

- typed contract/artifact: `ObligationGraph` and ledger DTOs;
- producer: `compile_obligation_graph(...)`;
- persisted artifact/event: `write_obligation_graph_artifact(...)` plus runtime
  event/evidence refs on the graph;
- orchestration bridge: W7 producer pipeline will consume frontier bundle ids;
- consumer: `obligation_graph_audit_surface(...)` and downstream W7/W8 readers;
- verification: `tests/unit/obligation_graph/test_compiler.py`;
- surface: machine/audit surface from `obligation_graph_audit_surface(...)`;
- semantic test: LLM burst, bundle dedup, legal-proof, budget deferral, and
  visibility tests.

Missing capability labels after W6.C: none for the local compiler, ledger,
artifact writer, audit surface, and semantic-test chain. Runtime closeout
enforcement is a distinct W7.F orchestration capability and cannot borrow this
ADR or W6.C tests as proof of staged-producer enforcement.

# ADR-0169: Bounded Liveness And Runtime Escalation

## Status

Accepted

## Date

2026-05-22

## Context

Universal Policy Design Case execution depends on multiple producer paths:
Scholar retrieval, Scientist orchestration, Fabric/Data Forge source work,
Lex legal authority, Foundry methods, closeout readers, replay, and review
telemetry. Several later tasks need liveness-sensitive statements such as
"eventually the producer emits evidence" or "eventually closeout can read the
required artifact."

Unbounded liveness is not a usable runtime guarantee for PolicyOS. A producer
wait that can hang indefinitely converts missing evidence into an invisible
stall, blocks finite replay, and lets downstream code confuse patience with
authority. For PolicyOS, every liveness expectation must be finite and
observable: `eventually X` means `X within governed deadline D, else escalate`.

The repository already has timeout and retry primitives in Scientist and
runtime dependency guards. The missing decision is the cross-capability
semantics: deadlines and retry ceilings are governed runtime configuration,
not hardcoded proof obligations or producer-local folklore.

This ADR ratifies W0.E FT-ADR-05 from the Universal Policy Design Case
implementation plan.

Source traceability is repo-owned:

- raw ledger:
  `docs/research/universal-policy-design/deep-research-reports-105-146-combined.md`
- normalized synthesis:
  `docs/backlog/universal-policy-design-case-research-results-consolidation.md`
- research plan:
  `docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_RESEARCH_PLAN.md`
- implementation plan:
  `docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_IMPLEMENTATION_PLAN.md`
- W0.G source ownership:
  `docs/reference/policy-design-case-source-ownership.md`

## Decision

1. PolicyOS does not accept unbounded temporal liveness claims for
   authority-bearing Policy Design Case workflows.
2. Any producer, bridge, closeout reader, replay step, or review/lifecycle task
   that says `eventually X` must compile to:
   `X within deadline D, else emit runtime escalation`.
3. Bounded liveness is checked as finite-state deadline consistency, not as an
   unbounded temporal proof.
4. Deadline values and retry ceilings are governed runtime config. They may be
   deployment-specific, but they must carry config identity, owner, version,
   feature flag, rollback path, and promotion evidence when promoted beyond
   defaults.
5. Producers may satisfy a liveness obligation only by emitting the expected
   artifact/event before the effective deadline.
6. Missing, late, cancelled, or over-budget producer waits become escalation
   states visible to consumers. They cannot silently remain pending.
7. Runtime escalation is not domain evidence. It may block, limit, downgrade,
   trigger acquisition/reissue/retry, or require review, but it cannot satisfy
   claim support, legal authority, data source-family, method validity,
   participation, or publication authority.
8. Retry policy is subordinate to the governed ceiling. A producer may request
   fewer retries than the ceiling, but cannot exceed the ceiling without a
   governed config change.
9. A liveness deadline may be stricter in a child producer than its parent
   workflow, but a child wait may not extend past the parent finite deadline
   unless the parent records an accepted runtime-budget/config change.
10. LLM-generated confidence that a producer will eventually finish is
    irrelevant to liveness satisfaction. Only runtime producer artifacts,
    runtime events, or explicit escalation states count.

## Structural Commitment

The implementation must model bounded liveness with at least these structural
fields:

- `schema_version`
- `config_id`
- `owner`
- `version`
- `configuration_authority`
- `feature_flag`
- `advisory_posture`
- `default_deadline_s`
- `default_retry_ceiling`
- `producer_deadline_overrides_s`
- `producer_retry_ceiling_overrides`
- `escalation`
- `rollback_path`
- `promotion_evidence_ref`
- `decision_ref`

The effective per-wait resolution must include:

- `producer_key`
- `deadline_s`
- `retry_ceiling`
- `escalation`
- `config_id`
- `config_version`
- `owner`
- `feature_flag`
- `notes`

The initial finite-state liveness vocabulary is:

| State | Meaning | Closeout effect |
| --- | --- | --- |
| `pending` | Producer obligation accepted but not started. | Not satisfiable. |
| `running` | Producer work has started within the configured bound. | Not satisfiable. |
| `satisfied` | Expected artifact/event arrived before deadline. | Consumer may evaluate artifact authority. |
| `escalated` | Deadline or retry ceiling was exceeded. | Consumer must block, downgrade, acquire, reissue, or review according to authority profile. |
| `failed` | Producer returned a terminal failure before deadline. | Consumer evaluates typed failure. |
| `cancelled` | Work was cancelled by runtime/operator before satisfaction. | Consumer treats as unsatisfied unless a replacement producer satisfies the obligation. |

The first implementation anchors are:

- `src/polisyos/core/contracts/bounded_liveness.py`
- `src/polisyos/scholar/search/jobs.py`
- `src/polisyos/scientist/orchestration/engine/retry.py`

Scholar deep-research jobs consume the governed deadline and escalate a
producer wait that exceeds it. Scientist retry wrappers consume the governed
retry ceiling when a liveness config is supplied.

## Tuned Parameter

These values are governed configuration, not structural truth:

- default producer deadline;
- producer-specific deadline overrides;
- default retry ceiling;
- producer-specific retry ceilings;
- escalation channel routing;
- feature-flag enablement and rollout cohort;
- advisory-versus-enforced posture for non-closeout telemetry;
- parent/child budget margins;
- retry backoff and jitter parameters;
- promotion evidence thresholds for tightening or relaxing deadlines.

Changing a tuned value does not require a new ADR if the structural rule remains
`X within deadline D, else escalate` and retry ceilings remain governed config.
Tuned config must keep owner, version, default source, feature/advisory posture,
rollback path, and promotion evidence when promoted.

## Authority Boundary

Bounded-liveness records and escalations are runtime governance evidence. They
are authoritative for:

- which producer wait was bounded;
- which config version supplied the deadline and retry ceiling;
- whether the expected artifact/event arrived before the deadline;
- whether the runtime escalated, failed, cancelled, retried, or clamped retry
  attempts;
- which consumer must handle the escalation.

They are not authoritative for:

- legal authority;
- data source-family satisfaction;
- source quality, lineage, or freshness;
- method validity;
- participation representativeness;
- claim support;
- evidence independence;
- public publishability.

An escalated liveness state may explain why closeout or publication is blocked.
It cannot replace the missing producer artifact.

## Negative Laundering Test

Future and current implementation must include tests with these minimum cases:

1. A Scholar deep-research producer that never returns must not make
   `DeepResearchJobManager.wait()` hang indefinitely. The wait must return an
   `escalated` status with a bounded-liveness error tied to the producer key.
2. Scientist retry execution with a requested retry count above the governed
   ceiling must clamp attempts to the ceiling.
3. A public/closeout reader must not treat `running`, `pending`, or
   `escalated` as evidence satisfaction.
4. A missing deadline config for a closeout-sensitive producer must fail closed
   or fall back to a governed default, never to an unbounded wait.
5. LLM output predicting eventual producer success cannot satisfy a liveness
   obligation.

## Feature Flag / Advisory Posture

Initial implementation uses:

- `universal_pdc_bounded_liveness`: governs bounded-liveness config resolution,
  producer wait deadlines, and retry ceilings.

Deadline enforcement is required for producer waits that can block closeout,
replay, or serious-run publication. Advisory mode may collect telemetry for
new non-blocking producers, but advisory mode may not create an unbounded wait
on a closeout-sensitive path.

## Revision Path

A new ADR is required to:

- allow an unbounded producer wait in a Policy Design Case authority path;
- let retry counts exceed governed ceilings without a config change;
- let `pending`, `running`, or `escalated` satisfy closeout or publication;
- remove owner/version/rollback requirements from liveness config;
- make LLM output satisfy a liveness obligation;
- change runtime escalation into domain evidence;
- weaken the requirement that liveness-sensitive paths expose an inspection
  surface or explicit out-of-scope rationale.

A config change is sufficient to tune deadlines, retry ceilings, rollout
cohorts, advisory posture, and escalation routing while preserving this
structure.

## Affected E Tasks

This ADR unblocks:

- E3 `can_i_closeout`, because closeout readers can treat missing producer
  completion as finite escalation rather than indefinite pending;
- E6 Concept Spine Kernel, because producer handshakes can require bounded
  reply windows;
- E7 NL/Replay Integration, because replay can reason over finite producer
  waits and escalation states;
- E19 Self-FMEA, because liveness failures become reviewable runtime-quality
  signals.

It also constrains:

- E18 Cost/SLA Gates, because wall-clock and retry budgets must align with
  bounded-liveness config;
- E15 Lifecycle/Reissue, because late producer completion must be handled as
  reissue or revision evidence rather than silent mutation;
- E22 Semantic Evaluation, because negative tests must include infinite-wait
  and LLM-eventuality laundering attempts.

## Validation

The ADR itself is validated by docs lifecycle gates:

```bash
uv run pytest tests/repo_quality/tools/test_docs_lifecycle.py tests/repo_quality/tools/test_docs_gate.py -q
```

Current implementation validation:

```bash
uv run pytest \
  tests/unit/core/contracts/test_bounded_liveness.py \
  tests/unit/scholar/search/test_service_jobs_tools.py::test_deep_research_job_manager_escalates_when_producer_wait_exceeds_deadline \
  tests/unit/scholar/search/test_service_jobs_tools.py::test_deep_research_job_manager_wait_returns_even_when_producer_ignores_cancel \
  tests/unit/scientist/orchestration/engine/test_retry.py::TestExecuteWithRetrySync::test_bounded_liveness_config_clamps_retry_ceiling \
  -q
```

Future implementation must add reader/closeout tests proving escalated
liveness cannot satisfy missing producer evidence.

## Capability Reality And Pattern Pass

Reuse classification: `extend_existing`. The existing Scientist retry wrapper,
Scholar job manager, runtime SLO, checkpoint/resume, and diagnostic-event
surfaces are the right owners. This ADR adds the common bounded-liveness
contract and narrows the first implementation to governed deadlines and retry
ceilings.

Relevant anti-patterns:

- P01 contract-only capability: a liveness config is not complete unless a
  producer wait consumes it and emits a visible escalation.
- P02 thin orchestration: producer waits, retry policy, closeout, replay, and
  self-FMEA must exchange bounded states rather than local timeout folklore.
- P05 authority dilution: an escalation can explain a blocker, but it cannot
  satisfy the missing producer artifact.
- P09 warning lifecycle gap: late, pending, failed, cancelled, and escalated
  waits need owned lifecycle states.
- P12 producer handshake gap: producer coordination needs finite reply windows
  before later waves rely on handoffs.
- P15 LLM speculation laundering: predicted eventual completion cannot satisfy
  a liveness obligation.

Existing anti-pattern found: timeout and retry primitives existed, but the
cross-capability meaning of `eventually` was not yet ratified. That created an
`implemented_but_not_orchestrated` risk where local timeouts could coexist with
unbounded PDC waits.

Target correct pattern: `eventually X` compiles to `X within governed deadline
D, else runtime escalation`, with retry ceilings clamped by governed config and
consumer readers treating escalation as unsatisfied evidence.

Missing capability labels after this ADR and W0.E bridge:
`consumer_missing`, `surface_missing`, and `semantic_test_missing` for full
closeout/API/dashboard consumption. The initial Scholar wait and Scientist
retry coverage close the immediate infinite-wait negative, but E3, E6, E7, and
E19 still need their own producer/consumer/surface proofs.

Acceptance signal: later work can cite ADR-0169, supply governed liveness
config, observe Scholar wait escalation instead of a hang, and prove retry
attempts cannot exceed the governed ceiling.

## Consequences

Positive:

- Producer waits become finite, inspectable, and replayable.
- Runtime can distinguish slow, failed, cancelled, and escalated producer
  states.
- Retry ceilings are tunable without hardcoding authority semantics.
- Closeout and replay can fail closed instead of waiting forever.
- E3, E6, E7, and E19 get a common liveness vocabulary.

Negative:

- Some long-running producers must surface partial progress, escalation, or
  reissue paths earlier.
- Config owners must maintain deadlines and retry ceilings as producers mature.
- Operators may initially see more escalations where waits were previously
  invisible.

## Concrete Impact

This ADR introduces or updates:

- bounded-liveness governed config contracts;
- Scholar deep-research job wait escalation;
- Scientist retry-ceiling clamping when governed liveness config is supplied;
- tests for governed config, non-hanging producer waits, and retry ceiling
  enforcement;
- ADR and implementation-plan links for W0.E.

Future work must wire bounded-liveness states into closeout readers, producer
handshakes, replay records, self-FMEA telemetry, API/dashboard/audit surfaces,
and runtime diagnostic events.

## Related Decisions

- Extends: ADR-0006 SLO Definitions for Scientist DAG.
- Extends: ADR-0011 Scientist DAG Checkpoint/Resume.
- Extends: ADR-0097 Runtime Rate Limiting and Idempotency.
- Extends: ADR-0148 Serious Run State Machine And Phase Barriers.
- Extends: ADR-0153 Diagnostic SLOs, Assurance Case, And Attestation.
- Extends: ADR-0154 Diagnostic Event Envelope And Runtime Log Contract.
- Extends: ADR-0156 Policy Design Case Runtime Quality Assurance Profile.
- Extends: ADR-0164 Run Cost, Proportionality, And Evidence Budget Governance.
- Extends: ADR-0165 Formal Policy Case And Substrate Invariant Specs.
- Related: ADR-0166 Evidence Acquisition Decision Boundaries.

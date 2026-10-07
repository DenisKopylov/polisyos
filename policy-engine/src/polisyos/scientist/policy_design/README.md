# Scientist Policy Design

This package contains Scientist-side policy design helpers for formulation,
critique, search, translation, and adversarial review. Runtime authority remains
outside this package: outputs here are candidate or analytic material until
they are bound by governed runtime-quality producers and closeout gates.

## LLM Worker Accounting

These worker module paths are internal under the public-surface manifest.
The local lazy re-exports do not register them as supported public entrypoints.

`ScenarioAdversaryWorker` and `PolicyTranslatorWorker` accept an optional
constructor `budget_middleware`. Budgeted use requires an explicitly
initialized `BudgetMiddleware` backed by a readable durable ledger. Its state
is the sole budget authority. The caller selects and initializes the ledger;
workers never choose a storage path or bootstrap a budget.

Raw `BudgetState` arguments, a raw state combined with middleware, and
ledgerless middleware raise `PolicyWorkerAccountingAdmissionError` before
gateway factory or provider work. This also applies to synchronous calls
inside an active event loop. Migrate `propose(..., budget_state=...)` and
`TranslatorInputBundle.budget_state` to constructor middleware, leaving the
raw field unset. Neither input retains the explicit unbudgeted contour,
which provides no durable accounting guarantee.

An obtained `LLMAccountingError` propagates unchanged before scientific
fallback. Unknown usage cannot become a successful fallback after a budgeted
physical call. Its exact pending obligation stays in the ledger; a newly
constructed worker or reopened middleware on intersecting keys refuses
another provider admission until trusted completion resolves it. Known
charges remain separate from unknown completion and protected audit status.
Ordinary parsing or scientific errors retain the configured fallback policy.

## Persisted Frontier Artifacts

`PolicyFrontierReport` and `RejectedAlternativesSummary` support schema v1 and
v3. Ordinary new producers write v3; schema v2 was unissued and is rejected.
Bounded compatibility tests round-trip synthetic v1 golden payloads
byte-exactly through the version-specific projection. An authentic committed
historical v1 fixture corpus is `not_established`, and complete historical
1.0 snapshot replay remains UNRUN. The v3 report DTO validator compares the
supplied source set with projected eligible identities, checks for duplicates
within the source and unknown sets and overlap between those sets, and
requires the projection assessment status to be `denominator_limited` when
the supplied source set differs from projected eligible identities or the
supplied unknown set is nonempty. It does not authenticate or independently
reconcile unknown identities. The ordinary
`PolicyArtifactBuilder._build_frontier_report` path does not receive an
independent source or unknown-eligibility input: it copies the projection's
eligible identities into the source field and leaves
the unknown set empty. That validation is self-derived on the ordinary path;
it cannot detect candidates omitted before registry projection and does not
establish a complete upstream universe. A missing registry remains
`basis_limited` and unranked. The summary has its own v3 `view_projection`,
not the report-level source/unknown fields. These artifacts remain candidate
material and do not confer runtime authority. See the
[artifact migration and rollout guidance](../../../../ops/migrations/ir/README.md#scientist-frontier-artifact-v3).

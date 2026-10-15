# Scientist Claims

Related references: [Scientist](index.md), [Best-in-class readiness](best-in-class-readiness.md), [Capability inventory](scientist-capability-inventory.md), [Governance accountability](governance-accountability.md), [Causal validity](causal-validity.md).

Owner: `@scientist-owners`
Backup owner: `@platform-owners`
Source of truth: `src/polisyos/scientist/evidence/claims/models.py`, `src/polisyos/scientist/evidence/claims/readiness.py`, `src/polisyos/scientist/evidence/claims/ledger.py`, `src/polisyos/scientist/evidence/claims/projections.py`, `src/polisyos/scientist/evidence/claims/validators.py`, `src/polisyos/scientist/evidence/claims/head_index.py`, `src/polisyos/scientist/orchestration/workflows/builder.py`, `src/polisyos/scientist/evidence/README.md`, `tests/unit/scientist/evidence/claims/test_readiness.py`, `tests/unit/scientist/evidence/claims/test_lifecycle.py`, `tests/unit/scientist/evidence/claims/test_head_index.py`, and `tools/ci/check_scientist_best_in_class_phase1_1.py`.
Source pin: `codex/docs-refresh-e02-20261014` at `bafca83bff9ff49eef1466bc491a8420b5cd1dbb`.
Evidence level: implementation and test sources inspected at this pin; tests not executed for this docs-only update.

This page is the Phase 1.1 reference for the Scientist claim/evidence/readiness
spine. The plan rule is:

> No naked claims.

Decision-bearing statements are intended to be projected into typed runtime
objects with support status, evidence refs, counterevidence refs,
provenance/readiness links, source attribution and publishability. This is a
design rule, not a claim that the current runtime blocks every uncovered
statement: the additive claim-spine producer is enabled by default, while
missing-`claims_ref` enforcement is opt-in and defaults off (see
[Feature Flags](#feature-flags)).

## Runtime Contracts

The claim spine extends the shared readiness ladder owned by
`polisyos.scientist.evidence.decision_readiness.DecisionReadiness`; it does not replace or
rename readiness levels. The former
`polisyos.scientist.methods.search.readiness.DecisionReadiness` path remains a compatibility
alias to the same enum object, and the enum retains that legacy module identity for new and
legacy pickle payloads.

| Contract | Source | Role |
| --- | --- | --- |
| `ClaimRecord` | `src/polisyos/scientist/evidence/claims/models.py` | One typed claim with `claim_type`, support status, evidence, counterevidence, readiness and publishability. |
| `ClaimLedger` | `src/polisyos/scientist/evidence/claims/models.py` | CAS sidecar for all projected claims attached to a run or decision artifact. |
| Claim readiness rules | `src/polisyos/scientist/evidence/claims/readiness.py` | Converts support/counterevidence/readiness into `draft`, `internal_only`, `review_required`, `publishable` or `blocked`. |
| Ledger persistence | `src/polisyos/scientist/evidence/claims/ledger.py` | Persists and loads `scientist.claim_ledger` artifacts through CAS. |
| Projection helpers | `src/polisyos/scientist/evidence/claims/projections.py` | Projects existing decision packet, policy bundle, governance, causal validity and frontier runtime outputs into claims. |
| Naked-claim validators | `src/polisyos/scientist/evidence/claims/validators.py` | Detects decision-bearing payloads or states without `claims_ref`; fail-closed is flag-gated. |

## Decision-bearing surface inventory

| Surface | First projection owner | Claim families | Current behavior |
| --- | --- | --- | --- |
| Decision packet | `build_decision_packet.py` | implementation, factual, causal, legal, distributional, welfare, forecast | Persists a `ClaimLedger`, writes top-level `claims_ref`, mirrors it into packet `artifacts.claims_ref`, and stores `claim_readiness_summary`. |
| Policy output bundle | `PolicyArtifactBuilder` and `build_policy_output_bundle.py` | implementation, source quality | Persists a bundle-level ledger and writes `PolicyArtifactBundle.claims_ref` plus `artifacts_index.claims_ref`. |
| Governance report | `run_governance.py`, `governance/report.py` | implementation, legal | Generates a governance-report ledger when claim spine is enabled and links it through `GovernanceReportLinks.claims_ref`. |
| Governance accountability | `governance/accountability.py` | source quality, governance implementation | Carries optional `claims_ref` in accountability input and metadata. |
| Causal effect/validity | `run_causal_evaluation.py`, `causal/validity.py` | causal, source quality | Persists causal claim ledgers and embeds `claims_ref` in causal validity bundles. |
| Frontier runtime | `orchestration/engine/frontier_runtime.py`, `evidence/claims/projections.py` | source quality | Exposes a projection owner and can project capability status claims without enabling frontier methods by default. |

## Publishability Rules

| Situation | Result |
| --- | --- |
| Supported claim with evidence at `analyst_advisory` or above | `publishable` unless counterevidence exists. |
| Legal, causal, forecast, distributional or welfare claim without evidence | `review_required`. |
| Claim with unresolved counterevidence | `review_required`. |
| Refuted claim or claim with blocking reasons | `blocked`. |
| Supported research-only claim | `internal_only`. |

Legacy artifacts remain readable. If a packet or artifact predates Phase 1.1,
renderers should show `claim_ledger_status = "legacy_missing"` rather than
failing to load the old artifact.

## Feature Flags

| Flag | Default | Meaning |
| --- | --- | --- |
| `scientist.best_in_class.wave1.phase1_1.claim_spine` | on | Produce additive claim ledgers and `claims_ref` sidecars. |
| `scientist.best_in_class.wave1.phase1_1.fail_on_naked_claims` | off | Fail closed for selected high-risk workflows when decision-bearing fields exist without `claims_ref`. |

The fail-closed workflow set is `scientist_policy_design`,
`scientist_policy_verified`, and `scientist_causal_full`.

When the naked-claim validators inspect a decision-bearing payload or state
without `claims_ref`, the default-off enforcement flag makes the result
`warning` with `passed=true`; that validator result does not block the
workflow. The flag changes the result to `blocked` only for the selected
workflows above. Therefore “No naked claims” states the target invariant; it
is not currently an unconditional runtime closeout gate.

## Current-Head Authority

Claim projection and Claim-owner currentness are separate handshakes. The
workflow builder installs `build_default_claim_ledger_owner()`, which returns
`UnappointedClaimLedgerOwner` in the production composition. That owner can
persist and summarize a candidate ledger, but initial-root prepare/finalize and
current-head resolution return typed `not_established` non-receipts, including
`claim_root_issuance_not_established` and `claim_head_absent`. The production
appointment slot remains empty (`absent/unallocated`); current Claim-head
authority is `not_established`. A CAS blob, `claims_ref`, readiness summary,
or publishability result therefore does not establish an owner-approved
current Claim. See `src/polisyos/scientist/orchestration/workflows/builder.py`,
`src/polisyos/scientist/evidence/claims/head_index.py`, and
`src/polisyos/scientist/evidence/README.md` for the default wiring and
appointment boundary.

## Validation

```bash
uv run pytest tests/unit/scientist/evidence/claims -q
uv run python tools/ci/check_scientist_best_in_class_phase1_1.py --repo-root . --output-format json --require-passing
uv run pytest tests/repo_quality/tools/test_scientist_best_in_class_phase1_1.py -q
```

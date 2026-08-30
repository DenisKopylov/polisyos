---
task_id: INT-R3
stage: 3
artifact_role: repository_baseline_amendment
responds_to:
  - ../../audits/int-r3/int-r3-anchor-and-citation-verification.md
  - ../../audits/int-r3/int-r3-claim-evidence-ledger.md
status: amendment_complete
pin: dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f
---

# INT-R3 repository-baseline amendment

This file supersedes only the baseline facts named below. Every other stage-1 coordinate retains its
original evidence class.

## Corrected positive anchors

### Trust posture route

Audited coordinate:

`apps/runtime-dashboard/src/features/trust/routes/TrustPosturePage.tsx`

At the pin, the complete file defines and exports `TrustPosturePage`. It does **not** define
`TrustPostureContent`; that stage-1 symbol is withdrawn.

The verified route behavior remains: it loads the trust-posture packet, renders loading,
`unavailable` and `available` arms, switches PUBLIC/REVIEWER/EXPERT audiences, renders
`ClaimPostureRegister`, methodology and accessibility evidence, and offers the exact MACHINE bytes.

### `TimeSemanticsLabel`

Audited coordinate:

`apps/runtime-dashboard/src/shared/ui/temporal/TimeSemanticsLabel.tsx`

At the package pin and on the amendment branch, the component accepts:

```text
cacheAgeLabel
children
className
freshness
payloadAsOf
txAt
validAt
```

It renders:

```text
Policy valid at
Knowledge tx at
Payload as of
Source as of
Observed at
Source state
Cache age
```

The stage-1 description using `createdAt`, `asOf`, `updatedAt`, `validFrom`, `validUntil` and
`generic` is withdrawn. Those names describe neither this component’s public props nor its rendered
clock vocabulary at the pin. A later branch may add another temporal prop; it does not retroactively
change this pinned baseline.

## Current versus planned targets

The stage-1 orientation conflated “in the repository” with “on current glass.” The amended census is:

| Target | State at pin | Coordinate class |
| --- | --- | --- |
| typed appointment/authority refusal | current rendered surface | Trust Posture and Case Workspace |
| weakest link and acquisition route | current rendered surface | Cycle Board |
| human acquire/escalate/abstain/decision controls | current rendered surface | Case Workspace + Human Decision Gate |
| present time/currentness labels | current primitive; full epoch behavior not complete | `TimeSemanticsLabel` and existing freshness projections |
| outer-set, explicit `unknown`, strict `incomparable` grammar | planned/in-flight target | DS16 plan |
| conditional δ chip on every δ figure | planned/in-flight target | DS17 master-plan scope |
| full epoch staleness chrome and six perturbation classes | planned/in-flight target | DS18 master-plan scope |
| quarantine ledger, re-entry and admission passport | planned/in-flight target | DS15/GY-N13b dependency |

Therefore, the repository contains current targets for part of the benchmark and plans for the
remainder. It does not currently render all eight constructs as one complete operator experience.

## Search actually executed by stage 1

Stage 1 followed named terms and task coordinates through selected paths. It did not execute a
complete tracked-tree census.

### Terms followed

```text
Authority not appointed
TrustPosturePage
ClaimPostureRegister
TimeSemanticsLabel
CycleBoard
CaseWorkspacePage
HumanDecisionGate
DS11-CURRENT-PAGE-A11Y
DS11-EXTERNAL-A11Y-COUNTERSIGN
DS11-GENERAL-COPY-SEMANTICS
unknown
incomparable
delta / δ
quarantine
```

### Path families inspected

```text
policy-engine/apps/runtime-dashboard/src/features/trust/**
policy-engine/apps/runtime-dashboard/src/features/runs/**
policy-engine/apps/runtime-dashboard/src/shared/ui/temporal/**
policy-engine/apps/runtime-dashboard/public/atlas/**
policy-engine/docs/plans/active/atlas-slices/**
policy-engine/docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md
policy-engine/docs/plans/active/DEBT-REGISTER.md
the governing research, identity, failure-pattern and W4-K05 documents named in the commission
```

### Denominator and controls

```yaml
tracked_path_denominator: not_computed
file_type_denominator: not_computed
positive_control: named source coordinates above
negative_control: not_executed_for_repository_wide_zero
executing_party: stage_1_researcher
predicate_provenance: sampled_named_path_search
```

## Corrected negative claims

| Stage-1 zero | Amended statement | Evidence standing |
| --- | --- | --- |
| no admitted human-comprehension evidence exists anywhere in the repository | no such evidence was found in the named paths and terms above; a complete repository-wide zero was not constructed | `not_established` |
| no canonical behavioral event/result contract exists | no canonical contract was found in the sampled owner and surface paths; complete-tree absence was not constructed | `not_established` |
| no benchmark owner exists | DS6 carried an allocation record, but the principal has adjudicated it stale because DS6 closed at `176276ef0` without the instrument; the instrument is currently unowned | `reconciled_stale_allocation` |

The narrower package fact remains established: the eight-file stage-1 package contains no human study
result.

## Historic page-a11y count

`20/24` remains recorded only as an institutionally supplied historical figure from committed DS11
receipts. Stage 1 did not recompute it and this amendment does not use it to settle any zero or human
outcome.

The three DS11 debts retain their own closure conditions. INT-R3 can supply behavioral comprehension
evidence; it cannot by itself close page-level accessibility conformance, appoint an external
accessibility countersigner or widen the structural copy checker.

## Owner and capability consequence

The stale DS6 allocation is recorded, not silently treated as a live owner:

```yaml
instrument_allocation:
  recorded_owner: DS6
  state: stale
  closure_commit: 176276ef0
  instrument_landed_before_closure: false
current_owner: unowned
allocation_route: human_principal
capability_standing: absent/unallocated
```

No owner is appointed in this stage. The principal receives the routing item.

## Baseline result after amendment

Positive coordinates are corrected. Repository-wide absence is no longer asserted from a sample.
Current and planned surfaces are separated. The baseline remains suitable for selecting benchmark
targets, but not for claiming human comprehension.

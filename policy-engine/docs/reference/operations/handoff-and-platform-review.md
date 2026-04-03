# Handoff and Platform Review

Related reference: [Operations Reference](index.md). Related runbooks:
[Runbooks](../../runbooks/index.md).

> Ownership in Phase 6 must survive vacations, refactors, and team changes.
> This page defines the minimum handoff format, retirement checklist, quarterly
> review ritual, and platform scorecard.

## Handoff Template

Every non-trivial subsystem or workflow change should leave a handoff note with
the following sections:

1. **What changed**
   concise scope, files, user-visible impact, changed commands.
2. **Why now**
   why this change was worth the migration cost at this time.
3. **Owner path**
   primary owner, fallback owner, escalation path.
4. **Operational surface**
   dashboards, alerts, logs, traces, runbooks, restore requirements.
5. **Rollback / exit path**
   how to stop or reverse the change safely.
6. **Known risks**
   what still worries us, what is not covered yet.
7. **Validation**
   which commands, checks, and environments were used.
8. **Follow-up**
   explicit open items with owners and dates.

## “Why Now” Guidance

Large refactors and infrastructure migrations must answer all four questions:

- what problem is bad enough today that this change is justified;
- why waiting one more quarter would be worse;
- what alternatives were rejected and why;
- how success and failure will be recognized operationally.

If the author cannot answer these questions, the change is not ready for
rollout.

## Retirement Checklist

When deleting or superseding a workflow, tool, or surface:

- identify replacement owner and replacement path;
- update docs, nav, and runbooks in the same change set;
- remove or reroute alerts and dashboards that pointed at the retired surface;
- classify retained artifacts: discard, migrate, or cold-archive;
- add deprecation note if users may still search for the old path;
- confirm no synthetic checks or CI jobs still rely on the retired behavior.

## Quarterly Platform Review Ritual

Cadence: once per quarter, with `@platform-owners` coordinating and subsystem
owners attending for their area.

### Agenda

1. Review error-budget spend and major incidents.
2. Review delivery metrics and instability indicators.
3. Review stale dashboards, noisy alerts, and silent-failure gaps.
4. Review retention footprint and restore drill outcomes.
5. Review onboarding friction and handoff gaps discovered this quarter.
6. Agree on 1-3 platform improvements for the next quarter.

### Required Inputs

- last quarter’s incident list and postmortems;
- current scorecard values;
- restore drill results;
- notable docs/onboarding updates;
- any ownerless or ambiguous operational surfaces.

## Platform Scorecard

The platform scorecard must include throughput and instability, not just static
policy compliance.

| Indicator | Why it matters | Owner |
|---|---|---|
| Deployment frequency | detects whether platform friction is slowing delivery | `@platform-owners` |
| Lead time for change | shows how quickly a merged fix reaches usable state | `@platform-owners` |
| Change failure rate | ties delivery speed back to reliability cost | `@platform-owners` |
| Mean time to restore | core operational responsiveness signal | `@platform-owners` |
| Error budget burn by surface | reliability state in shared language | service owner |
| CI flake rate / unstable gate count | delivery drag caused by tooling instability | `@platform-owners` |
| Docs publish freshness | detects silent docs drift | `@docs-owners` |
| Contract drift incidents | detects source-of-truth erosion | `@platform-owners` |
| Replay/restore drill success rate | validates recovery posture | `@platform-owners` |
| Benchmark review freshness | ensures performance/quality signal still trusted | `@foundry-owners` |

## Review Outputs

Every quarterly review must leave:

- updated scorecard snapshot;
- list of retired or newly owned surfaces;
- runbook/doc updates required;
- explicit owner and target date for each approved platform improvement.

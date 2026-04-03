# Review Migrations and Rollouts

> Use this guide when a change crosses schema, SQL, OpenAPI, generated-client, or infra boundaries.

## 1. Migration Classes

| Class | What it means | Expected reviewer stance | Default rollback stance |
|---|---|---|---|
| Additive safe | Backward-compatible change with no required consumer action | Normal review, standard PR gates | revert or ship follow-up if needed |
| Additive with consumer sync | Additive change, but generated clients or downstream consumers must update in lockstep | Confirm sync plan and owner | revert before consumer cutover, or stage follow-up immediately |
| Destructive / freeze-window required | Removes or invalidates a previously supported path | Require explicit freeze window and migration owner | mitigation usually means restore compatibility or ship a new migration |
| Forward-only operational migration | Data/backfill/ops move that should not be reversed mechanically | Require runbook and mitigation plan | mitigate with a new forward migration, not a blind rollback |

## 2. The Reviewer Checklist

Cross-boundary rollout PRs should make it obvious which surfaces changed.

The PR template carries a required `Migration owner` field plus the following checklist:

- schema snapshots;
- runtime OpenAPI export;
- generated clients;
- SQL / RLS migrations;
- Helm changes;
- Terraform changes;
- feature flags or staged exposure plan;
- canary / shadow / phased rollout stance for high-risk changes;
- docs and runbooks.

Reviewer rule:

- If none of those boxes apply, the PR is probably code-only.
- If any of them apply, the PR must explain rollout order, validation, and mitigation.

## 3. Rollout Order Expectations

### Additive safe

1. Land schema / API additions.
2. Regenerate affected clients if the repo owns them.
3. Update docs and examples.
4. Merge after normal Fast PR + Standard PR gates.

### Additive with consumer sync

1. Land additive producer change first.
2. Regenerate clients and confirm consumer owner.
3. Document cutover order in the PR.
4. Keep the old path alive until all listed consumers are updated.

### Destructive / freeze-window required

1. Declare the freeze window in the PR summary.
2. Name the migration owner.
3. Include a precise compatibility impact statement.
4. Include a concrete rollback or mitigation plan.
5. Do not merge until consumers, docs, and runbooks are aligned.

### Forward-only operational migrations

1. Explain why reversal is unsafe or misleading.
2. Include prechecks, observability, and abort conditions.
3. Define the mitigation path as another forward action.
4. Record canary, shadow, or phased rollout stance if runtime risk exists.

## 4. Rollback / Mitigation Guidance

| Migration class | Preferred response if rollout goes wrong |
|---|---|
| Additive safe | revert or disable the new call path |
| Additive with consumer sync | pause the consumer cutover, keep additive compatibility surface live |
| Destructive / freeze-window required | restore compatibility or ship a new corrective release; do not mutate already published artifacts |
| Forward-only operational migration | follow the documented mitigation path and capture lessons in the runbook |

## 5. What “Migration Owner” Means

The migration owner is the person responsible for the coordinated rollout, not only for the code diff.

That owner is accountable for:

- rollout order across product and infra boundaries;
- canary or phased validation where relevant;
- communication to downstream consumers;
- deciding whether to abort, pause, or promote.

If a reviewer cannot identify that owner, the PR is missing rollout governance metadata.

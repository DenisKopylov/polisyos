# OPS-11: родитель и соединение рабочих результатов

Canonical title: Trust succession, currentness duty, and custody cutoff. R26 форма: `split`. [Task manifest](../../../tasks.json) · [Preferred solution](../../../solutions/10-operations.md#OPS-11).

Эта страница — родительская accountability, не дополнительная дробная карточка и не второй implementation owner. Полный source scope сохраняется.

| Карточка | Группа | Observable результат |
|---|---|
| [OPS-11.trust-root](../cards/OPS-11/trust-root.md) | [G07](../groups/G07.md) | A current PolicyOS technical trust generation and successor are independently authorized, strictly monotonic and historically verifiable; a compromised root cannot appoint its own replacement. |
| [OPS-11.currentness-duty](../cards/OPS-11/currentness-duty.md) | [G07](../groups/G07.md) | Each currentness-bearing claim has a real accepted owner/deputy, due/source/time/cadence basis, bounded coverage and reaction/transfer/cutoff; a missed duty limits only the enrolled claim. |
| [OPS-11.archive-transfer](../cards/OPS-11/archive-transfer.md) | [G07](../groups/G07.md) | A successor’s preservation duty is counted only after actual acceptance, and any renewal claim is based on retrieved/verified retained bytes under a selected proven protocol. |

## Реальный join

Compose three independent outputs: independently authorized technical root generation, accepted bounded currentness duty/cutoff, and evidence-backed archive-duty transfer/renewal. Existing fresh trust/source-use reader consumes the first; LIF-04 persists the second and LIF-02 consumes affected claim status; OPS-05/LIF-05 archive reader consumes the third. External institution remains authority.

**Outputs:** [OPS-11.trust-root](../cards/OPS-11/trust-root.md), [OPS-11.currentness-duty](../cards/OPS-11/currentness-duty.md), [OPS-11.archive-transfer](../cards/OPS-11/archive-transfer.md).

**Fresh consumer / ответственный контур:** Existing PolicyOS trust verifier/source-use reader, LIF-04 durable duty owner, LIF-02 currentness projection and OPS-05/LIF-05 archive retrieval/custody consumer.

**Review размера:** Three distinct evidence bases stay separated. Root-currentness is not institutional delegation, claim freshness is not OPS-11 status, archive data is not acceptance/renewal. Trust and record paths share the parent canonical lease until exact post-E02 disjointness is proven.

Ниже сохранённые parent-wide clauses, а не разрешение спрятать реализацию. Они должны быть доказаны outputs названных карточек, собственным coordination decision или настоящим external input. Shared constraint сам не является выполненной работой.

- **join** — Aggregate acceptance, coordination, or shared constraint across trust-root, currentness-duty, archive-transfer; selectors task.deliverable, task.positive, task.adversarial, task.removal, task.surface, task.rollback, task.migration, task.acceptance_steps[0], task.acceptance_steps[1], task.acceptance_steps[2], task.acceptance_steps[3], task.acceptance_steps[4], task.mandatory_companions[0], task.mandatory_companions[1], task.mandatory_companions[2], task.mandatory_companions[3], task.mandatory_companions[4], task.rollback_precedence, task.r19_extension.question_ids[6], task.r19_extension.writer_rule, task.r19_extension.acceptance_ref, solution.implementation_steps[3], solution.migration_and_rollback, solution.composition_contracts[0], solution.input_resolution_rule are reconciled by parent_join against the named card outputs and existing consumer, not implemented as peer-owner work.
  `task.deliverable`; `task.positive`; `task.adversarial`; `task.removal`; `task.surface`; `task.rollback`; `task.migration`; `task.acceptance_steps[0]`; `task.acceptance_steps[1]`; `task.acceptance_steps[2]`; `task.acceptance_steps[3]`; `task.acceptance_steps[4]`; `task.mandatory_companions[0]`; `task.mandatory_companions[1]`; `task.mandatory_companions[2]`; `task.mandatory_companions[3]`; `task.mandatory_companions[4]`; `task.rollback_precedence`; `task.r19_extension.question_ids[6]`; `task.r19_extension.writer_rule`; `task.r19_extension.acceptance_ref`; `solution.implementation_steps[3]`; `solution.migration_and_rollback`; `solution.composition_contracts[0]`; `solution.input_resolution_rule`

## Owners и stages

**Canonical lease namespace:** `write:exact-path/{canonical_repo_path}`. Это namespace исходного parent, не доказательство disjoint write sets карточек. P0 binds exact paths/generated owner и пофазовые ресурсы.

Все inherited fields перечислены в [coverage.json](../coverage.json); `scope`, source IDs/debt refs, stage/phase, acceptance/conditional/execution и allocation rules сохраняют смысл canonical manifest. Producer-card links — выбранный плановый маршрут; actual source-qualified input всё равно обязателен на своей стадии.

До фактической приёмки E02 — только документация. Общий [порядок R26](../README.md) и [stage contract](../../05-stage-and-release-contracts.md).

# LIF-01: родитель и соединение рабочих результатов

Canonical title: Bind relation evidence to a specific admissible use. R26 форма: `split`. [Task manifest](../../../tasks.json) · [Preferred solution](../../../solutions/02-custody.md#LIF-01).

Эта страница — родительская accountability, не дополнительная дробная карточка и не второй implementation owner. Полный source scope сохраняется.

| Карточка | Группа | Observable результат |
|---|---|
| [LIF-01.relation_use](../cards/LIF-01/relation_use.md) | [G06](../groups/G06.md) | Exact content/verifier-bound relation supports only its claim, purpose, audience and time. |
| [LIF-01.cache_current_use](../cards/LIF-01/cache_current_use.md) | [G07](../groups/G07.md) | Cache reuse requires qualified basis and fresh use; rights/rule/dependency/purpose/audience changes cannot reuse stale green. |
| [LIF-01.trial_realization](../cards/LIF-01/trial_realization.md) | [G05](../groups/G05.md) | One method-qualified realization resolves per native intent; a fresh replicate is distinct with honest dependence. |

## Реальный join

Join outputs relation_use (persisted relation/assessment/use), cache_current_use (fresh basis/use decision), and trial_realization (accepted realization/dependence) through their actual readers. CAP02 receipt and LIF07 closure are selected inputs; LIF05 rights and DES03/GYD30/LIF04 trial identities retain their owners.

**Outputs:** [LIF-01.relation_use](../cards/LIF-01/relation_use.md), [LIF-01.cache_current_use](../cards/LIF-01/cache_current_use.md), [LIF-01.trial_realization](../cards/LIF-01/trial_realization.md).

**Fresh consumer / ответственный контур:** Fresh Claim/evaluation reader; selected CAP03 library reader only for the cache-eligible guarantee; DES03/GYD30 trial consumer on selected stochastic paths.

**Review размера:** 3 cards refine R25 cache/trial. Pattern pass P05/P07/P08/P10/P14/P15/P29/P32/P35/P37/P38; E02 paths unresolved; acceptance requires persisted relation, fresh reader and selected cache/trial probes.

Ниже сохранённые parent-wide clauses, а не разрешение спрятать реализацию. Они должны быть доказаны outputs названных карточек, собственным coordination decision или настоящим external input. Shared constraint сам не является выполненной работой.

- **binding** — Shared E02 rebind/oracle/implementation/consumer acceptance.
  `task.acceptance_steps[0]`; `task.acceptance_steps[1]`; `task.acceptance_steps[2]`; `task.acceptance_steps[3]`
- **binding** — Review, companions, journal and rights-aware rollback precedence.
  `task.acceptance_steps[8]`; `task.mandatory_companions[0]`; `task.mandatory_companions[1]`; `task.mandatory_companions[2]`; `task.mandatory_companions[3]`; `task.mandatory_companions[4]`; `task.rollback_precedence`
- **binding** — R17 delivery/quality/status/navigation.
  `task.r17_extension.delivery_slices[0]`; `task.r17_extension.delivery_slices[1]`; `task.r17_extension.quality_cases[0]`; `task.r17_extension.quality_cases[1]`; `task.r17_extension.quality_cases[2]`; `task.r17_extension.product_verification`; `task.r19_extension.status`; `task.r19_extension.product_verification`; `task.r19_extension.composition_contract_ref`
- **binding** — Native writer rule and acceptance ref.
  `task.r19_extension.writer_rule`; `task.r19_extension.acceptance_ref`
- **join** — Preferred solution spans all three card outputs.
  `solution.preferred_solution`
- **binding** — Parent input classification; missing native work assigned.
  `solution.input_resolution_rule`

## Owners и stages

**Canonical lease namespace:** `write:semantic-use/{owner}`. Это namespace исходного parent, не доказательство disjoint write sets карточек. P0 binds exact paths/generated owner и пофазовые ресурсы.

Все inherited fields перечислены в [coverage.json](../coverage.json); `scope`, source IDs/debt refs, stage/phase, acceptance/conditional/execution и allocation rules сохраняют смысл canonical manifest. Producer-card links — выбранный плановый маршрут; actual source-qualified input всё равно обязателен на своей стадии.

До фактической приёмки E02 — только документация. Общий [порядок R26](../README.md) и [stage contract](../../05-stage-and-release-contracts.md).

# CNT-02: родитель и соединение рабочих результатов

Canonical title: Onboard source-library metadata and supported classes (data/config only). R26 форма: `retain`. [Task manifest](../../../tasks.json) · [Preferred solution](../../../solutions/09-foundations.md#CNT-02).

Эта страница — родительская accountability, не дополнительная дробная карточка и не второй implementation owner. Полный source scope сохраняется.

| Карточка | Группа | Observable результат |
|---|---|
| [CNT-02.source-profile](../cards/CNT-02/source-profile.md) | [G01](../groups/G01.md) | A supported class resolves resource/version/representation/access metadata and a native owner route; a metadata row is discovery, not content-bound admission. |

## Реальный join

Join the source-profile output to the existing catalog resolver and selected class's native content/rights/applicability/currentness validator. The fresh consumer is the existing class-specific resolver/validator identified at E02 rebind; without it the row remains discovery-only.

**Outputs:** [CNT-02.source-profile](../cards/CNT-02/source-profile.md).

**Fresh consumer / ответственный контур:** Existing catalog resolver followed by the selected class's native validator/use-admission reader, rebound after E02.

**Review размера:** Retained as one descriptive metadata/profile result. A publisher or rights-holder supplies content terms; the catalog mechanism owner does not.

Ниже сохранённые parent-wide clauses, а не разрешение спрятать реализацию. Они должны быть доказаны outputs названных карточек, собственным coordination decision или настоящим external input. Shared constraint сам не является выполненной работой.

- **binding** — Shared accepted-source rebind, oracle, native owner use, fresh-consumer check and readback acceptance steps remain in the canonical parent contract.
  `task.acceptance_steps[0]`; `task.acceptance_steps[1]`; `task.acceptance_steps[2]`; `task.acceptance_steps[3]`; `task.acceptance_steps[4]`
- **binding** — Schema/generated consumer/migration/journal/review companions attach only if this profile changes them; parent contract retains the exact obligation.
  `task.mandatory_companions[0]`; `task.mandatory_companions[1]`; `task.mandatory_companions[2]`; `task.mandatory_companions[3]`; `task.mandatory_companions[4]`

## Owners и stages

**Canonical lease namespace:** `write:exact-path/{canonical_repo_path}`. Это namespace исходного parent, не доказательство disjoint write sets карточек. P0 binds exact paths/generated owner и пофазовые ресурсы.

Все inherited fields перечислены в [coverage.json](../coverage.json); `scope`, source IDs/debt refs, stage/phase, acceptance/conditional/execution и allocation rules сохраняют смысл canonical manifest. Producer-card links — выбранный плановый маршрут; actual source-qualified input всё равно обязателен на своей стадии.

До фактической приёмки E02 — только документация. Общий [порядок R26](../README.md) и [stage contract](../../05-stage-and-release-contracts.md).

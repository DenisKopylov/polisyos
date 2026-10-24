# CNT-01.facet-map — Зафиксировать грамматику и маршруты семейств

Группа: [G02 — Смысл оснований: право, метрики, ценности и участники](../../groups/G02.md). Родитель: [CNT-01](../../parents/CNT-01.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Версия общей грамматики, маршрутов и пределов покрывает все 26 текущих семейств и указывает существующего native owner/validator; метаданные не превращаются в content/authority evidence.

**Предпочтительное решение.** Сверить семейства с принятой грамматикой и расширить существующий registry/catalog owner-local данными. Класс без валидируемого owner/validator остаётся unsupported; не создавать общий foundation switch.

**Граница владельца.** Пишет только обнаруженный native catalog/registry owner под своей canonical lease family; CAP/claim/legal владельцы остаются consumers. После E02 разрешить exact пути и пересечения leases; до этого считать возможное пересечение общим.

**Входы.** Текущая грамматика и source registry; ответы существующих class owners. Справочные карточки и DCAT mappings не назначают production suppliers.

**Выход и consumer.** Версионированная карта 26 семейств и class→existing owner/validator, включая явные unknown/unsupported ветви; её читатель — case profile и source catalog resolver.

**Что можно готовить независимо.** Read-only census/crosswalk можно подготовить заранее; писать и заявлять поддержанный class можно только после accepted E02 rebind, exact stage/interface pins, lease и resource permit.

**Где результат соединяется с другими.** CNT-01 commissioned-case потребляет карту выбранных facets; fresh reader — существующий catalog resolver с native validator. Сама карта не admits content, rights или currentness.

**Positive.** Все 26 семейств имеют owner route/validator или явный unsupported; выбранный класс разрешается до точной версии/representation.

**Distinguishing negative.** Пропущенный класс, похожий label или ссылка без validator считается покрытием.

**Matched removal.** Удаление mapping/validator при сохранённых карточках не даёт поддержанному классу пройти fresh consumer.

**Граница контекста.** Общесемейная grammar/route — отдельный output; не означает сбор всех 197 cards или live acquisition всех семейств.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Inherited accepted E02 readiness and scoped source rebind apply to each listed card; no extra start gate is added, and canonical parent stage/dispatch remains authoritative.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `CNT-01`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — These fragments census existing owners, define new-class adapter boundary and require the all-26-family grammar/routes/limits map; no source content or permission is inferred.
  `solution.implementation_steps[0]`
- **execute** — These fragments census existing owners, define new-class adapter boundary and require the all-26-family grammar/routes/limits map; no source content or permission is inferred.
  `solution.free_grow.extension_boundary`
- **execute** — These fragments census existing owners, define new-class adapter boundary and require the all-26-family grammar/routes/limits map; no source content or permission is inferred.
  `solution.composition_contracts[2]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.

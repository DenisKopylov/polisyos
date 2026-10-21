# AD-E02-FABRIC-N818-01: сохранить типы исключений, сузить lint-исключение

Дата: 21 октября 2026. Версия решения: 1. **Архитектурный выбор G для реализации: вариант 1, с обязательным устранением конфликта конфигураций.** `architecture_selection=selected_by_G`; `code_acceptance=false`; `closure_ids=[]`. Решение подготовлено по прямому поручению пользователя. Оно не подтверждает применение patch, прохождение gates или получение human repository review.

Вход: `implementation-handoffs/LOCAL/decisions/g-choice-fabric-seven-exception-identities-20261021.md@880c238d834fa311195f40dcd50c627b0a719b9a`. Полные пути, исходные blobs и проверенные evidence hashes — в [receipt](fabric-exception-identities-inputs.json). Пакет относится к source исполнителя; G documentation branch не является его новым code snapshot.

## 1. Решение и причина

**Оставить семь существующих определений классов, их имена, иерархию и поведение.** Для каждого разрешён ровно `N818` на строке определения, с ADR-style пояснением и ссылкой на это решение. Одновременно убрать **только `N818`** из существующего общего Fabric per-file ignore и пересобрать конфигурационные projections штатным генератором. Остальные правила и исключения не ослаблять. Это один согласованный delivery: просто семь `noqa` из авторского patch недостаточны.

Правило проверяет суффикс имени, а не корректность исключения. Переименование ради него не даёт runtime-пользы и создаёт лишнюю миграцию. PEP 8 отдельно ставит сохранение совместимости выше следования стилю; Ruff предоставляет локальные подавления. Это обоснование инженерного выбора, а не внешняя выдача проектного approval. [PEP 8](https://peps.python.org/pep-0008/#a-foolish-consistency-is-the-hobgoblin-of-little-minds), [N818](https://docs.astral.sh/ruff/rules/error-suffix-on-exception-name/).

Не вводить новый exception framework, новые классы, алиасы, runtime-конструирование типов, изменение `__name__`/`__qualname__`, массовый рефакторинг или отдельную систему waiver. У всех семи сохраняется один canonical definition. Другой существующий `ContractViolationError` не является заменой `ContractViolation`.

## 2. Точный набор и совместимость

Все пути таблицы относительно `src/polisyos/fabric/`. Scope key — **путь + module-qualified class + N818**, а не простое имя или номер строки. Здесь семь определений в пяти Python-файлах на base `9743742e164c57503f4c8c68f308bc4f29973661`.

| Определение | Основание сохранения | Выбор |
|---|---|---|
| `connectors/testing/contracts.py::ContractViolation` | Connector-testing facade экспортирует тип; harness ловит его; `__str__` содержит исходное имя | Сохранить definition, facade binding и сообщения |
| `data_plane/cursor_store.py::CursorStoreConflict` | Реальный конфликт cursor/compensation; импорт и catch в streaming. Stable external support глубокой submodule-поверхности не установлен | Сохранить текущий тип как ограниченное решение E02; не объявлять его новым public-stable API |
| `data_plane/streaming.py::StreamDedupeUnsupported` | Typed refusal; три исходных oracle assertions проверяют точное имя типа | Сохранить имя и отказ, включая сохранность прежнего frontier |
| `world/materialize/errors.py::WorldSegmentHashMismatch` | World/materialize exports; проверка целостности сегмента | Сохранить тип и validation category |
| `world/materialize/errors.py::WorldMergeConflict` | World/materialize exports, producers и catch при конфликте | Сохранить тип, cleanup/rethrow и validation category |
| `world/materialize/errors.py::WorldKuzuNotAvailable` | Materialize export и условный world export при доступном DuckDB; отказ optional Kuzu backend | Сохранить тип, условия экспорта и transient category; не менять классификацию отказа ради имени |
| `world/write.py::WorldSnapshotBackendUnavailable` | World export; consumers отличают отсутствие backend от внутреннего import failure | Сохранить тип и границу отказа |

`public_surface/contract.toml` в source вопроса относит Fabric к `public_stable`, но это не делает каждый deep import поддерживаемым API. `__all__` тоже не доказывает такую поддержку. Поэтому тезис «все семь — формально стабильные публичные identities» не нужен и не принят. Достаточно доказанного использования и отсутствия полезного основания менять runtime semantics в этой работе. Решение не расширяет public-surface manifest.

Сохраняются bases/MRO, module/name/qualname, constructor/args, поля, строковое представление, error categories, raised types, exports и catch behavior. Проверка `is` относится к import bindings внутри одного процесса, не к адресам объектов между запусками. Совместимость pickle не объявляется существующим требованием: usage не установлен.

## 3. Обязательное согласование с Ruff

В source вопроса `architecture/tooling/ruff/per-file-ignores/50-fabric.toml` уже подавляет `N818` для всего `src/polisyos/fabric/**`. Авторский strict scan использует отдельный сохранённый map, в котором этого общего подавления нет. Поэтому его семь диагностик совместимы с наличием широкого workspace-ignore; это два разных effective profiles.

При добавлении локальных `noqa` поверх общего ignore появляются две проблемы: восьмой класс всё ещё скрыт; `RUF100` может считать локальный suppression неиспользованным/отключённым. Это подтверждается ветвями `disabled_codes`/`unmatched_codes` в [Ruff 0.14.10](https://github.com/astral-sh/ruff/blob/0.14.10/crates/ruff_linter/src/checkers/noqa.rs), но свежего исполнения этой комбинации G не проводил.

Исполнитель делает следующее в одном согласованном изменении:

1. На своём attached candidate повторно связывает таблицу с реальными definitions и effective config. Не применяет старый patch по совпавшим номерам строк. Если уже имеется эквивалентное корректное изменение, переиспользует его.
2. Добавляет точечные `# noqa: N818`; в затронутом файле даёт ADR-style объяснение, ID и путь этого решения. Например, возле определения: `# AD-E02-FABRIC-N818-01: preserve the existing exception identity.` Полный repo-relative путь решения можно указать один раз в комментарии файла. Голый suppression без объяснения не удовлетворяет `architecture/tooling/ruff/base.toml`.
3. Удаляет `N818` из canonical source fragment `50-fabric.toml`; никакие другие codes не удаляет и не добавляет. Использует существующий `tool_config_split.toml` и генератор `workspace tool-configs`; generated outputs вручную не редактирует. В source вопроса ожидаются workspace/generated Ruff projections; точный набор определяется manifest текущего candidate.
4. Проверяет весь фактический Python denominator затронутого Fabric glob. Исторический manifest содержит 306 путей и совпадает с полным tracked Fabric Python set base; это не константа для будущего дерева. Сохраняет source/tree, версию Ruff, effective config, полный список входов и outputs в существующем receipt.
5. Сохраняет отдельный unsuppressed `N818` diagnostic audit: без inline `noqa`, широких per-file ignores и name-based ignores. Использует изолированный rule-only профиль либо эквивалентно доказанные effective settings. Одного `--ignore-noqa` недостаточно, если config всё ещё подавляет правило. После применения локальных exceptions обычный effective profile должен поддерживать и N818, и RUF100.

Не добавлять `RUF100` suppression для исправления конфликта; не использовать `extend-ignore-names`, file-level `noqa`, wildcard-allowlist или фильтрацию готового списка ошибок как замену действующему Ruff. Новый неподтверждённый восьмой символ не попадает в эту семёрку. Новый внутренний класс без compatibility obligation следует назвать с `Error`; спорный существующий consumer контракт разбирается отдельно. Это не причина пересматривать уже выбранные семь.

В `static_analysis_overrides.toml` inline-noqa baseline и dead-check имеют `report_only`; они не выдают разрешение и не доказывают exact-symbol scope. Их не надо искусственно превращать в новый hard gate или подгонять baseline для зелёного отчёта. В receipt отразить фактический delta и narrowing N818. Старый sunset общего Fabric ratchet `2026-10-01` не продлевается этим решением; остальные codes остаются отдельным tooling debt, а N818 из blanket удаляется.

## 4. Issuer, review и срок действия

**Issuer архитектурного выбора: G, в рамках прямого поручения пользователя в этом чате.** Разрешённый implementation scope определён разделами 1–3 и точной таблицей. Это снимает вопрос «rename или preserve» для E02. Обычный code/config review остаётся частью реализации, а не новой архитектурной развилкой.

Accountability не выдумывается из labels: `team-polisyos` — заявленный owner public surface; `team-architecture` — owner static-analysis report и public version policy; `team-devx` — owner tool-config split. Repository review routes: `@fabric-owners` для source, `@architecture-owners` для architecture config, `@tools-owners` при изменении tooling; fallback `@platform-owners`. `ownership.md` хранит routing к `@DenisKopylov`, но не доказывает проведённый review. Этот документ не утверждает human approval, provisioning групп или новую должностную роль G. Исполнитель прикладывает actual review evidence к своему delivery; автор не reviewer собственного изменения.

**Permanent compatibility rationale, event-driven revisit:** пока сохраняются эти definitions и совместимость, ежегодное/ежедневное переодобрение не нужно. Пересмотр конкретной строки требуется при намеренной миграции/удалении/перемещении definition, изменении exception hierarchy/наблюдаемого контракта, доказанном прекращении его использования либо изменении semantics N818/tool profile, из-за которого suppression перестал соответствовать нарушению. Сдвиг строки, несвязанный commit или календарная дата сами по себе не отзывают решение. Новые символы не наследуют его по сходству имени.

При будущей полезной API-миграции owner явно выбирает новый контракт и release classification; для supported public-stable removals действует текущая repository policy, включая окно двух minor releases. Этот документ не назначает вымышленный номер major release и не требует переименования ради формальной даты.

## 5. Отклонённые альтернативы и атаки

| Альтернатива / атака | Разбор и решение |
|---|---|
| `Old = NewError` | Import/catch могут сохраниться, но меняются имя/qualname/repr canonical class; stream exact-name assertions перестают соответствовать результату. Не выбирать для style repair |
| `NewError = Old` | Identity сохраняется, но N818 остаётся; новый alias увеличивает API без необходимости |
| Старый subclass нового Error | Меняет hierarchy и exact type; новый raised base может не ловиться старым subclass catch; старая definition всё равно нарушает N818 |
| Менять tests, чтобы они принимали новое имя | Это выбор нового контракта, а не доказательство совместимости. Здесь не разрешён |
| Оставить blanket, добавить семь комментариев | Восьмое нарушение скрыто, возможен RUF100. Требуется совместный config narrowing |
| `RUF100` зелёный — значит exception одобрен | Он проверяет применимость suppression, не полномочия или membership в решении |
| Приравнять documentation G HEAD к более свежему code candidate | Ветки не упорядочены ancestry. Отсутствующий на G символ не доказывает его удаление у исполнителя; binding идёт к exact source вопроса и текущему candidate |
| Завести новую глобальную waiver-платформу | Избыточно для семи annotations. Reuse current config generator, lint pipeline, review и delivery receipts |

Python описывает names/qualified names как атрибуты классов, а pickle — через fully qualified names. Это объясняет потенциальную область миграции, но не доказывает использование сериализации этих исключений. [Python data model](https://docs.python.org/3/reference/datamodel.html#special-attributes), [pickle](https://docs.python.org/3/library/pickle.html#what-can-be-pickled-and-unpickled).

## 6. Минимальная приёмка реализации

**G сейчас выполняет только документационную проверку.** Следующие пункты — работа исполнителя, не результаты этой сессии:

- На actual frozen candidate проверить AST до/после этого slice: вне разрешённых комментариев и config/generated companions изменения runtime-кода отсутствуют. Для уже имеющегося большого typing patch использовать именно base узкого N818 slice; не приписывать ему весь общий diff.
- Выполнить canonical generator check и Ruff на полном актуальном native Fabric denominator. Сохранить отдельно native profile и workspace profile; зелёный одного не переносится на другой. Снять unsuppressed diagnostics и сопоставить их **по definition identity**, а не только числом 7. Другие FAIL не скрывать.
- В isolated scratch добавить восьмой `RuntimeError` subclass без суффикса и без `noqa`: canonical effective N818 должен дать FAIL. Для same-name класса в другом модуле copied suppression не разрешён: source-bound review/audit должен выявить его вне таблицы, даже если сам Ruff его подавит. Удаление одного разрешённого `noqa` возвращает N818; смена class name на соответствующее правилу при оставшемся комментарии выявляется RUF100. Эти probes не изменяют product tree.
- Переиспользовать фактическую команду, которая произвела native N818 census, и существующий receipt flow. Наличие raw результата ещё не доказывает существование готового exact-membership verifier. Если такого checker нет, достаточно небольшого source-bound аудита в delivery tooling: resolve path + module + ClassDef + rule + decision binding, с полным выводом и copied-suppression canary. `check_fabric_exception_baseline.py` проверяет другой класс — broad `except Exception` — и не является готовым N818 verifier. Baseline `inline_noqa_count` и plain grep тоже его не заменяют. Не строить универсальную verifier-of-verifier систему.
- Сохранить текущие stream type-name/refusal/frontier, cursor compensation, world integrity/conflict и backend-refusal assertions. Для comment-only slice не нужен новый дорогой replay; выполнить затронутые уже существующие проверки в плановой native wave. Если фактически изменились runtime identities, это выходит за scope и требует отдельной миграции, а не косметической смены ожидаемых значений.
- Доставить пять source-файлов, canonical config fragment и необходимые generated/receipt companions согласованно, соблюдая текущих writers. Старое разделение «5 у автора + 2 у соседей» не разрешает потерять два companion symbols. Ordinary repo gates и их реальные результаты сохраняются отдельно.

При выполнении всех условий корректная формулировка: **«native Ruff PASS; семь явно разрешённых N818 compatibility exceptions; unsuppressed N818 audit — те же семь identities»**. Не оставлять вечный `red-limited` после корректно применённого решения, но и не писать «нулевой naming debt» либо integrated runtime PASS. Прочие gates, source acceptance и finding closure этим выбором не решаются.

Pattern pass: P27/P31 — один canonical type; P35 — полный source-qualified denominator; P38 — suffix compliance не подменяет совместимость; P29/P32/P37 — реальные lint diagnostics и canary, не markers/count; P39 — обязательные config/receipt companions вне искусственной квоты семи строк; P40 — одно cohort решение; P41 — этот native gate пересекает candidate, статус inherited не установлен. Реализация и её подтверждение остаются `verification_missing` до actual delivery evidence. Изменение system-design-decisions не требуется.

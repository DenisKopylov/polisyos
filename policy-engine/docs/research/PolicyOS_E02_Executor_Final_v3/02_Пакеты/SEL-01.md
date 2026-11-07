# SEL-01 — Применимый метод без ложных требований и ложных объяснений

**LANE-01 · B34, B35, B36 · ТЗ исполнителю; все TEST — NOT_RUN.**
База `20d9009be21097bfbdc38a546a15cc60213b8ace`; [неизменённый аудит](../05_Основания/Аудит/02_Пакеты/SEL-01.md), [исходная карточка](../05_Основания/Аудит/05_Источники/SEL-01_исходные_строки.txt), строки 1444–1588.
**Практический результат:** Действительно доступный метод достигает своего consumer; singleton разрешён, каталог не переписывает запрос, а причины отказа подсказывают правильный следующий шаг.
Типы работы разделены ниже. Уже существующий механизм не переписывать только ради diff; qualify означает реальный запуск/потребление, capability — построение недостающего положительного пути.

## 1. Сохраняемые свойства

- No cardinality-only ban
- Native output-owner and context/content binding
- One actual registry owner
- Value/runnable/modality/route filter before limit
- Full value denominator distinct from eligible trace
- Relevant vs unrelated catalog context drift
- Unchanged explicit required modalities
- Malformed present input refused
- Explicit method obeys same hard requirements
- Защищённые различения: LK06. S08: новую совместимую конфигурацию проверять на том же механизме, а не ветке по ID кейса.

## 2. Полнота исходных обязательств и остатков

| Основание | REQ | Disposition / решение |
|---|---|---|
| audit-residual:C11_остатки:0 | REQ-SEL-01-01 | fix: Отделить hard source от technical lexical signal. |
| audit-residual:C11_остатки:1 | REQ-SEL-01-02 | fix: Loss reason по первому differing rank key. |
| audit-residual:C11_остатки:2 | REQ-SEL-01-04 | capability: Source-qualified full scope, не checksum shortcut. |
| audit-residual:C11_остатки:3 | REQ-SEL-01-03 | capability: Per-member hard exclusion trace. |
| audit-residual:C11_остатки:4 | REQ-SEL-01-05 | qualify: Необходимость converter не доказана; только конкретный producer/consumer case. |
| B34 | REQ-SEL-01-04, REQ-SEL-01-05 | fix: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| B35 | REQ-SEL-01-02, REQ-SEL-01-03, REQ-SEL-01-05 | fix: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| B36 | REQ-SEL-01-01, REQ-SEL-01-05 | fix: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| remaining:0085 | REQ-SEL-01-04 | capability: Scoped intake и consumer falsifier. |
| remaining:0086 | REQ-SEL-01-04 | qualify: Native singleton/hidden-member/readback. |
| remaining:0087 | REQ-SEL-01-02 | fix: Реальная lexicographic причина. |
| remaining:0088 | REQ-SEL-01-03 | capability: Каждый hard member получает disposition. |
| remaining:0089 | REQ-SEL-01-03, REQ-SEL-01-05 | qualify: Source/selector/consumer фактически связан. |
| remaining:0090 | REQ-SEL-01-01 | fix: Opaque/proposal не hard panel. |
| remaining:0091 | REQ-SEL-01-01, REQ-SEL-01-05 | qualify: Содержательное требование и concrete conversion только когда нужно. |

## 3. Нормативные REQ и конкретное решение

### REQ-SEL-01-01 — fix
Opaque candidate/atom IDs и lexical proposals не должны добавлять обязательную modality; explicit и owner-derived требования сохраняются независимо от каталога и имени.

**Решение на существующих владельцах.** Разделить _candidate_selection_signal для preferences от _required_modalities hard source. Исключить candidate_id/id/intervention_id/diversity key как самостоятельное semantic authority; explicit hints и typed ValueDataProfile остаются обязательными. Если содержательный текст предлагает panel, сохранить proposal отдельно до owner/declared requirement, не лечить regex только no_panel. Explicit method подчиняется тем же hard predicates.
**Приёмка:** TEST-SEL-01-01.

### REQ-SEL-01-02 — fix
Loss reason ранжированного метода должен отражать первый реально различающий ключ принятого lexicographic rank, не ложный scalar comparison.

**Решение на существующих владельцах.** В _rank_entries_with_scores/receipt builder сохранить structured ranking decision keys truthfulness_depth,score_rest,fqn/tie; reason derives first differing key. Не менять приоритет truthfulness и не переписывать сырые scores ради надписи. Receipt schema/legacy module compatibility сохранить через existing receipt.py owner; version new explanatory fields if needed.
**Приёмка:** TEST-SEL-01-02.

### REQ-SEL-01-03 — capability
Для каждого hard-excluded member полного value-denominator должна сохраняться адресная disposition без выдуманного numeric rank; eligibility применяется до top-k.

**Решение на существующих владельцах.** Сохранить full value denominator отдельно от eligible trace. Existing filter loop накапливает deterministic reason unrunnable/route/modality/owner-contract gap и declared scope; использовать существующий candidate-disposition pattern, не второй catalog traversal с иной политикой. Rank reasons TEST-02 не смешиваются с hard-exclusion. Не увеличивать limit вместо исправления.
**Приёмка:** TEST-SEL-01-03.

### REQ-SEL-01-04 — capability
Genuine singleton должен приниматься на source-qualified scoped intake, а согласованно усечённый denominator отвергаться actual receiving owner.

**Решение на существующих владельцах.** Использовать one MethodRegistry/view и existing catalog registry_report/bound manifest/intake members контракт; где claiming full scope, композиция передаёт require_bound_discovery и настоящий report, не только context equality. Consumer revalidates complete scoped owner rows. Не требовать2метода, подпись из воздуха или universal external catalog completeness; declared envelope явно ограничен.
**Приёмка:** TEST-SEL-01-04.

### REQ-SEL-01-05 — qualify
Выбранный подходящий метод должен реально потребить owner rows и дать полезный output; modality conversion допускается только через настоящий producer с сохранённым estimand.

**Решение на существующих владельцах.** Использовать FoundryValuePort→ValueDataProfile→select_value_method_for_problem→receipt/current context→method consumer. tests/unit/foundry/methods/test_selection_advisor.py — текущий suite; старый test_sel_01.py не найден. Для нового compatible registered resource подтвердить actual output, не water-quality projectorNone. Универсальный converter не заказывать: если конкретный разрешённый case требует conversion, bounded выбрать existing adapter либо implement общий contract с входами/units/shape/loss, output удовлетворяет исходному требованию.
**Приёмка:** TEST-SEL-01-05.

## 4. Локальные различающие тесты

Все номера TEST ниже — проектируемые проверки, не вымышленные имена существующих pytest-функций. Существующие файлы использовать/расширить; старый mutation или контролируемое удаление проверяемого механизма должен давать отличающийся исход.

### TEST-SEL-01-01 · NOT_RUN
- **Setup:** Actual selector/catalog с tabular method и explicit tabular; ID case-alpha→case-panel-alpha, atomID,no_panel_data; separately explicit panel.
- **Действие:** Пройти native selection→receipt/blocked consumer с каждым переименованием.
- **Oracle:** Применимость unchanged при technical rename; explicit panel по-прежнему blocked на tabular-only и проходит actual panel method.
- **Positive / negative / boundary:** Context hash может измениться по ID без изменения hard modality; malformed present не пустой request.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-SEL-01-02 · NOT_RUN
- **Setup:** SelectedA truthdepthhigh score10, B lowerdepth score100; equaldepth lower/tie scores и FQN tie.
- **Действие:** Пройти actual rank→receipt serialize→consumer; проверить объяснение всех losers.
- **Oracle:** B проигрывает по truthfulness, не «score ниже»; равный tier действительно объясняет score/tie; selected неизменен.
- **Positive / negative / boundary:** Число rank не становится authority, legacy readers либо понимают новое поле либо корректно ограничены.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-SEL-01-03 · NOT_RUN
- **Setup:** Каталог eligible panelB, hard-excluded tabularA,20non-value rows;12eligible при limit8.
- **Действие:** Выбрать actual method, serialize receipt+dispositions и открыть consumer; добавить нерелевантные diagnostic entries.
- **Oracle:** Полный value denominator и per-member hard reason сохраняются; selected/контекст unaffected нерелевантным расширением; trace ranked subset честен.
- **Positive / negative / boundary:** Excluded не получает fake advisor score; неизвестная причина не generic no-method.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-SEL-01-04 · NOT_RUN
- **Setup:** Настоящие registered output contracts, реальный owner intake/manifest для singleton и для нескольких members; не monkeypatch builder к удобному snapshot.
- **Действие:** Выполнить singleton automatic/explicit; затем скрыть mandatory member согласованно в receipt/trace и пересчитать hash, сохранив declared intake.
- **Oracle:** Singleton accepted как единственный в scope; hidden-member receipt rejected actual consumer; fictional explicit method не registered.
- **Positive / negative / boundary:** Self-consistent DTO не внешний denominator proof; cross-method consensus требование2отдельно не отменять.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-SEL-01-05 · NOT_RUN
- **Setup:** Один actual useful owner-backed value method и новый совместимый resource/entry; truthful absent-modality case. При conversion — конкретные declared source/target contracts.
- **Действие:** Пройти selection→реальное method execution→persisted consumer; сменить relevant catalog/profile, отдельно unrelated non-value drift.
- **Oracle:** Полезный output и exact basis; relevant drift invalidates, unrelated не скрывает старый метод; conversion проверяет output semantics, не merely план.
- **Positive / negative / boundary:** Нет automatic empirical/rollout authority; no adapter-needed scenario не превращается в обещание универсального converter.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

## 5. Общее испытание, зависимости и ownership

Общие сценарии: **E02-I01-A**, [определение LANE-01](../03_Интеграция/LANE-01.md). Исполнять только затронутый маршрут; CP — координационная приёмка, не новый runtime registry и не обязательный запуск всего CI.
- SEL-01 owns advisor/receipt semantics; existing MethodRegistry/catalog owner supplies intake, не второй registry. LK06 roles view/kernel сохраняются.
- REQ-01 аналогичный invariant ID≠semantics, но другой compiler owner: не объединять два механизма в новый NLP framework.
- CYC-02/EMP actual value consumer и SIM numeric profile; выбор одного метода не cross-method consensus.

## 6. Порядок и совместимость

Сначала воспроизвести на pinned baseline адресный контракт/дефект; затем один writer меняет общий owner, сохраняя callers и исторические readers. Поведенческий delta и перенос/cleanup описать раздельно. Не переписывать immutable старые artifacts: новая интерпретация получает явную version/basis. Rollback не переименовывает новые результаты как старые; reader обязан либо сохранить корректное чтение, либо дать точное unsupported/version ограничение. Команды и selectors проверить в checkout перед запуском, dependency install согласовать с общим исполнителем среды.

## 7. Design alignment и полезная способность

[System Vision, §6 Capability Reality Bar и §5 Rule12](../05_Основания/Архитектура/universal-policy-design-system-vision-and-organizing-rules.md): полный producer→persisted artifact→bridge→consumer; новый совместимый ресурс проходит общий механизм. Это не запрет нового общего кода для новой семантики. [D0 B-on-A](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md), раздел «D0 — Decision: B-on-A, Shadow-First»: полезная кандидатная работа допускается без автоматического полномочия. [Stage0 §4.3 K06](../05_Основания/Архитектура/stage0-custody-kernel-ratification.md): неизвестность ограничивает затронутое действие, не всё исследование.

Рост каталога обязан увеличивать доступность compatible ресурсов, не вытеснять нужные методы через non-value top-k. Истинные hard requirements не смягчаются ради зелёного выбора.

## 8. Ограниченные решения

Отдельного свободного исследования не требуется: контракт, owner и различающий oracle заданы выше. Выявленный недостающий общий interface расширять только с конкретным producer/consumer и тестом, не новым параллельным framework.

## 9. Проверенные текущие пути

- [policy-engine/src/polisyos/foundry/methods/selection/advisor.py:1753–1785](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/selection/advisor.py#L1753-L1785) — `def _required_modalities`.
- [policy-engine/src/polisyos/foundry/methods/selection/advisor.py:1519–1551](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/selection/advisor.py#L1519-L1551) — `def _build_value_method_selection_receipt`.
- [policy-engine/src/polisyos/foundry/methods/selection/advisor.py:1952–1984](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/selection/advisor.py#L1952-L1984) — `def _rank_entries_with_scores`.
- [policy-engine/src/polisyos/foundry/methods/selection/receipt.py:32–64](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/selection/receipt.py#L32-L64) — `class MethodSelectionReceipt`.

## 10. Точная preservation-трассировка

| Inventory ID | REQ / TEST | Смысл |
|---|---|---|
| preserve:0108 | REQ-SEL-01-04, TEST-SEL-01-04 | No cardinality-only ban |
| preserve:0109 | REQ-SEL-01-04, REQ-SEL-01-05, TEST-SEL-01-04, TEST-SEL-01-05 | Native output-owner and context/content binding |
| preserve:0110 | REQ-SEL-01-04, TEST-SEL-01-04 | One actual registry owner |
| preserve:0111 | REQ-SEL-01-03, TEST-SEL-01-03 | Value/runnable/modality/route filter before limit |
| preserve:0112 | REQ-SEL-01-03, TEST-SEL-01-03 | Full value denominator distinct from eligible trace |
| preserve:0113 | REQ-SEL-01-05, TEST-SEL-01-05 | Relevant vs unrelated catalog context drift |
| preserve:0114 | REQ-SEL-01-01, TEST-SEL-01-01 | Unchanged explicit required modalities |
| preserve:0115 | REQ-SEL-01-01, TEST-SEL-01-01 | Malformed present input refused |
| preserve:0116 | REQ-SEL-01-01, TEST-SEL-01-01 | Explicit method obeys same hard requirements |

## 11. Что предъявить и что не считать PASS

Предъявить конкретные до/после assertions и actual affected consumer, сохранённые outputs/refs, failure controls, source identity и поддержанный runtime. Наличие кода, формы receipt, этого ТЗ либо старого зелёного теста не является выполнением. Local/source-excerpt observation не native acceptance; skipped/blocked остаётся видимым. Число или candidate output не повышается автоматически в empirical/decision authority. Согласовать полезный positive, не ограничиваться запретами. Полные исходные probes находятся в отдельно доставленном phase1 ZIP; текущая подготовка не создаёт нового product execution.

[Машинная трассировка](../04_Трассировка/SEL-01.json). Аудит охватил127/127; это не означает выполненных127 ремонтов.

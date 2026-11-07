# CYC-05 — Реальная декомпозиция, правдивый stop и положительный deployment bridge

**LANE-01 · B15, B29, B30 · ТЗ исполнителю; все TEST — NOT_RUN.**
База `20d9009be21097bfbdc38a546a15cc60213b8ace`; [неизменённый аудит](../05_Основания/Аудит/02_Пакеты/CYC-05.md), [исходная карточка](../05_Основания/Аудит/05_Источники/CYC-05_исходные_строки.txt), строки 980–1090.
**Практический результат:** Два содержательных child проходят настоящий маршрут с видимыми лимитами; частичный результат сохраняется; проверенный deployment имеет достижимый currentness consumer, а неизвестный не самосертифицируется.
Типы работы разделены ниже. Уже существующий механизм не переписывать только ради diff; qualify означает реальный запуск/потребление, capability — построение недостающего положительного пути.

## 1. Сохраняемые свойства

- Requested/effective limit and reason
- Exact N4 child-set and contexts
- Proposal-only not_applied marker
- Accumulated numerical history at stop
- Exhaustive typed stop partition
- stop/stopped distinct from abstain/abstained
- Resource stop does not claim scientific exhaustion
- Missing/parse/read/direct caller distinctions
- Existing import-time loaded identity and currentness owner
- Candidate-band continuation, historical readability
- No automatic authority from clean source/identity equality
- Защищённые различения: релевантные candidate/authority, input/result, historical/current различия из отчёта. S08: новую совместимую конфигурацию проверять на том же механизме, а не ветке по ID кейса.

## 2. Полнота исходных обязательств и остатков

| Основание | REQ | Disposition / решение |
|---|---|---|
| audit-residual:C07_остатки:0 | REQ-CYC-05-04, REQ-CYC-05-05 | capability: CYC-05 bridge consumes lane12 actual build/census artifacts; назначение issuer не выдумывается. |
| audit-residual:C07_остатки:1 | REQ-CYC-05-01, REQ-CYC-05-02 | qualify: Actual two-child и budget stop. |
| audit-residual:C07_остатки:2 | REQ-CYC-05-03 | qualify: Normal stop producer сохранить; полная projection проверить. |
| audit-residual:C07_остатки:3 | REQ-CYC-05-07 | capability: CYC-05 authoring relationships, SIM-03 joint numerical semantics; не смешивать. |
| audit-residual:C07_остатки:4 | REQ-CYC-05-02 | qualify: Численный cap принимать по enclosing artifact, не standalone shape. |
| B15 | REQ-CYC-05-01, REQ-CYC-05-02, REQ-CYC-05-07 | fix: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| B29 | REQ-CYC-05-03 | qualify: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| B30 | REQ-CYC-05-04, REQ-CYC-05-05, REQ-CYC-05-06 | fix: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| remaining:0038 | REQ-CYC-05-01 | qualify: Actual meaningful children, не aliases. |
| remaining:0039 | REQ-CYC-05-02 | qualify: Первый результат + явный frontier. |
| remaining:0040 | REQ-CYC-05-07 | capability: Typed relationships и bounded authored joint путь с SIM-03. |
| remaining:0070 | REQ-CYC-05-03 | qualify: DTO/persisted/consumer roundtrip. |
| remaining:0071 | REQ-CYC-05-03 | qualify: Sibling-field corruption controls. |
| remaining:0072 | REQ-CYC-05-04 | capability: Реальный положительный issuer bridge, не тест fixed UNRUN. |
| remaining:0073 | REQ-CYC-05-04, REQ-CYC-05-05 | capability: Supported profile и invalidation. |
| remaining:0074 | REQ-CYC-05-05 | qualify: Фактический I/O замер, не заявленное ускорение. |

## 3. Нормативные REQ и конкретное решение

### REQ-CYC-05-01 — qualify
HTTP/worker должен сохранять requested/effective limits/reason и exact source-derived child denominator; каждый исполняемый child связан с собственными problem/context/N5, а proposal-only не выдаёт применённый recursive budget.

**Решение на существующих владельцах.** Сохранить _resolve_http_recursive_budget и derive_n4_candidate_child_problems→derive_recursive_design_graph→recursive controller. Не снимать cap3/configured child cap2; generic source-complete profile использует весь подтверждённый набор в разрешённом depth/nodes. Parent/source/context/job/scope согласуются до вызова. Не выдумывать graph простым увеличением depth.
**Приёмка:** TEST-CYC-05-01.

### REQ-CYC-05-02 — qualify
Остановка по общему ресурсу после первого child должна сохранять его результат и явный неисследованный frontier; standalone и enclosing budget projection согласуются.

**Решение на существующих владельцах.** Existing recursive partial builder/frontier continuation использовать без второго loop. Проверять numerical cap по enclosing HTTP budget resolution, поскольку standalone N6 не несёт max_cycles. Каждый начатый child/iteration привязан к admitted budget; не считать intrinsic shape validator доказательством численного cap.
**Приёмка:** TEST-CYC-05-02.

### REQ-CYC-05-03 — qualify
Normal stop, resource stop и abstention должны сохранять разные смыслы в decision/iteration/history/API/реальном UI; изменение только соседней проекции не должно давать согласованный результат.

**Решение на существующих владельцах.** Сохранить _N6_TERMINAL_STOP_PROJECTIONS полным по SearchTerminalKind, _refinement_decision/_search_iteration и intrinsic validator. Не исправлять уже правильный stop→stopped заново. Проверить конечный consumer; при несогласованной sibling decision/action/terminal адресно отказывать, не нормализовать к удобному success.
**Приёмка:** TEST-CYC-05-03.

### REQ-CYC-05-04 — capability
Должен существовать положительный назначенный build/deployment→N6 readiness путь для конечного поддержанного профиля, привязанный к фактически загруженному коду; константа UNRUN не заменяется без доказательства.

**Решение на существующих владельцах.** CYC-05 owns typed bridge в confidence_ledger: расширить inspect_packaged_deployment_identity, входом сделать проверяемый artifact от существующих build/distribution/census producers LANE-12. Artifact связывает exact distribution/source/lock/project/runtime baseline, relevant entrypoint/import bindings, census denominator/rule version/result и назначенного issuer/purpose. Existing ledger/identity verifier перечитывает artifact и проверяет issuer appointment/subject/scope/bytes; сам manifest/hash equality не issuer. Затем reconcile с import-time loaded baseline и известной disk/runtime consistency. Только совместный success даёт PackagedDeploymentIdentityReadiness PASS и observe_n6_deployment_currentness current; stale/missing/malformed/unappointed остаются точными limitations. Не создавать второй registry/receipt framework, не выдавать institutional authority из build integrity.
**Приёмка:** TEST-CYC-05-04.

### REQ-CYC-05-05 — qualify
Смена существенного code/lock/runtime/import binding должна инвалидировать ранее положительное deployment основание; неизменный run не повторяет full AST и не лишается исторической читаемости.

**Решение на существующих владельцах.** Использовать capture_loaded_deployment_identity frozen snapshot + existing canonical ledger revalidation; issuer artifact key включает весь заявленный relevant baseline. Verify-on-admission/readiness сохраняет loaded-vs-disk distinction: смена диска не переписывает identity уже загруженного процесса. Производить новый immutable artifact для новой basis, а не обновлять прежний PASS. Измерять actual I/O на unchanged run, без недоказанного speedup claim.
**Приёмка:** TEST-CYC-05-05.

### REQ-CYC-05-06 — qualify
Прямой structural census должен различать missing/empty/unreadable/parse error и настоящий запрещённый caller; недостаточный знаменатель не даёт positive verdict.

**Решение на существующих владельцах.** Сохранить _collect_strangle_source_census и inspect_n6_source_census как ограниченные diagnostics; manifest/proof производителя TEST-04 обязан назвать path denominator и неподдержанные динамические вызовы. LANE-12 owns фактический census/build artifact production; здесь проверяется чтение и bounded semantics, не новый AST framework.
**Приёмка:** TEST-CYC-05-06.

### REQ-CYC-05-07 — capability
Декомпозиция должна различать alternatives, joint components и sequential steps; граф детей не превращает alternatives в authored compound, но поддержанный явно сформулированный compound должен иметь проверяемый путь исполнения.

**Решение на существующих владельцах.** LLM/author может предложить typed relationships и composition intent. Расширять существующий ParentJointCandidateSelection/profile contract только для конкретного supported relation; сохранить source_candidate_relationship=alternatives/composition_status=not_established для старых inputs. CYC-05 owns authoring/decomposition→persisted relationship→consumer binding; SIM-03 owns actual model-bound joint comparator/effect/interaction computation. Для compound предъявить actual combined intervention/model, не сумму отдельных child outputs или hypothetical diagnostic.
**Приёмка:** TEST-CYC-05-07.

## 4. Локальные различающие тесты

Все номера TEST ниже — проектируемые проверки, не вымышленные имена существующих pytest-функций. Существующие файлы использовать/расширить; старый mutation или контролируемое удаление проверяемого механизма должен давать отличающийся исход.

### TEST-CYC-05-01 · NOT_RUN
- **Setup:** Existing tests/integration/runtime_quality/test_generic_n4_child_profile_set_served.py selector test_original_second_capture_serves_two_meaningful_children_through_fresh_get; два разных предложения tax credit/procurement backstop, третье blocked.
- **Действие:** Пройти ordinary POST/worker и fresh GET, затем удалить одного source-derived child при прежней graph оболочке; запросить7итераций и конфликт профилей.
- **Oracle:** Точные child refs и реальные численные результаты обоих; requested/effective/reason читаемы; missing denominator отказан, proposal-only not_applied_n4_proposal_only сохраняется.
- **Positive / negative / boundary:** Два aliases одного fixture не meaningful decomposition; третий configured child не молча отрезан, budget cap не обещает полноту.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-CYC-05-02 · NOT_RUN
- **Setup:** Реальный two-child setup TEST-01 с разрешённым budget ровно на первый child, actual result store.
- **Действие:** Выполнить первый, исчерпать общую allocation, прочитать completed/partial graph; попытаться подменить enclosing cap.
- **Oracle:** Первый actual output доступен, второй not_run с frontier reason, spent/iterations соответствуют разрешению; cap tamper не current accepted.
- **Positive / negative / boundary:** Budget stop не scientific exhaustion и не blanket invalidity всех результатов; разрешённый более дешёвый next action требует собственного admission.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-CYC-05-03 · NOT_RUN
- **Setup:** Настоящие DTO terminal frontier_stable, grounded_partial, budget_exhausted, abstained; persisted history и actual visible consumer.
- **Действие:** Roundtrip каждый тип; отдельно изменить только refinement decision, только iteration status без изменения terminal.
- **Oracle:** Успешный ограниченный stop не abstained; budget kind сохранён; истинное abstention видно; sibling corruption обнаруживается.
- **Positive / negative / boundary:** Historical read остаётся возможным без нынешней deployment-currentness; не объединять candidate/strict/history validators.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-CYC-05-04 · NOT_RUN
- **Setup:** Реальный ограниченный source-checkout либо installed distribution профиль, произведённый lane12 build/test artifact и назначенный допустимый issuer; настоящее confidence_ledger/load/reader, не injected ready(PASS).
- **Действие:** Build→persist artifact→load qualified process→inspect readiness→finish N6→strict current consumer; затем удалить issuer binding/census или заменить artifact.
- **Oracle:** Положительный current/PASS достижим только на согласованном реально загруженном профиле; effective consumer принимает точное structural основание, но не присваивает N9 по одной identity.
- **Positive / negative / boundary:** Self-issued manifest, clean git или matching source hashes недостаточны; no issuer остаётся not_established, candidate результаты продолжаются.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-CYC-05-05 · NOT_RUN
- **Setup:** Positive TEST-04, два deployment baselines и одна disk mutation после import; instrument только чтения/время, не verifier.
- **Действие:** Изменить по одному source, lock, relevant binding и artifact bytes; открыть historical run и candidate/strict readers; повторить unchanged N6.
- **Oracle:** Meaningful drift stale/not_established до strict use; historical bytes читаются, candidate limitations видимы; unchanged identity использует canonical snapshot без full source census per finish.
- **Positive / negative / boundary:** Не объявлять alias scan полной динамической недостижимостью; границы profile/denominator остаются в evidence.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-CYC-05-06 · NOT_RUN
- **Setup:** Малый настоящий filesystem с missing src, empty, invalidUTF8, parse failure, direct call и permitted fixture-site; installed profile без source отдельно.
- **Действие:** Исполнить actual inspector/receipt reader; удалить часть declared denominator либо заменить issuer-produced census digest.
- **Oracle:** Причины различимы, direct violation не смешан с parse error; incomplete не current/PASS. Alias limitation явно указана, не fake proof.
- **Positive / negative / boundary:** Пакетный build допускает source-free runtime только при верифицированном declared build evidence, не пустом обходе.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-CYC-05-07 · NOT_RUN
- **Setup:** Два meaningful components с явным authored joint intent и совместимой моделью из SIM-03; исходные alternatives как negative/control.
- **Действие:** Сохранить relationships, построить graph/request, выполнить совместный agreed numerical scenario и fresh consumer.
- **Oracle:** Relations/units/basis/limits переживают readback; compound actual joint result имеет отдельную правильную модельную постановку; alternatives остаются alternatives.
- **Positive / negative / boundary:** Неизвестное refinement/causal coupling сохраняется как limitation, не автоматически запрещает independent candidate исследование.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

## 5. Общее испытание, зависимости и ownership

Общие сценарии: **E02-I01-C, E02-X01**, [определение LANE-01](../03_Интеграция/LANE-01.md). Исполнять только затронутый маршрут; CP — координационная приёмка, не новый runtime registry и не обязательный запуск всего CI.
- CYC-05 единственный writer положительного confidence_ledger readiness bridge/current consumer. LANE-12 DFK/HYG/CLI — фактические build/distribution/census/test artifact producers; не второй readiness issuer.
- Issuer appointment и purpose/baseline contract согласовать с существующим identity owner до coding; не создавать внешний authority факт самостоятельно.
- SIM-03 owns actual compound contrast/math; CYC-05 owns authored relationships, decomposition и propagation.
- CYC-02 preserved numeric readback; CYC-03 current vs historical identities; общий generation_cycle.py mutex.

## 6. Порядок и совместимость

Сначала воспроизвести на pinned baseline адресный контракт/дефект; затем один writer меняет общий owner, сохраняя callers и исторические readers. Поведенческий delta и перенос/cleanup описать раздельно. Не переписывать immutable старые artifacts: новая интерпретация получает явную version/basis. Rollback не переименовывает новые результаты как старые; reader обязан либо сохранить корректное чтение, либо дать точное unsupported/version ограничение. Команды и selectors проверить в checkout перед запуском, dependency install согласовать с общим исполнителем среды.

## 7. Design alignment и полезная способность

[System Vision, §6 Capability Reality Bar и §5 Rule12](../05_Основания/Архитектура/universal-policy-design-system-vision-and-organizing-rules.md): полный producer→persisted artifact→bridge→consumer; новый совместимый ресурс проходит общий механизм. Это не запрет нового общего кода для новой семантики. [D0 B-on-A](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md), раздел «D0 — Decision: B-on-A, Shadow-First»: полезная кандидатная работа допускается без автоматического полномочия. [Stage0 §4.3 K06](../05_Основания/Архитектура/stage0-custody-kernel-ratification.md): неизвестность ограничивает затронутое действие, не всё исследование.

Развитие не ограничено UNRUN diagnostics: требуются достижимый положительный readiness bridge и полезная малая декомпозиция. Fail-closed касается strict current/authority, не всех candidate вычислений.

## 8. Ограниченные решения

- **DEC-CYC-05-01**: Какой реально поддержанный deployment профиль и существующий issuer appointment дают конечный положительный structural contract? Owner: CYC-05 совместно с LANE-12 producer/identity owner. Варианты: Source-checkout профиль с полным build/census artifact и canonical loaded baseline.; Installed distribution профиль с verified package manifest, declared build census и loaded binding.. Выбор по: Найденные actual build outputs, назначенный purpose/issuer и возможность проверить весь relevant denominator; не только наличие json.. Обязательный выход: Один именованный профиль, versioned artifact/issuer interface, valid positive и invalidation tests; отсутствие appointment оформляется точным внешним предусловием, а bridge/consumer всё равно реализуются и проверяются на допустимом тестовом principal.

## 9. Проверенные текущие пути

- [policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:5548–5580](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/confidence_ledger.py#L5548-L5580) — `def inspect_packaged_deployment_identity`.
- [policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:5577–5609](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/confidence_ledger.py#L5577-L5609) — `def observe_n6_deployment_currentness`.
- [policy-engine/src/polisyos/runtime/quality/generation_cycle.py:499–531](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L499-L531) — `_N6_TERMINAL_STOP_PROJECTIONS`.
- [policy-engine/src/polisyos/runtime/http/services/control/generation_cycle.py:218–250](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/http/services/control/generation_cycle.py#L218-L250) — `def _resolve_http_recursive_budget`.
- [policy-engine/src/polisyos/runtime/quality/recursive_generation_cycle.py:1594–1626](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/recursive_generation_cycle.py#L1594-L1626) — `class ParentJointCandidateSelectionV2`.

## 10. Точная preservation-трассировка

| Inventory ID | REQ / TEST | Смысл |
|---|---|---|
| preserve:0045 | REQ-CYC-05-01, REQ-CYC-05-02, TEST-CYC-05-01, TEST-CYC-05-02 | Requested/effective limit and reason |
| preserve:0046 | REQ-CYC-05-01, REQ-CYC-05-07, TEST-CYC-05-01, TEST-CYC-05-07 | Exact N4 child-set and contexts |
| preserve:0047 | REQ-CYC-05-01, TEST-CYC-05-01 | Proposal-only not_applied marker |
| preserve:0048 | REQ-CYC-05-02, TEST-CYC-05-02 | Accumulated numerical history at stop |
| preserve:0091 | REQ-CYC-05-03, TEST-CYC-05-03 | Exhaustive typed stop partition |
| preserve:0092 | REQ-CYC-05-03, TEST-CYC-05-03 | stop/stopped distinct from abstain/abstained |
| preserve:0093 | REQ-CYC-05-02, REQ-CYC-05-03, TEST-CYC-05-02, TEST-CYC-05-03 | Resource stop does not claim scientific exhaustion |
| preserve:0094 | REQ-CYC-05-06, TEST-CYC-05-06 | Missing/parse/read/direct caller distinctions |
| preserve:0095 | REQ-CYC-05-04, REQ-CYC-05-05, TEST-CYC-05-04, TEST-CYC-05-05 | Existing import-time loaded identity and currentness owner |
| preserve:0096 | REQ-CYC-05-03, REQ-CYC-05-05, TEST-CYC-05-03, TEST-CYC-05-05 | Candidate-band continuation, historical readability |
| preserve:0097 | REQ-CYC-05-04, TEST-CYC-05-04 | No automatic authority from clean source/identity equality |

## 11. Что предъявить и что не считать PASS

Предъявить конкретные до/после assertions и actual affected consumer, сохранённые outputs/refs, failure controls, source identity и поддержанный runtime. Наличие кода, формы receipt, этого ТЗ либо старого зелёного теста не является выполнением. Local/source-excerpt observation не native acceptance; skipped/blocked остаётся видимым. Число или candidate output не повышается автоматически в empirical/decision authority. Согласовать полезный positive, не ограничиваться запретами. Полные исходные probes находятся в отдельно доставленном phase1 ZIP; текущая подготовка не создаёт нового product execution.

[Машинная трассировка](../04_Трассировка/CYC-05.json). Аудит охватил127/127; это не означает выполненных127 ремонтов.

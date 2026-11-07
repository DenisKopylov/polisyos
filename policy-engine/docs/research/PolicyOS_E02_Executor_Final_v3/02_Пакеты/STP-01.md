# STP-01 — Атомарный актуальный сигнал и устойчивое plateau сравнение

**LANE-02 · B41, B122 · ТЗ исполнителю; все TEST — NOT_RUN.**
База `20d9009be21097bfbdc38a546a15cc60213b8ace`; [неизменённый аудит](../05_Основания/Аудит/02_Пакеты/STP-01.md), [исходная карточка](../05_Основания/Аудит/05_Источники/STP-01_исходные_строки.txt), строки 2161–2250.
**Практический результат:** Исследование не останавливается по отвергнутому embedding или переполнению; настоящая эвристическая стабильность и ресурсный stop остаются полезными и явно ограниченными.
Типы работы разделены ниже. Уже существующий механизм не переписывать только ради diff; qualify означает реальный запуск/потребление, capability — построение недостающего положительного пути.

## 1. Сохраняемые свойства

- Iteration/input/model/version/dimension binding; ordinary failed current embedding not reused.
- Typed candidate confidence and resource/heuristic stop remain distinct from science.
- Signed gain around zero; explicit min/max unit and abs/rel tolerance.
- Missing/nonfinite rows not silently turned into a converged series.
- Защищённые различения: релевантные candidate/authority, input/result, historical/current различия из отчёта. S08: новую совместимую конфигурацию проверять на том же механизме, а не ветке по ID кейса.

## 2. Полнота исходных обязательств и остатков

| Основание | REQ | Disposition / решение |
|---|---|---|
| audit-residual:C17_остатки:0 | REQ-STP-01-01 | fix: Validate/stage before embedding commit. |
| audit-residual:C17_остатки:1 | REQ-STP-01-02 | fix: No inf<=inf stop. |
| audit-residual:C17_остатки:2 | REQ-STP-01-03 | fix: Range/status contract. |
| audit-residual:C17_остатки:3 | REQ-STP-01-02 | lifecycle: Whole-history invariant сохранён; новый window толькоявно. |
| audit-residual:C17_остатки:4 | REQ-STP-01-04 | qualify: Native actual producer/consumer. |
| B41 | REQ-STP-01-01, REQ-STP-01-03, REQ-STP-01-04 | fix: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| B122 | REQ-STP-01-02, REQ-STP-01-04 | fix: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| remaining:0101 | REQ-STP-01-01 | fix: Rejected observation atomicity. |
| remaining:0102 | REQ-STP-01-03, REQ-STP-01-04 | qualify: Actual caller/readback и finite cosine. |
| remaining:0203 | REQ-STP-01-02 | fix: Stable derived arithmetic. |
| remaining:0204 | REQ-STP-01-02, REQ-STP-01-04 | qualify: Actual normalization/consumer; явная whole-history policy. |

## 3. Нормативные REQ и конкретное решение

### REQ-STP-01-01 — fix
Rejected numeric observation не должно оставлять embedding с будущим accepted iteration; metric/embedding принимаются атомарно.

**Решение на существующих владельцах.** В check_with_text валидировать metric до дорогого embed-вызова/мутации либо staging всей _EmbeddingRecord с commit только после успеха _do_check. Сохранить номер/input SHA/model/version/dimension и freshness пару; failed embed не старый current. Не очищать всю историю/не отключать recovery.
**Приёмка:** TEST-STP-01-01.

### REQ-STP-01-02 — fix
Plateau comparison для принятых finite inputs/tolerances должен оставаться арифметически определённым и согласованным с объявленной scale/direction, либо возвращать exact unavailable, не ложный stop.

**Решение на существующих владельцах.** У ImprovementPlateau использовать устойчиво отмасштабированное compare gain/threshold или проверенный bounded арифметический helper; detect intermediate overflow до inf<=inf. Не clip/не 0/не менять tol. Сохранить signed gain и PlateauToleranceProfile units/minmax. Непригодное baseline окно остаётся unknown; новый recovery window только через явный scope/epoch contract.
**Приёмка:** TEST-STP-01-02.

### REQ-STP-01-03 — fix
Cosine для поддержанного finite vector диапазона должен иметь finite bounded diagnostic либо явный unavailable, не NaN переписанныйв JSONnull безпричины.

**Решение на существующих владельцах.** У existing cosine helper нормализовать вектор через scale-safe norm/максимальный модуль до dot, validate zero/dimension/finite; ограничить roundoff только обоснованным [-1,1] range, не clip реальную ошибку. Raw diagnostic/status сериализуется честно. Actual encoder profile определяет supported range, не утверждать все векторы испорчены.
**Приёмка:** TEST-STP-01-03.

### REQ-STP-01-04 — qualify
Реальный consumer должен сохранять current-observation identity и различать heuristic/resource/scientific outcomes; text-path reachability устанавливается конечным caller census.

**Решение на существующих владельцах.** Использовать MultiPassLLMDrafter.check_candidate_observation с subject/request/response bytes/event/pass/model version, не подменять его check_with_text. Existing test_convergence_c49/test_stopping_c49 + test_plateau_lifecycle_c49 actual source objective; finite census text callers. DraftResult/finalization/readback сохраняют stop kind/limitations и invalid config не провоцирует лишний LLM call.
**Приёмка:** TEST-STP-01-04.

## 4. Локальные различающие тесты

Все номера TEST ниже — проектируемые проверки, не вымышленные имена существующих pytest-функций. Существующие файлы использовать/расширить; старый mutation или контролируемое удаление проверяемого механизма должен давать отличающийся исход.

### TEST-STP-01-01 · NOT_RUN
- **Setup:** Actual ConvergenceDetector/Pydantic; accepted10/text1→NaN/text2→20/None; inf и encoder failure, MULTI_SIGNAL semantic-only.
- **Действие:** Запустить sequence, inspect internal accepted records и serialized ConvergenceState; затем два настоящих current vectors.
- **Oracle:** Rejected call не меняет accepted basis; следующий missing не heuristic stop; два valid compatible current vectors дают ограниченную stability.
- **Positive / negative / boundary:** Scientific_convergedFalse; ordinarymissing без reject тоже не reuse старой пары.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-STP-01-02 · NOT_RUN
- **Setup:** Истории[0,1,1],[0,-1,-1],[-1,-2,-2], [1,-1,-1] и ×1e308,rel_tol1.8; maximize зеркало; Decimal.from_float independent oracle.
- **Действие:** Пройти actual stop/lifecycle/profile и readback; scale abs_tol соответственно.
- **Oracle:** Нормальные знаки сохраняются; extreme continue как oracle либоявный arithmetic unknown,никогда false plateau; resource limit может отдельно остановить.
- **Positive / negative / boundary:** None/NaN висториине фильтруются задним числом; не увеличивать patience ради bug.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-STP-01-03 · NOT_RUN
- **Setup:** Parallel[1e200,0]→cos1, ordinary orthogonal→0,zero/nonfinite/mismatch; actual configured encoder positive отдельно.
- **Действие:** Helper→typedstate→JSON→consumer.
- **Oracle:** Finite parallel дает 1 или declared unsupported range с reason,не NaN; zero/malformed не positive stop.
- **Positive / negative / boundary:** Это rangequalification, не доказанный productioncallerbug; heuristic не scientifictruth.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-STP-01-04 · NOT_RUN
- **Setup:** Actualdrafter с controlled traced LLM response и actual detector; replay/reuse/pass/modeldrift, missing current pass и budget stop; source-reconciled GDP objective units.
- **Действие:** Пройти producer→detector→finalDraftResult/реальный consumer; отдельно text caller еслиподдержан.
- **Oracle:** Positive useful draft доступен; current compatible heuristic stop ограничен, replay/stale неоснование; resource при unknown может stop без scientific converged.
- **Positive / negative / boundary:** 51isolated tests настаром runtime не native acceptance; no blanket запретэвристик илидоказательство глобальной оптимальности.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

## 5. Общее испытание, зависимости и ownership

Общие сценарии: **E02-I02-A**, [определение LANE-02](../03_Интеграция/LANE-02.md). Исполнять только затронутый маршрут; CP — координационная приёмка, не новый runtime registry и не обязательный запуск всего CI.
- STP-01 ownsdetector/plateau; CTL-01/CTL-03 owns run/cost/counters, не второй stop framework.
- SRV-03 complex resume сохраняет declared stop basis; OPT01actual objective units/source до meaningful plateau.

## 6. Порядок и совместимость

Сначала воспроизвести на pinned baseline адресный контракт/дефект; затем один writer меняет общий owner, сохраняя callers и исторические readers. Поведенческий delta и перенос/cleanup описать раздельно. Не переписывать immutable старые artifacts: новая интерпретация получает явную version/basis. Rollback не переименовывает новые результаты как старые; reader обязан либо сохранить корректное чтение, либо дать точное unsupported/version ограничение. Команды и selectors проверить в checkout перед запуском, dependency install согласовать с общим исполнителем среды.

## 7. Design alignment и полезная способность

[System Vision, §6 Capability Reality Bar и §5 Rule12](../05_Основания/Архитектура/universal-policy-design-system-vision-and-organizing-rules.md): полный producer→persisted artifact→bridge→consumer; новый совместимый ресурс проходит общий механизм. Это не запрет нового общего кода для новой семантики. [D0 B-on-A](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md), раздел «D0 — Decision: B-on-A, Shadow-First»: полезная кандидатная работа допускается без автоматического полномочия. [Stage0 §4.3 K06](../05_Основания/Архитектура/stage0-custody-kernel-ratification.md): неизвестность ограничивает затронутое действие, не всё исследование.

LLM формулирует содержательные гипотезы, этот owner проверяет действительное операционное основание остановки. Ресурсная экономия не переименовывается в научную сходимость.

## 8. Ограниченные решения

Отдельного свободного исследования не требуется: контракт, owner и различающий oracle заданы выше. Выявленный недостающий общий interface расширять только с конкретным producer/consumer и тестом, не новым параллельным framework.

## 9. Проверенные текущие пути

- [policy-engine/src/polisyos/scientist/orchestration/engine/convergence.py:354–386](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/convergence.py#L354-L386) — `def check_with_text`.
- [policy-engine/src/polisyos/scientist/orchestration/engine/convergence.py:588–620](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/orchestration/engine/convergence.py#L588-L620) — `def _current_embedding_pair`.
- [policy-engine/src/polisyos/scientist/methods/search/stopping.py:150–182](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/stopping.py#L150-L182) — `class ImprovementPlateau`.

## 10. Точная preservation-трассировка

| Inventory ID | REQ / TEST | Смысл |
|---|---|---|
| preserve:0132 | REQ-STP-01-01, REQ-STP-01-03, TEST-STP-01-01, TEST-STP-01-03 | Iteration/input/model/version/dimension binding; ordinary failed current embedding not reused. |
| preserve:0133 | REQ-STP-01-04, TEST-STP-01-04 | Typed candidate confidence and resource/heuristic stop remain distinct from science. |
| preserve:0320 | REQ-STP-01-02, TEST-STP-01-02 | Signed gain around zero; explicit min/max unit and abs/rel tolerance. |
| preserve:0321 | REQ-STP-01-02, TEST-STP-01-02 | Missing/nonfinite rows not silently turned into a converged series. |

## 11. Что предъявить и что не считать PASS

Предъявить конкретные до/после assertions и actual affected consumer, сохранённые outputs/refs, failure controls, source identity и поддержанный runtime. Наличие кода, формы receipt, этого ТЗ либо старого зелёного теста не является выполнением. Local/source-excerpt observation не native acceptance; skipped/blocked остаётся видимым. Число или candidate output не повышается автоматически в empirical/decision authority. Согласовать полезный positive, не ограничиваться запретами. Полные исходные probes находятся в отдельно доставленном phase1 ZIP; текущая подготовка не создаёт нового product execution.

[Машинная трассировка](../04_Трассировка/STP-01.json). Аудит охватил 127/127; это не означает выполненных 127 ремонтов.

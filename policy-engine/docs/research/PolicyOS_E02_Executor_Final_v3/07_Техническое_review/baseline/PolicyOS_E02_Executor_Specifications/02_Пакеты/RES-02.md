# RES-02 — Единый завершённый frontier и атомарный tier checkpoint

## 1. Паспорт и результат

**LANE-06 · CP2 · основание 20d9009be21097bfbdc38a546a15cc60213b8ace · статус: ТЗ, не выполнено.** Технический исполнитель и reviewer назначаются проектом. Исходные ID: B72, B73. Тип: preserve/qualify + correction existing test ABI.

Сохранённые state, frontier и head выражают одно принятое решение tier; skip не становится выполненным расчётом, rollback не уничтожает already-produced artifact.

Основания: [аудит](../05_Основания/Аудит/02_Пакеты/RES-02.md), [все остатки](../05_Основания/Аудит/01_Реестры/C66_остатки.json), [неизменная исходная карточка](../05_Основания/Аудит/05_Источники/RES-02_исходные_строки.txt), исходный объединённый план §RES-02 (исторические строки 7786–7884).

## 2. Уже работает — сохранить

- Ok-only completed_set независимо от ширины.
- Commit/rollback до одной atomic tier publication.
- Compensation frontier содержит только prior accepted aliases.
- Output existence отдельно от selected state/authority; native status contract у checkpoints.

Изменение продукта требуется только при воспроизведённом несоответствии ниже; отсутствие native проверки само по себе не дефект. Не создавать искусственный рефакторинг для отчёта.

## 3. Полнота обязательств и disposition

| Основание | Решение | Требования |
|---|---|---|
| C66-G01 | qualify: Atomic payload доказан ограниченно, требуется actual durable crash/reopen и outputs. | REQ-RES-02-01, REQ-RES-02-02, REQ-RES-02-03 |
| C66-G02 | fix: Existing persistence test fixtures обновить по selected-profile ABI, не удалять product checks. | REQ-RES-02-04 |

### Исходные обязанности, не только новые R

- B72 → REQ-RES-02-01: single/parallel metamorphic skip/ok/fail и реальный dependent consumer.
- B73 → REQ-RES-02-02/-03: crash first publication, no double increment, согласованные return/head/compensation и сохранённые output bytes.

## 4. Нормативный контракт

### REQ-RES-02-01
Добавление независимого соседа не меняет skip на successful completed. Только native ok включается в frontier; fail/skip не удостоверяют произведённый required output. Dependent node использует настоящий skip-blocker/output contract, не простое not-fail.

Источник: B72; аудит: C66-G01; проверки: TEST-RES-02-01.

### REQ-RES-02-02
Для A/B accepted tier первая доступная durable publication содержит одновременно merged state, всех accepted aliases и соответствующие cache refs. Crash после неё не вызывает второй increment B. Fail_fast rollback не публикует новый successful tier; continue фиксирует только successes. Returned state/head/compensation соответствуют этому решению.

Источник: B73; аудит: C66-G01; проверки: TEST-RES-02-02.

### REQ-RES-02-03
Record/output refs успешного вычисления остаются читаемыми после rollback state, но не включаются автоматически в selected outputs/authority. Status-blind historical completed metadata отказывается как неустановленная; node-only hook допустим serial, parallel отказывает до producer.

Источник: B72, B73; аудит: C66-G01; проверки: TEST-RES-02-03.

### REQ-RES-02-04
Все existing remediation persistence helpers соответствуют current return_selected_profile argument и result shape, сохраняя selected-profile checks; native bodies выполняются без обхода ownership или замены skip на ok.

Источник: B72, B73; аудит: C66-G02; проверки: TEST-RES-02-04.

## 5. Техническое решение и producer → consumer

Основной код _execute_tiers и CASCheckpointHook.on_tier_complete уже ставит правильную границу. Работа — квалифицировать её настоящими CAS/head/history и fault injection вокруг первой publication, не переписывать scheduler. В existing test_res_02 helpers принять current keyword и вернуть exact shape, аналогичную штатной persistence API; explicit fixture only для local scheduling, native test использует реальный owner. Дополнить единый E02-I06-B fault matrix: до write, после blobs до head, после head. Reader допускает либо старый согласованный frontier, либо новый целый; never half-tier.

### Проверенные owners на срезе
- policy-engine/src/polisyos/scientist/orchestration/engine/async_executor.py: _execute_tiers, _run_parallel_tier, _handle_tier_checkpoint
- policy-engine/src/polisyos/scientist/orchestration/engine/checkpoint.py: CASCheckpointHook.on_tier_complete, completed_node_status_contract
- policy-engine/tests/unit/remediation/test_res_02.py: persistence helpers

Перестановка append и per-node checkpoint общего final state неверны. Новый status vocabulary или обязательный checkpoint для всех workflows не требуются.

## 6. Локальная приёмка — все будущие проверки NOT_RUN

### TEST-RES-02-01
- Уровень: unit + targeted native integration.
- Setup: Один typed skip→optional consumer; добавить independent ok; controls native ok/fail.
- Действие: Run widths1/2 и resume.
- Точный oracle: Skip ни в одном completed/head; ok в обоих; fail не включён. Реальный required-output consumer blocked если output отсутствует, optional продолжает по объявленному контракту.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-RES-02-02
- Уровень: native process persistence.
- Setup: A writes a; B increments n0→1; реальные tmp CAS/head/history; stop barriers.
- Действие: Kill own process после первой publication и reopen; prior+left-ok/right-fail под обеими policies.
- Точный oracle: First head state n1/frontier[a,b]; resume n1 не2. Fail-fast state/head prior-only и compensation completed_before=[prior]; continue prior+left; no half-tier.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-RES-02-03
- Уровень: unit + targeted native integration.
- Setup: Real output bytes left до rollback; selected finalizer; historical unestablished status; hooks serial/parallel.
- Действие: Read fresh outputs и final selected results; attempt resume/hook admission.
- Точный oracle: Left bytes exact-readable, selected list не повышена; status-unestablished typed refusal; parallel node-only hook calls producer0, serial hook/no-hook positive сохранены.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-RES-02-04
- Уровень: unit + targeted native integration.
- Setup: Existing test_res_02 current fixture ABI и supported native runner.
- Действие: Run all current local bodies и actual selected-owner integration.
- Точный oracle: Нет fixture TypeError; ownership profile сохраняется; полные semantics tests не ослаблены для green.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

Повторно использовать/расширить реальные места, а не создавать 127 harness: `policy-engine/tests/unit/remediation/test_res_02.py`; `policy-engine/tests/unit/scientist/orchestration/engine/test_checkpoint.py`. До выбора selector прочитать полный test/fixture. Это проверенные пути, не утверждение о наличии всех предложенных assertions.

Допустимые doubles: events и controlled producer failure; unit persistence fixture только ABI. Запрещено: fake CAS/head/GC при durability claim; no selected-profile keyword removal.

## 7. Общая интеграция и порядок

RES-02 canonical owner successful-frontier/atomic-tier contract; EXE-02 не обходит его hooks. RES-01 использует тот же checkpoint для two-stop resume; CAS-01 отвечает bytes/manifest publication.

Точные общие сценарии: E02-I06-B из [контракта интеграции](../03_Интеграция/LANE-06.md); одно свидетельство переиспользуется по неизменным input/backend bindings. Зависимости: STA-01; исходный DAG — ориентир, работающий контракт может удовлетворять ребру без нового ремонта. Общие файлы из §5 интегрировать последовательно с затронутыми owners; lane не новый runtime-реестр и не требование полного CI после каждого пакета.

## 8. Совместимость, история, rollback

Исторический state-only completed set не маркировать native_node_outcome_v1 задним числом. Node-only hooks сохраняются serial. Rollback code не удаляет output blobs или history; при unsafe historical frontier только scoped refusal/recompute.

## 9. Free-grow и design direction

- policy-design-custody-time-model.md §2–5: snapshot фиксация и существование артефакта разные temporal facts.
- design_direction.md §2.6, §4.7–8: независимый useful result переживает локальный отказ; publication не повышает authority.

Архитектурные источники: [policyos-identity-and-custody-boundary.md §1, §3–6](../05_Основания/Архитектура/policyos-identity-and-custody-boundary.md); [policy-design-custody-time-model.md §2–5](../05_Основания/Архитектура/policy-design-custody-time-model.md). История и текущая пригодность раздельны; физическая раскладка не догма.

Полные исторические probes/commands/logs остаются в отдельно доставленном phase1 ZIP; ссылки внутри копий аудита на `04_Проверки` относятся к нему, не к новым исполненным проверкам этого комплекта.

## 10. Нерешённые решения и передача

Новых блокирующих продуктовых решений не требуется. Реальную доступность supported runtime установить до native проверки; недоступность оформлять NOT_RUN, не PASS.

Предъявить patch/base SHA (либо обоснованный no-code результат), актуальную карту callers, REQ→TEST→evidence, фактические команды/логи, различающий контроль и сохранённые инварианты. Поддержанный native профиль: P-CORE (Python >=3.14,<3.15 и project lock); для процессов P-PROCESS, для поставки P-PACKAGING. Не устанавливать зависимости без отдельного разрешения. Fixture/source-only, исторические PASS и отсутствие ошибки при импорте не закрывают свежий producer→persistence→fresh-reader. Успешная сериализация/конверсия/подпись не доказывает научной истины или полномочия policy result. Никакое требование/тест этой карточки ещё не исполнены.


# CMP-02 — Однозначные slots и ordering по occurrence

## 1. Паспорт и результат

**LANE-04 · CP-1 · основание 20d9009be21097bfbdc38a546a15cc60213b8ace · статус: ТЗ, не выполнено.** Технический исполнитель и reviewer назначаются проектом. Исходные ID: B45, B46. Тип: квалификация исправленных guards и сохранение ограниченного WARN.

Подтвердить однозначный STRICT/explicit-merge путь и честный WARN candidate через реальные compiler, executors и checkpoint; occurrence ordering не теряет раннее нарушение повторного FQN.

Основания: [аудит](../05_Основания/Аудит/02_Пакеты/CMP-02.md), [все остатки](../05_Основания/Аудит/01_Реестры/C43_остатки.json), [неизменная исходная карточка](../05_Основания/Аудит/05_Источники/CMP-02_исходные_строки.txt), исходный объединённый план §CMP-02 (исторические строки 5325–5427).

## 2. Уже работает — сохранить

- Единый SlotLinker.validate_chain проверяет concrete source/target node IDs и duplicate target slot на границе composer.
- Explicit merge получает отдельные left/right slots и даёт UUID-invariant результат60; roots продолжают получать внешние inputs.
- WARN сохраняет collision diagnostics и validation_context в исполнении, результате и checkpoint; OFF не стирает slot collision warning.
- Checkpoint связывает effective request, prefix, history и validation context; fresh readback с живой chain сохраняет ограничения.
- Ordering диагностика содержит конкретные node_id/index; ранний prerequisite достаточен и поздний повтор его не отменяет; STRICT/WARN различаются severity.

Изменение продукта требуется только при воспроизведённом несоответствии ниже; отсутствие native проверки само по себе не дефект. Не создавать искусственный рефакторинг для отчёта.

## 3. Полнота обязательств и disposition

| Основание | Решение | Требования |
|---|---|---|
| C43-G01 | qualify: Bounded actual-body observations не заменяют native registry/dispatcher/checkpoint на P-CORE. | REQ-CMP-02-01, REQ-CMP-02-02, REQ-CMP-02-03 |
| C43-G02 | qualify: WARN намеренно допускает ограниченный кандидат; проверить сохранение limitation в downstream, не объявлять сам tolerant profile дефектом. | REQ-CMP-02-02 |
| C43-G03 | qualify: Occurrence checker сохраняется; clean tag-rule report не доказывает методологическую состоятельность. | REQ-CMP-02-03 |

### Исходные обязанности, не только новые R

- B45: duplicate producers в один concrete input — STRICT reject; для детерминированного объединения explicit merge, не last-write-wins. WARN допустим только как явно ограниченный кандидат (REQ01–02).
- B46: prerequisite ordering по occurrence, а не последнему FQN; исходные эвристические tags не расширяются до универсального научного закона (REQ03).

## 4. Нормативный контракт

### REQ-CMP-02-01
На реальном MethodComposer→SlotLinker→sequential/async STRICT (либо linker allow_partial_links=False) отвергает повторное подключение одного concrete target slot до dispatch; ошибочные endpoints также отвергаются. Explicit merge с раздельными left/right принимает оба источника и возвращает один результат60 при перестановке UUID. Корневые external inputs и повторные FQN разных occurrences не объявляются collision.

Источник: B45, B46; аудит: C43-G01; проверки: TEST-CMP-02-01.

### REQ-CMP-02-02
WARN candidate сохраняет исходные collision warnings и compiler-owned validation_context до result и checkpoint fresh reader; потребитель, требующий однозначности, выбирает STRICT либо explicit merge, не трактует WARN как доказанное объединение. Исходно допустимые WARN результаты20/10 при UUID-порядке остаются явно ограниченными. Stripped/altered diagnostics, mode, effective request или incomplete prefix/history вызывают существующий отказ checkpoint/reconciliation до нового dispatch. Same request с полным checkpoint восстанавливает3 node results и выполняет0 новых dispatch.

Источник: B45, B46; аудит: C43-G01, C43-G02; проверки: TEST-CMP-02-02.

### REQ-CMP-02-03
SemanticValidator проверяет каждый dependent occurrence: наличие хотя бы одного prerequisite строго раньше данного index; self-tag не удовлетворяет себе, поздний prerequisite не исправляет раннее нарушение. Issues сохраняют node UUID/index и severity выбранного режима. Неизвестные/нейтральные tags могут дать чистый report, но не scientific attestation; установленные зависимости задаются existing signature/explicit edges.

Источник: B45, B46; аудит: C43-G01, C43-G03; проверки: TEST-CMP-02-03.

## 5. Техническое решение и producer → consumer

Сохранить SlotLinker.validate_chain единственным предикатом concrete bindings, который вызывает MethodComposer.validate; не делать независимые checker копии в executors. Проверить native путь signatures→validated compiled chain→dispatcher. Для неоднозначных источников positive deterministic route — существующий explicit merge node, не принудительная глобальная сериализация. В WARN не менять арифметику без отдельного решения: обеспечить неизменную передачу warnings/context и уже существующий reconcile_validation_context. CheckpointingExecutor использует _validation_context_payload и _compute_execution_digest перед восстановлением; читать JSON свежим объектом, а не проверять тот же in-memory payload. SemanticValidator._check_ordering_rules сохраняет ordered(node_id,FQN,tags) и сравнение any(prereq_index < dependent_index); family/variant/data_modalities остаются source-defined эвристикой. Если downstream теряет limitation, исправить конкретный projection/caller, не запрещать весь кандидатный contour.

### Проверенные owners на срезе
- policy-engine/src/polisyos/foundry/methods/components/composer.py: MethodComposer.validate, reconcile_validation_context
- policy-engine/src/polisyos/foundry/methods/components/linker.py: SlotLinker.validate_chain
- policy-engine/src/polisyos/foundry/methods/components/semantic_validator.py: SemanticValidator._check_ordering_rules
- policy-engine/src/polisyos/foundry/methods/backends/checkpointing.py: CheckpointingExecutor, _validation_context_payload

Не вводить новый semantic framework и не объявлять WARN silent defect: диагностика уже наблюдаема. Native qualification может завершиться no-code при сохранении всех oracles.

## 6. Локальная приёмка — все будущие проверки NOT_RUN

### TEST-CMP-02-01
- Уровень: native compiler + executors.
- Setup: Native signatures/registry: A→10, B→20; direct both→same target slot; separate merge(left,right)→sum→times2; fixed UUID swaps и repeated-FQN independent targets.
- Действие: Build+execute STRICT и partial-disabled; execute explicit merge sequential/async; mutate endpoint node IDs.
- Точный oracle: Collision/endpoint cases fail before dispatcher count increases; merge60 for both UUID assignments/backend; valid repeated occurrences and root external input succeed.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-CMP-02-02
- Уровень: native persistence + fresh consumer.
- Setup: Same two producers into one WARN slot, two UUID assignments; real checkpoint JSON/sidecar lifecycle, supplied same live chain, fresh reader and dispatch counter.
- Действие: Execute WARN, save/read/resume; strip warnings, alter mode/context/input/seed/prefix/history one at a time; inspect actual downstream result consumer role.
- Точный oracle: Baseline limited20/10 retains warning/mode; complete checkpoint returns3 prior node results,0 dispatch; each altered binding refuses before dispatch. Consumer requiring deterministic merge uses strict/explicit merge; no new authority registry. Checkpoint test is not standalone recipe reconstruction (CMP-01).
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-CMP-02-03
- Уровень: unit + targeted native integration.
- Setup: Real SemanticValidator with signatures tagged estimate/sensitivity: estimate1→sensitivity→estimate2; sensitivity1→estimate→sensitivity2; sensitivity1→sensitivity2→estimate; self both-tags; neutral tags.
- Действие: Validate STRICT and WARN; repeat dependent FQN with distinct UUIDs; inspect full issues.
- Точный oracle: First chain no ordering issue; second only index0; third indices0,1; self at0 fails; UUID/index exact; STRICT error versus WARN warning. Neutral clean report is recorded only as heuristic result, not empirical validity.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

Повторно использовать/расширить реальные места, а не создавать 127 harness: `policy-engine/tests/unit/remediation/test_cmp_02.py`. До выбора selector прочитать полный test/fixture. Это проверенные пути, не утверждение о наличии всех предложенных assertions.

Допустимые doubles: малые deterministic methods и observers dispatch; isolated I/O failure injection. Запрещено: stub registry/dispatcher/checkpoint serializer вместо native маршрута; scientific validity из arithmetic fixture.

## 7. Общая интеграция и порядок

Общий compile/merge witness переиспользовать с CMP-01/03; checkpoint binding и lifecycle — с RES-04. Здесь сохраняется diagnostic provenance, не новая standalone artifact capability.

Точные общие сценарии: E02-I04-A, E02-I04-B из [контракта интеграции](../03_Интеграция/LANE-04.md); одно свидетельство переиспользуется по неизменным input/backend bindings. Зависимости: CMP-01; исходный DAG — ориентир, работающий контракт может удовлетворять ребру без нового ремонта. Общие файлы из §5 интегрировать последовательно с затронутыми owners; lane не новый runtime-реестр и не требование полного CI после каждого пакета.

## 8. Совместимость, история, rollback

WARN/OFF остаются рабочими ограниченными профилями; STRICT остаётся отказом на collision. Legacy checkpoint без execution/context binding не повышать до безопасного resume. UUID invariant требовать для explicit merge, не обещать его для старого ограниченного WARN.

## 9. Free-grow и design direction

- Полезный conditional candidate допускается при сохранении ограничений; authoritative/однозначный потребитель не должен забывать их.
- Occurrence identity и custody diagnostics связаны с результатом; эвристическая проверка не подменяет эмпирическое основание.

Архитектурные источники: [policyos-identity-and-custody-boundary.md §1, §3–6](../05_Основания/Архитектура/policyos-identity-and-custody-boundary.md); [policy-design-custody-time-model.md §2–5](../05_Основания/Архитектура/policy-design-custody-time-model.md). Историческая подлинность и текущая пригодность раздельны; физический layout design-docs не догма.

## 10. Нерешённые решения и передача

Новых блокирующих продуктовых решений не требуется. Реальную доступность supported runtime установить до native проверки; недоступность оформлять NOT_RUN, не PASS.

Предъявить patch/base SHA (либо обоснованный no-code результат), актуальную карту callers, REQ→TEST→evidence, фактические команды/логи, различающий контроль и сохранённые инварианты. Поддержанный native профиль: P-CORE (Python >=3.14,<3.15 и project lock); для native численных/JIT/train проверок P-JAX (тот же lock, JAX/jaxlib/optax, deterministic tiny CPU); для процессов P-PROCESS, для поставки P-PACKAGING. Не устанавливать зависимости без отдельного разрешения. Fixture/source-only, исторические PASS и отсутствие ошибки при импорте не закрывают свежий producer→persistence→fresh-reader. Успешная сериализация/конверсия/подпись не доказывает научной истины или полномочия policy result. Никакое требование/тест этой карточки ещё не исполнены.


Полные probes исходного аудита доставлены отдельно в phase1 ZIP; ссылки аудита на них не означают включение тяжёлой evidence в этот исполнительский комплект.

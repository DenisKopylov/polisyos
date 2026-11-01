# CMP-01 — Импорт, effective DAG и единый payload исполнителей

## 1. Паспорт и результат

**LANE-04 · CP1 · основание 20d9009be21097bfbdc38a546a15cc60213b8ace · статус: ТЗ, не выполнено.** Технический исполнитель и reviewer назначаются проектом. Исходные ID: B42, B43, B44. Тип: native activation + persisted effective-plan capability qualification.

Довести действующий build/freeze/payload repair до native execution и fresh persisted reconstruction; preserve sequential и не изобретать второй executor.

Основания: [аудит](../05_Основания/Аудит/02_Пакеты/CMP-01.md), [все остатки](../05_Основания/Аудит/01_Реестры/C42_остатки.json), [неизменная исходная карточка](../05_Основания/Аудит/05_Источники/CMP-01_исходные_строки.txt), исходный объединённый план §CMP-01 (исторические строки 5200–5324).

## 2. Уже работает — сохранить

- MethodComposer единственный effective DAG owner; ordering-only requires не data-flow; sibling остаётся parallel.
- Sequential/async используют общий static→dynamic→override payload и separate seed dispatcher argument.
- Local deferred async imports, honest internal failure и отсутствие permanent unavailable latch.
- Current validation replay gate и ChainArtifact method refs/recipe остаются; recipe не объявляется executable plan автоматически.

## 3. Полнота обязательств и disposition

| Основание | Решение | Требования |
|---|---|---|
| C42-G01 | qualify: Native imports и actual composer/dispatcher/runner вместо registry/materializer fixtures. | REQ-CMP-01-01, REQ-CMP-01-03 |
| C42-G02 | capability: Найти и исполнить существующий persisted recipe→fresh compiler путь; если полного восстановления нет, узко дополнить существующий artifact/compiler owner, не только запустить старый тест. | REQ-CMP-01-02 |
| C42-G03 | qualify: Ray/fused JAX/heterogeneous profiles аттестуются отдельно по реальному activation; equivalent copied merge не defect сам по себе. | REQ-CMP-01-03 |

### Исходные обязанности, не только новые R

- B42: оба fresh import order, actual wrapper и правильная internal import diagnostic; missing optional backend не blanket unavailable.
- B43: build→freeze→execute и persisted current owner восстановление требует requires adjacency/occurrences/mode/levels; цикл/edge removal отказ до dispatch.
- B44: authored static values без повторного override достигают consumer; unknown parameter отказан. Optional backend qualification не блокирует исправный sequential профиль.

## 4. Нормативный контракт

### REQ-CMP-01-01
Fresh P-CORE процессы с двумя import order получают рабочий async wrapper и actual built chain. B.requires(A) без data-flow создаёт levels[A,C]→[B] с независимым C; cycle и missing requirement STRICT отказаны до dispatch. Internal import failure сохраняет причину, следующий вызов после устранения transient failure не permanently unavailable. Running event loop получает actionable await-route error для sync wrapper.

Источник: B42, B43; аудит: C42-G01; проверки: TEST-CMP-01-01.

### REQ-CMP-01-02
Persisted ChainArtifact/method-reference route в новом процессе восстанавливает или независимо recomputes у MethodComposer occurrence identities, requires-only adjacency, authored parameters, validation mode и parallel levels перед actual execution. Выполнить bounded inventory всех producers/loaders/callers; выбрать существующий route, если он достаточен. Если recipe не содержит достаточного основания и такого route нет, добавить минимальное versioned recipe/projection или loader у существующего owner, затем replay validation; не считать один execution_order доказательством dependencies. Edge-removal/unknown-context control отказан до dispatch.

Источник: B43; аудит: C42-G02; проверки: TEST-CMP-01-02.

### REQ-CMP-01-03
Actual MethodNode static window20, dynamic scale2 и per-call scale3 дают одинаковый полный payload/results sequential/async без повторного window override; seed не превращается в undeclared user parameter. Unknown authored/runtime parameter отказан. Ray/fused JAX/heterogeneous route получает отдельный native evidence либо явный NOT_QUALIFIED, не блокируя рабочий sequential; при изменении Ray merge использовать общий builder, сохраняя precedence.

Источник: B44; аудит: C42-G01, C42-G03; проверки: TEST-CMP-01-03.

## 5. Техническое решение и producer → consumer

Существующие _requirement_edges, freeze(extra_predecessors), reconcile_validation_context и _build_node_param_payload — owners, не заменять их. G02 исследование ограничить найденным ChainArtifact.from_chain/parts persistence и их реальными loaders/callers: составить producer→fields→source method refs→fresh compiler map. Если constraints восстанавливаются из admitted method refs, использовать его и добавить тест. Если нет — versioned additive recipe содержит недостающее authored/replay основание у _chain.py и compiler reconstruction; не сериализовать лишь derived levels без основания и не доверять caller mode как performed validation. Сохранить historical recipe readable/unqualified, а не молча считать executable.

### Проверенные owners на срезе
- policy-engine/src/polisyos/foundry/methods/components/composer.py: MethodComposer._requirement_edges, CompositionDAG.freeze, reconcile_validation_context
- policy-engine/src/polisyos/foundry/methods/backends/chain_executor.py: _build_node_param_payload, _validate_compiled_execution_plan, execute_heterogeneous_chain_async
- policy-engine/src/polisyos/foundry/methods/backends/async_chain_executor.py: AsyncChainExecutor
- policy-engine/src/polisyos/foundry/methods/artifacts/_chain.py: ChainArtifact.from_chain
- policy-engine/src/polisyos/foundry/methods/artifacts/parts.py: chain artifact persistence
- policy-engine/src/polisyos/foundry/methods/backends/ray_chain_executor.py: effective-level/payload consumer

Принудительно последовательное исполнение всех узлов вместо сохранения разрешённой параллельности скрывает concurrency defect и запрещено. Сериализация node recipe как данных допустима. Новый executor/parallel registry не нужен. Recipe отсутствие explicit adjacency пока не доказанный bug всего graph; decisive fresh reconstruction test выбирает no-code либо узкое расширение.

## 6. Локальная приёмка — все будущие проверки NOT_RUN

### TEST-CMP-01-01
- Уровень: unit + targeted native integration.
- Setup: Два fresh native child imports chain-first/async-first; настоящий MethodRegistry. Начальный state={sentinel:7}; A возвращает {value:state[sentinel]+5}, B читает committed state[value] и возвращает {answer:state[value]*3}; C пишет независимое поле. B.requires(A), input_slots пусты как в существующем native regression, явных data-flow bindings нет; shared state merge публикует value до B.
- Действие: composer.add B before A,C→build→freeze→execute modes; barrier A/C; cycles; injected internal import failure then recovery.
- Точный oracle: Answer36; A/C barrier одновременно достижим, B после A; data edges0 не стирают requires. Cycle/missingSTRICT до dispatch count0; internal cause виден, repeat succeeds, no module latch. OFF остаётся explicit limitation, не semantic approval.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-CMP-01-02
- Уровень: actual artifact producer → CAS → fresh process compiler → executor.
- Setup: Та же цепочка, real method artifacts и persisted recipe; discard in-memory chain/registry cache, заново resolve accepted refs.
- Действие: Восстановить через discovered route; сравнить adjacency/occurrence/mode/params; удалить requires edge либо изменить signature/context в отрицательной копии.
- Точный oracle: Native fresh result/levels совпадают с исходным authored plan; removed edge/ABI/context mismatch отказ до dispatcher. Если отсутствует route, acceptance только после минимальной owner extension и actual fresh consumer, не после документации missing field.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-CMP-01-03
- Уровень: unit + targeted native integration.
- Setup: Native dispatcher/runner, method с static default7, authored20 и dynamic2; optional supported profiles list.
- Действие: Run sequential/async без params_map, override scale3, затем window30/scale4; unknown override; activate supported optional route separately.
- Точный oracle: 40/60/120 по соответствующим inputs и equal payloads; отсутствие static regression контроль даёт14/21 и тест падает. Unknown refused; backend unavailable честно ограничен. Optional numeric parity не scientific method validation.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

Повторно использовать/расширить реальные места, а не создавать 127 harness: `policy-engine/tests/unit/remediation/test_cmp_01.py`. До выбора selector прочитать полный test/fixture. Это проверенные пути, не утверждение о наличии всех предложенных assertions.

Допустимые doubles: малые настоящие registered pure methods, barriers и controlled internal import fault. Запрещено: ручной frozen DAG вместо composer build, fake dispatcher/materializer в final native evidence, JSON fixture method refs вместо actual persisted chain.

## 7. Общая интеграция и порядок

CMP-02/03 расширяют тот же composer/linker plan; RES-04 checkpoint consumer использует reconciled plan. Shared chain harness один, local payload/cycle controls остаются. P-JAX/P-Ray только фактически доступные объявленные профили.

Точные общие сценарии: E02-I04-A, E02-I04-B из [контракта интеграции](../03_Интеграция/LANE-04.md); одно свидетельство переиспользуется по неизменным input/backend bindings. Зависимости: нет обязательного нового предшественника; исходный DAG — ориентир, работающий контракт может удовлетворять ребру без нового ремонта. Общие файлы из §5 интегрировать последовательно с затронутыми owners; lane не новый runtime-реестр и не требование полного CI после каждого пакета.

## 8. Совместимость, история, rollback

Рабочий sequential не зависит от завершения optional profiles. Исторический ChainArtifact остаётся recipe и не получает новую authority задним числом. Если добавляется schema, version/reader matrix и old-read-only disposition обязательны; rollback не переписывает historical CAS IDs.

## 9. Free-grow и design direction

- Persisted executable meaning должно быть воспроизводимо у текущего compiler owner; stored warning/mode не issuer authority.
- Один effective plan позволяет новым compatible methods подключаться без case-specific scheduling ветвей.

Архитектурные источники: [policyos-identity-and-custody-boundary.md §1, §3–6](../05_Основания/Архитектура/policyos-identity-and-custody-boundary.md); [policy-design-custody-time-model.md §2–5](../05_Основания/Архитектура/policy-design-custody-time-model.md). Историческая подлинность и текущая пригодность раздельны; физический layout design-docs не догма.

## 10. Нерешённые решения и передача

- G02 обязательный выход: таблица actual persisted route и PASS witness, либо минимальный versioned owner patch с тем же witness; blanket 'нужно исследовать' не приёмка.
- Optional backend список фиксируется по actual runtime/lock; отсутствующие environments остаются NOT_RUN без установки.

Предъявить patch/base SHA (либо обоснованный no-code результат), актуальную карту callers, REQ→TEST→evidence, фактические команды/логи, различающий контроль и сохранённые инварианты. Поддержанный native профиль: P-CORE (Python >=3.14,<3.15 и project lock); для native численных/JIT/train проверок P-JAX (тот же lock, JAX/jaxlib/optax, deterministic tiny CPU); для процессов P-PROCESS, для поставки P-PACKAGING. Не устанавливать зависимости без отдельного разрешения. Fixture/source-only, исторические PASS и отсутствие ошибки при импорте не закрывают свежий producer→persistence→fresh-reader. Успешная сериализация/конверсия/подпись не доказывает научной истины или полномочия policy result. Никакое требование/тест этой карточки ещё не исполнены.


Полные probes исходного аудита доставлены отдельно в phase1 ZIP; ссылки аудита на них не означают включение тяжёлой evidence в этот исполнительский комплект.

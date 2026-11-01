# FRY-01 — Foundry compile/catalog: randomization, families и прямой IR layout

## 1. Паспорт и результат

**LANE-04 · CP1 · основание 20d9009be21097bfbdc38a546a15cc60213b8ace · статус: ТЗ, не выполнено.** Технический исполнитель и reviewer назначаются проектом. Исходные ID: LA-001, LA-002, LA-037. Тип: native composition + versioned compatibility qualification.

Квалифицировать уже действующие compile/catalog/IR owners до persisted execution и IC consumer; не повторять перенос, не смешивать versioned RNG с cosmetic relocation.

Основания: [аудит](../05_Основания/Аудит/02_Пакеты/FRY-01.md), [все остатки](../05_Основания/Аудит/01_Реестры/C36_остатки.json), [неизменная исходная карточка](../05_Основания/Аудит/05_Источники/FRY-01_исходные_строки.txt), исходный объединённый план §FRY-01 (исторические строки 4397–4592).

## 2. Уже работает — сохранить

- TreasuryPlan schema1.0/kind foundry.treasury_plan, zero-seed историческая формула и stable node/stream salts.
- Historical unmarked execution остаётся отдельным путём; marked treasury_salts_v1 требует exact selected-profile lineage admission.
- Четыре family declarations/assumptions, IR certificate objects и unknown-ID refusal; runtime registry — view MethodRegistry, не второй реестр.
- Пять IR layout identities, весь текущий default registry (31 baseline slot), layout против family inventory и прямые compatibility bindings.

Изменение продукта требуется только при воспроизведённом несоответствии ниже; отсутствие native проверки само по себе не дефект. Не создавать искусственный рефакторинг для отчёта.

## 3. Полнота обязательств и disposition

| Основание | Решение | Требования |
|---|---|---|
| C36-G01 | qualify: Настоящие compiler/CAS/JAX/IC consumer и installed imports вместо manifest/fold fixtures. | REQ-FRY-01-01, REQ-FRY-01-02, REQ-FRY-01-03 |
| C36-G02 | qualify: Два versioned execution пути, seed override и historical corpus квалифицируются раздельно; новый digest допустим только при явном профиле. | REQ-FRY-01-01 |
| C36-G03 | lifecycle: Family assumptions и runtime dispatch отдельно от catalog; direct facades сохраняются до actual caller window. | REQ-FRY-01-02, REQ-FRY-01-03, REQ-FRY-01-04 |

### Исходные обязанности, не только новые R

- LA-001: перенос builder уже выполнен; current treasury_salts_v1 — отдельный intentional behavior delta, которому нельзя требовать ложной cross-version byte/draw equivalence.
- LA-002: family spec, IR certificate и executable method разные сущности. Catalog membership не доказывает IC и не ограничивает будущие families четырьмя.
- LA-037: два старых адреса теперь независимо прямые, не обязательная wrapper chain; retirement отдельно. LK03 ABIModelEntry registry не DTO duplicate; LK06 MethodRegistry view/runtime adapter не kernel.

## 4. Нормативный контракт

### REQ-FRY-01-01
Native compile→CAS→fresh execution сохраняет schema/kind/lineage TreasuryPlan и stable salts для seed0/17/−3, permutation и повторной compile в одном профиле. Marked treasury_salts_v1 reader принимает только exact program/treasury selected views, recomputed salts и seed; high-word salt/lineage/profile mismatch отказаны. Unmarked historical plan сохраняет старую execution law без принудительного treasury read. Между версиями изменение digest/draw допустимо и явно объявлено.

Источник: LA-001; аудит: C36-G01, C36-G02; проверки: TEST-FRY-01-01.

### REQ-FRY-01-02
IC consumer получает family spec у catalog owner и вызывает IR certificate implementation; positive/negative математический пример одной семьи даёт различающиеся certificate outcomes. Runtime descriptor view разрешает actual registered method и исполняет его state transition, не считает family ID executable kernel. Assumptions, parameters/modes/solver hints четырёх текущих declarations и unknown-ID refusal сохраняются; certificate применим только к проверенной постановке.

Источник: LA-002; аудит: C36-G01, C36-G03; проверки: TEST-FRY-01-02.

### REQ-FRY-01-03
Compiler использует IR layout builders и сохраняет slot_layout/treasury refs в compile report/Scientist outputs. Все текущие default slots сохраняют mapping; slot без state_path отсутствует в layout, но присутствует в family inventory, unknown prefix попадает global. Пять public objects у supported facades identity-equal IR; добавление нового совместимого slot не требует нового registry.

Источник: LA-037; аудит: C36-G01, C36-G03; проверки: TEST-FRY-01-03.

### REQ-FRY-01-04
Перед удалением treasury/design/layout aliases составить finite source/string/FQN/docs/installed consumer map и support window. Прямые фасады не удалять ради числа файлов; first-party consumers не возвращаются через obsolete hop. ABI registry/certificate owner/MethodRegistry view сохраняют свои роли; package/docs build не заявлять выполненным по source inspection.

Источник: LA-001, LA-002, LA-037; аудит: C36-G03; проверки: TEST-FRY-01-04.

## 5. Техническое решение и producer → consumer

Все три moves уже сделаны: compile.randomization builds/persists treasury; catalog.mechanism.families supplies IC; IR.kernel.slots owns layout. Patch только при воспроизведённом native mismatch. Связать найденные tests с одним actual compiler→CAS→execution witness и отдельным IC certificate/dispatch witness. For treasury use _execution_treasury existing admission and real JAX folding, не новый PRNG. Version marker/lineage — current contract, а не косметическая часть LA-001. Compatibility mapping оформляется по actual direct bindings.

### Проверенные owners на срезе
- policy-engine/src/polisyos/foundry/compile/randomization.py: build_treasury_plan, TreasuryPlan
- policy-engine/src/polisyos/foundry/compile/trinity_compiler.py: treasury/layout persistence
- policy-engine/src/polisyos/foundry/execute/_internal/graph/__init__.py: _execution_treasury
- policy-engine/src/polisyos/foundry/methods/catalog/mechanism/families.py: get_mechanism_family_spec
- policy-engine/src/polisyos/foundry/methods/catalog/mechanism/runtime_registry.py: _runtime_registry_descriptors
- policy-engine/src/polisyos/ir/kernel/slots.py: build_slot_layout, build_slot_family_manifest
- policy-engine/src/polisyos/scientist/validation/verification/ic/service.py: family certificate consumer

Не возвращать kernels в catalog, не копировать certificates в Foundry и не заводить fourth layout registry. Actual seed law compatibility дешевле квалифицировать двумя profiles, чем переписывать исторические артефакты.

## 6. Локальная приёмка — все будущие проверки NOT_RUN

### TEST-FRY-01-01
- Уровень: native compiler + local CAS + real JAX PRNG.
- Setup: Tiny valid ProgramGraph, real registered execution, fixed seeds0/17/−3; marked current and source-qualified unmarked historical plan.
- Действие: Compile twice/permuted nodes, fresh store execute; inject high-word salt/root seed/selected program mismatch, absent/duplicate randomization marker.
- Точный oracle: Within-profile canonical bytes/salts/draws reproducible; admission rejects each mismatch before random execution. Both salt words affect actual PRNG. Unmarked uses historical law, no treasury manifest read; cross-version difference labelled intentional, not failed equivalence.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-FRY-01-02
- Уровень: unit + targeted native integration.
- Setup: Actual catalog, IR certificate funcs, IC service and MethodRegistry runtime descriptors; small tax/auction inputs.
- Действие: Monotone vs nonmonotone earnings; valid vs off-grid payment residual; unknown family; actual income-tax dispatch.
- Точный oracle: Certificate certified/rejected follows actual obligations, not membership; unknown family ValueError. Descriptor dispatch changes expected state through true kernel; certificate sidecar survives fresh read. No empirical/global IC claim beyond grid/assumptions.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-FRY-01-03
- Уровень: unit + targeted native integration.
- Setup: Actual DEFAULT_SLOT_REGISTRY, added slot without state_path and unscoped slot, native compile/CompileFoundryNode.
- Действие: Build layout/family manifest; compile/persist/read refs; compare old facade identities; mutate builder after result.
- Точный oracle: Pinned31 default mappings preserved without forbidding future extension; no-path slot inventory-only; government.balance→government_balance; global fallback. Five identities exact; fresh consumer sees actual layout/ref, report retains failures honestly.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-FRY-01-04
- Уровень: native installed imports + caller lifecycle.
- Setup: Current aliases and recorded FQN/config/docs consumers; shared package baseline.
- Действие: Both old layout imports with intermediate alias poisoned in controlled process, canonical imports, docs/package validation and census.
- Точный oracle: External facade resolves IR directly; no intermediate hop dependency; no export expansion. Existing supported names remain until explicit retirement. Census boundaries and external unknowns recorded, no invented0usage.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

Повторно использовать/расширить реальные места, а не создавать 127 harness: `policy-engine/tests/unit/foundry/compile/test_treasury_execution.py`; `policy-engine/tests/unit/foundry/methods/catalog/mechanism/test_family_consumer_contract.py`. До выбора selector прочитать полный test/fixture. Это проверенные пути, не утверждение о наличии всех предложенных assertions.

Допустимые doubles: маленькие synthetic program/mathematical inputs и counters; final compiler, CAS, JAX и IC owner настоящие. Запрещено: fold observer как JAX evidence, ordinary json как Core canonical proof, fixture IR objects как native layout.

## 7. Общая интеграция и порядок

FRY compile artifacts питают actual execution chain CMP; shared CAS fresh reader повторно использует LANE-06 contract. FRY-03/ECO потребляют уже разрешённый runtime kernel, не duplicate catalog. P-JAX дополняет P-CORE: dtype/device/PRNG profile фиксируются.

Точные общие сценарии: E02-I04-A из [контракта интеграции](../03_Интеграция/LANE-04.md); одно свидетельство переиспользуется по неизменным input/backend bindings. Зависимости: нет обязательного нового предшественника; исходный DAG — ориентир, работающий контракт может удовлетворять ребру без нового ремонта. Общие файлы из §5 интегрировать последовательно с затронутыми owners; lane не новый runtime-реестр и не требование полного CI после каждого пакета.

## 8. Совместимость, история, rollback

Исторический запрет менять RNG при relocation соблюдается split: relocation equivalence отдельно, нынешнее versioned расширение отдельно. Source plan one-facade пожелание не требует удалить второй независимо direct supported address без window. Historical CAS bytes не переписывать.

## 9. Free-grow и design direction

- Identity/custody boundary требует exact persisted lineage, но не scientific authority из same bytes.
- Каталог families и registry views расширяются общими owners; design-doc физический layout не догма.

Архитектурные источники: [policyos-identity-and-custody-boundary.md §1, §3–6](../05_Основания/Архитектура/policyos-identity-and-custody-boundary.md); [policy-design-custody-time-model.md §2–5](../05_Основания/Архитектура/policy-design-custody-time-model.md). Историческая подлинность и текущая пригодность раздельны; физический layout design-docs не догма.

## 10. Нерешённые решения и передача

- Нужен source-qualified historical RNG corpus для полной declared backward support; synthetic v1 sample не весь production corpus.
- Предметная применимость IC assumptions определяется выбранной задачей отдельно от native mechanical PASS.

Предъявить patch/base SHA (либо обоснованный no-code результат), актуальную карту callers, REQ→TEST→evidence, фактические команды/логи, различающий контроль и сохранённые инварианты. Поддержанный native профиль: P-CORE (Python >=3.14,<3.15 и project lock); для native численных/JIT/train проверок P-JAX (тот же lock, JAX/jaxlib/optax, deterministic tiny CPU); для процессов P-PROCESS, для поставки P-PACKAGING. Не устанавливать зависимости без отдельного разрешения. Fixture/source-only, исторические PASS и отсутствие ошибки при импорте не закрывают свежий producer→persistence→fresh-reader. Успешная сериализация/конверсия/подпись не доказывает научной истины или полномочия policy result. Никакое требование/тест этой карточки ещё не исполнены.


Полные probes исходного аудита доставлены отдельно в phase1 ZIP; ссылки аудита на них не означают включение тяжёлой evidence в этот исполнительский комплект.

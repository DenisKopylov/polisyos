# FRY-03 — Fiscal/labor: эквивалентный перенос живых PatchMap kernels

## 1. Паспорт и результат

**LANE-04 · CP4 · основание 20d9009be21097bfbdc38a546a15cc60213b8ace · статус: ТЗ, не выполнено.** Технический исполнитель и reviewer назначаются проектом. Исходные ID: LA-003. Тип: native baseline-kernel/precision qualification.

Подтвердить настоящую spec→registry→PatchMap→merge→fresh state цепочку существующих baseline kernels и отдельно квалифицировать intentional precision изменение.

Основания: [аудит](../05_Основания/Аудит/02_Пакеты/FRY-03.md), [все остатки](../05_Основания/Аудит/01_Реестры/C37_остатки.json), [неизменная исходная карточка](../05_Основания/Аудит/05_Источники/FRY-03_исходные_строки.txt), исходный объединённый план §FRY-03 (исторические строки 4593–4710).

## 2. Уже работает — сохранить

- Canonical fiscal/labor kernels в execute/mechanisms, direct old aliases и runtime descriptor view над MethodRegistry.
- PatchMap/key ABI, active∩target masks, fiscal opposite counteraccount, employer IDs/active firm counts.
- Baseline threshold/uniform-employer law не заменяется EconomicState transition model; LK06/LK08 сохраняются.

Изменение продукта требуется только при воспроизведённом несоответствии ниже; отсутствие native проверки само по себе не дефект. Не создавать искусственный рефакторинг для отчёта.

## 3. Полнота обязательств и disposition

| Основание | Решение | Требования |
|---|---|---|
| C37-G01 | qualify: Actual JAX/eqx state, PRNG, registry, MergeEngine и spec/compiler/CAS fresh reader; NumPy/scripted RNG не final proof. | REQ-FRY-03-01, REQ-FRY-03-02 |
| C37-G02 | qualify: Historical serialized rate precision и x64/JIT/grad проверяются отдельно; не обещать восстановить Decimal изfloat32. | REQ-FRY-03-02 |
| C37-G03 | qualify: Полезный baseline сохраняется с явными scientific limits и отдельным решением signed tax base. | REQ-FRY-03-03 |

### Исходные обязанности, не только новые R

- LA-003: relocation уже выполнен; не переносить код снова и не сохранять независимую старую копию для теста.
- Equivalent address move отдельно от документированного source-rate precision delta; same alias object не независимый historical numerical oracle.
- Новый labor/tax law или authority требует explicit version/model decision, не silent clamp/upgrade baseline.

## 4. Нормативный контракт

### REQ-FRY-03-01
Native registered IncomeTax/TaxSubsidy/LaborMarketMechanism создаются через actual spec/class-path owner и дают PatchMap→MergeEngine→persisted state с сохранением input, masks/accounting/keys. Tax использует reported_income, subsidy income; fiscal key unchanged, labor возвращает третий split key, обновляет только active∩target agents и recomputes active firm counts. Zero firms и invalid eager scalar rate отказаны существующим boundary.

Источник: LA-003; аудит: C37-G01; проверки: TEST-FRY-03-01.

### REQ-FRY-03-02
В объявленных float32/x64 профилях rate precision сохраняется до receiving-income dtype с минимумом float32; JIT/grad/rebinding/pickle поддержанный путь согласован с current contract. Old alias identity сохраняется, но historical serialized float32 rate не выдаётся за исходный Decimal. Изменённые x64/reduction bytes квалифицируются как documented intended delta, не byte-neutral relocation.

Источник: LA-003; аудит: C37-G01, C37-G02; проверки: TEST-FRY-03-02.

### REQ-FRY-03-03
Выбранный consumer видит baseline law/scope: linear transfers и threshold employment/uniform firm assignment/wage×skill, а не universal calibrated market или causal/welfare proof. Negative reported-income reverse transfer сохраняется как текущая математическая law до отдельного model decision; silent clamp не допускается. Неприменимые assumptions ограничивают claim, не удаляют полезный conditional result.

Источник: LA-003; аудит: C37-G03; проверки: TEST-FRY-03-03.

## 5. Техническое решение и producer → consumer

Использовать canonical execution classes и existing create_mechanism_from_spec/runtime adapter без нового registry. Переиспользовать test_fiscal_labor_replay и test_fiscal_precision: именно full state/merge/CAS/key chain закрывает native gap. Сверить old class paths на installed profile, но historical numeric reference берётся из source-qualified artifact/formula, не того же alias object. Любое изменение traced scalar admission отдельно от relocation и с native transform oracle.

### Проверенные owners на срезе
- policy-engine/src/polisyos/foundry/execute/mechanisms/fiscal.py: compute_tax, IncomeTax.emit_patches, TaxSubsidy.emit_patches
- policy-engine/src/polisyos/foundry/execute/mechanisms/labor.py: LaborMarketMechanism.emit_patches
- policy-engine/src/polisyos/foundry/methods/catalog/mechanism/runtime_registry.py: create_mechanism_from_spec
- policy-engine/src/polisyos/foundry/methods/catalog/mechanism/runtime.py: runtime adapters
- policy-engine/src/polisyos/foundry/execute/_internal/patching/__init__.py: apply_patch_map

Plugin law не drop-in replacement. Отдельный versioned law допустим по предметной задаче, но не prerequisite этой квалификации; baseline не удаляется за простоту.

## 6. Локальная приёмка — все будущие проверки NOT_RUN

### TEST-FRY-03-01
- Уровень: native JAX + registry/compiler/CAS replay.
- Setup: Real GlobalState: reported[80,40,200,60], active[1,1,0,1], target[1,0,1,1], tax0.25; real firm state and fixed key.
- Действие: Spec→kernel→merge→fresh state; subsidy0.5 on income[100,50,25,80] target[0,1,0,1]; labor thresholds0/1, all-false target, zero firms.
- Точный oracle: Tax deltas[-20,0,0,-15],government+35; subsidy[0,25,0,40],government−65; transfer sum0. Actual keys law exact; non-target/inactive agents preserved, aggregate active firm counts recomputed (не frozen). No side mutation; zero firms отказ до RNG.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-FRY-03-02
- Уровень: unit + targeted native integration.
- Setup: Existing precision/replay tests, P-JAX dtype/device explicit; rate0.1000000001 receiving float64 income1e12; separate float32 historical serialized object.
- Действие: Eager/JIT/grad/pickle and old FQN imports; fresh persisted replay compare all state leaves/key.
- Точный oracle: x64 expected100000000100 within declared native tolerance, float32 obeys its quantization; historical lost precision не invented. Alias same identity, independent numeric oracle not alias comparison. No forced global x64 flag in product.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-FRY-03-03
- Уровень: unit + targeted native integration.
- Setup: Actual method authority metadata и selected consumer с baseline model; signed reported income; tax/labor finite inputs.
- Действие: Execute conditional baseline, inspect result description/assumptions, negative-base transfer and absent empirical evidence.
- Точный oracle: Patch result полезен и label baseline; no automatic causal/calibrated/welfare claim. Signed-base law unchanged unless separate approved version; metadata/citation не evidence substitute.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

Повторно использовать/расширить реальные места, а не создавать 127 harness: `policy-engine/tests/unit/remediation/test_fry_03.py`; `policy-engine/tests/unit/foundry/execute/mechanisms/test_fiscal_precision.py`; `policy-engine/tests/unit/foundry/execute/mechanisms/test_fiscal_labor_replay.py`. До выбора selector прочитать полный test/fixture. Это проверенные пути, не утверждение о наличии всех предложенных assertions.

Допустимые doubles: малые states и deterministic seed; fault observers в unit. Запрещено: NumPy-as-jnp/scripted RNG/recorder MergeEngine в final native path, старый alias как independent old algorithm.

## 7. Общая интеграция и порядок

FRY-01 supplies exact treasury/key law, ECO-01 сравнивает только выбранные observables двух profiles; PLG train не prerequisite baseline run. Tiny P-JAX numerical job общий для precision/consumer.

Точные общие сценарии: E02-I04-C из [контракта интеграции](../03_Интеграция/LANE-04.md); одно свидетельство переиспользуется по неизменным input/backend bindings. Зависимости: FRY-01; исходный DAG — ориентир, работающий контракт может удовлетворять ребру без нового ремонта. Общие файлы из §5 интегрировать последовательно с затронутыми owners; lane не новый runtime-реестр и не требование полного CI после каждого пакета.

## 8. Совместимость, история, rollback

Current direct aliases сохранены; historical source plan equivalent move не скрывает subsequent precision delta. Не переписывать старые serialized rates/IDs. New model/version только отдельно.

## 9. Free-grow и design direction

- Проверенный numerical result не эмпирическая пригодность; baseline можно использовать для честного conditional сценария.
- Общие registry/spec/patch consumers позволяют подключать совместимый kernel без ветки под case.

Архитектурные источники: [policyos-identity-and-custody-boundary.md §1, §3–6](../05_Основания/Архитектура/policyos-identity-and-custody-boundary.md); [policy-design-custody-time-model.md §2–5](../05_Основания/Архитектура/policy-design-custody-time-model.md). Историческая подлинность и текущая пригодность раздельны; физический layout design-docs не догма.

## 10. Нерешённые решения и передача

- При конкретном применении определить signed tax base и units/time-step; без решения conditional law явно ограничена, но native repair не блокируется.

Предъявить patch/base SHA (либо обоснованный no-code результат), актуальную карту callers, REQ→TEST→evidence, фактические команды/логи, различающий контроль и сохранённые инварианты. Поддержанный native профиль: P-CORE (Python >=3.14,<3.15 и project lock); для native численных/JIT/train проверок P-JAX (тот же lock, JAX/jaxlib/optax, deterministic tiny CPU); для процессов P-PROCESS, для поставки P-PACKAGING. Не устанавливать зависимости без отдельного разрешения. Fixture/source-only, исторические PASS и отсутствие ошибки при импорте не закрывают свежий producer→persistence→fresh-reader. Успешная сериализация/конверсия/подпись не доказывает научной истины или полномочия policy result. Никакое требование/тест этой карточки ещё не исполнены.


Полные probes исходного аудита доставлены отдельно в phase1 ZIP; ссылки аудита на них не означают включение тяжёлой evidence в этот исполнительский комплект.

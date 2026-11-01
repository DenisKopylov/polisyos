# FRY-03 — живые baseline fiscal/labor kernels у execution owner
## C37 · 31 октября 2026 года

**Исходный ID:** LA-003. **Порядок:** 37/127. **Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Только аудит.

## Решение

**Смысловой перенос выполнен: живые kernels принадлежат `execute/mechanisms`, старые файлы — прямые aliases, runtime class paths переключены.** PatchMap не заменён EconomicState, adapter не поглотил численный kernel, второй registry не создан. Простая threshold-модель не объявлена универсальным рынком труда.

**22 MATCH, 0 ERROR ограниченной диагностики; новых R-находок не установлено.** Настоящие JAX/registry/compiler/CAS/gradient tests не исполнены. Важный предел: NumPy algebra и scripted RNG проверяют control flow, но не native numerical equivalence. Полного закрытия нет.

## 1. Матрица исходной задачи

| ID | Сохранённое и подтверждённое | Остаток |
|---|---|---|
| LA-003 | Canonical execution classes; old-path identity; PatchMap ABI; actual runtime string paths; active/target masks; налог по reported income, subsidy по income; employer/count/key control flow | C37-G01: native chain; C37-G02: historical compatibility и intentional precision delta; C37-G03: baseline scientific scope |

[Полная карточка](../05_Источники/FRY-03_исходные_строки.txt), строки 4593–4710. Сохраняются LK06/LK08: registry view не дублирует MethodRegistry, DomainPlugin не равен FoundryMethodPlugin и не заменяется одним pure_step.

## 2. Владельцы и настоящий путь исполнения

Canonical fiscal/labor файлы содержат действительные `emit_patches`, а не forwarding оболочки. Старые fiscal/labor файлы напрямую импортируют эти же классы. P01 подтверждает actual object identity через точные facades в контролируемом namespace. Это полезная совместимость imports, **но не независимое сравнение старого и нового численного алгоритма**: обе стороны теперь один объект. [S01:1–149](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/execute/mechanisms/fiscal.py#L1-L149) [S02:1–95](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/execute/mechanisms/labor.py#L1-L95) [S04:1–10](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/mechanisms/fiscal.py#L1-L10) [S05:1–5](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/mechanisms/labor.py#L1-L5)

Три method descriptors указывают на `polisyos.foundry.execute.mechanisms:IncomeTax`, `TaxSubsidy`, `LaborMarketMechanism`. P20 сверяет эти литералы из actual class definitions. `runtime_registry.py` остаётся view над MethodRegistry. Историческое имя `_registry.py` отсутствует, но его роль не исчезла. [S07:163–190](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/mechanism/runtime.py#L163-L190) [S07:226–253](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/mechanism/runtime.py#L226-L253) [S07:288–319](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/mechanism/runtime.py#L288-L319) [S08:255–293](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/mechanism/runtime_registry.py#L255-L293)

Actual `create_mechanism_from_spec` выполняет coercion/validation, выбирает descriptor и загружает класс по строковому пути. P15–P17 исполняют этот путь с fixture descriptor inventory, настоящими IR ParamSpec/MechanismTypeSpec и реальными production kernel definitions; Decimal rate доходит до ожидаемого PatchMap. Native MethodRegistry/decorators не запускались. P16 unknown extra/missing rate и значения за bounds отказаны настоящим spec validator. [S08:173–199](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/mechanism/runtime_registry.py#L173-L199) [S11:110–144](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/contracts/specs.py#L110-L144)

Далее runtime adapter вызывает `init_state → emit_patches → _serialize_tree`. P18 показывает actual adapter и ordinary JSON readback двух tax slots. P19 actual `apply_patch_map` добавляет node/priority без мутации исходных patch records, но downstream MergeEngine заменён recorder. Настоящий graph consumer прочитан: он разрешает selector, создаёт kernel по spec, передаёт step key и target mask, получает PatchMap; полный state merge и persisted snapshot здесь не исполнены. [S07:113–158](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/mechanism/runtime.py#L113-L158) [S18:71–147](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/execute/_internal/patching/__init__.py#L71-L147) [S19:3869–4012](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/execute/_internal/graph/__init__.py#L3869-L4012)

## 3. Что именно сохраняется в численной ветке

P02 tax при reported income `[80,40,200,60]`, active `[1,1,0,1]`, target `[1,0,1,1]`, rate 0.25 даёт agent delta `[-20,0,0,-15]` и government `+35`. P03 subsidy использует именно income `[100,50,25,80]`, другую target mask и rate 0.5: `[0,25,0,40]`, government `−65`. Сумма противоположных transfers равна нулю, input arrays не изменены, fiscal key сохраняет identity. P04–P06 покрывают отсутствие target mask, all-false mask и invalid/nonfinite rates. [S01:15–49](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/execute/mechanisms/fiscal.py#L15-L49) [S01:76–98](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/execute/mechanisms/fiscal.py#L76-L98) [S01:128–149](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/execute/mechanisms/fiscal.py#L128-L149)

Labor P09 с threshold 1 и target `[1,0,1,1]` сохраняет untouched active incumbent и inactive agent: employer IDs `[1,0,1,0]`, расчётный income `[30,50,25,40]`, active firm counts `[2,1]`. P10 threshold 0 убирает active employment, но не меняет inactive agent. P11 фиксированные scripted draws различают threshold 0.5 и wage × skill. P12 all-false target сохраняет agents, но заново вычисляет aggregate active firm inventory; это не ошибка только потому, что firm count изменился. [S02:43–95](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/execute/mechanisms/labor.py#L43-L95)

P13 zero firms отказан до RNG; P14 неверная длина target mask отвергнута, но код не обещает сделать это до draws. Labor запрашивает split на три ключа, отдельно employment/firm draws и возвращает третий ключ. **Здесь наблюдались вызовы и scripted значения, а не настоящий JAX RNG.** P22 `init_state` сохраняет state/key для всех трёх kernels.

P21 отрицательная reported-income база даёт обратный transfer. Это существующая линейная law, не автоматически дефект: её предметное толкование надо выбрать явно. Молчаливый clamp изменил бы модель, а не завершил relocation.

## 4. Precision fix нельзя выдать за byte-neutral перенос

Текущий fiscal owner сохраняет исходную rate precision до выбора receiving income dtype с минимумом float32. P07–P08 подтверждают соответствующий путь в NumPy algebra, включая rate `0.1000000001` на income `1e12 → 100000000100`. Это **не native x64/JIT test**. [S01:24–49](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/execute/mechanisms/fiscal.py#L24-L49) [S01:63–86](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/execute/mechanisms/fiscal.py#L63-L86) [S01:116–123](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/execute/mechanisms/fiscal.py#L116-L123)

Документация прямо описывает последующее намеренное dtype/precision изменение: Python/Decimal rate при x64 больше не обязана предварительно округляться до float32; subsidy reduction и часть x64 bytes могут измениться. Старый serialized float32 rate не восстанавливает потерянный исходный Decimal простым cast. Эти границы нельзя скрыть под «equivalent move», но и нельзя объявить случайной регрессией, игнорируя заявленный новый контракт. [S21:1–58](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/docs/reference/foundry/fiscal-calculation-dtype.md#L1-L58)

Найденный полный precision test проверяет native float32/float64, JIT, rebinding/pickle, gradients и lower-precision inputs. Отдельный replay test проходит spec → compiler → CAS → execution → свежий store/state reader и сравнивает все state leaves плюс key oracle. Оба прочитаны, не исполнены. [S27:1–184](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/execute/mechanisms/test_fiscal_precision.py#L1-L184) [S23:1–194](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/execute/mechanisms/test_fiscal_labor_replay.py#L1-L194)

## 5. Область содержательной применимости

Labor — threshold employment плюс равномерный firm choice и wage × skill; fiscal — ограниченные линейные transfers. Существующие method authority fields явно не удовлетворяют causal effect, assumptions, uncertainty и другим научным obligations. Citation/description не превращают patch success в эмпирическую проверку. [S07:27–45](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/mechanism/runtime.py#L27-L45) [S07:288–357](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/mechanism/runtime.py#L288-L357)

Сохранить полезные дешёвые baseline kernels и их masks/accounting. Новая labor dynamics, налоговая law или causal interpretation требуют отдельного содержательного выбора и версии, не переименования старого fingerprints. Отсутствие универсального model inventor не добавлено как дефект.

## 6. Проверки и продолжение

Полные найденные tests прочитаны. Native команда на `test_fry_03.py` и replay test завершилась до collection: `No module named pytest`, exit 1. Один bounded запуск: 22 MATCH / 0 ERROR. NumPy-as-jnp, scripted RNG/segment sum, eqx base, state, descriptor/unit/typed-marker fixtures раскрыты; native package, registration, JIT/gradients и CAS не заявлены.

Следующий практический шаг — выполнить существующие native tests в поддерживаемой среде, отдельно сверить historical precision/old artifacts и предметную область выбранного baseline. Новая архитектура или удаление живого kernel не требуются.

[Диагностика](../04_Проверки/C37_FRY03/bounded_diagnostics.json) · [Команды](../04_Проверки/C37_FRY03/commands.json) · [Native границы](../04_Проверки/C37_FRY03/native_verification.json) · [Источники](../05_Источники/C37_источники.json) · [Остатки](../01_Реестры/C37_остатки.json).

**37/127 пакетов рассмотрены ограниченно; следующий — ECO-01. Полного закрытия нет.**

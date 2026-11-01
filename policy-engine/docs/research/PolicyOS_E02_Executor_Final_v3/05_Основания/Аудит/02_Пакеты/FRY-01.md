# FRY-01 — реальные владельцы randomization, families и IR layout
## C36 · 31 октября 2026 года

**Исходные IDs:** LA-001, LA-002, LA-037. **Порядок:** 36/127. **Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Только аудит.

## Решение

**Все три адресных ремонта содержательно присутствуют.** Treasury builder принадлежит `compile/randomization`; четыре декларации семейств — существующему catalog; shared certificates остаются в IR. Compiler использует IR layout, а старые адреса больше не образуют обязательную цепочку двух wrappers.

**24 MATCH, 0 ERROR. Новая конкретная R-находка не установлена.** Сохранены ограничения native chain, совместимости versioned RNG и предметной применимости сертификатов. Нельзя ни объявить пакет полностью закрытым, ни потребовать удалить полезные прямые facades только ради числа файлов.

## 1. Матрица исходных задач

| ID | Подтверждённый ремонт и полезное поведение | Остаток |
|---|---|---|
| LA-001 | Compile owner; прежняя seed-dependent builder law; schema/kind сохранены; compiler и execution reader найдены | C36-G01, G02: native CAS/JAX и отдельно квалифицировать намеренный versioned RNG delta |
| LA-002 | Четыре семейства у catalog owner; IC caller переключён; certificates IR-owned; runtime registry остаётся view | C36-G01, G03: native IC/runtime и область действия assumptions |
| LA-037 | Compiler читает IR; оба оставшихся адреса напрямую связывают actual IR objects; полные layout/default builders исполнены | C36-G01, G03: native compiler/imports/distribution и lifecycle поддерживаемых адресов |

[Полная исходная карточка](../05_Источники/FRY-01_исходные_строки.txt), строки 4397–4592. Защиты LK03/LK06 сохранены: ABI registry не объявлен дубликатом DTO, MethodRegistry view не заменяется новым реестром, runtime adapter не смешивается с kernel.

## 2. Randomization: перенос и versioned изменение — разные вещи

Канонический builder сохраняет `TreasuryPlan`, schema `1.0`, kind `foundry.treasury_plan` и стабильные node/stream salts; старый treasury файл — явный прямой facade. P01–P03 сравнивают actual output с отдельной SHA256 label формулой для seed 0, 17 и −3. При нуле сохраняется исторический label без seed prefix. P04 перестановка nodes и повтор дают одинаковый payload и контрольный обычный sorted JSON. P05 независимый literal v1 читается actual DTO; P06 подтверждает identity трёх old-path exports. [S01:1–61](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/compile/randomization.py#L1-L61) [S02:1–11](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/mechanisms/treasury.py#L1-L11)

Это **не проверка настоящих Core canonical bytes**: используемый контрольный JSON serializer раскрыт. Полная native повторная компиляция/CAS не запускалась.

В текущем compiler присутствует дополнительное намеренное поведение: выбранный seed используется при создании treasury, exec plan помечается `randomization:treasury_salts_v1`, treasury сохраняется и включается в lineage. Это больше косметического move. Execution reader проверяет выбранные profiles, program/treasury lineage и заново вычисленные salts; новые node streams зависят от обоих 32-bit слов stream и node salts. [S16:345–490](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/compile/trinity_compiler.py#L345-L490) [S17:193–266](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/execute/_internal/graph/__init__.py#L193-L266) [S17:2698–2704](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/execute/_internal/graph/__init__.py#L2698-L2704)

P18 исполняет настоящий admission с fixture manifests/load_model: прочитаны selected exec/program/treasury profiles. P19–P21 отвергают неизвестный/повторный profile, пропущенный treasury edge, лишний node, изменение high-word salt, неверный root seed и иной selected program profile. P22 непомеченный historical plan возвращает `None` без manifest reads: он не принудительно переводится на новую law. P23 exact key function передаёт слова в порядке stream low/high, node low/high; **это observer, не настоящий JAX PRNG**.

Документация явно разделяет новую compilation и старый unmarked execution: новая compilation может менять digest и draws. Требовать общей byte-equivalence между версиями было бы ошибкой; считать это скрытой случайной регрессией по одному сравнению — тоже. Нужна native проверка обоих заявленных путей, уже представленная в найденном `test_treasury_execution.py`. [S26:1–58](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/docs/reference/foundry/randomization-profile.md#L1-L58) [S33:1–569](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/compile/test_treasury_execution.py#L1-L569)

## 3. Семейства, сертификаты и исполняемые методы не склеены

P11 проверяет все четыре IDs, параметры, assumptions, verification modes и solver hints. P12 unknown family отвергнут; P24 изменение list в catalog view не мутирует исходные tuple assumptions. P13 старый design facade сохраняет identity настоящих IR certificate functions и canonical family owner. [S03:1–98](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/mechanism/families.py#L1-L98) [S04:1–26](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/mechanisms/design.py#L1-L26)

Actual IC service импортирует family lookup через Foundry methods API, чей export mapping указывает прямо в catalog. Затем service строит certificate выбранной семьи, а не объявляет catalog membership доказательством. [S18:27–48](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/validation/verification/ic/service.py#L27-L48) [S20:638–656](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/api.py#L638-L656) [S18:1652–1761](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/validation/verification/ic/service.py#L1652-L1761)

P14 actual IR tax certificate для одной и той же семьи различает monotone earnings `[0.85,1.2,1.55]` и adversarial `[1,0.8,1.4]`: первый certified, второй rejected с failed monotonicity. P15 actual affine certificate сохраняет IR family `tax_affine`. P16 auction с payments `[0,0.5,0.5]` certified, с `[0,0.6,0.5]` rejected, payment residual около 0.1. P17 actual certificate DTO переживает обычный JSON readback. Эти небольшие математические примеры **не являются empirical authority или запуском IC service**. [S12:39–709](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/mechanism_design.py#L39-L709)

Runtime registry по-прежнему строит descriptor-view из существующего MethodRegistry и загружает соответствующие classes. Четыре family IDs не объявлены четырьмя runtime kernels. Найденный consumer test отдельно проверяет family certificate, runtime descriptor loading и реальный income-tax dispatch/state transition; здесь он прочитан, но не исполнен. [S24:255–293](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/mechanism/runtime_registry.py#L255-L293) [S34:1–275](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/methods/catalog/mechanism/test_family_consumer_contract.py#L1-L275)

## 4. Layout: настоящий IR registry, а не пять пустых объектов

P07 подтверждает identity пяти actual IR объектов у обоих старых адресов; P08 отравление промежуточного alias не влияет на внешний facade. Внешний адрес связывается со стабильной IR surface, которая направляет к единственному kernel owner. Это **два независимых compatibility адреса, не два последовательных алгоритма**. Compiler также обращается к IR. [S05:1–9](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/compiler/layout.py#L1-L9) [S06:1–17](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/layout.py#L1-L17) [S21:1620–1640](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/__init__.py#L1620-L1640) [S16:1–98](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/compile/trinity_compiler.py#L1-L98)

P09 actual builders сохраняют различие layout и family inventory: slot без `state_path` отсутствует в layout, но остаётся в inventory; prefix действительного state path определяет family, unscoped path даёт global fallback. P10 исполняет весь actual default registry: **31 slot**, включая cells/agents/firms/household_cells/global и `government.balance → government_balance`. Не использован прежний слабый вариант с пятью fixture IR objects. [S07:1–508](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/kernel/slots.py#L1-L508)

Compiler сохраняет полученный layout, а Scientist `CompileFoundryNode` записывает `slot_layout` и `treasury_plan` derived refs в отдельные artifact keys и сохраняет compile report даже при result fail. Эта цепочка прочитана до реального consumer, но native исполнением не подтверждена. [S25:295–348](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/nodes/builtins/compile/compile_foundry.py#L295-L348)

Docs признают текущие адреса compatibility/internal и требуют отдельного lifecycle решения перед удалением. Полный census внешних FQN/config/import consumers и установленного distribution не выполнен; оставшиеся прямые facades сами по себе не доказательство незавершённого смыслового переноса. [S27:1–119](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/docs/reference/foundry/state.md#L1-L119) [S28:1–89](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/compiler/README.md#L1-L89)

## 5. Проверки, сохранение и следующий шаг

Полностью прочитаны найденные randomization, treasury, layout, family, native execution и artifact-consumer tests. Native команда на трёх focused файлах остановилась **до collection**: `No module named pytest`, exit 1. Repository tests не исполнялись; dependencies не устанавливались. Один bounded probe дал 24 MATCH / 0 ERROR.

Сохранить canonical owners, прямые compatibility bindings, actual IR certificates и единственный MethodRegistry. Следующий практический шаг — выполнить уже существующие native tests в поддерживаемой среде и отдельно квалифицировать versioned RNG совместимость и выбранную предметную интерпретацию family certificate. Не нужен второй registry, новый solver «по названию каталога» или универсальный генератор моделей.

[Диагностика](../04_Проверки/C36_FRY01/bounded_diagnostics.json) · [Команды](../04_Проверки/C36_FRY01/commands.json) · [Native границы](../04_Проверки/C36_FRY01/native_verification.json) · [Источники](../05_Источники/C36_источники.json) · [Остатки](../01_Реестры/C36_остатки.json).

**36/127 пакетов рассмотрены ограниченно. Следующий — FRY-03. Полного закрытия нет.**

# PLG-01 — общая discovery-механика, сохранённый Domain ABI и граница factory errors
## C39 · 31 октября 2026 года

**Исходный ID:** LA-022. **Порядок:** 39/127. **Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Только аудит.

## Решение

**Полезная часть миграции присутствует:** domain adapter использует Core `list_entry_points`, `discovery_module_name`, `load_module_from_file`; group `polisyos.plugins`, DomainPlugin state/reward/objectives/lifecycle и отдельный runtime registry сохранены. Directory/entrypoint order и duplicate winner детерминированы.

**18 MATCH, 0 ERROR; подтверждён C39-R01:** неверный результат dev/prefix factory не изолируется как source error, а прерывает auto-registration до следующего корректного plugin. Prefix scanning пока остаётся, один проход регистрации не является topological dependency loader. Полное закрытие не заявляется.

## 1. Матрица исходной задачи

| ID | Сохранённый и подтверждённый ремонт | Остаток |
|---|---|---|
| LA-022 | Core primitives вместо самостоятельной file/entrypoint механики; Domain ABI/group; stable order, duplicate warning, lazy lifecycle; actual tiny file loading | C39-R01: factory-result isolation; G01: native installed/builtin chain; G02: prefix/dependency order; G03: несуществующий implicit Components/authority bridge |

[Полная исходная карточка](../05_Источники/PLG-01_исходные_строки.txt), строки 4893–4994. LK08 сохранён: DomainPlugin не заменяется FoundryMethodPlugin, а `polisyos.components` не равен `polisyos.plugins`.

## 2. Реальный owner → loader → registry → consumer

Adapter действительно делегирует entrypoint/file loading Core. P02 загружает два настоящих audit-owned `plugin.py` через exact Core loader, получает порядок alpha/zeta, проверяет deterministic module names и cleanup из sys.modules. P03 import exceptions двух bad files остаются видимыми в source order, а промежуточный good source продолжает работу. P12 explicit dev root не захватывает sibling root; P18 missing/non-directory roots возвращают пустой список. [S01:115–158](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/plugins/discovery.py#L115-L158) [S03:129–157](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/core/discovery/base.py#L129-L157)

P05 Core сортирует объявленные entrypoints и запрашивает именно `polisyos.plugins`; P06 legacy metadata mapping fallback сохраняет выбранную группу. P07 failed/non-class entrypoint не мешает следующему valid entrypoint. Metadata enumeration — fixture, реальные установленные distributions не сканировались. [S01:64–89](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/plugins/discovery.py#L64-L89) [S03:109–127](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/core/discovery/base.py#L109-L127)

P04 duplicate ID сохраняет первый deterministic source alpha и visible registration warning. P11 actual загруженный dev-file DomainPlugin проходит registry.get и возвращает state/reward/objectives по прежнему ABI. P01 builtin discovery использует настоящий класс EconomicsPlugin, затем registry и actual `create_initial_state`; параметры n_agents 12/max_agents 16 и выбранный seed доходят до **fixture EconomicState factory**. Это не native economic model run. [S02:196–230](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/plugins/core.py#L196-L230) [S09:60–85](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/plugins/economics/plugin.py#L60-L85)

Высокоуровневый `PolisySimulator` действительно вызывает auto_register в constructor при auto_discover=True, затем разрешает выбранный domain по registry. Поэтому registration boundary — реальный consumer path, не только утилита без callers. Native simulator здесь не запускался. [S11:55–91](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/plugins/api.py#L55-L91)

## 3. C39-R01 — malformed factory output прекращает полезную регистрацию

Directory loader ловит исключения самого импорта/factory call, но без проверки добавляет возвращённый объект в список; prefix loader делает аналогично. `auto_register_plugins` далее вызывает registry.register и ловит только ValueError. Сам registry сразу читает `plugin.metadata`. [S01:104–110](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/plugins/discovery.py#L104-L110) [S01:140–158](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/plugins/discovery.py#L140-L158) [S01:174–195](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/plugins/discovery.py#L174-L195) [S02:196–206](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/plugins/core.py#L196-L206)

**P13:** выбранный `a_bad/plugin.py` возвращает `object()`, следующий `z_good/plugin.py` — корректный DomainPlugin. Actual Core loader успешно загружает оба. Auto-registration сначала регистрирует economics, затем падает с `AttributeError: 'object' object has no attribute 'metadata'`; **later-good не зарегистрирован**. P14 prefix factory с `None` воспроизводит ту же границу. Это не missing dependency и не harness failure.

Сохранить good partial work, deterministic order и действующий registry. На существующей domain admission границе нужно отклонять malformed factory results с понятной source diagnostic и продолжать обработку корректных кандидатов. Не требуется новый scanner/registry или перенос DomainPlugin в method ABI. Это bounded startup/availability дефект; production occurrence, эксплуатация или security sandbox bypass не заявлены.

## 4. Lifecycle и оставшийся prefix путь

P09 сохраняет намеренную семантику: dependency должна быть зарегистрирована; get(dependent) вызывает только её собственный on_load, не implicit dependency hook; повторный get не повторяет load; unregister dependency при живом dependent отказан, dependent unload вызывается один раз. P10 capability/tag filters не вызывают load. P16 failed on_load не помечает plugin loaded и допускает повтор. [S02:196–245](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/plugins/core.py#L196-L245)

P15 child-before-parent source order даёт warning для child, затем регистрирует parent без повторного прохода. Это **не topological loader**. Исходный lifecycle не следует менять автоматически: либо declarations обеспечивают поддержанный порядок, либо нужное расширение планируется у существующего adapter с сохранением явных hooks.

P08 подтверждает, что эвристический prefix scan **не выведен**: отсортированные matching distributions импортируются по преобразованному имени. Он не импортирует unrelated fixture distribution, но Core delegation сама по себе не означает переход исключительно на declarations. Выводить этот путь нужно после учёта известных consumers, не удалением работающей совместимости вслепую. [S01:91–112](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/plugins/discovery.py#L91-L112)

P17 `create_simple_plugin` сохраняет state/mechanism/reward/objective wrapper и прежнюю first-key-word передачу seed. Современный typed JAX key этим probe не квалифицирован. Его расположение рядом с discovery — вопрос ownership остатка, не причина менять формулу seed или требовать новый factory framework.

## 5. Общие primitives не являются готовым bridge или научной гарантией

Core components использует свои group/kind declarations; его legacy group — `polisyos.components`, methods — `polisyos.foundry_methods`. Прочитанный bootstrap имеет явные bridges для перечисленных component domains, но не доказывает готовый drop-in DomainPlugin bridge. Существующий pyproject method entrypoint не разрешает переименовать domain group. [S08:58–97](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/core/components/discovery.py#L58-L97) [S07:73–159](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/core/components/bootstrap.py#L73-L159) [S13:283–294](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/pyproject.toml#L283-L294)

Успешная загрузка plugin означает исполнимость данного ABI, не безопасность произвольного кода, не empirical validity и не policy authority. Здесь импортировались только маленькие собственные fixtures. Научная применимость economics отдельно ограничена C38; Domain discovery не добавляет ей доказательств.

## 6. Проверки и следующий шаг

Полный `test_plg_01.py` прочитан: его устаревший test-first комментарий не принят за нынешний red/green результат. Native команда остановилась до collection: `No module named pytest`, exit 1. Один bounded probe дал 18 MATCH / 0 ERROR, включая воспроизведение R01. Реальный importlib file loader и registry исполнены; metadata/import inventory, EconomicsState/RNG и normal package imports раскрыты как seams/UNRUN.

Следующий практический шаг — устранить invalid factory-result boundary у существующего adapter, затем выполнить найденные focused/native builtin tests и проверить declarations известных installed plugins. Prefix retirement и dependency order требуют конечной проверки consumers, а не консолидации всех registries.

[Диагностика](../04_Проверки/C39_PLG01/bounded_diagnostics.json) · [Команды](../04_Проверки/C39_PLG01/commands.json) · [Native границы](../04_Проверки/C39_PLG01/native_verification.json) · [Источники](../05_Источники/C39_источники.json) · [Остатки](../01_Реестры/C39_остатки.json).

**39/127 пакетов рассмотрены ограниченно; следующий — PLG-02. Полного закрытия нет.**

# PLG-01 — DomainPlugin: общая discovery-механика без смены ABI

## 1. Паспорт и результат

**LANE-04 · CP4 · основание 20d9009be21097bfbdc38a546a15cc60213b8ace · статус: ТЗ, не выполнено.** Технический исполнитель и reviewer назначаются проектом. Исходные ID: LA-022. Тип: factory admission isolation + discovery lifecycle qualification.

Malformed dev/prefix factory не обрывает регистрацию следующих пригодных plugins; общая Core loading механика и самостоятельный Domain ABI сохраняются.

Основания: [аудит](../05_Основания/Аудит/02_Пакеты/PLG-01.md), [все остатки](../05_Основания/Аудит/01_Реестры/C39_остатки.json), [неизменная исходная карточка](../05_Основания/Аудит/05_Источники/PLG-01_исходные_строки.txt), исходный объединённый план §PLG-01 (исторические строки 4893–4994).

## 2. Уже работает — сохранить

- Group polisyos.plugins и DomainPlugin state/mechanism/reward/objective/observation/lifecycle ABI, отдельный PluginRegistry.
- Core list_entry_points/load_module_from_file/discovery_module_name, deterministic source order и first duplicate winner.
- Уже зарегистрированные valid plugins и lazy load/unload/dependency guards; discovery не sandbox/empirical authority.

## 3. Полнота обязательств и disposition

| Основание | Решение | Требования |
|---|---|---|
| C39-R01 | fix: Validate factory result до append/register и source-qualified error isolation; object()/None не блокирует later-good. | REQ-PLG-01-01 |
| C39-G01 | qualify: Native builtin Economics и declared installed entrypoint actual state/consumer, не fixture metadata. | REQ-PLG-01-02 |
| C39-G02 | lifecycle: Prefix retirement/dependency ordering требуют declarations/caller decision; не менять hooks автоматически. | REQ-PLG-01-03 |
| C39-G03 | qualify: Сохранить separate Domain ABI; Components bridge только при реальном contract, discovery не security/scientific proof. | REQ-PLG-01-02, REQ-PLG-01-03 |

### Исходные обязанности, не только новые R

- LA-022: shared loading уже подключено; не менять группу на polisyos.foundry_methods или polisyos.components.
- Prefix scan ещё существует: перейти к declarations только после finite consumer map; one-pass registration не topological loader.
- LK08: DomainPlugin не pure_step; create_simple_plugin seed ABI не менять под relocation без отдельного key-profile теста.

## 4. Нормативный контракт

### REQ-PLG-01-01
Directory и prefix factory результаты проходят общий domain-candidate validation внутри existing per-source try до включения в candidates: isinstance DomainPlugin и пригодная metadata для registry. Неверный object()/None/ошибочная metadata дают diagnostic с source/type без повторного небезопасного обращения к metadata и продолжают следующий source. Registry не получает частичный malformed entry; valid earlier/later plugins и deterministic duplicate winner сохраняются. BaseException не поглощать.

Источник: LA-022; аудит: C39-R01; проверки: TEST-PLG-01-01.

### REQ-PLG-01-02
Native auto_discover→registry.get→actual Economics initial state/ordinary run и declared entrypoint сохраняют group/ABI, selected n_agents/max_agents/seed. Lazy hooks: get загружает один plugin один раз, failed on_load не marked loaded, filters не загружают, unregister dependency при живом dependent отказан. Import failure остаётся видимым, не success-shaped empty plugin.

Источник: LA-022; аудит: C39-G01, C39-G03; проверки: TEST-PLG-01-02.

### REQ-PLG-01-03
Finite inventory known installed prefix/dev/entrypoint consumers определяет declarations и support window. До retirement prefix path честно остаётся; child-before-parent current one-pass получает warning и не auto-retried, если порядок не объявлен поддержанным. При реальной необходимости retry/topological registration расширять existing adapter с явным missing/cycle disposition, без implicit on_load dependency hooks. Components integration не заявлять без существующего конкретного bridge.

Источник: LA-022; аудит: C39-G02, C39-G03; проверки: TEST-PLG-01-03.

## 5. Техническое решение и producer → consumer

Добавить маленький private validator у foundry/plugins/discovery.py и вызывать из factory branches до append в existing source try. Опираться на существующий DomainPlugin/metadata contract, не duck-accept произвольный object. Diagnostics используют source string и безопасно сохранённое имя, чтобы warning не повторял fault plugin.metadata. Registry.register остаётся единственным writer; при дополнительных metadata validation errors поймать только обычные candidate failures на discovery admission, не скрывать общий broken registry. Native builtins проходят тот же declared ABI.

### Проверенные owners на срезе
- policy-engine/src/polisyos/foundry/plugins/discovery.py: _discover_installed_plugins, _discover_directory_plugins, auto_register_plugins
- policy-engine/src/polisyos/foundry/plugins/core.py: DomainPlugin, PluginRegistry.register/get/unregister
- policy-engine/src/polisyos/core/discovery/base.py: list_entry_points, load_module_from_file
- policy-engine/src/polisyos/foundry/plugins/api.py: PolisySimulator auto_discover

Broad catch вокруг всего auto_register скрывает источник и оставляет later-good необработанным. Новый scanner/registry или переключение entrypoint group не нужно.

## 6. Локальная приёмка — все будущие проверки NOT_RUN

### TEST-PLG-01-01
- Уровень: unit + targeted native integration.
- Setup: Own dev a_bad/plugin.py возвращает object(), z_good valid; prefix factory None→valid; bad metadata и import exception; duplicate alpha/zeta.
- Действие: Actual Core load→domain discovery→auto_register.
- Точный oracle: bad source diagnostic содержит source/reason; later-good зарегистрирован и usable; earlier valid сохраняется, no half entry. Duplicate deterministic first winner с warning. Missing/non-directory root empty, arbitrary sibling не scanned; cleanup sys.modules.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-PLG-01-02
- Уровень: unit + targeted native integration.
- Setup: Native builtin Economics и один declared installed test distribution в уже подготовленном packaging environment; actual registry/state.
- Действие: Simulator initialize/run; lifecycle get twice/fail then retry/unregister/filter.
- Точный oracle: Actual state dimensions/seed and ordinary outcome пригодны; load exactly once after success, failed load not latched, filters0hooks; dependency guard intact. Domain ABI не заменён method ABI.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-PLG-01-03
- Уровень: unit + targeted native integration.
- Setup: Known consumers declaration/census, child-before-parent fixture и explicit prefix opt-in support state.
- Действие: Reproduce one-pass behavior; declared ordering positive; evaluate retirement docs/config paths.
- Точный oracle: Operational limitation видна, не названа topo loader. Supported declarations load; no unapproved prefix removal or environment-wide imports. No implicit security/certificate claim.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

Повторно использовать/расширить реальные места, а не создавать 127 harness: `policy-engine/tests/unit/remediation/test_plg_01.py`. До выбора selector прочитать полный test/fixture. Это проверенные пути, не утверждение о наличии всех предложенных assertions.

Допустимые doubles: tiny trusted plugin files, enumerated entrypoint metadata в unit; native installed evidence отдельно. Запрещено: импорт всего environment, fake EconomicState в final builtin witness, discovery success как sandbox guarantee.

## 7. Общая интеграция и порядок

Этот admission питает ordinary economics и PLG-02/03. Shared packaging entrypoint evidence один; malformed factory regression локальный без установки произвольных packages.

Точные общие сценарии: E02-I04-C из [контракта интеграции](../03_Интеграция/LANE-04.md); одно свидетельство переиспользуется по неизменным input/backend bindings. Зависимости: нет обязательного нового предшественника; исходный DAG — ориентир, работающий контракт может удовлетворять ребру без нового ремонта. Общие файлы из §5 интегрировать последовательно с затронутыми owners; lane не новый runtime-реестр и не требование полного CI после каждого пакета.

## 8. Совместимость, история, rollback

Prefix scan removal отдельный lifecycle change. Existing DomainPlugin class callers сохраняются; unsupported malformed objects не supported ABI. Seed first-key-word helper characterization не расширяется до typed JAX keys без проверки.

## 9. Free-grow и design direction

- Новый совместимый plugin проходит общий admission и существующий runtime registry без case-specific routing.
- Source load availability отделена от model authority; useful valid plugin не теряется из-за соседнего invalid source.

Архитектурные источники: [policyos-identity-and-custody-boundary.md §1, §3–6](../05_Основания/Архитектура/policyos-identity-and-custody-boundary.md); [policy-design-custody-time-model.md §2–5](../05_Основания/Архитектура/policy-design-custody-time-model.md). Историческая подлинность и текущая пригодность раздельны; физический layout design-docs не догма.

## 10. Нерешённые решения и передача

Новых блокирующих продуктовых решений не требуется. Реальную доступность supported runtime установить до native проверки; недоступность оформлять NOT_RUN, не PASS.

Предъявить patch/base SHA (либо обоснованный no-code результат), актуальную карту callers, REQ→TEST→evidence, фактические команды/логи, различающий контроль и сохранённые инварианты. Поддержанный native профиль: P-CORE (Python >=3.14,<3.15 и project lock); для native численных/JIT/train проверок P-JAX (тот же lock, JAX/jaxlib/optax, deterministic tiny CPU); для процессов P-PROCESS, для поставки P-PACKAGING. Не устанавливать зависимости без отдельного разрешения. Fixture/source-only, исторические PASS и отсутствие ошибки при импорте не закрывают свежий producer→persistence→fresh-reader. Успешная сериализация/конверсия/подпись не доказывает научной истины или полномочия policy result. Никакое требование/тест этой карточки ещё не исполнены.


Полные probes исходного аудита доставлены отдельно в phase1 ZIP; ссылки аудита на них не означают включение тяжёлой evidence в этот исполнительский комплект.

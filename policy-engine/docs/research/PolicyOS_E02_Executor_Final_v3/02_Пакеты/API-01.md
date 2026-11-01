# API-01 — Явные causal façades: native consumers, полный literal census и compatibility window

**Исполнительская спецификация; финальная QA комплекта ещё ожидается.**
**LANE-05 · CP5 · LA-020.** Основание `20d9009be21097bfbdc38a546a15cc60213b8ace`. Реализация документом не выполнена; все будущие проверки **NOT_RUN**. Именных исполнителя/reviewer назначает проект.

## 1. Практическая цель и область

Квалифицировать уже сделанную explicit identity-preserving поверхность двух пакетов. Исправить конкретный false-negative prefilter тестового census и подтвердить real leaf/installed/dispatch/FQN consumers без нового mega-facade или механического удаления compatibility names.

**Тип работы:** Preserve/native qualification; test-maintenance C51-G02; конечное lifecycle решение. Подтверждённого runtime R нет.

[Аудит](../05_Основания/Аудит/02_Пакеты/API-01.md) · [остатки](../05_Основания/Аудит/01_Реестры/C51_остатки.json) · [исходная карточка](../05_Основания/Аудит/05_Источники/API-01_исходные_строки.txt) · [источники](../05_Основания/Аудит/05_Источники/C51_источники.json) · [трассировка](../04_Трассировка/API-01.json). Полные диагностические scripts/logs остаются в отдельно доставленном ZIP фазы 1. Действуют [общие правила](../00_Общее/Правила_исполнения_и_приёмки.md).

## 2. Исходные обязанности и сохранение

LA-020 reflection-copy уже устранён: causal_engine public2/direct-only5, interference public9/direct-only3. Loop по globals очищает stale names при reload, не копирует произвольный leaf namespace. LK05/LK13 защищают реальные ID/BERL packages и algorithms. Остаток не равен повторной миграции всех внутренних modules.

- `preserve:0633`: Реальные causal_engine/interference packages и leaf owners → REQ-API-01-02, REQ-API-01-06; TEST-API-01-02, TEST-API-01-05.
- `preserve:0634`: Public manifests 2/9 и direct-only compatibility 5/3 → REQ-API-01-01; TEST-API-01-01, TEST-API-01-02.
- `preserve:0635`: Identity-preserving aliases → REQ-API-01-01; TEST-API-01-01, TEST-API-01-05.
- `preserve:0636`: Потребление четырёх supported monkeypatch bindings с restoration → REQ-API-01-03; TEST-API-01-03.
- `preserve:0637`: Отказ unknown names и cleanup stale globals при reload → REQ-API-01-02; TEST-API-01-01, TEST-API-01-02.

## 3. Disposition полного остатка

| ID | Действие / причина | REQ / общий владелец |
|---|---|---|
| `C51-G01` | qualify: Actual native leaves/installed/docs/FQN/dispatch вместо synthetic identity witness. | REQ-API-01-01, REQ-API-01-02, REQ-API-01-03, REQ-API-01-05, REQ-API-01-06 |
| `C51-G02` | lifecycle: Конкретный census test repair плюс отдельное supported client window, не runtime regression claim. | REQ-API-01-02, REQ-API-01-04, REQ-API-01-05 |

Все source-registry remaining также связаны: `remaining:0393`, `remaining:0394`. Подробная причина и REQ для каждой строки — в companion JSON; повторная запись не считается новым независимым дефектом.

## 4. Нормативный контракт

### REQ-API-01-01
Сохранить explicit supported manifests: causal_engine CausalEngine/DataReadinessBlockedError; interference четыре estimator classes, три identification functions и два public contracts. Восемь declared direct-only compatibility bindings доступны в установленном окне, но не расширяют star import. Все bindings сохраняют actual leaf object identity без wrappers.
Источник: LA-020; C51-G01. Проверки: TEST-API-01-01, TEST-API-01-02.

### REQ-API-01-02
Incidental import в leaf не расширяет package surface; reload удаляет stale injected names, unknown name не получает permissive fallback. Настоящие packages/leaf algorithms сохраняются независимо от retired sibling.py. Не удалять underscore symbols по одному grep и не переносить все helpers в api.py.
Источник: LA-020; C51-G01, C51-G02. Проверки: TEST-API-01-01, TEST-API-01-02.

### REQ-API-01-03
Четыре supported package monkeypatch bindings реально достигают actual identify/static dispatch и после restoration перестают действовать. Проверка class identity/__all__ без consumer call недостаточна; no-op sync removal control должен различающе проваливаться.
Источник: LA-020; C51-G01. Проверки: TEST-API-01-03.

### REQ-API-01-04
Literal consumer census рассматривает все tracked Python files в named denominator либо безопасный content-or-package-path prefilter с корректным relative resolution. Relative from . import artifacts/discovery/identification внутри package не пропускается из-за отсутствия его имени в тексте. Parse/encoding/unsupported syntax gaps считаются явно, actual imports выполняются в поддержанном runtime.
Источник: LA-020; C51-G02. Проверки: TEST-API-01-04.

### REQ-API-01-05
Installed wheel/sdist, actual public imports, real FQN/доверенные historical serialization fixtures и docs generation квалифицируются в поддержанном dependency profile. Computed/configuration/external consumer window перечисляется отдельно от AST census; unknown external usage не объявляется нулём. Retain/retire любого compatibility binding требует конкретного owner решения и migration path.
Источник: LA-020; C51-G01, C51-G02. Проверки: TEST-API-01-05, TEST-API-01-06.

### REQ-API-01-06
Public causal/interference positive или явно limited result достигает actual consumer с прежними DTO/exceptions/semantic scope. Facade success не выдаётся за empirical causal validity; synthetic leaf/fake algorithm tests только local binding controls, не native acceptance. Existing algorithms не меняются ради surface cleanup.
Источник: LA-020; C51-G01. Проверки: TEST-API-01-03, TEST-API-01-05.

## 5. Конкретное техническое решение

Product initializers уже explicit: сохранить их bindings и reload cleanup. Native tests должны импортировать реальные leaf modules, не class-shaped shells. Sync helper имеет11 потенциальных algorithms, но facade поддерживает только4 direct algorithm names; не расширять public API до11 по длине helper list. Actual consumer test проходит public identify→sync→branch, restoration и no-op control; one __all__ assertion недостаточен.

**Конкретная правка теста:** current `test_repository_literal_facade_imports_resolve` делает content-only prefilter до AST parse. Предпочтительно parse все tracked Python files: denominator конечен, существующий test уже repository census. Если стоимость требует filter, учитывать target package path и relative package address плюс absolute content, проверить его полноту на exhaustive reference. `ast.ImportFrom(level,module)` разрешается относительно фактического package (initializer и normal module различены), затем выполняется настоящее from-import с submodule fallback. Сохранить path/line/name/counts и parse gaps. Не добавить пять hardcoded exceptions: новая совместимая relative import должна обнаруживаться общим правилом.

**Compatibility:** fixed manifest не означает законченного external retirement. Сопоставить actual dynamic strings/config/generated/docs/доверенные FQN fixtures и объявленное release window. Defaultretain всех8 supported direct-only bindings; internal callers при обосновании переходят к leaf owner. Удаление конкретного binding — отдельный маленький lifecycle delta с positive canonical API и negative retired route, не новый центральный фасад. Packaging fixture с disposable Git commit не запускать без inspection/согласования; это будущая controlled acceptance, не разрешение менять наш audit checkout.

### Текущие owners и источники

- [policy-engine/src/polisyos/foundry/methods/catalog/causal/causal_engine/__init__.py:1–42](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/causal_engine/__init__.py#L1-L42)
- [policy-engine/src/polisyos/foundry/methods/catalog/causal/interference/__init__.py:1–67](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/interference/__init__.py#L1-L67)
- [policy-engine/src/polisyos/foundry/methods/catalog/causal/causal_engine/identification.py:94–115](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/causal_engine/identification.py#L94-L115)
- [policy-engine/src/polisyos/foundry/methods/catalog/causal/causal_engine/identification.py:2163–2223](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/causal_engine/identification.py#L2163-L2223)
- [policy-engine/tests/unit/foundry/methods/catalog/causal/test_facade_consumers.py:167–212](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/methods/catalog/causal/test_facade_consumers.py#L167-L212)
- [policy-engine/tests/unit/remediation/test_api_01.py:1–237](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_api_01.py#L1-L237)

## 6. Проверки: setup → действие → oracle

TEST-ID обозначает требуемую проверку, не существующий одноимённый pytest test. Расширять указанные действительные места, не дублировать suites.

### TEST-API-01-01 · native manifest/identity/import matrix
**NOT_RUN. REQ:** REQ-API-01-01, REQ-API-01-02.
**Setup:** Actual heavy leaves и два package initializers в supported environment; explicit manifest public2/9 и compatibility5/3.
**Действие:** Direct import, star import, getattr supported/unknown и identity comparisons с leaf owners.
**Oracle:** Exact public sets, direct-only names excluded fromstar, objects is canonical leaf objects, unknown ImportError/AttributeError. Реальные exception/DTO class identity сохранены. Никакие synthetic leaves в native evidence.
**Место:** `tests/unit/remediation/test_api_01.py; tests/unit/foundry/methods/catalog/causal/test_facade_consumers.py`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-API-01-02 · native incidental/reload controls
**NOT_RUN. REQ:** REQ-API-01-01, REQ-API-01-02.
**Setup:** Actual packages; controlled extra incidental leaf import и stale facade name; canonical objects saved.
**Действие:** Reload actual initializer, compare manifests/identity; restore test mutations.
**Oracle:** Incidental name не exported, stale name removed, supported direct/public objects retained. Само наличие globals cleanup loop не считается reflection-copy regression. Retired sibling filenames не требуются package resolution.
**Место:** `tests/unit/remediation/test_api_01.py`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-API-01-03 · native facade→identify→dispatch restoration
**NOT_RUN. REQ:** REQ-API-01-03, REQ-API-01-06.
**Setup:** Supported names id_star_algorithm,id_with_oracle_fallback,idc_star_algorithm,mz_id_algorithm; actual CausalEngine/graph/query. Delegating spies вокруг actual algorithms где возможно.
**Действие:** Patch facade binding, invoke соответствующий actual public identify route; restore and repeat; controlled no-op sync negative.
**Oracle:** Каждый выбранный branch действительно вызывает установленный binding один раз либо documented actual count; после restore исходный algorithm снова используется. No-op sync теряет patch consumption и regression падает при unchanged manifest/class identity. Result сохраняет valid/limited DTO semantics, не success-shaped fixture-only native claim.
**Место:** `causal_engine/identification.py::_sync_public_algorithm_overrides; tests/unit/foundry/methods/catalog/causal/test_facade_consumer_continuation.py`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-API-01-04 · native exhaustive literal census regression
**NOT_RUN. REQ:** REQ-API-01-04.
**Setup:** Pinned git ls-files *.py inventory, explicit path→package mapping; fixture files с relative imports без target words и absolute imports/aliases.
**Действие:** Сначала AST parse всего finite denominator (предпочтительно); resolve relative import level; execute actual import semantics incl submodule fallback. Classify executable/history отдельно.
**Oracle:** Пять известных relative sites из C51 включены на baseline; old content-only filter removal control теряет их. Counts recomputed на actual commit, не hardcoded71/8231 для вечности. Parse/encoding gaps0 либо explicit BLOCKED; AST inventory не выдаётся за computed/external census.
**Место:** `tests/unit/foundry/methods/catalog/causal/test_facade_consumers.py::test_repository_literal_facade_imports_resolve`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-API-01-05 · native installed consumer/FQN/docs E02-I05-A
**NOT_RUN. REQ:** REQ-API-01-05, REQ-API-01-06.
**Setup:** Coordinated wheel/sdist и clean import environment, actual real classes/functions, только доверенные retained serialization fixtures; docs build profile.
**Действие:** Import outside checkout, resolve genuine FQN, roundtrip trusted fixtures, run representative CausalEngine/interference consumer и docs surface.
**Oracle:** Origins установленного artifact; no wrapper-induced FQN/class drift; expected useful/limited result и exceptions сохранены. Public docs не получают incidental names. Отсутствие genuine historical fixture помечается gap, fresh synthetic pickle не считается history replay.
**Место:** `tests/unit/foundry/methods/catalog/causal/test_installed_facade_contract.py; test_facade_consumers.py`.
**Doubles:** Нельзя загружать недоверенный pickle. Existing installed fixture создаёт disposable Git copy/commit: сначала inspect и согласовать controlled packaging job; исходный checkout/refs не изменяются этим документом.

### TEST-API-01-06 · finite lifecycle decision
**NOT_RUN. REQ:** REQ-API-01-05.
**Setup:** Actual literal census, dynamic-string/config/generated/docs known clients и доступные external support declarations; internal tests using compatibility symbols.
**Действие:** Классифицировать public/test-facing/incidental; выбрать retain window либо конкретный authorized retirement, перевести только соответствующие internal callers к leaf owners.
**Oracle:** Default supported eight bindings остаются. Retirement имеет named caller migration и installed/FQN/monkeypatch negative+canonical positive evidence; unknown external window не превращается в blind deletion. Никакой новый mega-facade или alias chain.
**Место:** `Existing public-surface contract и causal facade documentation owners`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### Запуск: адаптируемый шаблон, не выполненная команда

Из `policy-engine/` в поддержанной Python3.14 среде с закреплёнными зависимостями. Этот документ не разрешает автоматические installs; отсутствующая dependency означает BLOCKED конкретной проверки.

```bash
python -V
python -m pytest -q tests/unit/remediation/test_api_01.py tests/unit/foundry/methods/catalog/causal/test_facade_consumers.py tests/unit/foundry/methods/catalog/causal/test_facade_consumer_continuation.py
# test_installed_facade_contract.py: только после inspection disposable build/commit fixture и согласования packaging job; не запускать автоматически.
```

Фиксировать профиль/backend, inputs/seed/hash, deciding output и exit. Ruff и затронутые architecture/import checks выбирать по фактическому patch; native slot согласовать, полный suite на каждый пакет не копировать.

## 7. Общая интеграция и ownership

Переиспользовать **E02-I05-A**: [канонический контракт LANE-05](../03_Интеграция/LANE-05.md). Одно свидетельство связывается с конкретными вариантами и REQ; не считается многими независимыми подтверждениями.

API-01 владеет двумя initializers/consumer tests и finite supported surface decision. GRF-01 сохраняет настоящие packages и structural mechanisms. Packaging/docs владелец LANE-12 исполняет один installed job; результат переиспользуется только при том же artifact/profile.

- **GRF-01:** Native packages и installed evidence разделяются; точечное sibling retirement не facade rewrite.
- **LANE-12:** Общий packaging/docs/public-surface job, не отдельная сборка на каждый alias.

## 8. Совместимость, миграция и возврат

Без нового product change explicit aliases сохраняют identity, FQN и intended monkeypatch semantics. Census enhancement только расширяет qualification denominator. Нельзя объявить случайно раскрытые исторические imports вечным API или удалить их без window evidence. Rollback test/census не должен возвращать reflection-copy; uncertain compatibility retains named explicit binding до решения, не namespace wholesale export.

## 9. Free-grow и обоснованные границы

- [universal-policy-design-target-architecture-and-gap.md — D0: explicit reusable capability surfaces](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md): Новая внутренняя зависимость не расширяет публичный contract случайно; реальная extensibility находится у leaf owners, не mega-facade.
- [policyos-identity-and-custody-boundary.md — Identity and compatibility boundaries](../05_Основания/Архитектура/policyos-identity-and-custody-boundary.md): Object/FQN identity и supported API lifetime проверяются явно; package import не подтверждает scientific authority result.

## 10. Конечные решения и сдача

### DEC-API-01-WINDOW
**Вопрос:** Какие compatibility bindings допускается снять и когда?
**Кто решает:** Public API/release owner.
**Конечное действие/выход:** TEST06 named finite census+actual support declaration; выбрать retain либо точечный retirement с caller/FQN/docs/monkeypatch acceptance. Недоступные external сведения честно ограничивают решение.
**До решения:** Восемь declared direct-only bindings сохраняются, public2/9 неизменны.

Сдать base/head и patch, exact REQ→TEST→shared variant, исходные входы и их идентичности, actual команды/exit/log, независимые численные/семантические oracles, positive/negative/removal controls, сохранённые инварианты и открытые решения. Source-only, fixture, native и scientific qualification отражать отдельно. Не повышать partial/NOT_RUN до PASS; квалифицированный локальный механизм не является автоматической готовностью всей политики.

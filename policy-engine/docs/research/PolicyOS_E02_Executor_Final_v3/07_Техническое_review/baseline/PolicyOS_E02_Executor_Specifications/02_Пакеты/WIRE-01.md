# WIRE-01 — Версионированный transport допустимых типов state

## 1. Паспорт и результат

**LANE-06 · CP2 · основание 20d9009be21097bfbdc38a546a15cc60213b8ace · статус: ТЗ, не выполнено.** Технический исполнитель и reviewer назначаются проектом. Исходные ID: B94. Тип: semantic-depth codec fix + test drift/native backend qualification.

Каждое принятое writer значение читается собственным reader с точными типами и bounded depth; deterministic codec failure не запускает дорогое вычисление повторно.

Основания: [аудит](../05_Основания/Аудит/02_Пакеты/WIRE-01.md), [все остатки](../05_Основания/Аудит/01_Реестры/C73_остатки.json), [неизменная исходная карточка](../05_Основания/Аудит/05_Источники/WIRE-01_исходные_строки.txt), исходный объединённый план §WIRE-01 (исторические строки 8489–8561).

## 2. Уже работает — сохранить

- Exact Decimal tuple/scale/negative zero и bytes tags; v2 payload отдельно от v1 integrity frame.
- Closed model registry, actual ArtifactRef/ArtifactID/manifest selector.
- OutputAware subtype и ordered mutation journal sidecar.
- Nonfinite/unsupported/cycles refuse, legacy readers и hash exact wire bytes.

## 3. Полнота обязательств и disposition

| Основание | Решение | Требования |
|---|---|---|
| C73-R01 | fix: Согласовать semantic tree depth с technical tags; guards не удалять. | REQ-WIRE-01-01 |
| C73-G01 | qualify: Actual stdlib/orjson и worker/attempt, не два fake backend labels. | REQ-WIRE-01-02, REQ-WIRE-01-03 |
| C73-G02 | fix: Current v2 assertion value.inputs, отдельный legacy read corpus. | REQ-WIRE-01-03 |

### Исходные обязанности, не только новые R

- B94 → REQ-WIRE-01-01…-03: state/outcome/safe exact typed transport across both real backends, positive accepted-writer→reader, no float/default=str.

## 4. Нормативный контракт

### REQ-WIRE-01-01
Для всех значений в объявленном supported depth profile successful serialize_state/outcome/safe гарантирует successful соответствующий decode с теми же типами/значениями. Escaped user _type mapping расходует ту же semantic depth, что plain mapping; technical wrappers не удваивают её. Слишком глубокие/циклические значения явно отвергаются до публикации.

Источник: B94; аудит: C73-R01; проверки: TEST-WIRE-01-01.

### REQ-WIRE-01-02
Оба настоящих JSON backend сохраняют finite Decimal в budgets/Any/union, bytes, actual refs/selectors, OutputAware subtype и journal. Unknown model/tag, duplicate mapping entry, malformed/nonfinite/untyped v2 budget и corrupted safe digest отказываются; digest не заменяет access/tenant admission.

Источник: B94; аудит: C73-G01; проверки: TEST-WIRE-01-02.

### REQ-WIRE-01-03
Current writer tests проверяют v2 envelope value.inputs, а legacy raw reader tests остаются независимыми. Actual process worker потребляет Decimal outcome; deterministic serialization refusal не приводит к лишнему physical attempt. Historical bytes продолжают читаться своим declared profile.

Источник: B94; аудит: C73-G01, C73-G02; проверки: TEST-WIRE-01-03.

## 5. Техническое решение и producer → consumer

Определить один semantic-depth convention в существующих _encode_wire_value/_decode_wire_value/_decode_wire_tag: depth увеличивается при переходе к пользовательскому child, не при dispatch самого tag/entries wrapper. Передавать в _decode_wire_tag тот же depth; mapping entry child +1, model payload согласовать с тем, что writer считает model field child. Отдельно соблюдать реальные raw parser limits backend: если orjson не способен читать encoded wrapper depth, writer должен заранее отказать в этом backend-profile либо выбрать общий меньший admitted semantic ceiling, а не выпускать unreadable bytes. Не просто увеличить MAX_DEPTH. Unit table обязана содержать nested models/tags/escaped maps, не только64 dictionaries.

Update stale test_artifact_ref_and_artifact_id_tags_are_compatible к v2 value.inputs; отдельный literal legacy payload оставляет read coverage. Encoder→exact bytes/hash→decoder→actual DTO→worker consumer, без общего model_dump(json) и default=str.

### Проверенные owners на срезе
- policy-engine/src/polisyos/scientist/orchestration/engine/runner/serialization.py: _encode_wire_value, _decode_wire_tag, _decode_wire_value, serialize_state/outcome/safe
- policy-engine/tests/unit/remediation/test_wire_01.py: current artifact tag assertion
- policy-engine/tests/unit/scientist/orchestration/engine/runner/test_serialization_e02.py: current v2/worker controls

Удаление depth guard, float(Decimal) и глобальный default=str недопустимы. Новый per-backend формат не нужен; различающий backend admission можно явно ограничить общей гарантией.

## 6. Локальная приёмка — все будущие проверки NOT_RUN

### TEST-WIRE-01-01
- Уровень: unit + targeted native integration.
- Setup: Depth sweep вокруг actual limit plain/escaped/model/list mixtures; pinned64 escaped counterexample; cycles.
- Действие: Encode/decode state/outcome/safe в каждом actual backend.
- Точный oracle: Каждый accepted writer input roundtrips; plain/escaped имеют одинаковую semantic boundary; too-deep typed refusal до publication. 64 escaped positive больше не own-reader failure либо writer explicitly refuses по объявленному общий backend contract.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-WIRE-01-02
- Уровень: unit + targeted native integration.
- Setup: Actual ExperimentState budgets Decimal('-0.00'), Decimal union, bytes, selected refs/outputaware/journal; malicious tag corpus.
- Действие: Both real backend cold/warm roundtrip and tamper.
- Точный oracle: Decimal.as_tuple exact, bytes equal, actual classes/selectors/subtype/journal retained; invalid inputs refused without coercion to str/0/null; safe digest equals exact transmitted body.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-WIRE-01-03
- Уровень: native tests + process integration.
- Setup: Updated v2 assertion + literal legacy fixture; actual bound worker and attempt counter.
- Действие: Native tests, Decimal process result, unsupported deterministic input.
- Точный oracle: Current value.inputs tags verified, legacy still readable; exact output through process. Serialization rejection yields no additional computation/retry and no accepted receipt.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

Повторно использовать/расширить реальные места, а не создавать 127 harness: `policy-engine/tests/unit/remediation/test_wire_01.py`; `policy-engine/tests/unit/scientist/orchestration/engine/runner/test_serialization_e02.py`; `policy-engine/tests/unit/scientist/orchestration/engine/runner/test_serialization.py`. До выбора selector прочитать полный test/fixture. Это проверенные пути, не утверждение о наличии всех предложенных assertions.

Допустимые doubles: synthetic typed payload/negative corpus; attempt counter as observer. Запрещено: mock orjson labelled native, fake DTO/codec/worker owner, default=str repair.

## 7. Общая интеграция и порядок

WIRE-01 owns typed transport; RUN-02 real pipe, STA-01 mutation replay, DUR-02 current attempt receipt. Ray/Temporal full services не обязательны базовому codec acceptance, их declared consumers scoped separately.

Точные общие сценарии: E02-I06-C из [контракта интеграции](../03_Интеграция/LANE-06.md); одно свидетельство переиспользуется по неизменным input/backend bindings. Зависимости: нет обязательного нового предшественника; исходный DAG — ориентир, работающий контракт может удовлетворять ребру без нового ремонта. Общие файлы из §5 интегрировать последовательно с затронутыми owners; lane не новый runtime-реестр и не требование полного CI после каждого пакета.

## 8. Совместимость, история, rollback

V2 writer не откатывать к legacy raw ради теста; legacy reader сохраняет прежний смысл. Если admitted depth сужается из-за actual backend parser, явно version/profile compatibility decision и readable historical bytes; не менять старые hashes.

## 9. Free-grow и design direction

- design_direction.md §4.1/§4.7: type/identity сохранены на границе; hash не authority.
- policy-design-custody-time-model.md §2–5: family-native semantics не заменять общей универсальной envelope ради удобства.

Архитектурные источники: [policyos-identity-and-custody-boundary.md §1, §3–6](../05_Основания/Архитектура/policyos-identity-and-custody-boundary.md); [policy-design-custody-time-model.md §2–5](../05_Основания/Архитектура/policy-design-custody-time-model.md). Историческая подлинность и текущая пригодность раздельны; физический layout design-docs не догма.

Полные исторические probes/commands/logs остаются в отдельно доставленном phase1 ZIP; ссылки внутри копий аудита на `04_Проверки` относятся к нему, не к новым исполненным проверкам этого комплекта.

## 10. Нерешённые решения и передача

Новых блокирующих продуктовых решений не требуется. Реальную доступность supported runtime установить до native проверки; недоступность оформлять NOT_RUN, не PASS.

Предъявить patch/base SHA (либо обоснованный no-code результат), актуальную карту callers, REQ→TEST→evidence, фактические команды/логи, различающий контроль и сохранённые инварианты. Поддержанный native профиль: P-CORE (Python >=3.14,<3.15 и project lock); для процессов P-PROCESS, для поставки P-PACKAGING. Не устанавливать зависимости без отдельного разрешения. Fixture/source-only, исторические PASS и отсутствие ошибки при импорте не закрывают свежий producer→persistence→fresh-reader. Успешная сериализация/конверсия/подпись не доказывает научной истины или полномочия policy result. Никакое требование/тест этой карточки ещё не исполнены.


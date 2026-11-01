# DDM-01 — Квалификация canonical contracts/lazy facade без повторного move

**LANE-11 · LA-056 · SHA `20d9009be21097bfbdc38a546a15cc60213b8ace`.**

**Статус:** исполнительская спецификация на последующую работу; требования и будущие тесты здесь не исполнены.

## 1. Практическая цель и тип работы

Contract consumers получают один тип без загрузки monitoring orchestration, public monitor остаётся доступным.

**Тип:** preserve/qualify-only C121-G01/G02; product changes только по reproduced mismatch.

Основания: [полный отчёт](../05_Основания/Аудит/02_Пакеты/DDM-01.md), [исходные карточки](../05_Основания/Аудит/05_Источники/DDM-01_исходные_строки.txt), [трассировка](../04_Трассировка/DDM-01.json).

## 2. Уже работает — сохранить

- LK01/14: DDM monitoring не Foundry fit/predictive calibration/N11 ledger.
- Canonical events/budget identity, lazy parents и forwarding old FQN.
- LK35 manual channel schema и runtime reversed-window guards разные; LK33/34 current validity/R2/diagnostic roles принадлежат DDM-02.

## 3. Полная disposition исходных обязанностей и остатков

| ID | Действие | Требования | Почему |
|---|---|---|
| LA-056 | qualify | REQ-DDM-01-01, REQ-DDM-01-02, REQ-DDM-01-03, REQ-DDM-01-04, REQ-DDM-01-05 | Move/lazy repaired; не повторять физический перенос. |
| C121-G01 | qualify | REQ-DDM-01-01, REQ-DDM-01-02, REQ-DDM-01-05 | Native supported extras/package qualification; отсутствующий optional checker не schema bug. |
| C121-G02 | lifecycle | REQ-DDM-01-03, REQ-DDM-01-04 | Реальный historical census и DDM-02 semantic ownership. |

## 4. Нормативные требования результата

**REQ-DDM-01-01.** Cold contract-only imports не должны загружать monitor/registry/incident; все supported old exports возвращают canonical class objects, root monitor API доступен по запросу.

**REQ-DDM-01-02.** Canonical relocation должна сохранять enum/event_type/pass aliases, strict extras и native validation; manual anyOf channel и runtime cross-field windows не заменяют друг друга.

**REQ-DDM-01-03.** Supported historical FQN/plugin/serialization consumers должны быть проверены на фактически доступном corpus; synthetic fixture не выдаётся за historical replay, aliases не удаляются до exit criteria.

**REQ-DDM-01-04.** Actual monitor должен сохранять drift-only/diagnostic-only/readiness/incident outputs; relocation не считается выполненной applicability/R2/authority работой DDM-02.

**REQ-DDM-01-05.** Installed wheel/sdist и supported tooling должны сохранять contract resources/exports, typing/import boundaries и действующий date-time checker.

## 5. Конкретное техническое решение — рекомендуемый способ

- Не менять canonical contracts/events.py/metric_budget.py и lazy __getattr__ без native mismatch. Existing facade/compatibility/fresh-consumer tests — primary owners.
- G01 run supported3.14 pinned extras; test that RFC3339 checker installed, не лечить missing environment удалением schema format. Build/package evidence reuses LANE12, без второго packaging harness.
- G02 bounded current/historical/plugin census, retain forwarding until owner/release window and all found consumers migrated. ReadinessPolicy remains executable readiness owner. Новые DDM-02 fields отдельно от equivalent relocation evidence; currentHEAD не доказывает byte-equivalent historical commit.

**Существующие code/test owners:**
- [`src/polisyos/ddm/__init__.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ddm/__init__.py).
- [`src/polisyos/ddm/contracts/events.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ddm/contracts/events.py).
- [`src/polisyos/ddm/contracts/metric_budget.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ddm/contracts/metric_budget.py).
- [`src/polisyos/ddm/integration/__init__.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ddm/integration/__init__.py).
- [`src/polisyos/ddm/integration/events.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ddm/integration/events.py).
- [`src/polisyos/ddm/integration/shift_event.schema.json`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ddm/integration/shift_event.schema.json).
- [`tests/unit/ddm/test_facade.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/ddm/test_facade.py).
- [`tests/unit/ddm/test_contract_compatibility.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/ddm/test_contract_compatibility.py).
- [`tests/unit/ddm/test_contract_fresh_consumers.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/ddm/test_contract_fresh_consumers.py).

## 6. Локальные проверки — все NOT_RUN

### TEST-DDM-01-01 → REQ-DDM-01-01, REQ-DDM-01-05

**Уровень:** cold processes/import trap. **Ожидается:** positive + negative + boundary.

**Setup:** Fresh process для root/contracts/events/budget/old-events; trap monitor import; installed package profile.

**Действие:** Import каждый surface, затем actual root monitor export.

**Oracle:** Contracts не достигают trap, actual monitor достигает контрольного trap; без trap доступен. Все14 event/enum exports и budget old/new is-identical.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-DDM-01-02 → REQ-DDM-01-02, REQ-DDM-01-05

**Уровень:** runtime/manual schema corpus. **Ожидается:** positive + negative + boundary.

**Setup:** Valid shift; no p/e/ert; reversed window; bad RFC3339 date; pass/pass_; nested extra.

**Действие:** Actual Pydantic и manual JSON schema with installed format-nongpl checker; проверить checker capability отрицательной датой.

**Oracle:** No-channel runtime+manual reject, plain generated shape не заменяет их; reversed window runtime reject; malformed date действительно reject, не просто создан FormatChecker. Existing aliases/literals preserved.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-DDM-01-03 → REQ-DDM-01-03, REQ-DDM-01-05

**Уровень:** historical + package. **Ожидается:** positive + negative + boundary.

**Setup:** Finite inventory plugins/FQN/resources и доступных trusted historical bytes; synthetic old-FQN event/budget controls отдельно.

**Действие:** Fresh reader JSON/pickle только trusted existing corpus; wheel/sdist resource/import census совместно с LANE12.

**Oracle:** Actual discovered consumers pass declared profile либо explicit migration issue; unknown corpus not claimed checked. No duplicate classes, old globals remain forwarding. Payload semantic/bytes where promised unchanged.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-DDM-01-04 → REQ-DDM-01-04

**Уровень:** E02-I11-B monitor. **Ожидается:** positive + negative + boundary.

**Setup:** Real shift .95; identical diagnostic-only control; no production registry grant.

**Действие:** Actual monitor→risk/readiness/root-cause/incident.

**Oracle:** Drift-only R2, diagnostic-only R4 under existing default profile; typed useful outputs present, registry_record None without context. No deployment/retrain side effect; DDM-02 gates separately.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

## 7. Совместная приёмка, зависимости и владение

Общие сценарии: **E02-I11-B, E02-I12-A** из [канонического lane integration-контракта](../03_Интеграция/LANE-11.md). Они переиспользуются; отдельный тяжёлый harness этого пакета не создавать.

Исходные предшественники: нет. Доказанный существующий контракт может удовлетворить зависимость; lane не глобальный барьер.

DDM-02 owns applicability/policy/source extension. LANE12 owns actual package evidence, not DDM semantic tests. MOVE-10 already resolved to actual current owners.

## 8. Совместимость и восстановление

Old supported FQN exports retained. Trusted historical pickle only, не произвольные внешние bytes. Explicit alias exit decision требует corpus/consumer evidence; отсутствие найденных consumers не доказательство отсутствия внешних.

## 9. Free-grow и design decisions

- [Stage-0 §4.3](../05_Основания/Архитектура/stage0-custody-kernel-ratification.md#43-k06--fail-closed-binds-the-protected-action-not-the-computation) и [синтез §4](../05_Основания/Исследование/design_direction.md): защищённый claim ограничивается своим основанием; useful diagnostic computation не блокируется целиком.

## 10. Решения, которые нельзя подменить догадкой

- DEC-DDM-01-01: inventory обнаруженных plugin/FQN/historical readers; определить поддерживаемое окно forwarding и evidence для retirement. Если historical corpus недоступен, bounded fixture qualification с точной границей, не invented PASS.

## 11. Что предъявить и что не является готовностью

Нет обязательного нового product diff. Native tests/resources/format checker и historical qualification отдельно; canonical identity не gate equivalence.

**Команды:** из `policy-engine/` использовать существующее поддержанное Python 3.14 окружение и точные существующие test paths выше. Шаблон: `<existing-python> -m pytest <selected-existing-path> <new-selector-after-authoring>`; это не выполненная команда и не утверждение, что будущий selector уже существует. Native job — один по общему ресурсу. Никаких install/full-suite по умолчанию.

## 12. Lossless inventory bindings

- `remaining:0489` → REQ-DDM-01-01, REQ-DDM-01-02, REQ-DDM-01-05; Native supported extras/package qualification; отсутствующий optional checker не schema bug.
- `remaining:0490` → REQ-DDM-01-03, REQ-DDM-01-04; Реальный historical census и DDM-02 semantic ownership.
- `preserve:0798` → REQ-DDM-01-01; Single canonical event/budget object — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0799` → REQ-DDM-01-01; Lazy root/integration facades — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0800` → REQ-DDM-01-03; Legacy forwarding and pickle globals — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0801` → REQ-DDM-01-02; Manual channel schema plus runtime cross-field guards — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0802` → REQ-DDM-01-04; ReadinessPolicy owner — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0803` → REQ-DDM-01-04; Diagnostic-only/drift-only distinctions — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.

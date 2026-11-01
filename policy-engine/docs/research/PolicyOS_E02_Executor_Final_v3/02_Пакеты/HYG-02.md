# HYG-02 — Миграция actual governance consumers и точный evidence helper lifecycle

**LANE-12 · LA-008, LA-009, LA-018 · SHA `20d9009be21097bfbdc38a546a15cc60213b8ace`.**

**Статус:** исполнительская спецификация на последующую работу; требования и будущие тесты здесь не исполнены.

## 1. Практическая цель и тип работы

Убрать лишние адреса без потери Scientist passes, evidence и Fabric read path.

**Тип:** C125-G01/G02 lifecycle implementation; C125-G03 native reader qualification.

Основания: [полный отчёт](../05_Основания/Аудит/02_Пакеты/HYG-02.md), [исходные карточки](../05_Основания/Аудит/05_Источники/HYG-02_исходные_строки.txt), [трассировка](../04_Трассировка/HYG-02.json).

## 2. Уже работает — сохранить

- Core class identity и действующие Scientist passes/evidence.
- Fabric world reader; retired evidence_sources/provenance/claims и lex.factlog не восстанавливаются.
- LK17 public OPA facade и LK18 cross-producer root evidence не входят в удаление.

## 3. Полная disposition исходных обязанностей и остатков

| ID | Действие | Требования | Почему |
|---|---|---|
| LA-008 | lifecycle | REQ-HYG-02-01, REQ-HYG-02-04 | Helper ещё есть; no static caller не universal proof. |
| LA-009 | lifecycle | REQ-HYG-02-02, REQ-HYG-02-04 | Конкретные2facade/3test imports требуют migration, не ещё один engine. |
| LA-018 | qualify | REQ-HYG-02-03, REQ-HYG-02-04 | Alias already absent; actual reader qualified separately. |
| C125-G01 | lifecycle | REQ-HYG-02-01 | Finite helper decision includes computed/package obligations. |
| C125-G02 | lifecycle | REQ-HYG-02-02 | Update actual facade first, tests/negative after accepted exit. |
| C125-G03 | qualify | REQ-HYG-02-03, REQ-HYG-02-04 | Real Parquet/native context, не DataFrame adapter. |

## 4. Нормативные требования результата

**REQ-HYG-02-01.** Точный _shim.py и install_module_shim/shim_getattr/shim_dir получают finite lifecycle decision; при отсутствии необходимого caller удаляется только helper, не evidence logic.

**REQ-HYG-02-02.** Подтверждённые Scientist facade Legal/Safety imports должны обращаться к canonical Core; alias retirement следует после config/plugin/monkeypatch consumers и supported window, сохраняя identity.

**REQ-HYG-02-03.** Lex должен продолжать читать через actual Fabric owner с прежними result/access/provenance semantics; отсутствие старого alias не меняет historical fact bytes.

**REQ-HYG-02-04.** Negative retired roots и protected live owners должны сохраняться в source/installed package; cleanup не расширяется на OPA/root evidence/другие Scientist passes.

## 5. Конкретное техническое решение — рекомендуемый способ

- Мигрировать scientist/governance/passes/__init__.py LegalPass/SafetyPass branches на existing Core imports; canonical builtin factories уже correct. После конкретного compatibility решения заменить только obsolete alias identity expectations negative controls, сохранив public facade identity.
- _shim.py retirement independently scoped. Не применять дату PHASE44 evidence manifest к governance aliases. При unresolved external consumer оставить named temporary forwarding и exit predicate, не arbitrary sunset.
- LA-018 не повторное удаление: native reader tests на реальном Parquet/locks/context. Не менять missing segment semantics из-за alias migration без отдельного demonstrated requirement.

**Существующие code/test owners:**
- [`src/polisyos/scientist/evidence/_shim.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/evidence/_shim.py).
- [`src/polisyos/scientist/evidence/compatibility.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/evidence/compatibility.py).
- [`src/polisyos/scientist/governance/passes/__init__.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/governance/passes/__init__.py).
- [`src/polisyos/scientist/governance/pass_entrypoints.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/governance/pass_entrypoints.py).
- [`src/polisyos/lex/normpack/select_sources.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/lex/normpack/select_sources.py).
- [`src/polisyos/fabric/world/store/segments.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/fabric/world/store/segments.py).
- [`tests/unit/scientist/governance/test_shared_shims.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/scientist/governance/test_shared_shims.py).
- [`tests/unit/scientist/methods/test_import_shims.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/scientist/methods/test_import_shims.py).
- [`tests/unit/lex/normpack/test_fabric_world_reader.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/lex/normpack/test_fabric_world_reader.py).
- [`tests/unit/scientist/evidence/test_phase44_taxonomy.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/scientist/evidence/test_phase44_taxonomy.py).

## 6. Локальные проверки — все NOT_RUN

### TEST-HYG-02-01 → REQ-HYG-02-01, REQ-HYG-02-04

**Уровень:** census/public roots. **Ожидается:** positive + negative + boundary.

**Setup:** Three helper symbols/full path across src/tools/config/generated references; unsupported list.

**Действие:** Finite census then chosen lifecycle delta; public Scientist/evidence imports and retired negative tests.

**Oracle:** No necessary caller: helper removed and no restored roots. Necessary caller: minimal forwarding with owner/exit evidence; no new shim framework. Root polisyos.evidence remains.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-HYG-02-02 → REQ-HYG-02-02, REQ-HYG-02-04

**Уровень:** actual facade/config/plugin. **Ожидается:** positive + negative + boundary.

**Setup:** LegalPass/SafetyPass/Base Core objects; existing facade2relative imports and shared-shim3test imports.

**Действие:** Switch actual facade, instantiate registry/config/plugin; monkeypatch contract test; retire aliases only after decision.

**Oracle:** Public facade is same canonical object, actual validators work, duplicate pass_id guard preserved. Negative old paths only after window closure; other Scientist passes remain.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-HYG-02-03 → REQ-HYG-02-03

**Уровень:** E02-I12-A native Fabric→Lex. **Ожидается:** positive + negative + boundary.

**Setup:** Real small Parquet segments, actual typed manifest, requested columns/provenance; missing file and malformed index; supported historical manifest if available.

**Действие:** Actual Fabric load_world_facts→Lex select_sources in fresh process.

**Oracle:** Correct selected data/columns, shaped empty for no data; current readable-segment skip semantics retained; malformed index fails not empty. Access/provenance controls tested at real owner, mere provenance column not authority.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-HYG-02-04 → REQ-HYG-02-04

**Уровень:** installed protection census. **Ожидается:** positive + negative + boundary.

**Setup:** Shared Q2 artifact binding from DFK-01.

**Действие:** Inspect retired FQNs and protected exports in wheel/rebuilt installed prefix.

**Oracle:** lex.factlog and retired Scientist roots absent; Core/Fabric/root evidence/OPA and actual passes present. Missing origin receipt not PASS.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

## 7. Совместная приёмка, зависимости и владение

Общие сценарии: **E02-I12-A** из [канонического lane integration-контракта](../03_Интеграция/LANE-12.md). Они переиспользуются; отдельный тяжёлый harness этого пакета не создавать.

Исходные предшественники: нет. Доказанный существующий контракт может удовлетворить зависимость; lane не глобальный барьер.

LANE-12 производит actual build/distribution/census evidence с artifact binding. CYC-05 владеет positive build/deployment→N6 readiness bridge в existing confidence_ledger и runtime currentness; здесь не создавать второй issuer/registry. CP6 — одно общее окно Q2/package qualification, не build на каждый alias. DFK-01 shared census, no duplicate installed oracle.

## 8. Совместимость и восстановление

Do not rewrite historical facts. Actual external facade obligations recorded before removal; forwarding identity preserved while needed. Public OPA facade not candidate retirement.

## 9. Free-grow и design decisions

- [North Star §2](../05_Основания/Архитектура/policy-design-causal-operating-system-north-star.md#2-everything-reduces-to-data--but-the-causal-structure-is-not-data) и [синтез §4](../05_Основания/Исследование/design_direction.md): общий действующий owner сохраняется, удаление исторического адреса не заменяет способность; новые compatible resources подключаются через существующий механизм.

## 10. Решения, которые нельзя подменить догадкой

- DEC-HYG-02-01: helper finite census and exact external obligations; DEC-HYG-02-02: governance supported window after actual facade/config migration. Outputs include changed consumers and negative-test activation criteria; no historical date guessed.

## 11. Что предъявить и что не является готовностью

Lifecycle migration substantive, не просто rerun tests. Reader repair acceptance не authenticity/currentness/legal source proof.

**Команды:** из `policy-engine/` использовать существующее поддержанное Python 3.14 окружение и точные существующие test paths выше. Шаблон: `<existing-python> -m pytest <selected-existing-path> <new-selector-after-authoring>`; это не выполненная команда и не утверждение, что будущий selector уже существует. Native job — один по общему ресурсу. Никаких install/full-suite по умолчанию.

## 12. Lossless inventory bindings

- `remaining:0368` → REQ-HYG-02-01; Finite helper decision includes computed/package obligations.
- `remaining:0369` → REQ-HYG-02-02; Update actual facade first, tests/negative after accepted exit.
- `remaining:0370` → REQ-HYG-02-03, REQ-HYG-02-04; Real Parquet/native context, не DataFrame adapter.
- `preserve:0596` → REQ-HYG-02-02; Canonical Core identity — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0597` → REQ-HYG-02-02, REQ-HYG-02-04; Actual Scientist passes/evidence — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0598` → REQ-HYG-02-03; Fabric world reader — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0599` → REQ-HYG-02-04; Negative retired roots — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0600` → REQ-HYG-02-04; Cross-producer root evidence — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0601` → REQ-HYG-02-04; Public OPA facade — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.

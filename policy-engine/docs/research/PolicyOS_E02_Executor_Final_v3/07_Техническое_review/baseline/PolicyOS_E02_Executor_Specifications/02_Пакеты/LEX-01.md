# LEX-01 — Структурная identity issue paths и честные impact topics

**LANE-11 · LA-017 · SHA `20d9009be21097bfbdc38a546a15cc60213b8ace`.**

**Статус:** исполнительская спецификация на последующую работу; требования и будущие тесты здесь не исполнены.

## 1. Практическая цель и тип работы

Не терять compliance transitions из-за slash collision и сохранить реальное правовое сравнение отдельно от количественного эффекта.

**Тип:** C123-R01 narrow identity fix; C123-G01 native compatibility; C123-G02 scoped domain validation.

Основания: [полный отчёт](../05_Основания/Аудит/02_Пакеты/LEX-01.md), [исходные карточки](../05_Основания/Аудит/05_Источники/LEX-01_исходные_строки.txt), [трассировка](../04_Трассировка/LEX-01.json).

## 2. Уже работает — сохранить

- Lex norm diff/compliance owners и исторические simulator aliases.
- Schema1.0 historical/unbound, opt-in1.1 selected binding и reader-first CLI.
- Candidate topics не measured effects; backend/context/jurisdiction limitations сохраняются.

## 3. Полная disposition исходных обязанностей и остатков

| ID | Действие | Требования | Почему |
|---|---|---|
| LA-017 | fix | REQ-LEX-01-01, REQ-LEX-01-02, REQ-LEX-01-03, REQ-LEX-01-04 | Смысловой move выполнен; identity residual и native/domain qualification остаются. |
| C123-R01 | fix | REQ-LEX-01-01 | Slash join теряет boundaries; не новый legal engine. |
| C123-G01 | qualify | REQ-LEX-01-02, REQ-LEX-01-03 | Helper reconciliation не actual selected CAS/CLI. |
| C123-G02 | qualify | REQ-LEX-01-04 | Сохранить честные limitations, при claim отдельно existing domain evidence, не invented numeric effect. |

## 4. Нормативные требования результата

**REQ-LEX-01-01.** Issue grouping должен сохранять границы и типы path segments; разные structural paths не становятся unchanged из-за одинакового slash display.

**REQ-LEX-01-02.** Norm diff/pass plan должны сохранять added/removed/modified/unchanged, issue multiset/severity и фактические compared NormPacks, не caller-substituted context.

**REQ-LEX-01-03.** Native selected1.1 reader/CLI должен сверять diff/manifest/counts/topics/issues перед display, сохраняя explicit1.0 historical compatibility и actual CAS identity.

**REQ-LEX-01-04.** Candidate impact topics должны оставаться qualitative unknown-direction suggestions; legal source/applicability/coverage и causal/economic effects требуют своих existing evidence owners.

## 5. Конкретное техническое решение — рекомендуемый способ

- В _group_issues заменить slash string key на immutable tuple of typed segments, например ((str,segment),(int,segment)); display formatting отдельно. Согласовать _issue_fingerprint: сейчас str(segment) теряет int/string distinction; сохранить historical profile и ввести explicit new identity profile только если emitted fingerprints меняются. Для narrow slash regression можно сначала исправить internal grouping без смены historical ID, но new typed identity contract должен иметь compatibility mapping.
- Не менять normpack/diff и pass plan ownership ради move: реальные current paths уже правильны. Preserve multiset sorting/severity и renderer topic wording.
- Selected reader/CLI existing guards квалифицировать native; causal effects передавать через существующие Scientist/Foundry evidence, не расширять Lex tag heuristic до фиктивного simulator.

**Существующие code/test owners:**
- [`src/polisyos/lex/legal_evaluation/impact_diff.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/lex/legal_evaluation/impact_diff.py).
- [`src/polisyos/lex/normpack/diff.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/lex/normpack/diff.py).
- [`src/polisyos/lex/simulator/cli.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/lex/simulator/cli.py).
- [`src/polisyos/core/components/_cli_lex.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/core/components/_cli_lex.py).
- [`tests/unit/remediation/test_lex_01.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_lex_01.py).
- [`tests/unit/remediation/test_lex_impact_semantics.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_lex_impact_semantics.py).
- [`tests/unit/lex/legal_evaluation/test_impact_diff.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/lex/legal_evaluation/test_impact_diff.py).
- [`tests/unit/lex/simulator/test_diff.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/lex/simulator/test_diff.py).

## 6. Локальные проверки — все NOT_RUN

### TEST-LEX-01-01 → REQ-LEX-01-01

**Уровень:** actual analyzer grouping. **Ожидается:** positive + negative + boundary.

**Setup:** Same code/message/severity; paths [norm_pack,n.income,a/b] и [norm_pack,n.income,a,b]; int1 vs string1; exact duplicate control.

**Действие:** Old/new issue grouping→compliance deltas, fingerprint/reconciliation.

**Oracle:** Разные typed paths дают removed+added transitions, не empty delta; exact duplicates сохраняют multiplicity/severity. Display slash не identity; historical fingerprint profile не silently changed.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-LEX-01-02 → REQ-LEX-01-02, REQ-LEX-01-04

**Уровень:** real NormPack/AST pass. **Ожидается:** positive + negative + boundary.

**Setup:** Unchanged/added/removed/modified; income2 old rule>=1,new>=3; caller injects foreign norm_pack.

**Действие:** Actual analyzer and LegalPass; empty/deduplicated/invalid pass plans; stub control.

**Oracle:** Compared packs govern result, new blocker expected; unchanged failing rule no false transition. Stub honestly not evaluated; custom backend not source-authorized by label.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-LEX-01-03 → REQ-LEX-01-03

**Уровень:** E02-I11-C native CAS/CLI. **Ожидается:** positive + negative + boundary.

**Setup:** Historical1.0 and opt-in1.1, actual store/manifest/diff ref, fresh CLI.

**Действие:** Persist→read→render; tamper count/topic/issue/source; rollback reader profile.

**Oracle:** Fresh reader rejects mismatch before display, valid output useful; self-reference omission and bytes/refs match actual store. Legacy1.0 remains readable/unbound; report_id not content hash.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-LEX-01-04 → REQ-LEX-01-04

**Уровень:** public meaning/domain boundary. **Ожидается:** positive + negative + boundary.

**Setup:** OBLIGATION/PROHIBITION/other tags, missing jurisdiction/backend/source coverage; existing causal evidence reference if quantitative request.

**Действие:** Render report and route quantitative request to existing Scientist/Foundry owner.

**Oracle:** Candidate topics, direction unknown, not measured explicit. No effect number from tag. Actual source/context/coverage absence restricts legal claim, not comparison computation; no invented external law corpus.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

## 7. Совместная приёмка, зависимости и владение

Общие сценарии: **E02-I11-C** из [канонического lane integration-контракта](../03_Интеграция/LANE-11.md). Они переиспользуются; отдельный тяжёлый harness этого пакета не создавать.

Исходные предшественники: нет. Доказанный существующий контракт может удовлетворить зависимость; lane не глобальный барьер.

Existing Lex comparison owner; no transfer of legal logic to Foundry. Quantitative downstream contract separate; MOVE-21 already applied.

## 8. Совместимость и восстановление

Historical report IDs/schema1.0/1.1 не переписывать. Internal grouping fix separate from versioned fingerprint semantics; old reader supports old identity, new profile requires declared migration. Conservative rollback preserves legacy read, not silent loss of new transitions.

## 9. Free-grow и design decisions

- [Stage-0 §4.3](../05_Основания/Архитектура/stage0-custody-kernel-ratification.md#43-k06--fail-closed-binds-the-protected-action-not-the-computation) и [синтез §4](../05_Основания/Исследование/design_direction.md): защищённый claim ограничивается своим основанием; useful diagnostic computation не блокируется целиком.
- [North Star §2](../05_Основания/Архитектура/policy-design-causal-operating-system-north-star.md#2-everything-reduces-to-data--but-the-causal-structure-is-not-data): causal structure не выводится из названия impact topic.

## 10. Решения, которые нельзя подменить догадкой

- DEC-LEX-01-01: finite fingerprint/report reader census; выбрать internal-only slash fix с explicit typed-fingerprint follow-through либо versioned typed path identity. Критерии: no boundary/type collision, immutable historical bytes, fresh reconciliation поддерживает declared profile.

## 11. Что предъявить и что не является готовностью

Structural regression + actual CAS/read-first display. Repair acceptance не legal advice/coverage или measured economic effect validation.

**Команды:** из `policy-engine/` использовать существующее поддержанное Python 3.14 окружение и точные существующие test paths выше. Шаблон: `<existing-python> -m pytest <selected-existing-path> <new-selector-after-authoring>`; это не выполненная команда и не утверждение, что будущий selector уже существует. Native job — один по общему ресурсу. Никаких install/full-suite по умолчанию.

## 12. Lossless inventory bindings

- `remaining:0390` → REQ-LEX-01-01; Slash join теряет boundaries; не новый legal engine.
- `remaining:0391` → REQ-LEX-01-02, REQ-LEX-01-03; Helper reconciliation не actual selected CAS/CLI.
- `remaining:0392` → REQ-LEX-01-04; Сохранить честные limitations, при claim отдельно existing domain evidence, не invented numeric effect.
- `preserve:0627` → REQ-LEX-01-02; Lex norm diff/compliance ownership — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0628` → REQ-LEX-01-03; Historical aliases and schema1.0 — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0629` → REQ-LEX-01-03; Explicit opt-in1.1 selected binding — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0630` → REQ-LEX-01-03; Reader-first CLI — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0631` → REQ-LEX-01-04; Candidate topics not measured effects — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0632` → REQ-LEX-01-04; Backend/context/jurisdiction limitations — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.

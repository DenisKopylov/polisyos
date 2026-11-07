# DFK-01 — Конечные lifecycle решения трёх schema surfaces и installed evidence

**LANE-12 · LA-005, LA-006, LA-026, LA-027 · SHA `20d9009be21097bfbdc38a546a15cc60213b8ace`.**

**Статус:** исполнительская спецификация на последующую работу; требования и будущие тесты здесь не исполнены.

## 1. Практическая цель и тип работы

Завершить точную очистку legacy addresses, сохранив работающие schema/evolution/migration/materialization contracts.

**Тип:** C124-G01 lifecycle; G02 installed/native qualification; G03 preservation qualification, R нет.

Основания: [полный отчёт](../05_Основания/Аудит/02_Пакеты/DFK-01.md), [исходные карточки](../05_Основания/Аудит/05_Источники/DFK-01_исходные_строки.txt), [трассировка](../04_Трассировка/DFK-01.json).

## 2. Уже работает — сохранить

- LA-006 mechanisms tombstone уже отсутствует, negative tests сохраняются.
- LK03 ABI reference registry, LK10 materialize planner, LK25 deterministic graph migrations не placeholders.
- Canonical classes/evolution и honest partial census: unsupported/ignored/unknown не zero.

## 3. Полная disposition исходных обязанностей и остатков

| ID | Действие | Требования | Почему |
|---|---|---|
| LA-005 | lifecycle | REQ-DFK-01-01, REQ-DFK-01-05 | Три DTO остаются; finite decision вместо предположенного удаления. |
| LA-006 | qualify | REQ-DFK-01-02, REQ-DFK-01-04 | Tombstone отсутствует; не удалять negative tests. |
| LA-026 | lifecycle | REQ-DFK-01-01, REQ-DFK-01-02, REQ-DFK-01-05 | Descriptor3fields не generator; не создавать новый ради имени. |
| LA-027 | lifecycle | REQ-DFK-01-01, REQ-DFK-01-02, REQ-DFK-01-05 | Alias identity есть; адресная миграция, не перенос registry. |
| C124-G01 | lifecycle | REQ-DFK-01-01 | Три независимые decisions, неизвестность одного не блокирует другие. |
| C124-G02 | qualify | REQ-DFK-01-03, REQ-DFK-01-04 | Existing census/Q2 oracle actual profile. |
| C124-G03 | qualify | REQ-DFK-01-02, REQ-DFK-01-05 | Preserve useful owners, native/historical boundary отдельно. |

## 4. Нормативные требования результата

**REQ-DFK-01-01.** Для foundry.domain.schema трёх DTO, kernel.schemas.codegen descriptor и kernel.pipeline.schemas aliases должны быть отдельные конечные consumer/lifecycle dispositions с конкретным owner/exit criterion.

**REQ-DFK-01-02.** Retired mechanisms package/reexports должны отсутствовать в source и установленной distribution; никакая очистка не удаляет canonical registry/evolution/migrations/materialize/ABI owners.

**REQ-DFK-01-03.** Native census должен связывать exact Git denominator и прочитанные bytes, exclusions/unsupported/computed loaders с partial status; ACTIVE discovery не разрешает retirement.

**REQ-DFK-01-04.** Wheel→sdist→rebuilt wheel и non-editable installed consumer должны предъявить actual artifact/source/origin binding; skipped missing profile не installed PASS.

**REQ-DFK-01-05.** Canonical schema capability и обнаруженные historical inputs должны сохранять свой реальный contract, без automatic migration данных от смены import address.

## 5. Конкретное техническое решение — рекомендуемый способ

- C124-G01 сначала finite census точных surfaces. Для LA-005 migrate реально используемые fields к existing plugin config или fixture; если consumers отсутствуют в согласованной поддержанной области — удалить точный file. Для LA-026 retain descriptor у actual registry owner только если доказан contract, иначе удалить; generator не строить. LA-027 переключить found consumers на kernel.schemas, снять alias после реального compatibility window.
- Existing schema_fqn_census v3 и test_e02_installed_census_contract — reuse. Зафиксировать partial reasons, receipt exact files/read bytes; no wildcard exemption для unsupported. Q2 build-chain/origin invariant source-owned, этот packet его consumer, не installer framework.
- Product changes только принятые lifecycle deltas или reproduced mismatch. Сохранить registry/evolution/migrations и ABI/materialize отдельно от legacy files.

**Существующие code/test owners:**
- [`src/polisyos/foundry/domain/schema.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/domain/schema.py).
- [`src/polisyos/data_forge/kernel/schemas/codegen.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/data_forge/kernel/schemas/codegen.py).
- [`src/polisyos/data_forge/kernel/pipeline/schemas/__init__.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/data_forge/kernel/pipeline/schemas/__init__.py).
- [`src/polisyos/data_forge/kernel/schemas/registry.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/data_forge/kernel/schemas/registry.py).
- [`src/polisyos/data_forge/kernel/schemas/evolution.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/data_forge/kernel/schemas/evolution.py).
- [`src/polisyos/data_forge/kernel/schemas/migrations.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/data_forge/kernel/schemas/migrations.py).
- [`tools/quality/validation/schema_fqn_census.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tools/quality/validation/schema_fqn_census.py).
- [`tests/unit/remediation/test_dfk_01.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_dfk_01.py).
- [`tests/unit/foundry/hygiene/test_no_compat_facade_imports.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/hygiene/test_no_compat_facade_imports.py).
- [`tests/unit/data_forge/test_phase7_schema_quality_observability.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/data_forge/test_phase7_schema_quality_observability.py).
- [`tests/repo_quality/tools/test_e02_installed_census_contract.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/repo_quality/tools/test_e02_installed_census_contract.py).

## 6. Локальные проверки — все NOT_RUN

### TEST-DFK-01-01 → REQ-DFK-01-01, REQ-DFK-01-03

**Уровень:** finite census + lifecycle acceptance. **Ожидается:** positive + negative + boundary.

**Setup:** Exact3surfaces/all DTO/helper symbols; source/config/relative/string/generated/file-loader/package/historical inventory.

**Действие:** Existing schema_fqn_census plus targeted review of unsupported/computed/external obligations.

**Oracle:** Each surface has retain-with-owner+exit-condition, migrate-known-consumers+remove, либо explicit unresolved external obligation. No universal no-client claim. Distinct other AgentType/SimulationConfig не mistaken caller; output не count-only.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-DFK-01-02 → REQ-DFK-01-02, REQ-DFK-01-05

**Уровень:** canonical native behavior. **Ожидается:** positive + negative + boundary.

**Setup:** Actual registry versions/evolution rules, branching graph with two equal-length paths, materialize missing/cycle controls.

**Действие:** Existing schema tests and canonical classes; old alias if retained.

**Oracle:** Identity same; graph chooses low→vialow independent registration order, duplicate edge refuses. Existing shallow copy/no auto-stamp retained. Materialize binds callable/plans dependencies; ABI registry refs retained. No universal schema inclusion theorem.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-DFK-01-03 → REQ-DFK-01-02, REQ-DFK-01-03, REQ-DFK-01-04

**Уровень:** E02-I12-A Q2 installed. **Ожидается:** positive + negative + boundary.

**Setup:** Actual source Git pinned, wheel/sdist/rebuilt wheel, prefix outside checkout, existing origin gate/binding.

**Действие:** Existing installed census test + native CLI, inspect resources/negative FQNs and exact bytes.

**Oracle:** Retired paths absent each artifact; canonical resources present; actual executed files originate installed distribution and reconcile hashes. Missing binding SKIP/NOT_RUN, never PASS; partial unsupported stays partial.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-DFK-01-04 → REQ-DFK-01-05

**Уровень:** historical/native consumer. **Ожидается:** positive + negative + boundary.

**Setup:** Only discovered supported historical DTO/descriptor inputs; native JAX economics consumer where applicable.

**Действие:** Roundtrip/converter at actual owner and current scenario.

**Oracle:** Actual retained semantics match declared converter; unknown archives not claimed tested. Unused DTO not relocated into common contracts; valid scientific consumer remains usable.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

## 7. Совместная приёмка, зависимости и владение

Общие сценарии: **E02-I12-A** из [канонического lane integration-контракта](../03_Интеграция/LANE-12.md). Они переиспользуются; отдельный тяжёлый harness этого пакета не создавать.

Исходные предшественники: нет. Доказанный существующий контракт может удовлетворить зависимость; lane не глобальный барьер.

LANE-12 производит actual build/distribution/census evidence с artifact binding. CYC-05 владеет positive build/deployment→N6 readiness bridge в existing confidence_ledger и runtime currentness; здесь не создавать второй issuer/registry. CP6 — одно общее окно Q2/package qualification, не build на каждый alias.

## 8. Совместимость и восстановление

Historical payloads immutable; exact converter/window only for found supported contract. Retained aliases narrow identity forwarding, no duplicate model. Tombstone absence remains independent of pending DTO retirement.

## 9. Free-grow и design decisions

- [North Star §2](../05_Основания/Архитектура/policy-design-causal-operating-system-north-star.md#2-everything-reduces-to-data--but-the-causal-structure-is-not-data) и [синтез §4](../05_Основания/Исследование/design_direction.md): общий действующий owner сохраняется, удаление исторического адреса не заменяет способность; новые compatible resources подключаются через существующий механизм.

## 10. Решения, которые нельзя подменить догадкой

- DEC-DFK-01-01/02/03: separate finite outcome for DTO file, descriptor, pipeline alias. Required outputs: caller evidence/exclusions, supported external obligation, chosen action, owner and objective exit condition; unknown obligation remains named, no invented sunset.

## 11. Что предъявить и что не является готовностью

Source lifecycle decisions и actual installed proof separately. Census не retirement authorization; canonical tests не universal JSON Schema algebra или empirical model validation.

**Команды:** из `policy-engine/` использовать существующее поддержанное Python 3.14 окружение и точные существующие test paths выше. Шаблон: `<existing-python> -m pytest <selected-existing-path> <new-selector-after-authoring>`; это не выполненная команда и не утверждение, что будущий selector уже существует. Native job — один по общему ресурсу. Никаких install/full-suite по умолчанию.

## 12. Lossless inventory bindings

- `remaining:0365` → REQ-DFK-01-01; Три независимые decisions, неизвестность одного не блокирует другие.
- `remaining:0366` → REQ-DFK-01-03, REQ-DFK-01-04; Existing census/Q2 oracle actual profile.
- `remaining:0367` → REQ-DFK-01-02, REQ-DFK-01-05; Preserve useful owners, native/historical boundary отдельно.
- `preserve:0590` → REQ-DFK-01-02, REQ-DFK-01-05; Canonical classes identity — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0591` → REQ-DFK-01-02, REQ-DFK-01-05; Schema registry/evolution — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0592` → REQ-DFK-01-02; Deterministic graph migrations — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0593` → REQ-DFK-01-02, REQ-DFK-01-04; Negative retired-FQN tests — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0594` → REQ-DFK-01-02; Materialize and ABI reference owners — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0595` → REQ-DFK-01-03; Honest partial census — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.

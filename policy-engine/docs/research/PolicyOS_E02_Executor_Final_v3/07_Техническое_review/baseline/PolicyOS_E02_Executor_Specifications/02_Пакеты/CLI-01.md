# CLI-01 — Безопасные wire names и AST-based package architecture gate

**LANE-12 · LA-043, LA-044 · SHA `20d9009be21097bfbdc38a546a15cc60213b8ace`.**

**Статус:** исполнительская спецификация на последующую работу; требования и будущие тесты здесь не исполнены.

## 1. Практическая цель и тип работы

Генерировать один полезный public client из выбранного OpenAPI и проверять реальную import surface без false positives строк.

**Тип:** C127-R01/R02 fix; G01 frozen native generation; G02 actual service/external qualification.

Основания: [полный отчёт](../05_Основания/Аудит/02_Пакеты/CLI-01.md), [исходные карточки](../05_Основания/Аудит/05_Источники/CLI-01_исходные_строки.txt), [трассировка](../04_Трассировка/CLI-01.json).

## 2. Уже работает — сохранить

- Canonical public types/operations, private raw handoff, LK22 canonicalizer/recursive normalizer.
- Package-pinned openapi-typescript7.13.0, three-output family, LK21 existing freshness/UNRUN, dashboard formatting profile.
- Binary/exposure/header/body/error transport и LK16/LK23 shell/styleguide roles.

## 3. Полная disposition исходных обязанностей и остатков

| ID | Действие | Требования | Почему |
|---|---|---|
| LA-043 | fix | REQ-CLI-01-01, REQ-CLI-01-02, REQ-CLI-01-03, REQ-CLI-01-05 | Raw retirement done; custom name/gate defects and native consumers remain. |
| LA-044 | qualify | REQ-CLI-01-02, REQ-CLI-01-04, REQ-CLI-01-05 | Package dependency ownership done; native frozen/profile proof required. |
| C127-R01 | fix | REQ-CLI-01-01 | Existing safe accessor использовать для path/query, no per-endpoint patches. |
| C127-R02 | fix | REQ-CLI-01-02 | Regex читает fixture strings, exact surface stale; no allow-all. |
| C127-G01 | qualify | REQ-CLI-01-03, REQ-CLI-01-04 | Real3-output family/tools, no fixture freshness claim. |
| C127-G02 | qualify | REQ-CLI-01-05 | Actual service/auth/resource and finite external compatibility. |

## 4. Нормативные требования результата

**REQ-CLI-01-01.** TS/JS path/query generation должна безопасно адресовать допустимые non-identifier wire names, сохраняя точные keys и encoding; malformed/unrepresentable input отказывает явно.

**REQ-CLI-01-02.** Package architecture check должен проверять настоящие import/export/dynamic-import syntax и exact allowed surface, не import-like text внутри строк/комментариев/templates.

**REQ-CLI-01-03.** Один selected OpenAPI должен породить ровно types.ts/canonicalRuntimeApiClient.ts/js через private raw handoff; freshness различает measured clean, drift и UNRUN.

**REQ-CLI-01-04.** Native pinned package tooling, canonicalizer/recursive types и dashboard formatting должны сохранять public type/runtime contract без dashboard runtime dependency.

**REQ-CLI-01-05.** Existing generated-client→Runtime service bridge должен проверять actual request/resource/auth/currentness boundaries; transport fixtures и bytes не authority, external raw imports требуют конечного compatibility решения.

## 5. Конкретное техническое решение — рекомендуемый способ

- В generate_runtime_client.py path substitutions использовать _typescript_param_access(name); query object keys json.dumps(name), JS optional access helper поддерживает params?.[quoted] либо params?.identifier. TS params required access existing shape. Для literal path text безопасно экранировать backtick/backslash/${ или собирать quoted string segments+encoded values, не интерполировать raw OpenAPI text как executable template. Один общий helper для TS/JS, no endpoint special cases.
- В check-architecture.mjs использовать уже package-owned TypeScript parser (createSourceFile) для ImportDeclaration/ExportDeclaration(moduleSpecifier)/ImportEquals и import() literal; обход AST видит interpolation expression, но не строковый payload. Nonliteral dynamic imports explicitly unsupported/violation по narrow contract. Обновить allowed files ровно actual generate-openapi-types pair и import lists typescript/node:path/openapi-typescript; checker own typescript import учесть. Не добавлять runtime dependency в public client.
- Existing full-family generator/guardrails остаются owners. Не удалять canonicalizer/normalizer и не возвращать committed raw. Frozen provisioning если требуется — отдельный согласованный CP6 execution, не в этой authoring фазе. Native Node22 test profile, не observed Node24.

**Существующие code/test owners:**
- [`tools/ops_runners/runtime/generate_runtime_client.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tools/ops_runners/runtime/generate_runtime_client.py).
- [`packages/runtime-api-client/scripts/check-architecture.mjs`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/packages/runtime-api-client/scripts/check-architecture.mjs).
- [`packages/runtime-api-client/scripts/generate-runtime-api-client.sh`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/packages/runtime-api-client/scripts/generate-runtime-api-client.sh).
- [`packages/runtime-api-client/scripts/generate-openapi-types.mjs`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/packages/runtime-api-client/scripts/generate-openapi-types.mjs).
- [`packages/runtime-api-client/scripts/canonicalize-runtime-client.mjs`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/packages/runtime-api-client/scripts/canonicalize-runtime-client.mjs).
- [`packages/runtime-api-client/scripts/normalize-recursive-openapi-types.mjs`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/packages/runtime-api-client/scripts/normalize-recursive-openapi-types.mjs).
- [`packages/runtime-api-client/runtimeApiClient.test.mjs`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/packages/runtime-api-client/runtimeApiClient.test.mjs).
- [`packages/runtime-api-client/runtimeApiClient.type-test.ts`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/packages/runtime-api-client/runtimeApiClient.type-test.ts).
- [`packages/runtime-api-client/remediation.test.mjs`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/packages/runtime-api-client/remediation.test.mjs).
- [`tools/ops_runners/runtime/check_runtime_api_contract.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tools/ops_runners/runtime/check_runtime_api_contract.py).
- [`tools/devx/architecture/guardrails.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tools/devx/architecture/guardrails.py).
- [`tests/integration/runtime_frontend/test_runtime_client_contract_bridge.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/integration/runtime_frontend/test_runtime_client_contract_bridge.py).

## 6. Локальные проверки — все NOT_RUN

### TEST-CLI-01-01 → REQ-CLI-01-01

**Уровень:** actual raw + canonical custom OpenAPI. **Ожидается:** positive + negative + boundary.

**Setup:** GET path{item-id}, query filter-mode, identifier controls item_id/filter_mode, header X-Trace-ID; quoted/backslash names and template delimiters in literal path negative/escaping controls.

**Действие:** Generate raw TS/JS→actual canonical pipeline; Node parse/call with local recording fetch, tsc.

**Oracle:** No SyntaxError/ReferenceError; path value a/b encoded a%2Fb, query key exactly filter-mode/value preserved. Quoted keys/access safe, no template interpolation from wire text. Existing identifier corpus stable except intentional formatting.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-CLI-01-02 → REQ-CLI-01-02

**Уровень:** architecture parser regression. **Ожидается:** positive + negative + boundary.

**Setup:** Legitimate generate-openapi-types.mjs/test; string/template/comment import decoys; real forbidden import/dynamic import/reexport.

**Действие:** Registered node scripts/check-architecture.mjs on actual package and isolated mutated copies.

**Oracle:** Current legitimate surface passes; decoys ignored; real forbidden dependency/export/unknown computed load receives explicit violation. Raw committed pair/extra file still denied, not broad exemption.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-CLI-01-03 → REQ-CLI-01-03, REQ-CLI-01-04

**Уровень:** E02-I12-B native full family. **Ожидается:** positive + negative + boundary.

**Setup:** Node22/Python3.14, actual frozen lock dependencies, custom/default OpenAPI, isolated output root.

**Действие:** Existing shell/check_runtime_api_contract/general guardrails; corrupt/miss each3output, addextra, force unavailable generator.

**Oracle:** Exactly3public outputs; private raw cleaned; same input all stages. Clean0/drift1/UNRUN2 per current checker; no worktree escape; dashboard own formatter separately. Repeat canonicalization idempotent, collision and recursive unguarded cycle refuse.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-CLI-01-04 → REQ-CLI-01-04, REQ-CLI-01-05

**Уровень:** public native transport/types. **Ожидается:** positive + negative + boundary.

**Setup:** Existing canonical runtimeApiClient.test/type-test and normalizer/canonicalizer tests; minimal consumer no dashboard runtime.

**Действие:** Run selected package scripts on supported toolchain; binary exposure and discriminated aliases.

**Oracle:** Public imports/types valid; supplied headers/body/query/error and arrayBuffer/exposure bytes preserved. Package resolves own tool7.13.0 from lock, no version upgrade; formatter profiles not assumed byte-identical.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-CLI-01-05 → REQ-CLI-01-05

**Уровень:** existing service bridge. **Ожидается:** positive + negative + boundary.

**Setup:** tests/integration/runtime_frontend/test_runtime_client_contract_bridge.py with local actual Runtime test service and scoped auth fixtures.

**Действие:** Generated client calls allowed selected routes; denied/missing-resource/stale-context negatives; external import census.

**Oracle:** Actual service enforces auth/resource/currentness independently; client conveys status/limitation, no fabricated permission. Selected POST allowlist remains scope;103operation census not103executions. No external deployment/action performed.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

## 7. Совместная приёмка, зависимости и владение

Общие сценарии: **E02-I12-B** из [канонического lane integration-контракта](../03_Интеграция/LANE-12.md). Они переиспользуются; отдельный тяжёлый harness этого пакета не создавать.

Исходные предшественники: нет. Доказанный существующий контракт может удовлетворить зависимость; lane не глобальный барьер.

LANE-12 производит actual build/distribution/census evidence с artifact binding. CYC-05 владеет positive build/deployment→N6 readiness bridge в existing confidence_ledger и runtime currentness; здесь не создавать второй issuer/registry. CP6 — одно общее окно Q2/package qualification, не build на каждый alias. CLI-01 owns generator/gate changes; HYG-04 consumes same build evidence; no third checker.

## 8. Совместимость и восстановление

Current public canonical operation/type surface remains; custom wire names corrected. Historical external raw filesystem imports require named window/route, not raw resurrection by default. Lock ownership/profile unchanged; unknown dynamic imports explicit not silently ignored.

## 9. Free-grow и design decisions

- [North Star §2](../05_Основания/Архитектура/policy-design-causal-operating-system-north-star.md#2-everything-reduces-to-data--but-the-causal-structure-is-not-data) и [синтез §4](../05_Основания/Исследование/design_direction.md): общий действующий owner сохраняется, удаление исторического адреса не заменяет способность; новые compatible resources подключаются через существующий механизм.

## 10. Решения, которые нельзя подменить догадкой

- DEC-CLI-01-01: finite external/filesystem raw-import census; choose migration instruction or narrow supported bridge only for actual obligation, no universal-client promise. AST checker dynamic loading policy bounded to actual package needs.

## 11. Что предъявить и что не является готовностью

R01 actual generation+execution and R02 positive/negative gate. Native regeneration/type/service proof separately. Transport output does not assert authority/verified policy ranking.

**Команды:** из `policy-engine/` использовать существующее поддержанное Python 3.14 окружение и точные существующие test paths выше. Шаблон: `<existing-python> -m pytest <selected-existing-path> <new-selector-after-authoring>`; это не выполненная команда и не утверждение, что будущий selector уже существует. Native job — один по общему ресурсу. Никаких install/full-suite по умолчанию.

## 12. Lossless inventory bindings

- `remaining:0454` → REQ-CLI-01-01; Existing safe accessor использовать для path/query, no per-endpoint patches.
- `remaining:0455` → REQ-CLI-01-02; Regex читает fixture strings, exact surface stale; no allow-all.
- `remaining:0456` → REQ-CLI-01-03, REQ-CLI-01-04; Real3-output family/tools, no fixture freshness claim.
- `remaining:0457` → REQ-CLI-01-05; Actual service/auth/resource and finite external compatibility.
- `preserve:0750` → REQ-CLI-01-01, REQ-CLI-01-04; Canonical public client/DTO aliases — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0751` → REQ-CLI-01-03; Private raw handoff — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0752` → REQ-CLI-01-03, REQ-CLI-01-04; Canonicalizer and recursive normalizer — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0753` → REQ-CLI-01-04; Package-pinned toolchain — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0754` → REQ-CLI-01-03; Three-output freshness/UNRUN — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0755` → REQ-CLI-01-03, REQ-CLI-01-04; Dashboard formatting profile — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0756` → REQ-CLI-01-04, REQ-CLI-01-05; Binary/exposure transport tests — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.

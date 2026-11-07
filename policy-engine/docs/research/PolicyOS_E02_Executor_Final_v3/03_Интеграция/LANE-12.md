# LANE-12: общий интеграционный контракт

**Цель:** Доставленный пакет и generated client имеют те же контракты, что проверенный checkout; retirement не удаляет нужных исторических consumers.

Состояние проверок: **NOT_RUN**. Это обязательные критерии будущей связанной приёмки, а не свидетельство текущего PASS. Семейство запускается один раз для согласованного изменения; локальные packet tests не дублируют его инфраструктуру.

## Область и зависимости

Пакеты: DFK-01, HYG-02, HYG-04, CLI-01

- CP6 после согласованного candidate input set; краткие T1/T2/T3 и второй случай, а не повтор всех проверок.
- DFK-01/HYG-02 исходно CP2, HYG-04/CLI-01 CP6. Старые alias остаются ровно до установленного safe retirement.

## Профиль и допустимые подмены

- **P-CORE:** policy-engine Python >=3.14,<3.15; actual project lock/extras, supported existing environment; imports bind tested checkout/artifact (основание: policy-engine/pyproject.toml:8)
- **P-PACKAGING:** Supported Python3.14 artifact build/install plus Node22/corepack pnpm frozen existing toolchain; generated family/type/client/runtime; macOS/server qualifications separate (основание: AGENTS.md; original sourceplan CP6; existing runtime_frontend owner)

- Контролируемая git-fixture для census, test service tenant и tmp storage; содержательные installed imports/generator/typecheck/client не подменяются.
- Server-specific unavailable profile остаётся отдельным результатом; Mac не аттестует Linux/server.

Подмена запрещена для принимаемого свойства: если проверяется запись/чтение, actual store и fresh reader обязательны; если численный метод — actual backend; если physical cleanup — actual OS resource. Внешний provider/encoder может быть лёгким и контролируемым, когда качество модели/сети не входит в claim.

## Подготовка и порядок

1. На выбранном поддерживаемом профиле связать checkout/build SHA и входные fixtures. Использовать существующие test owners ниже, прочитать их реальные seams перед расширением
2. Выполнить локальные REQ/TEST затронутых пакетов, затем каждый применимый вариант этого семейства. Независимые варианты допускают раздельный запуск
3. Положительный прогон должен пройти actual producer→передача/хранение→fresh consumer. При отсутствии хранения в конкретном алгоритме проверить непосредственный downstream consumer, не придумывая CAS ради отчётности
4. Повторить адресный негативный/граничный контроль. Изменение одного deciding input или отключение исправленного механизма должно менять наблюдаемый исход; unrelated пригодный результат остаётся доступным
5. Сохранить входы, события/значения/ошибки, ref identities, численные tolerances и команды. Итог связывает покрытые REQ, а не только список пакетных имён

## E02-I12-A — Finite consumer census → installed profile → compatibility

Покрываемая область: DFK-01, HYG-02, HYG-04

**Положительный oracle:** Именованный полный denominator включает imports/FQN/loaders/configs/generated/public surfaces; supported historical aliases сохраняют identity/bytes. Installed imports и четыре bootstrap profiles проверяются в настоящем wheel/sdist контексте.

**Различающий негативный oracle:** Необнаруженный индексным grep consumer не объявляется отсутствующим; required facade не удаляется при compatibility_pending. Invalid-byte/rename/untracked paths не исчезают из census; лишний import не запускает чужой тяжёлый subsystem.

**Приёмка:** предъявить оба исхода на одной объявленной модели/профиле с изменением только deciding условия. Точные локальные counterexamples и expected values берутся из связанных TEST соответствующих пакетов; совпадение summary без фактического потребления не принимается. Если метод стохастический, заранее указать seed/replica/ошибку сравнения, не подбирать tolerance после результата.

## E02-I12-B — Schema owner → generation → TS client → runtime

Покрываемая область: CLI-01

**Положительный oracle:** Actual package generator/private raw handoff даёт типизируемый client; generated call достигает runtime control service и сохраняет public DTO, errors/nullable fields/truth semantics. Generated JavaScript использует безопасные computed data keys/entries и own-property presence для __proto__/constructor/toString и non-identifier keys. Один local transport harness сохраняет actual service request/response envelopes и возвращает тот же service response через generated client decoder; GET и доступный allowlisted POST/binary профиль рассматриваются отдельно.

**Различающий негативный oracle:** Custom path/query names с недопустимым JS identifier не ломают client; drift schema/type/route и architecture contract дают различающий отказ, а не ослабление gates. Генерация без реального consumer call недостаточна. Inherited optional properties не отправляются; quoted __proto__ object literal недостаточен. Fake JS200 плюс отдельный Python GET не roundtrip; mutation response status/body/header, deny/missing/stale branch различается без blacklist допустимых endpoint names.

**Приёмка:** предъявить оба исхода на одной объявленной модели/профиле с изменением только deciding условия. Точные локальные counterexamples и expected values берутся из связанных TEST соответствующих пакетов; совпадение summary без фактического потребления не принимается. Если метод стохастический, заранее указать seed/replica/ошибку сравнения, не подбирать tolerance после результата.

## Существующие места расширения tests

Список означает проверенные пути, не доказательство полноты или запуска всего содержимого. Новые проверки добавлять к ближайшему владельцу; отдельный harness создавать только при реальном разрыве.

- [policy-engine/tests/repo_quality/tools/test_e02_installed_census_contract.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/repo_quality/tools/test_e02_installed_census_contract.py) — SHA256 `0d36dcb94628fde07f9857691fad718d25d34d1ab0c9afd045054de8e63d73f8`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.
- [policy-engine/tests/unit/foundry/hygiene/test_no_compat_facade_imports.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/hygiene/test_no_compat_facade_imports.py) — SHA256 `8597717d4d8e24d3a0fd6d882a6c7159f927e556d9448031193213986752f50a`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.
- [policy-engine/tests/unit/common/jax_env/test__policy.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/common/jax_env/test__policy.py) — SHA256 `bb25d1f8c0aedd0f762f1686c81b869468f027acf1788adf6a3cb8456b43713c`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.
- [policy-engine/tests/unit/runtime/http/test_runtime_api_contract_hardening.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/runtime/http/test_runtime_api_contract_hardening.py) — SHA256 `71358209e73aef26da41db78c7d89eb864643bb4eb96e8cbca22fa4f829caf32`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.
- [policy-engine/tests/integration/runtime_frontend/test_runtime_client_contract_bridge.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/integration/runtime_frontend/test_runtime_client_contract_bridge.py) — SHA256 `759722a3d2f6e7fdad9937dfec423e7cf9737ac5e6551d865ab622d82b0086cc`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.

## Выход приёмки

- Один manifest исполнения семейства: base/head SHA, scenario-ID, связанные REQ/TEST, профиль, входы и их hash, actual commands/exit, фактические positive/negative oracles, ограничения
- Перечень doubles с объяснением, какое свойство ими не проверяется
- Для failure/unknown: точная стадия и сохранённый полезный результат. Не перекрашивать BLOCKED/UNRUN в PASS
- Ремонт механизма и предметная валидность имеют разные решения. Синтетический механизм может пройти, не подтверждая прогноз/каузальную идентификацию/мандат реального кейса

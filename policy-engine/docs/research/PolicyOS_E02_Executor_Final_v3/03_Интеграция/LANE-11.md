# LANE-11: общий интеграционный контракт

**Цель:** Объяснение, monitoring и legal-impact projection сохраняют силу и ограничения утверждений и дают полезную диагностику, не подменяя институты.

Состояние проверок: **NOT_RUN**. Это обязательные критерии будущей связанной приёмки, а не свидетельство текущего PASS. Семейство запускается один раз для согласованного изменения; локальные packet tests не дублируют его инфраструктуру.

## Область и зависимости

Пакеты: BER-01, DDM-01, DDM-02, LEX-01

- DDM/BERL отдельные tiny scenarios, не один calibration backend с LANE-03/10.
- Fresh store/source clocks переиспользуют LANE-06; public projection проверяет не усиление истины из LANE-01/03/05.

## Профиль и допустимые подмены

- **P-CORE:** policy-engine Python >=3.14,<3.15; actual project lock/extras, supported existing environment; imports bind tested checkout/artifact (основание: policy-engine/pyproject.toml:8)

- Synthetic events/model transitions и локальный selected store; external institutional attestation fixture только как typed test input, не реальное полномочие.
- Никакой повторной дорогостоящей FP calibration ради import move; report/source/currentness validators и public consumer реальные.

Подмена запрещена для принимаемого свойства: если проверяется запись/чтение, actual store и fresh reader обязательны; если численный метод — actual backend; если physical cleanup — actual OS resource. Внешний provider/encoder может быть лёгким и контролируемым, когда качество модели/сети не входит в claim.

## Подготовка и порядок

1. На выбранном поддерживаемом профиле связать checkout/build SHA и входные fixtures. Использовать существующие test owners ниже, прочитать их реальные seams перед расширением
2. Выполнить локальные REQ/TEST затронутых пакетов, затем каждый применимый вариант этого семейства. Независимые варианты допускают раздельный запуск
3. Положительный прогон должен пройти actual producer→передача/хранение→fresh consumer. При отсутствии хранения в конкретном алгоритме проверить непосредственный downstream consumer, не придумывая CAS ради отчётности
4. Повторить адресный негативный/граничный контроль. Изменение одного deciding input или отключение исправленного механизма должно менять наблюдаемый исход; unrelated пригодный результат остаётся доступным
5. Сохранить входы, события/значения/ошибки, ref identities, численные tolerances и команды. Итог связывает покрытые REQ, а не только список пакетных имён

## E02-I11-A — BERL writer → strict wire profile → fresh reader

Покрываемая область: BER-01

**Положительный oracle:** Persisted explanation открывается выбранным свежим reader; effective alias dedup не удваивает вклад; useful explanation сохраняет basis и ограничения.

**Различающий негативный oracle:** Coercible wrong type/missing required/nested extra и permissive intake не проходят как valid persisted contract; raw score не превращается в stronger certainty.

**Приёмка:** предъявить оба исхода на одной объявленной модели/профиле с изменением только deciding условия. Точные локальные counterexamples и expected values берутся из связанных TEST соответствующих пакетов; совпадение summary без фактического потребления не принимается. Если метод стохастический, заранее указать seed/replica/ошибку сравнения, не подбирать tolerance после результата.

## E02-I11-B — Observation/report → DDM monitor → decision

Покрываемая область: DDM-01, DDM-02

**Положительный oracle:** Малые реальные event/model transitions сохраняют report/source/expiry/basis; valid declared R2 path допускается только при действительном contract. Historical FQN читается без скрытого нового owner. Source-backed calibration отличает calibration/holdout реальные artifact coordinates/time windows, а не labels: один stream не копируется во второй. Одинаковые values разных trusted observations допустимы. Raw quantile и actual/prepared-MBB method lineage различаются; declared MBB содержит связанный producer/index plan, включая действительный seed effect.

**Различающий негативный oracle:** Foreign-model shift/report, stale basis, R1/R0 и failed certificate не получают authority. Protective output и unresolved cause могут сохраняться; наблюдение не объявляется causal confirmation. Relabelled reused observations не дают независимого denominator; один source stream остаётся insufficient_holdout/unqualified, не получает synthetic certificate. Missing source допускает bounded research output, но не production qualification; В retained synthetic smoke holdout100 windows×4values задаёт100 window-level Bernoulli trials для Wilson arithmetic, не400 independent observations; повторение не доказывает независимость.

**Приёмка:** предъявить оба исхода на одной объявленной модели/профиле с изменением только deciding условия. Точные локальные counterexamples и expected values берутся из связанных TEST соответствующих пакетов; совпадение summary без фактического потребления не принимается. Если метод стохастический, заранее указать seed/replica/ошибку сравнения, не подбирать tolerance после результата.

## E02-I11-C — Norm/compliance diff → persisted impact → public view

Покрываемая область: LEX-01

**Положительный oracle:** Actual norms/compliance owners сохраняют issue path, severity и candidate topics; fresh JSON/Markdown содержат то же основание и denied uses.

**Различающий негативный oracle:** Slash grouping не теряет structural issue; default stub явно limited. Retrieval нормы и legal interpretation не доказывают relation/mandate и не расширяют полномочия PolicyOS.

**Приёмка:** предъявить оба исхода на одной объявленной модели/профиле с изменением только deciding условия. Точные локальные counterexamples и expected values берутся из связанных TEST соответствующих пакетов; совпадение summary без фактического потребления не принимается. Если метод стохастический, заранее указать seed/replica/ошибку сравнения, не подбирать tolerance после результата.

## Существующие места расширения tests

Список означает проверенные пути, не доказательство полноты или запуска всего содержимого. Новые проверки добавлять к ближайшему владельцу; отдельный harness создавать только при реальном разрыве.

- [policy-engine/tests/unit/berl/test_persisted_wire_profile.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/berl/test_persisted_wire_profile.py) — SHA256 `c45ab6836060fe66606a1a305127af2d6bfd722249fc0112c4c85b85b60ffda0`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.
- [policy-engine/tests/unit/ddm/test_contract_fresh_consumers.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/ddm/test_contract_fresh_consumers.py) — SHA256 `1d0d22a06c28bbdd550686e99ca767fe49573041fdeb496f806fbc70ca38c7d5`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.
- [policy-engine/tests/unit/ddm/test_full_acceptance.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/ddm/test_full_acceptance.py) — SHA256 `3925e7b8d3413e8df0d3b9e1a211251cd73dc90c8f1a6e772023fe4a6eeb3a41`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.
- [policy-engine/tests/unit/remediation/test_lex_impact_semantics.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_lex_impact_semantics.py) — SHA256 `0c95601db1785e7f0543ed25fa2f6e46cd86c15443e8e863d0b91617d330e2f0`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.

## Выход приёмки

- Один manifest исполнения семейства: base/head SHA, scenario-ID, связанные REQ/TEST, профиль, входы и их hash, actual commands/exit, фактические positive/negative oracles, ограничения
- Перечень doubles с объяснением, какое свойство ими не проверяется
- Для failure/unknown: точная стадия и сохранённый полезный результат. Не перекрашивать BLOCKED/UNRUN в PASS
- Ремонт механизма и предметная валидность имеют разные решения. Синтетический механизм может пройти, не подтверждая прогноз/каузальную идентификацию/мандат реального кейса

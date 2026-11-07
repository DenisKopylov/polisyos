# LANE-09: общий интеграционный контракт

**Цель:** Поиск источника и LLM assistance дают повторно используемые raw-backed результаты без выдуманных цитат и двойного списания.

Состояние проверок: **NOT_RUN**. Это обязательные критерии будущей связанной приёмки, а не свидетельство текущего PASS. Семейство запускается один раз для согласованного изменения; локальные packet tests не дублируют его инфраструктуру.

## Область и зависимости

Пакеты: SCL-01, SCL-03, LLM-01, LLM-02

- Raw snapshot handoff используется LANE-08 docs ingest и LANE-01 acquisition; common cache ledger/fencing LANE-06.

## Профиль и допустимые подмены

- **P-CORE:** policy-engine Python >=3.14,<3.15; actual project lock/extras, supported existing environment; imports bind tested checkout/artifact (основание: policy-engine/pyproject.toml:8)

- Fake HTTP/DNS/provider и deterministic LLM reply разрешены, сеть/платные вызовы не нужны для transport/custody correctness.
- Actual raw persistence, snippet extraction/validator, factory/cache/ledger и docs consumer должны быть реальными.
- Live retrieval quality и language understanding не объявляются доказанными этим deterministic test.

Подмена запрещена для принимаемого свойства: если проверяется запись/чтение, actual store и fresh reader обязательны; если численный метод — actual backend; если physical cleanup — actual OS resource. Внешний provider/encoder может быть лёгким и контролируемым, когда качество модели/сети не входит в claim.

## Подготовка и порядок

1. На выбранном поддерживаемом профиле связать checkout/build SHA и входные fixtures. Использовать существующие test owners ниже, прочитать их реальные seams перед расширением
2. Выполнить локальные REQ/TEST затронутых пакетов, затем каждый применимый вариант этого семейства. Независимые варианты допускают раздельный запуск
3. Положительный прогон должен пройти actual producer→передача/хранение→fresh consumer. При отсутствии хранения в конкретном алгоритме проверить непосредственный downstream consumer, не придумывая CAS ради отчётности
4. Повторить адресный негативный/граничный контроль. Изменение одного deciding input или отключение исправленного механизма должно менять наблюдаемый исход; unrelated пригодный результат остаётся доступным
5. Сохранить входы, события/значения/ошибки, ref identities, численные tolerances и команды. Итог связывает покрытые REQ, а не только список пакетных имён

## E02-I09-A — Scholar public search → raw snapshot → snippet → docs ingest

Покрываемая область: SCL-01, SCL-03

**Положительный oracle:** Empty/exception provider failover сохраняет non-URL sources; v1/cached v1/explicit v2 имеют правильный lineage. Каждый snippet восстанавливается из selected raw bytes/span; cache hit повторно применяет текущую политику допуска. Достаточный admitted cache hit после offline URL/domain/literal-IP/redirect/MIME/size policy checks и повторного чтения cached facts делает network0, включая DNS0. Live miss/refresh затем выполняет DNS/pin/peer/redirect SSRF guards.

**Различающий негативный oracle:** Invented snippet/shifted span/wrong-kind/foreign raw ref либо cache entry с теперь запрещённым destination отвергаются; no raw snapshot не восстанавливается из красивого summary. Changed offline policy отвергает прежний hit без сети; запрет live destination не обходится cache, но valid offline hit не требует доступности текущего DNS.

**Приёмка:** предъявить оба исхода на одной объявленной модели/профиле с изменением только deciding условия. Точные локальные counterexamples и expected values берутся из связанных TEST соответствующих пакетов; совпадение summary без фактического потребления не принимается. Если метод стохастический, заранее указать seed/replica/ошибку сравнения, не подбирать tolerance после результата.

## E02-I09-B — LLM factory → cache/single-flight → trace/ledger

Покрываемая область: LLM-01, LLM-02

**Положительный oracle:** Один controlled provider miss + hits оставляют один provider call, events каждого потребителя и корректную стоимость; waiter cancellation не уничтожает чужой результат. LLM-02 предъявляет strict finite six-role materialized TranslatorInputBundle → owner binder → scoped factory → actual PolicyTranslatorWorker consumer: exact closed input с literal URL/uncertainty notes даёт miss затем разрешённый hit без tool route.

**Различающий негативный oracle:** Scope/epoch/owner drift, retry/partial provider failure не превращаются в бесплатный authority result; повторный cache hit не возвращает stale admission. Сгенерированная интерпретация остаётся proposal. Incomplete/live/unresolved role или иной prepared request не дают strict reuse; default temperature и tool-calling independence не меняются ради зелёного результата.

**Приёмка:** предъявить оба исхода на одной объявленной модели/профиле с изменением только deciding условия. Точные локальные counterexamples и expected values берутся из связанных TEST соответствующих пакетов; совпадение summary без фактического потребления не принимается. Если метод стохастический, заранее указать seed/replica/ошибку сравнения, не подбирать tolerance после результата.

## Существующие места расширения tests

Список означает проверенные пути, не доказательство полноты или запуска всего содержимого. Новые проверки добавлять к ближайшему владельцу; отдельный harness создавать только при реальном разрыве.

- [policy-engine/tests/unit/scholar/search/test_service_jobs_tools.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/scholar/search/test_service_jobs_tools.py) — SHA256 `b3e9d2286f5a92c80f1b99c487063856d636f9ee4fbd18fb9cb415ebfe319d72`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.
- [policy-engine/tests/unit/scholar/search/test_source_binding.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/scholar/search/test_source_binding.py) — SHA256 `ee3b75fbce58bf22af512fa799e48a91791ebe93df77f5d27610a846ef5c71fe`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.
- [policy-engine/tests/unit/scholar/search/test_fetcher_security_cache.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/scholar/search/test_fetcher_security_cache.py) — SHA256 `8b5ddea43d7c70f34ac8b1484bd7062ccca65f789ebdc1bd29a76c33870cbe5c`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.
- [policy-engine/tests/unit/scientist/orchestration/llm/test_factory_cache_composition.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/scientist/orchestration/llm/test_factory_cache_composition.py) — SHA256 `8436d312b802d7ed8c73795ecf4f1916166ae7b44671602c8eebb1ac925bdafe`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.
- [policy-engine/tests/unit/scientist/orchestration/llm/test_cache_owner_admission.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/scientist/orchestration/llm/test_cache_owner_admission.py) — SHA256 `9035a7c53a0948da0eda911ca4c85cd642c300d7fd121cea2fc69545e34c94ab`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.

## Выход приёмки

- Один manifest исполнения семейства: base/head SHA, scenario-ID, связанные REQ/TEST, профиль, входы и их hash, actual commands/exit, фактические positive/negative oracles, ограничения
- Перечень doubles с объяснением, какое свойство ими не проверяется
- Для failure/unknown: точная стадия и сохранённый полезный результат. Не перекрашивать BLOCKED/UNRUN в PASS
- Ремонт механизма и предметная валидность имеют разные решения. Синтетический механизм может пройти, не подтверждая прогноз/каузальную идентификацию/мандат реального кейса

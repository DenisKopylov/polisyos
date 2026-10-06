# F: передача causal / graph / SCM / economics / Lex

Все 17 назначенных пакетов и 35 уникальных finding представлены в [INDEX.json](INDEX.json). Девять законченных slices опубликованы через отдельные topic branches и draft PR. Implementation commits, candidate trees, receipt heads и SHA256 указаны для каждого slice; код и deciding evidence доступны G через Git. Приёмка полного F-набора G и finding closure ещё не установлены: accepted_finding_closures пуст, B219 held; остальные критерии ограничены явно указанными остатками.

| Slice | PR | Основное bounded evidence |
| --- | --- | --- |
| cau-cohort-admission | [PR](https://github.com/DenisKopylov/polisyos/pull/18) | Native79PASS5DoWhySKIP; independent21PASS |
| graph-scm | [PR](https://github.com/DenisKopylov/polisyos/pull/23) | Native123PASS1DoWhySKIP; locked NetworkX29PASS and2400 oracle agreements; independent8PASS |
| economic-profile-consumers | [PR](https://github.com/DenisKopylov/polisyos/pull/15) | Defining32PASS; independent32PASS; mixed broader55PASS4FAIL remains separate |
| fit-tmle | [PR](https://github.com/DenisKopylov/polisyos/pull/26) | Native63PASS; independent33PASS with fit-integrity adversaries |
| fry-compile-contracts | [PR](https://github.com/DenisKopylov/polisyos/pull/20) | Native45PASS; independent14PASS |
| api-consumer-abi | [PR](https://github.com/DenisKopylov/polisyos/pull/19) | Native26PASS; independentreviewGO; UtilityJudge broader red retained unexcluded |
| lex-input-binding | [PR](https://github.com/DenisKopylov/polisyos/pull/21) | Final native22PASS; independent22PASS plus9 native persisted controls |
| economic-dtype | [PR](https://github.com/DenisKopylov/polisyos/pull/29) | Native60PASS; independent76PASS; default/x64 importers37/30PASS |
| causal-output | [PR](https://github.com/DenisKopylov/polisyos/pull/31) | Native196PASS8markerSKIP; independent12PASS plus actual direct-port removal |

Числа выше относятся к отдельным запускам и перекрывающимся scopes; их нельзя суммировать как уникальный общий test denominator. DoWhy/EconML исключены markers Python3.14 и отсутствуют: SKIP/UNRUN не служат backend witness. Statsmodels и NetworkX проверены в отдельных настоящих locked environments, без shim и изменения общей среды.

[Полная семантическая матрица](F-residual-authority-map.json) содержит по каждому ID missing inputs, semantic owner, authority limit и next action. Это неизменённый ранний snapshot семи receipts; актуальные девять head/tree bindings берутся из INDEX, включая Lex tuple snapshot, dtype, common causal outputs и отдельные substantive doc companions CAU/API. [Независимый исходный audit](receipt-audit.json) и [delta audit раннего checkpoint](receipt-audit-delta-approved.json) разделяют исходные и последующие checkpoints. [Ранний remote/PR readback](foundry-index-published-snapshot.json) сохраняет собственные heads; финальный readback и CI evidence указаны в delivery-index receipt.

Изменённые invariants: отказ от неподдержанного окна staggered cohort; соответствие GCM/shared causal declared ports реальным результатам; TMLE cache input binding и immutable fit storage; JAX scalar branch promotion; Lex compared-pack binding и замороженный validated pass plan. API/Foundry/economic-profile slices добавляют native consumer/oracle evidence и сохраняют unresolved bridges, profiles и decisions. Catalog membership, facade identity, pass/report ID и dispatcher success сами по себе не доказывают scientific или institutional authority.

Baseline: 307 F route rows, 118 уникальных cells, 115 исторических PASS и 3 FAILED; шесть cells включают skips. [Census](F-baseline-census.json) сохраняет полный относящийся набор. Исходные Fxx raw archives не получены, поэтому compact source receipts остаются навигацией, а не scientific admission.

## Приёмка G

Fetch каждого topic/ref из INDEX, затем проверка source/receipt binding и independent code review. Из policy-engine/../ выполнить:

```bash
python3 policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/verify_delivery.py policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/INDEX.json --negative-controls
```

Verifier пересчитывает весь TSV owner denominator, уникальность ID/bundle, owner/status, Git ancestry/tree, exact implementation footprints, source freeze и все объявленные Git path/hash/size refs. PASS этого инструмента означает только bookkeeping. Local ignored raw hashes остаются declarations/not_established и не входят в byte custody. Приёмка runtime property, научного метода, real data или authority отдельно необходима.

G применяет только принятые implementation commits, с отдельным receipt/evidence readback, и повторяет affected consumer/backend/oracle checks после композиции. Последний broad run выполняется на одном frozen integrated SHA. Existing economics mixed59-case output остаётся 55 PASS / 4 FAIL на своём исходном checkpoint; отдельный dtype repair не превращает его в integrated PASS.

Архитектурные проверки — UNRUN/exit2 с сохранёнными partial drifts; нужен supported Node22 и generator dependencies. Common-wrapper production invocation — UNRESOLVED/exit3; FIT scanner — ERROR/137; остальные static scanner PASS имеют partial coverage и runtime_invocation_established=false. Inherited-red exemption не установлен. Полные умеренные deciding logs лежат в соответствующих slice branches. Огромные raw/scanner bytes остаются local ignored с SHA и exact rerun, без утверждения о переданной custody.

Для data-dependent критериев G связывает локальные admitted bytes, caller/backend, estimand и authority с точным интеграционным candidate SHA и выполняет next action соответствующего finding. Full production inputs остаются локально/read-only. B210 и LA-004/LA-035 требуют principal scope/objective decision; B219 held не снимается установкой backend. C/G проверяют actual installed external/plugin consumers и real caller custody; local literal-import census не покрывает динамические/внешние consumers. Никакая недостающая семантика не выдумывается ради PASS.

Доступная ёмкость составляла шесть прямых субагентов плюс root; использованы все шесть с перераспределением задач. Cloud checks стартовали по готовности без искусственного process/thread/CPU лимита. Root не публикует integration или main; merges, force push и переписывание истории не выполнялись.

## Фактический CI и остатки для G

Полные логи CI с source/merge/job identity переданы в [ci-evidence](ci-evidence/README.md); [manifest](ci-evidence/transfer-manifest.json) связывает Git bytes с исходными логами. Python quality останавливается на import policy до pytest. Canary требует genuine service-principal token; performance/accessibility требуют локальный production catalog. Schema snapshots, OpenAPI dependency receipts, locale/CAS assertions и directory-health/JUnit reporting имеют отдельные FAIL; ownership/introduction не установлены одной красной строкой. SKIP и UNRUN не становятся PASS.

Собственные CAU/API `foundry_docs` gaps исправлены в существующих canonical docs и проверены независимым удалением companion. Полный native DocsGate на новых doc commits остаётся FAIL: freshness exception просрочен, observed violations 10 вместо 0; strict docs build UNRUN после этого отказа. Runtime native checks остаются привязаны к прежним implementation SHA. Новые published heads требуют собственного CI; исторические красные outcomes сохраняются. Никакие exceptions, baselines, credentials или missing production inputs не подменялись.

G уже опубликовал bounded acceptance раннего API runtime (`baada065` / `0c709ea`) в [checkpoint-03](https://github.com/DenisKopylov/polisyos/blob/15d50bac59d06a3fb010327abf8e0c90f9ccbed0/policy-engine/docs/research/e02-cloud-test-plan/integration/checkpoint-03.json): собственный native run 26 PASS, без LA-020 closure. Это решение сохранено отдельно в INDEX; новые doc/receipt commits API и полный F-набор остаются на приёмке.

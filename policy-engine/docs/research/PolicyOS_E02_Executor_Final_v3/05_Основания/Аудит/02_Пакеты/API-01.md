# API-01 — явная поверхность причинных пакетов
## C51 · 1 ноября 2026 года

**Порядок:** 51/127, LANE-05. **Исходный ID:** LA-020. **Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Только аудит. Этот C51 выполнен заново после внешнего сохранения C50; утраченный прежний C51 не используется как доказательство.

## Решение

Исходное отражающее копирование namespace **устранено в обоих целевых initializer**. `causal_engine` имеет 2 публичных имени, `interference` — 9; ещё 5 и 3 compatibility bindings доступны напрямую, но не через star import. Объекты привязываются без wrappers. Incidental imports из leaf modules не расширяют API; reload убирает случайно оставшиеся names.

Проверен не только `__all__`: **actual sync helper и полный actual static dispatcher** потребляют четыре поддержанных monkeypatch-адреса; restoration работает. Искусственное отключение sync ломает этот маршрут при неизменных class identity и manifest. **13 bounded MATCH; 8 неизменённых test bodies / 11 cases PASS изолированно. Подтверждённого runtime R нет.** Однако leaf objects/algorithms синтетические, native installed chain не запущена. Кроме того, обнаружен конкретный пробел existing consumer census: content-only prefilter пропускает пять relative submodule imports. Это G, а не доказательство сломанного публичного клиента.

## 1. Матрица исходного ID

| ID | Исходное требование | Текущий результат | Остаток |
|---|---|---|---|
| LA-020 | Вместо `dir()/globals-copy` определить supported API, сохранить реальные packages, identity и нужные test-facing names; проверить consumers, docs, monkeypatch, FQN | Полные initializer используют explicit bindings; public/compatibility разделены; actual import/reload/star/unknown/incidental controls пройдены с synthetic leaves; actual dispatcher получает facade patches | C51-G01: native leaf/installed/FQN/docs chain; C51-G02: census полнота и внешнее окно совместимости |

Полная карточка, строки 6221–6323, прочитана вместе с LK05/LK13. Защищённые реальные пакеты и BERL не объявлены legacy целиком. Никакие исходники, тесты, зависимости или Git refs не менялись.

## 2. Фактическая поверхность и владельцы

`causal_engine/__init__.py` явно получает `CausalEngine` из `api`, затем binds error/helper/четыре algorithms из `artifacts`. Public manifest — `CausalEngine`, `DataReadinessBlockedError`. Direct-only остаются `_make_dummy_identification_result`, `id_star_algorithm`, `id_with_oracle_fallback`, `idc_star_algorithm`, `mz_id_algorithm`. Это намеренная compatibility поверхность, а не лишние symbols, подлежащие механическому удалению. [S01:1–42](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/causal_engine/__init__.py#L1-L42) [S03:1–54](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/causal_engine/api.py#L1-L54)

`interference` явно exports четыре estimator classes из `api`, три functions из `identification`, два публичных contracts из `_interference_contracts`. Три private contracts сохранены direct-only: `_ReductionErrorBoundPlan`, `_SimplicialSupportGate`, `_TopologyCertificatePlan`. [S02:1–67](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/interference/__init__.py#L1-L67) [S06:1–104](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/_interference_contracts.py#L1-L104)

Точный список 11 public и 8 compatibility имён сохранён в [supported export manifest](../04_Проверки/C51_API01/supported_export_manifest.json). У двух initializer остался цикл по собственным globals **для удаления неразрешённых старых names**, не для отражающего копирования namespace из leaf. Наличие слова `globals` само по себе не воспроизводит LA-020.

Внутренний reflection в `identification`/`estimation` и `interference.api` действительно виден в прочитанных imports. Но LA-020 задаёт точную область двух package initializer; это не доказательство того, что package manifest снова расширяется. Перенос всех helpers в новый mega-facade не нужен. Исходный `id_engine` package не удаляется и не аттестуется целиком этим аудитом.

## 3. Producer → binding → настоящий dispatcher

`CausalEngine.api` собирает класс из существующих mixins. `identify` перед нормализацией и dispatch вызывает `_sync_public_algorithm_overrides`; helper берёт только присутствующие на package names. В его перечне 11 возможных algorithms, но это **не означает 11 поддержанных package exports**: целевой facade сохраняет четыре explicit algorithm bindings. [S04:94–115](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/causal_engine/identification.py#L94-L115) [S04:2163–2223](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/causal_engine/identification.py#L2163-L2223)

**P11:** для каждого из четырёх names fixture patch установлен на actual facade. Exact sync body переносит его в globals exact static dispatcher; appropriate branch вызывает patch один раз. После возврата исходного facade binding повторная синхронизация восстанавливает исходный algorithm object. Full dispatcher body исполнен без переписывания его условий; входные graph/result/algorithm и `_maybe_proximal_identify` — объявленные fixtures. [S04:247–624](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/causal_engine/identification.py#L247-L624)

**P12:** artificial no-op вместо sync оставляет manifests и class identity прежними, но patch получает ноль вызовов. Контроль отличает действующий consumer bridge от формального наличия names. Checkout не модифицировался. Полный top-level `identify` прочитан, но orchestration/admission, реальные scientific algorithms и их correctness этим исполнением не квалифицированы.

## 4. Исполненные проверки и честный предел identity

- **P01–P05:** actual initializer code создаёт fixed public 2/9 manifest, star imports совпадают с ним; 8 compatibility names остаются доступными; objects тождественны переданным leaf objects.
- **P06/P07:** noise в пяти synthetic leaf modules не попадает на package surface; настоящий `importlib.reload` очищает injected stale names.
- **P08:** unknown import не превращается в permissive fallback.
- **P09/P10:** pickle/FQN и pydoc не ломаются **для synthetic leaf objects**. Это подтверждает отсутствие facade wrappers в данном fixture, но не является replay старых production payloads или проектным documentation build.
- **P13:** 8 unchanged bodies из существующего regression file исполнены в 11 cases. Отдельный `test_interference_api_leaf_exports_are_bound_and_star_importable` намеренно **не запущен**, поскольку реальный heavy leaf module не загружен. [S08:1–237](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_api_01.py#L1-L237)

Native consumer, installed wheel/sdist, FQN, real monkeypatch, DTO/CAS и package-preservation tests прочитаны целиком, но не засчитаны как исполненные. В installed suite есть disposable Git-commit fixture — он также не запускался. Исторические 199 cases в reconciliation документе относятся к другому окну и не повышают текущий verdict. [S09](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/methods/catalog/causal/test_facade_consumers.py) [S10](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/methods/catalog/causal/test_installed_facade_contract.py) [S12](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/docs/reference/foundry/causal-installed-source-reconciliation.md)

## 5. C51-G02 — конкретная граница census, не выдуманный broken client

Существующий `test_repository_literal_facade_imports_resolve` заявляет literal imports, включая relative, но пропускает файл до AST parse, если в **его тексте** нет `causal_engine`/`interference`. Relative import может находиться внутри соответствующего package и не содержать эти строки. [S09:167–212](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/methods/catalog/causal/test_facade_consumers.py#L167-L212)

Свежий census проверяет bytes всех **8231 tracked `.py` files** против pinned Git blobs. Content-only вариант даёт 66 occurrences в 47 files; content-or-path prefilter с relative resolution — **71 в 50 files**, 145 parsed candidates, zero parse/encoding gaps. Добавленные пять sites: `causal_engine/__init__.py:5`; `causal_engine/api.py:12–14`; `causal_engine/estimation.py:7`. Это `from . import artifacts/discovery/identification`, то есть относительные **submodule fallback routes**, не пять доказанных сломанных публичных consumers.

Оба census сохранены; исправлен только внешний audit script. Counts относятся к именованному literal AST denominator двух packages: это не выполнение imports, не production-usage census и не доказательство отсутствия computed/configuration/external клиентов. Для migration closure нужно дополнить существующий prefilter/consumer check, а оставшиеся окна именовать явно. Полезный current finite dynamic-string test не становится универсальным historical compatibility proof. [S11:54–101](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/methods/catalog/causal/test_facade_consumer_continuation.py#L54-L101)

## 6. Сохраняемый результат и остаток

**Сохранить:** реальные packages/leaf owners, fixed manifests, прямую object identity, восемь объявленных compatibility bindings, sync→dispatch/restoration и negative incidental/reload controls. Не возвращать monolithic namespace ради случайного import; не удалять все underscore names без client evidence.

**C51-G01:** нужен supported Python 3.14 runtime и реальные focused/installed/FQN/docs/consumer tests. В текущей среде pytest отсутствует; оба native imports останавливаются на Python 3.14 exception syntax `uncertainty.py:287` под Python 3.12. Это environment BLOCKED, не product R. Synthetic scientific result не является доказательством causal capability, empirical validity или допустимости policy claim.

**C51-G02:** уточнить существующий literal consumer census и фактическое поддержанное migration window. Конкретный false-negative prefilter установлен; runtime regression не установлен. Недоступная проверка не заменена новой архитектурой или дополнительным approval workflow.

Начальный external probe имел syntax typo; исходник и failure сохранены, исправлен только harness. Финальный bounded run — exit 0. Все команды/exit/logs и seams доступны: [диагностика](../04_Проверки/C51_API01/bounded_diagnostics.json), [команды](../04_Проверки/C51_API01/commands.json), [native границы](../04_Проверки/C51_API01/native_verification.json), [census](../04_Проверки/C51_API01/source_import_census.json), [источники](../05_Источники/C51_источники.json), [остатки](../01_Реестры/C51_остатки.json).

**51/127 пакетов рассмотрены ограниченно; 121 уникальный B/LA частично оценён. Следующий — CAU-01. Полного закрытия нет.**

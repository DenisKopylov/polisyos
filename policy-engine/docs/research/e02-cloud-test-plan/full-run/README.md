# Полный облачный прогон существующих тестов E02

Дата 5 октября 2026 года. Получатель — Денис и локальные архитектурные и кодовые агенты E02.

Рекомендация: **15 независимых cloud задач F01–F15, по одной ревизии и одному последовательному pytest-процессу на VM**. Плановый общий объём одной задачи — **3,25–3,84 часа**, включая запас на подготовку, дополнительные команды и выдачу результатов. Это оценки расписания, не облачные замеры и не гарантия срока. В пилотах сами тесты занимали 9–12 минут, а полная задача 30–40 минут; новые задачи могут закончиться заметно раньше. Быструю VM не загружать искусственными повторами.

Это полный сбор **перечисленных существующих E02-маршрутов**: 560 текущих Python-файлов, 1 514 исторических запусков, четыре Node-файла, 14 отдельных команд проверки и девять дополнительных property replay states. Полный E02 DoD не заявляется; полный tree census 2 755 tracked `.py` путей под `policy-engine/tests/` включает также helpers и не является числом pytest-файлов. Нужные новые смысловые пробы остаются отдельной локальной работой. Исследование использовало десять прямых субагентов поверх исходного двадцатиагентного обзора; продуктовые тесты и cloud задачи в этом чате не запускались.

## Что входит

| Часть | Полный знаменатель | Назначение |
| --- | ---: | --- |
| Актуальный cut `6978076` | 560 полных `.py` файлов = 482 Q + 78 дополнительных маршрутов каталога | Основной фактаж для текущей архитектуры и исправлений |
| Исторический replay | 483 `.py` пути × четыре cut = 1 932 slots: 1 514 запускаемых, 414 MISSING, 4 safety UNRUN | Четырёхбазовое сравнение E02R2 и материал для P41 |
| Current safety | 1 UNRUN | `test_data_state_substrate.py` body/data исключены |
| Всего Python slots | **2 493 = 2 074 запуска + 414 MISSING + 5 safety UNRUN** | Это файловые ячейки, не pytest cases |
| Existing property replay | 3 test-only hooks × normal/removal/restored = **9** дополнительных whole-file запусков | F03, вне unique native cells; всего **2 083** плановых whole-file invocations |
| Native client / owner gates | 4 `.mjs` файла, 5 TS workspaces / 7 compiler operands, API contract, CG1/CG2/GY-N6/architecture | Отдельные commands/verdicts; в 2 074 не добавляются |

Все **93 файла Q01/Q02/Q14/Q15 запускаются заново** внутри 560. Пилоты считаются отладкой процесса; их результаты не принимаются в новый denominator. Единственный исключённый из 79 дополнительных catalog paths файл `tests/performance/test_overhead.py` — несвязанный с RUN-01 TypeVar/async discriminator benchmark; причина записана в allocation. Все 78 включённых дополнительных файлов действительно существуют, имеют test callables и явно указаны в pytest-командах каталога.

Исторические refs сохраняются: `78187878ee188ff6d27442ba1498bd094da9785b` — execution base; `00d946c2b7d052522be092f9c70eb9902f6521c2` — E02 head; `5fd3ebcc15637e98bbd4938de5d62ee5004504a8` — historical main; `0213101b6d124e6f855b1aff7c442bb0912a61c2` — integration cut. `69780761ae091d8fcc6ab8778c7f5f7227eeef0b` — актуальный исследуемый cut. Одинаковые 482 test blobs на 021/697 не разрешают reuse: между cuts изменились 20 документных путей, а полный input denominator каждой ячейки не reconciled.

История включена в этот полный запрос потому, что E02R2 `BASELINES.md` required closeout #6 требует Appendix A/B/touched whole files на четырёх базах. Для отдельного текущего архитектурного решения прежде всего нужны F01–F04. Четыре replay cuts сами по себе не устанавливают ownership красного: нужны реальная slice base, идентичные command/env/inputs и полный intersection proof. `BASELINES.md` #7 отдельно требует owner gates и TS команды; CP1–CP6 являются окнами приёмки, не ещё шестью full CI suites.

## Распределение и готовые промпты

Скопируй **весь файл каждого промпта** в отдельную cloud задачу. Он самостоятельный: содержит pin, expected source hashes, полный TSV manifest с blob OID, gates, exclusions, protocol результатов и одинаковый проверенный observer. При наличии доступной параллельности запускай все 15 одновременно; число 15 — размер раскладки, не утверждение о лимите сервиса или гарантии такого допуска. При меньшем доступном числе VM очередь увеличит общий makespan, но объём отдельной задачи сохраняется.

| Промпт | Cut | Python cells | Модель тестов | Запас gates | Property replay | Общая модель с setup/export |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| [F01](prompts/F01.md) | `6978076` | 139 | 2.35 ч | 30 мин | 0.0 мин | 3.60 ч |
| [F02](prompts/F02.md) | `6978076` | 140 | 2.35 ч | 30 мин | 0.0 мин | 3.60 ч |
| [F03](prompts/F03.md) | `6978076` | 141 | 2.36 ч | 15 мин | 29.0 мин | 3.84 ч |
| [F04](prompts/F04.md) | `6978076` | 140 | 2.35 ч | 25 мин | 0.0 мин | 3.51 ч |
| [F05](prompts/F05.md) | `7818787` | 145 | 2.98 ч | 0 мин | 0.0 мин | 3.73 ч |
| [F06](prompts/F06.md) | `7818787` | 145 | 2.98 ч | 0 мин | 0.0 мин | 3.73 ч |
| [F07](prompts/F07.md) | `00d946c` | 122 | 2.65 ч | 0 мин | 0.0 мин | 3.40 ч |
| [F08](prompts/F08.md) | `00d946c` | 130 | 2.65 ч | 0 мин | 0.0 мин | 3.40 ч |
| [F09](prompts/F09.md) | `00d946c` | 130 | 2.65 ч | 0 мин | 0.0 мин | 3.40 ч |
| [F10](prompts/F10.md) | `5fd3ebc` | 117 | 2.50 ч | 0 мин | 0.0 мин | 3.25 ч |
| [F11](prompts/F11.md) | `5fd3ebc` | 121 | 2.50 ч | 0 мин | 0.0 мин | 3.25 ч |
| [F12](prompts/F12.md) | `5fd3ebc` | 122 | 2.51 ч | 0 мин | 0.0 мин | 3.26 ч |
| [F13](prompts/F13.md) | `0213101` | 160 | 2.72 ч | 0 мин | 0.0 мин | 3.47 ч |
| [F14](prompts/F14.md) | `0213101` | 161 | 2.72 ч | 0 мин | 0.0 мин | 3.47 ч |
| [F15](prompts/F15.md) | `0213101` | 161 | 2.72 ч | 0 мин | 0.0 мин | 3.47 ч |

F01–F04: актуальный baseline + client/API, TSC и owner gates; F03 также три existing property серии. F05–F06: execution base. F07–F09: E02 head. F10–F12: historical main. F13–F15: integration cut. Каждый файл×cut назначен ровно одной VM. Сначала дорогие файлы; целые файлы не режутся для выравнивания. Gates тоже имеют единственного исполнителя. Один процесс внутри VM выбран для воспроизводимого baseline: пилот Q14 не установил throughput advantage двух workers, а его пары были резко неравны по времени и имели shared timing lock. Численные threads=1 не обещают 100% загрузку всех CPU; продуктивная параллельность здесь между VM, без повторов ради нагрузки.

LPT балансирует сумму консервативных исходных weights, добавляя максимум с reported pilot time там, где доступно. Пилотные raw archives не получены, поэтому это **source-reported planning prior**, не проверенный timing receipt. Общий Python вес 38.98 модельных VM-часа; остальные 1.67 часа — резерв gates. F03 дополнительно учитывает 29,0 минут property replay. Каждой VM отведено 45 минут setup/export: примерно 15 минут подготовки и 30 минут выдачи, без повторного добавления packaging reserve. Если setup длится дольше, к cutoff останется меньше времени для тестов. Не применять общий коэффициент 0,44 из четырёх специально выбранных пилотов: долгие и пропущенные файлы делают такое масштабирование недостоверным. Раскладка одной исторической базы не смешивается с другими checkout/venv.

## Границы среды и исполнения

Pro имеет default 4 vCPU, 16 GiB RAM и 32 GiB disk; фактические quotas/free space измеряет каждая задача. Это defaults из [официальной документации облачной среды](https://learn.chatgpt.com/docs/environments/cloud-environments), не результаты пилотного resource admission. Перед новым install/build репозиторий требует >=20 GiB free. Locked Linux x86_64 `search_bo` включает CUDA/NVIDIA/Triton при CPU execution: нижняя граница **4 117 853 878 bytes (~3,84 GiB)** сжатых wheels тяжёлого подграфа, до распаковки, cache, остальных extras, checkout и Node. Пригодность всего профиля на 32 GiB `not_established`; CPU-wheel вне lock не подставляется. Полный профиль, включая BoTorch/Torch и hnswlib, в пилотах не проверен; disk/toolchain/network blocker означает конкретный UNRUN, а не молчаливое отключение backend теста.

Frozen profile из exact cut, union только реально нужных extras своего списка, один install; numeric threads=1, JAX CPU. Node links устанавливаются до scanner. `temporalio` не объявлен в lock; Python markers исключают DoWhy/EconML. GPU/Metal/macOS, production service/LLM/API и отсутствующие реальные data inputs этим Linux-пакетом не аттестуются. Runtime tests с mock/synthetic producer остаются такими и отражают эту границу в handoff.

16 внешних документов final 021 freeze независимо reconciled с `HANDOFF_EVIDENCE` → committed readback → source binding → original foreign hash manifest. Все 16 bytes можно восстановить из pinned 697 Git blobs, исключительно как ожидаемый untracked/unstaged overlay на 021. [Manifest](foreign-overlay.json) и F13–F15 содержат exact hashes/paths; 4 376 552 bytes. На остальных cuts overlay не назначен. Production data не передаются.

Наблюдатель использует стабильные public pytest hooks, не мутации Hypothesis или historic hooks. Его проверили на изолированной синтетической fixture под Python 3.14 / pytest 9.0.2: pass, fail, setup error, skip, xfail/xpass и collection/session records. Это проверка instrumentation, не PolicyOS product tests. Snapshot origins в конце сессии ограничен реально загруженными owned modules; полной import history всех subprocess он не доказывает.

Канонический bound runner переиспользуется. Для debt-ledger test нужен observer fallback: его nested `--collect-only` выбирает другие пути, конфликтуя с inherited canonical receipt plugin. Same-file generation/promotion subprocess probes разрешены, их parent receipt сверяется и nested limitations сохраняются. Safety-файл можно только легитимно собрать по exact nested collector selector без выполнения body; копирование real data и самостоятельное исполнение body запрещены. Receipt quality хранится отдельно от pytest result: module skip + no canonical receipt не является обычным продуктовым FAIL.

## Пакет результатов для локальной работы

Каждая VM возвращает **result.json, cells.tsv, failures.jsonl, handoff.md** и хешированный raw archive; F03 также **properties.tsv** с девятью state rows и их target verdicts. Формат и fallback подробно зафиксированы внутри каждого промпта. Он обеспечивает одну primary row на cell ID, отдельные attempts, exact source/blob/argv/profile, phase-aware counts, node identities, реальные error values, тайминги/RSS и references на JUnit/origins/полный вывод. Причина и ownership по умолчанию `not_established`; candidate hypothesis не смешивается с наблюдением.

В пилотах все четыре raw архива имели `transfer_missing`. Поэтому здесь при недоступном экспорте финальный ответ обязан содержать **полные compact bytes** metadata/cells.tsv, назначенных properties.tsv и failure blocks, а не только VM paths или краткое PASS-summary. Raw transfer всё равно помечается missing: текстовый fallback полезен для проектирования воспроизводителя, но не является независимо проверенным archive/closure evidence. Большие deciding логи сохраняются только в игнорируемом raw/. Никаких upload workflows/committed raw/venv/caches.

Локальный агент получает конкретный cell/attempt и присоединяет path к [finding-routes.json](finding-routes.json), исходному [coverage.csv](../coverage.csv), [каталогу 127 пакетов](../bundle-catalog.md) и residual row B/LA. Порядок работы: проверить bytes/полноту передачи → найти actual producer/bridge/consumer → воспроизвести красный exact command → отделить unavailable inputs и receipt limitation → сформулировать свойство и отрицательный контроль → wire-existing / extend / consolidate / build-new. Не проектировать контракт из одного красного traceback или green exit.

## Что останется после прогона

[open-probes.json](open-probes.json) сохраняет будущую работу и ссылки на владельцев. У 42 предложенных regression filenames нет файла на cut; это не означает 42 доказанных semantic gaps или обязательность создания именно этих файлов. Общий реестр исследовательских предположений остаётся ignored, каталог содержит их проверяемые bundle anchors.

Для **B37/DUR-01** existing mirror-contract test теперь запускается, но real FileBudgetLedger concurrency/fault/empty-corrupt-ledger/BudgetMiddleware readback ещё `verification_missing`. Для D02 остаётся positive served candidate→N4/N5→acquired CAS→problem-bound WMR/context→second N5 и foreign/unchanged/UUID-only controls. Production signer/appointment/calibration authority не вытекает из candidate signing fixture. 13 logical stop states R1/R6/R7/R9 не объявляются закрытыми. F03 запускает уже имеющиеся test-only hooks R1 (V3 scalar), R6 (foreign-context identity), R7 (active-probe suppression): три свежие whole-file normal/removal/restored серии. Точное сопоставление R1 с final roster остаётся candidate; шестью R9 states эти hooks не являются — для owner-query witness/hash нужны test-only removal adapter или изолированный mutation harness. CP6 installed-wheel import inventory также остаётся `verification_missing`. Новые тесты и мутации исходников сюда не включены.

Pattern pass: P01/P02 — chain reality, missing producer/bridge и semantic tests не скрыты; P13 — не дополнять вычисления повторами; P14 — одна cell не становится многими независимыми witnesses; P29/P32/P37 — exact source/selection/result/bytes reconciled, authority не основана на существовании файлов; P35 — полные 560/1514/414/5/282/127 множества; P38 — свойство execution отличается от proxy PASS/exit (например 0 calls при importorskip); P41 — replay даёт материал, а не автоматическую атрибуцию.

Приёмка самого плана: complete Git census, нулевые дубликаты и gaps в assignment, source blobs и expected MISSING reconciled, standalone prompt manifests/hashes/plugin одинаковы, все 282 route rows сохранены. Приёмка cloud execution позднее: реальные result bytes/receipts и remaining UNRUN отдельно. План не повышает ни одну из 282 finding statuses. Решающий local verification сохранён в [verification.json](verification.json); source cuts и массивы в [allocation.json](allocation.json).

# E02 — первая независимая приёмка G, 27 октября 2026

**Три исходных критерия подтверждены на точно названных кандидатах: B87, B89 и B56. Это ещё не закрытие этих findings на текущей integration.** В остальных пакетах есть полезные принятые результаты, но они не покрывают соответствующие исходные критерии целиком. В V6 найден блокирующий дефект сопоставления manifest profile.

Вход: пакет `8c5efa250faa2e983b1ce7a2021b9ea135846a69`. Проверенный G до этой документации: `14bf638032063c3d5a92b29da4215b3b54951fd6`. Результат этой работы — независимое решение о свидетельствах и исходных критериях, а также точная очередь исправлений. Product source не изменён, commits реализации не интегрированы, `formal_closure_ids=[]`, global freeze не объявлен. Исторические closures, включая B198, сохранены.

## Решение по семи пакетам

| Пакет | Что G принимает | Что пока не принято |
|---|---|---|
| BOOT0 | Завершённый этап admission/сохранения работы на `a92c977`; подтверждены branch/base/input identities и очередь | Admission — запись на момент проверки, а не разрешение игнорировать последующие изменения рабочего дерева; продуктовых findings нет |
| T1 | Полный inventory семи назначенных строк и их owner/input/API границ | Ни один из семи исходных критериев не закрывается инвентаризацией |
| R2 | Bounded source review пяти механизмов и task exit на `65ac853`; **B87/B89 удовлетворены на этом кандидате** | Перенос в G и проверка затронутых consumers на составленном G source |
| I1 | Составленная группа из 18 source paths; same-stat mutation, unchanged skip, warm/fresh readers и WVS/session checks на `a92c977`/`76691bd` | **LA-041 не закрыт:** полнота checkpoint/legacy/recovery матрицы не доказана выполненными selectors |
| R4 | Configured competing-workload task exit и **B56 на source-qualified пути**: cap 1/2, сохранение roster/результатов, removal control | Никакой production-capacity, полного prepare→persist admission или длительной lease-устойчивости этим результатом не принято |
| I4 | Catalog bridge на `8a24cc8`; Legal direct-path witness на `567c38c` с ограниченным переносом неизменных частей | Нет свежего whole-process Legal PASS на новом source; пять назначенных findings и обе привязки LA-046 целиком не закрыты |
| V6 | Сохранность реального SimulationResult после независимого последующего сбоя и fresh parsed GET — доказанный ограниченный результат | **Source acceptance HOLD:** node/state join пропускает manifest profile. B13 также требует отдельного common-basis invalidation witness |

Это **не семь закрытых исходных findings и не «семь из девятнадцати»**. Исходный TASKS содержит 26 task/decision rows. Подробный remaining19-report охватывает 12 implementation rows, 6 verification rows и I1 author-complete; остальные шесть review packets находятся вне этого набора. Семь рассматриваемых пакетов связаны с **17 уникальными finding IDs / 18 criterion occurrences**. LA-046 имеет две привязки — REQ-01 и ACQ-01 — с одним исходным текстом; обе сохранены.

## Что проверено независимо

Восемь прямых reviewers работали read-only: шесть предметных групп (BOOT0/T1 вместе, R2, I1, R4, I4, V6), полный crosswalk и lineage. Детей, окружений и runtime-проверок они не создавали. G отдельно проверил исходные критерии, спорные решения и код выявленного V6 дефекта, исправил чрезмерные выводы из summaries.

Все **53 прямые `evidence[]` ссылки** семи `packet.json` доступны и совпадают по SHA-256. Это полный знаменатель именно этих прямых ссылок, не рекурсивная проверка всех вложенных assets и не доказательство поведения. Transferred-results `import_results.py --check` — PASS; его `verification.json` по-прежнему имеет grade `transfer_and_navigation_only`, исходные raw archives не переданы, поэтому этот индекс не используется как продуктовый PASS.

G дополнительно выполнил **две R2 race-проверки** на изолированной выгрузке exact Git source `65ac853e2735e827e27688a6175f1a385901e20e`: **2 PASS, 0 FAIL/ERROR/SKIP**, wall 5.08 s, peak около 336 MB. Все **373 уникальных загруженных source paths** совпали с этим Git object; foreign product modules — 0. Выполнение кода из живого checkout автора было запрещено audit guard. Использовался существующий Python environment read-only, без установки зависимостей и production data. Это native source run, не installed-wheel proof и не run текущего G.

Исторические R2 **316 PASS**, авторские **2 PASS** и новые G **2 PASS** — три отдельных исполнения; их числа не складываются. Остальные runtime results здесь проверены как сохранённые, source-qualified receipts, не выданы за новые прогоны.

## Почему реализация пока не переносится обычным merge

Кандидат `a92c977` и G расходятся от общего `b7adafe`: на стороне кандидата 923 commits, на стороне G — 38. Прямое сравнение их деревьев даёт **8 674 изменённых пути**. Даже перечисленные пакетами implementation commits затрагивают намного больше, чем узкие проверенные свойства. Поэтому merge всей ветки принял бы ещё не рассмотренную работу; `code_integration_required=false` в пакетах не доказывает, что код уже находится в G.

Пакеты сохраняют смысл и могут служить базой последующей приёмки. **Базовый путь — накопительная приёмка на единой lineage исполнителя**, без второго порта той же реализации на старый G. Не требуется заново исполнять весь E02 или переписывать исправленные механизмы. Следующий integration slice должен явно назвать полный состав source/test/config/public companions, их dependencies и способ переноса, сохраняющий append-only историю. G проверяет весь вносимый delta и ещё не рассмотренную ancestry этого slice; неизменные части уже проверенных receipts можно переиспользовать с новым source binding. Естественно отделимый, полностью проверенный commit можно интегрировать раньше остальной очереди. Пока такой состав не выбран, **формально закрытых новых findings в integration — 0**. Это ограничение размещения и приёмки source, а не опровержение трёх подтверждённых критериев.

## Что передать исполнителю

1. [Замечания и точные действия](review-findings.md): V6 profile join; I1 checkpoint matrix; I4 historical-index migration; R4 lease residual; исправления packet provenance и denominator.
2. [Сверка исходных требований](criterion-review.md): все 17 IDs / 18 occurrences, без подмены исходного критерия названием новой задачи.
3. [Машинные решения](decisions.json): exact candidates, отдельно task exit, criterion outcome, code integration и formal closure.
4. [Проверки и deciding evidence](evidence.json): происхождение, доступность, новый независимый R2 run и ограничения.

Свободное место после узкого прогона — около **8 GiB**, ниже пользовательского порога 18 GiB. Широкие replay/build/install/сканирования не запускались. Изоляция занимала только воспроизводимый выбранный source/test/config snapshot; ценные данные и чужая текущая работа не изменялись. Это основание не расширять локальную вычислительную волну без проверки доступных ресурсов, но не основание останавливать чтение, исправления документации или работу независимых владельцев.

## Pattern pass

P01/P02: task milestone отдельно от полной capability. P05/P07/P08/P14: scope/time/source qualification сохранены. P29/P32/P38: реальный FD oracle и обнаруженное расхождение полной ref identity с трёхполным comparator. P35/P36: 17 IDs, 18 occurrences и 53 прямые ссылки получены из полных выбранных наборов; R4 count исправлен по runtime roster. P40: V6 — тот же класс неполного content/profile binding, исправлять один invariant, не отдельный пример. P41: неизвестная краснота не названа inherited. `verification_missing`/`semantic_test_missing` указаны там, где код/тест существует, а решающего исполнения ещё нет; новые глобальные production/browser/all-backend gates не введены.

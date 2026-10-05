# E02: решения для полного исполнения A–F

Этот пакет задаёт следующую работу после первых реализаций A–F. Он не меняет
finding statuses и не утверждает завершение E02. Цель — довести каждый исходный
критерий до работающего механизма, его потребителя и независимой проверки,
используя уже исправленные части.

**Срез анализа:** integrated source `97c85fae2d4505ec8248540d98b9556296244208`,
tree `e77c0741d3b19acb43e07a0de2bdb97c8fa98ee3`; опубликованные topic heads
отдельно закреплены в input identity. Source, на котором принималось исправление,
source итогового owner-прогона и source G различаются. Коммиты с документацией,
добавленные позже, не превращают старый run в проверку нового кода.

## Файлы для передачи владельцам

| Исполнитель | Документ | Основное решение |
| --- | --- | --- |
| A, локально | [A](A.md) | Замкнуть served цикл, changed-basis re-entry, N5/N8 custody, acquisition, empirical/forecast и replay. |
| B, облако | [B](B.md) | Устранить runtime deadlock/admission escapes и доказать deadline, cancellation, restart, CAS и budget на настоящих consumers. |
| C, локально | [C](C.md) | Довести no-loss stream/restore, source generations, schema/canon, installed surfaces и реальные методы/миграции. |
| D, облако | [D](D.md) | Реальный optimizer/GP state и predictive behavior, transfer generations, evaluator/funnel authority и history consumers. |
| E, облако | [E](E.md) | Корректные calibration/UQ/sampling/DoE/backtest функции и source-bound producer→consumer цепочка. |
| F, облако | [F](F.md) | Реальная causal estimation/identification/RBC/SCM функция, корректные scientific semantics, экономические и legal consumers. |

[Методы и библиотеки](method-decisions.md) фиксируют выбранные численные
решения и альтернативы. [Межгрупповые контракты](cross-unit-contracts.md)
дают writer/dependency порядок. [Проверка и closeout](verification-and-closeout.md)
различают oracle, bounded runtime, admitted inputs, backend и итоговый freeze.
[Runtime-профили](runtime-profiles.md) задают путь к реально исполняемым внешним методам.
[Семантические решения](semantic-decisions.md) фиксируют рекомендованный v2 и узкие вопросы ратификации.
[Аудит поставок](delivery-evidence.md) отделяет принятый код от итогов авторов.
[Очередность и поручения A–F](execution-sequence.md) дают готовые задания следующей волны.
Машинный [coverage manifest](coverage.json) связывает все исходные finding и bundle IDs с задачами;
это учёт документа, не автоматически достаточное доказательство поведения.

## Что уже установлено и чего из этого не следует

Importer `results/import_results.py --check` прошёл до использования pack.
Полный `verification.json` закрепляет 2 074 test-file/source-cut cells:
1 673 PASS, 307 FAILED, 88 ERROR, 5 COLLECTION_SKIP, 1 COLLECTION_ERROR.
Исходных VM raw archives получено 0. Grade остаётся
`transfer_and_navigation_only`, product closure — `not_established`.
Finding/consumer ownership берётся из полного allocation, не из выборки
`query.py --failures-only --limit 30`, которая показывает 30 из 401 не-PASS cells.

Полный ownership denominator — 127 bundle rows и 282 finding rows.
Исходный residual ledger имеет свой исторический census: 9 closed, 260 partial,
12 held, 1 open. Это состояние записи до нынешней приёмки, не текущий
повторный behavioral census. Старые closed получают regression protection;
partial/held/open получают исполнение исходного критерия и отдельное closure решение.

Итоги шести owner-чатов не заявляют новых formal closures. Их scoped PASS могут
подтверждать полезные свойства; они не доказывают весь пакет. G уже принимает
ограниченные code slices append-only. В частности отказ от ложного corrected
RDD или conditional SHAP защищает честность, но оставляет соответствующую
реальную функцию задачей владельца. Ошибка входа при bootstrap не является
численным дефектом; отсутствующий backend не является PASS.

## Как исполнять

1. Владельцу передаётся его файл и общие method/contract/verification решения.
   Он фиксирует exact fetched integration base и полный actual diff footprint.
   Повторное исследование уже доказанной неизменившейся части не требуется.
2. Для каждого механизма сначала назвать estimand/property и production caller,
   затем positive functional example, независимый oracle и divergent negative.
   Перенести выбранное решение в существующий canonical owner. Заместить
   прежний default/caller в том же срезе; новый неиспользуемый helper не закрывает задачу.
3. Включить тесты и обязательные companions вне искусственного mechanism path cap.
   Запускать targeted defining-property и affected consumer checks. Новый upstream
   contract вызывает повтор затронутого downstream check, без полной волны каждый раз.
4. Принимать код и closing finding отдельно. Refusal-only repair, statistical
   approximation и непроверенный deployment не получают full functional closure.
   Облако не нуждается в локальном production dataset для математического DGP.
   Только intrinsically data-dependent criterion получает exact local read-only check.
5. После приёмки всех требуемых срезов G замораживает source, проводит один общий
   replay/CI и local data-dependent closeout, фиксирует closed/limited/held,
   unavailable inputs, skipped backends и remaining verification. Push main требует
   отдельной явной авторизации.

Решения о новой public-IR научной семантике ниже являются конкретными proposals
для именованного semantic owner. Документ не заменяет ratification и не отдаёт
G ownership finding или научную подпись. Работа над независимыми механизмами
продолжается параллельно, пока такой owner оформляет versioned решение.

## Pattern pass и критерий достаточности самого плана

P01/P02/P03 требуют реального producer→artifact→bridge→consumer→surface.
P05/P15 не допускают authority из LLM, UUID, checksum или self-attestation.
P27/P31 требуют canonical owner и исправление класса, а не соседних симптомов.
P29/P32/P33/P37/P38 требуют property witness, independently bound inputs и
случай расхождения с proxy. P35 требует полного 127/282 покрытия с denominator.
P40 запрещает бесконечную лестницу patch→escape: после второго случая расширить
общий механизм либо сформулировать конечную supported boundary с falsifier.
P41 требует точной команды на slice-base и доказанного disjoint input denominator.

Acceptance документа: каждый исходный finding ссылается на конкретную задачу,
каждый bundle учтён; задача содержит selected mechanism, writer, consumer,
необходимые inputs, положительный функциональный результат, independent oracle,
negative/adversarial control, команду и границу closure. Отсутствующий input
назван по содержанию и роли, а также указано, как его получить или какую
корректную supported функцию можно построить без него. Количество зелёных тестов,
наличие планов и слова “covered” этим критерием не являются.

Проверка полноты воспроизводится из Git: `python3 policy-engine/docs/research/e02-cloud-test-plan/closure-decisions/validate_coverage.py --self-check`.
Она сопоставляет полные наборы и ownership, исходные criterion bytes и task anchors;
count-preserving подмены ID, hash и anchor должны отвергаться. Это проверка учёта,
а не математической корректности или product closure. В исходном TSV `LA-053`
имеет текстовый `source_closure_owner`, а не bundle ID; индекс сохраняет этот
literal и маршрутизирует задачу в единственный исходный companion `PCL-01`.


## Что передавать в следующие задачи

Передавать владельцу его A–F файл вместе с этим README, method-decisions,
runtime-profiles, semantic-decisions, cross-unit-contracts и verification-and-closeout.
Поручение: исполнять выбранные решения по полному собственному набору, переиспользовать
проверенные неизменившиеся механизмы, исправлять реальные разрывы и возвращать
finding-by-finding closure с решающим output. Выпуск ещё одного bounded helper
или честного отказа допустим как checkpoint, но не как окончательное исполнение
критерия, который требует работающий метод.

Для каждого ID сначала сверить сегодняшний механизм: уже правильному коду может
требоваться только недостающий прямой consumer witness. Историческая четырёхбазовая
таблица не становится новым универсальным условием закрытия. Для утверждения
«красный унаследован» действует отдельный P41 replay на точном slice-base и полный
знаменатель его входов. При отсутствии такого утверждения проверять сам исходный
критерий на exact candidate; старую provenance-неопределённость записать отдельно.

Запись CAN приёмки опубликована документальным commit
`385a997603e85b5aa71b54f6b51c0d89a24839bd` поверх source G97. Checkpoints 01–07
содержат 14 bounded code slices и один D census/navigation slice; новых finding
closure нет. Документы этого пакета добавляются поверх этого checkpoint и не
переписывают source, на котором выполнены старые проверки.

## Главные выбранные изменения

| Зона | Решение, которое даёт функцию | Проверка против подмены |
| --- | --- | --- |
| A | Один штатный cycle/context provider; admitted changed basis вызывает новый N5 для прежнего candidate и сохраняет обе occurrences. | UUID/time-only изменение не считается новой basis; настоящая admitted observation меняет consumer result. |
| B | Deadline и terminal accounting охватывают реальное владение handle/worker; CAS сохраняет tenant claim при exact same-owner reuse. | Поздний handle не публикуется, незавершённый thread держит physical slot, foreign/unbound import не меняет intent/claim. |
| C | Один durable stream frontier и atomic selected generation; conditional BERL получает настоящий law-bound sampler. | Cap после restore, crash/restart, source membership и correlated-Gaussian conditional oracle. |
| D | BoTorch/GPyTorch хранит fitted state и conditioning basis; каждый transfer reader видит одну generation. | Независимая формула GP posterior, cross-process old-or-new read, реальный budget debit и typed permission. |
| E | Gaussian-likelihood inference отдельно от curvature; joint law отдельно от marginals; MC precision отдельно от predictive spread. | Analytic Hessian/covariance, tied draws, failed-domain denominator и estimator-specific error control. |
| F | Настоящий rdrobust RBC; исполняемый DoWhy profile; корректные graph/SCM/CI semantics. | Curved heteroskedastic DGP, фактический backend fit, multiedge permutation и predictive-vs-inferential discriminator. |

Все эти строки — выбранное направление следующей реализации, а не заявление
о её сегодняшнем завершении. Экономические цели и public-IR authority требуют
именованной semantic ратификации; технические исправления и независимые проверки
в остальных очередях не ждут её.

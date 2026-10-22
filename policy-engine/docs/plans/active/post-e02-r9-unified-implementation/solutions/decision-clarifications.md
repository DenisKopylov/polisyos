# Нормативные границы, которые инженерная рекомендация не меняет

Это конкретные предложения для проверки владельцем исходного критерия. Они не меняют system-design-decisions и не дают разрешение на реализацию до E02 acceptance. Пакет не переоткрывает уже принятые B01/C01/C02, ADR-0178/0179, AD-E02-01–03 и другие действующие решения.

## GYD-09: подготовить update path, сохранить действующий запрет активации

Основание: [withheld-propositions-register.md](../../../../system-design-decisions/withheld-propositions-register.md), **WP-01, WP-02, WP-03**; исходный GY-O1 и W5-K03. Сейчас WP-01 прямо сохраняет отсутствие posterior mutation. WP-02 не разрешает routine assimilation schedule. Принятый vocabulary/crosswalk и C02 о множественности inference profiles сами по себе не активируют политику обновления.

**Предпочтительный путь:** сначала реализовать в существующих owners живую диагностику движения, content-bound realized-versus-predicted comparison, provenance W4-K02, проверку ancestry, observation validity, interference/context и механизма. Весь путь до fresh consumer должен поддерживать действующий отказ от изменения posterior. Отсутствующий producer — задача инженера, а не требование принести внешний документ.

Затем представить компетентному principal конкретный activation packet WP-01: версии producers/rules, полный conjunction и основания каждого predicate, положительный допустимый пример, unresolved/mixed contributors, неверная ancestry, observation-process change и удаление самой activation-проверки. Рекомендовать scoped, versioned activation только для поддерживаемого effect/profile; вне него сохранять refusal. Если предполагается routine expected_variation, предложить отдельное решение R4-Q01/WP-02 с заранее объявленными schedule/eligibility/stop rules. Не выводить его из исправного discrepancy-driven механизма.

До решения допустимы инженерия, тестирование отказа и изолированное исследование estimator, но эксперимент не прикрепляется как operative posterior к claim/effect/world. Это не закрывает будущий положительный update-критерий. После решения активированный путь должен заново пройти собственный producer→artifact→O3→fresh reader falsifier. Другие независимые задачи программы продолжаются.

## GYD-08 / AS2: операционализировать sealed holdout без ложного сравнения

Исходный критерий требует выиграть у all-unresolved baseline по заранее определённой мере и отдельно содержит формулу «holdout-tuned classifier scores no better than one which never saw it». Из неё нельзя вывести универсальную теорему о численной точности: изолированная настройка по доступным holdout labels вполне может повысить измеренный score. Не определены comparator, доступ, направление шкалы и смысл слова score.

**Предлагаемое уточнение для владельца исходного критерия:** разделить predictive score и admissibility of evaluation. Классификатор с заранее замороженной версией сравнивается с all-unresolved по объявленной risk/coverage utility и margin на закрытом corpus. Преднамеренно contaminated challenger получает доступ к sealed labels или outcome-driven tuning; протокол должен обнаружить это по реальной истории доступа/версии/предъявления и не выдать ему **admitted evaluation**, независимо от того, выше или ниже его raw score. Сырые экспериментальные результаты сохраняются как contaminated. Этот challenger не может получить более сильное пригодное для O1 свидетельство, чем чистый участник.

Если владелец действительно требует численное сравнение двух моделей, он должен до раскрытия результатов выбрать population, independent evaluation set, loss/coverage measure, pairing/randomization, comparator и статистическое правило. Один пример не доказывает универсальное неравенство. Численные WP-09/WP-10 thresholds остаются withheld; здесь они не назначаются.

**Почему этот вариант предпочтителен:** он проверяет защищаемое свойство — отсутствие легитимации через утечку — и не обещает невозможного свойства всех обучаемых моделей. **Отклонённый вариант:** обучить оба классификатора и интерпретировать случайный меньший score contaminated модели как доказательство независимости. **Риск:** предлагаемое уточнение меняет операциональное прочтение оригинального done-критерия. Поэтому оно требует согласования его владельца; до этого literal criterion сохраняется и не считается закрытым.

Независимая инженерия sealed corpus, access custody, version binding, O1 refusal и отчёта может идти без этого согласования. Oracle labels остаются у уполномоченного evaluator; O1 получает разрешённое content-bound заключение и provenance, а не автоматически весь закрытый corpus. Это не новый общий барьер параллельности.

## Что не требует нового SDD

Source-use/AP07 owner allocation LIF-05, admission/host-enforcement seam LIF-06/OPS-08, provider budget OPS-07, PostgreSQL topology, UI Trust/Docs projection и finite EVSI calculation — конкретные engineering/rebind решения в существующих границах. Неизвестный API, отсутствующий parser или невыбранная структура файла не являются конституционным вопросом. Новое согласование требуется только если обнаруженное решение действительно меняет ratified authority/status/time/guarantee/criterion.

## Ограничение принятия

Ни одно предложение выше не является G acceptance, formal closure, научным результатом или изменением SDD. Применить нормативную поправку можно только после её отдельного согласования; остальные рекомендации остаются исполнимыми внутри действующих правил после E02 acceptance и scoped rebind.

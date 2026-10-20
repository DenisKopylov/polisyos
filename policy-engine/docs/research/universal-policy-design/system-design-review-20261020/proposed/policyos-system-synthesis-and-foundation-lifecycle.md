---
title: PolicyOS — System Synthesis and the Lifecycle of External Foundations
status: research synthesis; optional SDD placement not approved
created: 2026-10-20
decision_status: recommend retaining in research; SDD placement requires explicit user approval; no new ratification
supersedes: nothing
---

# PolicyOS: единое видение системы и жизненный цикл оснований

Этот текст — предлагаемая связующая design note. Он объединяет положительные механизмы проектирования с принятыми границами authority и custody. Он не заменяет исходные решения, не вводит новый subsystem и не устанавливает состояние реализации.

## 1. Вопрос и предлагаемое решение

PolicyOS должна уметь находить и проектировать решения в новых областях, объяснять их обоснованность, учиться на опыте и сохранять честность своих публичных выводов. Эти функции описаны в разных документах: causal north star, B-on-A architecture, execution/search targets, operating model и custody ratifications. Без связанного чтения можно ошибочно получить либо генератор идей без основания, либо механизм ограничений без способности создавать решения.

Предлагаемое решение — читать систему как один замкнутый процесс: **постановка вопроса → поиск оснований → порождение и композиция вмешательств → исследование альтернатив → обоснование вывода → внешнее институциональное решение/исполнение → наблюдение → диагностика → обновление знания и пересмотр собственных утверждений**. Неизвестность внутри этого процесса порождает исследование, acquisition, ограниченный вывод или новый design candidate; сама по себе она не запрещает candidate работу.

Альтернативы: оставить связь только в отдельных документах; расширить ещё один универсальный registry; заменить множество моделей единой численной score. Первое дешевле, но оставляет повторяющиеся смысловые разрывы; второе дублирует владельцев; третье скрывает несовместимые основания. После независимой критики предпочтены точечные поправки в документах-владельцах; эту связующую note предлагается пока оставить исследовательским crosswalk. Перенос в SDD имеет смысл лишь если он уменьшит повторяющиеся ошибки чтения без нового источника правил.

## 2. Что строится и что принадлежит PolicyOS

Система проектирует политики и хранит обоснование собственных выводов во времени. Её накапливаемый интеллектуальный актив — причинная модель мира вместе с проверяемыми измерительными, семантическими, нормативными и институциональными основаниями её применений. Policies — программы против объявленной модели и контекста; публичный claim — отдельный результат с точной областью допустимости.

Накопление такого актива не передаёт PolicyOS функции суда, администратора, исполнителя, платёжной системы или органа выдачи разрешений. Внешний акт остаётся внешним; система получает его evidence, проверяет допустимые отношения и пересматривает свои зависимые утверждения. Signature rule и own/integrate/observe/out_of_scope применяются к раздельным плоскостям цепочки, по identity decision и S0-K03/K04.

## 3. Универсальность как способность расширяться

Универсальная grammar и facet algebra позволяют выразить новые конструкции и композиции без каталога всех отраслей. Новые соответствующие существующему интерфейсу corpus resources должны обнаруживаться через действующие ports/indexes без per-domain allowlist. Обнаруживаемость, исполнимость и admission остаются разными свойствами.

Действительно новый operator, метод, язык обязательств или verifier может потребовать явного capability extension. Это не отказ от универсальности: универсальна способность выразить различие, сохранить неизвестное и расширить средства. Новизна ресурса не должна исчезать из candidate пространства только из-за отсутствия готового adapter.

Отдельно существует проверяемый публичный claim о границах универсальности. Успех нескольких примеров или число семейств в исследовательском каталоге не устанавливает certified envelope. B-promotion для конкретного результата и S14 universality claim не подменяют друг друга.

## 4. World model и основания её использования

Выбранные design targets допускают versioned конкурирующие causal hypotheses, set-valued reference, partial identification, heterogeneity и unresolved correspondences. Это согласуется с уже выбранными credal search/grounding targets; не требуется новый «multi-model engine» рядом с ними. Одинаковые наблюдения могут быть совместимы с разными последствиями вмешательства.

Внешние основания включают наблюдения, качественное знание, понятия, методики измерения, causal assumptions, статистические конвенции, закон, institutional acts, ценностные позиции, capacity и права доступа. Их цифровая форма не делает их взаимозаменяемыми. Дополнительные строки не создают мандат; причинная идентификация не выбирает общественную цель; подпись не доказывает governing correspondence (W5-K01/K07/K08).

Следует различать ресурс, конкретное положение из него и task-specific use. Для применения требуется не только source ref, но и обоснование соответствующей связи: variable→construct, method→estimand, output→metric, source→target context, norm→lever, mandate→objective. ADR-0179 уже принимает meaning principles correspondence и различает evidential assessment и constitutive act. Общая acceptance rule описана в её register row; для первых concrete profiles и purpose-qualified review остаются названные открытые входы. Этот документ не назначает reviewer и не создаёт положительного решения. Candidate uses могут исследоваться условно, с явно перенесёнными assumptions и unknowns.

## 5. Как основания участвуют в дизайне

Intent задаёт требуемый эффект, контекст, principal и ограничения, сохраняя неразрешённые вопросы. Concept/requirement machinery раскрывает необходимые основания. Discovery приносит существующие и новые варианты. B порождает вмешательства и композиции; A проверяет применимые обязанности assurance через соответствующих владельцев и evidence paths. A не является универсальным арбитром по науке, праву и ценностям. Acquisition может изменить и знание, и постановку задачи, и доступное пространство действий.

Один policy task может исследовать несколько datasets, операционализаций, методов, causal structures, scenarios и нормативных рамок. Совместимость не предполагается по общей JSON-форме или числовой единице. Разные estimands и contexts сохраняются раздельно либо связываются обоснованным преобразованием.

Закон не выбирается по желаемому outcome: применимый режим устанавливается по контексту, а правовая реформа рассматривается как отдельное вмешательство. Предпочтения можно исследовать условно; от имени principal выбирать objective/tradeoff можно лишь на соответствующем основании. Конфликтующие рамки могут дать несколько условных решений вместо одного искусственного победителя.

Портфель для major empirical claim по ADR-0160 сохраняет спецификации, выбранные и отвергнутые линии, зависимость и контрсвидетельства. Adaptive discovery не становится подтверждением только от последующей регистрации плана. Confirmation требует подходящего дизайна и применимых гарантий. Percentage-of-positive-specifications не является вероятностью эффекта без отдельной вероятностной модели.

## 6. Model intervention и реальное исполнение

Интервенционный атом остаётся относительным к model resolution: operator, target-slot, bundle direct effects и declared intended effect; goals остаются отдельным слоем выбора. Model-side `do()` описывает операцию в модели. Реальное изменение требует связи с institutional lever, implementation, take-up/compliance и возможными стратегическими реакциями.

Целый design требует совместного анализа взаимодействий. Pairwise consistency и сумма локальных эффектов не доказывают whole-design validity. Simulation — важный выбранный механизм исследования этих взаимодействий. **Отдельное предложение C01, ещё не принятое:** разрешить точный совместный расчёт или иной валидированный joint witness для конкретного свойства вместо обязательного simulation witness. Это не разрешает пропустить joint evaluation. Ни simulation, ни математическая композиция сами не подтверждают эмпирическую истинность используемой модели. Научная, правовая и implementation применимость остаются отдельными обязанностями.

## 7. Поиск и приобретение

Eligibility предшествует VOI/ranking. Разрыв может требовать нового наблюдения, identification experiment, semantic mapping, method contract, permission, actual institutional act или уточнения principal. У каждого маршрута свои условия, цена, failure modes и доступность. Численная VOI не навязывается, если не установлены её decision/payoff/probability предпосылки.

Поиск сохраняет frontier, release/index, query, cutoffs и причины включения/исключения. Такой след обеспечивает обозримость, но не доказывает recall. Known-groundable misses, stale index и недоступный канал нельзя выдавать за предел доменного знания. Исторический успех acquisition обучает будущему поиску; он не является evidence текущего claim.

## 8. Обучение и сохранение причин ошибок

Различаются обучение discovery, применимости методов, эмпирической модели и пониманию институционального/ценностного контекста. У каждого свои сигналы и границы. Неисполненная альтернатива не получает отрицательный outcome; повторное использование одной study не создаёт независимое подтверждение; высокий retrieval score не придаёт source authority.

Confirmatory и exploratory контуры сохраняются. Способ inference/update выбирается по свойству и дизайну; Bayesian posterior — предусмотренный путь, но сам по себе не подтверждает identification, implementation или transfer. INT и credal targets уже допускают разные значения утверждений, включая set-valued и no-number. **Отдельное предложение C02:** расширить формулировку North Star §6 до явно квалифицированных inference/update profiles; принятие этой возможности не авторизует конкретную мутацию posterior и не снимает требований diagnosis/admission.

Аномалия требует диагностики: изменились мир, измерение, исполнение, selection, incentives или модель? `diagnosis_unresolved` не даёт causal update по W5-K03. Защитная реакция может иметь собственное основание, не становясь доказательством причины (W5-K04). Новая информация может сузить прежний вывод; это корректный результат обучения, а не деградация продукта.

## 9. Наблюдаемость и custody

Пользователь должен видеть смысл результата, выбранные основания и альтернативы, sensitivity, ограничения и условия пересмотра. Expert/reviewer/machine проекции раскрывают необходимые методы, relations, provenance и checks в рамках разрешённого доступа. Public projection не усиливает authority, certainty или currentness; она сохраняет существенные отрицательные результаты и относительную область вывода (PV-K01–K09).

Данные поиска, graph topology, timestamps и stable identifiers тоже могут раскрывать чувствительные сведения. Hash не является privacy protection. CTM сохраняет отдельные роли времени у canonical owners; новый универсальный event envelope не требуется.

Изменение источника или институционального контекста рассматривается по реальным claim dependencies. Исторический replay остаётся на прежних refs/rules; текущая публичная позиция проходит revalidation/reissue/withdrawal при соответствующем основании. Scope этой обязанности — собственная подпись PolicyOS, не управление чужим процессом.

## 10. Размещение и критерии полезности

Reuse map: Data Forge/Fabric — acquisition и source artifacts; Scholar/academic SKG — discovery и научные положения; Lex — правовые источники и scope facts; Foundry — методы/модели/симуляция; Scientist — workflow, portfolios, arguments и governance; существующие Runtime/CTM/custody/surface owners — orchestration, время и объяснение. Это семантическая карта, не новое назначение authority и не statement о полноте реализации.

Наблюдаемые различающие случаи для будущей реализации:

- новый тип основания остаётся видим candidate discovery без правки domain allowlist;
- обоснованная смена метрики меняет ranking, и surface показывает зависимость;
- хорошо подобранная статистическая модель с неверной causal structure не получает causal authority;
- реальная capacity/permission gap не скрывается успешной simulation;
- противоположные outcomes при допустимых предпосылках сохраняются без удобного усреднения;
- source correction запускает оценку затронутого claim, сохраняя прошлый replay;
- отсутствие институционального положительного основания не запрещает инженерную реализацию candidate и refusal путей.

Принятие этой note, если оно состоится, не принимает код и не закрывает findings. Новое правило authority, назначение adjudicator или изменение принятого target contract требует отдельного решения там, где оно связывает исполнителя. Условия пересмотра: конкретный конфликт с ratified clause; доказанный redundant owner; новый case, который текущая composition не выражает; либо устойчивое сужение candidate work из-за этой формулировки.

## 11. Источники и standing

Ссылки при предлагаемом размещении в `system-design-decisions`: causal north star §§2–10; target architecture D0/D2–D4; organizing rules Rules 1–12; execution topology; accepted search и CGF target specs; best-in-class operating model; identity §9; S0/INT/PV/W4/W5 ratifications; CTM. Accepted ADR-0160/0166/0172/0174/0179 задают соответствующие portfolio/acquisition/memory/discovery решения. Точные документы и hashes перечислены в research review `document-map.json`.

Pattern pass: P01/P02/P05/P07/P08/P10/P13/P14/P15/P16/P17/P20/P24/P25/P27/P35/P37/P38. Missing capability labels присваиваются только после проверки реальной цепочки конкретного механизма; эта synthesis не оценивает runtime completeness.

### Прямые ссылки для этой research-копии

- [North Star](../../../../system-design-decisions/policy-design-causal-operating-system-north-star.md), §§2–10; [CGF](../../../../system-design-decisions/policy-design-causal-grounding-firewall.md), §3; [Search](../../../../system-design-decisions/policy-design-search-target-spec.md), §§1–5.
- [Identity](../../../../system-design-decisions/policyos-identity-and-custody-boundary.md), §§4,9; [S0](../../../../system-design-decisions/stage0-custody-kernel-ratification.md), K03/K06; [W5](../../../../system-design-decisions/wave5-evidence-substitution-ratification.md), K01/K03/K07/K08.
- [ADR-0160](../../../../adr/0160-evidence-portfolio-independence-multiverse-synthesis.md), [ADR-0172](../../../../adr/0172-balanced-memory-influence-ledger.md), [ADR-0174](../../../../adr/0174-policy-evidence-capability-graph.md), [ADR-0179](../../../../adr/0179-correspondence-vocabularies-meaning-principles-first-profiles-open.md).
- [Все 20 source documents](../document-map.json) и [раздельные варианты согласования](../02-approval-options.md).

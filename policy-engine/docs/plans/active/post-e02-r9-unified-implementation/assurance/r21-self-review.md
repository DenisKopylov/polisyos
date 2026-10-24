# R21: самостоятельный критический разбор free-grow и исполнимости

24 октября 2026. Автор и reviewer delta — root; субагенты в этом раунде не
использовались по запросу пользователя. Base:
`30e70777b2c577c66912af3e24d7fd123bfdfde8`. Это исправления **плановой документации**,
не независимая приёмка будущего кода. Implementation, product checks и E02 acceptance
этим пакетом не выдаются. Новые изменения system-design-decisions не внесены.

## Вывод и границы разбора

Основные возможности плана сохраняются: содержательный поиск, несколько научных
оснований и моделей, адаптивные стратегии, проектирование исследований, обучение,
долгосрочная custody и рабочие поверхности. Проблема этого delta — несколько
мест, где конкретный первый маршрут, способ проверки или физическая реализация
могли стать универсальным ограничением. Ни полный новый scheduler, ни новые
верхнеуровневые задачи для исправления не нужны.

Проверены полный состав task/solution IDs, прямые зависимости, все extension
mirrors и question→task маршруты. Содержательный разбор сосредоточен на
cross-owner границах acquisition, resource lifetime, квалификации, reuse,
extensions и источниках нормативных требований. Это не утверждение о повторной
построчной научной верификации всех исследований или готовности runtime.
Исторические R13–R20 reviews и результаты сохранены как результаты своих версий.

## Найденные проблемы и выбранные исправления

| ID | Проблема на base | Исправление и owner | Различающий будущий сигнал |
|---|---|---|---|
| R21-01 | S15 называл D2.3 grounds ratified; повторяющийся спрос становился необходимым даже для одного существенного counterexample. | GYD-32 и S15 используют точный принятый Vision §11/native-owner contract. D2.3 — проектные примеры, не закрытый eligibility list. Изменён routed R19 delta и question research text. | Единичный существенный контрпример может войти в исследование/extension; это не даёт ему authority. Same-schema смена unit всё ещё требует semantic qualification. |
| R21-02 | CAP-02 «single-response first» и CNT-03 WDI rule могли распространиться на все источники и сериализовать независимые adapters. | Сохранён исходный WDI A1 witness и его more-pages refusal. Другие выбранные file/query/stream/paged protocols готовятся независимо и активируются по собственным CAP/LIF/rights/resource predicates. | Другой qualified protocol проходит свой fresh consumer без fictitious HTTP/WDI semantics; WDI receipt не закрывает его missing continuation. |
| R21-03 | CAP-04 подробно задавал feed route, но не исполнимый путь для источника без журнала. Отсутствие feed могло остановить вообще любую реакцию на реальные изменения. | CAP-02 supplies comparable observations; CAP-04 emits exact **observed** change/coverage loss; LIF-02 owns scoped reaction. Local observation journal не объявляется полным журналом источника. | Изменение без webhook достигает fresh reader. A→B→A между опросами остаётся неизвестным; failed/partial poll не доказывает unchanged/repeal/deletion. |
| R21-04 | OPS-08 запрещал unmeasured class, не определяя доступный путь первого измерения; one-class/cap-at-a-time превращал диагностический приём в общее ограничение параллельности. | OPS-08 проводит qualification внутри уже проверенного, разрешённого finite enforcement envelope; LIF-06 сохраняет единый admission owner. Production/duty eligibility появляется только после измерений. Изолированные lanes могут идти параллельно, interacting policy требует joint-load evidence. | Новый class измеряется без protected commitment; без envelope run запрещён. Две независимые qualification lanes работают, но shared capacity не умножается. |
| R21-05 | LIF-06 разрешал «transfer or release reservation» без явного сохранения живых allocations родителя. Ledger release мог выглядеть как освобождение RAM. | LIF-06 и R16 C7 учитывают actual lifetime: combined peak, уже зарезервированный envelope либо verified physical release. CPU yield не освобождает memory/disk. | Parent держит 60/100 RAM, child требует 50: ledger transfer не допускает запуск. Shared buffer считается один раз, copy отдельно; реальное освобождение позволяет продолжить. |
| R21-06 | Fresh use был описан без явного различения повторной проверки текущего допуска и дорогого immutable assessment. Исполнитель мог заново читать/верифицировать весь корпус на каждом использовании. | LIF-01 owns exact assessment reuse; CAP-03 consumes it. Current rights/purpose/generation/fence остаются actual checks. Cache допустим только с полным relevant dependency closure; он не новая authority. | Одинаковый covered use не вызывает повторный scientific verifier; changed rights/rule или matching dependency меняет решение при тех же bytes. Cache-off сохраняет смысл результата. |
| R21-07 | Single owner мог быть прочитан как global mutex/process; OPS-10 требовал semantic adapter для каждого нового mount/configuration. | LIF-04/OPS-10 сохраняют canonical invariant owner, разрешая concurrency по доказанно disjoint keys. Поддержанный semantic class использует тот же adapter с собственным configuration conformance. | Второй bucket/site того же supported class не требует central-code diff; changed semantics не заимствует старую проверку. Shared budget нельзя разделить tenant labels. |
| R21-08 | CNT-03 «without deleting provenance history» мог противоречить lawful deletion/minimization, уже заданной LIF-05. | CAP-03/CNT-03 явно подчиняют retention также identifiers, hashes и lineage; сохраняется только разрешённая история. Lost replay/verification показан как limitation. | После applicable deletion решение нельзя обойти history/cache/export/restore. Разрешённый минимальный receipt не выдаётся за сохранённые forbidden bytes. |

Дополнительно исправлен текущий общий reader guide: учитывать **все присутствующие
`*_extension`**, не только R14/R15; брать denominator из manifest, не исторических
109 карточек/26 семейств. Общая заметка об O2→O3 теперь явно сохраняет отдельный
structural route R20, а не требует O1 posterior от любого вида научного результата.
Это перенос уже выбранной границы, не новое разрешение operative world write.

## Почему ограничения сняты именно здесь

- **Оригинальные критерии сохранены.** A1 single-response witness остаётся
  обязательным в его исходном scope. Параллельная работа другого adapter не
  закрывает A1. Новый ресурс не принимается одной registry-записью.
- **Подготовка, квалификация, применение разделены.** Measurement envelope должен
  существовать до неизвестной нагрузки. Prototype/candidate label не даёт права
  расходовать неизвестные ресурсы, раскрывать данные или принимать custody duty.
- **Scope cache не равен stale admission.** Immutable assessment может жить долго;
  текущее использование проверяется по relevant versioned dependencies и fence.
  При неизвестной полноте зависимостей используется scoped requalification или
  честное ограничение, а не optimistic cache hit.
- **Наблюдение не превращается в внешний акт.** Poll может доказать полученные
  bytes/изменение выбранного представления. Он не доказывает отсутствие событий
  между polls, юридическую отмену или полноту всей external source history.
- **Canonical ownership — семантическая граница.** Source-file leases остаются
  single-writer. Runtime partitioning требует доказательства разделимости;
  provider-principal cap, common head и disclosure budget остаются общими.
- **История сохраняет правдивость, не запрещённое содержимое.** Решение об удалении
  принадлежит actual retention/rights owner. Документация не устанавливает новый
  закон или retention duration и не обещает физическое удаление внешних копий.

## Собственные повторные атаки на исправления

| Атака | Решение после повторного review |
|---|---|
| Назвать dangerous job «measurement» и запустить его на serving host. | Не допускается: требуется ранее проверенный конечный isolation/enforcement envelope, service/platform permission, reserve, scratch/time bound. Иначе suitable isolated host или unavailable. |
| Дать каждому child копию reservation parent-а. | Учёт привязан к actual allocation/lifetime и общему owner; передача ownership не увеличивает capacity. Shared buffers и copies различаются. |
| Превратить «same configuration class» в обход provider conformance. | Exact selected namespace/IAM/retention/restore evidence остаётся обязательным; changed semantics требует adapter delta. |
| Считать successful poll новым legal event или восстановить current после пустого feed. | Observed-change и source-authoritative semantics различаются; coverage/as-of limitation сохраняется и потребляется LIF-02. |
| Reuse assessment с тем же content hash после revoke, смены rule или появления нового matching source. | Cache зависит от полной relevant closure, включая negative/membership queries; fresh-use fence не кешируется как вечное allow. |
| Снять need for repeated demand и тем самым разрешить arbitrary plugin/new authority. | Допускается рассмотрение counterexample; compilation, waist, owner contract, provenance, conformance и authority boundary остаются. |
| Удалить всю историю по неподтверждённому запросу и назвать это privacy. | Нужна applicable owner-qualified retention/deletion decision. Правомерная оставшаяся история сохраняется; запрет raw/history не назначается caller-ом. |
| Начать код, поскольку план стал детальнее. | P0-ACCEPT и actual E02 acceptance остаются неизменным глобальным входом. |

## Передача исполнителю и проверка документации

Изменены существующие task/solution строки CAP-02/03/04, CNT-03, GYD-32,
LIF-01/04/06, OPS-08/10 и соответствующие prose cards. Отдельные root tasks,
новые product enums, центральные services и глобальные зависимости не добавлены.
R19 routed question сохраняет identity; его normative rationale уточнён.
Новые falsifiers добавлены в task acceptance steps и preferred acceptance,
а обязательные связанные поля/карточки синхронизированы.

[Документарная проверка R21](r21-validation.json) воспроизводит состав tasks,
mirrors, маршруты, прямой DAG и локальные ссылки; она не проверяет научные или
runtime свойства перечисленных future tests. Субагенты, product imports, tests,
builds, installs и production reads не запускались. После реальной приёмки E02
исполнитель перепривязывает actual owners/paths и выполняет эти semantic probes
на реализации. Обоснованное отклонение от механизма допускается через existing
change/rebind procedure с сохранением исходного свойства.

Pattern pass: P01/P02/P05/P07/P08/P13/P27/P29/P31/P32/P35/P36/P37/P38/P39/P40.
Класс исправления — ложное универсальное ограничение/подмена свойства его
процедурным proxy. При обнаружении ещё одного примера применяется общий invariant,
а не новый локальный default. `product_verification=UNRUN`, `closure_ids=[]`.

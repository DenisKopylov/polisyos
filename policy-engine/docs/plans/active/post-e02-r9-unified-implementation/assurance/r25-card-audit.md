# R25: нагрузка карточек на исполнителя

Документарный аудит полного текущего task manifest и рекомендаций исполнения.
База — R24 `f8e2c66edf6b56a5436e696e669bfe690f68e58b`. Product implementation и
runtime verification — **UNRUN**. До фактической приёмки E02 реализация не начинается.

## Вывод

Часть карточек действительно объединяет несколько самостоятельных работ.
Другая часть велика из-за общего инварианта и обязательных companions: её
механическое деление создаст разные трактовки одного контракта. Третий источник
перегрузки — повторяющиеся указания читать весь родительский пакет, хотя leaf
получает только один из его механизмов.

Поэтому R25 вводит два уровня: canonical parent с полным обязательством и
bounded work packet с конкретным результатом. Родительская карточка не удаляется,
не переименовывается и не закрывается суммой leaf PASS. Это сохраняет source
traceability, а исполнителю даёт меньшее замыкание необходимого контекста.

| Форма выдачи | Родителей | Значение |
|---|---:|---|
| `split` | 48 | Кандидаты на несколько различимых outputs/properties с явными owners и join |
| `sequence` | 40 | Один writer/инвариант, продолжение через полные checkpoints; подготовка может идти параллельно |
| `retain` | 33 | Связный scope либо aggregate coordination/acceptance; убрать дублирующую историю, сохранить нужный контекст |
| Всего | **121** | Полный набор `tasks.json:tasks[*]` и соответствующих 121 preferred rows |

Шесть `retain` — два P0 и четыре FINAL: они остаются coordination parents,
а не назначением всей реализации одному leaf. Число потенциальных результатов
не равно числу новых capabilities или одновременно работающих writers.

## Что изменено

1. [Полный audit](../execution/task-decomposition/audit.json) содержит решение и
   rationale для каждого ID, а для составных задач — предлагаемые меньшие
   observable результаты и границы владельцев. Это каталог для root/lead.
2. [Правила](../execution/task-decomposition/README.md) и
   [work packet](../execution/task-decomposition/work-packet.md) требуют полного
   маршрута обязательств у родителя и точного operative context у leaf.
   Общее ограничение не считается выполненным output; unknown applicability
   не превращается в exclusion.
3. [Пять подробных примеров](../execution/task-decomposition/proposals.md)
   показывают различные случаи: последовательный LIF-02, составной GYD-30,
   persistence/recovery OPS-05, verification campaigns DES-10 и surface UI-02.
   Для каждого результата указаны inputs, output, owner, preparation/composition
   и positive/negative/removal signals.
4. Writer/reviewer/verification/foundation-supplier prompts теперь явно задают
   приоритет bounded reading над старыми широкими указаниями читать все extensions.
   Root/lead по-прежнему читает весь parent и отвечает за exhaustive allocation.
   При прямой выдаче целого parent полный scope сохраняется.
5. Устранено реальное противоречие маршрутизации GY-DEF22: старое поле DEB-09
   повторно назначало internal owner acceptance, уже принадлежащую DEB-04.
   Теперь DEB-04 имеет complete current bounded-claim set и content-bound
   owner readback; P41 остаётся отдельным обязательным conjunct. Исторические
   «шесть» не являются постоянным acceptance denominator. GYD-15 сохраняет
   свой FA1 mechanism; DEB-09 сохраняет реальные institutional slots/GY-DEF23.

## Почему это уменьшает контекст без потери смысла

Leaf должен удерживать свойство, реальный путь producer→artifact→consumer,
зависимые semantics и весь footprint этого изменения. Ему не требуется помнить
историю всех соседних mechanisms и заодно реализовывать их. Root/lead удерживает
полную карту покрытия, источники и joins, но может распределять подготовку этой
карты по семействам и проверять её против полного source set. Ответственность
за полноту не требует помещать весь репозиторий в один prompt.

Предпочтительная граница — полезный результат с реальным owner/interface/stage,
который можно опровергнуть независимо. Слои «DTO отдельно, runtime потом, tests
ещё позже» допустимы только как подготовка с явным unfinished capability.
Нельзя потерять generated/client/migration companions ради размера.

Для sequence сохраняется один native механизм. Проверенный checkpoint передаёт
новому назначению exact contract/result refs, текущее состояние и остаток;
память старого чата не является входом. Отдельные consumers и oracles могут
готовиться одновременно, если actual writes и shared resources это позволяют.

## Review и исправления

Семь прямых помощников рассмотрели непересекающиеся назначенные семейства;
восьмой атаковал сам механизм декомпозиции и leaf prompts. Дополнительные CNT
наблюдения CAP reviewer использованы как сверка, но исключены из canonical
счётчика: одна оценка на каждый ID. Root прочитал все рекомендации, сопоставил
различия между split и sequence, проверил пять подробных примеров и оставил
один original task registry. Дети, product процессы и новые окружения не запускались.

В review исправлены следующие реальные риски:

- «Другой контекст» сам по себе не основание split: нужен самостоятельный
  observable result и фактическая граница, иначе сохранить sequence/retain.
- Shared clause — ограничение. Для substantive obligation всё равно нужны
  owner, output/evidence, parent join либо qualified disposition/явный остаток.
- Slice ID не создаёт ещё один DAG/status/closure authority; multi-parent
  packet отдельно reconciles каждый source route.
- Пропущенный clause приостанавливает affected writes/acceptance, а не всю
  очередь. Незатронутые назначения продолжаются.
- Первоначальная формулировка leaf scope оставляла старое требование «читать
  extension целиком». Добавлен прямой приоритет exact assigned clauses и их
  транзитивных contracts; applicable repo instructions не сужаются.
- GY-DEF22 исправлен в task field, preferred solution и human card вместе,
  а не только в пояснительной прозе. Независимый debt review дал bounded GO
  без изменения original inventory или criteria.
- В examples явно восстановлены inherited routes, которые могли спрятаться за
  общим описанием: qualified assessment против derivative-only variance, due
  при outage без overdue event, unsupported-cycle refusal без selected C2,
  actual invocation closure и stochastic attempts/late replies. Последующий
  delta review LIF-02 и GYD-30 подтвердил сохранение owners и conditional joins.

## Проверка и пределы

[Документарный receipt](r25-validation.json) фиксирует проверенный denominator,
целостность IDs/dependencies/extensions и relative links. Полные actual file/Git
read records и outputs остаются в ignored scratch, с identity в receipt.
Это не runtime evidence и не эмпирическое измерение потерь контекста LLM.

Не утверждается, что все 48 составных родителей уже превращены в ready-to-run
assignments. Каталог даёт конкретные property boundaries, а пять examples —
полные формы таких границ. После E02 root выполняет accepted-source rebind,
полную clause allocation, назначает exact leases и materializes нужные packets.
Неизвестные будущие source paths не подменяются выдуманными pins. Реальная
параллельность и эффект на скорость будут проверяться при исполнении.

Сохраняются все исходные criteria и additive obligations. Ни количество букв,
ни число slices, файлов или checks не являются surrogate completeness gate.
Если actual source не поддерживает независимую границу, proposed slices
объединяются без утраты обязательств. Изменений system-design-decisions нет.

Pattern pass: P01/P02/P03/P13/P27/P29/P31/P35/P37/P38/P39/P40. Выявленные
document-level defects — чрезмерно широкий leaf reading scope и повторное
назначение GY-DEF22. Target: один canonical owner/parent, полное obligation
coverage, меньший executable context и реальный end-to-end join. Product
capability states остаются по текущему плану; документация их не повышает.

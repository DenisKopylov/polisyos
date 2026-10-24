# R24: redteam R23 — recovery, obligations и фактический consumer

24 октября 2026. Исходный R23: `b41bb846b0a2e596020185d0e5f9baf2c36709e4`,
tree `8e60d2f0c5f372e3f92b5252bb72d99fa1a4d3ad`. Только документация; E02
не принят этим review, runtime **UNRUN**, `closure_ids=[]`. Реализация начинается
после фактической приёмки E02 и source rebind.

Восемь прямых read-only reviewers исследовали reuse, observations, recovery,
queue, compatibility, dependency DAG, public consumers и free-grow. Root
сопоставил замечания с точными task/solution fields, внёс исправления и отдельно
проверяет изменённые условия. Дочерних агентов, тестов, сборок, установки пакетов
и чтения production payload не было. Это bounded review стыков R23, не новое
доказательство полноты всех исторических источников или работоспособности кода.

## R24-01. Оставшийся API/worker lockstep в rollback

**Найдено:** R23 migration и acceptance OPS-04 уже разрешали независимый rollback,
но `tasks.json → OPS-04.rollback` всё ещё требовал вернуть worker и API единой
парой. Исполнитель мог получить противоположные указания из одного задания.

**Исправлено:** поле rollback использует ту же directional API/worker/schema/rule
compatibility matrix. Останавливаются affected admissions; active leases и
неопределённые effects reconciled. Откатывается один компонент при поддержанном
mixed version; coordinated pair требуется только для такого selected profile.
Application/config artifact pair означает компонент и его настройки, не
обязательное одновременное обновление всей системы.

**Проверка после E02:** существующий R23 positive mixed-version job + fresh reader,
unsupported direction refusal и removal реальной compatibility check сохраняются.
Это пропущенный consumer того же R23 класса, не новый deployment subsystem.

## R24-02. Повтор stochastic computation не равен новому свидетельству

**Контрпример:** результат получен, persistence прерван, retry получает другое
значение; затем возвращается старый attempt. Одни seed/cache markers не решают,
какой realization принят и сколько независимых trial реально существует.

**Решение:** DES-03/GYD-30 связывают native invocation/trial, attempts, realization
или method-qualified realization set и accepted result. LIF-04 использует тот же
intent для orchestration recovery. LIF-01/07 и CAP-03 потребляют именно эту связь.
Изменившийся reply сохраняется как attempt output в допустимой retention границе;
новый artifact не увеличивает автоматически evidence denominator. Late attempt
не подменяет уже сосланный result и не получает authority через arrival order.

**Free-grow:** один job может законно содержать много samples, SCC iterations или
replicates — единицу и dependence определяет выбранный native method contract.
Qualified pure replay разрешён без внешней transactional ceremony. Replacement
realization допускается при явном successor basis и учёте failed/unknown attempts,
стоимости и selection effects. Retry-until-favourable не скрывается под recovery.
Если method не поддерживает восстановление конкретной realization, нельзя
объявить новый draw точным историческим replay; ограничивается эта гарантия.
Новой универсальной RNG schema, intent ledger или глобального result lock нет.

**Falsifier:** crash после draw до persistence → retry → late original output →
fresh trial/reuse reader. Accepted realization set однозначно связан с intent;
attempts не становятся независимыми наблюдениями. Explicit new replicate имеет
свой basis, но independence требует method criterion. Удаление этой связи при
сохранении markers обязано провалить double-count/substitution discriminator.
Это R23 reuse identity на producer/recovery boundary, а не замена scientific
validation подсчётом артефактов.

## R24-03. Service commitment переживает policy update и потерянный wakeup

**Контрпример:** v1 обещает service, v2 переводит класс в best-effort; старый duty
сохраняет age, но получает отказ по v2 до старого deadline. R23 age/review control
может остаться зелёным, хотя исходное обещание исчезло. Отдельно process-local
wakeup не гарантирует recovery durable duty после остановки worker.

**Решение:** existing LIF-04 intent/control-store record связывает stable duty,
admission-policy version, committed class/terms, original age и durable due/next
trigger generation. Обычные обновления policy применяются к новым admissions.
Изменение существующего duty — явный owner-qualified successor/cutoff/transfer,
с сохранением исходного обещания, missed interval и affected coverage. Native
automatic transitions разрешены; нового обязательного human approval нет.

**Критическая граница:** current safety/rights и реальные resource caps действуют
немедленно. Persisted promise не сохраняет старое разрешение или несуществующую
capacity. Невозможность исполнить прежнее обещание отражается как lapse/limitation,
а не как разрешение нарушить safety или переписать обещание задним числом.

Wakeup — hint; due work восстанавливается из durable state, duplicate/старые
generations fenced. Persisted effective-time basis и elapsed-duration clocks
различаются; нельзя переносить process-local monotonic timestamp как wall clock.
Неизвестность clock/order evidence ограничивает timing guarantee. LIF-06/OPS-08
дают current eligibility/measurement, а не переписывают обязательство.

**Falsifier:** v1 duty → v2 для новых admissions → потерянный/дублированный wakeup,
restart через due time и clock movement. Старый duty сохраняется либо получает
явную transition/lapse; новые admissions используют v2; safety блокирует unsafe
dispatch. Removal persisted commitment либо durable recovery должен выявить
downgrade/stranding. Это тот же R23 service-laundering класс, расширенный один раз.

## R24-04. Actual duty outcome должен доходить до fresh claim

**Пробел:** общая overdue-to-claim норма была у LIF-04/06/OPS-08, но в task LIF-02
не было явного selected composition join. Наличие обратного LIF-04 readiness
dependency не доказывает фактическую передачу результата consumer.

**Исправлено:** условное `LIF-02.conditional_acceptance_requirements` с actual
LIF-04 output, `required_stage=composition`, для claim с таким continuing custody
promise. Enrollment → due/continuation/cutoff/lapse → LIF-02 reaction → selected
fresh UI-02/UI-19/API reader. OPS-11 и resource outputs подключаются только для
их заявленного свойства; для них добавлены отдельные conditional composition
requirements. Applicability recomputed из native enrolled claim–duty relation и
coverage contract. Wrong duty/scope или omitted required relation не отменяют
обязанность и не восстанавливают green. Independent claim продолжает работу.

**Параллельность:** никаких новых start edges. LIF-02 owner readiness и agreed
interfaces позволяют параллельную подготовку LIF-04; completion witness ждёт
конкретные emitted outputs, не whole-task completion. Removal bridge при
сохранённых queue/review markers обязан обнаружить falsely current coverage.

## R24-05. Retained derivative после erasure и numerical document

**Найдено:** короткий OPS-05 acceptance говорил об unavailable erased-dependent
use без точной границы; DES-06 positive безусловно требовал recompute numbers.
Это могло запретить разрешённый historical/result-only use после удаления raw
input, хотя собственные custody contracts уже отличают эти режимы.

**Решение:** проверяется фактический use/dependency через LIF-05/LIF-07. Retained
assessment/model/result может использоваться при собственных current-use rights
и достаточном verification basis, в том числе через valid derivative-specific
rule. Mere receipt/hash/number недостаточен. Use, которому нужны удалённые raw
bytes или raw recomputation, остаётся limited/unavailable. Историческое значение
не становится новым current head; external authority не восстанавливается.

DES-06 recomputes только доступную и разрешённую derivation. Иначе он проверяет
допустимый retained result через sufficient bound evidence и показывает replay
limits. UI-04 workstream summary теперь подчиняет сохранение истории actual
retention/deletion, включая identifiers и existence metadata.

**Falsifier:** законный retained use проходит, raw-required/new unpermitted use
ограничивается. Removal dependency/rights qualification выявляет и false admission,
и blanket false refusal. Это уточнение consumer scopes, не новое право хранить
все derivatives после удаления родителя.

## R24-06. Проверенные bytes должны быть теми, которые consumer прочитал

**Пробел проверки:** cold-object verification уже требуется R23, но отсутствовал
различающий case подмены locator/version/chunk между verification и consumption.
P32 задаёт общее свойство; R24 добавляет конкретный native read witness.

**Решение:** OPS-05/CAP-03 используют существующий qualified immutable handle,
version pin/read lease или bounded verified stream. Если integrity устанавливается
только в конце stream, промежуточная обработка provisional; protected use ждёт
требуемой проверки. Chunk-level use требует соответствующего native contract.
Актуальные права/fences всё равно проверяются на protected use. По delta review
явно включены integrity-dependent external egress, publication и irreversible
effects: late-corrupt-final-chunk probe проверяет actual sink и отсутствие раннего
partial release. Provisional outputs остаются внутри existing rights/resource
bounds; removal release fence выявляется даже при последующем красном hash.

**Free-grow:** не нужны второй archive, double scan, global lock, universal Merkle
representation или full-object RAM copy. Уже принятое E02 свойство rebind/witness,
а не переписывается. Подмена actual consumed bytes при сохранённых hash/manifest
markers должна сорвать protected-use проверку; bounded read/buffer work измеряется
для выбранного profile, не объявляется по тексту документа.

## Отклонённые или ограниченные замечания

- Требование всегда разделять observation fence по selector labels отклонено.
  Такие labels не доказывают non-overlap, общие права или membership independence.
  R23 допускает supported scoped order; conservative source scope корректен при
  недоказанной независимости. Reviewer повторно проверил и снял substantive finding.
- Ни changed response, ни новый artifact сами по себе не новый independent study;
  исправлена формулировка, но scientific denominator остаётся native method property.
- Unresolved review/currentness и stale-poll history уже согласованы; нового
  polling owner, global current-head lock или повторной реализации не назначено.
- Нельзя замораживать unsafe permission ради service promise, принуждать каждый
  pure retry к human reconciliation, либо разрешать derivative по одному hash.
  Эти варианты root отдельно отверг при редактировании.

## Review, проверка и границы доставки

Первые независимые разрезы: `r24_reuse`, `r24_observation`, `r24_recovery`,
`r24_queue`, `r24_compat`, `r24_dag`, `r24_surfaces`, `r24_freegrow`.
Delta-only review после правок: reuse, queue и compatibility — bounded GO.
Reuse reviewer заметил отсутствующий в момент review report-link; companion
создан, ссылки проверяются отдельно. Recovery reviewer потребовал actual sink
probe для late-corrupt stream: добавлен release fence/negative/removal в тех же
owners, без нового subsystem. DAG reviewer подтвердил core duty join и указал
на optional suppliers, оставшиеся только в prose: они получили отдельные
conditional composition requirements. Root также конкретизировал P37 applicability
по enrolled relation, включая wrong-duty/omitted-relation negative. Это локальные
документарные поправки того же класса; весь план не объявляется runtime green.
После этих двух refinements recovery и DAG reviewers повторно дали GO по
изменённому delta; исходные замечания и границы review сохранены выше.

[Receipt](r24-validation.json) пересчитывает полный task/solution denominator,
start DAG, extension mirrors, 84 question routes, selected changed cards и
локальные inline Markdown links. Actual file/Git reads и limitations инструмента
сохраняются в ignored receipt, указанном по path/hash; это не runtime proof.
Ни исходные SDD, ни принятые пять proposals не изменяются. Product hooks не
запускаются из-за запрета тяжёлых/product процессов; hook configuration не меняется.

Pattern pass: P01/P02/P03/P04/P05/P07/P08/P09/P10/P13/P14/P27/P29/P31/P32/P35/
P37/P38/P40/P41. Классы — пропущенные native consumer bindings и различающие
проверки recovery, не новые sovereign subsystems. Capability execution остаётся
`verification_missing`/`semantic_test_missing` до будущей source-bound реализации;
там, где owner rebind обнаружит отсутствующий bridge, он получает `bridge_missing`.
Документация не объявляет, что эти звенья уже реализованы или приняты.

## Итоговое самостоятельное review root

Проверены не только acceptance, но и отдельные positive/rollback/migration и
consumer summaries: именно их расхождение породило OPS-04/DES-06 escapes.
Решения оставляют native выбор размера realization set, метода replay, допустимой
derivative representation, compatibility direction и точности source scope.
Они не требуют нового метода или формата ради регистрации нового provider.

Остались явные реальные границы: неизвестная independence не становится фактом;
неизвестный порядок наблюдений допускает conservative scope; недостаточный
retained basis не заменяется квитанцией; clock uncertainty не даёт timing SLA;
отсутствующий actual producer не заменяется согласованным интерфейсом. При этом
каждая граница ограничивает своё утверждение/use, не останавливает весь проект.

Машинный пересчёт сохранил 121 task и 368 start edges, все 84 question IDs/388
routes и пять согласованных SDD proposals. Изменены 12 task rows; три новых
условных требования LIF-02 относятся только к composition. Подробные множества,
файловые знаменатели, actual-read trace и ограничения — в receipt.

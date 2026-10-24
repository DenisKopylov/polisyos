# R22: редтим технических решений и их композиции

24 октября 2026. Проверенная база — `7bf96b19d437dba747cab8489f898c4a0dc41eaf`
(R21). Root и восемь прямых read-only reviewers; без дочерних агентов, product
imports, тестов, сборок, установок, production reads и реализации. Изменяется
только план. Actual E02 acceptance остаётся обязательным входом в исполнение.
Новые SDD не изменены и не приняты; `closure_ids=[]`, `product_verification=UNRUN`.

## Итог

Общий выбор механизмов выдержал проверку: native owners, раздельные scientific и
authority predicates, typed plurality, scoped generation fences и реальная
параллельность полезнее нового универсального движка. Найдены стыки, на которых
эта архитектура теряла свои свойства из-за неполной передачи контракта или
противоречащего критерия. Исправления внесены в существующие задачи, их решения,
composition requirements и semantic acceptance. Отдельных services, enums,
верхнеуровневых задач и whole-task start dependencies не добавлено.

Это целевой критический разбор содержания и согласованности, а не заявление о
доказанной оптимальности всех технологий, построчной независимой перепроверке
всего корпуса или готовности runtime. Новых внешних технологических фактов этот
раунд не утверждает: решающие источники — исходный R9, принятые решения и exact
контракты плана. Дополнительный web search не потребовался.

## Дефекты и окончательные решения

| ID | Проблема на R21 и источник | Исправление / граница / owner | Различающий будущий сигнал |
|---|---|---|---|
| R22-01 | CAP-04 допускает local observation journal, а LIF-02 требует source-native C/W replay; bounded fallback не задаёт однозначный consumer contract. [LIF](../solutions/02-custody.md#LIF-02), [CAP](../solutions/01-capture.md#CAP-04) | Отдельная evidence basis observation-cut: CAP-02 root, selector/profile/coverage, observation time, local journal identity/position. LIF-02 закрывает **локальный** enrollment race и ограничивает claim; источник не получает придуманную continuity/effective time. | Изменение до enrollment достигает fresh reader. A→B→A между polls, partial poll и потеря local replay floor не дают uninterrupted-current PASS. |
| R22-02 | CAP-02 не переносил точный controlled-proxy proof из [R9 acquisition § «Проверять фактического адресата»](../../../../research/universal-policy-design/external-foundations/acquisition/01-acquisition-routes.md#проверять-фактического-адресата-запроса). Socket peer прокси не доказывает конечный адрес. | Shared transport owner проверяет authenticated request-bound enforcement result: request/attempt, final target, policy/proxy, egress decision, redirect/credential scope. Только выбранный proxy route; private connector со своим явным разрешением сохраняется. | Allowed target проходит; forbidden metadata target через тот же proxy, чужой receipt или forwarding header — нет. Удаление проверки при сохранённых labels обнаруживается. |
| R22-03 | LIF-01 разделил assessment/use, но LIF-07 включал admission-only изменения в вычислительный key. Для reuse acceptance не был явно связан реальный supplier. [LIF-07](../solutions/03-lineage.md#LIF-07) | Role-qualified computational/semantic, current-use и retention dependencies у прежнего lineage owner. LIF-01 readiness → emitted LIF-07/accepted-native closure → actual LIF-01/CAP-03 reader → composition. Только выбранный cache claim; uncached route полезен отдельно. | Grant-generation rotation не повторяет unchanged lawful analytic verifier; revoke блокирует use; redaction/selection change требует пересчёта. Cache-off сохраняет смысл. |
| R22-04 | LIF-01 называл весь legal act/applicability `institutionally_supplied`, вопреки [S04-M1](../solutions/lifecycle-r19/S04.md) и P37. | Внешний акт — supplied evidence. Каждый required authenticity/competence/status/applicability predicate получает фактический basis; native qualified rule может recompute/reconcile scope. Неопределённая интерпретация/компетенция остаётся limited. | Qualified source + все необходимые predicate checks допускают scoped use без нового внешнего заключения на каждый вызов. Убрать evaluator, оставить official markers — отказ. |
| R22-05 | OPS-08 позволял снять reservation после terminal attempt, хотя R21 требовал считать живые shared allocations. [OPS-08](../solutions/10-operations.md#OPS-08) | LIF-06 accounting и OPS-08 physical reconciliation следуют lifetime ресурса. Shared allocation сохраняет одного живого owner; transfer/release idempotent. Допустим conservative enforced envelope — без per-object tracing как общей обязанности. | Terminal attempt оставил60/100, следующий просит50/100: нельзя принять без actual headroom. Duplicate release не создаёт capacity; реально освобождённый private ресурс доступен. |
| R22-06 | Queue age наблюдался, но starvation не обязан был завершаться disposition; исходный [R9 resource §6](../../../../research/universal-policy-design/external-foundations/lifecycle/09-resource-execution-design.md#6-рабочий-режим-перегрузка-и-recovery) требует policy/aging/expiry. | LIF-04 due selector применяет versioned profile policy; LIF-06 eligibility, OPS-08 measurements. Service opportunity либо bounded terminal/review outcome; no universal DRF/deadline. Custody/revocation duty не исчезает по TTL. | Непрерывный class A не оставляет старый class B в silent perpetual defer. Retry не обнуляет возраст. Expiry/refusal не выдаётся за execution. |
| R22-07 | UI-02/04 и LIF-05 rollback всё ещё требовали безусловно хранить signed bytes/lineage/public interval, хотя R21 допускает законное удаление идентифицирующих оснований. | UI/history/export/restore потребляют actual LIF-05 placement/metadata outcome. Только permitted history неизменна; lawful erasure не переписывает прошлое и не доказывает reversal. Receipt/existence disclosure сохраняются только если разрешены. | Раздельные retention и erasure positives; forbidden canary не достигает selected managed readers. Ни unsupported caller request, ни generic history slogan не обходят owner. Внешний recall не обещан. |
| R22-08 | Recovery checkpoint явно связывал rights watermark, но не material Claim/public histories и witness вне rollback closure. Исходный [R9 E06](../../../../research/universal-policy-design/external-foundations/lifecycle/10-adversarial-review-and-delivery.md) требует оба. | OPS-05 связывает journal cuts/floors, head mapping и continuity witness вне **actual selected rollback closure**; LIF-02/publisher reconciles и fences enablement. Нет обязательного нового service. Утрата lawful evidence оставляет affected restore limited/quarantined. | Backup S0 + subsequent withdrawal/reissue восстанавливается с правильным fresh head. Rollback обоих journals, missing/deleted witness или withdrawal при switch не проходят rights/hash-only gate. |
| R22-09 | [R15 assurance](09-adaptive-research-and-method-quality.md) запрещал любую posterior/world mutation без WP, хотя R20 разделил effect и structure. | DES-12 assurance и task/solution probe сохраняют separate actual structural-write rule через единственного GYD-12 writer. WP остаётся обязательным для соответствующего effect-posterior/assimilation route. | Structural positive с applicable rule без WP; убрать rule — candidate. Отдельный O1 positive без требуемой activation запрещён. Ни один receipt не заменяет другой. |

R22-01/03/05/07/09 — продолжения уже известных классов на consumer/acceptance
границе; повторные escapes исправлены общим invariant и обязательными companions,
а не новыми per-instance services. R22-02/06/08 возвращают точные исходные
обязательства, потерянные в конспекте задачи. R22-04 устраняет противоречивую
классификацию. Ни один пункт не доказывает текущий runtime defect.

## Независимые разрезы и повторное review

| Reviewer | Прочитанный разрез / первичный результат | Финальный результат delta |
|---|---|---|
| `r22_acquisition` | CAP/CNT capture, proxy, no-feed→LIF; R22-01/02 | Bounded GO: local order не превращается в external continuity; private-source positive сохранён |
| `r22_resources` | Qualification, shared allocation, fairness, host envelope; R22-05/06 | Bounded GO: lifetime сохранён, expiry не выдаётся за service, custody не теряется |
| `r22_reuse` | Assessment, lineage, current use, P37; R22-03/04 | Bounded GO: current fence/retention остаются, role distinction не даёт stale authority |
| `r22_dag` | Stage/acceptance dependencies и leases; supplier часть R22-03 | Bounded GO: conditional composition joins не образуют whole-task start cycle |
| `r22_freegrow` | GYD-32, S15, native owner/config classes | На R21 substantive finding нет; non-exhaustive extension rationale и per-config conformance сохранены |
| `r22_science` | Productive search, studies, heterogeneous methods, structural learning; R22-09 | Bounded GO: scientific qualification и write authority не смешаны; нового разрешения нет |
| `r22_surfaces` | Useful publication/history/revision/access flow; R22-07 | Повторное review обнаружило старые acceptance формулировки; после синхронизации bounded GO |
| `r22_retention` | Retention/restore/no-store/custody; R22-08 и sibling R22-07 | Повторное review обнаружило `never erase`/unconditional lineage; после class-level correction bounded GO |

Reviewers не редактировали tracked source и не запускали product checks. Root
перечитал решающие исходные положения, сопоставил counterexamples, внёс изменения
и отдельно проверил каждую группу решений. Minor suggestion о competence-specific
removal не создаёт нового blocker: actual required-predicate coverage уже общий
контракт; при отдельном evaluator он входит в выбранный native discriminator set.

## Собственные атаки на окончательный проект

- **Ложная актуальность:** observation-cut закрывает только наши observed events;
  для scientific/current/legal утверждения всё ещё нужны его собственные grounds.
- **Permission churn как вычислительный DoS:** admission-only изменение не вызывает
  полный scientific replay, но role-changing selection/redaction и unavailable
  closure не получают cache hit. Deleted result нельзя сохранить ради ускорения.
- **Дешёвый accounting proxy:** terminal receipt/owner transfer не освобождают RAM.
  Aggregate enforced envelope допустим; детализация ledger не стала самоцелью.
- **Фиктивная fairness:** выбранная policy не обещает успех под любой нагрузкой.
  Она даёт service либо честный bounded outcome; durable custody не отменяется.
- **История против privacy:** нужен actual qualified retention/deletion decision.
  При запрете даже identifying receipt не сохраняется; правдивость истории не
  доказывается реконструкцией запрещённого содержимого.
- **Восстановление всего вместе с ложным witness:** независимость определяется
  actual rollback closure, а не числом копий. Необязательно удалённое облако; нужен
  подходящий переживший closure trusted anchor либо честный recovery limitation.
- **Один правило-владелец как глобальный stop:** joins остаются выбранными
  effect/composition predicates; base contract/readiness и независимые scopes
  могут продвигаться. Оба научных маршрута сохраняют реальные обязательства.

## Проверка и передача

[Полный документарный receipt](r22-validation.json) пересчитывает полный набор
tasks/solutions, extension mirrors, question routes, прямой DAG и stage delta;
проверяет изменённые human cards, JSON и локальные Markdown targets. Это лёгкие
stdlib/text проверки, не тестирование PolicyOS. Полные старые reviews и receipts
сохраняют свою исходную source qualification.

Реализация по-прежнему начинается после actual E02 acceptance и P0 rebind. Все
новые positive/adversarial/removal cases — задания будущему исполнителю. Новых
политических, правовых, научных или институциональных полномочий этот документ
не создаёт. Общие retain-history формулировки читаются по [S17](../solutions/00-shared-decisions.md#s17-r22-границы-фактов-lifetime-и-сквозной-приёмки),
а конкретные conditional joins — по [scoped readiness](../execution/07-scoped-readiness.md#r22-explicit-composition-joins-without-start-cycles).

Pattern pass: P01/P02/P03/P04/P05/P07/P08/P09/P10/P13/P14/P27/P29/P31/P32/P35/P37/P38/P40.

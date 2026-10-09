# Исполнение связанной очереди

TASKS сохраняет все 23 исходных task IDs и их finding routes; BOOT0, DX0 и DEC0 добавляют admission, tooling и decision work. Все 282 исходных IDs имеют маршрут. Зависимости — prerequisites конкретного exit signal, а не запрет заранее исследовать source, готовить fixtures, reviewers или consumers.

Завершение task не меняет findings автоматически. Для **каждого** назначенного ID и каждого canonical occurrence нужен отдельный результат: проверенное исходное свойство, bounded limitation, доказанная unavailable input/G decision либо open action с выполненными попытками и точным следующим check. В частности, общий Q0 не заменяет UKOPS/Linux outcome LA-029; Q1 source selection — compatibility/legacy outcome LA-021; три решения S1 — остальных LA-023/LA-032/LA-036; R1 contours — inputs B61/B148; generic T2 positive — issuer/currentness LA-018/LA-025/B131/B137/B164. Дублированные source occurrences сохраняются как исходные bindings, не объявляются уникальными диапазонами.

## Начальный запуск

BOOT0: прочитать root AGENTS, CONTRIBUTING, HANDOFF, failure/repair register, новый INPUTS/TASKS и исходную connected-plan/findings/closure coverage. Запустить `results/import_results.py --check` и прочитать `results/verification.json`; transferred text — navigation, не raw runtime receipt. Сверить attached branch, HEAD/tree/status, Git transport и лёгкий `df`. Отдельно записать точный entry base до собственных изменений.

Использовать один длительно живущий собственный candidate checkout, стартующий от опубликованного G. Не использовать G checkout для авторства. Reuse подходящей собственной attached lane предпочтительнее; при её отсутствии создать одну изоляцию и ветку `codex/e02-unified-local-20261009`. Не reset-ить существующее незнакомое состояние и не создавать новый checkout на каждую волну. Сохранить поздние incoming refs и непубликованные изменения; выяснить активных writers по конкретным paths.

Проверить ordinary retrieval missing ORCH03 bytes один раз через реально доступный канал. Если bytes недоступны, зафиксировать границу и перейти к новой минимальной реализации на текущем source. Старый путь `/workspace/...` не является доставкой. Prepared B exact objects доступны: взять защищённые refs/точный fetch из INPUTS; PR55 не объявлять содержащим подготовленную дельту.

## Полезные параллельные потоки

| Поток | Начать сейчас | Зависимый этап | Ресурс, который сериализуется |
|---|---|---|---|
| Source/CAS | Q1, independent CAN/Core options/profile analysis, I2 оставшиеся CLI companions | R1 exact B composition; R2 physical cleanup | Один canonical writer Core/IR DTO и общий schema/generator |
| Data/profile | I1 C05 current-G composition | I4 C12 Legal/Catalog request→encoder→reader | Material-basis owner, shared DB/fixtures и facade writer |
| Runtime/served | V1 DTO/intake/CAS/GET preparation; V2 actual N4 producer research | V1/V2 positives после выбранных profile/source inputs; V6 persisted simulation sibling-failure | Generation-cycle/HTTP writer, fixed server ports, governance artifacts |
| Numerical/economics | R3/R4 controls, V5 receiver/profile investigation, S1 отдельные semantic decisions | GP joined Search; S2 method-specific law intake; V7/V4 fresh empirical consumer | Один тяжёлый Mac slot; один numerical thread сначала; shared CAS isolated |
| Custody/authority | T1 source/ref/context inventory, минимальные L1/L2 joins | T2 protected positive/commit-time refusal; S3 subject join | Read-only production handles и подписанные authority inputs |
| DevX/verification | DX0 Ruff caller basis, archive input custody, scoped format; Q0 independent whole-property crosswalk | Q2 canonical generated+installed consumers; final replay | Lockfiles/tool manifests/generated family, packaging scratch |

Начать с 6–8 независимых исполнителей/исследователей и отдельных reviewers; расширять до 20 прямых помощников при наличии конкретной непересекающейся очереди и ресурсов. Это не квота авторов. Никто из помощников не создаёт детей. Root отвечает за source selection и один writer на файл с обязательными companions. Не поручать параллельно менять одни и те же facades, generation_cycle, run_lifecycle, streaming, schema/lockfile или generated family. Test/oracle author получает отдельный path либо отдаёт patch canonical writer.

Лёгкие tests/lint/typecheck, read-only analysis и авторство независимых модулей идут параллельно. Сериализуется contended DB/port/file или тяжёлая локальная нагрузка. Установка необходимых поддерживаемых зависимостей и создание isolated profiles разрешены; использовать existing lock/recipes/cache/offline там, где это возможно. Отсутствующий пакет в сегодняшней G venv не является постоянным blocker. Для Linux-only worker использовать поддерживаемый локальный контейнер/VM с portable fixtures; production остаётся локально read-only. Не отключать platform guards для имитации Linux на Mac.

## Что не следует исполнять повторно

Не переносить целиком C05/C12/B старые широкие ветки. Выбрать пути и existing contracts, сохранить все нужные facade/tests/config/resource companions. CAN/C10/C11/исправленный DFK уже в базе: прежний unchanged source review используется в своей границе; новый consumer/delta/dependency получает новую проверку. Q0 проверяет исходное свойство, а не переписывает все proposed-closed механизмы.

V4 и V7 используют общую empirical producer/consumer семью: один writer, два разных criteria/receipts. V1 и V2 разделяют runtime bridge; root последовательно применяет их source deltas, пока независимые investigators готовят profile, N4 и semantic controls. Q2 можно готовить заранее, но итоговую canonical regeneration выполнять после выбора upstream DTO/contracts.

## Протокол перед любым остаточным blocker

1. Воспроизвести точную boundary на candidate с полной командой, средой, input identity и output. Различить product FAIL, setup ERROR, capture incomplete, SKIP и UNRUN. Причину signal9/137 не угадывать.
2. Проверить source DAG, существующие callable APIs, resource locators и supported environment recipes. Уточнить, нужен ли реальный внешний факт или достаточно собственного configured witness исходного свойства.
3. Проверить минимальный discriminating input: отсутствие против malformed/present-but-fake; реальный producer против вручную заполненного DTO; source mutation против ID/mtime-only; typed limitation против authority. Не заменять scientific law checksum или fixture label.
4. Исправить внутренний механизм и его necessary companions самостоятельно, если смысл следует из действующего контракта. Не запрашивать старую A/C/F-группу лишь потому, что её буква стоит в locator.
5. При неоднозначности провести reuse-first исследование и дать G конкретные варианты из DECISIONS, с prototype/falsifier и рекомендацией. До ответа продолжать независимые ready задачи. Не встраивать неподтверждённую product law в контракт.
6. Только после этих попыток оставить узкий остаток: affected criterion/claim, missing typed label, источник факта/решения, что проверено, почему инженерное решение не даёт этого факта, минимальный input, следующие runnable actions. Один unknown не удерживает всю очередь.

## Freeze и завершающее доказательство

На каждом чистом boundary — implementation commit, затем отдельный handoff commit, обычный topic push и remote readback. Source acceptance и formal findings принадлежат G; автор в handoff пишет proposals, scope и deciding outputs. Late G checkpoint принимать ordinary merge после проверки delta; не rebase/reset.

До expensive wave завершить независимые source reviews и batched blocking fixes. Установить explicit candidate/source/input/backend freeze, именованный root выбранного serving instance и полный supported profile denominator. Затем один общий дорогой composed replay, один требуемый read-only production-dependent closeout, installed wheel + rebuilt-sdist/архив consumers и обязательные repo gates. После изменения upstream contract повторять affected checks; broad replay повторять лишь когда новый blocking delta инвалидировал freeze, а не по числу утративших актуальность summaries.

Retain full deciding stdout/stderr, removals, environment/input/source identities и независимые conclusions. Ссылаться на tracked source как `path@sha`; не копировать source snapshots или многократные derived inventories. Крупные raw — ignored рядом с hash/locator. Unknown P41 attribution остаётся `not_established` до exact slice-base replay и доказательства zero intersection с полным gate denominator. Успех активного docs hook не означает, что native Python SOTA/quality chain выполнялась.

Завершить авторскую работу можно после исполнения всей ready очереди и source freeze/replay, когда каждый остаток либо исправлен и проверен, либо имеет доказанный внешний input/G decision и выполненное исследование. Это ещё не G formal closeout. Финальный report сохраняет 282 IDs/291 occurrences, historical decisions, proposals, accepted source checkpoints, FAIL/ERROR/SKIP/UNRUN, external facts и точные remaining actions; counts разных прогонов не суммировать.

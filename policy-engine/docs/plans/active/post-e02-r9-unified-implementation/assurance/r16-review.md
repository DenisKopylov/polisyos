# R16: исследование, независимые атаки и самостоятельное review

23 октября 2026. Source pin `4633fc44df0aedeb3f9989b7a68036349cca2969`. **Документарное решение для будущей реализации**, не code acceptance, runtime PASS или closure. Все product checks UNRUN; E02 должен быть фактически принят до реализации. SDD не изменяются.

## Происхождение

Шесть прямых read-only исследователей: `r16_incremental` (native influence/epoch/currentness), `r16_cycles` (compiler/coupling/clock), `r16_epistemics` (causal/scientific semantics), `r16_reactive_systems` (events/replay/resources), `r16_freegrow` (owners/task decomposition), `r16_numerics` (solvers/error/stochastic/cost). Ни один не создавал детей и не запускал product tests, imports, builds, installation или production scans.

Три новых независимых reviewers читали созданный R16 пакет: `r16_red_semantics_v2`, `r16_red_dispatch_v2`, `r16_red_execution_v2`. Авторы исследовательских предложений не назначались reviewer собственного текста. Root составляет итоговую документацию, проверяет source anchors и принимает решения по атакам. Счёт agents описывает организацию работы, не strength of scientific evidence.

Primary источники и точные ограничения переноса перечислены в [research dossier](../research/composition-reexecution-r16.md). Root отдельно проверил actual whole-plan feedback invocation, final graph path, semantic epochs, runtime cache и selected compiler/checkpoint seams. Это inspected selection, не полный source census; никакой runtime FAIL из static риска не выводился.

## Findings и исправления

| Review / класс | Конкретный escape | Решение и consumer проверки |
|---|---|---|
| Scientific / P01–P02 coverage | Новые Q cases есть у freeze/replay, но FINAL-REVIEW мог пропустить их | FINAL-REVIEW получает обязательный r16_extension и C8 coverage; task/solution зеркальны; independent selected-Q review до существующей final wave. Delta reviewer подтвердил исправление |
| Scientific / P14 | «Независимый второй Bernoulli success» допускает путаницу marginal и conditional independence | Q10 прямо связывает θ, sampling/selection и conditional independence. Posterior arithmetic не новый empirical receipt. Delta reviewer подтвердил |
| Scientific / P27 free-grow | Запрет любой allowlist мог запретить корректную security registration нового semantic adapter | Q15 запрещает per-family hard-coded dispatch, разрешает owner-reviewed declarative registration/security admission. New semantic class всё ещё требует adapter/conformance. Delta reviewer подтвердил |
| Dispatch / P02–P38 stage mismatch | Таблица разрешала параллельную CAP-04 подготовку, machine edge ожидал полного LIF-02 readiness | Existing CAP-04/LIF-02 edge становится interface_agreement; real enrolled replay/currentness остаётся actual selected composition supplier. Остальные prerequisites и UI-19 acceptance сохранены. Delta reviewer подтвердил |
| Execution / P31–P40 purity scope | Нарисованный SCC меньше actual callback closure: existing feedback вызывает весь ExecPlan и может повторять внешний one-shot node | C1 связывает native subplan: frozen upstream → admitted map block/final residual → downstream. Whole-plan fallback должен доказать repeatability/ресурсную допустимость **всех реально вызванных** members, иначе limitation/refusal. Q04 добавляет outside-SCC effect discriminator; GYD-30/LIF-06 machine criteria расширены |
| Execution / P38 stochastic proxy | Zero sampled residual плюс noise_sd ошибочно проходят expected equilibrium | Q14 задаёт явный Tω(x)=x+δ+ξ с mean-zero noise и no fixed point у expected map. Expected profile требует validated stochastic rule/достаточное evidence либо limitation; fixed-path result имеет другую границу. Machine DES-11 и C2 уточнены |
| Execution / P37 requiredness | Adapter объявляет обязательную facet optional и тем самым сам сужает собственный admission denominator | Native verifier выводит requiredness из resolved/content-bound versioned producer/consumer/selected-guarantee contracts. Missing/conflicting contract не пустое множество. C1/Q15/GYD-30/GYD-32 содержат generic discriminator, не список сегодняшних полей |
| Root / P35 companion drift | Старый dependency-levels.json оставался на 119 tasks после R15 | Полная projection пересчитана из 121 task/368 stage-qualified preparation edges. Это не runnable width, speedup или union с acceptance joins |
| Root / P08 retention | «Historical result всегда readable» мог обещать хранение запрещённых bytes | История сохраняется в разрешённой проекции; при lawful deletion/restricted access exact replay может быть unavailable. Architecture, Q05 и DES-11/mirror согласованы |
| Root / native anchors | Shared GYD-30 write scope и graph path не полностью совпадали с actual native layout | Scoped r16_owner_alignment и conflict anchors включают настоящие compile/execute/_internal/graph/chain/schema paths. Это rebind candidates, не blanket ownership |

Все атаки bucketed как уточнение существующих классов, а не повод для новой лестницы per-fixture repair. Не требуется создавать ещё один scheduler, universal evidence graph или authority subsystem. Все три reviewers завершили delta-only проверку принятых исправлений: scientific/dispatch gaps закрыты в документации, execution reviewer дал bounded GO без оставшегося blocker в проверенных классах. Отказ от тяжёлых проверок не назван runtime PASS.

## Самостоятельное содержательное решение root

Root перечитал восемь delivery slices, все 28 additive task objects и зеркальные решения, 17 quality groups и stage dependencies. Приняты следующие границы:

1. **Одна композиция — несколько meanings.** Execution graph, computational influence, scientific justification и current-use authority связаны, но имеют собственных owners. Numerical cycle не causal certificate.
2. **Repeatability по actual вызовам.** SCC extraction должна реально менять map boundary либо признать whole-plan repeat scope; hidden outside-block effects входят в admission/cost. Pure function не обязана иметь checkpoint; stateful member не объявляется pure по интерфейсу.
3. **Correct fallback раньше оптимизации.** Unknown read-set/unsupported delta update не превращаются в empty dependencies. Bounded clean recompute/refit остаётся корректным; exact selective reuse получает независимый fresh comparator. Negative/membership/dynamic dependencies обязательны по actual чтению.
4. **Immediate custody, bounded compute.** Currentness реакция не ждёт solver. Actual duty ведёт к durable intent и реальным trials; без duty — honest next action. Отдельные branches и resource phases не блокируются общим completion lock.
5. **Научное обновление сохраняет target и dependence.** Observation, intervention, mechanism и scenario различны. Conditional likelihood, retraction/refit и as-known-then history не заменяются числами provenance. Candidate discovery и operative activation остаются разными paths.
6. **Честная численная гарантия.** Residual не solution error; fixed sample path не expected equilibrium; convergence не global optimum, model adequacy или societal preference. Exact/approximate/statistical guarantee определяет её собственный oracle.
7. **Free-grow без скрытых defaults.** Owner-native requiredness и real registry/bootstrap → consumer допускают conforming extensions. Выбор FMI/HELICS/BMI и других protocols — по предъявленной property, не обязательная migration.
8. **Полная полезная capability.** Q17 требует meaningful real design/research update и fresh projection. All-refusal/marker-only suite не проходит; внешняя authority/empirical validity требует настоящих inputs.

Original task, solution, inventory и R15 требования сохранены. Из existing fields меняются только явно названные stage relationships; additions не означают новые finding closures. [Machine validation](r16-validation.json) фиксирует полный denominator и виды документарных проверок. Mandatory companions вынесены за любой mechanism path cap.

## Границы завершения

Документы могут обосновать архитектурный выбор и определить future acceptance, но не establish native implementation или production readiness. Невыполнены: actual graph/solver/reexecution tests, source-level integration, benchmarks, installed/public consumers, fresh deployment и authentic scientific/custody inputs. Они остаются в своих task obligations и existing final wave.

Unconditional application hooks contrast/reduced-motion/typecheck не запускаются для этой docs-only поставки по ограничению пользователя на вычислительные процессы. Exclusion действует только на эту операцию, конфигурация hooks не меняется; omitted hooks — UNRUN. Проверки JSON/ссылок/diff и source-anchor existence лёгкие, без product imports.

Pattern pass: P01/P02/P04/P05/P07/P08/P10/P13/P14/P15/P27/P29/P31/P32/P35/P37/P38/P39/P40/P41. Принятие документации не является выполнением её runtime criteria.

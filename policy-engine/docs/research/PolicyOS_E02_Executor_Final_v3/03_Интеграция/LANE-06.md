# LANE-06: общий интеграционный контракт

**Цель:** Продолжение, отмена и хранение не меняют смысл расчёта, не теряют полезные результаты и не дают старой попытке повторно применять действие.

Состояние проверок: **NOT_RUN**. Это обязательные критерии будущей связанной приёмки, а не свидетельство текущего PASS. Семейство запускается один раз для согласованного изменения; локальные packet tests не дублируют его инфраструктуру.

## Область и зависимости

Пакеты: STA-01, STA-02, EXE-01, EXE-02, RES-01, RES-02, RES-03, RUN-01, RUN-02, RUN-03, DUR-01, DUR-02, WIRE-01, CAS-01, CAS-02, CAS-03, REP-01, CAN-01, MIG-01, MIG-02, MIG-04, MIG-05

- Общие infrastructure witnesses переиспользуются всеми lanes по content/backend-qualified binding, не копируются 12 раз.
- RES-03 consumes CYC-02/CMP-01; не превращать весь LANE-06 в обязательного предшественника первого useful run.

## Профиль и допустимые подмены

- **P-CORE:** policy-engine Python >=3.14,<3.15; actual project lock/extras, supported existing environment; imports bind tested checkout/artifact (основание: policy-engine/pyproject.toml:8)
- **P-PROCESS:** P-CORE with real OS process/pipe and isolated tmp DB/CAS; platform-specific controls named; no production stores (основание: original sourceplan §§6–7; existing process test owners)

- Только отдельные tmp CAS/DB, controlled clock/barriers/fault injection и own child processes.
- Нельзя подменить owner ledger, transactional fence или свежий reader памяти-фейком в принимаемой persistence/authority части.
- Store I/O задержка допустима для scheduling test, но отдельный persistence witness использует реальный backend.

Подмена запрещена для принимаемого свойства: если проверяется запись/чтение, actual store и fresh reader обязательны; если численный метод — actual backend; если physical cleanup — actual OS resource. Внешний provider/encoder может быть лёгким и контролируемым, когда качество модели/сети не входит в claim.

## Подготовка и порядок

1. На выбранном поддерживаемом профиле связать checkout/build SHA и входные fixtures. Использовать существующие test owners ниже, прочитать их реальные seams перед расширением
2. Выполнить локальные REQ/TEST затронутых пакетов, затем каждый применимый вариант этого семейства. Независимые варианты допускают раздельный запуск
3. Положительный прогон должен пройти actual producer→передача/хранение→fresh consumer. При отсутствии хранения в конкретном алгоритме проверить непосредственный downstream consumer, не придумывая CAS ради отчётности
4. Повторить адресный негативный/граничный контроль. Изменение одного deciding input или отключение исправленного механизма должно менять наблюдаемый исход; unrelated пригодный результат остаётся доступным
5. Сохранить входы, события/значения/ошибки, ref identities, численные tolerances и команды. Итог связывает покрытые REQ, а не только список пакетных имён

## E02-I06-A — State → cold/warm → partial workflow

Покрываемая область: STA-01, STA-02, EXE-01, EXE-02

**Положительный oracle:** Независимое поле и declared subtree сохраняются; same-value intent не теряется. A→C начинает после committed A без ожидания независимого B; read разрешён без нового compute. Parameter-prior bridge parity проверяет wiring; независимый Normal prior fixture mean2,std0.6 при value2,std_error0.2,multiplier3 и confidence_interval absent отдельно проверяет арифметику до actual consumer. Все три actual await routes shared Future используют общий private nonblocking adapter; watchdog находится вне проверяемого loop.

**Различающий негативный oracle:** Whole-root set не снимает protected guard; changed source/seed/draw count не получает старый reuse. Late callback не блокирует event loop; aliased list-index не обходят conflict analysis. Blocking callback/retry await, cancellation/late close и job-slot ownership проверяются на actual route; cancelled waiter не освобождает занятую физическим job capacity. Переиспользование producer conversion как единственного expected prior запрещено.

**Приёмка:** предъявить оба исхода на одной объявленной модели/профиле с изменением только deciding условия. Точные локальные counterexamples и expected values берутся из связанных TEST соответствующих пакетов; совпадение summary без фактического потребления не принимается. Если метод стохастический, заранее указать seed/replica/ошибку сравнения, не подбирать tolerance после результата.

## E02-I06-B — Checkpoint → fresh reader → exact resume

Покрываемая область: RES-01, RES-02, RES-03, REP-01

**Положительный oracle:** A→B→C с двумя остановками достигает того же result/refs; skip не входит successful frontier; partial сохраняет successful siblings/error и useful numerical output.

**Различающий негативный oracle:** Остановка между публикациями не создаёт half-tier; changed request не совпадает по одним FQN. Старые refs не применяются/не списываются дважды, повреждённая запись не становится valid continuation.

**Приёмка:** предъявить оба исхода на одной объявленной модели/профиле с изменением только deciding условия. Точные локальные counterexamples и expected values берутся из связанных TEST соответствующих пакетов; совпадение summary без фактического потребления не принимается. Если метод стохастический, заранее указать seed/replica/ошибку сравнения, не подбирать tolerance после результата.

## E02-I06-C — Deadline/retry/process transport → durable fencing

Покрываемая область: RUN-01, RUN-02, RUN-03, DUR-01, DUR-02, WIRE-01

**Положительный oracle:** Decimal/bytes/typed outcomes проходят настоящий codec/process pipe; retry стартует с чистого baseline и сохраняет прошлые costs. Current lease выполняет разрешённую запись один раз. RUN-02 дополнительно квалифицирует объявленный OS/start-method profile после завершённого native JAX вычисления в parent: actual child numerical value, cleanup и typed result/termination; Linux fork и Darwin spawn не смешиваются.

**Различающий негативный oracle:** Cancel/EOF/timeout диагностически различаются; late old worker после expiry/takeover не пишет через sibling inlet. Heartbeat unavailable не останавливает unrelated class; rollback сохраняет transaction/event/outbox целостность. Missing/hanging supported profile фиксируется адресно NOT_QUALIFIED/BLOCKED, без предположения неизбежного deadlock и без глобальной замены start method; EOF repair принимается независимо от непроверенных платформ.

**Приёмка:** предъявить оба исхода на одной объявленной модели/профиле с изменением только deciding условия. Точные локальные counterexamples и expected values берутся из связанных TEST соответствующих пакетов; совпадение summary без фактического потребления не принимается. Если метод стохастический, заранее указать seed/replica/ошибку сравнения, не подбирать tolerance после результата.

## E02-I06-D — CAS generation A/B → signature → fresh reader

Покрываемая область: CAS-01, CAS-02, CAS-03

**Положительный oracle:** Correct bytes и exact inventory доступны после publication; failed B сохраняет A; chosen manifest/profile и реальный verifier согласованы. Batch сохраняет independent valid/rejected/not-run результаты.

**Различающий негативный oracle:** Wrong bytes/size/tenant/revoked key/foreign inventory отклоняются; late foreign file не удаляется cleanup. Cancel census не переименовывается в complete; absent signature не превращается по удобству в valid/invalid.

**Приёмка:** предъявить оба исхода на одной объявленной модели/профиле с изменением только deciding условия. Точные локальные counterexamples и expected values берутся из связанных TEST соответствующих пакетов; совпадение summary без фактического потребления не принимается. Если метод стохастический, заранее указать seed/replica/ошибку сравнения, не подбирать tolerance после результата.

## E02-I06-E — Canon/migration → historical and current consumers

Покрываемая область: CAN-01, MIG-01, MIG-02, MIG-04, MIG-05

**Положительный oracle:** Версии/профили Core/IR сохраняют заявленные semantics; migration no-op валидирует actual DTO, writer→manifest→reader читает те же bytes по declared roots. Migration registration descriptor означает identity зафиксированного registration snapshot, не доказанную идентичность произвольного mutable callable во все моменты; post-registration captured config mutation проверяется явно.

**Различающий негативный oracle:** No basename fallback/path escape; unsupported closure identity не молча склеивается. Historical bytes читаются как прежний профиль, не переписываются ради нового hash; одинаковый текст не доказывает равенство policies. Observer closures не замораживаются и не rehash на каждом вызове ради ложной purity. Reproducible converter требует явного stable config/version contract; иная динамика получает ограниченный nonreproducible scope.

**Приёмка:** предъявить оба исхода на одной объявленной модели/профиле с изменением только deciding условия. Точные локальные counterexamples и expected values берутся из связанных TEST соответствующих пакетов; совпадение summary без фактического потребления не принимается. Если метод стохастический, заранее указать seed/replica/ошибку сравнения, не подбирать tolerance после результата.

## Существующие места расширения tests

Список означает проверенные пути, не доказательство полноты или запуска всего содержимого. Новые проверки добавлять к ближайшему владельцу; отдельный harness создавать только при реальном разрыве.

- [policy-engine/tests/unit/scientist/orchestration/engine/test_state_merge.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/scientist/orchestration/engine/test_state_merge.py) — SHA256 `44597a58ee34d703db68f189d03b6e7a99a5d7bbe7a9352ac8876241537e1648`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.
- [policy-engine/tests/unit/remediation/test_res_02.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_res_02.py) — SHA256 `8d551b56b147c2e817b018626ea28a83c076c3f6684508a0935f5d522d6765a7`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.
- [policy-engine/tests/unit/remediation/test_dur_02_process.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_dur_02_process.py) — SHA256 `35f48eb3182363408dbb02e4c57b4cdb01b37b6f6df4391f3753bdf975426b48`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.
- [policy-engine/tests/unit/scientist/orchestration/engine/runner/test_timeout_transport_attempt_binding.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/scientist/orchestration/engine/runner/test_timeout_transport_attempt_binding.py) — SHA256 `cd472c2756f3064e83fabd19feadcb2a94ffa04e43459cd1f513b2ea429014c5`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.
- [policy-engine/tests/unit/remediation/test_cas_02.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_cas_02.py) — SHA256 `e93cc5988daa523bc75c7080c33c9d7370427d524262c413d26f5f2f0f045eea`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.
- [policy-engine/tests/contract/test_trinity_migration.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/contract/test_trinity_migration.py) — SHA256 `b0dc58bef19edb11c46170e9070967388ea043e8d6819af166b355f6ac89aa0b`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.
- [policy-engine/tests/unit/runtime/test_runtime_manifest_paths.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/runtime/test_runtime_manifest_paths.py) — SHA256 `29276dd62752d47ff7c1838ec8b1a2e8d658c760a693b51d5d24cb73fe5596c2`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.

## Выход приёмки

- Один manifest исполнения семейства: base/head SHA, scenario-ID, связанные REQ/TEST, профиль, входы и их hash, actual commands/exit, фактические positive/negative oracles, ограничения
- Перечень doubles с объяснением, какое свойство ими не проверяется
- Для failure/unknown: точная стадия и сохранённый полезный результат. Не перекрашивать BLOCKED/UNRUN в PASS
- Ремонт механизма и предметная валидность имеют разные решения. Синтетический механизм может пройти, не подтверждая прогноз/каузальную идентификацию/мандат реального кейса

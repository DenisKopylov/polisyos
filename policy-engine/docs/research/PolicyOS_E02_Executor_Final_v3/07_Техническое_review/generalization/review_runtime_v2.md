# Независимый readback runtime/delivery revisions v2

**Дата:** 2026-11-01. **Решение:** пять пересмотренных карточек пригодны для включения в предложенную v2 в принятом ограниченном scope. **Открытых новых блокирующих замечаний нет.** Это acceptance текста спецификации, не реализации: product/native tests остаются **NOT_RUN**.

Проверены `EXE-01`, `STA-02`, `RUN-02`, `MIG-05`, `CLI-01` — полный revised MD, соответствующий JSON, фактический baseline→v2 diff, `runtime_delivery/findings.json` RD-01–06 и `runtime_delivery/proposed_changes.json`. Уникальные JSON metadata прочитаны; все requirement/setup/action/oracle поля независимо сопоставлены с полностью прочитанным MD. Усечённые фрагменты вывода восстановлены. Выборочно прочитаны реальные владельцы; exact ranges/hashes находятся в `review_runtime_v2.json`. Raw actual diff сохранён отдельно: `runtime_v2_actual_diff.txt`.

## 1. Результат по каждому принятому finding

### RD-01 → EXE-01: общий неблокирующий completion bridge — ACCEPT

Изменены REQ-EXE-01-01, техническое решение, owners и TEST-EXE-01-01. Теперь охвачены три реальные sibling routes: `run_blocking_async`, `SharedExecutionHandle.result_async`, `retry._execute_with_timeout_thread_async`. Один private transport-only adapter остаётся у Common; обычные callbacks не становятся unbounded inline callbacks. Требования cancellation/shutdown/closed-loop, physical slot until underlying completion и timely receipt сохранены.

Независимое source чтение подтверждает причину: `common/async_tools/__init__.py:223–242` направляет late callback в `run_callback_sync`; `:301–351` допускает синхронное ожидание capacity/result; `:141–155` и `:951–952`, а также `retry.py:2479–2504` используют `asyncio.wrap_future`. Поэтому исправление лишь первого helper действительно не охватывало бы заявленный общий путь.

Новый тест различает именно ошибку: completed first future, capacity занят вторым job, heartbeat обязан пройти **до release** во всех трёх actual callers. Watchdog находится вне проверяемого loop, поэтому зависание не делает тест бесконечным. Result/error identity и exactly-once delivery не подменены повторным callable. При реализации нужно сохранить отдельные outcomes closed-loop/cancel, а не требовать успешной доставки в уже закрытый loop; текущая формулировка этой гарантии не требует.

Выбор `call_soon_threadsafe` и обработка закрытия согласуются с [Python3.14 event loop documentation](https://docs.python.org/3.14/library/asyncio-eventloop.html#asyncio.loop.call_soon_threadsafe). Locked AnyIO4.12.0 действительно не прекращает уже running thread при abandoning waiter; отказ от новой pool/framework migration обоснован. [AnyIO4.12.0 source](https://raw.githubusercontent.com/agronholm/anyio/4.12.0/src/anyio/to_thread.py).

### RD-02 → CLI-01: wire keys и own-property presence — ACCEPT

REQ-CLI-01-01 и TEST01 теперь различают quoting от data-property semantics: computed keys либо entries, explicit own-property policy и reserved-key corpus. `params?.[key]` не объявляется решением inherited property lookup. JSON.parse/null-prototype positive input не теряет `__proto__` до входа в client; absent optional `{}` проверяет inherited `constructor/toString` отдельно. TS/JS получают общий emitter, поддержанные новые имена и перестановка не требуют endpoint branches. Literal path escaping и прежний `a/b→a%2Fb` oracle не потеряны.

Исходный generator `:483–493`/`:625–635` создаёт path/query обращения из raw names, а buildQuery `:439–458`/`:590–609` перебирает собственные entries. Следовательно, позитивный `URLSearchParams.getAll/keys` oracle обнаружит исчезновение reserved key, а не только синтаксическую ошибку. Особая noncomputed `__proto__` семантика и computed data property независимо проверены по [ECMAScript PropertyDefinitionEvaluation](https://tc39.es/ecma262/multipage/ecmascript-language-expressions.html#sec-object-initializer).

Scope не расширен до произвольных class-instance getters: поддержан params-record, иной реальный caller требует явного отдельного контракта. Canonicalizer, exact three outputs, Node22, lock, public error/binary ABI и architecture gate остаются обязательными.

### RD-03 → MIG-05: registration descriptor не universal behavior hash — ACCEPT

Passport и REQ-MIG-05-04 теперь корректно ограничивают fingerprint registration-time descriptor. Narrow except repair REQ01/TEST01 не ослаблен и не замаскирован новым framework. Stable supported повтор, conflicting repeat, empty-cell и unsupported-capture outcomes сохранены. TEST04 добавляет post-registration semantic-config mutation, immutable positive и harmless observer control; stronger reproducibility отделена от обычного compatibility corpus.

Source `ir/migrations/base.py:508–558` действительно допускает mutable mapping/list/set; `:561–591` вычисляет snapshot hash, `:594–650` сохраняет live `fn`, `:1100–1123` позже вызывает его. После изменения captured semantic dict регистрационный fingerprint сам по себе не может обещать прежнее поведение. Поэтому новый bounded non-reproducible outcome — честное сужение чрезмерного claim, не новая продуктовая неспособность, скрытая отказом.

Нет blanket rehash/freeze всех captures, исторические IDs не меняются молча, Common/IR observable profiles и DataForge graph distinction сохранены. Для реально заявленного reproducible converter нужен выбранный finite stable semantic binding; глобальная эквивалентность Python не требуется.

### RD-04 → RUN-02: warm numerical parent qualification — ACCEPT

REQ-RUN-02-03 и TEST03 теперь явно отличают cold transport от actual warm numerical launch. Нужны actual parent JAX operation, recorded start method/backend/env, meaningful child numerical result, typed attempt binding, bounded external watchdog и cleanup. Неподдержанный profile может остаться явно незаквалифицированным; это не объявляется FAIL уже проведённого запуска и не блокирует отдельный EOF repair.

`retry.py:2514–2529` действительно явно выбирает Linux fork и Darwin spawn. Многопоточный fork проблематичен по [Python3.14 multiprocessing](https://docs.python.org/3.14/library/multiprocessing.html#contexts-and-start-methods), а [pinned JAX0.8.2 xla_bridge.py](https://raw.githubusercontent.com/jax-ml/jax/jax-v0.8.2/jax/_src/xla_bridge.py) содержит соответствующее предупреждение. Это риск, а не доказательство неизбежного deadlock в каждой операции.

Revised text не предписывает «заменить одно слово на spawn», не меняет global start method и не убирает supervisor/subreaper/group cleanup. Forkserver предлагается только с проверкой clean preload. Linux/Darwin остаются отдельными profiles; cold small/1MiB transport, drain-before-join, current receipt и прежняя EOF decision table не изменены.

### RD-05 → STA-02: независимый prior oracle — ACCEPT

REQ-STA-02-01 и TEST01/04 теперь сохраняют direct-bridge parity **как wiring regression**, но требуют отдельный mapping oracle: value2, std_error0.2, multiplier3, отсутствующий confidence_interval → pre-sampling mean2/std0.6. Это не exact sample mean. Численное совпадение после смены seed/draws не считается само по себе ни доказательством reuse, ни ошибкой. Проверяется фактически использованная текущая конфигурация.

Source `parameter_transfer.py:112–138` умножает base std на multiplier и применяет finite floor; `:177–205` сначала использует пригодный CI, затем std_error. Предлагаемый fixture правильно исключает CI precedence. `:342–362` вычисляет sampled statistics, поэтому отказ от exact sample-mean oracle необходим. Second parameter и permutation различают field mixing; мутант, одинаково игнорирующий multiplier в fresh/reused bridge, теперь не пройдёт независимый prior oracle.

ResolveParametersNode ранний return `:235–253` и existing fresh derivation `:419–443` подтверждают, что reuse repair и mathematical qualification — разные задачи. Existing bundle ref, selector calls=0, source-bound matcher, five presence values, prepared DuckDB connection и finite/unsupported behavior не потеряны. Native causal consumer qualification не превращена в blocker narrow repair и не обещает Python3.14 поддержку dependency с несовместимым marker.

### RD-06 → CLI-01: actual bidirectional service roundtrip — ACCEPT

REQ-CLI-01-05 и TEST05 теперь требуют полный request envelope в actual local Runtime service и возврат actual status/headers/body bytes в JS Response, затем результат через неизменённый public generated-client decode/error path. Это устраняет конкретную слабость: текущий test owner `test_runtime_client_contract_bridge.py:138–166` возвращает fake200 в JS, а `:169–198` отдельно передаёт Python TestClient только parsed.path.

Новый bounded relay проверяет реальный transport contract, не заменяет auth/service/store; permitted ephemeral local server — альтернативный future execution profile, не внешнее действие в этом review. Header drop/status alteration/binary corruption должны различаться на публичном клиентском результате, поэтому constant result/error suppression больше не удовлетворяют предложенному oracle. Selected supported GET и доступные allowlisted POST/binary families достаточно ограничены: 103-operation census не превращён в 103 обязательных executions. Неизвестные/неподдержанные routes явно вне claim; существующие binary/error ABI не меняются ради теста.

## 2. Сохранение исходных obligations и согласованность документов

Независимая stdlib проверка обеих версий подтвердила для каждой карточки:

- **20 REQ и 20 TEST** суммарно: ID sets и порядок не изменены; новых IDs нет.
- У каждого REQ не изменены source/audit/test bindings; у каждого TEST — requirement bindings.
- Полностью неизменны residual dispositions, preservation и preservation bindings, исходные source obligations, inventory obligation dispositions, dependencies и shared scenario IDs.
- Все revised requirement text, test setup/action/oracle совпадают между MD и JSON.
- Actual file hashes совпадают с proposed_changes manifest; actual semantic JSON changes ограничены перечисленными corrections (плюс EXE owner census и CLI technical solution).
- Baseline, product repository и proposed files в ходе этого readback не редактировались.

**Отложенное согласование, не новый packet finding:** shared03/aggregate04 по мандату ещё не обновлены. Перед финальной упаковкой туда необходимо перенести strengthened I06/I12 assertions и точные role/limit bindings. Старый общий smoke не должен выдавать PASS за новые independent prior/full-client-roundtrip claims. Это уже запланированная интеграционная стадия root, а не основание переписывать исправленные пять карточек.

## 3. Что остаётся future execution, а не readback acceptance

Не запускались Node22, JAX, AnyIO, migrations, pytest, generated client, actual runtime service или subprocess supervisor. Официальные источники подтверждают язык/API/risk, но не product PASS. Actual race matrix, bytes roundtrip, native warm-parent result, field mapping и installed callback corpus ещё должны быть предъявлены исполнителем в поддержанном профиле.

При реализации сохранять две точности, уже предусмотренные текстом: finite floating comparison для0.2×3, а не битовое равенство десятичному literal; warm JAX операция должна действительно завершиться перед выбранным launch, а не быть только поставлена в async queue. Это execution-detail checkpoints, не обнаруженные новые дефекты спецификации.

## 4. Exact reviewed hashes

Полные baseline/new MD+JSON hashes и source hashes сохранены в `review_runtime_v2.json`; ниже новый immutable readback slice.

| Пакет | revised MD SHA256 | revised JSON SHA256 |
|---|---|---|
| EXE-01 | `3847d3d580e2a05b39dfcb2ec6636d6907d22cf9295aeb42e8231a15e26b7519` | `1fa6106d9bf422671517a72241152524d666817177b3976ad6d6460c3c6ae7c1` |
| STA-02 | `77dfdc8b59e5d65b6474e9915e6dabc355daffd6a72b91dc92d98a4b8bd361a4` | `805a6b4ada6c6524619fe33b972bf9cd8b616782c6dabc3a4c351677c538ca2d` |
| RUN-02 | `ebebd0c2f88692edeb925ff72baf200c36fa42f3dbb056b55bb807588b60fff3` | `b745f3333e6c2bad85eebe19c27b8909247795d44766d36cb60c3e2c5d4d1757` |
| MIG-05 | `c43fad07954078f6418d740daee490b6c00c3b14d2ac05f8696419da9a86ebb2` | `1ea3190f21cf89033767f9eef5bd86904fb9084e19203deb4caef30f1dbb8025` |
| CLI-01 | `c3c0681f4f20c2b2bc24c2583b39c08ffb6b5142d47b67b7e8b0f8dd682dab87` | `d674dc4134ea01e49252bf7b70175fdd11018dd3719ad744a2cabf09cebc6214` |

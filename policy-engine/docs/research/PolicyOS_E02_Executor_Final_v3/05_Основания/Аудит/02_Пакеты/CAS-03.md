# CAS-03 — одна подготовка bytes и bounded batch verification

## 1. Решение

**Ограниченно оценён, не закрыт.** B152 и B154 имеют реальные содержательные исправления: один verified immutable snapshot используется подписью, локальные ошибки не уничтожают независимые результаты, abort сохраняет completed rows. Pending futures действительно ограничены. В B155 остаются **R01 — полная непрерываемая подготовка default inventory; R02 — потеря cooperative cancellation внутри дедупликации explicit source**.

Свежий C76: **7 MATCH,23 unchanged existing bodies/cases PASS** в явно ограниченном harness; actual Ed25519 исполнена, native pytest/custody не заявлены. MATCH включает воспроизведение остатков. Срез `20d9009be21097bfbdc38a546a15cc60213b8ace`. [Исходные строки 8781–8892](../05_Источники/CAS-03_исходные_строки.txt), [SHA/lines/Git blobs](../05_Источники/C76_источники.json).

## 2. Матрица B152/B154/B155

| ID | Найденный ремонт | Граница |
|---|---|---|
| B152 | Integrity owner вычисляет один digest; snapshot хранит точные blob/manifest bytes; store signature path не открывает их повторно | P02: по одному read blob/manifest/signature и один integrity hash, настоящий Ed25519 valid. Сам public crypto verifier отдельно хэширует входные bytes; это не прежний triple-integrity bug и не требование доверять внешнему checksum. |
| B154 | Локальные Exception становятся ERROR; completed независимые rows сохраняются; executor/inventory/cancel/global signal имеют aborted state | P01:23 cases PASS, включая BrokenExecutor submit/result, local PermissionError, BaseException propagation и caller-owned authorization loss. Native owner/tenant qualification остаётся. |
| B155 | Source читается через bounded pending window; explicit ID dedup не делает ранний list; callback contexts переносятся | Existing40-ID test при pending4 проходит. Default name census всё ещё O(N) до первого yield; dedup loop не видит cancel между повторами. Final details и seen IDs остаются O(N), не «константная память». |

## 3. Producer → persisted bytes → verifier → consumer

`FileSystemCAS` public sign/verify нормализует typed selector; transaction lease и `_load_verified_snapshot` читают ровно выбранные manifest/blob, проверяют identity/profile/type/size/digest. `_load_signature_for_snapshot` читает sidecar, связывает её с **тем же manifest snapshot**, затем `_signature_ops.verify_signature` передаёт exact bytes настоящему `Ed25519Verifier` (`S03:2903–3054,5983–6243`; `S02:254–328`). Native current ownership в harness заменён fixture, но actual selected read/verification bodies и cryptographic algorithm не подменены.

Verifier проверяет content bindings, trust, revocation, optional strict identity и Ed25519. P04 меняет live blob после загрузки snapshot: signature того snapshot valid, а следующий live integrity read отказывает. Это различает snapshot от повторного открытия пути, **не разрешает внешним writers обходить lease**. P05 даёт untrusted/revoked/invalid identity/invalid signature на свежих реальных keys.

Batch owner сохраняет input order, typed item statuses и отдельные `state/admitted/finished/inventory_exhausted/abort_reason`. Request-owned `BatchAuthorizationLossSignal` останавливает новые admissions атомарно относительно submit, но не является собственным authorizer и не прерывает уже admitted callbacks (`S04`). Локальный denied item нельзя автоматически превратить в утрату всей общей авторизации.

CLI consumer найден и прочитан полностью: JSON передаёт DTO, text показывает state/reason, invalid/untrusted/revoked/error дают nonzero exit; unsigned зависит от явной опции (`S08:217–292`). Legacy `BulkVerificationReport.ok` — outcome-only convenience, не доказательство runtime completeness или custody. Native CLI запуск не выполнен.

## 4. Что реально исполнялось

**P01:**9 selected bodies из `test_cas_03.py` и все14 из `test_b154_batch_completion.py` исполнены unchanged. Среди них local item/preflight failures, generator dedup,40 IDs с pending4, cancellation, broken inventory, default membership change, BrokenExecutor при submit и Future.result, completed rows, legacy DTO, authorization loss до admission/после результата/drain admitted, BaseException и типизированный signing-vs-verification abort reason. Все23 PASS, не native pytest.

**P02:** actual no-follow store readers: blob1, manifest1, signature1; integrity hash1; crypto verifier blob hash1. Это counters, не ускорение. **P03:** good/tamper/wrong-size/restored good каждый с одним integrity hash, результаты true/false/false/true. **P04:** exact snapshot preservation против позднего live mutation. **P05:** настоящие cryptographic negatives. **P06–P07:** отрицательные controls ниже.

Сохранять реальный repair: same exact immutable bytes, independent verifier input checking, current trust/revocation без глобального validity cache, local ERROR не valid, explicit aborted reports, контекст workers, scoped inventory reconciliation, bounded pending и отсутствие безусловного materialized list для explicit source.

## 5. Подтверждённые остатки

### C76-R01 — default census не bounded/cancellable (low)

`_authenticated_default_inventory_cursor` честно документирует полный name-tree walk и materialized map/visible IDs до первого yield. `cancel_event` проверяется вокруг `next(iterator)`, но не внутри `_capture_inventory_member_paths` (`S03:5353–5510`; `S02:127–151`). P06 на20 actual fixture artifacts ставит cancel при первом CAS-root scandir: всего38 scans,37 после отмены. Member reads пусты, worker admissions0, итог правильно `aborted/cancelled`.

Это **не authority bypass и не ложный success**, а непокрытая часть B155 — затраты preparation и реакция на отмену. Existing collected default test считает content reads/yields, поэтому не опровергает name traversal. Неколлектируемый removal probe в начале test file прямо отличает этот случай; мы его не выдаём за запуск native test. Исправлять через existing cursor/stop contract, сохранив complete canonical membership и scoped-owner проверку; не убирать валидацию ради bounded claim. RSS и latency не измерены.

### C76-R02 — explicit dedup source поглощает повторы после cancel (low)

Actual `_iter_canonical_artifact_ids` внутри одного `next` перебирает повторные ID без cooperative stop. P07: первый unique item завершён; source ставит cancel, выдаёт200 повторов того же ID и заканчивается. Все200 прочитаны, `_run_bounded` видит StopIteration раньше post-next cancel check и возвращает `state=complete, inventory_exhausted=True, abort_reason=None` при выставленном cancel. Контроль с distinct вторым ID корректно даёт `aborted/cancelled`, admitted1 (`S03:280–291,3024–3054`; `S02:127–151`).

Нарушение узкое: cancellation не останавливает inventory consumption внутри dedup и не отражается в этой ветви завершения. Мы не исполняли бесконечный iterator, не утверждаем production hang, лишнюю crypto работу, потерю completed rows или незаконную публикацию. Нужно расширить существующий iterator/cooperative stop и проверить exhaustion, сохранив dedup; новый scheduler не нужен.

## 6. Квалификационные остатки и минимальное продолжение

**G01:** native initialized CAS, tenant/input/current owner, durable sidecar transaction, native stream/metrics bodies и CLI. Actual Ed25519 над fixture store — больше, чем fake verifier, но меньше полной custody цепи. Protected current access нельзя заменить правильным hash. Full package imports требуют supported runtime.

**G02:** production-size memory/throughput, большие blobs и consumer-level semantic claim. Полный report и seen-ID set по-прежнему O(N); snapshot хранит bytes целиком. Pending cap — не byte cap и не RSS measurement. Отдельный digest внутри public cryptographic verifier сохраняет собственную проверку входа: не объявлен дефектом только ради буквального «один hash везде». Subject-matter validity, научная состоятельность и допустимость policy recommendation не следуют из подписи synthetic bytes. Расширять existing owners/consumer contracts, не новый общий provenance runtime.

## 7. Команды, seams и честность результата

[Commands/exit/logs](../04_Проверки/C76_CAS03/commands.json) · [Все observations/cases](../04_Проверки/C76_CAS03/bounded_diagnostics.json) · [Native/seams](../04_Проверки/C76_CAS03/native_verification.json) · [Остатки](../01_Реестры/C76_остатки.json).

Финальный run04 exit0. Attempt01/02 сохранены: внешняя ошибка extraction closing line и namespace annotation, исправлены только в harness. Attempt03 был успешен; final run добавил measured read counter и distinct-ID control. Base helper derived from C74/C75, но C76 — новый свежий run, не reconstructed lost evidence. Whole integrity/signing/batch_control, actual ThreadPoolExecutor и selected unchanged store/batch bodies исполнены. PEP695 context trampoline — explicit `context.run` fixture; owner index/admissions/sidecar publication/generation — fixtures. Эти seams не скрываются названием PASS.

Native pytest отсутствует; обычный store import на Python3.12.14 блокирован Python3.14 syntax, Pydantic2.13.4 вне baseline. Native pytest bodies=0. Никаких installs, checkout edits, production keys или network services. Репозиторий чист.

**76/127 рассмотрены ограниченно. Следующий — REP-01. Полного закрытия нет; фаза 2 не начата.**

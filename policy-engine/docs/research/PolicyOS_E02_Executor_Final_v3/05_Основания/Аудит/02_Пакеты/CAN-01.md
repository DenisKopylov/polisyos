# CAN-01 — общий строгий канон с раздельными Core/IR профилями

## 1. Решение

**Ограниченно оценён, не закрыт. Основное выделение общего primitive выполнено; новый подтверждённый product defect не установлен.** Codec/hash mechanics принадлежат нейтральному `common`; Core и IR сохраняют собственные фасады, классы исключений, tag policies и исторический default 0.2.0. IR не получил скрытого импорта Core или его расширенного decoder.

Свежий прогон: **7 bounded MATCH; 52 неизменённых test bodies / 127 cases: 125 PASS, 2 FAIL**. Два FAIL сохранены, а не устранены изменением тестов: старый characterization требует записи `float_hex`/`bytes_hex` в прежнем виде, тогда как нынешняя producer conformance защита намеренно запрещает non-roundtrippable output. Low-level чтение этих bytes сохранено, но selected-profile admission их отвергает. Поэтому полного historical compatibility PASS нет.

Срез `20d9009be21097bfbdc38a546a15cc60213b8ace`. [Исходная карточка](../05_Источники/CAN-01_исходные_строки.txt) · [Pinned sources](../05_Источники/C78_источники.json).

## 2. Исходные требования и состояние

| ID | Проверенный результат | Остаток |
|---|---|---|
| LA-021 | Общие canonical/hash owners; отдельные Core/IR allowed tags и exceptions; ordinary golden byte/hash parity; version-specific 0.3 grammar, неизвестная версия не становится default | G01: intentional delta и красные characterization cases; G02: native persisted consumer; G03: полнота исторического корпуса |
| LK07 | Strict canon не объединён с runtime `JsonDataVisitor`; отдельные wire semantics сохранены | C73/WIRE не переаттестован этим codec прогоном |
| LK20 | Независимые hashlib vectors подтверждают digest точных bytes | Hash не доказывает полноту входов, reuse eligibility, custody или closeout |

Файл `common/canonical.py` здесь не новая третья конкурирующая реализация: фасады вызывают его функции с собственными policy/error arguments (`S01`, `S04`, `S07`). Core hash facade и IR content_hash делегируют `common.hashing` (`S03`, `S05`). Named-domain hashes сохраняют старую механику; совпадение version string вне canonical domain не включает новую grammar автоматически.

## 3. Producer → bytes/profile → consumer

**Codec.** Shared encoder фиксирует допустимый CanonSpec до caller callbacks. Для canonical name версия 0.2.0 остаётся исторической; 0.3.0 явно экранирует обычные mappings с `_type`, отличая их от native envelope. Logical depth и физический wire budget различаются. Bounded encoder принимает закрытый callback-free набор, считает bytes/nodes/depth до крупных materializations, фиксирует counted snapshot и отказывает cycles. Core descriptor carriers введены явно; IR не принимает их как свои native types (`S01`, `S04`, `S07`, `S15`).

**Profile.** Shared parser требует полный raw canon declaration; отсутствие возможно только как явно unqualified candidate, неизвестный профиль остаётся raw-only, same-byte decode/reencode проверяется отдельно. Конструирование похожего `CanonicalProfileRead` не даёт доступа к authority value. Core и IR указывают разные reader policy IDs: `core-tag-policy@1/2` и `ir-tag-policy@1/2` (`S02`, `S11`). Эти IDs обозначают выбранный reader, а не аттестацию producer.

**IR.** Actual `put_json_artifact` строит typed options/CanonInfo, затем вызывает store boundary; get сначала читает raw declaration, сопоставляет selector/typed manifest при наличии, проверяет payload SHA и только затем запускает IR decoder/profile bridge. В C78 actual facade сохранён, storage заменён простым файловым fixture. Generic 0.3 writer отказывает до store call; explicit 0.3 reader работает над предоставленным подходящим profile/bytes fixture. Это не разрешение включить generic writer или owned callbacks (`S09:401–514,644–782`).

**Core.** Unbounded selected reader проверяет raw/typed manifest и profile selection, выбирает exact payload ref, сверяет content hash, затем вызывает общий profile bridge и связывает artifact identity. C78 исполняет actual decode dispatcher и существующий malformed-profile-before-payload тест, но не квалифицирует весь native CAS owner (`S11`). Документация отдельно описывает узкий bounded 0.3 cohort; наличие codec не заменяет его enrollment/resource/custody qualification (`S18`).

## 4. Свежие проверки

1. **P01 — исходный CAN corpus:** 9 bodies, 19 cases; 17 PASS, 2 FAIL. Ordinary Decimal/date/bytes/null/numeric bytes и hashes, malformed JSON/unknown tags/depth, exact non-string-tag exception identities, separate exports и SHA1 warning проверены unchanged.
2. **P02 — текущий 0.3/bounded corpus:** 33 bodies, 98 cases PASS. Включены escaped mappings, native-vs-raw различение, malformed envelopes, duplicate keys, NaN constants, unknown versions, descriptor carriers, exact/one-over budgets, отказ до serializer/base64/sort, counted snapshot после изменения source, shared occurrence/cycle и Unicode/separator vectors.
3. **P03 — shared profile corpus:** 10 bodies/cases PASS. Declared/absent/unknown и forged-read границы, whole-profile conformance, различия tag laws, отказ malformed Core profile до payload IO, v1/v2/v3 manifest projection goldens. Actual Core modules работают за package initializer shell, а не native full artifact package.
4. **P04 — intentional delta:** low-level Core decoder читает `float_hex` как 3.0 и `bytes_hex` как bytes. Current writer и selected-profile bridge отказывают оба alias payload с `canon_profile_payload_nonconformant`; `array_digest` control сохраняет bytes и проходит selected profile. Existing producer regression прямо требует отказа первых двух до persistence (`S17`). Не следует удалять защиту для возвращения зелёного старого characterization.
5. **P05 — actual IR chain:** facade writer → реальные локальные blob/manifest bytes → actual reader возвращает mixed value. Изменённые bytes дают identity mismatch; false float policy даёт profile nonconformance; неизвестная версия отказывает после manifest без payload read. Generic 0.3 writer fenced до storage, explicit 0.3 reader принимает корректный escaped fixture. Storage не настоящий CAS.
6. **P06 — current policy dispatch:** actual Core profile bridge и IR callbacks читают 0.2/0.3 под соответствующими отдельными policy IDs; ordinary mixed payload имеет ожидаемую byte parity. Это не доказательство равенства двух tag domains.
7. **P07 — raw hashing:** SHA256, BLAKE2b default/20 bytes, bytes/bytearray/memoryview/UTF-8 string, streaming и truncation совпадают с независимым hashlib. Unknown algorithm и неположительная длина отказывают; SHA1 warning отдельно в P01.

Native standalone imports common/Core/IR codecs и IR IO прошли без product stubs. Дополнительный свежий процесс `import polisyos.ir.artifacts.io` оставил список Core modules пустым. Full architecture scan не запускался. **MATCH P01 означает честно воспроизведённые два FAIL, а не все тесты зелёные.**

## 5. Что сохранить и что осталось

**Сохранить:** один нейтральный owner; точные старые bytes/IDs; разные Core/IR exceptions/tag sets; explicit version dispatch и policy IDs; текущий conformance guard; bounded callback-free encoder; отдельный runtime JSON contract; generic writer fence. Не требуется новая codec архитектура или массовая перезапись CAS.

**C78-G01 — compatibility и oracle.** Отделить equivalence move от намеренного ужесточения writer/selected reader. Старые raw alias bytes читаются низкоуровневым decoder, но не проходят современное same-byte admission. Нужны source-qualified реальные исторические objects и явный read-only/candidate compatibility путь, если он требуется поддержкой; не выдавать synthetic alias за production corpus и не ослаблять authority gate. Согласовать старые regression ожидания с принятым текущим контрактом. Конкретный испорченный production artifact не установлен; два красных case не скрыты.

**C78-G02 — native integration.** На supported Python/Pydantic исполнить existing pytest, native filesystem/async writer preflight и selected reader, затем общий LANE-06/CP2 installed-package прогон. C78 не проверяет native transaction, owner/signature admission или crash durability. Узкий уже существующий 0.3 sidecar cohort квалифицировать как отдельный enrolled path, не распространять разрешение на generic/owned callbacks.

**C78-G03 — полнота и смысл.** Golden corpus и 125 PASS не равны доказательству всех старых структур или всех consumers. Сохранять LK07/LK20: runtime JSON другой контракт; digest не producer authority, полнота evidence set, reuse eligibility или научная валидность. Отсутствие universal deterministic semantic model здесь не дефект; codec не должен придумывать содержание политики.

## 6. Воспроизводимость, ограничения и уточнение C76

[Commands/exit/logs](../04_Проверки/C78_CAN01/commands.json) · [Cases/observations](../04_Проверки/C78_CAN01/bounded_diagnostics.json) · [Native/seams](../04_Проверки/C78_CAN01/native_verification.json) · [Остатки](../01_Реестры/C78_остатки.json).

Final run03 exit 0: 7 MATCH, 127 unchanged cases с сохранёнными 2 FAIL. Run01/02 сохранены; дополнительные controls добавлялись только во внешний probe. Pytest отсутствует, full Core artifact import блокирован Python 3.14 syntax при текущем 3.12; environment failure не product defect. Actual native codec imports работают — blanket «всё UNRUN» неверно. Existing bodies запускались внешними pytest helpers, не native runner/plugins. Core initializer shell и filesystem storage fixture раскрыты отдельно. Checkout чист; зависимости и product source/tests не менялись.

**Уточнение C76:** прежняя metadata фраза о якобы неподдержанном PEP695 на Python 3.12 ошибочна. Это был выбор extraction harness. [Явное исправление и новый supplemental replay](../03_Основания/Уточнение_C76_в_C78.md): whole actual `_signature_ops` с исходным trampoline, 7 MATCH и 23/23 existing cases PASS, при прежних fixture custody seams. Запечатанный C76 не изменён; это не ретроспективный native PASS и не добавление этих 23 cases к CAN counts.

**78/127 рассмотрены ограниченно. Следующий — MIG-01. Фаза 2 ещё не начата.**

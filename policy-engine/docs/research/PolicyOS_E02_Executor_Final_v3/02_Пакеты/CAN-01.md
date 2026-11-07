# CAN-01 — Strict canon: один primitive, явные Core/IR профили

## 1. Паспорт и результат

**LANE-06 · CP2 · основание 20d9009be21097bfbdc38a546a15cc60213b8ace · статус: ТЗ, не выполнено.** Технический исполнитель и reviewer назначаются проектом. Исходные ID: LA-021. Тип: intentional delta reconciliation + native historical qualification.

Сохранить общий strict primitive с разными Core/IR policy, явно оформить два исторических characterization расхождения и проверить bytes/profile→native consumer без ослабления conformance gate.

Основания: [аудит](../05_Основания/Аудит/02_Пакеты/CAN-01.md), [все остатки](../05_Основания/Аудит/01_Реестры/C78_остатки.json), [неизменная исходная карточка](../05_Основания/Аудит/05_Источники/CAN-01_исходные_строки.txt), исходный объединённый план §CAN-01 (исторические строки 9008–9128).

## 2. Уже работает — сохранить

- Common canonical/hashing нейтральны; Core/IR фасады сохраняют разные tag sets, exact exception catches и policy IDs.
- Исторический default0.2.0 и подтверждённые byte/hash identities; explicit0.3 grammar не включается молча по сходству version/name.
- Текущий same-byte conformance, bounded callback-free encoding и generic0.3 writer fence.
- Runtime JsonDataVisitor/WIRE — другой контракт (LK07); hash не authority/reuse/closeout (LK20).

Изменение продукта требуется только при воспроизведённом несоответствии ниже; отсутствие native проверки само по себе не дефект. Не создавать искусственный рефакторинг для отчёта.

## 3. Полнота обязательств и disposition

| Основание | Решение | Требования |
|---|---|---|
| C78-G01 | qualify: Два красных старых oracle оформить как intentional producer/selected-reader delta; raw historical compatibility отдельно, gate не снимать. | REQ-CAN-01-01, REQ-CAN-01-02 |
| C78-G02 | qualify: Реальные sync/async writer→CAS→selected reader и only enrolled bounded0.3 route. | REQ-CAN-01-03 |
| C78-G03 | qualify: Расширить source-qualified supported corpus, сохранить separate policies/ABI и границы hash; малый golden не exhaustive proof. | REQ-CAN-01-01, REQ-CAN-01-03 |

### Исходные обязанности, не только новые R

- LA-021: эквивалентное выделение shared primitive отдельно от intended format/conformance behavior delta; Core не единственный правильный профиль.
- Все numeric/Decimal/date/bytes/null/depth/tags/error/hash-warning обязательства сохраняются; корпус конечный и его provenance явны.
- LK07/LK20 запрещают merge всех serializers и повышение digest до полномочия на scientific/reuse result.

## 4. Нормативный контракт

### REQ-CAN-01-01
Core и IR продолжают вызывать один neutral primitive с собственными allowed tags, CanonViolation identity/catches и reader policy IDs. На source-qualified supported corpus сохраняются exact bytes/hash ordinary0.2 и low-level чтение поддержанных aliases; IR не получает Core tags/import. Unknown version/profile не fallback default. Goldens отдельно фиксируют exception type/message/code и SHA1 warning.

Источник: LA-021; аудит: C78-G01, C78-G03; проверки: TEST-CAN-01-01.

### REQ-CAN-01-02
Старые characterization ожидания записи float_hex/bytes_hex согласовать с явным current contract: low-level raw decoder читает aliases, но current producer и selected-profile admission отказывают non-roundtrippable bytes canon_profile_payload_nonconformant. array_digest positive остаётся. Если реальные поддержанные historical aliases нужны, использовать явный read-only/candidate path без authority elevation и без переписи IDs; необходимость/границы фиксируются из реального corpus, не синтетического предположения.

Источник: LA-021; аудит: C78-G01; проверки: TEST-CAN-01-02.

### REQ-CAN-01-03
Native filesystem и async writer preflight→exact selected manifest→fresh reader сохраняют canon declaration, payload hash, profile selection и current owner admission. Malformed/mismatched declaration отказывает до payload IO там, где текущий boundary это гарантирует; generic0.3 producer остаётся fenced. Only enrolled bounded0.3 cohort проверяется по собственному allowed payload/resource/custody policy; успех codec не расширяет enrollment.

Источник: LA-021; аудит: C78-G02, C78-G03; проверки: TEST-CAN-01-03.

## 5. Техническое решение и producer → consumer

Не выделять ещё один codec: common.canonical/common.hashing уже owners. Обновить test_can_01 только по зафиксированной split matrix raw-read vs current-producer vs selected-read, сохранив два прежних failed observations в audit. При необходимости historical support добавить узкий явно named candidate consumer над существующим raw decoder, не обход _decode_and_reencode_profiled_bytes в authority path. Native bridge IR _read_json_artifact_with_bytes и Core selected profile использовать без fixture store; new default/version rollout не входит в пакет.

### Проверенные owners на срезе
- policy-engine/src/polisyos/common/canonical.py: shared strict encoding/decoding
- policy-engine/src/polisyos/common/canonical_profile.py: _decode_and_reencode_profiled_bytes, profile admission
- policy-engine/src/polisyos/common/hashing.py: content_hash
- policy-engine/src/polisyos/core/canon/canon_json.py: to_canonical_bytes, _validate_core_json_payload_conformance
- policy-engine/src/polisyos/ir/model_layer/canon.py: to_canonical_bytes, _validate_ir_json_payload_conformance
- policy-engine/src/polisyos/ir/artifacts/io.py: put_json_artifact, _read_json_artifact_with_bytes

Общий широкий decoder/default0.3 ломает persisted ABI и policy separation. Массовое re-encode CAS меняет IDs и не нужно. Read-only candidate — только если реально требуется support, не обязательная новая подсистема.

## 6. Локальная приёмка — все будущие проверки NOT_RUN

### TEST-CAN-01-01
- Уровень: unit + targeted native integration.
- Setup: Два фасада и common primitive; ordinary corpus Decimal/date/datetime/bytes/null/numeric, typed tags, depth exact/one-over, malformed JSON/duplicate keys/NaN; исторические файлы с provenance.
- Действие: Encode/decode/hash и exact exception tests; fresh import IR IO; v0.2/v0.3 mappings с _type, unknown version/name combinations.
- Точный oracle: Поддержанные goldens byte/hash identical, separate Core/IR errors/tags/policy IDs; fresh IR не импортирует Core. v0.3 escapes не влияют на default0.2; unknown не default. Corpus denominator/version зафиксирован, не заявление universal parity.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-CAN-01-02
- Уровень: unit + targeted native integration.
- Setup: Два unchanged failing characterization из test_can_01 и текущие producer conformance regressions; raw float_hex/bytes_hex/array_digest vectors.
- Действие: Переписать только устаревшие expected outcomes после explicit decision: raw read отдельно, encode и selected admission отдельно; проверить реальный historical object если доступен.
- Точный oracle: Raw aliases readable; producer/selected reader дают established nonconformance refusal до persistence; array_digest проходит. Не удалены negative tests/gate. Historical candidate помечен unqualified, не выдаётся authority value; исходные bytes/IDs неизменны.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-CAN-01-03
- Уровень: native writer + local CAS + fresh selected consumer.
- Setup: Current sync/async producer, real CAS and owner context; exact0.2 profile и explicitly enrolled bounded0.3 cohort, limits exact/one-over.
- Действие: Write/read, tamper bytes/raw-vs-typed manifest/profile, missing/unknown declaration; generic0.3 write; enrolled0.3 valid/overbudget/unsupported callback.
- Точный oracle: Exact selected ref и same bytes roundtrip; negatives refusal без publication/authority. Generic0.3 storage call count0; enrolled profile только accepted cohort, no callback before refusal. Hash validates bytes, не completeness/producer authority. Fresh package same behavior.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

Повторно использовать/расширить реальные места, а не создавать 127 harness: `policy-engine/tests/unit/remediation/test_can_01.py`; `policy-engine/tests/unit/common/test_canonical_profile.py`; `policy-engine/tests/unit/common/test_canonical_v3.py`; `policy-engine/tests/unit/core/artifacts/test_canonical_v3_writer_fence.py`; `policy-engine/tests/unit/ir/test_canon_v3.py`. До выбора selector прочитать полный test/fixture. Это проверенные пути, не утверждение о наличии всех предложенных assertions.

Допустимые doubles: storage-call counters для preflight unit tests и bounded input generators; final path real CAS. Запрещено: initializer shells/fixture storage для native acceptance, forged profile read как authority, synthetic corpus как production history.

## 7. Общая интеграция и порядок

MIG corpus сохраняет original bytes под old canon; CAS scenario повторно использует exact profile consumer, без отдельного огромного codec integration. WIRE-01 не переаттестуется canon tests.

Точные общие сценарии: E02-I06-E, E02-I06-D из [контракта интеграции](../03_Интеграция/LANE-06.md); одно свидетельство переиспользуется по неизменным input/backend bindings. Зависимости: нет обязательного нового предшественника; исходный DAG — ориентир, работающий контракт может удовлетворять ребру без нового ремонта. Общие файлы из §5 интегрировать последовательно с затронутыми owners; lane не новый runtime-реестр и не требование полного CI после каждого пакета.

## 8. Совместимость, история, rollback

Relocation equivalence, intentional conformance tightening и historical candidate support получают отдельные статусы. Старые125 PASS/2 FAIL — sealed historical evidence, не свежий PASS. Default0.2/exception API сохранять; rollout0.3 только explicit enrolled policy.

## 9. Free-grow и design direction

- Профиль декодирования не удостоверяет producer; current admission и историческая читаемость раздельны.
- Нейтральная механика позволяет рост новых явно версионированных profiles без Core→IR coupling.

Архитектурные источники: [policyos-identity-and-custody-boundary.md §1, §3–6](../05_Основания/Архитектура/policyos-identity-and-custody-boundary.md); [policy-design-custody-time-model.md §2–5](../05_Основания/Архитектура/policy-design-custody-time-model.md). Историческая подлинность и текущая пригодность раздельны; физический layout design-docs не догма.

Полные исторические probes/commands/logs остаются в отдельно доставленном phase1 ZIP; ссылки внутри копий аудита на `04_Проверки` относятся к нему, не к новым исполненным проверкам этого комплекта.

## 10. Нерешённые решения и передача

- Назвать supported historical corpus и решить, нужен ли alias candidate consumer; если реального корпуса нет, не заявлять blanket compatibility.
- Обновление двух expectations требует явного записанного behavior-delta решения; просто сделать suite green не acceptance.

Предъявить patch/base SHA (либо обоснованный no-code результат), актуальную карту callers, REQ→TEST→evidence, фактические команды/логи, различающий контроль и сохранённые инварианты. Поддержанный native профиль: P-CORE (Python >=3.14,<3.15 и project lock); для процессов P-PROCESS, для поставки P-PACKAGING. Не устанавливать зависимости без отдельного разрешения. Fixture/source-only, исторические PASS и отсутствие ошибки при импорте не закрывают свежий producer→persistence→fresh-reader. Успешная сериализация/конверсия/подпись не доказывает научной истины или полномочия policy result. Никакое требование/тест этой карточки ещё не исполнены.


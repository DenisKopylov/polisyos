# SCL-03 — Selected snapshot проходит normalization и полный enrich

**Лейн:** LANE-09 · **Окно:** CP2 · **Основания:** LA-025 · **Тип:** fix + migration preserve + native qualification.

**Практический результат.** Полный найденный документ той же версии, с известными applied constraints, достигает docs/claims без повторной загрузки и без потери selected reference.

**Статус:** исполнительское ТЗ. Это не выполненный ремонт; все новые TEST ниже — **NOT_RUN**. Исходный аудит выполнен на `20d9009be21097bfbdc38a546a15cc60213b8ace`; его полнота не означает закрытия остатков.

## 1. Основание и границы
[Аудит SCL-03](../05_Основания/Аудит/02_Пакеты/SCL-03.md), [остатки C105](../05_Основания/Аудит/01_Реестры/C105_остатки.json), [полная исходная карточка](../05_Основания/Аудит/05_Источники/SCL-03_исходные_строки.txt). LA-025 accountable closure; LK09/LK20 сохраняют разные owners и distinction bytes identity/reuse permission. R01 не означает утрату всей web_evidence lineage или доказанный native exploit. Full probes доступны в отдельно доставленном phase1 ZIP; historical bounded counts не являются свежей native приёмкой.

## 2. Сохранить
API preflight, all-snippet check, selected manifest, exactv1/explicitv2, no snippet reconstruction, ordinary URL/local/bytes routes и limits.

## 3. Полная disposition остатков

- **C105-R01 — fix** → REQ-SCL-03-01. Carry existing typed ref through normalization до intended recheck.
- **C105-R02 — fix** → REQ-SCL-03-02. Producer записывает фактически применённый profile; перенос synthetic field недостаточен.
- **C105-G01 — qualify** → REQ-SCL-03-03, REQ-SCL-03-04. Native full CAS/docs/fresh reader и applicable source rules; product wiring fix только по установленному разрыву.

Исходные обязанности и сохранения lossless inventory связаны отдельно в companion JSON (`obligation_dispositions`, `preservation_bindings`); номера residual не заменяют исходные обязанности.

## 4. Нормативные требования

### REQ-SCL-03-01
Bytes normalization должна сохранить typed selected raw_artifact_ref и согласованную source identity, чтобы actual _acquire_bytes повторно проверил тот же selected CAS view. Digest/size/bytes mismatch или недоступность selected view даёт gap/refusal до docs ingest; обычные manual bytes без ref остаются рабочими.

Основание: LA-025; аудит: C105-R01. Проверка: TEST-SCL-03-01, TEST-SCL-03-02.

### REQ-SCL-03-02
Actual fetch producer должен записать effective fetch_profile с реально применёнными normalized constraints, raw max_bytes, timeout, user-agent и transport/profile version, а также фактический byte_size независимо от наличия cache. Cache/SourceMetadata/API seed должны сохранить profile без подмены default policy. Historical missing profile явно unknown.

Основание: LA-025; аудит: C105-R02. Проверка: TEST-SCL-03-03.

### REQ-SCL-03-03
Search snapshot v1 должен доходить до full docs/claims consumer без повторного URL fetch; явный refresh v2 создаёт новую lineage и сохраняет доступный v1. Missing/denied raw не реконструируется из snippets и не запускает скрытый live fallback.

Основание: LA-025; аудит: C105-G01. Проверка: TEST-SCL-03-02, TEST-SCL-03-04.

### REQ-SCL-03-04
API source-binding gate должен проверять selected manifest/digest/schema/producer/profile и каждый snippet как exact extracted substring; document/byte/MIME и current applicable access/reuse limits сохраняются через normalization/acquire. Public-web label не является самостоятельным разрешением.

Основание: LA-025; аудит: C105-G01. Проверка: TEST-SCL-03-01, TEST-SCL-03-04, TEST-SCL-03-05.

## 5. Решение на текущих owners
Все code paths ниже repo-relative от `policy-engine/` на pinned commit.

1. `src/polisyos/scholar/discover/manual.py` bytes normalization создаёт новый SourceSpec и сейчас теряет `raw_artifact_ref`. Передать typed ref неизменённым вместе с data/license/props; canonical bytes locator по hash остаётся. Проверить consistency ref.artifact_id и data digest без downgrade selected profile до digest-only. Ordinary manual data без ref не делать искусственно зависимыми от CAS.
2. `src/polisyos/scholar/orchestrator/enrich.py::_acquire_bytes` уже выполняет selected get_manifest/get_bytes, equality/hash/size; включить его existing logic сохранённым ref, а не писать второй policy. Public API `src/polisyos/scholar/api.py::_seed_sources_from_web_bundle` и `src/polisyos/scholar/search/source_binding.py::validate_web_evidence_source_binding` остаются preflight, acquisition recheck не заменяет их. Сохранять отдельный web_evidence payload.
3. `src/polisyos/scholar/search/fetcher.py::fetch_open_page` при actual successful fetch заполнить existing FetchResult.fetch_profile до cache.put и byte_size=len(raw_bytes) даже без cache. Минимальный versioned profile: actual normalized SearchConstraints fields, max_bytes, timeout_s, user_agent, transport contract/profile version; final_url/redirect chain/MIME/hash — existing sibling evidence. Версия описывает интерпретацию fields, не фиктивное software attestation. Не копировать requested settings, если transport фактически применил другое значение. SCL-01 совместно использует profile для current-cache admission; один writer fetcher.
4. Existing `UrlFetchCache`, SourceMetadata, APIseed уже переносят profile; закрепить actual production wiring tests, не ещё DTO. Historical empty profile имеет unknown marker/diagnostic, не retroactive defaults. Не создавать новый snapshot store/AcquireResult type.
5. Verified test files: `tests/unit/remediation/test_scl_03.py`, `tests/unit/scholar/search/test_source_binding.py`, `tests/unit/scholar/test_api_web_bootstrap.py` (существующий full native test). Устаревший fake DNS tuple обновить по actual socket family/type contract, сохранив отдельный прежний FAIL в audit, а не утверждая ретроспективный PASS. Native integration не заканчивается sentinel перед docs publication.

## 6. Локальные различающие проверки

Все TEST — будущие спецификации проверок, не заявления о существующих тестовых функциях. Сначала расширять перечисленные реальные test owners; новый файл — только при отсутствии подходящего owner.

### TEST-SCL-03-01 — native normalization→acquire / NOT_RUN
- **Setup:** Реальный bytes SourceSpec с selected nondefault ArtifactRef и props/hash/size; actual CAS. Контроль manual bytes без ref.
- **Действие:** Нормализовать через discover/manual.py и вызвать whole orchestrator; между API preflight и acquisition отказать selected read/подменить bytes в owned fixture.
- **Oracle:** Ref/profile preserved точно; actual selected get_manifest/get_bytes вызываются и отказ блокирует docs ingest. Direct и whole route согласованы. Manual bytes остаются допустимы.
- **Ожидаемый исход:** Old ref-loss reproducer различающий; positive normal/manual paths.
- **Doubles / граница:** Controlled denial own-store allowed; CAS binding/normalizer/acquire реальные, не compare DTO alone.
- **REQ:** REQ-SCL-03-01, REQ-SCL-03-04.

### TEST-SCL-03-02 — native source version lineage / NOT_RUN
- **Setup:** Search raw v1 с exact snapshot; URL transport теперь v2; public API cache hit/miss.
- **Действие:** Enrich v1 twice, затем explicit refresh v2.
- **Oracle:** Первые два enrich читают v1 без fetch; refresh получает v2 один раз и связывает parentv1; v1 immutable доступен. No snippet reconstruction или silent URL path.
- **Ожидаемый исход:** Positive useful persisted source handoff.
- **Doubles / граница:** Local deterministic HTTP endpoint допустим; API/cache/normalizer/orchestrator реальные.
- **REQ:** REQ-SCL-03-01, REQ-SCL-03-03.

### TEST-SCL-03-03 — native actual producer→metadata / NOT_RUN
- **Setup:** Nondefault domain/MIME/timeout3/UA/maxbytes4096, no-cache и cache routes; реальные normalized constraints.
- **Действие:** Actual fetch_open_page, cache JSON reload, SourceMetadata, _seed_sources_from_web_bundle.
- **Oracle:** Каждое profile field равно реально переданному transport argument; byte_size=len(raw) в обоих routes; seed retains same profile; no manually populated FETCH_PROFILE. Legacy{} явно unknown.
- **Ожидаемый исход:** Old actual producer{} должен нарушить oracle; second compatible profile проходит без branch.
- **Doubles / граница:** Fake response допустим; не fake FetchResult/profile producer.
- **REQ:** REQ-SCL-03-02.

### TEST-SCL-03-04 — native API→CAS→docs/claims→fresh reader / NOT_RUN
- **Setup:** Existing full bootstrap tiny corpus; native FileSystemCAS и настоящий docs pipeline, выбранный manifest profile, exact snippets; output root новый.
- **Действие:** Исполнить full enrich, закрыть process objects и прочитать published document/fragments/claims через actual reader; missing/corrupt blob variant.
- **Oracle:** Fresh artifacts имеют input lineage к exact rawv1/v2; fragments offsets/content связаны с bytes; no capture/sentinel до публикации. Invalid selected source не становится valid knowledge bundle; остальные законные docs сохраняются.
- **Ожидаемый исход:** Положительный полный downstream путь; scientific truth и whole corpus completeness не заявляются.
- **Doubles / граница:** Контролируемая сеть/model extraction при declared scope разрешены; fake CAS/manifest publication/docs ingest запрещены.
- **REQ:** REQ-SCL-03-03, REQ-SCL-03-04.

### TEST-SCL-03-05 — native policy and span boundaries / NOT_RUN
- **Setup:** Каждый snippet tampered separately, mismatched manifest/profile, denied selected view, MIME/byte/maxdocs limits, explicit rights unknown.
- **Действие:** Выполнить public source binding и actual enrich with limits.
- **Oracle:** All-snippet validation отказывает на любом mismatch, не только первом; maxdocs1→1doc и totalbytes1→0doc с точной причиной; rights unknown не объявлены разрешением. Valid independent docs остаются полезны.
- **Ожидаемый исход:** Positive exact span и partial independent work плюс targeted refusals.
- **Doubles / граница:** Не invent license/authority; applicable policy witness конкретный, иначе qualify stronger claim.
- **REQ:** REQ-SCL-03-04.

## 7. Общий сценарий, зависимости и ownership
**E02-I09-A**: Scholar→raw snapshot→snippet→docs ingest. SCL-01 владеет shared transport/cache admission/deadline; SCL-03 — effective profile producer wiring и selected-ref handoff. `src/polisyos/scholar/search/fetcher.py` общий: один writer, согласованная последовательность, не два несовместимых cache predicates. SCL-03 интегрировать после SCL-01. Native CAS и docs-ingest контракты читаются у существующих owners, не создаётся второй store. [Канонический сценарий LANE-09](../03_Интеграция/LANE-09.md). CP2 — окно связанной приёмки, не новый runtime gate.

## 8. Совместимость, история и rollback
Old cache/SourceMetadata remain readable с unknown profile. Existing refs/bytes/history не переписываются; новое поле заполняется вперёд. На missing selected view affected source даёт gap; independent documents остаются. Rollback new profile producer не снимает rawref recheck или включает hidden fetch; stronger cached admission остаётся qualified.

## 9. Free-grow/design alignment
[Vision §3,§7](../05_Основания/Архитектура/universal-policy-design-system-vision-and-organizing-rules.md) — reuse owners и действительный downstream. [Custody/time model](../05_Основания/Архитектура/policy-design-custody-time-model.md) — выбранная версия и её время отдельно от current reuse. Хеш не scientific truth и не license; unknown rights ограничивает claim, не требует нового универсального правового движка. Новый compatible URL проходит общий transport/snapshot handoff.

## 10. Приёмка и пределы PASS
Предъявить normalization-ref regression, real producer profile values, native full published docs/fresh reader evidence и explicitv2 lineage; all-snippet/limits controls. Fixture CAS/AST node execution и old capture-to-docs ingest не native closure; existing test presence не PASS. Не объявлять public-web универсальным reuse grant или snippets полным документом.

Для каждого TEST: actual command/runtime/commit, exit/log, input hashes, assertions и список doubles. Новые tests NOT_RUN до исполнения. Адаптируемый шаблон `<supported-python> -m pytest <verified test paths>` из `policy-engine/`; runner/dependencies здесь не объявлены доступными. Не устанавливать зависимости как часть этого задания на документы.


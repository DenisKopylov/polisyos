# SCL-03 — точный snapshot между search и enrichment
## C105 · LANE-09 · LA-025 · сохранить LK09 и LK20

**Решение: частично подтверждено, не закрыто.** Bootstrap больше не обязан превращать найденный документ обратно в URL: actual API проверяет сохранённый raw snapshot и создаёт bytes seed. Подтверждено использование v1 без второго fetch и явного v2 с новой lineage. Но normalizer удаляет selected raw reference перед acquisition recheck, а actual search-fetch producer не заполняет effective fetch profile.

Срез `20d9009be21097bfbdc38a546a15cc60213b8ace`. **6 MATCH + 1 PARTIAL; 14 неизменённых test bodies / cases: 13 PASS и 1 FAIL.** Bounded цепочка доведена до вызова docs-ingest, но не до настоящих docs/claims или native CAS publication. **105/127**, далее LLM-01.

## 1. Две оси и исходная матрица

| Ось / ID | Подтверждённое | Незакрытое |
|---|---|---|
| Исходный ремонт LA-025 | Cache сохраняет raw ref; SourceMetadata переносит ref/digest/license/lineage; API перепроверяет manifest/content/spans и читает точные bytes вместо URL-only seed. Missing/denied/mismatched snapshot даёт gap без reconstruction из snippets. | C105-R01: selected ref теряется в следующем normalizer; C105-R02: effective profile не рождается в actual producer. |
| Содержательная способность | Actual service → cache → API source-binding → bytes seed → normalization → orchestrator → docs-ingest получает v1, затем cached v1, затем явно refreshed v2. Provider snippet не заменяет документ. | Полная обработка fragments/claims и свежий native CAS reader не исполнены; данные опыта синтетические, не научное подтверждение. |
| LK09 | Search, discover и enrichment остаются разными стадиями; live user URL сохраняет общий raw adapter. | Не сливать поддеревья и не строить новый store ради handoff. |
| LK20 | Hash, selected manifest и exact span проверяются отдельно; неизвестный legacy profile имеет warning. | Идентичность bytes не доказывает актуальное разрешение reuse, лицензионные права или полноту корпуса. |

LLM остаётся semantic proposer. Здесь проверяется реальная передача и допустимость материала в существующей цепочке, а не способность детерминированного кода самостоятельно изобретать универсальную модель.

## 2. Фактическая цепочка

1. Search cache записывает полный payload и получает typed raw `ArtifactRef`; metadata builder переносит его, digest, byte_size, license и lineage [S05; S06; S08].
2. Public API сначала вызывает `validate_web_evidence_source_binding(require_all_sources=True)`. Он проверяет наличие raw artifact, selected/default manifest, digest/size, kind/schema/producer/profile, заново извлекает текст и сравнивает **каждый** snippet с точным substring. Это не shape-only gate [S01:64–93; S04].
3. Converter читает selected bytes, сверяет digest/identity/size и создаёт `SourceSpec(kind="bytes")`. Metadata включает URL, source ID и profile; raw ref проходит отдельным typed полем. Missing raw не заменяется live URL или search snippets [S01:232–410].
4. Orchestrator сначала нормализует seeds, затем выбирает `_acquire_bytes`, а не `fetch_url`. В bytes acquisition предусмотрена повторная проверка selected view, но normalizer не сохраняет поле, которое активирует её [S02:175–215,526–544; S03:91–101].
5. Отдельный `web_evidence` payload сохраняет исходный raw ref. Поэтому R01 не означает, что вся provenance исчезла: дефект относится к admission edge между normalization и acquire [S02:437–490].

## 3. Что реально выполнено

| ID | Результат и граница |
|---|---|
| P01 | 9 unchanged SCL-03 bodies: 8 PASS / 1 FAIL. Exact v1, explicit v2 lineage, missing/denied/digest gap и cache retention подтверждены с fixture store. FAIL — старый fake DNS tuple без TCP family/type, raw assertion не достигнут. |
| P02 | 5 unchanged source-binding bodies PASS: каждый snippet, missing CAS, неправильный manifest contract, выбранный nondefault view и warning для legacy default. Первые 2 tests с дополнительным Scientist verifier не исполнялись. |
| P03 | Selected seed сохраняет ref до normalization и теряет после. Direct acquire того же seed отказывает при own-fixture denial; whole orchestrator доходит до docs-ingest без selected store reads. Per-doc byte limit продолжает отказывать. |
| P04 | Actual raw fetch с явно заданными domain/MIME/timeout/UA/size параметрами создаёт profile `{}`. Пустой profile проходит через cache, SourceMetadata и API seed. |
| P05 | Отдельный current-contract DNS control сохраняет seed raw bytes, MIME и license. Это не ретроспективное исправление existing FAIL. |
| P06 | Actual public цепочка до docs-ingest: miss v1, hit v1 без нового raw call, явный ttl=0 refresh v2. На 3 enrich попытки — 2 fake transport calls; v1 остаётся доступен, v2 связан с ним lineage. |
| P07 | Direct selected-ref positive; actual max_docs=1 оставляет 1 источник; max_bytes_total=1 оставляет 0 acquired docs с точной причиной остановки. Exact span принимается, выдуманный текст отвергается. |

[Диагностика](../04_Проверки/C105_SCL03/bounded_diagnostics.json) · [команды](../04_Проверки/C105_SCL03/commands.json) · [existing tests](../04_Проверки/C105_SCL03/probe_scl03.py) · [остатки](../04_Проверки/C105_SCL03/probe_boundaries.py) · [public chain](../04_Проверки/C105_SCL03/probe_chain.py) · [admission controls](../04_Проверки/C105_SCL03/probe_admission_controls.py).

## 4. Подтверждённые остатки

### C105-R01 — selected reference удаляется перед предназначенной перепроверкой

Bytes normalizer создаёт новый `SourceSpec` с data/props/license и `bytes.sha256_...` locator, но без `raw_artifact_ref` [S03:91–101](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scholar/discover/manual.py#L91-L101). В `_acquire_bytes` selected-view recheck включается только при наличии этого поля [S02:175–215](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scholar/orchestrator/enrich.py#L175-L215).

P03 различает два actual пути на одном seed: direct acquire видит selected reference и отказывает при контролируемом отказе нашего fixture store; whole orchestrator после normalization не обращается к selected store и передаёт те же bytes в docs-ingest. P06 подтверждает отсутствие ref в actual acquire seed после public API bootstrap, хотя web source сохраняет её.

**Оставшаяся работа:** сохранить existing selected reference и согласованную identity через bytes normalization, довести её до предусмотренной acquisition проверки. Сохранить API preflight, digest/size checks, обычные manual bytes и web_evidence provenance. Не вводить новый store и не заменять profile одним hash. Этот опыт не доказывает native permission exploit, изменение raw bytes или глобальную утрату lineage; исходный API gate остаётся полезным и действующим.

### C105-R02 — поле fetch profile переносится, но actual producer оставляет его пустым

FetchResult создаётся без effective request profile [S07:74–98](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scholar/search/fetcher.py#L74-L98). Cache и metadata builder честно копируют пустой словарь; converter сериализует его как `{}`. P04 прослеживает это при nondefault allowed/blocked domains, text/plain, timeout 3, max_bytes 4096 и отдельном user-agent.

Existing SCL-03 tests задают `FETCH_PROFILE` вручную. Они полезно доказывают перенос уже имеющегося контекста, но не подключение реального producer. P06 также получает пустой profile в реальной сервисной композиции с fixture transport.

**Оставшаяся работа:** заполнять существующее поле фактически применённым контекстом на producer boundary, сохранять его через handoff и честно различать неизвестный исторический профиль. Минимальный состав и правила reuse согласовать с существующим owner; profile не становится лицензией, не даёт автоматическое право повторного использования и не требует новой бумажной архитектуры.

## 5. Сохранить и доквалифицировать

Сохранить exact snapshot вместо второго URL-fetch, public source-binding gate, selected manifest contract, all-snippet checking, отсутствие reconstruction из fragments, явную refresh lineage, неизменность v1 и действующие document/byte limits. Ordinary user URL и local/bytes sources остаются допустимыми разными входами.

**C105-G01.** FileFixtureCAS — явно конечный filesystem test double. Он использует actual manifest DTOs, `ManifestLifecycle.build` и profile digest, но не native ownership, signatures, atomic publication или транзакции. API/orchestrator исполнялись как unchanged non-import AST nodes; imports тяжёлых backends исключены. Whole orchestrator остановлен capture/sentinel до document publication. Поэтому не заявлены настоящие fragments/claims или опубликованный knowledge bundle.

Native API/orchestrator imports BLOCKED на Python3.14 CAS syntax в Python3.12.14; pytest отсутствует. Полный existing HTTP→native CAS→full enrich→fresh-reader test прочитан [S16:624–865], но не запускался. Его наличие не является execution evidence. Current fake DNS control отдельно от сохранённого FAIL; весь пакет не объявлен зелёным.

Нужно квалифицировать полный поддерживаемый маршрут, текущие access/license/reuse правила и оба исправления. `public-web` — metadata, не универсальное разрешение. Содержательная достоверность статьи, corpus completeness и научная валидность остаются отдельными вопросами, не закрытыми byte identity или return code.

[Исходная карточка](../05_Источники/SCL-03_исходные_строки.txt) · [pinned источники](../05_Источники/C105_источники.json) · [реестр остатков](../01_Реестры/C105_остатки.json) · [точные границы](../04_Проверки/C105_SCL03/Чтение_и_границы.md).

**105/127 — промежуточный аудит. Следующий LLM-01. Фаза заданий исполнителю не начата.**

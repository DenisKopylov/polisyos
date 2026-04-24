# E2.9 (Phase 17) — Lex NormPack assembly v1.0: сборка применимых NormPack из корпуса/claims (IR‑контракт)

Repo snapshot date: 2026-02-04

## 0) Цель фазы

Lex получает способность собрать **применимый** `NormPack` (IR‑контракт из `polisyos.ir.norm_pack`) для заданного `LegalContext` / `NormPackBuildRequest`:

- `jurisdiction` (обяз.)
- `as_of` дата/время (обяз., ISO)
- `domain/topic` (опц., MVP = простая фильтрация)

**Источники норм**:

1. **Legal corpus** (Phase 16 / E2.8): `DocMeta` + `ProvisionIndexV1` (провижены как `doc.fragment`).
2. **Claims** из этих provisions через уже существующий claims write‑path (Phase 13 / E2.6).
3. **Trust + conflict resolution** (Phase 14): `detect_conflicts`/`resolve_conflicts` из `polisyos.fabric.claims`.

**Результат**:

- CAS артефакт `NormPack` (content‑addressed)
- `WorldEvent(kind=assemble_norm_pack)`
- world facts минимум: **artifact node** для NormPack + **PROV edges** через событие (и, опционально, дополнительные доменные edges).

> Важно: Phase 17 не вводит отдельное хранилище Lex. Всё хранится как CAS артефакты + факты/события в Fabric World Graph.

---

## 1) Контекст репозитория (что уже есть)

### 1.1. Lex Corpus (Phase 16 / E2.8)

Существующие контрактные артефакты и API:

- `lex.corpus.provision_index` (`polisyos.lex.corpus.ProvisionIndex`, v1.0)
  - файл: `policy-engine/src/polisyos/lex/corpus/index.py`
  - строится в `build_legal_structure(...)` и сохраняет список provisions:
    - `fragment_id` (WorldID `frag.sha256_...`)
    - `anchor_path` + offsets (python slice semantics)
    - `props["lex_kind"]` (article/point/...)
- `lex.corpus.version_index` (`polisyos.lex.corpus.VersionIndex`, v1.0)
  - файл: `policy-engine/src/polisyos/lex/corpus/versioning.py`
  - selection policy уже задана в Lex (`lex.versioning_v1.effective_range_then_published_at`)
- `resolve_active_version(...)` — детерминированный выбор активной версии по `as_of` (date semantics)

World Graph уже используется Lex’ом:

- world nodes (`doc.source`, `doc.version`, `doc.fragment`) + edges (`doc.has_version`, `doc.has_fragment`)
- world events (`fetch_doc`, `structure_doc`, `validate`, …)

### 1.2. Fabric Claims (Phase 13 / E2.6)

Существующий write‑path:

- `extract_claims_from_doc(...)` (chunks → claims)
- `normalize_claims(...)`
- `detect_conflicts(...)`, `resolve_conflicts(...)`

Claims — это IR контракты `polisyos.ir.world.claim.Claim`, сохраняемые как `fabric.world.claim`, и индексируемые в world projections (`world.claims`, `world.claim_citations`, …).

### 1.3. IR NormPack (Phase 3)

Контракт NormPack уже существует:

- `policy-engine/src/polisyos/ir/norm_pack.py`:
  - `NormPack(pack_id, jurisdiction, effective_date, norms[], metadata)`
  - `NormRule(norm_id, provision_refs[], rule_type, description, applicability, backend_metadata, …)`
  - `NormRef(provision_id, citations[])` (в MVP `provision_id` может быть `fragment_id`)

---

## 2) Scope и Deliverables (код/док)

### 2.1. Новый пакет Lex NormPack assembly (Phase 17)

Новый пакет (рекомендуемое размещение):

```text
policy-engine/src/polisyos/lex/normpack/
  __init__.py
  policies.py
  select_sources.py
  extract_norm_claims.py
  applicability.py
  assemble_pack.py
```

Тесты:

```text
policy-engine/tests/fabric/test_normpack_phase17.py
```

Док:

```text
policy-engine/docs/contracts/E2_9_LEX_NORMPACK_ASSEMBLY_V1_0.md
```

### 2.2. Поддерживающие изменения вне deliverables (обязательны для MVP)

Чтобы соблюсти требование “отдельный extractor_id” и корректный trust scoring:

1. **Добавить extractor** в `polisyos.fabric.claims.backends`:

- новый backend файл (пример):
  - `policy-engine/src/polisyos/fabric/claims/backends/lex_norm_regex_v1.py`
- регистрация в `_EXTRACTOR_REGISTRY`:
  - ключ: `"lex.norm_extractor.regex_v1"`

1. **Добавить extractor reliability** в conflict policy:

- `policy-engine/src/polisyos/fabric/claims/conflicts/policies.py`
  - `extractor_reliability["lex.norm_extractor.regex_v1"] = Decimal("0.80")` (или другое значение, см. §9.3)

1. (Опционально) Экспортировать high‑level API из `polisyos.lex.api`:

- `assemble_norm_pack(...)` как facade над `polisyos.lex.normpack.assemble_pack`.

---

## 3) Входной контракт (MVP): `NormPackBuildRequest`

### 3.1. Где хранить

Добавить в `policy-engine/src/polisyos/lex/types.py`:

- `NormPackBudgets`
- `NormPackBuildRequest`
- `NormPackBuildResult` (выходной контракт)

> Важно: `lex/types.py` уже является местом для публичных контрактов Lex (Phase 16).

### 3.2. Поля и семантика

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class NormPackBudgets:
    max_docs: int | None = None
    max_provisions: int | None = None
    max_claims: int | None = None

@dataclass(frozen=True)
class NormPackBuildRequest:
    jurisdiction: str
    as_of: str                      # ISO date/datetime
    domain: str | None = None
    doc_source_ids: list[str] | None = None  # manual whitelist; None => "все в corpus"

    selection_policy_id: str = "lex.versioning_v1.effective_range_then_published_at"
    conflict_policy_id: str = "policy.conflicts.default_v1"
    trust_policy_id: str = "policy.trust.default_v1"  # MVP: informational/metadata-only

    budgets: NormPackBudgets = NormPackBudgets()
```

#### Нормализация (обязательная, для детерминизма)

На входе сборки:

- `jurisdiction_norm = jurisdiction.strip().casefold()`
  - **требование**: `jurisdiction_norm` должен соответствовать `ID_PATTERN` (`^[a-z][a-z0-9_.-]*$`).
- `as_of_norm = normalize_as_of(as_of)`
  - принимает `YYYY-MM-DD` или `datetime ISO`, возвращает `YYYY-MM-DD`
  - семантика Phase 17 = “date_inclusive” (как в `lex.corpus.versioning.resolve_active_version`)
- `domain_norm = domain.strip().casefold()` или `None`
  - **требование**: если не `None`, должен соответствовать `ID_PATTERN`.
- `doc_source_ids`:
  - если задано: dedup + сортировка (строка сравнения) + валидация `ID_PATTERN`

#### Валидация budgets

Каждое поле budgets:

- `None` = без лимита
- иначе `>= 0`
- `0` допустимо и означает “ничего не выбирать”, но в этом случае сборка должна быть короткой:
  - `max_docs=0` => `selected_doc_versions=[]` => NormPack без норм (или ошибка по policy, см. ниже)
  - `max_provisions=0` => `selected_fragments=[]` => NormPack без норм
  - `max_claims=0` => `claims=[]` => NormPack без норм

Рекомендованный MVP‑policy: **не падать**, а возвращать пустой NormPack + warning.

---

## 4) Выходной контракт (MVP): `NormPackBuildResult`

Рекомендуемая структура (dataclass, frozen):

```python
@dataclass(frozen=True)
class SelectedDocVersion:
    doc_source_id: str
    doc_version_id: str
    doc_meta_artifact_id: str
    selection_policy_id: str
    used_version_index_artifact_id: str | None
    explanation: list[str]

@dataclass(frozen=True)
class NormPackBuildResult:
    request: NormPackBuildRequest
    jurisdiction_norm: str
    as_of_norm: str
    domain_norm: str | None

    selected_doc_versions: list[SelectedDocVersion]
    selected_fragment_ids: list[str]

    claim_set_artifact_ids: list[str]
    norm_claim_ids: list[str]

    conflict_set_ids: list[str]
    conflict_resolution_artifact_ids: list[str]
    trust_assessment_ids: list[str]

    norm_pack_artifact_id: str
    norm_pack_world_id: str

    world_event_id: str
    world_event_artifact_id: str
    world_segment_manifest: FactSegmentManifest

    warnings: list[str] = field(default_factory=list)
```

Принцип: `NormPackBuildResult` должен давать полный “audit trail” входов/выходов без необходимости читать DB.

---

## 5) Пайплайн сборки NormPack (строго по шагам)

Ниже — нормативное описание алгоритма Phase 17. Реализация должна быть максимально механической и детерминированной.

### 5.0. Общие правила детерминизма

Во всех шагах:

- Любой набор id должен быть:
  - `sorted(set(...))` (строковая сортировка)
  - обрезан по budgets **после** сортировки
- Любые списки в payload’ах CAS (claim_set, norm_pack.metadata, …) должны быть отсортированы стабильно.
- Никаких runtime‑полей (timestamps, random ids) внутри payload’а `NormPack` и `NormRule`.
  - runtime/audit информация пишется в `WorldEvent` (это допускает уникальные события на каждый запуск).

### 5.1. Step 1 — Выбор источников (doc sources + versions)

#### 5.1.1. Вход

- `NormPackBuildRequest`
- `cas: FileSystemCAS`
- `fact_log_root: Path`
- (опционально) `db: SimulationDB` — используется только для ускорения query; алгоритм не должен зависеть от наличия DB.

#### 5.1.2. Как получить candidate `doc_source_ids`

1. Если `request.doc_source_ids is not None`:

   - `doc_source_ids = sorted(set(request.doc_source_ids))`
   - дополнительно: фильтруем по `jurisdiction` (см. ниже)

2. Если `request.doc_source_ids is None` (режим “все документы corpus”):

   - MVP‑реализация должна работать без DuckDB, используя fact log:
     - читаем manifests через `polisyos.fabric.world.store.load_world_fact_manifests(fact_log_root)`
     - читаем parquet по колонкам `subject_id,predicate_id,object_value,target_id,tx_time,fact_id` (минимум)
     - собираем все `subject_id`, где `predicate_id == "world.kind"` и `object_value == "doc.source"`
   - Затем применяем фильтр “Lex corpus docs”:
     - Для каждого `doc_source_id` должны существовать версии (`world.rel.doc.has_version`)
     - Для хотя бы одной версии должен существовать DocMeta, где:
       - `meta.props["lex"]["corpus"] == "lex.corpus"` (устанавливается `lex.corpus.ingest_v1`)
     - Если этот фильтр слишком дорог для MVP, допускается “best effort”:
       - отбирать doc_source_id, которые имеют `official_id` и/или `canonical_url` (через projections если есть db)

3. После получения doc_source_ids:

   - сортируем
   - применяем `budgets.max_docs` (если задан)

#### 5.1.3. Фильтрация по jurisdiction

Цель: на вход сборки NormPack попадали только документы соответствующей юрисдикции.

Нормативный MVP‑фильтр:

- Документ считается принадлежащим `request.jurisdiction_norm`, если **active version meta** содержит:
  - `DocMeta.jurisdiction` (case-insensitive) == `request.jurisdiction_norm`, или
  - `DocMeta.props["lex"]["jurisdiction"]` (case-insensitive) == `request.jurisdiction_norm`

Если юрисдикция в DocMeta отсутствует — документ допускается (MVP permissive), но добавляется warning:

- `warning:doc_jurisdiction_missing:<doc_source_id>`

#### 5.1.4. Выбор active version по `as_of`

Алгоритм для каждого `doc_source_id`:

1. **Primary path**: использовать существующий Lex versioning:

   - вызвать `polisyos.lex.api.resolve_active_version(...)`
   - strategy:
     - `ActiveVersionStrategy(fact_log_root=fact_log_root)` (чтобы работало не только по `Path(cas.root).parent`)
   - если вернул `selected_doc_version_id is not None`:
     - принять его
     - сохранить `selected_doc_meta_artifact_id`
     - сохранить `used_version_index_artifact_id`

2. **Fallback path (обязателен)**: если `resolve_active_version` не готов (нет version index pointer):

   - извлечь doc_version_ids из world facts:
     - найти все edge‑facts `predicate_id == world.rel.doc.has_version` для `subject_id==doc_source_id`
   - для каждого doc_version_id найти “latest DocMeta artifact”:
     - взять `world.artifact_id` факты по `subject_id==doc_version_id`
     - выбрать запись с max `(tx_time, fact_id)` (как в `lex.corpus.versioning._latest_object_by_subject`)
   - загрузить DocMeta для каждого кандидата и извлечь temporal поля:
     - `effective_from = meta.props["lex"]["effective_from"]` (строка ISO date/datetime)
     - `effective_to   = meta.props["lex"]["effective_to"]`
     - `published_at   = meta.props["lex"]["published_at"]`
   - применить active selection:
     - `as_of_date = normalize_as_of(as_of)` как `date`
     - candidate active если:
       - `effective_from <= as_of_date` и
       - `effective_to is None or as_of_date <= effective_to`
     - tie-break (должен быть детерминированным и документированным):
       - `effective_from` (desc, None = date.min)
       - `published_at` (desc, None = date.min)
       - `doc_version_id` (asc)
   - если нет активных по effective range:
     - fallback на `published_at <= as_of_date` (tie-break: published_at desc, doc_version_id asc)
   - если нет published candidates:
     - fallback на `(doc_meta_artifact_id, doc_version_id)` в детерминированном порядке (как в `resolve_active_version`)

Выход на Step 1:

- `selected_doc_versions: list[SelectedDocVersion]`
- все списки отсортированы по `doc_source_id`

### 5.2. Step 2 — Выбор provisions (фрагменты/положения)

#### 5.2.1. Предусловия (Lex readiness)

Для каждого выбранного `doc_meta_artifact_id` должно выполняться:

- `DocMeta.normalized_ref != None` (иначе нечего резать по offsets)
- `DocMeta.props["lex"]["provision_index_ref"]` существует

Если provision index отсутствует — это LexNotReadyError:

- “run `polisyos.lex.api.build_legal_structure` for this doc_version”

#### 5.2.2. Загрузка provision index

- `ProvisionIndexV1 = polisyos.lex.corpus.index.load_provision_index(cas, provision_index_ref)`
- validate:
  - `index.doc_version_id == meta.doc_version_id`
  - `index.doc_source_id == meta.doc_source_id`

#### 5.2.3. Domain/topic фильтрация (MVP без ML)

Если `request.domain_norm is None`:

- берем provisions по правилам ниже без дополнительного фильтра

Если `request.domain_norm` задан:

- использовать `polisyos.lex.normpack.policies.DOMAIN_KEYWORDS`:
  - `DOMAIN_KEYWORDS[domain] = [kw1, kw2, ...]` (в lower/casefold)
- provision входит в выборку, если:
  - keyword встречается в `ProvisionEntryV1.citation_label.casefold()`, или
  - keyword встречается в preview текста provision (см. ниже)

Preview текста provision (должен быть детерминированным):

- грузим normalized text один раз на doc_version:
  - `normalized_text = load_json_artifact(cas, meta.normalized_ref)["text"]`
- preview = `normalized_text[offset_start:offset_end]`, затем:
  - collapse whitespace → single spaces
  - `.casefold()`
  - ограничение длины: первые 500–1000 символов (policy)

#### 5.2.4. Какие provision kinds включать (MVP)

В MVP рекомендуем:

- базовый включаемый набор kinds: `{"article", "point", "subpoint"}`
- `paragraph` и `part` включать по policy‑флагам (см. `policies.py`)

#### 5.2.5. Budgets

`budgets.max_provisions` применяется **глобально** после детерминированной сортировки.

Нормативная сортировка provisions:

1. `doc_version_id`
2. `provision.anchor_path`
3. `fragment_id`

> Это устраняет “случайное” влияние порядка документов на то, какие provisions попадут в лимит.

Выход Step 2:

- `selected_fragment_ids: list[str]` (`frag.*`)
  - отсортированы и уникальны
- “provision selection report” (в памяти) для шага 3:
  - для каждого fragment_id: offsets, doc_version_id, provision_key, anchor_path, citation_label, kind

### 5.3. Step 3 — Извлечение нормативных claims из provisions

#### 5.3.1. Требования

- использовать существующий CAS/world write‑path (как в Fabric Claims):
  - `persist_claim`, `emit_claim_facts`, `persist_world_event`, `emit_world_event_facts`, `write_world_fact_segment`
- extractor id должен быть **отдельный** от обычных (например `regex_numeric_v1`):
  - `extractor_id = "lex.norm_extractor.regex_v1"` (Phase 17 ABI)
- каждый claim должен иметь обязательные citations на `doc.fragment` (fragment_id provision’а).

#### 5.3.2. Extractor backend contract

Extractor реализует интерфейс `ClaimExtractorFn` из `polisyos.fabric.claims.backends`:

```python
def extract(
    *,
    ctx: ChunkContext,
    meta: DocMeta,
    normalized_text: str,
    options: ClaimExtractOptions,
) -> list[ClaimCandidate]: ...
```

MVP‑парсер (“regex_v1”) должен быть полностью детерминированным и offline.

Рекомендуемый MVP‑формат внутри provision текста (без LLM):

- строка начинается с `norm:` (или `claim:`), далее:
  - `predicate_id` (ID_PATTERN или строка, приводимая через canonicalize_id)
  - опционально `(subject_text)`
  - затем `=` или `>=`/`<=`/`>`/`<`
  - затем `value` и опционально `[unit]`

Пример (для фикстур и регрессионных тестов):

```text
Стаття 1...
norm: roads.lane_width_min_m >= 3.5 [m]
norm: roads.max_speed_kmh <= 50 [km]
```

#### 5.3.3. Преобразование ClaimCandidate → Claim (Lex‑слой)

Важно: Phase 17 требует `jurisdiction/domain/validity` нормализацию.
Так как `polisyos.fabric.claims.extraction._candidate_to_claim` в Phase 13 не заполняет эти поля,
в Phase 17 преобразование должно жить в `polisyos.lex.normpack.extract_norm_claims`.

Нормативные правила преобразования:

- `predicate_id`:
  - `canonicalize_id(candidate.predicate_id)` (обязателен)
- `subject_id`:
  - если `candidate.subject_id` задан и валиден → использовать
  - иначе использовать стабильный id: `lex.norm` (ID_PATTERN)
  - **запрещено** дефолтить в `doc_source_id` (иначе conflict_key не группирует нормы из разных документов)
- `value_text`:
  - `.strip()`; пусто => candidate drop + warning
- `value_decimal/unit_id`:
  - `unit_id = canonical_unit(...)` (если задан)
  - числовой парсинг:
    - если extractor смог вычислить `value_decimal` → использовать
    - иначе `None` (и это допустимо для definition/boolean норм)
- `citations`:
  - ровно 1 минимальная citation:
    - `minimal_doc_citation(meta, fragment_id=<ctx.fragment_id>)`
  - дополнительные citations допустимы только если они deterministic и не включают runtime props
- `jurisdiction`:
  - `request.jurisdiction_norm`
- `domain`:
  - `request.domain_norm` (может быть None)
- `valid_from/valid_to`:
  - из DocMeta.props["lex"].effective_from/effective_to если доступны
  - конвертация:
    - `YYYY-MM-DD` => `datetime(YYYY,MM,DD, tz=UTC)`
    - datetime ISO => parse to aware datetime in UTC
- `qualifiers`:
  - только стабильные данные, влияющие на конфликт_key и claim_id
  - **запрещено** включать туда runtime counters/trace ids
- `props`:
  - разрешено хранить lex‑метаданные, не влияющие на claim_id:
    - `{"lex": {"provision_key": ..., "anchor_path": ..., "extractor_id": ...}}`
- `confidence`:
  - MVP: фиксированное значение (например `Decimal("0.6")`) или `candidate.confidence`

Далее:

- `claim_id` вычисляется строго через `claim_id_from_payload(...)`
- проверяется `validate_claim_id(claim)`

#### 5.3.4. Dedup + budgets

Дедуп по `claim_id`:

- если дубликат:
  - сохраняем более высокий `confidence`
  - если confidence равен — tie-break по `(predicate_id, value_text, unit_id)` (asc)

`budgets.max_claims`:

- применяется к итоговым deduped claims после сортировки по `claim_id`
- если лимит обрезал список — warning:
  - `warning:max_claims_truncated:<kept>/<total>`

#### 5.3.5. Persist + WorldEvent (claims extract)

Для каждого claim:

- `persist_claim(cas, claim)` → `claim_artifact_id`
- `emit_claim_facts(claim, claim_artifact_id, stable_world_provenance_v1())`

Рекомендуемый claim_set (per doc_version):

- kind: `lex.norms.claim_set` (или `fabric.claims.claim_set`, но с `stage="lex_norm_extract_v1"`)
- payload включает:
  - `extractor_id`
  - `doc_meta_artifact_id`
  - `doc_source_id/doc_version_id`
  - `provision_index_artifact_id`
  - `selected_fragment_ids`
  - `claims[]` (sorted by claim_id; содержит claim_artifact_id)

WorldEvent для шага:

- `event_kind = EventKind.EXTRACT_CLAIMS`
- `agent_id = "prov.agent.lex_norms"`
- `activity_id = "prov.activity.lex_norms.extract"`
- `props.pipeline = "lex.normpack.extract_norm_claims_v1"`
- inputs:
  - doc_meta_artifact_id (artifact)
  - normalized_ref (artifact)
  - provision_index_artifact_id (artifact)
  - selected fragments (world ids)
- outputs:
  - claim_set_artifact_id (artifact)
  - claim ids (world ids)

### 5.4. Step 4 — (Рекомендовано) Нормализация claims

Запускать `polisyos.fabric.claims.normalize_claims(...)` на каждом claim_set.

Зачем:

- canonicalize predicate ids и unit ids
- canonical numeric `value_text`
- построить prov.was_derived_from edges (новый claim -> старый claim)

Важно:

- для дальнейшей сборки NormPack использовать **normalized claim ids**
- сохранять `normalized_claim_set_artifact_ids` в результат

### 5.5. Step 5 — Trust scoring + conflict detection/resolution

Вызов:

```python
resolve_conflicts(
  cas=cas,
  fact_log_root=fact_log_root,
  db=db_or_none,
  conflict_set_ids=None,
  claim_ids=<normalized_claim_ids>,
  claim_set_artifact_ids=<normalized_claim_set_artifact_ids>,
  policy_id=request.conflict_policy_id,
)
```

Результаты Phase 14 используются как есть:

- `ConflictSet` артефакты обновляются с `resolution` (winner_claim_id, confidence, rationale, resolution_artifact_id)
- `TrustAssessment` создаются для:
  - doc versions
  - claims
  - conflict sets

### 5.6. Step 6 — Canonical claims set

Построить множество canonical claims для NormPack:

1. загрузить каждый `ConflictSet` (из `conflict_set_artifact_ids`) и собрать `member_claim_ids`
2. winner claim id = `resolve_result.winner_by_conflict_set[conflict_set_id]`
3. canonical_claim_ids =

   - все winners
   - - все claim_ids, которые не принадлежат ни одному conflict_set
4. canonical_claim_ids сортируем

### 5.7. Step 7 — Преобразование claims → IR NormRule → IR NormPack

#### 5.7.1. Mapping Claim → NormRule (MVP максимально механический)

Для каждого canonical claim:

- `norm_id`:
  - MVP: `norm_id = claim.claim_id` (1:1, детерминированно)
- `rule_type`:
  - MVP default: `RuleType.OBLIGATION`
  - если extractor/props помечает отрицание (`must_not`) — `RuleType.PROHIBITION`
- `description`:
  - стабильная строка, например:
    - `"{predicate_id} {value_text} [{unit_id}]"` (unit_id опционален)
- `provision_refs`:
  - для каждой citation с `fragment_id`:
    - `NormRef(provision_id=<fragment_id>, citations=[citation])`
  - сортировка provision_refs по `provision_id`
- `applicability`:
  - минимум:
    - `jurisdiction.any_of=[request.jurisdiction_norm]`
    - `time.valid_from/valid_to` из claim.valid_from/valid_to (если есть; в ISO)
  - всё остальное пусто (MVP)
- `backend_metadata`:
  - обязательно фиксировать:
    - `predicate_id`
    - `value_text`, `value_decimal`, `unit_id`
    - `source_claim_id`
    - `conflict_set_id` (если claim был winner’ом какого-то conflict_set)
    - `trust_score`/`trust_tier` (из TrustAssessment, если найден)
    - `extractor_id` (если доступен из claim_set payload)

#### 5.7.2. Sorting NormRules (deterministic)

Так как `NormRule` не содержит `predicate_id` как отдельное поле, сортировку определяем на этапе сборки:

- `rule_sort_key = (claim.predicate_id, applicability_key, norm_id)`

Где `applicability_key` — детерминированный ключ:

- `sha256(canonical_json(NormRule.applicability.model_dump()))[:32]` (hex string)

#### 5.7.3. NormPack payload

Поля:

- `jurisdiction = request.jurisdiction_norm`
- `effective_date = request.as_of_norm` (YYYY-MM-DD)
- `norms = sorted NormRules`
- `pack_id`:
  - детерминированный id, зависящий от:
    - normalized request (jurisdiction/as_of/domain)
    - selection_policy_id/conflict_policy_id/trust_policy_id
    - списка `selected_doc_version_ids` (sorted)
    - списка `canonical_claim_ids` (sorted)
    - версий алгоритмов (extractor_id + conflict resolver versions)
  - рекомендуется вычислять через `stable_world_id_from_canon(prefix="normpack", payload=...)`
- `metadata` (обязательно, deterministic):
  - `selection_policy_id`
  - `conflict_policy_id`
  - `trust_policy_id`
  - `domain` (если задан)
  - `source_doc_version_ids` (sorted)
  - `source_doc_source_ids` (sorted)
  - `source_fragment_ids` (sorted, может быть truncated по budgets)
  - `algorithm_versions`:
    - `norm_claim_extractor_id`
    - `claims_normalize_version` (если применялось)
    - `conflict_trust_algorithm_version`
    - `conflict_resolution_algorithm_version`
  - `budgets` + `actual_counts`
  - `warnings` (sorted)

### 5.8. Step 8 — Persist NormPack + WorldEvent(kind=assemble_norm_pack)

#### 5.8.1. Persist NormPack (CAS)

Нормативный kind:

- `lex.norm_pack` (рекомендуется)

SchemaInfo:

- `SchemaInfo(name="polisyos.ir.NormPack", version="1.0")` (или эквивалент, но фиксировать в коде)

Inputs (PutOptions.inputs):

- включить артефакты, от которых NormPack был derived:
  - provision_index_artifact_ids
  - claim_set_artifact_ids (extract + normalize)
  - conflict_resolution_artifact_ids
  - trust_assessment_artifact_ids (опционально, но полезно)

#### 5.8.2. World facts (минимум)

Semantic facts (stable provenance):

- создать world node для NormPack как artifact node:
  - `norm_pack_world_id = artifact_id_to_world_id(prefix="artifact", artifact_id=norm_pack_artifact_id)`
  - facts:
    - `world.kind="artifact"`
    - `world.artifact_id="<sha256:...>"`

#### 5.8.3. WorldEvent: assemble_norm_pack

WorldEvent:

- `event_kind = EventKind.ASSEMBLE_NORM_PACK`
- `agent_id = "prov.agent.lex_normpack"`
- `activity_id = "prov.activity.lex_normpack.assemble"`
- `activity_type = ProvActivityType.ASSEMBLE_NORM_PACK`
- `props` включает:
  - pipeline id/version: `"lex.normpack.assembly_v1"`
  - normalized request fields
  - ids политик
  - counts (docs/provisions/claims/conflicts/rules)

Event inputs (WorldObjectRef):

- selected doc versions (world ids)
- selected fragments (world ids)
- norm claim ids (world ids)
- conflict_set ids (world ids)
- trust assessment ids (world ids)
- claim_set artifacts / provision_index artifacts / resolution artifacts (artifact ids)

Event outputs:

- `WorldObjectRef(world_id=norm_pack_world_id)`
- (опционально) conflict_set ids (world ids) как “secondary outputs”

Пишем event артефакт через `persist_world_event`, факты через `emit_world_event_facts(..., event_world_provenance_v1(event_id))`.

#### 5.8.4. Segment write

Факты Phase 17 пишутся в world fact log:

- `write_world_fact_segment(facts, fact_log_root, segment_name="lex_normpack_assemble_<suffix>")`
- `append_world_segment_index(manifest, fact_log_root)`

---

## 6) Идемпотентность и воспроизводимость

### 6.1. Что должно быть идемпотентным

При повторной сборке с тем же request и тем же входным подграфом:

- `norm_pack_artifact_id` должен совпадать (CAS = content‑addressed)
- `pack_id` внутри NormPack должен совпадать (если payload deterministic)
- набор `norm_id` должен совпадать
- сортировка NormRules должна совпадать

### 6.2. Что может быть неидемпотентным (audit)

- `WorldEvent` может создаваться заново (новый event_id), т.к. включает `started_at/ended_at`.
- audit facts (PROV edges) могут добавляться.

Важно: semantic facts должны использовать `stable_world_provenance_v1()` (как в Phase 13/16), чтобы повторное эмитирование не плодило новые `fact_id` для тех же утверждений.

---

## 7) Файлы Phase 17 (функции модулей + связи)

### 7.1. `polisyos/lex/normpack/policies.py`

Содержит:

- константы ids:
  - `DEFAULT_SELECTION_POLICY_ID`
  - `DEFAULT_CONFLICT_POLICY_ID`
  - `DEFAULT_TRUST_POLICY_ID` (MVP informational)
  - `DEFAULT_EXTRACTOR_ID = "lex.norm_extractor.regex_v1"`
  - `NORM_PACK_KIND = "lex.norm_pack"`
- domain filters:
  - `DOMAIN_KEYWORDS: dict[str, list[str]]`
  - `DEFAULT_INCLUDED_PROVISION_KINDS: set[str]`
- версии алгоритмов:
  - `ASSEMBLY_PIPELINE_ID = "lex.normpack.assembly_v1"`
  - `NORM_CLAIM_EXTRACT_PIPELINE_ID = "lex.normpack.extract_norm_claims_v1"`

### 7.2. `polisyos/lex/normpack/select_sources.py`

Содержит:

- `normalize_as_of(...)` (ISO → date)
- `select_doc_sources(...)`:
  - реализует Step 1.2 (all docs vs whitelist)
- `select_active_doc_versions(...)`:
  - реализует Step 1.4 (primary resolve_active_version + fallback)
- output type `SelectedDocVersion` (или импорт из lex.types)

### 7.3. `polisyos/lex/normpack/extract_norm_claims.py`

Содержит:

- преобразование provision → ChunkContext
- запуск extractor backend (get_extractor)
- conversion ClaimCandidate → Claim (с jurisdiction/domain/validity)
- persist claims + emit facts
- persist claim_set per doc_version (extract stage)
- опционально: запуск normalize_claims
- возвращает:
  - claim_set_artifact_ids
  - claim_ids (raw + normalized)
  - event ids + segment manifests (если делаем отдельные events)

### 7.4. `polisyos/lex/normpack/applicability.py`

Содержит:

- `build_norm_applicability(...)`:
  - `NormApplicability(jurisdiction.any_of=[...], time window from claim, …)`
- `applicability_key(...)`:
  - стабильный hash key для сортировки
- (опционально) `applies_to_context(...)`:
  - MVP: проверка jurisdiction + time window

### 7.5. `polisyos/lex/normpack/assemble_pack.py`

Содержит:

- `assemble_norm_pack(...)` — end‑to‑end orchestrator:
  - Step 1–8
- `claims_to_norm_rules(...)`:
  - mapping + sorting (Step 7)
- `persist_norm_pack(...)`:
  - CAS put_json + inputs
- `emit_norm_pack_world_facts(...)`:
  - artifact node facts (stable provenance)
- `emit_norm_pack_assemble_event(...)`:
  - WorldEvent(kind=assemble_norm_pack) + facts + segment

### 7.6. `polisyos/lex/normpack/__init__.py`

Публичный фасад:

- re-export `NormPackBuildRequest/Result` + `assemble_norm_pack` (или `build_norm_pack`)

---

## 8) Тесты (обязательные): `test_normpack_phase17.py`

Размещение: `policy-engine/tests/fabric/test_normpack_phase17.py`

### 8.1. Unit тесты

1. **Deterministic mapping Claim → NormRule**

- одинаковый входной Claim (одинаковые поля, включая citations) должен давать одинаковый `NormRule.model_dump()`.
- проверяем:
  - norm_id стабильный (например = claim_id)
  - provision_refs стабильно отсортированы
  - backend_metadata не содержит runtime полей

1. **Sorting deterministic**

- собрать 3–5 claims в разном порядке
- убедиться, что правила в NormPack отсортированы одинаково (по predicate/applicability/norm_id)

### 8.2. Integration тест (end‑to‑end)

Фикстура:

- 2 legal docs одной юрисдикции (`UA:LAW-A`, `UA:LAW-B`), обе structured (Phase 16)
- внутри provisions содержатся `norm:` строки, извлекаемые regex extractor’ом
- одна пара норм конфликтует (например, `roads.max_speed_kmh <= 50` vs `<= 60`)

Шаги:

1. `ingest_legal_doc_bytes` для каждой версии
2. `build_legal_structure` для каждой
3. `build_version_index` (опционально; либо тестировать fallback selection)
4. `assemble_norm_pack` для `jurisdiction="ua", as_of="2025-06-01", domain="roads"`
5. `materialize_world_duckdb_from_fact_log(tmp_path, db, cas)`

Assert:

- NormPack artifact существует в CAS:
  - `cas.has(ArtifactID(norm_pack_artifact_id)) == True`
- `world.world_events` содержит событие:
  - `event_kind == 'assemble_norm_pack'` (или activity_id == `prov.activity.lex_normpack.assemble`)
- citations в NormRules указывают на существующие `doc.fragment` ids:
  - для каждого `CitationRef.fragment_id` проверить наличие в `world.doc_fragments`
- при конфликте выбирается winner детерминированно:
  - повторная сборка с тем же input subgraph даёт тот же `norm_pack_artifact_id`
  - winner claim id стабилен (например, меньший/больший по score; tie-break = lexicographic claim_id)

---

## 9) Полиси, значения по умолчанию и расширяемость

### 9.1. Selection policy

По умолчанию:

- `lex.versioning_v1.effective_range_then_published_at` (уже используется Phase 16)

Phase 17 обязана:

- сохранять `selection_policy_id` в NormPack.metadata
- не “угадывать” правила выбора: только строго по policy

### 9.2. Conflict policy

По умолчанию:

- `policy.conflicts.default_v1` (Phase 14)

Phase 17 обязана:

- прокидывать `conflict_policy_id` в `resolve_conflicts(policy_id=...)`
- сохранять policy id/version в NormPack.metadata и в event.props

### 9.3. Trust policy

MVP:

- `trust_policy_id` сохраняется как metadata‑поле (информативно)
- фактический trust scoring выполняется внутри Phase 14 conflict policy

Рекомендуемое расширение (v1.1+):

- разделить “trust_policy_id” и “conflict_policy_id” в Phase 14 API

### 9.4. Domain/topic

MVP:

- `domain` влияет только на выбор provisions (Step 2)
- допускается domain‑список keywords в `policies.py`

В будущем (v2):

- domain может влиять на:
  - подбор predicate registry
  - нормализацию онтологии (subject_id/object selectors)
  - выбор backends для `backend_exprs`

---

## 10) Definition of Done (Phase 17)

Phase 17 считается выполненной, если:

1. Lex может собрать применимый `NormPack` на дату и юрисдикцию из собственного corpus:

   - вход: `NormPackBuildRequest`
   - выход: CAS артефакт `lex.norm_pack` + `WorldEvent(kind=assemble_norm_pack)` + world facts сегмент
2. В сборке используется:

   - выбор активных версий по `as_of`
   - выбор provisions из `lex.corpus.provision_index`
   - извлечение norm claims с обязательными citations на `doc.fragment`
   - conflict resolution (Phase 14) с детерминированным winner
3. Есть обязательные тесты Phase 17 (unit + integration), см. §8.

## D1-L4 Validation Links

| Link type           | Current anchor                                                                                                                                                                    |
| ------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Source plan phase   | D1-L4 Phase 0 norm/citation determinism and Phase 5 governance contract handoff                                                                                                   |
| Contract tests      | `tests/contract/test_applicability_contract.py`, `tests/fabric/test_normpack.py`, `tests/fabric/test_conflicts.py`                                                                |
| Schema snapshots    | `schemas/snapshots/ir/norm_pack.schema.json`, `schemas/snapshots/ir/norm_ref.schema.json`, `schemas/snapshots/ir/norm_rule.schema.json`, `schemas/snapshots/ir/claim.schema.json` |
| Generated reference | [IR Schema Catalog](../reference/ir/schema-catalog.md), [JSON Schema Catalog](../reference/schemas.md)                                                                            |

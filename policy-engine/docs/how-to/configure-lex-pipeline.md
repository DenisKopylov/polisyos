# Настройка Lex pipeline

Related explanation: [Lex Pipeline](../explanation/lex-pipeline.md). Related reference: [Lex](../reference/lex/index.md).
Evidence: `tests/unit/lex/**`, [Lex contracts](../contracts/E2_9_LEX_NORMPACK_ASSEMBLY_V1_0.md), [Lex legal evaluation contract](../contracts/E2_10_LEX_LEGAL_EVALUATION_V1_0.md).

> Эта страница для инженеров и операторов, которым нужно собрать устойчивый Lex ingestion path, а не просто разово вызвать один helper.

## Вход

- сырой корпус legal documents или batch input directories;
- решение, нужен ли вам stage-level API path или control-plane batch path;
- настроенные artifact roots для CAS и provenance/fact logs.

## Выход

- reproducible Lex pipeline path для ingest, structure, versioning и NormPack;
- понимание, какие job ids, artifact ids и world events ожидать на каждом шаге;
- минимальный набор operational checks для локального triage.

## Команды

```bash
cd policy-engine
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops_runners/runtime/check_runtime_api_contract.py
curl -X POST "http://localhost:8000/api/v1/control/lex/trigger" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"cards_path":"data/lex/cards","texts_path":"data/lex/texts","output_dir":".polisyos/lex-out","resume":true,"execution_profile":"research"}'
```

В PolicyOS есть два нормальных способа работать с Lex:

- stage-level Python API из `polisyos.lex.api`, если вы собираете corpus/versioning/normpack pipeline внутри кода;
- control-plane endpoint `POST /api/v1/control/lex/trigger`, если нужен job-based batch запуск с `pipeline_id` и `job_id`.

## Когда использовать какой путь

- Используйте stage-level API, если вам нужны точные артефакты и контроль над `cas`, `fact_log_root`, version selection и `NormPackBuildRequest`.
- Используйте control plane, если важны очереди, `resume`, polling job status и operational visibility через `/api/v1/control/jobs/{job_id}`.

## 1. Подготовьте artifact roots

Для stage-level path заранее определите:

- CAS root для артефактов;
- `fact_log_root` для world events и segment manifests;
- единый `doc_source_id` strategy, чтобы версии закона потом можно было собрать в version index.

Минимальная форма локального setup:

```python
from pathlib import Path

from polisyos.core.artifacts.store import FileSystemCAS

cas = FileSystemCAS(Path(".polisyos/cas"))
fact_log_root = Path(".polisyos/world")
```

## 2. Ingest и structure legal documents

Для корпусного stage path используйте `ingest_legal_doc_bytes()` и затем `build_legal_structure()`:

```python
from polisyos.lex.api import build_legal_structure, ingest_legal_doc_bytes
from polisyos.lex.types import LegalDocSource, LexIngestOptions, LexStructureOptions

source = LegalDocSource(
    canonical_url="https://zakon.rada.gov.ua/laws/show/example",
    license="official-publication",
    jurisdiction="ua",
    language="uk",
    title="Example Act",
)

ingest_result = ingest_legal_doc_bytes(
    cas=cas,
    fact_log_root=fact_log_root,
    source=source,
    raw_bytes=raw_bytes,
    mime="text/html",
    options=LexIngestOptions(run_normalize=True, run_structure=False, run_chunk=False),
)

structure_result = build_legal_structure(
    cas=cas,
    fact_log_root=fact_log_root,
    doc_meta_artifact_id=ingest_result.doc_meta_artifact_id,
    options=LexStructureOptions(jurisdiction="ua"),
)
```

На этом этапе вы уже получаете:

- `doc_meta_artifact_id`
- `fragment_ids`
- `provision_index_artifact_id`
- world event refs / segment manifests

## 3. Соберите version index

Если у документа несколько редакций, следующий обязательный слой для reproducible legal evaluation:

```python
from polisyos.lex.api import build_version_index, resolve_active_version
from polisyos.lex.types import ActiveVersionStrategy, LexVersionIndexOptions

index_result = build_version_index(
    cas=cas,
    fact_log_root=fact_log_root,
    doc_source_id=ingest_result.doc_source_id,
    options=LexVersionIndexOptions(),
)

active = resolve_active_version(
    cas=cas,
    doc_source_id=ingest_result.doc_source_id,
    as_of_iso="2025-01-01",
    strategy=ActiveVersionStrategy(include_candidates=True),
)
```

Это даёт детерминированный answer на вопрос "какая версия закона действовала на дату анализа", вместо случайного выбора document id.

## 4. Соберите `NormPack`

Когда versioning готов, переходите к policy-facing артефакту:

```python
from polisyos.lex.api import assemble_norm_pack
from polisyos.lex.types import NormPackBuildRequest

norm_result = assemble_norm_pack(
    cas=cas,
    fact_log_root=fact_log_root,
    request=NormPackBuildRequest(
        jurisdiction="ua",
        as_of="2025-01-01",
        domain="roads",
    ),
)
```

Ожидаемые ключевые выходы:

- `norm_pack_artifact_id`
- `norm_pack_world_id`
- selected doc versions
- conflict/trust outputs
- `world_event_id` для `assemble_norm_pack`

## 5. Используйте control-plane path, если нужен batch job

Для operator-friendly запуска у runtime есть control endpoint:

```bash
curl -X POST "http://localhost:8000/api/v1/control/lex/trigger" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "cards_path": "data/lex/cards",
    "texts_path": "data/lex/texts",
    "output_dir": ".polisyos/lex-out",
    "stages": {
      "parse": true,
      "structure": true,
      "spo": true,
      "graph": true,
      "embed": false
    },
    "resume": true,
    "execution_profile": "research"
  }'
```

После accepted response работайте с:

- `pipeline_id`
- `job_id`
- `GET /api/v1/control/jobs/{job_id}`
- `GET /api/v1/control/lex/status/{pipeline_id}`

## 6. Настройте quality toggles осознанно

Полезные практические правила:

- отключайте `embed`, если вам нужен быстрый structural smoke run без vector layer;
- включайте `resume=true` только если `output_dir` и предыдущие промежуточные артефакты действительно должны быть reused;
- фиксируйте `execution_profile`, если поведение control plane должно быть воспроизводимым между dev/research/governed paths.

Для stage-level path полезно явно задавать:

- `LexIngestOptions.run_normalize`
- `LexIngestOptions.run_structure`
- `LexIngestOptions.run_chunk`
- `LexStructureOptions.jurisdiction`
- `ActiveVersionStrategy.include_candidates`
- `NormPackBuildRequest.budgets`

## 7. Какие артефакты ожидать

Если pipeline настроен правильно, вы обычно увидите четыре слоя результатов:

- corpus artifacts: raw/normalized/structured document payloads;
- versioning artifacts: version index и active-version explanation;
- policy artifacts: `NormPack` и trust/conflict outputs;
- provenance artifacts: world events и fact segments.

Это важнее, чем один финальный JSON: downstream governance и intervention layers читают именно этот bundle of evidence.

## Откат

- если batch path был запущен с неверным `output_dir` или `execution_profile`,
  остановите дальнейшее переиспользование этих артефактов и перезапустите
  pipeline с корректными параметрами;

- если структура или version index собраны из неверного source payload,
  пересоберите их из корректного ingest input, а не поверх спорного результата;

- если ошибка касается only-docs/operator guidance, откатите workflow к
  последнему verified stage sequence.

## Troubleshooting

- Если stage-level pipeline даёт "правдоподобный, но непонятный" результат,
  проверьте сначала `doc_source_id`, `fact_log_root` и active-version strategy.

- Если control-plane batch не даёт ожидаемых output artifacts, смотрите `job_id`
  и status endpoint отдельно от content-level артефактов.

- Если нужен быстрый structural smoke run, выключите `embed`, чтобы не путать
  Lex structure/debugging с vector-stage задержками.

## Что дальше

- Для operational surface откройте [Use Control Plane](use-control-plane.md)
- Для reason-why behind stage design смотрите [Lex Pipeline explanation](../explanation/lex-pipeline.md)
- Для policy-facing contracts откройте [Lex reference](../reference/lex/index.md)

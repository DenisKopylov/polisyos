# Datasets Knowledge (`polisyos.datasets.knowledge`)

`polisyos.datasets.knowledge` — runtime-слой чтения и аналитики поверх каталога датасетов, собранного batch-пайплайном.

## Роль в системе

Подпакет решает две задачи:

- discovery: быстрый поиск и резолв датасетов (`hybrid search`, metrics lookup, connector params);
- transportability support: выбор источников под канонические переменные, расчет `P*(Z)` и proxy fallback.

## Модульная карта

| Файл | Назначение |
|---|---|
| `types.py` | Pydantic-модели домена: `DatasetRecord`, `DatasetSearchResult`, `DatasetMatch`, `PStarZResult`, и др. |
| `store.py` | Низкоуровневый read-only доступ к DuckDB и HNSW (`DatasetCatalogStore`). |
| `search.py` | Высокоуровневый API поиска (`DatasetCatalogGraph`): hybrid vector+text поиск, metric/variable lookup. |
| `registry.py` | `DatasetRegistry` для подбора датасетов по `canonical_var` и расчета `P*(Z)` / `P*(Z|X=x)`. |
| `variable_alignment.py` | Загрузка seed alignments + deterministic semantic/meta-analytic alignment helpers. |
| `proxy_resolver.py` | Построение proxy chain и validation-checklist для fallback при отсутствии direct data. |

## Контур 1: Dataset Catalog Search

`DatasetCatalogGraph` (`search.py`) строится поверх `DatasetCatalogStore` (`store.py`).

Основные возможности:

- `search_datasets(query, ...)`:
  - text часть: `ILIKE` по title/description;
  - vector часть: cosine KNN по HNSW;
  - итог: weighted merge (`vector_weight` + `text_weight`) и ранжирование.
- fallback на чисто text-поиск, если embedding model недоступна.
- `find_by_polisyos_metric(...)` и `find_by_variables(...)` для deterministic поиска.
- `get_connector_params(dataset_id)` и `get_distributions(dataset_id)` для downstream fetch.

Используемые артефакты:

- DuckDB: `graph/dataset_catalog.duckdb`;
- HNSW + embeddings: `ds_dataset_index.hnsw`, `ds_dataset_embeddings.npz`.

## Контур 2: Dataset Registry и transportability

`DatasetRegistry` (`registry.py`) работает с registry-таблицами в DuckDB:

- `ds_registry_datasets`
- `ds_variable_alignments`
- `ds_observations`

Ключевые операции:

- `find_datasets_for_variable(...)`: ранжирует кандидатов по proxy/non-proxy, coverage и temporal match, confidence.
- `compute_p_star_z(...)`: возвращает point/empirical оценку и `penalty_breakdown` (proxy/temporal/conditional).

`proxy_resolver.py` дополняет этот контур:

- `resolve_proxy(...)`: строит proxy candidates/chain с гармонической композицией confidence;
- `validate_proxy(...)`: 4-condition check (relevance, exclusion, non-collider, completeness).

## Откуда берутся данные для knowledge-слоя

- `graph_load`/`graph_index` (из `datasets.batch`) заполняют `ds_datasets`/`ds_distributions`.
- `embed` формирует vector artifacts для semantic retrieval.
- `core_sources_ingest` заполняет registry/alignments/observations, необходимые для `DatasetRegistry`, и в catalog-driven режиме расширяет transportability coverage за счет execution-core международных источников.
- seed alignments читаются из `data/dataset_catalog/seed_variable_alignments.yaml`.

## Связи с другими директориями

- `polisyos.scientist.agent.knowledge_tools`
  Использует `DatasetCatalogGraph` как typed инструмент для агентного discovery.
- `polisyos.fabric.retrieval.service`
  Использует catalog lane (`find_by_polisyos_metric` + connector params) для resolve/fetch planning.
- `polisyos.scientist.nodes.builtins.causal.resolve_transport`
  Использует `DatasetRegistry`, `resolve_proxy`, `validate_proxy` в цикле transportability.
- `polisyos.ir.analytics`
  Использует proxy/confidence utilities и `PStarZResult` в аналитических контрактах.

## Практические ограничения текущей реализации

- `DatasetCatalogStore` работает в read-only режиме и не управляет пересборкой артефактов.
- Hybrid search требует локально доступного `SentenceTransformer`; при ошибке остается text-only режим.
- `compute_p_star_z` возвращает первое подходящее ранжированное совпадение, а не ансамбль по всем наборам.
- Conditional `P*(Z|X=x)` требует заполненного `condition_json` в `ds_observations`; при отсутствии условий вернется failure penalty.

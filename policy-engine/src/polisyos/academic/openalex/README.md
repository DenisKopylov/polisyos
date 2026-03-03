# Academic OpenAlex

`polisyos.academic.openalex` — слой интеграции с OpenAlex для topic-driven отбора работ, используемый batch стадиями `topic_select` и `article_extract`.

## Роль в системе

Подпакет отвечает за:
- загрузку каталога тем из `relevant_topics_*.csv`;
- rate-limited и retry-safe запросы к OpenAlex `/works`;
- ранжирование и отбор top-N работ на тему с fallback стратегиями;
- lightweight policy-priority фильтрацию для phase-0 extraction.

## Модули

| Модуль | Назначение |
|---|---|
| `topic_catalog.py` | Поиск/парсинг topic CSV в `TopicEntry` |
| `client.py` | Async OpenAlex client (`OpenAlexClient`, `OpenAlexRequest`) |
| `rate_limiter.py` | Sliding-window limiter + global backoff после HTTP 429 |
| `selector.py` | Основной алгоритм topic selection (`select_topic_works`, `select_all_topics`) |
| `priority_filter.py` | TIER1/TIER2 policy relevance фильтр (`should_process`) |

## Алгоритм topic selection (selector.py)

Для каждой темы:
1. выполняются два strict батча:
   `strict_classic` (2000+, citations>10, article, EN) и
   `strict_recent` (2018+, citations>2, article, EN, sort fwci).
2. при недоборе включается fallback ladder:
   - `fallback_citations_relaxed`;
   - `fallback_no_language`;
   - `fallback_with_reviews`.
3. кандидаты дедуплицируются по `work_id`.
4. назначается `selection_score`:
   - 0.30 impact,
   - 0.20 recency,
   - 0.20 method signal,
   - 0.15 content availability,
   - 0.15 transportability signal.
5. применяется diversity policy:
   - не более 5 работ из одного journal;
   - не более 2 работ одного first author;
   - prefill quota на review и recent работы.

Результат сериализуется в `SelectedTopicWork` с provenance полями (`run_id`, `batch_origin`, `rank`, `selection_score`, `topic_*`).

## Retry/rate-limit поведение клиента

- `OpenAlexClient.list_works()` использует:
  - retry на `429` и `5xx`;
  - экспоненциальный backoff;
  - `Retry-After` при наличии;
  - лимит RPS и concurrency через `OpenAlexRateLimiter`.
- `mailto` и `User-Agent` настраиваются через `openalex_email`.

## Связи с batch

- `batch/topic_select.py`:
  `load_topics()` + `select_all_topics()` + запись `topic_selection/*.jsonl`.
- `batch/article_extractor.py`:
  `should_process()` для раннего отсечения нерелевантных работ.

## Конфигурация

Основные параметры приходят из `AcademicBatchConfig`:
- `openalex_email`;
- `openalex_max_rps`;
- `openalex_max_concurrent`;
- `openalex_timeout_seconds`;
- `openalex_max_retries`;
- `openalex_backoff_seconds`;
- `openalex_per_page`.

## Проверки

Релевантные тесты:
- `policy-engine/tests/academic/batch/test_topic_catalog.py`;
- `policy-engine/tests/academic/batch/test_topic_selector.py`;
- `policy-engine/tests/academic/batch/test_openalex_rate_limiter.py`;
- `policy-engine/tests/academic/batch/test_priority_filter.py`.

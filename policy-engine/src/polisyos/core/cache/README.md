# Core Cache

`core.cache` — минимальный общий слой in-memory кэшей для `core` и доменных модулей.
Реализации зависят только от stdlib и безопасны для конкурентного доступа.

## Публичный API

- `Cache[K, V]` — protocol для mutable key/value кэша
- `LRUCache[K, V]`, `LRUCacheStats` — потокобезопасный least-recently-used кэш
- `TTLCache[K, V]`, `TTLCacheStats` — TTL кэш с опциональным LRU-ограничением

## Роль в системе

- Единый кэш-контракт для модулей, где нельзя тянуть внешние зависимости.
- Предсказуемая эвикция (LRU/TTL) для быстрых lookup-paths.
- Легкий переносимый слой для security/observability/runtime-интеграций.

## Ограничения и принципы

- In-process only: не предназначен как распределенный cache.
- Без persistence: после рестарта состояние не сохраняется.
- Потокобезопасность обеспечивается внутренним `RLock`.

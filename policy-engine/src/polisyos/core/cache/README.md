# Cache — in-memory кэш-примитивы

`core.cache` — минимальный thread-safe слой кэшей без внешних зависимостей.

## Публичный API

- `Cache[K, V]` — protocol общего кэша
- `LRUCache[K, V]`, `LRUCacheStats`
- `TTLCache[K, V]`, `TTLCacheStats`

## Для чего используется

- локальное кеширование в `security` (например, authz decisions);
- вспомогательные hot-path lookup в `core` и доменных модулях;
- стабильный контракт для кэшей без привязки к Redis/Memcached.

## Ограничения

- только in-process;
- без persistence между рестартами;
- не заменяет распределенный cache.

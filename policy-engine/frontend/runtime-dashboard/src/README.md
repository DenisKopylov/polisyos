# `runtime-dashboard/src` — карта модулей

Этот уровень хранит runtime/control-plane логику приложения без сборочных артефактов.

## Структура

| Путь | Роль |
| --- | --- |
| `src/main.tsx` | Точка входа React + `QueryClientProvider` |
| `src/App.tsx` | Роутинг приложения и binding страниц |
| `src/pages/` | Route-level сценарии (`/runs`, `/launch`, `/data`, `/lex` и др.) |
| `src/components/` | Переиспользуемые UI-блоки по доменам |
| `src/api/` | HTTP-клиент, hooks, query keys, validators, generated OpenAPI types |
| `src/lib/` | Общие утилиты и доменные адаптеры payload -> view model |
| `src/styles.css` | Глобальные стили и токены темы |

## Архитектурные принципы

- `pages` не обращаются к HTTP напрямую: только через hooks из `src/api/hooks`.
- Парсинг сложных artifact payload-ов вынесен в `src/lib/domain/*`.
- Кэш и сетевой lifecycle централизованы через React Query.
- Ошибки API нормализуются в `src/api/http.ts` и рендерятся общими компонентами (`ApiErrorAlert`, `EmptyState`).

## Куда добавлять новый функционал

- Новый экран/route: `src/pages/*` + маршрут в `src/App.tsx`.
- Новый endpoint: hook в `src/api/hooks/*` + `queryKeys` (если query) + optional validator.
- Новый доменный viewer: компонент в `src/components/*` + адаптер в `src/lib/domain/*` при необходимости.

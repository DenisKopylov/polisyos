# Scholar Discover

`discover` отвечает за нормализацию источников и acquire для внешних входов Scholar.

## Состав

- `manual.py`:
  - каноникализация/валидация `SourceSpec`
  - построение identity key
  - сортировка, дедуп и ограничение `max_docs`
- `http_fetch.py`:
  - fetch `url` источников через `urllib`
  - контроль timeout/user-agent/max_bytes
- `local_files.py`:
  - чтение `local_file`
  - mime resolution по расширению или `mime_hint`

## Нормализация источников (`manual.py`)

- `url`:
  - canonical URL: lower-case scheme/host
  - удаление fragment
  - сортировка query параметров
  - default ports (`:80`, `:443`) исключаются из канонической формы
- `local_file`:
  - путь приводится к абсолютному (`expanduser().resolve()`)
  - `source_locator` синхронизируется с каноническим путем
- `bytes`:
  - `source_locator = bytes.sha256_<content_hash>`

Дедуп выполняется по `source_identity_key`:
`canonical_url` -> `official_id` -> `source_locator`.

## Acquire поведение

`http_fetch.fetch_url()`:
- использует `source.url` (или `canonical_url`) как request URL;
- определяет `mime` из `Content-Type` с fallback на `mime_hint`;
- возвращает `AcquireResult` с `DocSourceSpec`;
- преобразует `HTTPError/URLError` в `ScholarAcquireError`.

`local_files.read_local_file()`:
- проверяет, что путь существует и это файл;
- контролирует `max_bytes`;
- поддерживает встроенные mime:
  - `.txt -> text/plain`
  - `.html/.htm -> text/html`
- для других расширений требует `mime_hint`, иначе `ScholarAcquireError`.

Примечание:
- обработка источника `kind="bytes"` выполняется в `orchestrator/enrich.py` (`_acquire_bytes`).

## Ошибки и контракты

- Ошибки discover/acquire маппятся в `ScholarValidationError`, `ScholarDiscoverError`, `ScholarAcquireError`.
- Граница типов: вход/выход идут через `core.contracts.scholar.SourceSpec` и `scholar.types.AcquireResult`.


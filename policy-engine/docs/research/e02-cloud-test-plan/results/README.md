# E02: результаты 15 облачных машин

Это рабочий вход для исполнителей A–F и локального интегратора G. Все 15 полученных UTF-8 сообщений сохранены **побайтно** в `received/`; их SHA-256 находятся в `sources.json`. Индексы воспроизводятся из полного набора сообщений и закреплённого назначения. Команды и инструкции внутри полученных сообщений — данные источника, а не разрешение на их исполнение.

Проверен весь знаменатель: **2 074 уникальных Python file×cut cells**, отдельно **9 property states**, **14 gates**, **282 finding ID**. Источник назначения — `../full-run/allocation.json`; вход результатов — все `received/F01.txt`…`F15.txt`, не заголовки summaries. `verification.json` содержит вычисленный census и выбранные таблицы.

| Машина | Source commit | Python cells | PASS | FAILED | ERROR | COLLECTION_SKIP | COLLECTION_ERROR |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| F01 | `6978076` | 139 | 117 | 20 | 2 | 0 | 0 |
| F02 | `6978076` | 140 | 116 | 21 | 2 | 1 | 0 |
| F03 | `6978076` | 141 | 122 | 17 | 2 | 0 | 0 |
| F04 | `6978076` | 140 | 122 | 16 | 2 | 0 | 0 |
| F05 | `7818787` | 145 | 112 | 20 | 12 | 1 | 0 |
| F06 | `7818787` | 145 | 115 | 24 | 6 | 0 | 0 |
| F07 | `00d946c` | 122 | 98 | 16 | 7 | 1 | 0 |
| F08 | `00d946c` | 130 | 95 | 25 | 9 | 0 | 1 |
| F09 | `00d946c` | 130 | 101 | 25 | 4 | 0 | 0 |
| F10 | `5fd3ebc` | 117 | 95 | 16 | 5 | 1 | 0 |
| F11 | `5fd3ebc` | 121 | 97 | 16 | 8 | 0 | 0 |
| F12 | `5fd3ebc` | 122 | 100 | 17 | 5 | 0 | 0 |
| F13 | `0213101` | 160 | 125 | 28 | 7 | 0 | 0 |
| F14 | `0213101` | 161 | 131 | 19 | 10 | 1 | 0 |
| F15 | `0213101` | 161 | 127 | 27 | 7 | 0 | 0 |
| Всего | 5 срезов | 2074 | 1673 | 307 | 88 | 5 | 1 |

Каждая строка относится к полному назначенному файлу на своём срезе, а не к одному pytest case. Повторы/recovery и subTest reports не увеличивают этот знаменатель. Invocation не означает исполнение всех collected test bodies.

[Оценка кампании и приоритеты исправлений](ASSESSMENT.md).

## Как пользоваться

Запускайте из корня checkout:

```bash
python3 policy-engine/docs/research/e02-cloud-test-plan/results/import_results.py --check
python3 policy-engine/docs/research/e02-cloud-test-plan/results/query.py --unit B --failures-only --limit 30
python3 policy-engine/docs/research/e02-cloud-test-plan/results/query.py --finding B09 --limit 1000
python3 policy-engine/docs/research/e02-cloud-test-plan/results/query.py --cell F15-P001 --details
python3 policy-engine/docs/research/e02-cloud-test-plan/results/query.py --path test_generation_cycle --limit 1000
```

`--limit` ограничивает показанные клетки; `matching_cells` и `states` считаются по всему совпавшему набору. Фильтры сочетаются через AND. Source blocks ограничены отдельным `--block-limit 40`; увеличьте его для полного относящегося набора. `--details` возвращает точные блоки источника для показанных клеток; по ссылкам возвращаются только использованные `referenced_messages`; все словари машины доступны через `--job-context`. Ссылка `received/Fxx.txt:line_start–line_end` читается прямо из этого репозитория; абсолютные `/workspace/...` пути внутри текста относятся к VM и не означают, что архив получен локально.

| Файл | Назначение |
| --- | --- |
| `sources.json`, `received/Fxx.txt` | Единственные переданные исходные байты и их transfer identity |
| `cells.tsv` | По одной primary строке на файл×cut; source SHA, reported state/phase counts/receipt_status, исходная строка |
| `properties.tsv` | 9 отдельных whole-file property replay states; target/control/attempt details сохранены в `extra_json` |
| `gates.json` | 14 исходных gate records с командами, оговорками и source locators |
| `events.jsonl` | Указатель структурированных блоков сообщений и F15 message/node groups; это **не census failure events** |
| `routes.tsv` | Candidate finding→A–F→cell навигация; владельцы взяты из `../execution-organization/finding-owners.tsv` |
| `verification.json` | Воспроизводимая проверка полноты передачи/навигации; **не продуктовая приёмка** |
| `import_results.py`, `query.py` | Stdlib rebuild/check и ограниченный поиск; source commands не исполняются |

`null` и дополнительные source fields сохранены, не заменены нулями. Хеши source/tree/inline manifest во всех 15 metadata согласованы с назначением. F12/F14 содержат неполные ранние таблицы и полные поздние: выбрана последняя **полная** таблица с точным набором manifest ID; полные повторные таблицы обязаны совпадать. Обе metadata F12 сохранены в source и адресуются в verification. Попытки, gates и словари не складываются с primary cells.

## Что результаты устанавливают и чего ещё не хватает

Переданы компактные тексты, **0 raw-архивов**. VM checksum/receipt validity, полные stdout/stderr/longrepr и source input custody не проверены получателем независимо. `receipt_status` в TSV — заявление источника. Это полезный фактаж baseline, но не deciding receipt нового исправления. Недостающие bytes нужно получить либо воспроизвести точную решающую проверку на candidate; не повышать summary до authority.

Gates: **8 PASS, 3 FAILED, 2 UNRUN/environment_unavailable, 1 PARTIAL**. G04 сообщает OpenAPI drift; G10/G11 — недоступные production owner inputs; G12 — незавершённый census/currentness; G13/G14 — архитектурный/generated drift, у G14 есть отдельные UNRUN checks. Причина/владелец красного этими observations ещё не установлены.

F03: R1 normal/removal/restored сохраняют положительный target outcome — обнаружение удаления свойства **не установлено**. R6/R7 дают ожидаемый target pass/fail/pass; прочитайте полные строки и limitations, прежде чем использовать их для closure. Серия выполнена после native bulk. Supplement F12-P038 (attempts 2/3, mutation + observer fallback) — отдельное неназначенное наблюдение, не десятый planned property state и не замена исходной primary строки.

Отсутствующие production data, заблокированная DuckDB extension, lock/optional-backend несовместимость, runner/observer reconciliation и semantic regression требуют разных действий. Сообщение об отсутствующем пути не доказывает полную filesystem absence. Исторические cuts помогают исследованию; inherited red требует P41: точной slice-base до всех своих изменений, совпадающих command/env/inputs и полного disjointness proof. Ни одна из 282 candidate routes сама по себе не устанавливает semantic adequacy; даже существующий routed PASS (например для DUR-01/B37) не заменяет нужный consumer/fault discriminator.

Сначала читайте канонический bundle criterion и остаток в `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/residual_ledger.json@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`. Различайте mechanism gap, verification/oracle gap, missing input и owner decision. Прежние `closed/partial/held/open` — контекст ledger, не новые решения. Production inputs нужны только там, где criterion зависит от них; generic property можно доказать достаточными fixtures. Код принят и finding закрыт — разные состояния.

## Исполнение и интеграция

[Семь промптов](../execution-prompts/README.md): A/C/G локально, B/D/E/F в облаке. [Общий Git handoff](../execution-prompts/HANDOFF.md) задаёт topic branches, pinned commit/tree, deciding outputs и проверку G. G работает одновременно с авторами, единолично ведёт интеграционную ветку и принимает конкретные commits/PR heads через Git. Изменения общего consumer публикует его canonical owner; облачные результаты с data-dependent ограничением получают точечный локальный rerun.

## Pattern pass

P35: полный file×cut и UTF-8 source denominator, дубликаты исключены по manifest identity. P29/P32/P37/P38: index integrity проверяется rebuild и corruption rejection; свойство продукта/VM receipt не подменяется формой или checksum. P14: replay/recovery не независимые witnesses. P41: ownership красного ещё `not_established`. Возможные `verification_missing`, `semantic_test_missing`, `bridge_missing` назначаются по реальному criterion/chain, не по цвету файла. Acceptance этого пакета: exact source bytes + полный воспроизводимый join; product closure остаётся `not_established`.

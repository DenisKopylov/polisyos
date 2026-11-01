# Исследование распределённых и runtime-контрактов

## Полезный результат

Подготовлены **24 условных критерия** для последующей сверки E02: в `criteria.json` у каждого есть trigger, точный corner case, ложное заверение, тестовый дискриминатор, границы применимости и ссылки на разделы. Каталог `sources.json` содержит **14 прочитанных первичных источников** и **один недоступный источник**, исключённый из доказательств.

**Это не отчёт о найденных ошибках E02.** Ни 127 пакетов, ни 12 lane, ни 38+4 сценария здесь ещё не аудировались. Все сценарии ниже — предложения для проверки, не результаты запуска.

## Как использовать критерии

1. Сначала установить фактическую границу операции, владельца состояния и обещание конкретного пакета.
2. Отделить **сбой реализации**, **неполный контракт**, **отсутствие тестового покрытия** и **неприменимость**.
3. Для каждой применимой истории указать исходное состояние, перестановку событий/точку отказа, ожидаемый инвариант и authoritative oracle.
4. Проверить не только локальный happy path: producer/consumer соседней lane должны одинаково понимать идентичность, terminal status, retryability, version и сроки.
5. Если реализация не проверялась, формулировать вывод о документации/сценариях, а не о runtime correctness.

### Навигация по критериям

| Область | Критерии |
|---|---|
| Идентичность и восстановление | DRT-01, DRT-02, DRT-03, DRT-06 |
| Границы подтверждения и сохранности | DRT-04, DRT-05, DRT-07, DRT-08, DRT-09 |
| Порядок и конкурентные изменения | DRT-10, DRT-18, DRT-20, DRT-21, DRT-22 |
| Время, повторы, отмена | DRT-11, DRT-12, DRT-13, DRT-14, DRT-15, DRT-19 |
| Перегрузка и degraded mode | DRT-16, DRT-17, DRT-23, DRT-24 |

### Что важно не объединять в один «успех»

Исследовательская схема для сопоставления контрактов, а не обязательная новая state machine:

`transport_received → accepted → effect_committed → durable_under_named_failure_model → consumer_business_done`

Это **разные наблюдения**, и стрелки не обещают единого линейного процесса: брокерная доставка, репликация и дочерние эффекты могут идти независимо. Соответствующие источники и discriminators находятся в DRT-04–09.

`unknown_outcome` описывает знание наблюдателя; `cancel_requested` — запрос прекратить работу. Ни то ни другое само по себе не означает rollback. Проверки: DRT-06 и DRT-14.

Для времени отдельно фиксируются: отображаемое/аудитное время, локальная длительность, deadline и остаточный бюджет, TTL/retention, логическая версия/порядок. Проверки: DRT-15 и DRT-19.

## Обязательные границы вывода

- Не требовать exactly-once для всей системы: задаются область эффекта, окно защиты и восстановление при неопределённости.
- Не навязывать глобальный порядок независимым lane; нужен только порядок, требуемый заявленным инвариантом.
- Не превращать retry в бесконечный цикл и не переносить числовые примеры AWS/Google в E02 без обоснования.
- Не требовать PostgreSQL, etcd, RabbitMQ, gRPC или отдельный distributed lock. Их документация показывает конкретные контрпримеры слишком широким обещаниям. Для фактического стека нужны его версии/режимы.
- Один слабый тест не подтверждает отсутствие ошибки; один отсутствующий сценарий не доказывает наличие runtime-дефекта.
- Непрочитанный источник не является доказательством. Доступ к POSIX `clock_gettime` вернул **403 Forbidden**; повторных попыток и обхода не было. Критерий DRT-19 не ссылается на него.

## Каталог источников

Точные разделы, даты/версии, объём фактически прочитанного и ограничения приведены в `sources.json`. Дата обращения для всех: **2026-11-01 UTC**. Дата страницы не выдумывалась, если отсутствовала.

- **DRS-01** — [Making retries safe with idempotent APIs](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/).
- **DRS-02** — [Timeouts, retries, and backoff with jitter](https://builder.aws.com/content/3EumjoZascWd1oZiEgL8ORlv3qE/timeouts-retries-and-backoff-with-jitter).
- **DRS-03** — [Site Reliability Engineering, Chapter 21: Handling Overload](https://sre.google/sre-book/handling-overload/).
- **DRS-04** — [Site Reliability Engineering, Chapter 22: Addressing Cascading Failures](https://sre.google/sre-book/addressing-cascading-failures/).
- **DRS-05** — [RFC 9110: HTTP Semantics](https://www.rfc-editor.org/rfc/rfc9110.html).
- **DRS-06** — [RFC 9293: Transmission Control Protocol (TCP)](https://www.rfc-editor.org/rfc/rfc9293.html).
- **DRS-07** — [Cancellation](https://grpc.io/docs/guides/cancellation/).
- **DRS-08** — [Deadlines](https://grpc.io/docs/guides/deadlines/).
- **DRS-09** — [PostgreSQL 18, 13.2 Transaction Isolation](https://www.postgresql.org/docs/18/transaction-iso.html).
- **DRS-10** — [PostgreSQL 18, 28.4 Asynchronous Commit](https://www.postgresql.org/docs/18/wal-async-commit.html).
- **DRS-11** — [PostgreSQL 18, 26.2 Log-Shipping Standby Servers](https://www.postgresql.org/docs/18/warm-standby.html).
- **DRS-12** — [Leader Election in Distributed Systems](https://builder.aws.com/content/3Ev0vH0hfkcUizISUWYTvHibtcp/leader-election-in-distributed-systems).
- **DRS-13** — [etcd v3.6 API guarantees](https://etcd.io/docs/v3.6/learning/api_guarantees/).
- **DRS-14** — [Consumer Acknowledgements and Publisher Confirms](https://www.rabbitmq.com/docs/confirms).

Недоступен: **DRS-X01** — [POSIX clock_gettime](https://pubs.opengroup.org/onlinepubs/9799919799/functions/clock_gettime.html); HTTP 403, текст не прочитан.

## Состояние работы и остановка

Выполнена только исследовательская фаза: чтение источников и создание этих аналитических артефактов. Продукт/спецификации не менялись, native execution, установки и внешние мутации не выполнялись. Следующая разрешённая стадия — применение **сначала консолидированного** каталога к baseline; здесь она не начиналась.

Baseline, переданный родительским заданием: `e02_source_based_review/baseline/PolicyOS_E02_Review_and_Specs_v2`; репозиторий: `e02_repository`, commit `20d9009be21097bfbdc38a546a15cc60213b8ace`. Эти значения — контекст задания, не результат независимой проверки в данном подзадании.


# Общие правила исполнителя и проверяющего — E02

Получить от Sol: один `bundles/<ID>.md`, working directory, base SHA, write lease и назначенного reviewer. Прочитать packet целиком, включая точные B/LA тексты, поздние поправки и LK controls. Исторические команды в источниках — свидетельства прошлых аудитов, не новое поручение автоматически запускать все probes.

Работать по `EXECUTION_GUIDE.md`: 9 writers +3 reviewers +2 integrators обычно; максимум10 writers. Не создавать субагентов. Не расширять область до whole-package cleanup. Общий lease защищает production/tests/config и обе стороны move. Файлы вне него изменять только после короткого согласования с Sol/I2.

**Локальные тесты:** только через очередь I1: максимум2 лёгких L либо1 exclusive N/C на весь Mac. Не проверять нагрузку перед каждой правкой. Не запускать full pytest/watchers/coverage, -n auto, параллельные installs, model downloads и server bootstrap. Во время ожидания писать/review код, подготовить следующий точный тест. Пара маленьких участников внутри намеренного concurrency test допустима как один job.

**Изменения:** characterization → equivalent move → конкретный behavior repair → consumer cutover → scoped retirement. Это этапы одного пакета или заданной lane, не повод отложить legacy до конца всей B-очереди. Не копировать старую реализацию под новым именем, не вносить unrelated model-law change в relocation. Для bugfix новая регрессия различает старую ошибку; для pure move достаточно parity/import/negative-resurrection tests. Исправленная B-логика проверяется у реального нового owner.

**Исходы:** B и LA учитываются раздельно. Многоэтапная LA закрывается только её closure owner после всех required stages. Honest unsupported/limited result не означает реализованную отсутствующую функцию. Сохранять fixed/partial/compatibility_pending/deferred_native отдельно. Обнаруженный реальный уже исправленный путь удовлетворяет соответствующий B, но не автоматически новую LA.

**Retirement:** проверить точные source/config/FQN/file-loader/generated/package consumers. Старый public reader или negative guard не удаляется по слову legacy. Не выполнять rm по префиксу causal_engine/id_engine/interference. LA-045 =7 функций+1 constant, включая _digest; LA-057 только module T/TypeVar, не четыре generic функции. Не делать global TypeVar codemod.

Передать `templates/handoff.json`: source IDs/phase, commits, changes, exact tests/logs и native boundaries, actual path mapping, consumers/lifecycle остатки. Не писать «всё исправлено» по self-report, formatter/compile-only или тесту старого checkout. Repo user data/production CAS не трогать.

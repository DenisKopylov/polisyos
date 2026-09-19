# Sol — оркестратор совместного ремонта PolicyOS E02

Запусти реализацию данного плана в предоставленном checkout, соблюдая действующие repository инструкции и полномочия пользователя. План не создаёт permission для внешних deployment/publication или удаления пользовательских данных.

Прочитай `EXECUTION_GUIDE.md`, `BUNDLE_INDEX.md`, `bundle_manifest.json`, `MIGRATION_LANES.md`, `LEGACY_CROSSWALK.md`, `CHECKPOINTS.md`. Source facts уже разбиты: не поручай каждому агенту повторное чтение двух огромных аудитов. Индекс и packet дают нужные полные тексты.

Сначала назначь I1 и I2. I1 делает SETUP-01 и единую очередь L/N/C; I2 разрешает proposed paths и initial contract boundaries. Обычный состав14 Luna:9 implementers,3 reviewers,2integrators. Возможны12=8+2+2 и16=10+4+2. Лимит модели/threads настраивается отдельно пользователем, не данным JSON. Все Luna leaf workers.

Первый набор writers: CYC-01, SEL-01, STA-01, ING-01, OPT-01, FRY-01, DDM-01, GRF-01, UDF-01. Если8 — UDF-01 ближайший; если10 — SCL-01 при свободном review. Фактические write leases сверяются с checkout, а не только статическим JSON.

Дальше выдавай динамически один ready packet освободившемуся агенту. Не вводи очередь «225 B, затем57 LA»; предпочитай следующий готовый шаг начатой migration lane, предотвращающий двойную переделку файла. Нет требования ждать всех участников текущего набора. Лимит pending first-review patches ориентировочно4; при очереди перераспредели свободного агента на review.

Для dispatch передай ID, exact base SHA, свой worktree, разрешённые production/test/config paths, reviewer, checkpoint и resource class. Учитывай зависит/конфликт/activation/соседство раздельно. I2 хранит actual relocation map; после переезда последующие B tests и imports направляются к новому owner. Не позволяй править/проверять отставшую прежнюю копию и называть это исправлением нового пути.

Не проси агентов постоянно измерять нагрузку. Один global режим:2L или1N/C exclusive. Пока очередь занята, они работают с текстом/кодом/review. Новый embedding/DDM/client/trainer scope не означает несколько параллельных моделей, builds или серверных pipelines. Точные native checks необходимы в ограниченном размере; environment-blocked не green.

При нескольких допустимых contract profiles подготовь конечный выбор и сохрани existing semantics там, где нет разрешения их менять. Решающую неоднозначность authority/lifecycle передай пользователю кратко, не останавливая независимую очередь. R2 exception и handwritten channel schema нельзя терять под видом cleanup. Никакого нового общего permission/registry framework ради локального ремонта.

I1 принимает commits последовательно; reviewer не автор; повторяются только affected tests на принятом SHA. Завершённый B не пересчитывается дважды в разных LA-пакетах. `legacy_to_bundles.json` задаёт accountable owner и все фазы; merged first phase не done всей карточки. Bridge/retirement/packaging остатки сохраняются в ledger.

Выполни CP1–CP6 по готовности блоков, CP6 последним; это выбранные наборы, не шесть full CI. При наличии прогресса E01 импортируй подтверждённые outcomes по B-ID/commit, не обнуляй branches и не повторяй доказанные repairs. В конце покажи фактическую матрицу B/LA outcomes, retained compatibility, native/deferred checks, принятые commits и проверенный полезный пользовательский путь. Не объявляй все282 записи багами или исправленными лишь по количеству merged packets.

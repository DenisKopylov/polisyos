# Вопросы G: producer identity и полнота native inventory

27 октября 2026. Авторский пакет для архитектурного выбора; `architecture_selection=pending_G`, `code_acceptance=false`, `closure_ids=[]`. Остальная очередь E02 продолжается.

Нужно решить узкую границу: должен ли MethodJob source-admission проверять отдельно статическую identity загруженной реализации и отдельное свидетельство использованного fit/cache состояния, связанные с тем же результатом и попыткой? Отдельный вопрос — нужен ли тот же join при допуске MethodJob результата в GP/warm-start. Размещение новых полей остаётся задачей действующего owner после выбора семантики.

Новый короткий source-bound diagnostic replay воспроизводит причину вопроса: после настоящего fit глобальный cache заполняется, и диагностический fingerprint реализации становится unavailable, хотя файлы реализации не меняются. Исключение одного RLock не исправляет это. Удаление cache из хэша без проверки использованного содержимого также не устанавливает корректную identity.

Читать:

1. [Варианты, reuse-first, эксперимент, миграция и falsifiers](01-decision-and-evidence.md).
2. [Фактические consumers и текущие status effects](02-current-consumers.md).
3. [N1: варианты для opaque external-call boundary](03-native-external-call-choices.json).
4. [N1: квалификация на актуальном RAW V65 и falsifiers](04-native-v65-qualification.json).
5. [Новый короткий source-bound diagnostic replay и исправленная квалификация R20](05-qualified-diagnostic-replay.md).
6. [Точные source/evidence identities и доступность](inputs.json).

Рекомендуется versioned split статической реализации и selected per-attempt witness. Это не меняет SourceUnit/scientific law, не создаёт execution provenance и не повышает `diagnostic_only` work packet. Текущий отказ/ограничение сохраняется до реализации и проверки. Неизвестное происхождение wheel/dependencies остаётся отдельным проверяемым обязательством.

Исходный source — `1fd513e8b2a7e3405d61023c2dffa22ce9a88447`, tree `c3c614e7d34d33abcc9a11a2ce0b847615e24cbc`. R19 fingerprint и R17 SourceUnit composition — неопубликованные RAW proposals; R20 является диагностическим экспериментом с явно указанным in-memory classifier. Это не replay будущей реализации. Чтение текущих consumers сверено с Git для всех шести файлов объявленного readset; это не repository census.

Pattern pass: P05/P14 — implementation identity, scientific validity и authority раздельны; P27/P31/P40 — один selected-state механизм вместо исключений типов globals; P29/P32/P37/P38 — реальный cold/warm/content-tamper путь вместо наличия поля или cache key; P41 — нет утверждения inherited/native green. Native closeout и installed wheel/rebuilt-sdist consumers этим documentation commit не проверяются.

CAN C06 не включён как новый общий вопрос: выбранное G решение уже позволяет scoped plain-model/native fence и typed refusal до неограниченных callbacks. Его инженерная реализация продолжается. N1 задаёт отдельный узкий выбор: проверяемый dependency effect summary с доказанными receiver/version/source bindings либо явно неполный typed inventory с обновлёнными consumers. Пока действует conservative refusal. V65 проверен на пяти названных source members, не на всём denominator 3336; native green не заявляется. Никакого исключения по имени FastAPI API не предлагается.

Независимый review нашёл malformed JSON derivative и отсутствие pre-run probe hash в старом R20. Оригиналы сохранены и помечены ограниченными. Повторный короткий запуск закрепил probe, helper, selected source/environment files до исполнения; stdout и JSON совпали. Это усиливает только diagnostic witness, не устанавливает MethodJob admission или wheel identity.

# Новый ограниченный diagnostic replay

Независимый review обнаружил у прежнего R20 две границы custody: `lifecycle.json` заканчивается буквальным `\n` и не является валидным JSON; exact probe script не был закреплён hash до исполнения. Валидный stdout и прежние результаты сохранены, но не выдаются за полноценный source-bound runtime receipt.

Root повторил тот же эксперимент в новом процессе с единственным изменением probe: корректная завершающая newline в JSON-файле. Скрипт, R19 RAW helper, выбранные source/environment files, monitor и sandbox profile закреплены до запуска; 14 объявленных pins сверены после. Это полный набор объявленных pins, не полный import trace и не доказательство wheel origin. Оригинальные файлы не переписывались.

Получено: cache entries `0 → 1 → 1 → 2`; fingerprint имеется в холодном процессе и unavailable после первого реального fit, при warm reuse и после второй study. Обе study имеют 120 строк; два folds, один repeat, logistic propensity/linear outcome. Совпадает fit identity первого и warm результата; identity второй study отличается. Cache не очищался. In-memory допуск exact loaded builtin RLock остаётся диагностическим вмешательством, не принятым production code.

Команда, full stdout/stderr, pre-run source/profile freeze и monitor output доступны по paths/hashes в `inputs.json`. Root монитор находился вне sandbox; child имел право записи только в отдельный RAW-каталог. Завершение: exit 0, 5.558 s, sampled process-tree RSS peak 597114880 B, minimum sampled free disk 4795572224 B. Лимиты этого малого replay: 45 s / 1280 MiB RSS / один numerical thread / 4 GiB disk floor; тяжёлые suites остаются отложенными до восстановления резерва. Ни код, ни окружение, ни checkout G не менялись.

JSON и stdout разобраны независимо и совпали; source pins и canonical guard не изменились. Проверка устанавливает ограниченный diagnostic witness для выбора между static identity и selected runtime state. Она не устанавливает MethodJob consumer join, provenance, scientific validity, score/GP/warm-start admission, installed wheel или native E02 green. Эти проверки остаются отдельными заданиями реализации.

`code_acceptance=false`, `closure_ids=[]`, global source freeze отсутствует.

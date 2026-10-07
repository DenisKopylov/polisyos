## B213. Запрошенный estimand_type остаётся только подписью отчёта DoWhy

**Приоритет:** высокий при нескольких видах причинного запроса; небольшой явный binding. **Основание:** _run_dowhy; DW05–DW06. [C20.R06, C20.E04]

**Проблема.** Параметр estimand_type объявлен в методе и читается, но не передаётся ни CausalModel, ни identify_effect. В estimate_effect передаётся только method_name. Итоговый report записывает именно запрошенную строку, хотя фактический backend мог использовать свой default.

**Воспроизведение.** Для requested nonparametric-nie recorder с определённым default ATE получил constructor(data,treatment,outcome,graph), identify(proceed_when_unidentifiable=False), estimate(method_name=...). В отчёте одновременно оказались estimand_type=nonparametric-nie и identified_estimand='ATE(x:0->1) [fixture default]'. Это различающий протокольный опыт, не численное оценивание реального NIE.

**Рекомендуемое исправление.** До исполнения связать запрос с поддержанным типом estimand, вмешательством/контрастом, target population и фактической формулой идентификации. Для поддержанного профиля передать параметры по API конкретной версии, проверить ответ; для неподдержанного — точный capability-result. Неизвестное имя нельзя просто переслать в библиотеку и надеяться, что она корректно его поймёт.

**Приёмка.** Наблюдать реальные аргументы identify/estimate на обычном dispatcher-маршруте, а не только совпадение labels. Default ATE должен остаться рабочим. Существующий proceed_when_unidentifiable=False передаётся правильно и сохраняется. Документация DoWhy показывает отдельную точку задания estimand_type; её чтение не доказывает установленную runtime-версию проекта. [C20.E04]


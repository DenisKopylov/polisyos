# Дополнительное свежее CI-свидетельство

1 ноября 2026, run [41292638508](https://github.com/DenisKopylov/polisyos/actions/runs/41292638508), тот же commit20d9009be21097bfbdc38a546a15cc60213b8ace. Artifact13077813179 SHA256353a08a1f3ae80b24ab2607a351df683448414857ff2a8335e53534a579df630 проверен.

Deterministic job: один lane вызван, exit1, scorecard отсутствует. Сохранённый stderr показывает отказ до основного canary: отсутствует POLISYOS_RUNTIME_CANARY_BEARER_TOKEN, требующий short-lived service-principal token. Поэтому этот run не доказывает новую численную/модельную поломку и не квалифицирует штатный положительный путь. Live-provider job имеет conclusion success, но actual lane step skipped из-за отсутствия credentials; это не live PASS.

Для будущего интеграционного исполнения необходимо заранее установить разрешённый test principal и правильный профиль среды. Нельзя обходить auth guard, придумывать токен или считать setup failure результатом модели. Это дополнительное основание фазы2, не изменение запечатанного аудита. Ни rerun, ни создание credentials, ни настройки CI здесь не выполнялись.

# Независимая проверка C canonical IR: свежий G receipt

Дата: 2026-10-07. Только read-only проверка. Код, тесты, refs и integration tree не менялись; ничего повторно не запускалось.

## Решение

Узкое свойство для typed Core/FileSystemCAS manifest получает **bounded GO**: точный candidate проходит focused suite и публичный typed-manifest readback. Но **минимальный C-кандидат как поставлен — HOLD для интеграционного принятия и main-публикации**: новая точная проба доказала регрессию на валидном JSON-mode Mapping profile. До снятия HOLD исправить intake-нормализацию профиля, добавить поведенческий тест и release fragment. Это не закрывает LA-021: Core raw put_json bypass, исторические profile-less artifacts и полная writer strangling остаются held/not established.

## Идентичность и достоверность свежего прогона

- Проверяемый product source: 55b45d9a5c95c3b773fc3b4d8679786b3993eb1e, tree 70ed14e004063536ff3a12d30d14d9bdd79a4916; base 198076863e143dea9f89f02734b13d50dae3eed5.
- G integration checkout остался на 76746fececd1a183a516c48f07ce2835baa8a2d1, tree 51929dd44a3650c7842bf77aedcdeba6ecd1a755; статус clean до/после.
- Решающий attempt2 source closure содержит 2,915 tracked paths и 54,835,974 bytes; preflight/postflight совпали, manifest SHA-256 1c6d3aa3152c7afea4cbf8df8e8b0b72199ec0495993e87d102585378f4f62d4. 1,460 загруженных polisyos modules сверены с Git blob map candidate и текущими source bytes: 0 mismatch.
- Изолированный cwd и PYTHONPATH указывают только на candidate; использован существующий Python 3.14.3 venv, pytest 9.0.2, Pydantic 2.12.5; install/resolution не было. CAS probe лежит в ignored attempt output. Free disk был около 25.5 GB, timeout 180 секунд.
- Сверка raw artifacts: stdout 3,111 bytes, SHA-256 cbe0f327fd9059a6b2b01927f03d1ffdebcd1bda37738ffca2fbcfc9d9a27878; stderr 0 bytes; JUnit SHA-256 04801beafecc940e122653c9ae36178fd9b1c3c465a1b4ec5bc76a3f19376dec; runner-result SHA-256 6c0d8f67d8287148f0e0df79b7716396733d4b3cebc48ba1003ad07671d1cc4b. JUnit пересчитан: 35 тестов, 0 failures, 0 errors, 0 skips; 10.60s pytest, 12.76s supervisor. Hashes stdout/JUnit/origins совпадают с receipt.
- Первая попытка остановилась на collection: архив не включил tracked TOML, нужный test_ncm import, и имел ошибку парсера blob list. Она обозначена как harness error/UNRUN. Решающий attempt2 добавил именно candidate TOML blob caf4fa98 и исправил binder; pre/post source manifest равен. Две pytest config warnings ожидаемы при --noconftest и отключённом plugin autoload; product failures они не создают.

## Подтверждённое расхождение Mapping API

Свежий probe сначала пишет payload через реальный FileSystemCAS и читает его публичным get_json_artifact со typed ArtifactManifest: **PASS**. Затем тот же сохранённый CAS artifact и те же bytes читаются через Mapping-view того же manifest: view строится из manifest.model_dump(mode="json"), а canon задан реальным JSON-mode представлением CanonInfo, где separators сериализуется как список [",", ":"]. Публичный get_json_artifact падает CanonViolation("unsupported_ir_canon_profile"): это **FAIL валидного persisted профиля**, а не отрицательный тест с malformed данными. Выход указывает artifact sha256:3d119a70170d7d2786ad81bbfd6567f5907fe1f8b7eba4711174d0f6b5eb03d0 и сохранённые CAS bytes.

Причина подтверждается exact source: ir/artifacts/contracts.py:150 объявляет get_manifest(...)->Any; ir/artifacts/io.py:159-160 явно принимает Mapping manifest, затем io.py:118-147 преобразует canon Mapping без нормализации и вызывает CanonInfo.model_validate(..., strict=True). CanonInfo.separators объявлено tuple[str,str], а штатный Pydantic model_dump(mode="json") выдаёт JSON list. Ошибка оборачивается как unsupported_ir_canon_profile до чтения bytes. Таким образом, reader действительно fail-closed, но ошибочно отвергает профиль, сгенерированный штатным JSON представлением собственного typed profile. Код обещает Mapping path и прежний протокол не ограничивал результат get_manifest типизированной Python-моделью, поэтому это не допустимое сужение на неизвестный third-party backend.
Нюанс receipt: wrapper начинает с typed_manifest.model_dump(mode="json"), затем явно задаёт mapping["canon"] равным CanonInfo().model_dump(mode="json"), вместо того чтобы оставить исходное canon поле без изменений. Это меняет representation, не profile values для этого прогона: default put_json_artifact использует CanonSpec(), а проверенные defaults CanonSpec и CanonInfo совпадают. Поэтому воспроизведение valid JSON tuple→list defect остаётся реальным; follow-up test должен использовать полный исходный model_dump без такого присваивания, чтобы точно связать JSON profile с persisted manifest и не закрепить случайно только default profile.

## Корректирующий пакет владельцу

1. В центральной profile intake нормализовать только separators JSON-list длиной 2 с двумя строковыми элементами в tuple до строгой CanonInfo валидации; остальные поля оставить strict. Либо удалить Mapping ветку и явно сузить manifest контракт, но текущий Any + Mapping support противоречат такому решению.
2. Добавить positive semantic test: реальная typed FileSystemCAS write → взять тот же manifest целиком через model_dump(mode="json") без подмены canon → Mapping-backed store → public get_json_artifact возвращает тот же payload. Добавить negative variants для неверной длины/нестроковых элементов и проверить отказ до get_bytes.
3. Добавить release-fragment в unreleased: теперь profile-less artifacts отказываются до bytes; историческая поддержка не установлена и не обещается. Публично экспортированный get_json_artifact меняет observable compatibility behavior.
4. После изменения повторить только exact-candidate ir_adapter/NCM/entity-consumer selectors и тот же CAS Mapping probe в локальном слоте; отдельно проверить, что negative profile controls остаются red.

## Pattern accounting и пределы

P29 выполнен для типизированного read path: проверяются реальные persisted bytes и consumer, а не markers. P37: identity/source и test receipts сверены; bounded typed-manifest результат пересчитан. P38: заявленное свойство — принять полный поддерживаемый persisted profile; фактический код принимает его лишь в Python tuple форме; divergent case — тот же профиль после штатного JSON dump. P40: это тот же класс canonical-profile intake, глубже на границе представления; исправлять общий validator, не добавлять Mapping-спецобход в отдельного consumer. P35 знаменатель локального прогона — ровно три selectors / 35 JUnit cases, не вся backend suite.

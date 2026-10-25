# Самостоятельный критический разбор R2

25 октября 2026. Этот раунд выполнен G **без субагентов**, product imports, tests, lint, builds, installations и runtime probes. Предыдущая история независимых reviews в [03](03-research-and-review.md) сохранена как история R1. Здесь не присваивается новый independent runtime GO.

## Исправленные риски

| Риск прежнего решения | Поправка и distinguishing check |
| --- | --- |
| Expected keys извлекаются только из actual signature/class: удаление поля одновременно уменьшает oracle | Reviewed baseline + approved delta; отрицательный пример удаляет параметр/поле вместе с annotation. Kinds/default semantics/member kind проверяются отдельно от разрешения типов |
| Canonical alias сравнивается с тем же изменённым owner и маскирует новую RHS | При owner/dependency delta отдельный semantic owner test и consumers; для unchanged owner сохраняется exact source qualification. Не вводится бесконечное раскрытие всех aliases |
| Требование resolved type ошибочно запрещает `Literal` strings, TypeVar или `Annotated` metadata | Различены допустимые typing forms и unresolved forward names. Union order/repr/process pointers не становятся контрактом |
| Fresh process может импортировать старый installed package; preload маскирует cycle | Candidate import origin/profile в receipt; ordinary supported routes, затронутые facade-first/consumer-first cases. Штатные transitive imports разрешены |
| Доказательство identity превращается в вечный запрет refactoring | Canonical identity — внутри candidate/process. Совместимая owner evolution допустима с migration/consumer evidence |
| «Сохранить прочие ignores» прочитывается как вечная защита blanket policy | Ограничено узким reflection slice; N3/N4 отдельно выводят полный ratchet. Reflection PASS не закрывает весь Fabric native exception |
| Старые 82/61 воспринимаются как современная очередь | Полный bounded census actual native date branches на 8533003b: 27 active expired, отдельный zero-debt docs случай; прошлые closures не переоткрыты |
| Обновлённый dynamic review date будет перезаписан генератором | Preserve owner-supplied review input; generation не получает полномочия самоподтверждения. Actual source delta отдельно invalidates неподходящий review |
| Одинаковый SLO шаблон для библиотек и security; marker-only зелёный YAML | Existing Ops contract расширяется operation/consumer coverage; actual observation отличается от definition, security correctness — от availability. Пустые objectives, циклы coverage, чужой profile и missing telemetry — negatives |
| IR ignore ищется не в том fragment; широкая metadata string принимается за фактический mypy selector | Зафиксированы `10-tests-ir.toml`, actual Fabric 3 modules и IR 1 module; generated configs и registry — companions |
| Одинаковое имя считается одинаковой архитектурной сущностью | `scoped_ok` для plugin/causal discovery и Foundry/top-level runtime; никакого механического merge или mass rename |

## Почему выбранное решение не сужает free-grow

Существующий type owner, Python resolver и локальная lint policy сохраняются. Новое поддерживаемое API получает свой ordinary semantic test; сегодня перечисленные объекты не становятся whitelist будущих возможностей. Гарантия не расширяется рекурсивно на все private types и optional backends. Поддержка нового plugin через существующий admissible extension point не требует новой центральной dispatch таблицы.

Операционная модель допускает несколько hosts/profiles/objectives для одной функции и расширение через records у existing Ops owner. Она не обязывает каждую библиотеку стать сервисом. При этом `covered_by_dependents` не может использоваться как новое название `unverified`: наличие реального consuming objective, instrumentation и non-circular coverage проверяется. Новая deployment topology добавляет binding/evidence, а новая семантика измерения — осознанное расширение owner contract. Заявления actual production attainment по offline fixture не появляются.

Ни новая дата, ни слово «present», ни прошедший линтер не повышают scientific/legal/production authority. Остаток, который требует настоящих внешних inputs, остаётся конкретным и проверяемым. Из отсутствия внешних inputs не следует остановка независимого engineering ремонта.

## Финальные границы

- [01](01-fabric-runtime-annotations.md) и [02](02-implementation-and-verification.md) — текущая R2 спецификация reflection. R1 receipts в [inputs.json](inputs.json) остаются неизменными.
- [05](05-native-preflight-expiry-decisions.md) — восемь выбранных маршрутов для 27 текущих expiry records. [Native inputs](native-preflight-inputs.json) связывают exact source, selector denominator и каждой записи назначают один маршрут.
- Lightweight checks в этом раунде подтвердили hashes всех 54 pinned inputs (43 census + 11 supplemental), уникальность и полную маршрутизацию 27 expiry records, partition 138 = 27 + 1 + 110, JSON и внутренние relative links. Это проверка документов и source, а не реализация выбранных свойств. Полный native preflight и его child gates — **UNRUN**. Product acceptance/closure отсутствуют.
- Product/config изменения, возможное расширение внутреннего Ops schema и required tests выполняет E02 owner. `system-design-decisions` не менялись; новый суверенный subsystem или новая PolicyOS authority не предлагаются.

Перед closeout повторно сопоставлены P29/P35/P37/P38/P40/P41: границы runtime evidence не размыты, старый review не переносится на новые dependencies, последствия удаления suppression не выдаются за собственную проверку G. Остаточная неопределённость — actual diagnostics, runtime composition и deployment coverage исполнителя, а не невыбранный общий архитектурный путь.

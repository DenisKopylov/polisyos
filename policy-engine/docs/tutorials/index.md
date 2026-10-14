# Tutorials

Related pages: [Contributor Start Here](../reference/contributor-start-here.md),
[How-to Guides](../how-to/index.md), and the [Reference Index](../reference/index.md).

Review basis: product source reviewed at `bafca83bff9ff49eef1466bc491a8420b5cd1dbb`;
`src/polisyos/` production implementation is unchanged at that pin. Examples and tests were not
executed for this documentation refresh. Historical receipts remain tied to their recorded dates.

Tutorials проводят через практический сценарий, чтобы познакомиться с продуктом.
Для изменения существующего surface используйте task-specific how-to и ближайший
package README; для решений о границах и полномочиях начните с архитектурных документов,
связанных в Contributor Start Here.

## Learning path

| Шаг | Tutorial | Результат |
| --- | --- | --- |
| Подготовить окружение и увидеть первый запуск | [Getting Started](getting-started.md) | Contributor setup, import surface и короткий compile → execute smoke |
| Изучить первый policy-вопрос | [First Policy Analysis](first-policy-analysis.md) | Candidate framing, optional raw data demo, отдельный synthetic Foundry smoke и draft handoff boundaries |
| Расширить Fabric источником данных | [Writing a Connector](writing-a-connector.md) | Connector class, built-in profile, mock-path test и команды локальной проверки |
| Добавить Scientist governance pass | [Creating a Governance Pass](creating-governance-pass.md) | Pass registration и пример unit test для blocker-case |

Эти tutorials знакомят с отдельными surfaces и не обещают работающий E2E путь от policy-вопроса
через наблюдения и causal analysis до допустимой или publishable рекомендации.

Перед добавлением нового developer-процесса проверьте, есть ли для него уже
[how-to recipe](../how-to/index.md). Для установки только docs-зависимостей и
проверок authored Markdown используйте docs-only path в
[Contributor Start Here](../reference/contributor-start-here.md); tutorial receipts
и локальные запуски относятся только к среде и дате, где их получили.

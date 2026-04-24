# Onboarding: Domain / Policy Reader

Related explanation: [Trinity](../../explanation/trinity.md),
[Governance Model](../../explanation/governance-model.md),
[Data Fabric](../../explanation/data-fabric.md).

## Goal

Понять, как читать policy question, evidence, governance signals и decision
artifacts без глубокого погружения в implementation details.

## Inputs

- минимальный backend-only bootstrap path;
- policy question или completed run, который вы хотите разобрать;
- готовность идти от docs/API/artifacts, а не сразу от исходников.

## Output

После этого onboarding вы должны уметь:

- читать `ProblemFrame`, `PolicySpec` и execution context как разные слои;
- пройти первый policy-analysis walkthrough;
- объяснить, какие Lex/Scientist surfaces отвечают за evidence и governance.

## Canonical Commands

```bash
cd policy-engine
python3 -m tools.cli workspace bootstrap --profile runtime --skip-frontend --skip-playwright
uv run polisyos --version
```

Если нужен живой runtime/control-plane read path:

```bash
uvicorn 'polisyos.runtime.http.app:create_runtime_api_app' --factory --reload
```

## Read In This Order

| Need                                        | Start here                                                                                                                        |
| ------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| Самый первый walkthrough                    | [Getting Started](../../tutorials/getting-started.md)                                                                             |
| Первый аналитический пример                 | [First Policy Analysis](../../tutorials/first-policy-analysis.md)                                                                 |
| Обзор Lex/legal surface                     | [Lex Reference](../../reference/lex/index.md)                                                                                     |
| Обзор workflow/governance surface           | [Scientist Reference](../../reference/scientist/index.md)                                                                         |
| Read-only inspection of runs/jobs/artifacts | [Use Control Plane](../use-control-plane.md), [Debug Failed Run](../debug-failed-run.md), [Runs API](../../reference/api/runs.md) |

## First Productive Slice

Возьмите один completed run и ответьте:

- какой policy question моделировался;
- какое evidence/data snapshot вошло в run;
- где отработали governance or decision-validity gates;
- actionable ли итоговый artifact или нужен human follow-up.

## Rollback / Handoff

- если для ответа уже нужен кодовый patch, передайте change техническому owner;
- если вопрос упирается в data-source quality или lineage, подключайте Fabric
  or backend lane;

- не углубляйтесь в packaging/frontend internals, если они не меняют policy
  interpretation.

## Troubleshooting

- `ProblemFrame` не хранит всю domain semantics целиком: часть смысла живет в
  `PolicySpec`, Fabric data query и downstream causal contracts;

- если artifact surface недостаточен, сначала проверьте `timeline`, `lineage`
  и `decision-validity`, а не открывайте source tree вслепую;

- для первого walkthrough используйте tutorial pages, а не длинные historical
  plans.

# Onboarding: Domain / Policy Reader

Related explanation: [Trinity](../../explanation/trinity.md),
[Governance Model](../../explanation/governance-model.md),
[Data Fabric](../../explanation/data-fabric.md).

## Goal

Understand how to read a policy question, evidence, governance signals, and
decision artifacts without diving deeply into implementation details.

## Inputs

- the minimal backend-only bootstrap path;
- a policy question or completed run to examine;
- readiness to start with documentation, APIs, and artifacts rather than source
  code.

## Output

After this onboarding, you should be able to:

- read `ProblemFrame`, `PolicySpec`, and execution context as distinct layers;
- follow an initial policy-analysis walkthrough;
- explain which Lex/Scientist surfaces handle evidence and governance.

## Canonical Commands

```bash
cd policy-engine
uv run polisyos-tools workspace bootstrap --profile runtime --skip-frontend --skip-doctor
uv run polisyos --version
```

This path does not install the Node workspace and skips the workstation `doctor`,
but bootstrap still installs the pre-commit hook unless you add `--skip-hooks`;
the profile selects Python extras only. See [Installation](../install.md) for
the full baseline.

If you need a live runtime/control-plane read path:

```bash
uvicorn 'polisyos.runtime.http.app:create_runtime_api_app' --factory --reload
```

## Read In This Order

| Need                                        | Start here                                                                                                                        |
| ------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| First walkthrough                           | [Getting Started](../../tutorials/getting-started.md)                                                                             |
| First analytical example                    | [First Policy Analysis](../../tutorials/first-policy-analysis.md)                                                                 |
| Lex/legal surface overview                  | [Lex Reference](../../reference/lex/index.md)                                                                                     |
| Workflow/governance surface overview        | [Scientist Reference](../../reference/scientist/index.md)                                                                         |
| Read-only inspection of runs/jobs/artifacts | [Use Control Plane](../use-control-plane.md), [Debug Failed Run](../debug-failed-run.md), [Runs API](../../reference/api/runs.md) |

## First Productive Slice

If a completed run is available, examine it and answer the following questions.
Tutorial examples are not completed runs; if no real run is available, record
the missing artifacts and stop at reference-level reading:

- which policy question was modeled;
- which evidence/data snapshot entered the run;
- where governance or decision-validity gates ran;
- whether the resulting artifact is actionable or needs human follow-up.

## Rollback / Handoff

- if answering requires a code patch, hand the change to the technical owner;
- if the question depends on data-source quality or lineage, involve the Fabric
  or backend owner;

- do not dig into packaging or frontend internals unless they change the policy
  interpretation.

## Troubleshooting

- `ProblemFrame` does not contain all domain semantics: some meaning lives in
  `PolicySpec`, the Fabric data query, and downstream causal contracts;

- if the artifact surface is insufficient, first inspect `timeline`, `lineage`,
  and `decision-validity` instead of opening the source tree blindly;

- for an initial walkthrough, use the tutorial pages rather than lengthy
  historical plans.

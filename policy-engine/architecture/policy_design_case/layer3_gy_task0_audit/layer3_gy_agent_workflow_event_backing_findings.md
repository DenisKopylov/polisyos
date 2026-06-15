# GY Agent Workflow Event Backing Audit

Date: 2026-06-14
Scope: Task 0 audit-only pass for NL agent workflow event backing.
Primary artifact: `layer3_gy_agent_workflow_event_backing_audit.json`

## Bottom Line

The NL runtime path does invoke PI, DataNeedExtractor, Drafter, Formalizer, and
Critic. A temp simulated NL run proved 13 runtime steps, including the five
agent roles, are carried in `llm_model_variants[].steps[]`. The `/runs/{run_id}/agents`
surface can project those steps through the debug service.

That is useful runtime telemetry, but it is not G6 event backing. There are no
dedicated persisted role-event artifacts for PI, drafter, formalizer, or critic,
and the committed G6 `AgentRunRecord` is a readiness projection for
`req-layer3-g6-readiness`, not a live NL run record.

## Execution Facts

Two no-network simulated NL probes were run through the real
`ControlPlaneService._execute_nl_pipeline(...)` path with `simulated-qwen`,
fake retrieval, and `run_experiment` captured before DAG execution.

The dev-profile probe produced:

- `agent_circuit=true`
- `variant_status=completed`
- `provider=gateway`
- `verdict=APPROVE`
- `step_count=13`
- role steps: `pi_agent`, `data_need_extractor`, `drafter`, `formalizer`, `critic`
- no `prompt_tool_ledger_ref`

The research-profile probe produced the same 13 steps plus:

- `prompt_tool_ledger_ref=sha256:5f31045a3ee25c27d580c6d329c825b9df7d87c8d990d3f8222d75eb92f4f0f0`
- `prompt_tool_authority_status=pass`
- `prompt_tool_step_count=13`
- `prompt_tool_tool_names=[]`
- `reports_index.prompt_tool_ledger_ref` present

The important distinction is that the serious-profile ledger is a
PromptToolParserAuthorityLedger over variant steps. It is CAS-backed parser/status
lineage, not proof that the NL path executed `scientist.agent.tools.run_tool_loop`.

## Role Classifications

| Component | Runtime invoked | Carrier | G6 event-backed? | Classification |
| --- | --- | --- | --- | --- |
| `pi_agent` | yes | `llm_model_variants[].steps[]` | no | `runtime_step_telemetry_only` |
| `data_need_extractor` | yes | steps + `retrieval_context.data_needs` | covered elsewhere for `DataNeedSpec`, not G6 role record | `covered_runtime_step_plus_data_need_contract_elsewhere` |
| `drafter` | yes | `llm_model_variants[].steps[]` | no | `runtime_step_telemetry_only` |
| `formalizer` | yes | steps + downstream `trinity_bundle_ref` | no role record | `runtime_step_plus_output_artifact_not_g6_role_record` |
| `critic` | yes | steps + embedded `critic` payload | no | `runtime_step_telemetry_plus_embedded_payload_only` |
| `prompt_tool_ledger` | serious profiles | CAS artifact + reports index | parser ledger only | `runtime_cas_backed_parser_ledger_not_tool_loop` |
| `scientist_tool_loop` | no on NL path | none | no | `implemented_but_not_orchestrated_in_nl_run` |
| `g6_agent_run_records` | no live NL binding | committed G6 readiness artifact | projection only | `projection_only_not_nl_runtime_event_backed` |

## Source Findings

`nl_pipeline.py` instantiates mock or LLM versions of PI, DataNeedExtractor,
Drafter, Formalizer, and Critic, then wraps each role call in `_capture_step(...)`.
That wrapper records agent/action/status/timing/token/cost fields into `steps` and
emits job progress.

The selected model variant is persisted into `state_payload.params.llm_model_variants`.
`runtime/http/services/debug.py` reads that field and projects nested steps into
`AgentPipelineStep` for `/api/v1/runs/{run_id}/agents`.

For serious profiles, `build_prompt_tool_ledger_from_model_variant(...)` builds a
PromptToolParserAuthorityLedger from the same variant steps and persists it to CAS.
The research probe confirmed this, but also confirmed `tool_names=[]`.

`nl_pipeline.py` has no `run_tool_loop`, `ToolLoopResult`, or
`scientist.agent.tools` references. The actual `run_tool_loop(...)` call is in
`runtime/quality/layer3_bounded_agent.py`, inside the G6 bounded-agent quality
producer, not the NL runtime path.

The committed G6 records are tied to `req-layer3-g6-readiness` and G5 bridge refs.
They are authoritative for G6 routing/readiness projection only; they do not bind
to a live NL run id, control job id, `/runs/{id}/agents`, or CAS role-event chain.

## Plan-Changing Implications

1. Do not add PI/drafter/formalizer/critic as `event_backed` G6 assets in the
   census yet. They are `runtime_step_telemetry_only` unless a dedicated role-event
   artifact or explicit out-of-scope boundary is added.
2. Count `prompt_tool_ledger_ref` as real CAS-backed parser lineage on serious
   NL profiles, but not as tool-loop backing.
3. Keep G6 `AgentRunRecord` as `projection_only_not_nl_runtime_event_backed`
   until it binds to live runtime `run_id`/`job_id` and consumes role-event refs.
4. If GY-2 governance depends on agent workflow truth, the next acceptance signal
   must include a negative test proving variant-step telemetry cannot satisfy a
   G6 role-event requirement by itself.

## Negative Controls To Preserve

- Variant steps alone must not count as G6 `AgentRunRecord`.
- PromptToolParserAuthorityLedger must not count as `ToolLoopResult`.
- `req-layer3-g6-readiness` artifacts must not count as live NL run backing.
- Dev-profile NL telemetry must not imply `prompt_tool_ledger_ref`; the parser
  ledger is serious-profile conditional.

## Next Audit Probe

Run one persisted NL control job through the worker-backed API, then fetch
`/api/v1/runs/{run_id}`, `/api/v1/runs/{run_id}/agents`, the raw
`prompt_tool_ledger_ref` artifact, and the control outbox/diagnostic events. That
will decide whether the existing generic event stream can be promoted into the
producer-root chain, or whether G6 needs new role-event artifacts.

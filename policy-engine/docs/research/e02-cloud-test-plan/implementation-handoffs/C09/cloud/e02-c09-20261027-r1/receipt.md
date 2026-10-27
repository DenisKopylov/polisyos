# C09 normal N7 pre-planner diagnostic receipt

## Identity and admission

- Task/environment: `C09`, token `e02-c09-20261027-r1`, Codex Cloud environment ID
  `6965429cdb308191a0e6eb63cb118ea3`.
- Checkout: `/workspace/polisyos`, attached branch `work` (`refs/heads/work`). The branch label differs
  from the selected published branch, which is an allowed observation for this provisioned task.
- Admitted base: commit `8db01b1076e425b7998b05a658776c991b7bd594`, tree
  `1706923ebe943f1a332dca4860cd145ddd366e36`; the worktree was initially clean.
- Capacity at admission: disk 33,770,192,896 bytes total, 29,082,923,008 bytes available; RAM
  18,883,018,752 bytes total, 14,656,397,312 bytes free and 17,681,293,312 bytes available; no
  swap; 3 online logical CPUs. Disk and RAM are intentionally reported separately.

## Source and input identities

- `tests/_helpers/acquisition_production.py` preimage:
  `95b9ecb849b315b52f91bd12149efec5aedc67fa64ed7ea69f7f6736c46e42ed`.
- `src/polisyos/runtime/quality/generation_cycle.py`:
  `4d82eb434bbcb48e234ceecc5c468224c0311d85ed3c11241b27b762a69d5ba4`.
- `tests/unit/runtime/http/test_control_service_di.py`:
  `95c8bb5c1db535ff644a841416e230eb200dfae681c05e458f9eb1da5ee18f3d`.
- `tests/unit/runtime/quality/test_n7_source_gap_projection.py`:
  `269100d0ca19600a7376575a8c543b25aa5ac8d91d92c40b86341afb4b6bb85e`.
- Tracked r4 proposal:
  `6e8192a2798e648d653809fbb2724d1e65e7924a0c227166076d49b1bd290a3d`.
- Additional readset: `acquisition_planner.py`
  `05a5d0fd34d67fa5a63a0777993eb13a10c5cda80b8c493ac6597181e2d00737`,
  `compiler.py` `01664bd6b6f4863bdead5b420ecbf685fa06985c4fef9e4557a270f1aacfc509`, and
  `acquisition_surface_execution.py`
  `9e6b4b52faafed58ac8764dad9bf2aadec987d225ef7838e5678ccce69b83b71`.

## Delivered footprint

- The r4 proposal was applied without alteration only to
  `tests/_helpers/acquisition_production.py`. Its postimage is
  `f04e9b5fd36eb482d42b3a1570741ad2abb11c9009db1dfed3a9757806ad1a0e`; the complete Git diff has
  SHA-256 `33581a6c2e526b4c694f54082e2ca25742659d8c0ca097aad7696af865d78f06`.
- The diagnostic retains `len(route_cycles) == 1` and adds only the recursive blocked reason,
  counterexample code/class, revision strategy/payload keys, and VOI next action/reason to its
  assertion payload. It changes no product behavior, fixture disposition, provenance check, or
  route closure.
- This receipt and `focused-test-output.txt` are new task-scoped evidence. There are no shared
  generated-family, lock, inventory, schema, client, dashboard, test-file, or product changes and
  no companion proposal is required.

## Static control-flow diagnosis

These are source observations, not runtime findings from this attempt:

1. The value observation turns a `value_blocked` status into a value-gap counterexample. Terminal
   selection then supplies `acquisition_required`; the revision owner maps that terminal to its
   terminal-driven strategy and carries the acquisition requirement in the strategy payload.
2. `decide_next_action` turns an `acquisition_required` terminal into VOI action `escalate` with
   reason `terminal_requires_escalation:acquisition_required`, independently of the scheduler's
   recommendation. A `blocked` VOI action instead makes the enclosing generation run blocked before
   N7 routing.
3. After a cycle returns, `GenerationCycleController.run` first reconciles a blocked VOI action.
   It invokes the N7 planner only when the enclosing terminal disposition is not already blocked.
   Therefore counterexample/revision presence alone does not prove planner invocation.
4. The N7 planning function compiles and persists the requirement basis before deriving routed
   compiler gaps. It emits a bound refusal report for unbound inputs, a routing limitation, or no
   compiled gap; otherwise it invokes `plan_requirement_gap_acquisition`. Every report is context
   bound and persisted/read-verified before attachment to the cycle.
5. Closed-loop execution independently recomputes gaps, compares the planner's exact ordered
   `(requirement_gap_ref, compiled_requirement_ref)` denominator, requires the persisted planner and
   compiler reports when requested, and refuses basis-limitation reports before owner dispatch.
   The downstream WDI surface additionally requires the L1 variable schema, data-requirement family,
   `data_snapshot_release` gap type, `production_snapshot_build` strategy, and exactly one canonical
   variable field.
6. The recursive route helper selects only cycles with an attached planner report. Consequently its
   zero-cycle assertion establishes that no report survived onto the compiled recursive leaf, but it
   does not by itself distinguish a pre-planner blocked terminal, compilation/persistence refusal, or
   later transformation. The added fields are designed to discriminate the first case from the
   remaining cases without asserting a new contract.

## Execution and outcomes

Backend/profile: native Linux x86_64, repository Python 3.14.4 `.venv`, `uv --frozen`, extras
`runtime,test`; private `TMPDIR=/tmp/e02-c09-private` and private XDG cache. No production data,
credentials, browser, live model, or external law were used.

- **ERROR (infrastructure):** the exact focused node never entered pytest. `uv` attempted to
  complete the locked runtime profile, retried the locked `structlog==25.5.0` wheel three times, and
  the environment's outbound tunnel failed. Exit status was 1; measured wall time was 4.713151 s,
  peak RSS 29,428 KiB, user CPU 0.201607 s, and system CPU 0.147407 s.
- **UNRUN:** selected pytest node, JUnit case, positive route assertion, adversarial foreign-scope,
  foreign-source, foreign-variable and refusal controls, property-removal controls, and planner
  source-gap/live-route comparisons. An infrastructure failure is not evidence of a product cause.
- **not_established:** counterexample code/class, revision strategy/payload keys, VOI next
  action/reason, recursive blocked reason, compiler/planner presence and refs, and the precise normal
  source-gap stop. The previous local facts supplied in the assignment remain original metadata,
  not observations of this cloud execution.
- **Smallest next owner action:** in a supported frozen Python 3.14 environment whose lock artifacts
  include `structlog==25.5.0`, rerun exactly:
  `uv run --frozen --extra runtime --extra test pytest tests/unit/runtime/quality/test_n7_source_gap_projection.py::test_n7_source_gap_semantics_survive_compiler_and_fresh_route_read -q -ra`.
  If its expanded assertion still shows a pre-planner blocked terminal, the canonical
  `generation_cycle.py` owner should use those fields to propose the smallest source-bound change;
  C09 makes no such proposal without the deciding runtime observation. Planner correctness remains
  unknown.

## Deciding output and transport

- `focused-test-output.txt` contains the complete measured command output and measurement trailer;
  SHA-256 `0068577ac1ff0f511304e868d08d717750f17ba1aba58b6fafec553d68886b41`.
- Delivery channel: ordinary task Git diff/commit and the supported cloud task diff interface. The
  locator is repository-relative and includes new files; coordinator retrieval and hash
  recomputation remain pending. No inaccessible scratch locator is claimed as delivery.

This diagnostic does not close V4, V7, B16, B32, either LA-051 occurrence, or B09. G acceptance and
finding adjudication remain separate.

## Independent review

An independent read-only reviewer re-read the final helper diff, receipt, deciding output, and the
relevant source control flow. The reviewer reported no blocking findings; independently reproduced
the helper postimage, proposal, Git-diff, and deciding-output hashes; confirmed that the original
assertion remains intact and that no product or target-test file changed; and confirmed that the
receipt separates source inference from the runtime facts left `not_established`. The reviewer made
no file changes. This review is not G acceptance.

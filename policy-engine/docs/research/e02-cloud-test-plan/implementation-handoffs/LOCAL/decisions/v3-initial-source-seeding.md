# V3 initial source seeding and cached no-growth patch preparation

Status: **PATCH ONLY**. This note and the sibling diff are the only outputs written. No product source was edited; no tests, producer route, Git command, or runtime application was executed. The diff is unapplied and requires root review/application.

## Exact source footprint and preimages

The patch changes only these test/helper files:

- `tests/_helpers/acquisition_production.py` — `b3d6d8f8aa6a666d33ff56aa284a3499e45cd677f965e7c686bb947d983d1806`
- `tests/_helpers/acquisition_chain.py` — `0181432ff573222c7960a45ca57d3547d64a745030c9f2065212e4f5a2aabe28`
- `tests/integration/core_runtime/test_acquisition_authority_served.py` — `a209732bb8dd4b5acec574018d64e13c9f43fec6e0eea704538438341ead04e3`
- `tests/integration/core_runtime/test_acquisition_world_growth_chain.py` — `ecaf1ba5af2f39375e99a39d98994913f2afd05259bffaf6168ecb94683478f2`

The four current readbacks match those preimages. The final patch artifact is `LOCAL/raw/v3-initial-source-seeding.patch` (`sha256:739e01d14e14e61abd338b5e5ce59f80fddb4ac6438e32c08f1478e41034502d`, 666 lines).

## Initial source/profile binding

The previous patch draft manually changed an industrial-MSME compiler fixture to fiscal/Ukraine/2024 while preserving the old industrial raw request. That was not a source-backed fiscal profile. This revision binds the producer path to an explicit fiscal NL request instead.

The served positive submits a source string that explicitly names Ukraine (`UKR`), 2024 policy/data time and 2024-12-31 as-of time, a government-balance budget multiplier, the global-tax-rate objective/measure, Ukrainian fiscal-review stakeholders, and candidate-only status. The controlled compiler tool-call fixture is constructed with that same raw request/source surface and exactly one matching lever/objective. Its two `request_text` constraints carry source spans copied from the scope and candidate-only sentences. The real NL builder merges the actual submitted request, validates the DTO, binds those spans against the actual request text, and invokes the deterministic span-support client. The actual worker then persists N4/N5/profile artifacts, which the test reads back through typed refs before route use.

A discriminating negative calls that same builder with the recorded industrial-MSME request while keeping the fiscal candidate tool-call fixture and selected profile available. The fiscal-scope span is absent from that request, so the builder must raise `design_problem_admissibility_unverified` with `fiscal_request_scope:source_span_unbound:request_text`. The served positive asserts the compiler output's request/source surface, fiscal domain, jurisdiction/time fields, selected lever, objective/outcome, and exact constraint spans, and then checks that its selector matches the configured profile. The negative therefore tests source mismatch rejection, not a missing profile marker.

The gateway remains a deterministic local test fixture, not a live LLM judgment or an independent policy authority. It returns a prepared candidate DTO and replays a recorded candidate-generation response under a content-identified synthetic overlay. This patch proposes actual runtime compiler/worker/CAS/profile wiring and source/request binding for the controlled candidate. It does not claim independent model reasoning, grounded causal effects, or a real policy result.

`persist_wdi_route` remains for tests whose property is specifically the contract-testing fixture. The served lineage test instead posts `/api/v1/control/runs/nl`, dispatches the actual control worker, resolves the completed route through `AcquisitionRouteLoop`, and reads the persisted initial N4 source and N5 input before continuing the acquisition and fresh HTTP history readback. The initial N4 origin remains explicitly absent.

## Cached same-content control

Root's retained actual replay reported `16 passed / 5 failed`; all five failures were the stale assertion at `test_acquisition_world_growth_chain.py:556` expecting `acquisition_live_attempt_exhausted` after successful same-route N4 re-entry. The current port measures a repeat against active native membership and returns a typed zero-delta result. The patch reads the `AcquisitionWorldGrowthNoGrowthReceipt` and prior `AcquisitionWorldGrowthAttempt` from CAS, requires unchanged membership snapshots/evidence binding, and checks the attempt and re-entry pointers/bytes remain unchanged. It also requires no transport call, no new re-entry, zero admitted delta, and stable route projection. Separate unknown/corrupt-owner exhaustion and out-of-authority/new-content refusal controls are untouched.

This is `P40 SAME_CLASS_DEEPER`: widen one source→profile→re-entry producer/consumer class across the initial request/profile predicate and cached no-growth readback, not a field-by-field ladder. Relevant patterns are P01/P02 producer/bridge reality, P27 avoiding a duplicate source path, P29/P32 behavioral typed evidence, P38 source/provenance proxy detection, and P40 quantity-level repair. Original B09/B12/B27/B28 and LA046 lineage remain the target; no formal closure is claimed.

## Deciding checks and limits

- Served positive selector: `tests/integration/core_runtime/test_acquisition_authority_served.py::test_served_acquisition_selects_committed_human_authority_and_reopens_worker`.
- Its source mismatch negative uses the actual `build_design_problem_from_nl_request` owner with the original industrial prompt and the same fiscal fixture/profile; it expects a typed refusal for the absent fiscal scope span.
- Cached repeat selector: `tests/integration/core_runtime/test_acquisition_world_growth_chain.py::test_actual_wdi_admits_delta_and_reenters_same_case` (both existing `guarded_cas` parameter values).
- No deciding command was run for this revised patch. The root-supplied `16 passed / 5 failed` output is the only executed result referenced; this packet makes no PASS or closure claim.
- The no-growth helper test checks owner CAS/attempt/re-entry state locally. The served integration retains fresh HTTP history readback for the initial N4/N5/profile lineage.
- After root applies the patch, falsifiers are: remove source-span binding while retaining fiscal/profile markers (the source-basis assertion must fail); submit the original industrial request with the fiscal fixture/profile (the negative must refuse); remove initial N4/N5 persistence while retaining the model id/route markers (typed source-ref assertions must fail); or remove/corrupt the no-growth receipt while retaining markers (typed CAS readback must fail).

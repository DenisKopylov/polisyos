# PolicyOS Agent Instructions

Scope: entire repo. Product root is `policy-engine/`; follow `policy-engine/CONTRIBUTING.md` for style, tests, boundaries, and PR hygiene.

## Operating Model

- Treat this file as the always-on map, not the manual. Add only repo-wide rules here; put detailed or path-specific guidance in docs, package READMEs, or nested `AGENTS.md` files.
- Build working governance, not impressive contracts. A capability is real only when producer, typed artifact, orchestration bridge, consumer, verification, and audit/API/dashboard surface are wired or explicitly out of scope.
- Prefer `wire-existing`, then `extend-existing`, then `consolidate-existing`, and only then `build-new`.
- Treat authority, time, status, rule version, provenance, and audience as semantic load-bearing fields, not metadata decoration.
- Keep edits small, typed, and boundary-aware. Do not refactor unrelated code or touch user changes.

## Where To Look

- Contributor baseline: `policy-engine/CONTRIBUTING.md`.
- Architecture boundaries: `policy-engine/architecture/imports/policy.toml`, `policy-engine/architecture/public_surface/contract.toml`, package `README.md` files.
- Public/generated surfaces: `policy-engine/docs/reference/public-surface.md`, `policy-engine/docs/reference/generated-artifacts.md`.
- Policy Design Case failure/repair register: `policy-engine/docs/reference/policy-design-case-failure-patterns.md`.
- Canonical paths, not shims: `scientist/evidence/claims`, `scientist/orchestration/orchestrator`, `scientist/orchestration/workflows`, `data_forge/domains/*`, `foundry/agent_sim/world`.

## Pattern Lifecycle

For every nontrivial task, including plans, backlogs, specs, ADRs, research handoffs, docs, tests, and code, ask:

- Are we about to repeat a known anti-pattern?
- Did exploration reveal an existing anti-pattern in the touched code?
- What is the smallest correct pattern that closes or avoids it?

For any governance, evidence, runtime-quality, PDC, producer, API, dashboard, export, LLM-authority, or research-plan work, open the failure/repair register before design and again before closeout:

`P01` contract-only capability; `P02` thin orchestration; `P03` hidden internal richness; `P04` status lattice gap; `P05` authority boundary leak; `P06` shim drift; `P07` rule replay gap; `P08` time-role conflation; `P09` warning lifecycle gap; `P10` semantic adequacy gap; `P11` failure-only memory; `P12` producer handshake gap; `P13` governance gravity; `P14` evidence independence inflation; `P15` LLM speculation laundering.

Capability reality check: `typed contract/artifact + producer + persisted artifact/event + orchestration bridge + consumer + verification + external/audit/API/dashboard surface or explicit out_of_scope + negative/e2e semantic test`. If incomplete, name the state precisely using the register labels, such as `contract_only`, `producer_missing`, `artifact_missing`, `bridge_missing`, `consumer_missing`, `verification_missing`, `implemented_but_not_orchestrated`, `surface_missing`, `surface_out_of_scope`, or `semantic_test_missing`.

Planning rule: any plan/backlog/spec/ADR touching these areas should include a short pattern pass: relevant IDs, existing anti-patterns found, target correct pattern, missing capability labels, and acceptance signal. Do not turn unresolved research questions into code contracts.

Repair priority: first authority/status/soft gates (`P05`, `P04`, `P09`) and LLM/projection authority (`P15`, `P05`, `P10`), then producer/bridge reality (`P01`, `P02`), external surfaces (`P03`), rule/time reproducibility (`P07`, `P08`), evidence-strength truthfulness (`P14`), and complexity budget (`P13`).

## Implementation Bar

- New capability claims need an end-to-end demonstration: input condition -> producer -> persisted artifact/event -> orchestration/lifecycle effect -> consumer/API/dashboard/audit export.
- Governance/evidence work should prioritize bridge tasks: claim binding, reissue triggers, invalidation paths, uncertainty refs, admissibility composition, closeout gates, and multi-audience projections.
- Artifacts crossing workflow boundaries should carry authority purpose, provenance, rule/schema version, and relevant time semantics.
- New enums/gates require composition rules and mixed-outcome tests, especially for `warn`, `partial`, `near_binding`, `contested`, and `review_required`.
- Avoid constructor-only contract tests. Add at least one negative or integration-style test proving the signal is produced and consumed.

## Commands

- Bootstrap/doctor: `cd policy-engine && python3 -m tools.cli workspace bootstrap && python3 -m tools.cli workspace doctor`
- Fast backend verify: `cd policy-engine && python3 -m tools.cli workspace verify --backend-only`
- CI parity: `cd policy-engine && python3 -m tools.cli workspace ci-parity --skip-browser`
- Architecture guardrails: `cd policy-engine && uv run polisyos-tools architecture guardrails check`
- Runtime contract: `cd policy-engine && uv run --extra runtime --extra ml polisyos-tools runtime check-runtime-api-contract`

Use `rg`/`rg --files` for search, keep tests mirrored under `tests/`, public APIs fully typed, Pydantic public DTOs strict (`extra="forbid"`), and Google-style docstrings for public modules/classes/functions.

## Instruction Hygiene

- Keep `AGENTS.md` short enough to scan in one pass; target under roughly 100 lines.
- Add a rule here only when it is stable, repo-wide, and repeatedly useful. If it is long, conditional, or subsystem-specific, link to a doc or create a scoped instruction file.
- When an agent or review finds a repeated failure mode, update the pattern register with the diagnostic question and closure move instead of adding narrative here.

# PolicyOS Agent Instructions

Scope: entire repo. Product root is `policy-engine/`; follow `policy-engine/CONTRIBUTING.md` for style, tests, boundaries, and PR hygiene.

## North Star (read first — what we are building)

We are building a **causal operating system for policy**, and its ratified identity is the **epistemic custodian of policy justification**: the system proves *why* a policy recommendation, limitation, abstention, or publication is admissible — and keeps that justification honest for the whole life of the policy. Everything reduces to **data**; abstractions ("worker", "firm") are not objects but **communities over a causal variable graph** (an SCM) — but the causal *structure* (which variable affects which) is a distinct, harder, partly-irreducible knowledge, not just data. An **intervention** is a `do()` operation (direct state edit) carrying a predicted distribution over downstream change `P(Y|do(X))` (indirect); its atom is *(one operator, one target-slot, one bundle of direct effects, one declared intended effect)*, relative to the world-model resolution — goals are a separate selection layer. A **design** composes many atomic interventions, checked individual → pairwise → **joint** by **simulation in the world model**. Data is **required vs available**; the gap is filled by **VOI-driven acquisition** (demand paging). The real product is the **growing causal world model**; policies are programs against it; a deployed policy is monitored in two contours — **confirmatory** (high-authority Bayesian effect update) and **exploratory** (low-authority anomaly discovery under false-discovery control) that grows the model. The **safety kernel** is the honest-grounding firewall: every effect/abstraction/value is a **candidate until grounded + validated**; the worst failure is a **confident-wrong effect** shipped on a fake/weak coupling. Full frame: `policy-engine/docs/system-design-decisions/policy-design-causal-operating-system-north-star.md`; the law: `.../universal-policy-design-system-vision-and-organizing-rules.md`.

## Identity And Boundary (ratified 2026-07-20 — applies to every task, however local)

- **The signature rule:** PolicyOS owns everything it signs, for exactly as long as the signature publicly stands; it consumes everything others sign as **typed evidence**; it makes **no claims it cannot custody**. A claim honest at t0 silently becomes false when law, data, calibration, or the world changes — so epochs, staleness, revalidation, and the perturbation cascade are the *completion* of honesty, not optional operations.
- **Three roles:** design authority (grounded design or costed refusal-with-a-path) · justification custodian (every published signature stays honest over time) · post-deployment learning loop. **Binding anti-roles:** not an administrator, executor, case-management system, court, notification channel, payment system, or CRM — those are other institutions' signatures.
- **Scope questions are adjudicated, not debated:** apply the four-way test — absence makes OUR published claim silently false → **own**; output changes our claims' validity → **integrate** (we own the typed fail-closed evidence contract, not the function); changes only who answers for claims → **observe**; else → **out_of_scope**. Rulings and procedure: `policy-engine/docs/system-design-decisions/policyos-identity-and-custody-boundary.md`.
- **Classify one plane at a time** (`S0-K03`) — the test breaks on a mixed row. The chain is: external institutional act → evidence emission → our receipt/verification/admission → our scoped claim reaction → public projection. Decompose a row that spans several *before* letting it constrain work. Related: fail-closed binds the **authority** band — protected actions, published claims, custody facts (`S0-K06`); the candidate band may work under unknown scope with a **declared** unknown carried forward as a typed limitation. Silently substituting a concrete scope for an unknown one is the violation; a declared assumption is not. The sixteen ratified custody invariants: `policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md`.
- **Extensions:** take those that are *projections of already-built core* (cascade → appeal ingestion; epochs → staleness surfaces; DDM → KPI contract); decline those requiring a new sovereign subsystem. When your local task seems to need an out-of-boundary function, the deliverable is the integrate-contract, never ownership.

## Operating Model

- Treat this file as the always-on map, not the manual. Add only repo-wide rules here; put detailed or path-specific guidance in docs, package READMEs, or nested `AGENTS.md` files.
- Build working governance, not impressive contracts. A capability is real only when producer, typed artifact, orchestration bridge, consumer, verification, and audit/API/dashboard surface are wired or explicitly out of scope.
- Prefer `wire-existing`, then `extend-existing`, then `consolidate-existing`, and only then `build-new`.
- Treat authority, time, status, rule version, provenance, and audience as semantic load-bearing fields, not metadata decoration.
- Fix the class, not the instance (`P31`): when a defect is one case of a class — authority emitted from unverified evidence, bytes leaving a surface ungated — close it with one structural invariant (single intake AND single emission), not a per-site patch; a sibling consumer reopens an instance fix.
- Verify substance, not form (`P32`): an authority/promotion/Ring-2 decision admits evidence only by resolve + content-bind + verifier-provenance; presence/shape/keyword/string/self-attestation is not evidence, and absence fails closed.
- A probe is a witness, not the spec (`P33`/`P34`): fix the general property and self-generate adversarial variants (synonym, malformed, present-but-fake, sibling consumer) before claiming done; finish a revert/stash isolation before excluding a failing test as honest/unrelated.
- Enumerate the set; cite the finding, not the prose (`P35`/`P36`): every set-level fact you state — a count, a distribution, "the field is always X" — comes from a script walking the COMPLETE set, quoted with its denominator, never from one sampled member or a truncated `grep -A N`. Every claim you take from an authoritative document is cited by its finding ID; an aside in an authoritative source carries that source's tone, not its warrant, and arithmetic is reproduced from the pinned owner. When you correct an inherited claim, grep the binding key (`bound_*`, the ID) and fix every dependent reference — repairing the narrative is not repairing the binding.
- A gate must exercise the property, not check markers (`P29`): a validator/contract guarding a semantic property (a runtime cap, a round-trip, a strangle, a promotion rule) must import and run the real path and assert the property holds/fails — not confirm that marker strings or field names are present. Prove it with the *remove-the-property-keep-the-markers* probe: if the gate stays green when the runtime property is deleted but its markers remain, it is form-based and must be rewritten to behavioral. Stopping point: a verifier is *complete-by-construction* when it is GENERIC over the source of truth (derives its set from the runtime's rejection reasons / the artifact's schema / the actual objects — no enumerated list) with genuine exemptions (a "justified default-only" field must be truly type-constrained, e.g. a `Literal`, not a `str` loophole). Past that, coverage of future additions is governed by this rule + review — do not recursively verify the verifier; a merely hypothetical future gap against a generic mechanism is a GO, not a NO-GO.
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

`P01` contract-only capability; `P02` thin orchestration; `P03` hidden internal richness; `P04` status lattice gap; `P05` authority boundary leak; `P06` shim drift; `P07` rule replay gap; `P08` time-role conflation; `P09` warning lifecycle gap; `P10` semantic adequacy gap; `P11` failure-only memory; `P12` producer handshake gap; `P13` governance gravity; `P14` evidence independence inflation; `P15` LLM speculation laundering. Newer rows are in the register: `P16`–`P26` universal-design axes; `P27` owner-bypass duplication; `P28` un-strangled legacy; `P29` authorial proof; `P30` provenance naming; `P31` instance-patching; `P32` trust-by-form; `P33` teaching-to-the-test; `P34` uncompleted-exclusion green; `P35` sampled-denominator generalization; `P36` authority by adjacency.

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

During iteration, verify by blast radius — the changed modules plus their importer tests, the recomputing validators (`--check` + a corrupt-field drift that must fail), `ruff`, and architecture guardrails — rather than the full suite; reserve the full backend-verify/CI-parity for closeout.

Use `rg`/`rg --files` for search, keep tests mirrored under `tests/`, public APIs fully typed, Pydantic public DTOs strict (`extra="forbid"`), and Google-style docstrings for public modules/classes/functions.

## Toolchain Facts (measured — do not re-derive per worktree)

- **Silently wrong if skipped:** `corepack pnpm` (never bare `pnpm`) — run
  `corepack pnpm install --frozen-lockfile` in a fresh checkout **before trusting any TypeScript
  scanner**, since missing `node_modules/@polisyos/*` links make generated-owner proofs emit false
  findings. Edit governed JSON **surgically**; a full `json.dumps` reformat is rejected even when the
  parsed content is identical.
- **Fails loudly:** `ruff` is a module (`.venv/bin/python -m ruff`); macOS has no `timeout`; zsh needs
  glob flags quoted (`--include='*.py'`); repo-root Prettier is absent (a missing formatter is a
  tooling non-receipt, never a product failure); `rm -f` and writes outside the repo are blocked —
  use the harness scratch; worktrees have no `production_data` and no venv (link data read-only,
  provision `--offline`), and some capstone validators require an isolation-local `.venv`.

## Work Preservation, History, Verification Economics

Full statements: GY plan §3.5.7 (E11–E14) and §3.5.13; Atlas plan Execution Doctrine.

- **Uncommitted work is not storage.** Commit at every clean boundary; a stash is a transient for
  minutes, never a place to leave work across a stop, handoff, or compaction. A validator demanding
  a clean tree is satisfied by **committing**, not stashing.
- **History is append-only.** No `rebase`, `reset --hard`, `reset` onto an ancestor, `push --force`,
  `filter-branch`, `stash drop`/`clear`, or `checkout` that moves HEAD off current work. **One
  exception:** `--amend` on the immediately preceding commit you authored this session and have not
  handed to review. **Unexpected HEAD/branch/tree state → stop and report, never self-repair.**
- **Verify branch attachment, not just cleanliness** — at session start and before every commit:
  `git status -sb` (or `git symbolic-ref -q HEAD`). A detached worktree looks completely normal to
  `git log -1` and `git status --short`, and a commit made there is orphaned from the branch.
- **Freeze source → all reviews → run the expensive wave once.** A review landing after the wave
  re-prices it. Post-freeze: cosmetic finding → recorded debt; blocking finding → batched.
- **Serialize only the contended resource** (shared owner scratch/DuckDB, Playwright/Storybook,
  fixed-port server, same governed artifact) — name it in the task plan. Lint, typecheck, logic
  tests, builds and read-only censuses run in parallel with a long replay.
- **Measure each suite's wall time once, then set explicit timeouts** (an unmeasured default that
  kills a healthy run is a harness finding). **Delta-only re-review** after the first full package.
  **Poll silently** — state changes only; heartbeat evidence, never heartbeat prose.

## Instruction Hygiene

- Keep `AGENTS.md` short enough to scan in one pass; target under roughly 100 lines.
- **Rules with different motivations get separate lines and their own stated reason.** A bundled
  clause is followed in the shape it was written: "no merge, no push, no rebase" mixed a
  *publication* rule with a *history* rule, and the history half was dropped. Never name a specific
  commit hash in an instruction — name the relationship ("the immediately preceding commit you
  authored"); a hash is true when written and a trap after any legitimate recovery.
- Add a rule here only when it is stable, repo-wide, and repeatedly useful. If it is long, conditional, or subsystem-specific, link to a doc or create a scoped instruction file.
- When an agent or review finds a repeated failure mode, update the pattern register with the diagnostic question and closure move instead of adding narrative here.

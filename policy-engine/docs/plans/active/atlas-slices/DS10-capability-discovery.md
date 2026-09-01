---
plan_id: atlas-ds10-capability-discovery
title: "DS10 - Capability Discovery"
type: slice-plan
status: implementation_receipts_complete_unmerged
created: 2026-08-25
last_verified: 2026-08-25
stability: verified_unmerged
slice: DS10
baseline_commit: c31c8cec725727637ee986e4541ac7926a553513
branch: codex/ds10-capability-discovery-plan
master_plan: ../POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md
surface_constitution: ../../../system-design-decisions/policyos-atlas-surface-constitution-and-frontend-vision.md
identity_boundary: ../../../system-design-decisions/policyos-identity-and-custody-boundary.md
failure_register: ../../../reference/policy-design-case-failure-patterns.md
layer3_roadmap: ../POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER3_GROUNDING_SUBORDINATION_IMPLEMENTATION_PLAN.md
debt_register: ../DEBT-REGISTER.md
disposition_register: ../../../../architecture/atlas_surfaces/frontend-disposition-register.json
audiences: [REVIEWER, EXPERT, MACHINE]
frontend_owner: team-design
registry_gate_owner: team-architecture
registry_producer_lane: runtime/quality
feature_flags: none
depends_on:
  - ../POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md
  - ../../../system-design-decisions/policyos-atlas-surface-constitution-and-frontend-vision.md
  - ../../../system-design-decisions/policyos-identity-and-custody-boundary.md
  - ../../../reference/policy-design-case-failure-patterns.md
  - ../POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER3_GROUNDING_SUBORDINATION_IMPLEMENTATION_PLAN.md
---

# DS10 - Capability Discovery

## For agentic workers

This is an approval-gated implementation plan, not authorization to implement.
The planning branch `codex/ds10-capability-discovery-plan` was attached and clean
at immutable `main` base `c31c8cec725727637ee986e4541ac7926a553513` before
this file became its sole change. The repository coordinate is always measured
with `git rev-parse --show-prefix`: from the product root it is `policy-engine/`,
and from the repository root it is empty. Root alone writes. Before every future
commit, re-read `git status -sb`, `git symbolic-ref -q HEAD`, the prefix, and the
cluster path fence. Before approval: no production code, writer, register lock,
regeneration, visual lane, merge, push, rebase, stash storage, or master-plan
line-7 edit.

The front-matter `last_verified` value deliberately remains the approval-era
date: the task's binding no-line-7 rule survives implementation. C07's
2026-08-26 verification date and receipts are recorded in the execution journal
instead of mutating that sentinel.

After approval, C00 starts from the attached execution branch containing this
plan. Adapter-registry data-only free growth is **not established at the pinned
base**, but that upstream backend gap is not a DS10 gate: C00 registers it as
owned debt and continues. DS10's binding free-growth property is frontend
genericity: a correctly formed capability row, established through one of the
six resource kinds' real owner indexes and admission paths, renders with zero
dashboard production-code change. DS10 may consume that owner path; it may not
redesign post-G0 adapter admission.

Use `corepack pnpm`, never bare `pnpm`. Do not run `guardrails sync`. Run only the
targeted commands named here. Generated output is produced only while holding the
regeneration token; visual snapshots only while holding the visual lane. No two
serialized resources co-hold.

## Mission and boundary

DS10 makes Laws 2 and 12 executable: navigation and pickers search typed indexes
whose contents can grow without frontend source edits. It exposes methods,
datasets, sources, legal norms, cases, and Scientist agent/tool capabilities;
renders `discoverable`, `executable`, and `admitted_authority` from independent
producers; shows selected and rejected candidates, real cutoffs, freshness, and
incompleteness; and separates fixed application chrome from open-ended
capability discovery.

DS10 does not make discovery authoritative, infer execution from an index row,
infer authority from `admitted=true`, create adapter-registry content, invent a
global case index, turn L4 world-agent rows into UI capabilities, trigger Lex as
an implication of discovery, or render decisions publicly. `discoverable` always
wears candidate clothing. At the pinned base current production content honestly
produces no `admitted_authority` positives because the typed owner binding is
absent; the negative is the product state, not a reason to mint one.

The opening capability state is `producer_missing + bridge_missing +
consumer_missing + surface_missing + semantic_test_missing` for DS10 as an
end-to-end capability. Existing contracts and row artifacts reduce effort but do
not close that chain.

## Canonical Closure Contract

DS10 closes only when every checkbox below has its named receipt. No cluster may
define a second closure contract.

- [x] **CC01** The approved plan, exact execution base, attached branch, prefix,
      clean-tree predicate, path fences, and red witnesses are re-read before
      every commit.
- [x] **CC02** The upstream data-only registry-growth gap is registered as
      `ds10-adapter-registry-data-only-free-growth`, owned by
      `team-architecture` with producer lane `runtime/quality` and the exact
      executable closure signal below. It is not a DS10 blocker and is not
      `admitted_authority`.
- [x] **CC03** One canonical strict contract owns the six resource kinds, three
      independent posture arms, typed negatives, authority purpose, provenance,
      schema/rule versions, and time/freshness semantics; G0 imports rather than
      duplicates its vocabulary.
- [x] **CC04** `discoverable` is established only by a searched typed-index row
      plus snapshot/freshness evidence; no match, unavailable index, stale index,
      and incomplete index are distinct negatives.
- [x] **CC05** `executable` is established only by the real operation/adapter
      registry, conformance, and current execution policy; an index hit or best-
      effort fallback cannot establish it.
- [x] **CC06** `admitted_authority` is established only by the conjunction of the
      deployed DS9 `ProductionApprovalPacketResolver.require_currentness` result
      and a separately owner-signed typed capability-ref/digest and
      authority-purpose binding that content-binds to the packet's existing
      expected consumer/audience. That binding is absent at the pinned base, so
      every current positive authority arm is `not_established`.
- [x] **CC07** Falsifying any one posture producer while retaining the other two
      cannot promote or preserve that posture; status precedence and mixed arms
      are permutation-invariant.
- [x] **CC08** Methods, datasets, sources, legal norms, cases, and Scientist
      agent/tool capabilities each have one declared provider or a typed
      producer-negative; L4 world-agent data is not silently substituted.
- [x] **CC09** At the pinned base, case search renders `producer_missing` and an
      incomplete frontier because the global case index is `absent/unallocated`;
      DS10 adds no case store or index builder.
- [x] **CC10** One persisted/replayable frontier projection carries the request,
      selected and rejected candidates with reasons, actual cutoffs, searched
      index refs, freshness, replay key, and typed incompleteness.
- [x] **CC11** A true no-hit, recall-unmeasured result, stale index, budget cutoff,
      and producer outage render differently; none justifies abstention or
      authority.
- [x] **CC12** `GET /control/capabilities` contains no authored open-ended feature
      rows: each of its opening 21 entries is removed, registry-projected, split,
      or moved to a typed fixed/policy/roadmap owner exactly as adjudicated below.
- [x] **CC13** The complete 21-key opening constructor set has one and only one
      keyed one-time baseline adjudication. A Python import-aware AST check fails
      any direct constructor contributing to manifest `features`; the existing
      type-aware TypeScript check fails contextual feature literals.
- [x] **CC14** Fixed workspace/route/tab chrome is resolved by an explicit local
      `SurfaceAvailability` owner and never by a discovery result; open command-
      palette/picker results come only from the typed search response.
- [x] **CC15** The exact free-growth e2e test admits one correctly formed
      `legal_norm` capability row through the real Lex owner index and its
      grounding/temporal admission path, rebuilds the real capability index, and
      renders its generated ID through the real FastAPI route, hook, and panel
      with zero tracked
      `apps/runtime-dashboard/src/**` production-byte change. Backend admission
      data may change through its real owner path; no fixture response or
      substituted provider may satisfy the witness. Execution is established
      only by its independent producer, and authority remains `not_established`
      unless the independent owner-signed binding exists.
- [x] **CC16** Three bounded controls go red independently: an import-resolved
      backend manifest constructor, a contextual generated-TypeScript feature
      literal, and a literal `capability_ref`/adapter-ID/resource-kind branch or
      row array inside the generic discovery-render boundary. Fixed typed
      `WorkspaceConfig`/surface chrome remains a benign control.
- [x] **CC17** The canonical search endpoint, the data-catalog compatibility
      projection, OpenAPI, both generated client families, the dashboard hook,
      and route prefetch share one response contract and existing read authz.
- [x] **CC18** REVIEWER/EXPERT surfaces keep candidate clothing inseparable from
      discoverable results, announce typed negatives/no-hit reasons, and pass the
      named keyboard, screen-reader, contrast, and visual cases.
- [x] **CC19** MACHINE downloads the exact captured endpoint bytes; a DOM decoder
      independently reconstructs the full result/frontier packet and detects
      omitted, reordered, or mutated selected/rejected/posture fields.
- [x] **CC20** All ten DS10-owned root register objects are adjudicated once;
      register writer/check/corruption tests and ledger diff agree, with no
      family-complete claim beyond that set.
- [x] **CC21** Generated OpenAPI/client ABI outputs reproduce byte-for-byte from
      two fresh scratch roots, and all named targeted backend, frontend,
      architecture, a11y, and visual commands complete within frozen ceilings.
- [x] **CC22** The final branch readback proves the closure-item receipts, exact
      changed-path set, cap/round accounting, serialized-resource release,
      executable debt ownership, and every item in `## Explicit non-closure`.

### Implementation receipt index

The detailed red/green commands, elapsed times, uptime pairs, invalidated freezes,
and commit readbacks live in the execution journal. This index binds each closed
item to the smallest durable witness; typed negatives and declared non-closures
remain closure evidence rather than being promoted to positives.

| item | durable implementation receipt |
| --- | --- |
| CC01 | C00-C07 identity/path-fence/readback entries in the journal and the final attached-branch readback |
| CC02 | `ds10-adapter-registry-data-only-free-growth` in `DEBT-REGISTER.md`; its exact absent-test command remains `artifact_missing` |
| CC03-CC07 | canonical strict contracts plus mixed/permutation/falsified-producer tests in `test_capability_discovery.py`; execution reads the independent policy resolver and authority stays fail-closed |
| CC08-CC09 | six-kind provider federation and API tests; `case` returns `producer_missing` with an incomplete frontier and no new case index |
| CC10-CC11 | replay/frontier contract, API, panel, exact-twin, no-hit/recall/stale/outage tests, and the two visual witnesses |
| CC12-CC13 | zero live authored manifest contributors, exact 21-key adjudication, import-resolved Python strangle, and contextual TypeScript strangle |
| CC14 | `SurfaceAvailability` owner tests plus generic command-palette search/selection into the evidence query |
| CC15 | `test_new_legal_norm_owner_row_appears_without_frontend_code_change`: artifact-absent RED, then real Lex owner-index/FastAPI/hook/panel GREEN with complete test-start frontend byte equality |
| CC16 | backend constructor, contextual generated-feature literal, and generic-render enumeration/ID-branch corruption controls; fixed chrome is the benign control |
| CC17 | shared canonical/compatibility route tests, OpenAPI/runtime client regeneration, strict dashboard hook, and route-prefetch tests |
| CC18 | candidate badge/typed-negative semantic tests; strengthened opaque-backdrop numeric WCAG-AA, keyboard, screen-reader, and two-snapshot visual receipts |
| CC19 | captured response bytes equal MACHINE download; independent DOM decoder omission/reorder/mutation tests and free-growth DOM parity |
| CC20 | surgical ten-root writer, exact five/five partition, 261 live-root and 217 DS8-assignment denominators, byte preservation, and corruption rejection |
| CC21 | C04 two-scratch ABI reproduction and C07 targeted backend/frontend/architecture/a11y/visual receipts within the frozen ceilings; declared non-receipts remain excluded |
| CC22 | 46/50 mechanism-path and 14/15 round derivations, serialized-resource release checks, debt/non-closure audit, C07 commit, and post-commit attached-branch readback |

## The four design problems and their rulings

### 1. The postures do not collapse

The API carries three sibling results, not one ordinal/max enum. A positive arm
names its producer and proof; a negative arm names why that producer could not
answer. The aggregator may display all three but may not derive one from another.

| posture arm | sole establishing producer | P37 basis | typed negative when producer cannot answer |
| --- | --- | --- | --- |
| discovery | provider-owned search against a content-bound typed index snapshot (`CapabilityIndex`, L1 DCAT, source-profile/connector registry, L3 Lex index, Foundry/Scientist registries) | `recomputed` | `no_match`, `index_unavailable`, `index_stale`, `incomplete` |
| execution | provider-owned live operation/adapter registration **and** current conformance **and** `RuntimeExecutionPolicyResolver` result | `independently_reconciled` | `not_executable`, `execution_blocked`, `not_established`; retain the concrete reason such as `connector_missing`, `parser_unsupported`, `policy_disabled`, or `conformance_failed` |
| authority | conjunction of deployment-issued `ProductionApprovalPacketResolver.require_currentness` **and** a separately owner-signed typed binding of `capability_ref`, digest, and `authority_purpose` to that packet's existing expected consumer/audience | `independently_reconciled` only after both producers verify; otherwise `not_established` | `candidate_only`, `producer_missing`, `bridge_missing`, `artifact_missing`, `invalid_source`, `revalidation_required`, `authority_blocked`, `not_established` |

`AdapterAdmissionRecord.admitted`, G1/G3 conformance, an execution flag, a human-
decision ref, and a search rank are evidence inputs, never the final authority
predicate. DS9's human-act boundary is authoritative for the human act, not for
publication or claim evidence. Its current packet has expected consumer/audience
currentness but no typed capability ref, capability digest, or authority-purpose
binding; the opaque `governed_action_key` is not a semantic join (P32/P37). DS10 may define and
consume the fail-closed integration port, but cannot parse that key or create the
missing owner signature. Positive authority is therefore absent at this base.

### 2. The 21 entries are 21 decisions

The opening manifest mixes fixed chrome, open registry capability, execution
policy, roadmap posture, and several entries that combine two of those planes.
The keyed adjudication below is binding. A bulk “all fixed” or “all discovered”
rewrite fails CC13.

### 3. Free growth is the architecture test

The decisive property is:

> A correctly formed new capability row appears after its real owner index and
> admission path are rebuilt, with zero frontend production-code change.

The test is designed before the endpoint or component. It uses the canonical
Lex owner database, real capability-index compiler, and production Lex discovery
provider; it does not seed an HTTP response, MSW result, frontend fixture,
hardcoded capability ID, direct DTO constructor, or test provider double as its
positive proof. The complete dashboard source digest and invalid-row sibling
make frontend genericity and the fail-closed half executable. Backend owner data
is not part of this invariant. The new row is discoverable; execution stays with
its independent registry/conformance/policy producer, while authority honestly
remains `not_established`.

### 4. Frontier honesty is part of discovery

Results and frontier are one response. The visible surface includes the request,
selected candidates, rejected candidates and rejection reasons, actual cutoff,
searched indexes, freshness/recall status, no-hit frontier, and incompleteness.
Rendering only hits is `surface_missing` for DS10 even when the list looks useful.

## Measured entry receipts

### Base, coordinate, and timing receipts

| item | pinned receipt |
| --- | --- |
| base | attached `codex/ds10-capability-discovery-plan`; `HEAD == main == c31c8cec725727637ee986e4541ac7926a553513` before the plan edit |
| entry gates | `c77888b7c3a910081f966b232956b0756d7d4306` is an ancestor of the base (exit 0); `uv run polisyos-tools architecture guardrails check` passes on the attached branch whose sole change is this plan, including both generated-client freshness families; 177.8s tool wall, uptime `12:46 up 1 day, 2:59` -> `12:49 up 1 day, 3:03` |
| coordinate | product-root `git rev-parse --show-prefix` = `policy-engine/`; repository-root result = empty; top level `/Users/deniskopylov/polisyos` |
| baseline debt projection | exact stdout says `register_ids=59`, `gy_ids=38`, `atlas_debt_rows=22`, `frontend_disposition_rows=217`; source read proves the last label actually counts `ds8_strangle_coverage.assignments`, so its property name here is `ds8_strangle_coverage_assignments=217` (P38), while the live root register is separately 261 rows; only the ten known `register_supplies_missing_standing` and one `register_withholds_source_standing` informational rows; 0.99s, uptime `12:06 up 1 day, 2:19` before/after |
| targeted backend comparison | resolver + compiler + G0 posture + live control API, all selected tests green; 147.05s; uptime `12:01 up 1 day, 2:14` -> `12:03 up 1 day, 2:16` |
| targeted dashboard comparison | 5 files / 31 tests green; 13.13s; uptime `12:03 up 1 day, 2:17` -> `12:04 up 1 day, 2:17` |
| regeneration comparison | OpenAPI scratch export 74.83s, runtime client 0.15s, dashboard OpenAPI TypeScript + format 4.83s; uptime pairs `12:04 up 1 day, 2:18` -> `12:06 up 1 day, 2:19` and `12:04 up 1 day, 2:17` -> same minute |

Two failed scratch invocations (`pnpm exec` from the wrong package root, then a
relative schema path resolved under the dashboard) are tooling non-receipts and
set no ceiling. The completed absolute-schema `corepack pnpm --filter` command is
the timing evidence.

### Requested starting-state census

Every set count below has two independent derivations. Disagreement is retained
as a different denominator rather than averaged away.

| fact | derivation A | derivation B | ground truth and known member |
| --- | --- | --- | --- |
| `services/control/capabilities.py` physical lines | `wc -l` | `awk 'END {print NR}'` and pinned `git show ... \| wc -l` | **267**; SHA-256 `a76615dd1a6cbad967095051aeeb7f23d78762b31c9c6a66b26e15f4c931752d` |
| direct authored constructors | Python AST direct `Call` nodes | `tokenize`: `NAME CapabilityFeatureInfo` immediately followed by `(`, excluding comments/docstrings | **21**; known `workflow_runs` at line 52; exact lines `52,59,68,75,84,94,101,108,115,124,131,140,147,154,164,174,184,191,198,206,213` |
| `discoverable` exact string constant in tracked `src/**/*.py` | quoted-string `git grep` | AST string constants over all **2,576** tracked source Python files | **1 file**, `pre_adapter_grounding_inventory.py`; it owns the opening posture triad |
| `executable` exact string constant | quoted-string `git grep` | same AST walk | **2 files**, `pre_adapter_grounding_inventory.py` and `runtime/quality/workspace/loop.py`; broad token search is 5 files/35 tokens because `sys.executable` and identifiers are a different denominator |
| `admitted_authority` exact string constant | quoted-string `git grep` | same AST walk | **2 files**, `pre_adapter_grounding_inventory.py` and `legal_mandate_search.py`; only the former uses it in the posture triad, while the legal file uses the same string as legal status/precondition vocabulary |
| discovery seed | route decorator/source read | OpenAPI operation/source search | `src/polisyos/runtime/http/routes/control.py:715`, `GET /data/catalog/search`; current response has query/matches/total only |
| live frontend register | JSON `len(entries)` + unique `unit_id` set | schema/checker pins the complete DS1 root set and rejects duplicates | **261 rows / 261 unique**, known `route-welcome` |
| supplied “frontend register 217” | JSON `ds8_strangle_coverage.assignments` count/set | surgical-writer preservation test from pinned DS8 preimage | **217 assignments / 217 unique paths**, known `apps/runtime-dashboard/src/features/artifacts/bureaucratic/BureaucraticArtifactView.a11y.test.tsx`; this is an immutable DS8 sub-register, not the 261-row live root |
| DS10-owned live roots | `jq select(.owner_slice=="DS10")` | Python JSON set projection | **10 / 10 unique**, known `route-knowledge` |
| free-growth production-byte denominator | pinned `git ls-tree -r --name-only` path set | working-tree `git ls-files` path set | **3,873 / 3,873 unique tracked paths**: `src/**` 2,786 (`.py` 2,576, `.md` 164, `.csv` 15, `.yaml` 11, `.json` 10, `.pyi` 5, `.cypher` 2, `.typed` 2, `.sql` 1; known `src/README.md`) plus dashboard `src/**` 1,087 (`.tsx` 623, `.ts` 403, `.json` 27, `.md` 18, `.css` 13, extensionless 3; known `apps/runtime-dashboard/src/App.tsx`) |

The tracked `src/**` denominator is 2,786 paths; 2,576 are Python. The user-
supplied file counts are confirmed only for exact string constants, not for a
loose word match that also counts comments, docstrings, and unrelated names.

### Adapter-registry content gate and free-growth precondition

Two complete-set derivations agree that the canonical artifact family contains
five admission JSONs plus five contract TOMLs. Known member:
`architecture/policy_design_case/layer3_adapter_admission_registry.json`.
`git ls-tree` over the pinned tree
and the lifecycle-owner declarations in `architecture/generated_artifacts.toml`
plus the G0 readiness manifest produce the same **10-artifact** set.

Independent `jq` and Python JSON walks agree on **61 admission rows**:

| slice | rows | current meaning |
| --- | ---: | --- |
| G0 | 52 | 51 `candidate_shadow_only`, 1 `blocked`, 0 admitted |
| G1 | 2 | both adapter-conformance admitted for `binding` / `gap_routing` |
| G2 | 0 | summary/refs only |
| G3 | 6 | adapter-conformance admitted |
| GL | 1 | candidate/reference-only |
| total | **61** | **8 admitted, 52 candidate, 1 blocked** |

Known admitted member:
`layer3-substrate-data-binding-to-source-contract`. A `tomllib` walk of all five
contract TOMLs gives **41 declared adapter paths** (G1 2, G2 4, G3 6, G4 11,
GL 18); known path `layer3_data_asset_port_to_source_contract`. The
G1/G3/G4/GL declared count fields and the enumerated G2 refs reproduce the same
partition.

The master-plan entry predicate “meaningful adapter-registry content” is
**satisfied** by this substantive row-level content. The stronger backend
data-only free-growth witness is **`artifact_missing`**; its underlying
data-only free-growth property is therefore **not established**.
The admitted G1 rows are emitted by `_adapter_admissions(...)` as two authored
constructors; G3 admissions are derived from an authored adapter-path tuple; G0
intentionally forbids admission. Adding a new contract row cannot enter the
admitted set by data-only mutation. Nonempty/admitted-row count is therefore a
P38 proxy for the required property.

Current backend data-only free-growth state: `artifact_missing` (underlying
property `not_established`). Accountable owner: `team-architecture`, the owner
of the Layer-3 roadmap and adapter discipline; producer lane: `runtime/quality`.
Exact discharge identity:

```bash
uv run pytest tests/unit/runtime/quality/test_adapter_registry_free_growth.py::test_post_g0_registry_admits_new_contract_from_data_only_mutation -q
```

The test must be tracked, select exactly one test, and prove backend source-tree
bytes unchanged across the mutation. C00 records its absent/skipped/red state as
debt and continues; DS10 does not add the registry producer or content needed to
make it green.

## Six resource-provider adjudication

The finite provider algebra is allowed; enumerating its changing rows is not.
Each provider searches its owner index and returns the same canonical contract.

| resource kind | discovery producer | execution producer | pinned limitation |
| --- | --- | --- | --- |
| method | release `CapabilityIndex` L6/Foundry method-contract records and method-catalog snapshot; the default bridge is currently `producer_missing` | actual Foundry method/operation registration + adapter conformance + execution policy | a method route or backend-availability boolean is not an indexed discovery row, empirical authority, or legal authority |
| dataset | L1 DCAT / existing catalog retrieval search and capability-index snapshot | `RetrievalService` fetch-target resolution + connector/dataset/parser + rights/policy + conformance | `/data/catalog/search` currently drops frontier/postures and becomes a compatibility projection, not a second searcher |
| source | `SourceProfileRegistry` plus connector registry snapshot | concrete connector registration/profile resolver + conformance + policy | DS15 owns connector/acquisition content; DS10 only consumes the registry |
| legal_norm | L3 Lex KG index / existing Lex search projection, preserving grounding, hallucination, jurisdiction, temporal, and frontier fields | registered Lex search operation + index readiness + conformance + policy | scalar confidence/norm type cannot substitute for grounding or authority |
| case | **no producer at the pinned base** | `not_established` | `ds8-global-case-index` is `absent/unallocated`; render `producer_missing`, do not build it |
| agent | Scientist `NodeRegistry` / `ToolRegistry` discovery reports for agent/tool operations | the registered node/tool plus bootstrap/conformance/execution policy | L4 `agent_registry_full.parquet` describes world-model entities and is explicitly not substituted for a capability registry |

For any positive resource, the authority arm separately requires DS9 currentness
and the owner-signed typed resource/purpose binding described above. The second
producer is `bridge_missing` at the pinned base, so present production rows are
`candidate_only`/`not_established` even when discovery and execution are positive.

## Per-entry adjudication of the 21 authored manifest rows

The table has 21 unique keys and its key set equals the AST constructor-key set.
The one-time baseline partition is **3 fixed chrome + 3 registry discovery + 9
split-plane + 5 execution-policy projection + 1 roadmap status = 21**. “Split”
means two independently produced records, never one row promoted across planes.
A Python Markdown-table parser joined to the AST key set and an independent
`awk` ruling-column histogram reproduce both the 21 total and this partition.
The table is a conservation receipt, not a future whitelist; the generic lint
below derives its production denominator without enumerating these keys.

| line / key | current producer, metadata, and target/consumer evidence | plane ruling | accountable owner and closure action | typed residual if owner cannot answer |
| --- | --- | --- | --- | --- |
| 52 `workflow_runs` | literal `enabled=True`, category `runs`; gates `/compose` and `/runs` in `app/workspaces.ts` through `WorkspaceBoundary.tsx` | fixed chrome | `team-design` / `app/surfaces`: remove manifest gate; express both routes in `SurfaceAvailability` | a separately searched run-kind row is `producer_missing`, not inferred from the route |
| 59 `natural_language_runs` | literal `enabled=True`, `runs`; gates the fixed run-agents tab in `app/surfaces/surfaceRegistry.ts`/`runDetailTabs.ts` | fixed chrome | `team-design`: keep tab/route availability local; NL job availability stays with `runtime/http` operation policy | operation posture `not_established` if no live registration/policy answer |
| 68 `multimodel_nl` | env helper `_is_multimodel_enabled`, `runs`; `LaunchRunPage.tsx` gates form state and sends highlights to `ComposerModeSections.tsx` | split | `foundry/methods` owns searchable method registration; `runtime/http` execution policy owns enablement; composer consumes only execution arm | discovery `producer_missing` or execution `not_established`, independently |
| 75 `scientist_v2` | env helper `_is_scientist_v2_enabled`, `runs`; no keyed dashboard consumer, only generic Header/Platform/Fabric manifest rendering; `control/nl_pipeline.py` executes it | split | Scientist `NodeRegistry`/`ToolRegistry` owns agent discovery; `runtime/http` policy owns execution; retire generic card if no typed result consumer | discovery `producer_missing`; execution `policy_disabled`/`not_established` |
| 84 `scientist_shadow_mode` | env helper `_is_scientist_shadow_mode`, `runs`; no keyed dashboard consumer; `control/nl_pipeline.py` reads policy | execution policy | `runtime/http` execution-policy owner: project candidate/shadow rule, epoch, and expiry outside search results | `not_established` or `policy_disabled`; never discoverable by virtue of the flag |
| 94 `required_preflight` | env helper `_is_required_preflight_enabled`, `governance`; `LaunchRunPage.tsx` gates composer and passes state to `ComposerModeSections.tsx` | execution policy | `runtime/http` preflight-policy owner: issue typed current execution result; composer consumes that result only | `not_established`/`policy_disabled`, fail closed for the gated launch |
| 101 `evaluator_reports` | literal `enabled=True`, `governance`; gates governance tabs/panels in `surfaceRegistry.ts` and `runDetailTabs.ts` | fixed chrome | `team-design`: remove tab/panel availability gates; evaluator artifact producer may separately emit searchable rows | report discovery `producer_missing`; fixed governance chrome remains available |
| 108 `reproducibility_manifests` | literal `enabled=True`, `governance`; no keyed dashboard consumer beyond generic manifest rendering | registry discovery | runtime run-artifact owner: project persisted replay/hash/determinism artifacts generically or remove the card | `producer_missing + consumer_missing` |
| 115 `transport_summary` | literal `enabled=True`, `governance`; capability key has no keyed consumer, while real summaries come from `services/debug.py` into run-detail governance views | registry discovery | runtime governance-artifact owner: index real persisted transport summaries; delete manifest row | `producer_missing`; existing per-run summary is not global discoverability |
| 124 `promotion_lane` | literal `enabled=True`, `evidence`; gates evidence surfaces and is highlighted by `LaunchRunPage.tsx` → `ComposerModeSections.tsx` | split | `team-design` owns fixed evidence chrome; runtime promotion registry/policy owns searchable operation/execution; remove literal | discovery/execution independently `producer_missing`/`not_established`; authority always separate |
| 131 `auto_materialization` | env helper `_is_auto_materialization_enabled`, `evidence`; gates launch payload/forms in `LaunchRunPage.tsx`, `ComposerModeSections.tsx`, and `forms.ts` | execution policy | `runtime/http` NL materialization-policy owner: project operation+policy result; composer reads execution only | `not_established`/`policy_disabled`; no discovery row manufactured |
| 140 `binding_profiles` | literal `enabled=True`, `evidence`; no keyed UI consumer; real list owner is `control_registry_providers.py` via `GET .../binding-profiles` | registry discovery | `runtime/http` binding-profile registry owner: index/search the real registry and remove literal | `producer_missing` if registry unavailable; `consumer_missing` if no picker adopts it |
| 147 `source_profiles` | literal `enabled=True`, `evidence`; gates Evidence panels in `surfaceRegistry.ts`; real list owner is `SourceProfileRegistry`/`control_registry_providers.py` | split | `team-design` owns fixed Evidence panels; DS15/`team-fabric` owns registry content; DS10 wires generic source search only | `producer_missing` for rows, while chrome remains explicit; no DS10 acquisition work |
| 154 `scientist_web_search` | env helper `_is_scientist_web_search_enabled`, `evidence`; no keyed dashboard consumer; NL pipeline reads it | split | Scientist tool registry owns discovery; runtime grounding/execution policy owns enablement; remove generic manifest card | discovery `producer_missing`; execution `policy_disabled`/`not_established` |
| 164 `scientist_swarm` | env helper `_is_scientist_swarm_enabled`, `runtime`; no keyed dashboard consumer; NL pipeline reads it | split | Scientist node registry owns agent discovery; runtime orchestration policy owns execution | discovery `producer_missing`; execution `policy_disabled`/`not_established` |
| 174 `scientist_reflexion` | env helper `_is_scientist_reflexion_enabled`, `runtime`; no keyed dashboard consumer; NL pipeline/CLI own the operation | split | Scientist node/tool registry owns discovery; runtime orchestration policy owns execution | discovery `producer_missing`; execution `policy_disabled`/`not_established` |
| 184 `lex_pipeline` | literal `enabled=True`, `knowledge`; `DashboardPage.tsx` gates Lex state, while Lex status/search/trigger have separate endpoints | split | `team-design` owns fixed `/knowledge`; `team-lex` owns search/status/trigger; search is discovered, status informs execution, trigger stays a fixed authenticated mutation | legal search `producer_missing` or execution `not_established`; trigger never enters results |
| 191 `unified_dag` | env helper `_is_unified_dag_enabled`, `runtime`; gates workflow/panel surfaces in `surfaceRegistry.ts`/`runDetailTabs.ts`; real DAG node/runner exists | split | Foundry/Scientist node registry owns method discovery; runtime execution policy owns enablement; fixed tabs move to chrome | discovery `producer_missing`; execution `policy_disabled`/`not_established` |
| 198 `security_admin_layer` | literal `enabled=False`, stage `deferred`, `platform`; no production keyed consumer | roadmap status | `team-architecture` allocates any future owner; remove from capability/search and do not create a status surface in DS10 | `absent/unallocated` |
| 206 `durable_control_plane` | `resolved_policy.fallback_rules[durable_control_required]`, `platform`; no keyed feature consumer; Platform Health already reads manifest policy fields | execution policy | `runtime/http` `RuntimeExecutionPolicyResolver`: project provenance/rule/epoch outside open search | `not_established` if resolver cannot answer |
| 213 `control_plane_local_waiver` | `resolved_policy.fallback_rules[local_control_plane_waiver_active]`, stage active/planned, `platform`; no keyed feature consumer | execution policy | `runtime/http` waiver-policy owner: project issuer, scope, validity and expiry as a limitation, never a capability | `not_established`/`revalidation_required`; no implied permission |

Closeout scope correction (2026-08-26): the planning census correctly identified
`project_capability_features(causal_contract)` as producer-backed, but inspection
of its complete output shows backend/family `enabled` booleans rather than typed
owner-index rows. Routing those booleans into `discoverable` would be a P38
execution-to-discovery proxy. The causal contract remains available under the
manifest's typed `causal_runtime` execution-policy projection; the old feature
projection has zero callers and is not a bypass. Method discovery therefore
stays the honest `producer_missing` typed negative until the default release
`CapabilityIndex` bridge exists. Debt
`ds10-causal-method-index-provider-bridge`, owner `foundry/methods`, producer
bridge lane `runtime/quality`, owns the exact executable closure signal. This is
a scope correction discovered at closeout, not permission to manufacture rows.

## DS10 frontend-disposition adjudication

All ten current root objects start `rebind_pending/pending`, owner `team-design`,
owner slice `DS10`. The writer changes only the schema-valid fields below,
records a rationale/source-consumer receipt, and leaves the 217-row DS8
historical assignment set byte-stable. “Use as is” accepts an already separate
dedicated operation; it does not claim that operation is capability discovery.

| root object | source / current consumer | schema-valid writer result | rationale and ownership |
| --- | --- | --- | --- |
| `route-knowledge` | `routeManifest.ts` → `LexKnowledgeGraphPage.tsx` | `rebind_pending/strangled`, successor refs to fixed route plus generic legal-norm panel | keep owner `team-design`/DS10; chrome and candidate frontier are split, no local authority synthesis |
| `feature-command-palette` | `CommandPalette.tsx` → `surfaceRegistry.ts` | `rebind_pending/strangled`, successor refs to fixed-command source and generic result source | keep owner `team-design`/DS10; arbitrary results come from search and literal-ID branch red |
| `feature-lex` | `LexKnowledgeGraphPage.tsx` and its export paths | `rebind_pending/strangled`, successor refs to dedicated Lex surface plus discovery projection | keep owner `team-design`/DS10; preserve grounding/hallucination/jurisdiction/time/frontier; public authority out |
| `api-op-get-control-capabilities` | `useCapabilities.ts` and all manifest consumers mapped below | `rebind_pending/strangled`, successor refs to narrow execution manifest and fixed-chrome/discovery owners | keep owner `team-design`/DS10; all 21 literals removed/adjudicated |
| `api-op-search-data-catalog` | `useDataCatalogSearch.ts` → `DataIntelligencePanel.tsx` | `rebind_pending/strangled`, successor is canonical dataset compatibility projection | keep owner `team-design`/DS10; dedicated panel remains, while response gains canonical frontier without a second searcher |
| `api-op-get-data-index-stats` | `useDataIndexStats.ts` → Dashboard/Evidence/Data Intelligence | `use_as_is/not_applicable` | keep owner `team-design`/DS10; accepted freshness evidence only, never a posture producer by itself |
| `api-op-get-lex-graph-stats` | `useLexGraphStats.ts` → Dashboard/Lex page | `use_as_is/not_applicable` | keep owner `team-design`/DS10; accepted dedicated Lex evidence, not authority |
| `api-op-search-lex-graph` | `useLexSearch.ts` → Lex page | `use_as_is/not_applicable` | keep owner `team-design`/DS10; dedicated search remains while canonical provider preserves its rich truth/frontier |
| `api-op-get-lex-pipeline-status` | `useLexPipelineStatus.ts` → Lex page | `use_as_is/not_applicable` | keep owner `team-design`/DS10; accepted fixed status read, only an execution input |
| `api-op-trigger-lex-pipeline` | `useLexTrigger.ts` → Lex page | `use_as_is/not_applicable` | no transfer: frontend disposition stays `team-design`/DS10 and `team-lex` owns operation behavior; fixed authenticated mutation never appears as a discovered action |

The DS10 surgical writer must emit exactly these five `rebind_pending/strangled`
and five `use_as_is/not_applicable` transitions, with successor records on all
rebound rows and none on use-as-is rows. Any other 261-row change, owner transfer,
missing source/rationale, or 217-assignment byte change fails CC20.

## Manifest strangle denominator and scope decision

Two independent derivations agree on 14 direct manifest interpreters plus one
semantic downstream consumer = **15 production paths**: (A) complete `rg` walks
of owner imports, helper calls and `requiredCapabilities`, followed through the
Launch-page prop; (B) a TypeScript compiler AST walk of all non-test `.ts/.tsx`
files resolving the two owner imports and `requiredCapabilities` property, plus
an independent JSX/data-flow check for `CapabilityHighlightsSection`. Known
member: `api/hooks/useCapabilities.ts`; known downstream member:
`features/composer/routes/ComposerModeSections.tsx`. C05 and C06 classify all 15;
no count is inferred from a single hook import.

| current path | current use | target plane / action |
| --- | --- | --- |
| `api/hooks/useCapabilities.ts` | query plus misleading `useCapabilityDiscovery` wrapper | narrow to execution/platform manifest; rename wrapper to `useCapabilityManifestAvailability`; new generic API is `useCapabilitySearch` |
| `shared/lib/capabilities.ts` | key lookup/boolean helpers | retire for fixed chrome; replace execution consumers with typed execution-policy selector |
| `app/layout/Header.tsx` | counts enabled manifest rows | show typed execution/discovery counts separately; never call an authored count “registry” |
| `app/routes/WorkspaceBoundary.tsx` | blocks fixed workspace by manifest feature | fixed `SurfaceAvailability` plus authz/feature flag only |
| `app/workspaces.ts` | `requiredCapabilities` and manifest prefetch | fixed chrome; remove capability keys/prefetch dependency |
| `app/surfaces/surfaceRegistry.ts` | `requiredCapabilities` on tabs/panels | fixed chrome; typed execution gates only where an action, not a route, truly needs them |
| `features/commandPalette/CommandPalette.tsx` | wraps manifest as “discovery” and filters fixed commands | fixed commands from surface registry; open result group from `useCapabilitySearch` |
| `features/composer/routes/LaunchRunPage.tsx` | keyed execution flags plus four manifest highlights | typed execution-policy arms; open searchable suggestions use generic query |
| `features/composer/routes/ComposerModeSections.tsx` | renders `CapabilityHighlight` values forwarded by Launch page | remove manifest highlight channel; render typed execution reasons and generic candidates through distinct props |
| `features/dashboard/routes/DashboardPage.tsx` | gates Lex fixed state with `lex_pipeline` | fixed Lex chrome plus real Lex status/readiness |
| `features/evidence/routes/EvidenceFabricPage.tsx` | counts enabled manifest rows | generic discovery panel and independent index-health evidence |
| `features/lex/routes/LexKnowledgeGraphPage.tsx` | reads manifest alongside dedicated Lex hooks | fixed route, dedicated operation state, and canonical legal-norm discovery remain separate |
| `features/platform/routes/PlatformHealthPage.tsx` | lists/counts every manifest row | narrow execution/platform policy view plus typed discovery-provider health |
| `features/runs/domain/runDetailTabs.ts` | filters tabs by manifest keys | fixed tabs; remove manifest availability filtering |
| `features/runs/routes/RunDetailLayout.tsx` | supplies manifest to tab filtering | stop fetching manifest for chrome; consume action-specific execution state only if needed |

`rg`/TypeScript import resolution and the existing type-aware checker reproduce
the 14 direct set; the Launch-page prop construction and
`CapabilityHighlightsSection` render prove the fifteenth semantic edge. The C06
sibling-consumer mutation adds the same data flow under a renamed prop and must
still fail, closing the `ComposerModeSections.tsx` P31 escape.

## Contract and endpoint design

Promote the existing G0 posture vocabulary into
`core/contracts/capability_discovery.py`; have G0 import it. Reuse
`SearchRequest`, `SearchCandidate`, and `SearchLedger` rather than create a
parallel frontier grammar. The strict response carries:

```text
CapabilityDiscoveryResponse
  meta
  request + request_digest + authority_purpose + audience
  results[]
    capability_ref + content_digest + resource_kind + label/description
    discovery_result { state, producer_ref, snapshot/freshness/provenance refs }
    execution_result { state, producer_ref, conformance/policy refs, reasons }
    authority_result { state, producer_ref, purpose/binding/currentness refs, reasons }
    authoritative_for + may_not_use_for + schema/rule/time fields
  frontier
    selected_candidates[] + rejected_candidates[]
    requested/evaluated/returned counts + actual cutoff/budget
    searched index/snapshot/freshness refs
    no_hit_frontier[] + completeness_status + incompleteness_reasons[]
    replay_key + replay_command + expected output hash
```

Canonical route:

```text
POST /api/v1/control/capabilities/search
```

It reuses the existing control read permission/resource discipline. The current
`GET /api/v1/control/data/catalog/search` calls the same owner service with
`resource_kind=dataset` and becomes a typed compatibility projection; it does
not search independently. `GET /api/v1/control/capabilities` remains a narrow
execution/platform manifest and contains no fixed chrome or authored open-ended
feature rows. Workspaces/routes/tabs live in the fixed frontend chrome registry.

The search response is not cached forever. Its query key includes request digest
and server index/version epoch; route re-entry/manual refresh issues a fresh
request. No client clock upgrades server freshness.

## Approved amendment — 2026-08-26 CC15 owner-row scope correction

The original C00–C04 execution narrowed the master-plan word “adapter” to the
post-G0 bridge-adapter family. That census was factually correct—those admitted
rows have no DS10 resource kind, capability purpose, passport/currentness
receipt, or honest projection into the six-kind contract—but the binding was a
P38 proxy. The surface renders capability rows, not provider implementations or
semantic bridge adapters. Rule-12 growth in the approved federation is therefore
a new row from an existing kind's owner index; provider count remains fixed.

Two independent complete-set derivations found zero concrete production
`CapabilityDiscoveryProvider` implementations at the amendment entry point and
six contract kinds. The owner-index census then found these actual growth seams:
CapabilityIndex inputs for `method`, `dataset`, and `legal_norm`; the source
profile registry for `source`; paired Scientist registries for `agent`; and no
global index for `case`. `legal_norm` is the strongest honest witness because
the real Lex database/CapabilityIndex path admits a row only after recomputing
grounding, reference resolution, hallucination clearance, jurisdiction, and
temporal effectiveness. Source and Scientist registries lack an equivalent
durable content-bound snapshot today; cases remain `producer_missing`.

Accordingly CC15 is re-bound to a generated `legal_norm` row admitted by the
real Lex owner database and real index compiler, then searched by a production
Lex provider. The test may install that production provider through the runtime's
normal override seam, but may not substitute a test provider or owner-returned
DTO. The real FastAPI route, real dashboard hook, and real panel remain required.
The complete tracked dashboard `src/**` set is frozen at test start and compared
by path, extension partition, and bytes at test end. The post-G0 data-only gap
and bridge gap remain separately owned upstream debts; neither is a CC15
conjunct. This amendment consumes one approved execution round. The hard round
ceiling is raised from 12 to 15; the hard path ceiling remains 50.

## Exact free-growth falsifier

`test_new_legal_norm_owner_row_appears_without_frontend_code_change`
performs this exact sequence:

1. Reproduce the pinned opening count of 1,087 dashboard production paths, then
   enumerate and hash the complete tracked test-start denominator under
   `apps/runtime-dashboard/src/**`, preserving its file-type partition and known
   member. C05's own generic hook/panel files legitimately make the latter set
   larger than 1,087; excluding them would create an ID-branch escape. Generate
   one capability ID that is absent from both backend and dashboard source bytes.
2. Copy the real Lex owner database into test scratch, add one fully grounded,
   reference-resolved, effective, hallucination-clear norm through its real
   tables, and rebuild the real CapabilityIndex. Compute the new
   `capability_ref` from the admitted owner row; do not name it in renderer source
   or construct a discovery DTO. A malformed/ungrounded sibling must be rejected
   by that same admission path.
3. Search the rebuilt snapshot through the production Lex discovery provider,
   boot the actual FastAPI application through its real container override seam,
   call the canonical route, and render the actual generic hook/panel. Do not
   seed an HTTP/MSW response, frontend fixture, or test-substituted provider.
4. Assert exactly one DOM result for the generated ID: `discoverable` from the
   searched snapshot, `executable` only if live registration/conformance/policy
   establish it, candidate clothing remains visible, and selected/rejected
   frontier position is exact. Because the typed owner-signed capability-purpose
   binding is absent today, `admitted_authority` must be `not_established` and no
   approve/publish action appears.
5. Assert downloaded MACHINE bytes equal the captured `response.clone()` bytes
   and `decodeCapabilityDiscoveryDom(container)` equals the parsed complete
   response.
6. Re-enumerate and rehash the complete test-start dashboard production set and
   require exact path, partition, and byte-digest equality. The separately
   reported 1,087 count remains the opening-base census, not an allowlist that
   can omit C05 source. A generic-result-boundary lint plus the real route/panel
   assertion prevents a frontend ID special case.
7. Repeat with missing owner inputs, stale index, quarantined owner data,
   malformed row, policy disablement, no-hit, and recall miss; each fails at its
   own independently produced posture and none renders `admitted_authority`.

The upstream backend data-only test is a separately owned debt signal, not a
conjunct of this UI falsifier. A later optional positive-authority sibling may
run only after the upstream authority owner ships the separately signed typed
binding contract; DS10's test cannot manufacture it.

## Red-first semantic tests

Backend identities:

- `test_adapter_registry_free_growth.py::test_post_g0_registry_admits_new_contract_from_data_only_mutation` — upstream owned debt signal.
- `test_capability_discovery_postures_use_three_independent_producers`.
- `test_discoverable_row_cannot_establish_execution_or_authority`.
- `test_bare_adapter_admitted_flag_cannot_establish_authority`.
- `test_current_ds9_packet_without_typed_capability_purpose_binding_is_not_established`.
- `test_capability_discovery_accepts_only_owner_signed_capability_purpose_binding`
  (upstream artifact/bridge missing until its owner ships the contract).
- `test_capability_discovery_wrong_resource_purpose_expiry_and_consumer_fail_closed`.
- `test_capability_discovery_frontier_preserves_selected_rejected_cutoff_and_incompleteness`.
- `test_capability_discovery_distinguishes_no_hit_recall_unmeasured_stale_and_outage`.
- `test_capability_discovery_case_kind_is_typed_producer_missing`.
- `test_capability_discovery_agent_provider_never_reads_world_agent_rows`.
- `test_new_legal_norm_owner_row_appears_without_frontend_code_change`.
- `test_control_capability_manifest_has_no_authored_feature_rows`.
- `test_data_catalog_search_is_projection_of_canonical_discovery_service`.
- `test_capability_discovery_route_reuses_control_read_authorization`.

Frontend/architecture identities:

- `CapabilityDiscoveryPanel > renders independent posture proofs and candidate clothing`.
- `CapabilityDiscoveryPanel > renders selected and rejected frontier with cutoff and incompleteness`.
- `CapabilityDiscoveryPanel > distinguishes no-hit recall stale and producer-missing states`.
- `CapabilityDiscoveryPanel a11y > announces candidate grade and every typed frontier limitation`.
- `CapabilityDiscoveryPanel a11y > keyboard search result traversal and MACHINE download`.
- `CapabilityDiscoveryPanel a11y > candidate and limitation clothing pass opaque-background contrast`.
- `CapabilityDiscoveryPanel MACHINE > exact HTTP bytes equal download and decoded DOM`.
- `Capability discovery free growth > new legal-norm owner row renders without frontend production change`.
- `Fixed chrome separation > routes tabs and mutations do not consume discovery as availability`.
- `Lex discovery > preserves candidate grounding hallucination jurisdiction and temporal truth`.
- `DS10 register coverage > all 10 opening roots have one checked disposition`.
- `DS10 capability-menu lint > backend/frontend enumerations and adapter switches fail`.
- `DS10 visual > executable candidate and incomplete no-hit frontier retain hierarchy and candidate clothing`.

The enforcement controls are deliberately three separate properties: Python AST
resolves imports and rejects direct `CapabilityFeatureInfo(...)` calls that feed
manifest `features`; the existing type-aware TypeScript checker rejects
contextual generated `CapabilityFeatureInfo`/`features` object literals; and the
designated generic-result boundary rejects literal `capability_ref`, adapter-ID,
resource-kind branches or result arrays. It does not inspect fixed typed
`WorkspaceConfig`/surface-registry data. Mutation controls preserve marker fields
while deleting the real property, add a sibling unsafe consumer, reorder
selected/rejected DOM rows, change one raw frontier field, falsify a posture
declaration, and add a hardcoded picker array. Marker/string checks alone cannot
pass CC16 or CC19; free growth is the behavioral backstop.

## Clustered execution plan

Caps count unique production/tooling mechanism paths. Tests; this plan/journal;
generated OpenAPI/client ABI files; register/report/debt/ledger records;
snapshots; and tests that pin a moved constant are mandatory P39 companions
outside caps. They are still listed and committed with their mechanism. Never
split one mechanism across commits to fit a cap.

The declared caps total **42 unique mechanism paths**. The hard slice-wide
ceiling is **50 unique mechanism paths**; path 51 is a real stop. Slack is eight
paths (19.0%), based on the complete current consumer/provider census rather than
DS9's shape. The original cluster plan declared 12 rounds. The approved CC15
amendment raises the execution stop ceiling to **15 total rounds**: 7 were
consumed through C04, one admits the correction, and C05/C06/C07 retain their
declared 2/3/1 budgets. Narrowing is free: a
change that only removes a way the system can be fooled is pre-authorized and
consumes no round. A change that adds a capability, surface, permission, or
producer arm consumes one widening round.

The two cap derivations are the cluster-table arithmetic and a parser that unions
each cluster's declared Add/Modify mechanism paths (tests/P39 companions removed);
both must return 42 unique paths; known member
`src/polisyos/core/contracts/capability_discovery.py`. A separate round-column
sum preserves the original 12-round plan; the amendment records the independent
15-round execution ceiling and the reason for the difference.

A production path outside a cluster's declared list is pre-authorized only when
a named closure item requires it and no existing seam suffices. The receipt names
the CC item, path, and rejected seam before editing. The path still counts against
the cluster and 50-path ceiling. A second finding of one class invokes P40:
widen the mechanism to the property or declare a bounded residual and run its
falsifier; do not patch another instance.

| cluster | property | path cap | round budget |
| --- | --- | ---: | ---: |
| C00 | Admit plan, remeasure the entry state, pin DS10 reds, and register upstream registry-growth debt. | 0 mechanism | 1 transaction; 0 widening |
| C01 | Canonicalize independent posture/frontier contracts and make the no-enumeration lint generic. | 5 | 2 widening |
| C02 | Federate existing typed indexes and independently reconcile discovery/execution while authority fails closed across DS9 currentness and the missing owner binding. | 5 | 3 widening |
| C03 | Expose the search bridge, re-ground the manifest, and bind the data-catalog compatibility projection. | 7 | 2 widening |
| C04 | Regenerate and reproduce the frozen OpenAPI/client ABI atomically. | 0 mechanism | 1 regeneration transaction |
| C05 | Land the generic discovery surface, frontier, refresh semantics, and exact-byte MACHINE twin. | 13 | 2 widening |
| C06 | Separate fixed chrome and migrate every current capability-manifest consumer/adjudication. | 12 | 3 widening |
| C07 | Freeze, review, run targeted semantic/a11y/visual lanes, register debts, and read back closure. | 0 mechanism | 1 verification transaction |

Closeout accounting preserves that approved 42-path declaration and records the
four pre-authorized path exceptions instead of rewriting the plan after the
fact. Two independent derivations agree on **46/50 actual unique mechanism
paths**: (a) the base-to-working-tree diff classified under P39, and (b) accepted
C00-C04 `18` + C05 `13` + C06 `12` + three C07 narrowing paths. The C07 paths
are `features/evidence/domain/searchParams.ts` (CC14 real palette selection), the
deleted `useDataCatalogSearch.ts` (CC17 one strict hook), and
`DataIntelligencePanel.tsx` (CC11/CC18/CC19 removal of the sibling hit-only
renderer). Their rejected seams were decorative/fixed query parsing, a
compatibility hook that bypassed the full contract, and a second incomplete
discovery surface. The fourth exception is C04's
`tools/ops_runners/runtime/generate_runtime_client.py`: generation logic is a
mechanism even though C04 originally capped only generated companions. The C05
compiler narrowing reused an already-declared C02 path and adds no unique path.
Actual widening use is **14/15**; narrowing repairs consume no round.

### C00 — plan admission, real reds, and owned upstream debt

**Mechanism cap:** 0. **Round:** one register/test transaction; no widening.

**P39 only:** this plan; execution journal
`docs/superpowers/journals/2026-08-25-ds10-capability-discovery.md`;
`docs/plans/active/DEBT-REGISTER.md`; generated `LEDGER.md`; and the upstream
tracked gate test only if it has already arrived on main. The debt-register
denominator constant and its pinned behavioral test move only as the compulsory
companion of this new row. C00 may add DS10's backend/frontend red test shells,
but no source producer, generated output, registry artifact, or registry builder.

**Named red:** DS10
`test_capability_discovery_postures_use_three_independent_producers`;
`test_control_capability_manifest_has_no_authored_feature_rows`; and the
frontend hardcoded picker negative.

**Acceptance:** exact current-main parent has the known debt-checker informational
rows only; all requested censuses are independently reproduced; DS10's own named
tests are present and red for the intended missing behavior; and debt
`ds10-adapter-registry-data-only-free-growth`, owner `team-architecture`, producer
lane `runtime/quality`, carries the exact command above. Record the upstream
test's current absent/skipped/red/green receipt without making it a conjunct,
release the register lock, commit C00, and enter C01 with 0/12 widening rounds.

```bash
git status -sb
git symbolic-ref -q HEAD
git rev-parse --show-prefix
uv run python tools/quality/validation/check_debt_ledger.py --check --report-only
uv run pytest tests/unit/runtime/quality/test_adapter_registry_free_growth.py::test_post_g0_registry_admits_new_contract_from_data_only_mutation -q
```

**Commit boundary:** `test(atlas): bind DS10 discovery reds`.

### C01 — canonical contract and enumeration strangle

**Mechanism cap:** 5. **Rounds:** 2 widening.

**Add:**

- `src/polisyos/core/contracts/capability_discovery.py`

**Modify:**

- `src/polisyos/core/contracts/search.py`
- `src/polisyos/core/contracts/control.py`
- `src/polisyos/runtime/quality/proving_ground/pre_adapter_grounding_inventory.py`
- `architecture/atlas_surfaces/check_atlas_enforcement.py`

**P39 tests:** contract tests mirrored under
`tests/unit/core/contracts/test_capability_discovery.py`;
`tests/unit/runtime/quality/test_proving_ground_pre_adapter_grounding_inventory.py`;
`architecture/atlas_surfaces/test_atlas_enforcement.py`; and a generic backend
denominator test under `tests/repo_quality/tools/`. The new module remains an
internal typed cross-runtime contract imported directly; adding it to the stable
Python facade/public-surface inventory is `surface_out_of_scope` for DS10. The
HTTP/OpenAPI contract is the external surface, so no `guardrails sync` is needed.

**Named red:** direct backend constructor, contextual frontend literal, indirect
features array, adapter-ID switch, hardcoded picker row, missing posture arm,
discoverable-to-authority laundering, and benign typed fixed chrome.

**Acceptance:** strict/frozen public DTOs (`extra="forbid"`) compose existing
search DTOs; G0 imports the vocabulary with schema/replay behavior unchanged;
the Python check import-resolves manifest `features` contributors, the retained
type-aware TypeScript check rejects contextual generated feature literals, and
the generic-render check bans literal result-ID/kind branches only inside the
designated discovery boundary. Each remove-property-keep-markers mutation fails;
fixed `WorkspaceConfig` is the benign control. The 21-row plan table is a
one-time conservation receipt, not the source of future lint truth. No current
adapter IDs or result rows appear in the contract.

```bash
uv run pytest tests/unit/core/contracts/test_capability_discovery.py tests/unit/runtime/quality/test_proving_ground_pre_adapter_grounding_inventory.py architecture/atlas_surfaces/test_atlas_enforcement.py -q
```

**Commit boundary:** `feat(core): define independent capability discovery postures`.

### C02 — provider federation and fail-closed posture composition

**Mechanism cap:** 5. **Rounds:** 3 widening, because search federation,
execution reconciliation, and the DS9-currentness-plus-owner-binding integration
port are three distinct properties.

**Add:**

- `src/polisyos/runtime/quality/capability_discovery.py`

**Modify:**

- `src/polisyos/runtime/quality/capability_index.py`
- `src/polisyos/runtime/quality/capability_index_compiler.py`
- `src/polisyos/runtime/quality/capability_resolver.py`
- `src/polisyos/runtime/quality/capability_authority.py`

**Forbidden paths:** all canonical adapter admission/contract JSON/TOML artifacts
and their row-producing builders. C02 consumes their real interface and does not
add or alter upstream registry content.

**P39 tests:** `tests/unit/runtime/quality/test_capability_discovery.py`, existing
capability index/compiler/resolver tests, DS9 production-approval resolver tests,
and temporary-store free-growth fixtures.

**Named red:** three-producer independence; index hit with missing operation;
best-effort Fabric fallback; conformance pass with policy disabled; bare
`admitted=true`; current DS9 packet with no typed capability-purpose binding;
unsigned/self-attested binding; signed binding wrong resource/purpose/audience;
stale/wrong-consumer packet; cases missing; world-agent substitution;
selected/rejected frontier mutation.

**Acceptance:** one provider protocol returns searched rows plus real index
ledger; one execution resolver independently reads the live registry/policy; one
authority composer requires opaque currentness from the concrete DS9 resolver
**and** an independently verified owner-signed typed capability-purpose binding.
It never parses `governed_action_key`; without the second producer it emits
`bridge_missing/not_established`, so this base has no authority-positive fixture.
Six kinds have provider or typed-negative arms. The free-growth backend test uses
no enumerated resource ID.

```bash
uv run pytest tests/unit/runtime/quality/test_capability_discovery.py tests/unit/runtime/quality/test_capability_index_compiler.py tests/unit/runtime/quality/test_capability_resolver.py tests/unit/runtime/quality/test_capability_authority.py tests/unit/runtime/quality/test_approval.py -q
```

**Commit boundary:** `feat(runtime): compose registry-backed capability discovery`.

### C03 — HTTP bridge, manifest strangle, and compatibility route

**Mechanism cap:** 7. **Rounds:** 2 widening.

**Add:**

- `src/polisyos/runtime/http/services/control/capability_discovery.py`

**Modify:**

- `src/polisyos/runtime/http/services/control/capabilities.py`
- `src/polisyos/runtime/http/services/control/run_lifecycle.py`
- `src/polisyos/runtime/http/services/control_registry_providers.py`
- `src/polisyos/runtime/http/container.py`
- `src/polisyos/runtime/http/routes/control.py`
- `src/polisyos/runtime/http/openapi_contract.py`

**P39 tests:** `tests/unit/runtime/http/test_capability_discovery_api.py`,
`tests/unit/runtime/http/test_control_api.py`,
`tests/unit/runtime/http/test_control_service_di.py`, authz/resource tests, and
OpenAPI hardening/example tests.

**Named red:** missing provider yields typed 200 response, not empty success;
direct feature row; data-catalog route diverges from canonical service; request
purpose/audience drift; search route without existing control-read authz; stale
index; malformed provider payload; sibling route bypass.

**Acceptance:** the canonical POST and dataset compatibility GET share one owner
service and frontier; current 21 direct constructors are zero; all entry rulings
are realized; fixed chrome is absent from server discovery; DS9 currentness is
resolved only through the attested container instance and cannot fill the absent
typed owner-binding port; OpenAPI examples include discoverable/executable with
authority `not_established`, candidate-only, no-hit/incomplete, and
producer-missing arms. No authority-positive example is authored at this base.

```bash
uv run pytest tests/unit/runtime/http/test_capability_discovery_api.py tests/unit/runtime/http/test_control_api.py tests/unit/runtime/http/test_control_service_di.py tests/unit/runtime/http/test_runtime_api_authz.py tests/unit/runtime/http/test_runtime_api_contract_hardening.py -q
```

**Commit boundary:** `feat(api): expose capability search and strangle authored manifest`.

### C04 — frozen OpenAPI/client ABI regeneration

**Mechanism cap:** 0. **Round:** one serialized regeneration transaction.

**P39 generated companions:**

- `schemas/runtime_api_v1.openapi.json`
- `packages/runtime-api-client/runtimeApiClient.ts`
- `packages/runtime-api-client/runtimeApiClient.js`
- `packages/runtime-api-client/types.ts`
- `packages/runtime-api-client/canonicalRuntimeApiClient.ts`
- `packages/runtime-api-client/canonicalRuntimeApiClient.js`
- `apps/runtime-dashboard/src/api/types.ts`
- `release-fragments/unreleased/2026-08-25-ds10-capability-discovery.toml`
  with the existing compatibility/API impact fields

Acquire the regeneration token only after C03 source freeze. Run the canonical
writers once, then reproduce all outputs from two fresh scratch roots and compare
bytes. Never hand-edit governed JSON or generated TypeScript.

```bash
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops_runners/runtime/export_runtime_openapi.py --output schemas/runtime_api_v1.openapi.json
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops_runners/runtime/generate_runtime_client.py --openapi schemas/runtime_api_v1.openapi.json --out-ts packages/runtime-api-client/runtimeApiClient.ts --out-js packages/runtime-api-client/runtimeApiClient.js
corepack pnpm --filter @polisyos/runtime-dashboard exec openapi-typescript ../../schemas/runtime_api_v1.openapi.json --output ../../packages/runtime-api-client/types.ts
node packages/runtime-api-client/scripts/canonicalize-runtime-client.mjs --openapi schemas/runtime_api_v1.openapi.json --client packages/runtime-api-client/runtimeApiClient.ts --out-ts packages/runtime-api-client/canonicalRuntimeApiClient.ts --runtime-js packages/runtime-api-client/runtimeApiClient.js --out-js packages/runtime-api-client/canonicalRuntimeApiClient.js
corepack pnpm --filter @polisyos/runtime-dashboard exec openapi-typescript ../../schemas/runtime_api_v1.openapi.json --output src/api/types.ts
corepack pnpm --filter @polisyos/runtime-dashboard exec prettier --write ../../packages/runtime-api-client/types.ts src/api/types.ts
uv run pytest tests/integration/runtime_frontend/test_runtime_client_contract_bridge.py tests/unit/runtime/http/test_runtime_api_contract_hardening.py -q
```

**Commit boundary:** `chore(api): regenerate capability discovery ABI`.

### C05 — generic discovery, frontier, and MACHINE surface

**Mechanism cap:** 13. **Rounds:** 2 widening.

**Add:**

- `apps/runtime-dashboard/src/api/hooks/useCapabilitySearch.ts`
- `apps/runtime-dashboard/src/features/evidence/components/CapabilityDiscoveryPanel.tsx`
- `apps/runtime-dashboard/src/features/evidence/export/capabilityDiscoveryTwin.ts`

**Modify:**

- `apps/runtime-dashboard/src/api/hooks/useCapabilities.ts`
- `apps/runtime-dashboard/src/api/validators.ts`
- `apps/runtime-dashboard/src/api/queryKeys.ts`
- `apps/runtime-dashboard/src/app/routes/routeManifest.ts`
- `apps/runtime-dashboard/src/app/routes/prefetch.ts`
- `apps/runtime-dashboard/src/features/evidence/routes/EvidenceFabricPage.tsx`
- `apps/runtime-dashboard/src/features/platform/routes/PlatformHealthPage.tsx`
- `apps/runtime-dashboard/src/app/layout/Header.tsx`
- `apps/runtime-dashboard/src/shared/i18n/locales/en.json`
- `apps/runtime-dashboard/src/shared/i18n/locales/uk.json`

**P39 tests:** hook, validator, route/prefetch, panel, Evidence page, Platform
Health, Header, DOM decoder/twin, and export tests. Do not extend
`DataIntelligencePanel.tsx`; capability discovery is a focused sibling concern.
Locale parity tests are mandatory companions. Add
`apps/runtime-dashboard/src/features/evidence/components/CapabilityDiscoveryPanel.a11y.test.tsx`
and modify the three focused journeys
`e2e/a11y/keyboard-journeys.spec.ts`,
`e2e/a11y/screen-reader-snapshots.spec.ts`, and
`e2e/a11y/color-blind-simulation.spec.ts` under the named DS10 grep.

**Named red:** arbitrary new ID; stale `Infinity` cache; discovery without
candidate clothing; selected-only frontier; empty no-hit explanation; raw-byte
mutation; DOM omission/reorder; adapter-specific component/switch; offline state
retaining authority.

**Acceptance:** `useCapabilities.ts` retires/renames its legacy
`useCapabilityDiscovery` export to `useCapabilityManifestAvailability`; the new
`useCapabilitySearch` is the only generic-search hook. It reuses
`runtimeApiClient`'s per-request `fetch` override and the proven
`captured.clone().arrayBuffer()` pattern from `useRunPaper.ts`, validates the
strict payload, keys freshness by server epoch, and feeds one generic panel. The
panel renders every resource kind without a kind/ID-specific branch, exposes the
full frontier, exports exact response bytes, announces candidate grade and every
no-hit/recall/stale/producer-missing reason, supports keyboard search/result and
MACHINE-download traversal, and passes opaque-background contrast. Header and
Platform Health show typed counts/states rather than an authored feature count.

```bash
corepack pnpm --filter @polisyos/runtime-dashboard exec vitest run src/api/hooks/useCapabilitySearch.test.tsx src/features/evidence/components/CapabilityDiscoveryPanel.test.tsx src/features/evidence/components/CapabilityDiscoveryPanel.a11y.test.tsx src/features/evidence/export/capabilityDiscoveryTwin.test.ts src/features/evidence/routes/EvidenceFabricPage.test.tsx src/features/platform/routes/PlatformHealthPage.test.tsx src/app/layout/Header.test.tsx
corepack pnpm --filter @polisyos/runtime-dashboard exec playwright test e2e/a11y/keyboard-journeys.spec.ts e2e/a11y/screen-reader-snapshots.spec.ts e2e/a11y/color-blind-simulation.spec.ts --project=chromium --grep 'DS10 capability discovery' --workers=1 --timeout=90000 --global-timeout=240000
```

**Commit boundary:** `feat(atlas): render capability discovery and frontier`.

### C06 — fixed chrome separation and complete consumer migration

**Mechanism cap:** 12. **Rounds:** 3 widening, measured from the complete current
production consumer set rather than one sampled screen.

**Modify:**

- `apps/runtime-dashboard/src/shared/lib/capabilities.ts`
- `apps/runtime-dashboard/src/app/workspaces.ts`
- `apps/runtime-dashboard/src/app/surfaces/surfaceRegistry.ts`
- `apps/runtime-dashboard/src/app/routes/WorkspaceBoundary.tsx`
- `apps/runtime-dashboard/src/features/commandPalette/CommandPalette.tsx`
- `apps/runtime-dashboard/src/features/composer/routes/LaunchRunPage.tsx`
- `apps/runtime-dashboard/src/features/composer/routes/ComposerModeSections.tsx`
- `apps/runtime-dashboard/src/features/dashboard/routes/DashboardPage.tsx`
- `apps/runtime-dashboard/src/features/lex/routes/LexKnowledgeGraphPage.tsx`
- `apps/runtime-dashboard/src/features/runs/routes/RunDetailLayout.tsx`
- `apps/runtime-dashboard/src/features/runs/domain/runDetailTabs.ts`
- `architecture/atlas_surfaces/check_frontend_disposition_register.py`

**P39 tests:** every corresponding existing test, including an explicit
`ComposerModeSections` sibling-edge case; fixed-chrome benign-control lint; Lex
CSV/JSON/share/export truth tests; the 10-root register coverage test; and
`architecture/atlas_surfaces/test_frontend_disposition_register.py` plus
register/report/debt/ledger companions.

**Named red:** fixed route disappears when discovery is unavailable; discovered
candidate unlocks fixed tab; command palette hardcodes adapter; composer reads
authority from discoverability; Lex drops candidate/grounding/temporal fields;
pipeline trigger appears as a discovered action; one of the 21/10 sets is
unadjudicated.

**Acceptance:** fixed chrome is local, typed, and explicit; execution-policy gates
remain server-produced but distinct from discovery; open palette/pickers query
the generic endpoint; all 14 direct interpreters plus the one
`ComposerModeSections.tsx` downstream edge use the correct plane; the 21-entry
and 10-root keyed-set checks are exact. No new permission or mutation is
introduced.

```bash
corepack pnpm --filter @polisyos/runtime-dashboard exec vitest run src/app/workspaces.test.ts src/app/surfaces/surfaceRegistry.test.ts src/app/routes/routeBoundaries.test.tsx src/features/commandPalette/CommandPalette.test.tsx src/features/composer/routes/LaunchRunPage.test.tsx src/features/composer/routes/ComposerModeSections.test.tsx src/features/dashboard/routes/DashboardPage.test.tsx src/features/lex/routes/LexKnowledgeGraphPage.test.tsx src/features/runs/routes/runDetailSurfaces.test.tsx src/shared/lib/capabilities.test.ts
uv run pytest architecture/atlas_surfaces/test_atlas_enforcement.py architecture/atlas_surfaces/test_frontend_disposition_register.py -q
```

**Commit boundary:** `refactor(atlas): separate fixed chrome from discovery`.

### C07 — freeze, targeted verification, visuals, debt, and readback

**Mechanism cap:** 0. **Round:** one verification/visual/register transaction.

Freeze source, run independent review and delta-only repair, then acquire one
resource at a time. A cosmetic post-freeze finding is recorded debt; a blocking
finding batches before the single expensive wave. Reopen a mechanism only under
the declared CC/path-exception rule and count it against its original cluster and
the 50-path ceiling.

**P39 companions:** DS10 plan/journal; frontend register/report plus schema
validation; debt register/ledger; generated freshness receipts; release record; and tests pinning
moved counts. Exact visual/a11y companions are:

- modify `apps/runtime-dashboard/e2e/runtime-dashboard.visual.spec.ts` with two
  deterministic intercepted response fixtures: (a) generated capability ID,
  candidate discovery, executable, authority `not_established`, selected plus
  rejected candidate, fixed epoch/cutoff; (b) no hit, rejected candidates,
  `recall_unmeasured`, budget cutoff, stale/missing-provider incompleteness;
- add `apps/runtime-dashboard/e2e/runtime-dashboard.visual.spec.ts-snapshots/ds10-capability-discovery-executable-candidate-chromium-darwin.png`;
- add `apps/runtime-dashboard/e2e/runtime-dashboard.visual.spec.ts-snapshots/ds10-capability-discovery-incomplete-no-hit-chromium-darwin.png`;
- add `apps/runtime-dashboard/src/features/evidence/components/CapabilityDiscoveryPanel.a11y.test.tsx`
  and modify the three C05 a11y journey specs named above.

Those intercepted payloads are visual determinism fixtures only; they cannot
satisfy CC15, whose positive comes through the real backend admission path.

**Acceptance:** targeted backend and frontend lanes, generic enforcement checker,
free-growth e2e, one writer for the final frozen visual source plus two no-writer
runs, exact-byte/DOM parity,
two-scratch regeneration comparison, register corruption probes, path/round
accounting, and every `## Explicit non-closure` command has a declared
green/red/`artifact_missing` receipt with open states written to debt. Re-read every
committed path from attached branch; do not run a full backend/CI-parity suite or
`guardrails sync` for this slice.

```bash
uv run pytest tests/unit/runtime/quality/test_capability_discovery.py tests/unit/runtime/http/test_capability_discovery_api.py tests/repo_quality/tools/test_ds10_capability_discovery_strangle.py -q
corepack pnpm --filter @polisyos/runtime-dashboard exec vitest run src/api/hooks/useCapabilitySearch.test.tsx src/features/evidence/components/CapabilityDiscoveryPanel.test.tsx src/features/evidence/components/CapabilityDiscoveryPanel.a11y.test.tsx src/features/evidence/export/capabilityDiscoveryTwin.test.ts src/features/commandPalette/CommandPalette.test.tsx src/features/lex/routes/LexKnowledgeGraphPage.test.tsx
uv run pytest architecture/atlas_surfaces/test_atlas_enforcement.py architecture/atlas_surfaces/test_frontend_disposition_register.py tests/repo_quality/tools/test_debt_ledger_checker.py -q
.venv/bin/python architecture/atlas_surfaces/check_frontend_disposition_register.py --write-ds10-capability-discovery
.venv/bin/python architecture/atlas_surfaces/check_frontend_disposition_register.py --write-report
.venv/bin/python architecture/atlas_surfaces/check_frontend_disposition_register.py --check --verify-baseline-source-bytes --corruption-probes
uv run python tools/quality/validation/check_debt_ledger.py --write
uv run python tools/quality/validation/check_debt_ledger.py --check --report-only
uv run pytest tests/repo_quality/tools/test_debt_ledger_checker.py::test_ds10_debt_projection_has_only_declared_informational_findings -q
```

The final debt predicate is not the checker's composite exit: report-only output
must contain exactly the ten inherited `register_supplies_missing_standing` rows
and one inherited `register_withholds_source_standing` row, with zero render,
denominator, closure, or DS10 debt drift. DS10 does not change the checker's
frontend denominator or its misleading 217 label.

The DS10 writer/check additionally runs
`test_ds10_writer_emits_five_rebind_five_use_as_is_and_preserves_217_assignments`
and a corruption probe that changes one DS8 assignment while leaving its count
217; both the writer preservation test and checker must reject the mutation.

**Commit boundary:** `docs(atlas): close DS10 capability discovery`.

## Serialized resources and fixed ceilings

| resource | cluster / ceiling and evidence |
| --- | --- |
| register-family lock | C00 and C07 as separate acquisitions; current report-only completion 0.99s -> fixed 30s for report/check, 240s for writer + corruption probes using the last completed Atlas bound; no overlap with writers/visuals |
| regeneration token | C04 only; OpenAPI export 74.83s -> 150s, runtime client 0.15s -> 30s, each OpenAPI TypeScript/canonicalization/format step uses the measured 4.83s comparison -> 30s, complete transaction ceiling 240s; each later command freezes at `max(30s, 2x completed planning measurement)` |
| visual lane | C05 focused a11y browser journey and C07 visual transaction as separate acquisitions; inherited latest completed DS9 Atlas lane: 90s per test, 240s invocation; C07 must select exactly 2/2 DS10 tests and has exactly one `--update-snapshots` run then two no-writer runs, `--workers=1`, zero retries |
| focused dashboard | ordinary lane; 13.13s -> 30s |
| focused backend | ordinary lane; 147.05s -> 300s |

Every execution receipt records `uptime` immediately before and after the exact
command, selected count, exit, elapsed, ceiling, and whether it wrote. A killed
run never changes a ceiling. No ceiling widens mid-run.

Exact visual commands differ only by the first writer flag:

```bash
CI=1 PLAYWRIGHT_RETRIES=0 PLAYWRIGHT_INCLUDE_RUN_PAPER_FIXTURES=1 corepack pnpm --filter @polisyos/runtime-dashboard exec playwright test --config=playwright.visual.config.ts --project=chromium --grep 'DS10 capability discovery' --workers=1 --timeout=90000 --global-timeout=240000 --update-snapshots
CI=1 PLAYWRIGHT_RETRIES=0 PLAYWRIGHT_INCLUDE_RUN_PAPER_FIXTURES=1 corepack pnpm --filter @polisyos/runtime-dashboard exec playwright test --config=playwright.visual.config.ts --project=chromium --grep 'DS10 capability discovery' --workers=1 --timeout=90000 --global-timeout=240000
CI=1 PLAYWRIGHT_RETRIES=0 PLAYWRIGHT_INCLUDE_RUN_PAPER_FIXTURES=1 corepack pnpm --filter @polisyos/runtime-dashboard exec playwright test --config=playwright.visual.config.ts --project=chromium --grep 'DS10 capability discovery' --workers=1 --timeout=90000 --global-timeout=240000
```

## File map

| role | planned home |
| --- | --- |
| canonical posture/frontier contract | `core/contracts/capability_discovery.py`, reusing `core/contracts/search.py` |
| provider federation | one new orchestration owner `runtime/quality/capability_discovery.py` adapting existing index/compiler/resolver and `capability_authority.py`; no parallel provider package |
| evidence/authority composition | concrete DS9 currentness resolver plus fail-closed port for a separately owner-signed typed capability-purpose binding; binding producer is out of DS10 and absent at base; no UI authority computation |
| HTTP owner | `runtime/http/services/control/capability_discovery.py`, composed by existing control service/container |
| compatibility seed | `routes/control.py` data-catalog search delegates to canonical owner |
| authored-manifest strangle | `services/control/capabilities.py` plus generic Atlas enforcement checker |
| fixed chrome | extend the existing `app/surfaces/surfaceRegistry.ts` and workspaces owner with typed `SurfaceAvailability`; no parallel registry |
| generic search surface | `useCapabilitySearch.ts`, `CapabilityDiscoveryPanel.tsx` |
| MACHINE/DOM parity | `features/evidence/export/capabilityDiscoveryTwin.ts` |
| governance | DS10 plan/journal, frontend register/report, debt register/ledger |

## Issue codes

| code | meaning |
| --- | --- |
| `DS10-REGISTRY-FREE-GROWTH-NOT-ESTABLISHED` | upstream data-only admitted-registry mutation proof absent/red; owned debt, not a DS10 blocker |
| `DS10-DISCOVERY-INDEX-UNAVAILABLE` / `DS10-DISCOVERY-INDEX-STALE` | discovery producer unavailable/stale; candidate frontier only |
| `DS10-DISCOVERY-INCOMPLETE` / `DS10-DISCOVERY-NO-MATCH` | bounded/unknown remainder or true searched no-match; never abstention authority |
| `DS10-EXECUTION-NOT-ESTABLISHED` / `DS10-EXECUTION-BLOCKED` | live registry/conformance/policy cannot establish execution |
| `DS10-AUTHORITY-BRIDGE-MISSING` / `DS10-AUTHORITY-ARTIFACT-MISSING` | DS9 currentness exists but separately signed typed capability-purpose binding producer/artifact is absent |
| `DS10-AUTHORITY-INVALID` / `DS10-AUTHORITY-REVALIDATION` | content/purpose/consumer mismatch or stale currentness |
| `DS10-DISCOVERY-NOT-AUTHORITY` | index/adapter/LLM/search state attempted to fill authority arm |
| `DS10-CASE-INDEX-PRODUCER-MISSING` | no global case index; typed frontier, no builder |
| `DS10-FRONTIER-LOSS` | selected/rejected/cutoff/freshness/incompleteness lost in bridge/UI/export |
| `DS10-HARDCODED-CAPABILITY` | backend/frontend authored row, ID switch, or picker enumeration |
| `DS10-FIXED-CHROME-COLLAPSE` | fixed route/tab availability depends on discovery |
| `DS10-MACHINE-BYTE-DRIFT` / `DS10-DOM-PARITY-DRIFT` | export differs from response or DOM omits/reorders truth |
| `DS10-REGISTER-DRIFT` / `DS10-GENERATED-FRESHNESS` | complete governed set or generated bytes differ |

## Pattern pass and capability state

Read the failure/repair register again before C00 and C07 closeout.

| patterns | opening anti-pattern | target pattern and acceptance signal |
| --- | --- | --- |
| P01/P02/P03/P12 | contracts/rows exist without a DS10 producer→bridge→consumer→surface chain | typed provider result → replay/frontier artifact → HTTP → hook/UI/MACHINE → semantic negative |
| P04/P05/P09/P15 | posture/admission vocabulary can be read as an ordinal or boolean | three independent arms; search/LLM/adapter admission cannot promote authority |
| P10/P25/P29 | current catalog API renders hits/count only | behavioral no-hit/recall/stale/incomplete frontier and DOM/raw-byte parity |
| P27/P28/P31 | 21 authored rows and keyed consumers bypass an owner | generic registry projection plus complete keyed strangle; fixed chrome explicitly separated |
| P32/P37/P38 | `admitted=true`, packet-ref presence, opaque action key, nonempty registry, or status name used as proof | DS9 currentness AND independently verified typed capability-purpose binding; frontend-only free-growth digest; upstream data-only registry growth remains separately owned debt |
| P33/P34 | test fixture or marker-specific lint teaches to the probe | source-digest free-growth, indirect literal/sibling consumer/synonym/malformed mutations |
| P35/P36 | loose grep/comment adjacency and 217/261 denominator collapse | two independent complete-set derivations with file-type denominator and known member |
| P39 | path budget counts plan/tests/generated companions | 42 mechanism paths, companions outside, one mechanism never split |
| P40/P41 | repeated instance repair or inherited-red claim without base replay | bucket second finding; replay exact slice base and prove changed-input intersection zero |

Target closure state is `typed contract + producer + persisted
frontier/replay artifact + orchestration bridge + consumer + verification +
REVIEWER/EXPERT/MACHINE surface + negative/e2e semantic test`. The upstream
backend data-only growth gap remains debt and does not weaken the frontend
genericity proof.

## Explicit non-closure

Every row has an executable signal and owner. Prose alone owns nothing.

| non-closure | state / boundary | owner | executable closure signal |
| --- | --- | --- | --- |
| `ds10-adapter-registry-data-only-free-growth` — **resolved-history** — generic post-G0 registry data-only free growth | `artifact_missing`; the underlying data-only growth property is `not_established`; registered debt, not a DS10 blocker; DS10 will not build registry content | `team-architecture`, producer lane `runtime/quality` | `uv run pytest tests/unit/runtime/quality/test_adapter_registry_free_growth.py::test_post_g0_registry_admits_new_contract_from_data_only_mutation -q` **RESOLVED 2026-08-31 by task C — `closed` in the debt register as `ds10-adapter-registry-data-only-free-growth`.** Kept in place rather than deleted so the obligation's history stays readable; it is no longer a non-closure. |
| `ds10-adapter-admission-capability-discovery-bridge` — **resolved-history** — admitted-adapter capability-discovery bridge | `producer_missing + artifact_missing`; the real G3 admission builder can grow only a semantic bridge-adapter set, while the complete 61-row admission family supplies no DS10 resource kind, capability purpose, passport/evidence/currentness receipt, or concrete capability-discovery provider. Inferring `method` would be P38. The 2026-08-26 amendment corrects the earlier mistake of making this true upstream gap a CC15 blocker: DS10 free growth is owner-index row growth within the approved six-kind contract | `team-architecture`, producer lane `runtime/quality` | `uv run pytest tests/unit/runtime/quality/test_adapter_registry_capability_discovery.py::test_admitted_adapter_emits_typed_capability_kind_purpose_passport_evidence_and_currentness -q` **RESOLVED 2026-08-31 by task C — `closed` in the debt register as `ds10-adapter-admission-capability-discovery-bridge`.** Kept in place rather than deleted so the obligation's history stays readable; it is no longer a non-closure. |
| `ds10-owner-signed-capability-purpose-binding` — **resolved-history** — owner-signed typed capability-purpose authority binding | `bridge_missing + artifact_missing`; DS9 currentness binds its expected consumer/audience but has no typed capability ref/digest/purpose join, and opaque `governed_action_key` cannot substitute; DS10 defines/consumes only a fail-closed port | `team-runtime`, producer lane `runtime/quality` (DS9 authority owner) | `uv run pytest tests/unit/runtime/quality/test_capability_discovery.py::test_owner_signed_capability_purpose_binding_joins_ds9_currentness -q` **RESOLVED 2026-08-31 by task C — `closed` in the debt register as `ds10-owner-signed-capability-purpose-binding`.** Kept in place rather than deleted so the obligation's history stays readable; it is no longer a non-closure. |
| `ds10-global-case-index-producer-allocation` — global case index | `absent/unallocated`; DS10 renders `producer_missing`, adds no store/index | `team-architecture` owns owner allocation; eventual producer owner then replaces it | `uv run pytest tests/unit/runtime/http/test_capability_discovery_api.py::test_case_provider_is_backed_by_canonical_global_index -q` |
| `ds10-causal-method-index-provider-bridge` — **resolved-history** — default causal-method CapabilityIndex bridge | `bridge_missing + semantic_test_missing`; causal backend/family availability remains an execution-policy projection and cannot be promoted to indexed discovery | `foundry/methods`, producer bridge lane `runtime/quality` | `uv run pytest tests/unit/runtime/quality/test_capability_discovery.py::test_default_causal_method_index_provider_projects_owner_rows_without_execution_promotion -q` **RESOLVED 2026-08-31 by task C — `closed` in the debt register as `ds10-causal-method-index-provider-bridge`.** Kept in place rather than deleted so the obligation's history stays readable; it is no longer a non-closure. |
| `ds10-c13-print-receipt-reissue` — DS6 C13 print receipt reissue | `verification_missing`; C13 currentness is `not_established`. A complete 11-binding census found exactly two stale whole-file bindings after the DS10 slice diff: `RunDetailLayout.tsx` and the shared visual spec. The fail-fast global checker exposes the first and stays red; DS10 neither rewrites another slice's evidence nor treats the old receipt as current. Its atomic writer admits that one exposed error only after hash-pinning the complete 2/11 mismatch set and replaying every other C13 conjunct from the receipt; every adjacent, duplicate, differently hashed, or additional mismatch aborts | `team-design`, DS6 independent print-evidence lane | reissue from two distinct zero-retry/no-writer Playwright outputs, then `uv run pytest architecture/atlas_surfaces/test_frontend_disposition_register.py::DS6C13PrintTransitionTests::test_independent_receipt_binds_the_full_conjunction_and_current_bytes -q` and `.venv/bin/python architecture/atlas_surfaces/check_frontend_disposition_register.py --check` both exit zero |
| **not-a-debt** — debt-checker frontend denominator label | P38: stdout `frontend_disposition_rows=217` measures the DS8 assignment sub-register, not the 261-row live root; DS10 never uses it as the live denominator | `tools/quality/validation` debt-ledger owner | `uv run pytest tests/repo_quality/tools/test_debt_ledger_checker.py::test_frontend_disposition_metric_names_live_root_and_ds8_assignments_separately -q` |
| `ds10-connector-acquisition-content` — connector/acquisition content | DS10 consumes source profiles/connector readiness only; no connector creation or acquisition workflow; DS15 is the successor lane once executable | `team-fabric` | `uv run pytest tests/unit/runtime/http/test_control_api.py::test_list_connectors_and_profiles_are_producer_backed -q` |
| `ds10-layer3-owner-ledger-rejection-richness` — **resolved-history** — G2/G3/GL rejected/incompleteness richness | provider projection must carry typed incompleteness where owner ledgers lack rejected candidates; DS10 does not rewrite those artifacts | `team-architecture` Layer-3 owners | `uv run pytest tests/unit/runtime/quality/test_capability_discovery.py::test_all_layer3_providers_emit_real_rejections_and_incompleteness -q` **RESOLVED 2026-08-31 by task C — `closed` in the debt register as `ds10-layer3-owner-ledger-rejection-richness`.** Kept in place rather than deleted so the obligation's history stays readable; it is no longer a non-closure. |
| `ds10-lex-pipeline-mutation-boundary` — **resolved-history** — Lex pipeline mutation | fixed authenticated operation, not a discovered/admitted action | `team-lex` | `uv run pytest tests/unit/runtime/http/services/test_lex_pipeline.py -q` and `corepack pnpm --filter @polisyos/runtime-dashboard exec vitest run src/features/lex/routes/LexKnowledgeGraphPage.test.tsx -t 'Capability discovery > never invokes Lex trigger'` **RESOLVED 2026-08-31 by task C — `closed` in the debt register as `ds10-lex-pipeline-mutation-boundary`.** Kept in place rather than deleted so the obligation's history stays readable; it is no longer a non-closure. |
| `ds10-public-decision-rendering` — public decision rendering | internal REVIEWER/EXPERT discovery and MACHINE frontier only; DS12 is the successor lane once executable | `team-design` | `uv run pytest tests/unit/runtime/http/test_public_export.py::test_public_decision_projection_is_custody_bound -q` |
| `ds10-world-agent-capability-discovery-boundary` — **resolved-history** — L4 world-agent lookup | world-model entity/data discovery is not Scientist agent/tool capability discovery | `runtime/quality` data-state substrate | `uv run pytest tests/integration/runtime_quality/test_data_state_substrate.py::test_agent_registry_has_typed_discovery_surface -q` **RESOLVED 2026-08-31 by task C — `closed` in the debt register as `ds10-world-agent-capability-discovery-boundary`.** Kept in place rather than deleted so the obligation's history stays readable; it is no longer a non-closure. |

**Seven of the twelve rows above were resolved on 2026-08-31 by task C and are marked in place.** The four that remain honest non-closures are C13, connector/acquisition, public decision and global case index, each now carrying a named blocker object in the register; the debt-checker frontend denominator label is a standing P38 note, not a debt. **This table is invisible to `check_debt_ledger`'s `explicit_nonclosure_missing` rule**, which parses bullet lists only — registered as `explicit-nonclosure-check-blind-to-table-shaped-lists`, so nothing here should be read as gate-verified.

An absent future test file is `artifact_missing`, not a green signal. C07 registers
any still-open row in the debt register before claiming closure.

Historical stop receipt (2026-08-25): after source-frozen C04, two independent
reconnaissance passes correctly found the admitted-adapter bridge above absent
and stopped at `c279bbd142fdab8d88751ee411b2b82e823c6cf3`, 18/50 mechanism
paths and 7/12 rounds. The 2026-08-26 owner correction establishes that the stop
was caused by CC15's own over-narrow post-G0 binding, not by the master-plan UI
property. Two independent six-kind owner-index censuses found the real Lex path
extensible, so execution resumes at 7/15; the amendment itself consumes round 8.

## Commit sequence

| boundary | message |
| --- | --- |
| planning hand-back | `docs(atlas): plan DS10 capability discovery` |
| C00 | `test(atlas): bind DS10 discovery reds` |
| C01 | `feat(core): define independent capability discovery postures` |
| C02 | `feat(runtime): compose registry-backed capability discovery` |
| C03 | `feat(api): expose capability search and strangle authored manifest` |
| C04 | `chore(api): regenerate capability discovery ABI` |
| C05 | `feat(atlas): render capability discovery and frontier` |
| C06 | `refactor(atlas): separate fixed chrome from discovery` |
| C07 | `docs(atlas): close DS10 capability discovery` |

Before every commit: `git status -sb`, `git symbolic-ref -q HEAD`, exact dirty
path read, cap/round receipt. History is append-only. No merge, push, rebase,
reset, stash storage, or unrelated cleanup.

## Hand-off packet

The executor/architect receives: approved plan commit; execution base and prefix;
gate result/test/source digest; the two-method 21/10/61/261/217 censuses; exact
21-entry and 10-root adjudication maps; provider/posture source refs; request,
selected/rejected/cutoff/incompleteness replay packet; DS9 resource/purpose
currentness refs plus the explicit missing typed-binding receipt;
HTTP/raw/DOM/MACHINE hashes; generated two-scratch comparison;
visual/a11y receipts; path/round totals; serialized-resource uptime pairs; debt
transitions; and committed-branch readback.

Anything that changes the six resource meanings, broadens DS9 authority, creates
adapter content, invents a case index, adds a mutation/permission, or raises the
50-path ceiling requires an owner-approved plan amendment before code.

## Non-negotiables

- Discovery is candidate state; it never implies execution, authority,
  abstention, approval, or publication.
- `admitted=true`, a packet ref, a confidence score, and an index hit are not
  authority predicates.
- The free-growth test is behavioral and frontend-generic; it hashes the full
  tracked dashboard production denominator while admitting through the real
  backend path, so a fixture response or enumerated frontend ID cannot satisfy it.
- Fixed app chrome stays explicit and typed, but it never masquerades as open
  discovery.
- Selected and rejected candidates, cutoff, freshness, no-hit, and
  incompleteness survive API, DOM, and exact-byte MACHINE export.
- Adapter-registry content, global case indexing, DS15 acquisition, Lex mutation,
  and DS12 public decisions remain with their named owners.
- No `guardrails sync`, full-suite substitution for the targeted commands,
  unmeasured ceiling widening, hand-edited generated output, or unreported path.

## Amendment — 2026-08-26 stable-facade closure

The closeout at `040000ed970b093f50a1fdaba8018a33c918ebdb` left the release
guardrail red on exactly 12 DS10-owned cross-root imports. The earlier C01
ruling that `capability_discovery` facade routing was `surface_out_of_scope`
was based on the wrong owner boundary: DS10 created the contract module and all
nine imports of it. This owner-approved amendment retires that non-closure and
the associated `ds10-capability-discovery-stable-facades` debt. No edge is
transferred to `team-polisyos`.

The narrowing adds all 15 `capability_discovery.__all__` names to the existing
lazy `polisyos.core.contracts` facade, completes the existing `.search` entry
for `SearchCompletenessStatus` and `SearchFrontier`, completes `.control` for
`ExecutionProfile`, and re-spells all 12 caller edges through that facade. The
facade grows from 31 to 32 mapped modules. Runtime identity, `TYPE_CHECKING`,
and facade `__all__` are checked together; an import path that only appeases the
AST scanner is not closure.

The hard mechanism ceiling is raised from 50 to **54**. The 12 callers are
already in the slice's 46-path set. The initial facade-only replay stayed red:
the deep-import guardrail recognizes a facade only when it is a declared
supported entrypoint. Therefore `src/polisyos/core/contracts/__init__.py` and
`architecture/public_surface/contract.toml` are the two required new mechanism
paths, and the final account is **48/54**. The rejected seam was a runtime-only
lazy facade that remained internal to the public-surface policy and therefore
could not close the release gate. The plan, journal, debt register, generated
ledger, and two generated public-surface files are P39 companions. This is
narrowing and consumes no round: **14/15** remains the final round account. The
follow-up commit boundary is
`refactor(core): close DS10 contract facade edges`.

The registered public-surface generator is run after declaring
`polisyos.core.contracts` as Core's second supported entrypoint. This is the
existing lazy contracts door, not a second contract implementation. The
generated `architecture/public_surface/inventory.json` and
`docs/reference/public-surface.md` record the complete facade surface; the
deep-import baseline is narrowly regenerated as a mandatory companion because
the newly supported facade makes 15 historical `-> polisyos.core.contracts`
rows stale. The semantic delta is **3,648 -> 3,633, 15 removals, 0 additions**;
every removed row targets exactly the graduated facade. No new deep edge or
baseline exception is accepted, and the broad guardrail sync is never run.

The historical deletion record is also made explicit: the complete dashboard
diff deletes only `apps/runtime-dashboard/src/api/hooks/useDataCatalogSearch.ts`
and `apps/runtime-dashboard/src/api/hooks/dataCatalogSearch.test.tsx`.
`DataIntelligencePanel.tsx` and
`features/evidence/domain/searchParams.ts` were modified, not deleted.

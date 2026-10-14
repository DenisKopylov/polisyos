# Current Frontend Surface Map

Freshness: 2026-10-14

Owner: `team-frontend`

Source of truth: `architecture/frontend_workspaces.toml`,
`architecture/generated_artifacts.toml`, `schemas/runtime_api_v1.openapi.json`,
`src/polisyos/runtime/http/**`, `apps/runtime-dashboard/**`,
`packages/runtime-api-client/**`, and `apps/runtime-reference-shell/**`.
Evidence pin: `bafca83bff9ff49eef1466bc491a8420b5cd1dbb`.

This is a manual source-and-test map for the frontend in the pinned repository
snapshot. Source files and test cases below were inspected; no tests were run,
and no browser or server was started. The map therefore does not establish
runtime availability, rendered appearance, visual behavior, or deployed data.

## Route And Workspace Shape

The route registry puts `/welcome` and `/public/decisions/:signedId` at the
top level, then mounts the app frame and its nested routes. Inside that frame,
the workspace registry defines six operator workspaces. `clerk` and `analyst`
are interface modes used for workspace visibility; they are not evidence of
server authorization. Feature flags also affect selected workspace visibility.
The route and workspace sources are `apps/runtime-dashboard/src/app/routes/routes.tsx#L209-L243`,
`apps/runtime-dashboard/src/features/runs/route.tsx#L135-L181`, and
`apps/runtime-dashboard/src/app/workspaces.ts#L68-L175`.

| Workspace | Main path and aliases | Mode visibility / flag |
| --- | --- | --- |
| Command center | `/` | `clerk`, `analyst` |
| Scenario composer | `/compose`; `/launch` redirects here | `analyst`; `enableScenarioComposer` |
| Runs and decisions | `/runs` | `clerk`, `analyst`; `enableRunsWorkspace` |
| Evidence fabric | `/evidence`; `/sources` and `/data` resolve here | `analyst` |
| Lex and knowledge | `/knowledge`; `/lex` resolves here | `analyst`; `enableLexKnowledge` |
| Platform health | `/platform`; `/health` resolves here | `analyst`; `enablePlatformHealth` |

Run details add tabbed views, compare/report/deck paths, and the Cycle Board
under the runs feature. `/trust` is registered as a separate artifact-backed
route in the app frame; the public-decision viewer is a public route. This is a
map of the route and workspace registries, not a claim that every route or
feature has a complete producer, verification path, or authority surface.

## Contract, Generation, And Ownership

The dashboard and generated client share the checked-in Runtime API OpenAPI
snapshot, but their generated outputs have different consumers:

```text
Runtime HTTP routes and DTOs
  -> schemas/runtime_api_v1.openapi.json
     -> packages/runtime-api-client/types.ts
        + canonicalRuntimeApiClient.ts/.js
        -> runtime-reference-shell imports canonicalRuntimeApiClient.js
     -> apps/runtime-dashboard/src/api/types.ts
        -> local openapi-fetch client + auth-aware fetch
        -> API hooks, validators, query cache, route components
```

The dashboard client is constructed in
`apps/runtime-dashboard/src/api/client.ts#L1-L27`; it binds local generated
`paths` types to `openapi-fetch` and `authAwareRuntimeFetch`. API hooks use that
client and local response validators. The runtime-reference shell imports the
canonical JavaScript package client, as documented in
`apps/runtime-reference-shell/README.md`. Some dashboard feature DTOs also use
types exported from the shared client package, but the dashboard's normal
request transport remains its local client.

Both generated surfaces use `schemas/runtime_api_v1.openapi.json` as input.
The dashboard generator writes only `apps/runtime-dashboard/src/api/types.ts`
(`apps/runtime-dashboard/scripts/generate-api-client.sh#L45-L56`). The package
generator owns its types and canonical TypeScript/JavaScript pair
(`packages/runtime-api-client/scripts/generate-runtime-api-client.sh` and
`packages/runtime-api-client/README.md#L10-L44`). The generated artifact
registry records both families as committed outputs and marks stale-output
checks as fail-closed (`architecture/generated_artifacts.toml#L794-L890`).

Ownership labels refer to different scopes and should not be collapsed:

| Surface or artifact | Workspace / lifecycle owner | Source detail |
| --- | --- | --- |
| Frontend workspace root | `team-frontend`; backup `team-runtime` | `architecture/frontend_workspaces.toml#L1-L11` |
| Runtime API client package | `team-runtime` workspace owner | `architecture/frontend_workspaces.toml#L13-L39` |
| Runtime dashboard | `team-frontend` workspace owner | `architecture/frontend_workspaces.toml#L41-L68` |
| Runtime reference shell | `team-runtime` workspace owner | `architecture/frontend_workspaces.toml` |
| Generated runtime client and dashboard types | `team-polisyos` artifact owner and approver; `team-frontend` version owner | `architecture/generated_artifacts.toml#L794-L890` |
| Trust posture JSON | `team-architecture` artifact owner and approver | `architecture/generated_artifacts.toml#L2230-L2267` |
| Atlas UI components | Maintenance route `team-frontend / team-design` | `packages/atlas-ui/README.md` |

The `trust-claim-posture-register` family is generated and committed to
`apps/runtime-dashboard/public/atlas/trust-claim-posture.v1.json`; its declared
inputs include tracked posture sources, the ratified identity boundary, and
accessibility evidence. Its generator and stale check are registered in
`architecture/generated_artifacts.toml#L2230-L2270`. The `/trust` page reads
this static asset rather than a Runtime API response.

## Candidate, Status, And Authority Displays

These surfaces use separate status vocabularies. A candidate, a data-promotion
decision, an authenticated report, and a policy-authority claim are different
things in the source contracts.

### Evidence Fabric promotion candidates

The generated `PromotionCandidate` type has `pending`, `approved`, and
`rejected` statuses (`apps/runtime-dashboard/src/api/types.ts#L15190-L15246`).
Evidence Fabric loads the candidate endpoint through a typed query hook and
schema validator (`apps/runtime-dashboard/src/api/hooks/useDataPromotionCandidates.ts#L14-L45`).
Its summary UI displays candidate status and source lane; when mapping one
summary shape, it uses `pending` as a fallback for an absent status
(`apps/runtime-dashboard/src/features/evidence/routes/EvidenceFabricPage.tsx#L187-L204`,
`apps/runtime-dashboard/src/features/evidence/routes/EvidenceFabricPage.tsx#L750-L780`,
`apps/runtime-dashboard/src/features/evidence/routes/EvidenceFabricPage.tsx#L1251-L1282`).

The detailed review surface shows each candidate's status, confidence, source
metadata, and reviewer reason. It checks distinct approve/reject permissions,
disables a decision for a pending request or another reviewer's active lock,
and asks for confirmation before sending the optional reason with the decision
(`apps/runtime-dashboard/src/features/evidence/components/DataIntelligencePanel.tsx#L158-L162`,
`apps/runtime-dashboard/src/features/evidence/components/DataIntelligencePanel.tsx#L418-L451`,
`apps/runtime-dashboard/src/features/evidence/components/DataIntelligencePanel.tsx#L1236-L1301`).
The live component uses `useLivePromotionDecision`: successful POSTs invalidate
candidate and related queries; retryable failures do not queue, terminalize,
or replay a decision (`apps/runtime-dashboard/src/features/evidence/hooks/useLivePromotionDecision.ts#L16-L65`,
`apps/runtime-dashboard/src/features/evidence/hooks/useLivePromotionDecision.test.tsx#L40-L124`).
The component test drives both confirmation dialogs and checks the dispatch
arguments (`apps/runtime-dashboard/src/features/evidence/components/DataIntelligencePanel.test.tsx#L217-L334`).

`usePromotionDecision.ts` also exports a separate optimistic hook wrapper that
snapshots cache state, restores it on request failure, and invalidates after
success (`apps/runtime-dashboard/src/api/hooks/usePromotionDecision.ts#L122-L206`);
the inspected live panel instead calls the request functions through
`useLivePromotionDecision`. Neither an optimistic badge nor an approved data
promotion means that a policy recommendation is authorized or publishable.

### Trust posture and audience detail

The trust page loads the static JSON with `cache: no-store`, captures its raw
bytes, parses it as an untrusted candidate, and admits it only after the Zod
shape check and semantic validation pass. Fetch, encoding, parse, or admission
failure becomes an explicit unavailable result
(`apps/runtime-dashboard/src/features/trust/domain/loadPosture.ts#L6-L79`,
`apps/runtime-dashboard/src/features/trust/domain/posture.ts#L2804-L2813`).
The page defaults to `PUBLIC`; `PUBLIC`, `REVIEWER`, and `EXPERT` are human
detail controls, while the machine export downloads the captured artifact bytes
(`apps/runtime-dashboard/src/features/trust/routes/TrustPosturePage.tsx#L11-L32`,
`apps/runtime-dashboard/src/features/trust/routes/TrustPosturePage.tsx#L71-L109`).

Claim rows are filtered to rows whose artifact audience includes `PUBLIC`.
Switching to reviewer or expert detail does not select a different claim set;
it reveals `authoritative_for`, `may_not_use_for`, evidence references,
establishment classes, and verifier references for those rows
(`apps/runtime-dashboard/src/features/trust/components/ClaimPostureRegister.tsx#L18-L37`,
`apps/runtime-dashboard/src/features/trust/components/ClaimPostureRegister.tsx#L239-L267`).
The page test compares claim-bearing values before and after the reviewer
toggle, and checks that additional evidence detail is revealed
(`apps/runtime-dashboard/src/features/trust/routes/TrustPosturePage.test.tsx#L44-L91`).

The artifact distinguishes source states (`supported`, `planned`, `candidate`,
`blocked`, `not_established`) from effective claim states (`supported`,
`planned`, `blocked`). Effective state composition blocks empty bindings and
any candidate, blocked, or not-established source; a planned state requires
established ownership and an executable closure signal; supported requires
the complete support-predicate set to be satisfied with recomputed or
independently reconciled establishment. `grounded_performance` remains blocked
by this posture evaluator
(`apps/runtime-dashboard/src/features/trust/domain/posture.ts#L34-L55`,
`apps/runtime-dashboard/src/features/trust/domain/posture.ts#L2428-L2469`). The
dashboard displays the artifact's effective state, blocker codes,
limitations, and source dates; it is a consumer of the generated posture
artifact, not the producer of that posture.

### Quantity, lineage, and Trust View

`Quantity` renders the supplied value together with its lineage status and
freshness, uncertainty-dispute cue, and optional provenance popover. The
popover loads lineage on open. `QuantityRuntimeProvider` uses the dashboard's
local typed client for GET `/api/v1/lineage/{lineage_id}`, POST
`/api/v1/lineage/batch`, and the two lineage export GET routes; it validates
responses and carries the active temporal cursor into those requests
(`apps/runtime-dashboard/src/shared/ui/quantity/Quantity.tsx#L78-L297`,
`apps/runtime-dashboard/src/shared/ui/quantity/ProvenancePopover.tsx#L39-L72`,
`apps/runtime-dashboard/src/app/providers/QuantityRuntimeProvider.tsx#L22-L116`).
The provider connects the presentation component to API transport; it does not
produce or admit a policy claim.

The shell's Trust View toggle changes `off`, `compact`, and `expanded`
presentation modes through URL/local preference state. Its metadata component
consumes the trust metadata carried by a quantity or other subject; the toggle
does not select a new server answer or change a permission
(`apps/runtime-dashboard/src/app/providers/TrustViewProvider.tsx#L21-L121`,
`apps/runtime-dashboard/src/shared/ui/trust-view/TrustViewToggle.tsx#L12-L35`,
`apps/runtime-dashboard/src/app/providers/QuantityRuntimeProvider.tsx#L107-L145`).
The display's trust-glyph boundary is deliberately limited: absent or
projection-only metadata is rendered as unknown, and the current presentation
records `content_bound_verification_receipt_missing` rather than promoting a
bare `verification_status: verified`. Source tests exercise missing,
projection-only, and forged presentation inputs, but were not run for this
documentation pass (`apps/runtime-dashboard/src/shared/ui/trust-view/trust-glyphs.ts#L15-L135`,
`apps/runtime-dashboard/src/shared/ui/trust-view/TrustViewAuthority.test.tsx#L15-L128`).
Neither a glyph, detail toggle, lineage status, nor readable provenance is
proof of policy correctness, current authority, or publishability.

### Run-bound predictive-calibration diagnostic

The Overview surface loads and submits the run-bound predictive-calibration
operation through the dashboard's local typed `runtimeApiClient`: GET reads
the existing association and POST submits a strict candidate request. The
hook validates each response and invalidates the GET query after mutation;
its mutation blocks while offline and reuses the `runs.feedback.evaluate`
mutation identity (`apps/runtime-dashboard/src/api/hooks/useRunPredictiveCalibration.ts#L13-L87`).
The form is gated in the UI by `runs.feedback.evaluate`, while the server
declares an owned-run POST dependency on that permission and an owned-run GET
dependency on `runs.review` (`apps/runtime-dashboard/src/features/runs/routes/tabs/OverviewTab.tsx#L1118-L1124`,
`src/polisyos/runtime/http/routes/runs.py#L194-L209`,
`src/polisyos/runtime/http/routes/runs.py#L3960-L4055`).

The dashboard displays the association assessment and calibration summary;
the hook test covers a `limited` association whose
`counterfactual_credibility_status` is `not_established`. This is a diagnostic
candidate surface, not evidence of causal credibility or policy authority
(`apps/runtime-dashboard/src/features/runs/routes/tabs/OverviewTab.tsx#L1310-L1357`,
`apps/runtime-dashboard/src/api/hooks/useRunPredictiveCalibration.test.tsx#L28-L51`).
The generated package types include both HTTP methods, but its inspected
canonical convenience surface exposes a `getRunPredictiveCalibration`
request helper; this dashboard flow does not use that helper
(`packages/runtime-api-client/types.ts#L1771-L1783`,
`packages/runtime-api-client/canonicalRuntimeApiClient.ts#L3439-L3451`).

### Public decision verification

The public viewer fetches `/api/v1/public-decisions/verification` directly,
without credentials, with `no-store` caching and redirects rejected. It checks
that the response record ID matches the requested ID and parses either a
strict report-only schema or the separately discriminated governed-record
schema. The governed schema also binds document/record schema version and the
record ID, decision, issuer, issue time, and digest (`apps/runtime-dashboard/src/features/runs/api/publicDecisionVerification.ts#L152-L220`,
`apps/runtime-dashboard/src/features/runs/api/publicDecisionVerification.ts#L245-L267`).
The server route resolves the ID through its verifier and sets
`Cache-Control: no-store` (`src/polisyos/runtime/http/routes/public_decisions.py#L99-L127`).

The display keeps authentication separate from authority:

- A legacy report-only response has no promoted record and all seven
  verification dimensions constrained to `not_established`. If the report is
  authenticated, the page labels and displays it as a candidate preview, not a
  verified policy decision (`apps/runtime-dashboard/src/features/runs/api/publicDecisionVerification.ts#L23-L54`,
  `apps/runtime-dashboard/src/features/runs/routes/PublicDecisionViewerPage.tsx#L257-L294`).
- A governed public-record response can establish only `issuer_issuance` and
  `projection_faithfulness`. Public history, durable verifiability, current
  authority, status-snapshot selection, and public evidence obtainability stay
  `not_established` in this contract (`apps/runtime-dashboard/src/features/runs/api/publicDecisionVerification.ts#L152-L192`).
- That governed document permits only `bounded_public_custody` and denies
  policy performance, current policy authority, complete public history, and
  first-publication claims. A revoked key can still authenticate historical
  issuance; revocation is not a current-authority assertion
  (`apps/runtime-dashboard/src/features/runs/api/publicDecisionVerification.ts#L99-L150`,
  `apps/runtime-dashboard/src/features/runs/api/publicDecisionVerification.ts#L152-L171`).

The viewer does not admit a browser-created signed packet. Its tests verify
that forged legacy URLs are rejected, report authentication does not establish
decision authority, malformed or authority-inflating governed responses are
withheld, and a route change cannot display a late response for the old ID
(`apps/runtime-dashboard/src/features/runs/routes/PublicDecisionViewerPage.test.tsx#L164-L185`,
`apps/runtime-dashboard/src/features/runs/routes/PublicDecisionViewerPage.test.tsx#L239-L317`,
`apps/runtime-dashboard/src/features/runs/routes/PublicDecisionViewerPage.governed.test.tsx#L206-L265`,
`apps/runtime-dashboard/src/features/runs/routes/PublicDecisionViewerPage.governed.test.tsx#L385-L535`).

The server source also contains an authenticated issuance route for
report-only, governed-record, and governed-record-candidate variants; the
caller selects a run and publication class, not a document or authority
verdict. Its POST declares `require_action_permission(RuntimePermission.PLATFORM_ADMIN, ...)`
bound to the owned existing `run_id` path, and then enforces tenant access
before issuance (`src/polisyos/runtime/http/routes/public_decisions.py#L48-L56`,
`src/polisyos/runtime/http/routes/public_decisions.py#L130-L237`). This
corrects the July audit's source-snapshot claim that no server verification
route or POST action-permission gate existed; it establishes the declarations
in this source, not deployment configuration or successful access enforcement.
A backend test issues and reads back a synthetic governed record and asserts
its limited use/dimension semantics
(`tests/unit/runtime/http/test_public_export.py#L363-L402`). Those source and
test paths do not establish that a record exists or can be issued in a
particular deployment.

### Social-card and email summary code

The dashboard repository contains a typed `PublicShareSummary`, a sanitizer,
email/OG rendering helpers, and tests that render the fixtures and generate
HTML, SVG, and PNG previews. A repository-wide tracked `.ts`, `.tsx`, `.js`,
and `.jsx` source search at the pin finds the `generateOg*` and `EmailSummary`
callsites only in `OGCard.test.tsx`; no production route or service imports
these names. Treat the preview renderer as
`implemented_but_not_orchestrated`, and its `verified` fixture text as input
data rather than verification evidence. The DS0 decision separately keeps
email delivery `surface_out_of_scope` until a notification producer, privacy
and redaction contract, delivery owner, and negative disclosure tests exist
(`apps/runtime-dashboard/src/features/export/social/email-fixtures.ts#L1-L89`,
`apps/runtime-dashboard/src/features/export/social/OGCard.tsx#L1-L140`,
`apps/runtime-dashboard/src/features/export/social/generate-og.ts#L24-L77`,
`apps/runtime-dashboard/src/features/export/social/OGCard.test.tsx#L1-L92`,
`docs/brand/ATLAS_SOURCE_OF_TRUTH.md#L431-L449`). These test fixtures and
renderers do not establish a public publication route, a delivered email, or
a publishable policy system.

## Tests And Evidence Limits

The following source tests are the closest located evidence for the described
semantics; this documentation pass did not execute them:

- Trust artifact admission and tampering: `apps/runtime-dashboard/src/features/trust/domain/posture.test.ts`.
- Trust route audience detail and unavailable behavior: `apps/runtime-dashboard/src/features/trust/routes/TrustPosturePage.test.tsx` and `apps/runtime-dashboard/src/features/trust/routes/TrustPosturePage.route-contract.test.tsx`.
- Promotion POST/cache behavior: `apps/runtime-dashboard/src/api/hooks/promotionDecision.test.tsx`.
- Public viewer report-only and forged-ID behavior: `apps/runtime-dashboard/src/features/runs/routes/PublicDecisionViewerPage.test.tsx`.
- Governed public-record projection and schema negatives: `apps/runtime-dashboard/src/features/runs/routes/PublicDecisionViewerPage.governed.test.tsx`.
- Server issuance and verification: `tests/unit/runtime/http/test_public_export.py`.

The tests establish intended behavior only when run in their configured
environment. This source inspection does not prove visual fidelity, keyboard
behavior in a browser, live-server integration, record availability, audience
enforcement beyond the inspected paths, or current deployment state.

## Stale Or Proposed Design Statements

Several older design records should not be used as the current implementation
inventory:

- The [Atlas live application audit](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/docs/reference/frontend/atlas-live-application-audit.md) is
  explicitly pinned to a different branch and dated 2026-07-16. Its “Public
  Decision URL: Browser-Forgeable” finding says the viewer relies on a browser
  verifier and that no server verifier route exists. The pinned source now has
  a direct server-verification request and a backend route; frontend tests
  reject forged browser packets. Treat that audit's specific route/verifier
  assertion as historical. Its other findings need their own current evidence
  before reuse.
- The active Atlas implementation plan's DS12 text still says the public route
  is frozen pending server verification and classifies the server record
  verifier path as missing (`docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md#L577-L582`,
  `docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md#L1778-L1785`).
  At this source pin, both the verifier and issuer routes are in runtime source,
  and the synthetic issue/readback test exists. The plan's separate warning
  that a real record or current authority must not be inferred remains
  material: the viewer contract explicitly leaves most public dimensions
  unestablished, and route/test presence is not deployment evidence.
- The [Atlas surface constitution and frontend vision](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/docs/system-design-decisions/policyos-atlas-surface-constitution-and-frontend-vision.md)
  marks itself a proposed draft and labels its state as a 2026-06-10 snapshot.
  Its “Proving-Ground Board” section is a proposal, not the current route
  registry. In this pin, `APP_ROUTES` has no `/proving-ground` entry.

## Pattern Pass And Limits

This map was checked against the dashboard/public-projection failure register,
especially P01/P02 (capability without a wired producer/consumer path), P03
(internal richness hidden from the surface), P04/P05/P09 (status and authority
leaks), P10/P15 (semantic adequacy and candidate laundering), and P31/P32
(instance patching and trust by form). The corrective documentation pattern
is to name the typed input, producer or endpoint, consumer behavior, tests
present, and the part that remains unestablished. This map is documentation
and evidence indexing; it does not close a capability, approve a promotion,
or claim a visual or production verification receipt.

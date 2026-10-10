# Independent review: browser consumer companion

## Finding

The 20-line companion is correctly attached to the real source-bound run and
checks the unknown-cost value at the agents consumer. It extends the existing
journey by waiting for a `GET /api/v1/runs/{run_id}/agents` response after
navigating to `/runs/{same-run-id}/agents`, requiring the `run-tab-agents`
surface, and checking `Unknown` within the parent of an exact `Cost` label.
That is a consumer-scoped cost assertion, not an unscoped match against another
`Unknown` label on the page.

The test first gets the run ID from the accepted V1 control job, then performs a
fresh `cache: "no-store"` agents read and checks a cost event with
`cost_origin: "unknown"` and no amount. Its later route navigation is the
dashboard client path for that same run ID: `AgentsTab` calls
`useSuspenseRunAgents`, which fetches `/api/v1/runs/{run_id}/agents`, parses
`runAgentsSchema`, and renders `AgentPipelinePanel`. The panel's domain
normalizer maps an unknown-origin event to a null cost and `costUnknown`; the
English cost field renders that as `Unknown`. The new request wait and
run-specific route therefore connect producer payload, fresh API consumer,
and visible consumer without substituting a hand-authored event.

The underlying opt-in fixture is controlled but follows the real local
producer route. `serve_fixture_runtime_api.py` installs
`source_bound_catalog_profile_fixture` when the fixture environment variable is
set and adds the Legal profile fixture to that runtime. The source-bound fixture
wraps a `ControlledCandidateGateway`; its local proxy removes provider `usage`
from successful responses before the actual traced client and durable budget
settlement path receive them. This supports an unknown-cost candidate
observation only. It does not establish an external fiscal fact, production
currentness, or settlement authority.

The cost locator is appropriately scoped to the cost cell under the agents
surface. It uses the first exact `Cost` field, so the live witness should also
confirm that the fixture's rendered cost row is populated as expected; no DOM
or browser behavior was observed in this static review.

## Existing Legal UI coverage

The journey is not Catalog-only despite its filename and title. Before the V1
run, it visits `/knowledge`, reads the selected Legal search profile for the
fixture output directory, submits its selected intent with the Legal query,
and checks successful vector retrieval and the result. It then mutates the
selected generation ID and checks typed stale-profile refusal with text
fallback and the same fact result. The test also retains the later catalog
profile conflict refusal and V6 partial-history assertions. This proves that
the Legal UI path is present in the journey source; it does not count as an
executed browser witness until the full journey runs.

The composed reconciliation currently says otherwise: its I4 row and follow-up
text state that the journey does not show the Legal UI (lines 45 and 65–66 of
`docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/decisions/composed-task-denominator-reconciliation.md`).
That source claim should be corrected to distinguish the existing Legal UI
assertions from the still-unrun browser witness. The I4 denominator may remain
unchanged unless the owner’s criteria say otherwise.

## Source and verification boundary

- Reviewed base: commit `7b1b50dd1b36d8a67927775e68560eaf4842dbe1`, tree
  `9bad8150d5efa1d2186f0188041de81ef13f15bf`.
- Journey working-tree source:
  `apps/runtime-dashboard/e2e/journeys/catalog-profile-source-bound.spec.ts`
  @ `bca8cf651a363615085a53cdfe1615f4288a377773048e8a84aa8980e3a7f4ea`.
  Relative to the reviewed base, the diff is exactly the requested 20 added
  lines; no other journey lines changed.
- Current route and fixture inputs inspected:
  `apps/runtime-dashboard/scripts/serve_fixture_runtime_api.py` @
  `87b39c9f8c0be64f38bf49334e7bae6bc8c26459691a1a3cc47133e822d5e00f`,
  `apps/runtime-dashboard/scripts/fixture_support/catalog_profile_source_fixture.py`
  @ `c40d9a0344e6ccf343f433c44c60af9ee2ac355dcaa553d6487e1d444cdd9985`,
  `apps/runtime-dashboard/e2e/helpers/runtime-dashboard.ts` @
  `c1cbe7ca10aa5e178064cb08c20d84fa4d0729c88d850a91dea2c92f260f0829`,
  `apps/runtime-dashboard/src/api/hooks/useRunAgents.ts` @
  `ed0666714c84c24fbd38d35bcbc2c38b44312fc6731c8d46cbc60191f096ded2`,
  `apps/runtime-dashboard/src/features/runs/routes/tabs/AgentsTab.tsx` @
  `b436106704c95f80bdcec949f3673bdf79401f3fddf4a88e5f05dd5aaeff3d59`,
  `apps/runtime-dashboard/src/features/runs/components/AgentPipelinePanel.tsx`
  @ `740fa5c11378eecb30c73139ec1c36c7d256a31a61bfce8525e38132f1fb6675`,
  `apps/runtime-dashboard/src/shared/lib/domain/agents.ts` @
  `ed5d7a7035dd9c4edc2c65774d22362db80dc701a6df37389a3891c6092f330d`, and
  `apps/runtime-dashboard/src/shared/i18n/locales/en.json` @
  `ecd9b0330cb0c93fb5c36db4c6673e935e97f0860151f622ec5db15de953e719`.
- Existing static receipts in `LOCAL/raw/browser-consumer-companion/` record
  `corepack pnpm --dir apps/runtime-dashboard run typecheck` (exit 0,
  15.436838 seconds) and Playwright Chromium `--list` (exit 0, one collected
  journey, 0.947139 seconds). The receipt hashes are recorded in
  `static-output-hashes.json`; the captured TypeScript and collection stdout
  hashes match that manifest. Collection is not execution.
- No server, browser, test, or port was started for this review. The full
  source-bound browser journey remains unrun and its rendered verification is
  still `verification_missing` pending the root-owned frozen browser slot.

## Pattern classification

This is P40 same-class, one level deeper: the existing source-bound run and
fresh API DTO establish unknown-cost semantics, while the added route checks
that the existing dashboard consumer does not project that value as a dash or
number. It does not introduce a separate monetary class. The new assertion is
source-complete but not behaviorally verified in a browser yet, so no closure
claim follows from this review.

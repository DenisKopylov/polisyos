# Task P dashboard evidence journal

Date: 2026-09-01
Branch: `codex/debt-p-dashboard-evidence`
Base: `f6c465648`
Source revision: `39b5e0d9ceb453eb8afd4c5429cbef4ebeca50c2`
C13 evidence revision: `cfaf2cac071082be7505e44503a8c6759d7d37c2`

This journal is the append-only execution and closure-attempt record for
`ds10-c13-print-receipt-reissue`, `DS11-INHERITED-C13-PRINT-RECEIPT`, and the
remaining DS9 conjunct of `decision-validity-fixed-temp-concurrency`. It does
not modify an active architecture plan.

## Entry controls and pattern pass

`corepack pnpm install --frozen-lockfile` completed before any TypeScript or
browser result was trusted. Its prepare hook ran against the repository's
shared Git-hooks path; no shared hook was modified or removed. The positive
control then passed: `src/shared/lib/utils.test.ts -t "merges tailwind
classes"` reported one pass and two skips.

The relevant failure-pattern pass was `P28`, `P29`, `P32`, `P33`, `P35`,
`P37`, `P38`, `P40`, and `P41`. The existing defect was a real semantic
migration hidden behind unreachable fixtures: the dashboard still asserted
the superseded `artifact_missing` response although production correctly
failed closed with HTTP 409 `run_paper_source_invalid` when no exact
run-bound `DesignRecord` existed. The target pattern was an exact producer ->
run-bound artifact -> strict HTTP consumer -> governed browser assertion ->
raw receipt chain. The capability labels on entry were
`producer_missing`/`semantic_test_missing`; the acceptance signal was three
distinct exact bindings, the unchanged negative 409 behavior, two complete
3/3 captures, and current-byte admission of all eleven C13 bindings.

## Before and after C13 binding census

The denominator is the complete eleven-member `C13_SOURCE_REFS` population.
At `f6c465648`, five binding digests matched and six were stale. At source
revision `39b5e0d9ceb453eb8afd4c5429cbef4ebeca50c2`, the reissued receipt binds
all eleven current bytes. The fixed eleven-member denominator is preserved;
three additional producer-chain bindings separately prevent the current
fixture producer, helper, or producer contract from drifting behind a green
historical browser receipt.

| Source | prior binding | entry byte | entry | reissued byte |
| --- | --- | --- | --- | --- |
| `src/styles/print.css` | `b087aebb054c89c24196db8b2feeccdeca1095e7c0bb44053aa545bfff4ae9dc` | `b087aebb054c89c24196db8b2feeccdeca1095e7c0bb44053aa545bfff4ae9dc` | current | `b087aebb054c89c24196db8b2feeccdeca1095e7c0bb44053aa545bfff4ae9dc` |
| `AmbientTelemetryHud.tsx` | `232392b06df5bbaca4380a20fd669554d9ddd0f132396c8f290dea5804faf740` | `a06e6a98fc766b48b569d7215ee3e6f390abe8a3022ffe2bb98116ace23093cd` | stale | `a06e6a98fc766b48b569d7215ee3e6f390abe8a3022ffe2bb98116ace23093cd` |
| `OperatorCraftPanel.tsx` | `687a831dce4165393622ed37d60e4269f61b3dd424589b62fb3ae924b1196b66` | `8d94ade694f63613d913042cf36f612e62327b843e01781cd3b9872d365702ef` | stale | `8d94ade694f63613d913042cf36f612e62327b843e01781cd3b9872d365702ef` |
| `RunDetailLayout.tsx` | `514ddff6df513859ec99e2b429e50b7e6bf5c6417b320f416c2a576a744777df` | `f4533fee648a8e2de5fb7ca6bedc56ac1e908b02351019950bae11b21cf25d66` | stale | `f4533fee648a8e2de5fb7ca6bedc56ac1e908b02351019950bae11b21cf25d66` |
| `RunReportPage.tsx` | `4bb0bea6d71ad045d3d129dc9455cb0f4786d723199d77d95a372de2c22542bb` | `bfd0a87a5e0941de7ff4d3f6746cc5e8d4dee52ad25e4b8aff39a5cd440333b7` | stale | `010bb84e6a130d227eacd6e9c656fc16c9624af0559cdee5a5eca86b96d41a13` |
| `RunReportPage.parity.test.tsx` | `59d5eed9242d7bacd58ddfa8a5f61fe71efad62f129c25ac4312fddeae07146e` | `59d5eed9242d7bacd58ddfa8a5f61fe71efad62f129c25ac4312fddeae07146e` | current | `59d5eed9242d7bacd58ddfa8a5f61fe71efad62f129c25ac4312fddeae07146e` |
| `RunReportPage.test.tsx` | `d3b5819eb8e3a0390d4c7bc4f261457ddf2583d504424feaad2584c04ad5b6dd` | `30023d274e3a48235cc72a1dbbe1ee39d8276a5299b9c2c8ab12cbd46c96d1a9` | stale | `45514accacad83df24e2e90129aa2ed874a9b51d0b9cd9a9859b6fa6215c0c38` |
| `src/features/runs/route.tsx` | `710e301c25a11af2a41f169b2571a6f0bb1f68afda370d0248d044b2c6b11d1c` | `710e301c25a11af2a41f169b2571a6f0bb1f68afda370d0248d044b2c6b11d1c` | current | `710e301c25a11af2a41f169b2571a6f0bb1f68afda370d0248d044b2c6b11d1c` |
| `e2e/helpers/pdfGeometry.ts` | `f91afff757dffbb1b8d8ea42f1dc879bbcf18fe9ae428e4b4ba02118fe754f07` | `f91afff757dffbb1b8d8ea42f1dc879bbcf18fe9ae428e4b4ba02118fe754f07` | current | `f91afff757dffbb1b8d8ea42f1dc879bbcf18fe9ae428e4b4ba02118fe754f07` |
| `runtime-dashboard.visual.spec.ts` | `c472f411f4ee512a9e1a54057b8c5a3a64130d6df8a6d79a6c09a4e5efeca8d9` | `3a69dd559452400e50eec543fdf365c03cf5b3d358b6fc04adcb1b8953ce9ab8` | stale | `6976dead2d03638597243866ed29ac3c7ffa33b480bcc281cfcfcc4853e300b2` |
| governed PNG | `26cca8a75e61cfcf8873cfc7417b6bb0c7f2cacdd8490bfa45d256422513041a` | `26cca8a75e61cfcf8873cfc7417b6bb0c7f2cacdd8490bfa45d256422513041a` | current | `26cca8a75e61cfcf8873cfc7417b6bb0c7f2cacdd8490bfa45d256422513041a` |

Full reissued SHA-256 values are content-bound in the machine-readable receipt
below. This census walks eleven of eleven sources; it is not a sampled claim.
The separately enumerated producer chain is three of three:
`serve_fixture_runtime_api.py` at
`210a02646fc4bdade933ca85fa53ced9b91dcdea4ca49d62abd265b5d7826dce`,
`tests/_helpers/runtime_http.py` at
`08246ff951e03835aac8885e7ca38ce154175b75532a311636bdcab33fc7f4bb`,
and `test_fixture_runtime_bound_paper.py` at
`818ce928bf891837a17315701124226747245d135234bd43a6d43a4c572762ec`.

## Fixture and assertion migration

`apps/runtime-dashboard/scripts/serve_fixture_runtime_api.py` now creates
distinct deterministic S2 inputs
for `core`, `empty`, and `growth`, runs the canonical S2 design loop, persists
the result, and publishes exact run/case binding factories only when the
run-paper fixture flag is enabled. `tests/_helpers/runtime_http.py` validates
the `DesignRecord`, `SearchLedger`, and binding references before attaching
them to the three runs. Direct helper callers remain unbound by default, and
`tests/repo_quality/frontend/test_fixture_runtime_bound_paper.py` proves the
three bindings have distinct content digests plus the growth-only 64-output
delta.

The three governed assertions in
`apps/runtime-dashboard/e2e/runtime-dashboard.visual.spec.ts` now require
`record_available_authority_abstaining`, mandatory record/search/binding
references, the typed nonreceipts, three admitted links, and the exact
64-link growth delta. This is a migration to the current production semantics,
not a weakening: two negative API tests still prove that terminal runs without
an exact case binding, including the legacy opt-in fixture path, return HTTP
409. No edit was made to `runs.py`, a governed snapshot, an OpenAPI source, a
generated client, or a schema.

The browser trace also exposed an independent race: two epoch-staleness
requests could finish after decision submission, rebuild the signed packet,
change `packetHash`, and correctly filter the newly created browser-local
annotation. The governed test now waits for those parameterized requests and
the stable decision packet before creating the annotation. The print time
semantics label moved from the bounded identity crop to a sibling section in
the print document; it remains rendered, printed, and tested, while the
unchanged 746×84 governed identity continues to prove the property it names.

## Capture receipts

The two Task C failures remain honest evidence: raw JSON SHA-256
`c25f674d11a722d91c56e2f38baaed4c623ecffc34d2093c779a6114308d2809`
(`run-3`) and
`4596542a9027c1c825a3d1b2fe4c52969032c658c2d3c94dbdfc70613bf9f9e2`
(`run-4`) each selected all three titles and failed 0/3 before the governed
property because their fixtures had no run-bound record.

Task P preserved two further diagnostic failures without normalizing their
reporter bytes. `c13/run-1` (raw SHA-256
`92c680da793d88180eebccf5bf1b18bc8fbe524bdcf5ecb002cf62362df68b6b`)
passed 1/3 and exposed the annotation race plus the stale identity crop.
`c13-passing/run-1` (raw SHA-256
`c93b32e31a727cde8332214f12497b81c8254862818a0f45d967e0f2868784e7`)
passed 2/3 and isolated the annotation race. Those failures identify which
fixture/test changes made the final captures pass; collection success was
never counted as capture success.

The first passing pair under `c13-final` was preserved append-only, then
superseded as the authority-bearing pair after the governed unit test was
repaired to satisfy the dashboard lint gate. That byte-only query repair did
not change the runtime property, but current-byte evidence required a new
source freeze and new captures. From working directory
`/Users/deniskopylov/polisyos/.worktrees/debt-p-dashboard-evidence/policy-engine/apps/runtime-dashboard`,
the final authoritative commands were the following. Their stdout redirection
retained reporter-authored JSON outside the Playwright artifact child:

```text
/usr/bin/env CI=1 PLAYWRIGHT_RETRIES=0 PLAYWRIGHT_INCLUDE_RUN_PAPER_FIXTURES=1 UV_PROJECT_ENVIRONMENT=/Users/deniskopylov/polisyos/.worktrees/debt-p-dashboard-evidence/policy-engine/.venv UV_NO_SYNC=1 PYTHONPATH=/Users/deniskopylov/polisyos/.worktrees/debt-p-dashboard-evidence/policy-engine/src /opt/homebrew/bin/corepack pnpm exec playwright test --config=/Users/deniskopylov/polisyos/.worktrees/debt-p-dashboard-evidence/policy-engine/apps/runtime-dashboard/playwright.visual.config.ts --project=chromium --grep='DS8 governed run paper' --workers=1 --retries=0 --timeout=90000 --global-timeout=240000 --update-snapshots=none --output=/Users/deniskopylov/polisyos/.worktrees/debt-p-dashboard-evidence/policy-engine/docs/superpowers/journals/receipts/2026-09-01-debt-p-dashboard-evidence/c13-final-v2/run-1/artifacts --reporter=json > /Users/deniskopylov/polisyos/.worktrees/debt-p-dashboard-evidence/policy-engine/docs/superpowers/journals/receipts/2026-09-01-debt-p-dashboard-evidence/c13-final-v2/run-1/results.json
/usr/bin/env CI=1 PLAYWRIGHT_RETRIES=0 PLAYWRIGHT_INCLUDE_RUN_PAPER_FIXTURES=1 UV_PROJECT_ENVIRONMENT=/Users/deniskopylov/polisyos/.worktrees/debt-p-dashboard-evidence/policy-engine/.venv UV_NO_SYNC=1 PYTHONPATH=/Users/deniskopylov/polisyos/.worktrees/debt-p-dashboard-evidence/policy-engine/src /opt/homebrew/bin/corepack pnpm exec playwright test --config=/Users/deniskopylov/polisyos/.worktrees/debt-p-dashboard-evidence/policy-engine/apps/runtime-dashboard/playwright.visual.config.ts --project=chromium --grep='DS8 governed run paper' --workers=1 --retries=0 --timeout=90000 --global-timeout=240000 --update-snapshots=none --output=/Users/deniskopylov/polisyos/.worktrees/debt-p-dashboard-evidence/policy-engine/docs/superpowers/journals/receipts/2026-09-01-debt-p-dashboard-evidence/c13-final-v2/run-2/artifacts --reporter=json > /Users/deniskopylov/polisyos/.worktrees/debt-p-dashboard-evidence/policy-engine/docs/superpowers/journals/receipts/2026-09-01-debt-p-dashboard-evidence/c13-final-v2/run-2/results.json
```

Both commands exited 0 with the exact three titles passed once, retry zero,
one worker, and snapshot updates disabled. Run-one raw JSON is 909,230 bytes
at SHA-256
`d690cadf342818aa71db090c538797cc9ade7c65964a2283ad231eb398a010ae`;
run two is 909,294 bytes at SHA-256
`e715358c328aa555017b3afd3fd091aab1fdad5fb85bb58c6813bf85f19c7b34`.
The environment tuple was identical before, between, and after at SHA-256
`a3d2aa1dd115939f50e2274bbef635e9f9efa33a082a96d6f6e3b56bc2efb19f`.
Each base PDF was 16 pages and each growth PDF was 41 pages; growth therefore
added 25 pages in both independent captures. Every page was portrait A4 within
0.5 pt. The governed PNG remained byte-identical at SHA-256
`26cca8a75e61cfcf8873cfc7417b6bb0c7f2cacdd8490bfa45d256422513041a`,
19,197 bytes, 746×84.

## Machine-readable C13 reissue

<!-- TASK-P-C13-PRINT-RECEIPT-REISSUE:START -->
{
  "captures": [
    {
      "capture_id": "task-p-c13-verification-1",
      "environment_sha256": "a3d2aa1dd115939f50e2274bbef635e9f9efa33a082a96d6f6e3b56bc2efb19f",
      "exit_code": 0,
      "output": "docs/superpowers/journals/receipts/2026-09-01-debt-p-dashboard-evidence/c13-final-v2/run-1/artifacts",
      "pdfs": {
        "base_bytes": 184165,
        "base_page_count": 16,
        "base_sha256": "dd4fa6e4dbe65db7fc49d2c5f054062613972065a375ccd5f0a3a5b9d4c0213b",
        "box_height_pt": 841.91998,
        "box_width_pt": 594.95996,
        "grown_bytes": 478058,
        "grown_page_count": 41,
        "grown_sha256": "a29fe774e1ddad59cee7d13fb58bcce29eed887834dd0faf9efae9388869729f",
        "max_height_delta_pt": 0.03018,
        "max_width_delta_pt": 0.31564
      },
      "retries": 0,
      "tests": {
        "failed": 0,
        "passed": 3,
        "skipped": 0,
        "total": 3
      }
    },
    {
      "capture_id": "task-p-c13-verification-2",
      "environment_sha256": "a3d2aa1dd115939f50e2274bbef635e9f9efa33a082a96d6f6e3b56bc2efb19f",
      "exit_code": 0,
      "output": "docs/superpowers/journals/receipts/2026-09-01-debt-p-dashboard-evidence/c13-final-v2/run-2/artifacts",
      "pdfs": {
        "base_bytes": 184190,
        "base_page_count": 16,
        "base_sha256": "2e0762a0572f6b806449756d29f07ded8b1c345629e300d6022e5e21a2b1b281",
        "box_height_pt": 841.91998,
        "box_width_pt": 594.95996,
        "grown_bytes": 478081,
        "grown_page_count": 41,
        "grown_sha256": "a2840d8f6808101ec34cfc1cd422e30c2d0ccc5e111d9af5379b46481c61364e",
        "max_height_delta_pt": 0.03018,
        "max_width_delta_pt": 0.31564
      },
      "retries": 0,
      "tests": {
        "failed": 0,
        "passed": 3,
        "skipped": 0,
        "total": 3
      }
    }
  ],
  "command": {
    "global_timeout_ms": 240000,
    "grep": "DS8 governed run paper",
    "include_run_paper_fixtures": true,
    "project": "chromium",
    "reporter": "json",
    "retries": 0,
    "timeout_ms": 90000,
    "update_snapshots": "none",
    "workers": 1
  },
  "environment": {
    "architecture": "arm64 Apple M2",
    "browser": "Chromium 147.0.7727.15",
    "commit": "39b5e0d9ceb453eb8afd4c5429cbef4ebeca50c2",
    "fonts": {
      "@fontsource/ibm-plex-mono": {
        "file_count": 243,
        "tree_sha256": "80fe419a5ee77cf65cc4565657770a81f275dab4fa9a48bf9c9b3d8dfe77de9e",
        "version": "5.2.7"
      },
      "@fontsource/manrope": {
        "file_count": 148,
        "tree_sha256": "cf76bd50ef127d9a8019fc98b72ebda6f8e8eb6f2737abcdb2d9366437e7c3df",
        "version": "5.2.8"
      }
    },
    "host": "MacBook-Air-Denis.local",
    "kernel": "darwin 25.6.0",
    "os": "macOS 26.6.2 (25G83)",
    "playwright": "1.59.1"
  },
  "environment_probe_producer": {
    "path": "architecture/atlas_surfaces/capture_c13_execution_environment.mjs",
    "sha256": "a5fe832d9ed686a1d808b6307a8bf3123139b7fe5338652fd094e9e980c7e434"
  },
  "environment_sha256_receipts": [
    "a3d2aa1dd115939f50e2274bbef635e9f9efa33a082a96d6f6e3b56bc2efb19f",
    "a3d2aa1dd115939f50e2274bbef635e9f9efa33a082a96d6f6e3b56bc2efb19f",
    "a3d2aa1dd115939f50e2274bbef635e9f9efa33a082a96d6f6e3b56bc2efb19f"
  ],
  "evidence_revision": "cfaf2cac071082be7505e44503a8c6759d7d37c2",
  "predicate_provenance": "recomputed",
  "producer_bindings": [
    {
      "path": "apps/runtime-dashboard/scripts/serve_fixture_runtime_api.py",
      "sha256": "210a02646fc4bdade933ca85fa53ced9b91dcdea4ca49d62abd265b5d7826dce"
    },
    {
      "path": "tests/_helpers/runtime_http.py",
      "sha256": "08246ff951e03835aac8885e7ca38ce154175b75532a311636bdcab33fc7f4bb"
    },
    {
      "path": "tests/repo_quality/frontend/test_fixture_runtime_bound_paper.py",
      "sha256": "818ce928bf891837a17315701124226747245d135234bd43a6d43a4c572762ec"
    }
  ],
  "raw_artifacts": [
    {
      "bytes": 909230,
      "path": "docs/superpowers/journals/receipts/2026-09-01-debt-p-dashboard-evidence/c13-final-v2/run-1/results.json",
      "sha256": "d690cadf342818aa71db090c538797cc9ade7c65964a2283ad231eb398a010ae"
    },
    {
      "bytes": 45,
      "path": "docs/superpowers/journals/receipts/2026-09-01-debt-p-dashboard-evidence/c13-final-v2/run-1/artifacts/.last-run.json",
      "sha256": "91d1c43004802cd49950d78eb11c8fa7d05da8ffffe219a8b13b2f561bc00903"
    },
    {
      "bytes": 909294,
      "path": "docs/superpowers/journals/receipts/2026-09-01-debt-p-dashboard-evidence/c13-final-v2/run-2/results.json",
      "sha256": "e715358c328aa555017b3afd3fd091aab1fdad5fb85bb58c6813bf85f19c7b34"
    },
    {
      "bytes": 45,
      "path": "docs/superpowers/journals/receipts/2026-09-01-debt-p-dashboard-evidence/c13-final-v2/run-2/artifacts/.last-run.json",
      "sha256": "91d1c43004802cd49950d78eb11c8fa7d05da8ffffe219a8b13b2f561bc00903"
    },
    {
      "bytes": 865,
      "path": "docs/superpowers/journals/receipts/2026-09-01-debt-p-dashboard-evidence/c13-final-v2/environment-before.json",
      "sha256": "8facd679acd0a5927e95d235a021f6f342eab037ce39c8f4d0fa202c159102ba"
    },
    {
      "bytes": 866,
      "path": "docs/superpowers/journals/receipts/2026-09-01-debt-p-dashboard-evidence/c13-final-v2/environment-between.json",
      "sha256": "af0cd5e6828e1c292791e6ec01eb9f055eb2eb50a22b852ad5cb95da09320594"
    },
    {
      "bytes": 864,
      "path": "docs/superpowers/journals/receipts/2026-09-01-debt-p-dashboard-evidence/c13-final-v2/environment-after.json",
      "sha256": "e6dfb3463b672678f20900aab281478c28d6555db6db4807cbeed77b37bf652f"
    }
  ],
  "receipt_id": "task-p-c13-run-paper-reissue",
  "reissue_revision": "39b5e0d9ceb453eb8afd4c5429cbef4ebeca50c2",
  "repair_commit": "69aca1e25921e145fecdf57eac5a73f638f11db4",
  "schema_version": "2.0",
  "semantic_conjunction": {
    "bounded_identity_matches_after_font_readiness": true,
    "browser_local_state": 0,
    "hud_craft_chrome": 0,
    "machine_bytes_equal_exact_single_response_body": true,
    "overview_paper_payload_count": 0,
    "report_is_sole_paper_emitter": true,
    "signed_targets": 0,
    "synthetic_links": 0,
    "visible_controls": 0,
    "visible_links_equal_admitted_packet_links": true
  },
  "snapshot": {
    "bytes": 19197,
    "derivation": "first_derivation_under_new_name",
    "height": 84,
    "path": "apps/runtime-dashboard/e2e/runtime-dashboard.visual.spec.ts-snapshots/run-report-identity-a4-print-chromium-darwin.png",
    "sha256": "26cca8a75e61cfcf8873cfc7417b6bb0c7f2cacdd8490bfa45d256422513041a",
    "sha256_receipts": [
      "26cca8a75e61cfcf8873cfc7417b6bb0c7f2cacdd8490bfa45d256422513041a",
      "26cca8a75e61cfcf8873cfc7417b6bb0c7f2cacdd8490bfa45d256422513041a",
      "26cca8a75e61cfcf8873cfc7417b6bb0c7f2cacdd8490bfa45d256422513041a"
    ],
    "width": 746
  },
  "source_bindings": [
    {
      "path": "apps/runtime-dashboard/src/styles/print.css",
      "sha256": "b087aebb054c89c24196db8b2feeccdeca1095e7c0bb44053aa545bfff4ae9dc"
    },
    {
      "path": "apps/runtime-dashboard/src/features/runs/components/AmbientTelemetryHud.tsx",
      "sha256": "a06e6a98fc766b48b569d7215ee3e6f390abe8a3022ffe2bb98116ace23093cd"
    },
    {
      "path": "apps/runtime-dashboard/src/features/runs/components/OperatorCraftPanel.tsx",
      "sha256": "8d94ade694f63613d913042cf36f612e62327b843e01781cd3b9872d365702ef"
    },
    {
      "path": "apps/runtime-dashboard/src/features/runs/routes/RunDetailLayout.tsx",
      "sha256": "f4533fee648a8e2de5fb7ca6bedc56ac1e908b02351019950bae11b21cf25d66"
    },
    {
      "path": "apps/runtime-dashboard/src/features/runs/routes/RunReportPage.tsx",
      "sha256": "010bb84e6a130d227eacd6e9c656fc16c9624af0559cdee5a5eca86b96d41a13"
    },
    {
      "path": "apps/runtime-dashboard/src/features/runs/routes/RunReportPage.parity.test.tsx",
      "sha256": "59d5eed9242d7bacd58ddfa8a5f61fe71efad62f129c25ac4312fddeae07146e"
    },
    {
      "path": "apps/runtime-dashboard/src/features/runs/routes/RunReportPage.test.tsx",
      "sha256": "45514accacad83df24e2e90129aa2ed874a9b51d0b9cd9a9859b6fa6215c0c38"
    },
    {
      "path": "apps/runtime-dashboard/src/features/runs/route.tsx",
      "sha256": "710e301c25a11af2a41f169b2571a6f0bb1f68afda370d0248d044b2c6b11d1c"
    },
    {
      "path": "apps/runtime-dashboard/e2e/helpers/pdfGeometry.ts",
      "sha256": "f91afff757dffbb1b8d8ea42f1dc879bbcf18fe9ae428e4b4ba02118fe754f07"
    },
    {
      "path": "apps/runtime-dashboard/e2e/runtime-dashboard.visual.spec.ts",
      "sha256": "6976dead2d03638597243866ed29ac3c7ffa33b480bcc281cfcfcc4853e300b2"
    },
    {
      "path": "apps/runtime-dashboard/e2e/runtime-dashboard.visual.spec.ts-snapshots/run-report-identity-a4-print-chromium-darwin.png",
      "sha256": "26cca8a75e61cfcf8873cfc7417b6bb0c7f2cacdd8490bfa45d256422513041a"
    }
  ],
  "test_titles": [
    "semantic DOM closes overview and report paper egress",
    "PDF keeps every page A4 and admitted growth adds pages",
    "bounded identity A4 print"
  ],
  "verified_revision": "0440f0a8d6b64c254c37b64144461e5091e2b1db"
}
<!-- TASK-P-C13-PRINT-RECEIPT-REISSUE:END -->

The canonical (`sort_keys`, compact separators) receipt SHA-256 is
`dd61ccd579fdf860a648ff580a139244e7351fb0eca063f55e6747287a529006`.
The historical `verified_revision` is retained because it is the immutable
DS6 register-transition witness. `reissue_revision` is the current source
byte witness, and `evidence_revision` is the immutable raw-capture witness.
Conflating those roles would make the old transition unauditable or the new
source admission false.

## DS9 capture receipt

The first post-repair DS9 invocation passed all four selected identities, but
its shell redirection placed `results.json` inside Playwright's configured
output directory. Playwright correctly cleared that directory at startup, so
only the reporter-authored `.last-run.json` survived. It is retained under
`ds9-final/run-1` as an evidence nonreceipt and is not counted as capture
success.

The replacement invocation ran from
`/Users/deniskopylov/polisyos/.worktrees/debt-p-dashboard-evidence/policy-engine`,
used a fresh append-only directory, and placed the raw reporter JSON outside
the Playwright artifact child:

```text
CI=1 PLAYWRIGHT_RETRIES=0 PLAYWRIGHT_INCLUDE_RUN_PAPER_FIXTURES=1 UV_PROJECT_ENVIRONMENT=/Users/deniskopylov/polisyos/.worktrees/debt-p-dashboard-evidence/policy-engine/.venv UV_NO_SYNC=1 PYTHONPATH=/Users/deniskopylov/polisyos/.worktrees/debt-p-dashboard-evidence/policy-engine/src /opt/homebrew/bin/corepack pnpm --filter @polisyos/runtime-dashboard exec playwright test --config=playwright.visual.config.ts --project=chromium --grep='DS9 human decision gate' --workers=1 --retries=0 --timeout=90000 --global-timeout=240000 --update-snapshots=none --output=/Users/deniskopylov/polisyos/.worktrees/debt-p-dashboard-evidence/policy-engine/docs/superpowers/journals/receipts/2026-09-01-debt-p-dashboard-evidence/ds9-final/run-2/artifacts --reporter=json > /Users/deniskopylov/polisyos/.worktrees/debt-p-dashboard-evidence/policy-engine/docs/superpowers/journals/receipts/2026-09-01-debt-p-dashboard-evidence/ds9-final/run-2/results.json
```

It exited 0. The raw JSON is 8,561 bytes at SHA-256
`7c865806b5b898bff5417bae657aa672d4bd21ab234fa2e1cc617bdaeaca0e83`;
the `.last-run.json` is 45 bytes at SHA-256
`91d1c43004802cd49950d78eb11c8fa7d05da8ffffe219a8b13b2f561bc00903`.
The reporter records Playwright 1.59.1, global timeout 240,000 ms,
`updateSnapshots=none`, one worker, Chromium timeout 90,000 ms, retry zero,
and `expected=4`, `unexpected=0`, `flaky=0`, `skipped=0`. These exact four
titles passed once at retry zero:

1. `available pre-action gate retains readable hierarchy`
2. `blocked pre-action gate retains readable hierarchy with long reason TTL and provenance`
3. `reflows at 320px and 200% zoom and preserves keyboard contestability`
4. `remains absent from the public decision route`

The fixture now lets all three case-workspace variants render the real page.
The governed assertions require the current authority-abstaining inspection
state; the public-route case supplies and asserts typed epoch nonreceipt. This
is capture success, not collection success: all four reporter results are
`passed`, and the raw bytes are retained.

## Gate terminal output and the governing stop

The exact C13 conjunction is green:

```text
$ /Users/deniskopylov/polisyos/.worktrees/debt-p-dashboard-evidence/policy-engine/.venv/bin/python -m pytest /Users/deniskopylov/polisyos/.worktrees/debt-p-dashboard-evidence/policy-engine/architecture/atlas_surfaces/test_frontend_disposition_register.py::DS6C13PrintTransitionTests::test_independent_receipt_binds_the_full_conjunction_and_current_bytes -q
.                                                                        [100%]
exit 0
```

The global frontend-disposition checker is not green. Its exact final output
is preserved because the user-supplied stop rule forbids the schema change
required to admit the current source denominator:

```text
$ PYTHONPATH=/Users/deniskopylov/polisyos/.worktrees/debt-p-dashboard-evidence/policy-engine/src:/Users/deniskopylov/polisyos/.worktrees/debt-p-dashboard-evidence/policy-engine /Users/deniskopylov/polisyos/.worktrees/debt-p-dashboard-evidence/policy-engine/.venv/bin/python /Users/deniskopylov/polisyos/.worktrees/debt-p-dashboard-evidence/policy-engine/architecture/atlas_surfaces/check_frontend_disposition_register.py --check
ds18_time_semantics_landing_slice_reconciliation_required:file_manifest_sha256
ds18_time_semantics_landing_slice_reconciliation_required:root_manifest_sha256
ds18_time_semantics_file_receipt_drift:apps/runtime-dashboard/src/features/runs/routes/RunReportPage.tsx:source_sha256
ds18_time_semantics_root_inventory_drift:apps/runtime-dashboard/src/features/runs/routes/RunReportPage.tsx
ds18_time_semantics_root_receipt_drift:apps/runtime-dashboard/src/features/runs/routes/RunReportPage.tsx:RunPaperDocument:jsx:322:5:root_source_sha256
ds18_time_semantics_file_receipt_drift:apps/runtime-dashboard/src/features/trust/domain/posture.ts:source_sha256
ds18_time_semantics_behavioral_evidence_drift:apps/runtime-dashboard/src/features/runs/routes/RunReportPage.tsx:PaperFact:jsx:35:5:apps/runtime-dashboard/src/features/runs/routes/RunReportPage.test.tsx
ds18_time_semantics_behavioral_evidence_drift:apps/runtime-dashboard/src/features/runs/routes/RunReportPage.tsx:CaseRecordSection:jsx:72:9:apps/runtime-dashboard/src/features/runs/routes/RunReportPage.test.tsx
ds18_time_semantics_behavioral_evidence_drift:apps/runtime-dashboard/src/features/runs/routes/RunReportPage.tsx:CaseRecordSection:jsx:124:9:apps/runtime-dashboard/src/features/runs/routes/RunReportPage.test.tsx
ds18_time_semantics_behavioral_evidence_drift:apps/runtime-dashboard/src/features/runs/routes/RunReportPage.tsx:CaseRecordSection:jsx:247:9:apps/runtime-dashboard/src/features/runs/routes/RunReportPage.test.tsx
ds18_time_semantics_behavioral_evidence_drift:apps/runtime-dashboard/src/features/runs/routes/RunReportPage.tsx:RunPaperDocument:jsx:322:5:apps/runtime-dashboard/src/features/runs/routes/RunReportPage.test.tsx
ds18_time_semantics_count_drift:inherits_admitted_dom_root_count
ds18_time_semantics_count_drift:obligated_root_count
ds18_time_semantics_count_drift:covered_root_count
ds18_time_semantics_source_bytes_drift:Task-D-dashboard-freeze:exit=1
census_observation_drift:census-browser-signing-protected-live:reference_count
typescript_reference_content_drift:apps/runtime-dashboard/e2e/runtime-dashboard.visual.spec.ts#ts-identity=eyJkZWNsYXJhdGlvbl9jaGFpbiI6WyJjYWxsOmJ1aWxkU2lnbmVkUHVibGljRGVjaXNpb25QYWNrZXQ6ZW5jbG9zaW5nOnBhY2tldCIsInN5bWJvbDpidWlsZFNpZ25lZFB1YmxpY0RlY2lzaW9uUGFja2V0IiwicmVzb2x2ZWQ6YnVpbGRTaWduZWRQdWJsaWNEZWNpc2lvblBhY2tldCIsImRlY2xhcmF0aW9uOmFwcHMvcnVudGltZS1kYXNoYm9hcmQvc3JjL2ZlYXR1cmVzL3J1bnMvZG9tYWluL3B1YmxpY2F0aW9uUGFja2V0LnRzOkZ1bmN0aW9uRGVjbGFyYXRpb24iXSwiZGlzY3JpbWluYXRvciI6ImJ1aWxkU2lnbmVkUHVibGljRGVjaXNpb25QYWNrZXQiLCJub3JtYWxpemVkX3Rva2Vuc19zaGEyNTYiOiJhZDMyY2VjNzc5YjIzMjJiZDYyY2NjMTM1NzQyMDczNjE2YjhmZDk1Nzg5ZGQ5YWNiMjliOGY0MGEwZGQzMDMyIiwicm9sZSI6ImNhbGxfZXhwcmVzc2lvbiIsInNvdXJjZV9wYXRoIjoiYXBwcy9ydW50aW1lLWRhc2hib2FyZC9lMmUvcnVudGltZS1kYXNoYm9hcmQudmlzdWFsLnNwZWMudHMiLCJzdHJ1Y3R1cmFsX3BhdGgiOlsiRXhwcmVzc2lvblN0YXRlbWVudDo0MyIsIkNhbGxFeHByZXNzaW9uOjAiLCJBcnJvd0Z1bmN0aW9uOjIiLCJCbG9jazoxIiwiRXhwcmVzc2lvblN0YXRlbWVudDoyMCIsIkNhbGxFeHByZXNzaW9uOjAiLCJBcnJvd0Z1bmN0aW9uOjIiLCJCbG9jazoxIiwiRXhwcmVzc2lvblN0YXRlbWVudDozIiwiQ2FsbEV4cHJlc3Npb246MCIsIkFycm93RnVuY3Rpb246MiIsIkJsb2NrOjMiLCJGaXJzdFN0YXRlbWVudDoyIiwiVmFyaWFibGVEZWNsYXJhdGlvbkxpc3Q6MCIsIlZhcmlhYmxlRGVjbGFyYXRpb246MCIsIkNhbGxFeHByZXNzaW9uOjEiXSwidmVyc2lvbiI6MX0
exit 1
```

The final identity line above is copied as terminal text; its long opaque
identity does not carry independent semantic warrant. The deciding rule is
the DS18 schema itself: lines 2566-2568 fix the sole reconciliation to
`Task-D-dashboard-freeze` at `03c5783609271c27d6f3d212b76dda7eddef2074`,
and lines 2621-2625 require exactly one item (`minItems=1`, `maxItems=1`). The
complete current denominator needs a second append-only source
reconciliation: it must retain Task D, content-bind the already-present
`posture.ts` change, and bind Task P's `RunReportPage.tsx`/test changes. A
landing cannot substitute because this transition has zero entrants and zero
exits; overwriting Task D would falsify checkpoint provenance. Independent
review also found no honest CSS-only route: unchanged DOM plus visible in-flow
epoch content makes the governed identity 746×332 rather than 746×84, while
clipping that semantic descendant from the locator would weaken the capture.
The smallest honest migration is therefore the sibling print section already
captured, followed by a schema-versioned append-only DS18 reconciliation.
That schema change is explicitly forbidden in Task P, so no schema, register,
report, snapshot, OpenAPI source, generated client, or `runs.py` contract was
changed to manufacture a green result.

## Closeout verification

- The complete C13 transition class plus the DS10
  current-receipt/retired-nonclosure node pass 11/11; this includes the exact
  required conjunction, raw-artifact/property-removal falsifiers, all three
  current producer-byte falsifiers, and wrong producer-population negatives.
- The DS15 transition candidate test exits 1 on the same DS18 source
  reconciliation and protected-signing identity drift shown by global
  `--check`. It is not counted as a new failure class or a passing Task P
  gate; closing it requires the same forbidden schema migration and companion
  rebind.
- The fixture producer plus both strict-409 negatives pass 5/5. The two
  negative cases still return `run_paper_source_invalid` for an unbound
  terminal run and for the legacy opt-in empty/growth fixtures.
- Dashboard typecheck exits 0; `RunReportPage.test.tsx` passes 3/3; Prettier
  over all three changed TypeScript files exits 0. ESLint over every changed
  production, e2e, and test TypeScript file exits 0. The two original
  `testing-library/no-node-access` findings were repaired with scoped Testing
  Library queries, committed as the final source revision, and followed by a
  fresh authoritative two-capture pair; they are not carried as debt.
- Ruff passes all three changed fixture/helper Python files. The current two
  governed architecture Python artifacts emit 703 file-wide style findings;
  the complete Ruff diagnostic/diff-line intersection is empty. Their base
  provenance is `not_established`; no unrelated mass formatting was performed.
- `check_docs_lifecycle.py` reproduces the carried baseline: exit 1 with
  exactly six findings (two active-plan metadata findings and four removed
  stub references). Architecture guardrails exit 1 on three deep imports from
  `acquisition_admission_bundle.py`; that source and the import baseline are
  disjoint from Task P's changed paths, but provenance remains
  `not_established` because this lane did not replay the exact command at a
  pre-Task-P base.
- `check_debt_ledger.py --check` exits 0 with zero blocking findings. Its
  complete output reports 178 register IDs, 22 Atlas debt rows, 29 explicit
  nonclosure entries, and ten informational unresolvable closure identities;
  none is blocking.
- `git diff --check` is clean across every human-authored Task P path and this
  journal. A repository-wide invocation reports trailing spaces only inside
  Playwright-authored diagnostic `error-context.md` bytes retained from the
  two honest failing captures; those reporter bytes are intentionally not
  normalized.

## Exact append-only prose for architect transcription

### `ds10-c13-print-receipt-reissue`

> **TASK P 2026-09-01 — `blocked` (`verification_missing`).** The dashboard
> corridor now provides three distinct content-bound S2 `DesignRecord`
> fixtures; both strict unbound-run HTTP 409 negatives remain green; two fresh
> single-worker, zero-retry, `--update-snapshots=none` captures pass all three
> governed titles; raw JSON SHA-256 values are `d690cadf...` and
> `e715358c...`; and the exact C13 conjunction admits all 11/11 current source
> bytes plus all 3/3 current producer-chain bytes at exit 0. The row does not
> close because its second required gate, global
> frontend-disposition `--check`, exits 1 on the complete current DS18/source
> census. `blocked_by`: a schema-versioned append-only DS18 source
> reconciliation that preserves Task D and adds Task P; schema v1 fixes the
> sole item to Task D and enforces `maxItems=1`. Task P's stop rule forbids the
> required schema change, and no snapshot, 409 contract, source census, or
> checkpoint provenance was weakened to substitute a false green.

### `DS11-INHERITED-C13-PRINT-RECEIPT`

> **TASK P 2026-09-01 — `blocked` (`verification_missing`), independently
> recorded.** Task P does not close this inherited DS11 half by substitution:
> it records its own two 3/3 raw captures, 11/11 current-source and 3/3
> producer-chain byte reissue, strict HTTP 409 negatives, and green exact
> conjunction. The separately required
> global frontend-disposition gate remains exit 1 for the same complete-current
> DS18 reconciliation, whose schema-versioned second checkpoint is forbidden
> in this lane. `blocked_by`: preserve Task D's immutable source checkpoint and
> append a content-bound Task P reconciliation after the schema admits more
> than one source reconciliation; then rebind the protected signing census and
> replay global `--check`. Task C's failures remain history, not this row's
> closure.

### `decision-validity-fixed-temp-concurrency`

> **TASK P 2026-09-01 — remaining DS9 conjunct `open` -> `closed`.** The Task M
> promotion/generation conjunct is carried closed and the already-correct
> UUID/O_EXCL/0600/fsync/atomic-replace writer was not re-litigated. After the
> fixture/collection repair, the exact single-worker, zero-retry,
> `--update-snapshots=none` DS9 command reaches and passes all four identities
> at exit 0, including current authority-abstaining case-workspace semantics,
> 320px/200% keyboard contestability, and typed epoch nonreceipt on the public
> route. Reporter-authored JSON is 8,561 bytes at SHA-256 `7c865806...`, with
> `expected=4`, `unexpected=0`, `flaky=0`, and `skipped=0`. The earlier passing
> invocation whose reporter target was cleared is retained only as an evidence
> nonreceipt; collection or an unretained pass was not used as closure.

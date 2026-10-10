# DX0 native preflight: import debt and expiry issuers

This is a read-only source-state audit plus the authorized removal of 21 unused
expired import-exception selectors. It is not the native SOTA wave. No expiry
dates were moved and no live import violations were waived or classified as
inherited.

## Evidence and denominator

The complete pre-edit contract-only finding set contains 82 rows. Its exact
row/issuer/expiry mapping is retained in
[`sota-contract-expiry-issuer-inventory.json`](sota-contract-expiry-issuer-inventory.json)
(SHA-256 `e911732449b6b99e3a4d9c3ad26ed419a1b40bd6a90b619ae798e888e28bd1e6`,
82 rows, inventory candidate `9e89dddfbcc3d8c44a421cc1fc143ec84f3753ae`,
slice base `93d6aa62a8d236667fdf322a5fc17962523b185e`). The current pre-edit
contract report is `LOCAL/raw/native-preflight/contract-current.json`
(SHA-256 `0ccefb36427c48cb7030eda8b262e988d513572fd9cb160d01e1737659761607`).
After retiring the import rows, the contract report has 61 findings:
1 docs-freshness, 9 complexity, 12 shims, and 39 Phase 6.5. The full output is
`LOCAL/raw/native-preflight/contract-after-import-exception-retirement.json`
(SHA-256 `9e0d9887fea10cbf6f22c91d2bfd4f1079f1f26a36b02205eebd15a5d7b96a85`).

These are contract-only metadata findings. Expiry is checked as a date field;
an expired row is not evidence that the obligation is resolved, and an expired
row cannot be made current by changing its date alone. No native child gate or
full SOTA wave was run here.

## Retired import exceptions

The pre-edit full import-linter stdout is
`LOCAL/raw/native-preflight/import-linter-current.stdout.bin` (SHA-256
`a07704f4fa6fd456eec96dabe8be76e741eeeb87d21e2e31233af60f2db2975c`). A
complete selector replay found zero coverage for all 21 exception selectors;
an empty-registry before/after comparison preserved the same 21 live violation
identities. The proof receipt is
`LOCAL/raw/native-preflight/import-exception-retirement-proof.json` (SHA-256
`bc5fd7ead6d7e564e56acda649baf528a6b8d879c30dc952071ad6384017e4aa`). The
post-edit complete output is
`LOCAL/raw/native-preflight/import-linter-after-retirement-current.stdout.bin`
(SHA-256 `349adc6499eaaeb44f22d9e35dee4fc3d08371a67f2abb98052eba99bf3a5034`,
11,489 bytes, exit 1, 21 current violations, 0 lapsed covers, 0 exception
matches). Current and empty-scratch outputs match. The exact pre-edit registry
is identified by `architecture/imports/exceptions.toml@74de9ec4637a00ecc840f6c9ee4a402ed25a269c0b8b6f21f61a37d7b0f5db79`. Post-edit TOML SHA-256 is
`d21239455043387a83ffe8eafb1142ce23a90747579746ed2231efffc86c6433`; Markdown
SHA-256 is `6eac5fc2d09449eb4e7aba741e832fdd930f7407530764aed0ed6f066b7df32d`.
The 21 matching rows were removed from both registries; no active violation
was exported or waived.

The 21 live violations are grouped by existing contract path:

| Count | Current sources | Smallest established path |
| --- | --- | --- |
| 1 | `src/polisyos/fabric/retrieval/service.py:42` | TYPE_CHECKING catalog types are already exported by `polisyos.data_forge.read_api.catalog`. |
| 11 | `src/polisyos/foundry/methods/catalog/causal/literature_prior.py:27`; `src/polisyos/scientist/cross_graph/compiler.py:87`; `scientist/methods/discovery/prior_miner.py:28`; `scientist/nodes/builtins/causal/build_literature_prior.py:42`, `resolve_parameters.py:39`, `resolve_transport.py:90`; `scientist/nodes/builtins/planning/compile_cross_graph_evidence.py:64`, `run_discovery_blueprint_runtime.py:65`, `run_hierarchical_policy_search.py:90`; `scientist/orchestration/engine/context.py:11`, `protocol.py:15` | `PreparedSKGRead` is already exported from `polisyos.data_forge.read_api.academic`. |
| 1 | `src/polisyos/ir/analytics/posterior_summary.py:20` | `ArtifactRef` is exported from `polisyos.core.artifacts`. |
| 2 | `src/polisyos/runtime/quality/chronology_proof.py:18`; `generation_source.py:19` | Existing public artifact projection/hash helpers can replace private `ManifestLifecycle` use. |
| 1 | `src/polisyos/ir/migrations/base.py:10` | `common.migrations` has no equivalent public generic migration-engine API; owner-approved API or ownership change is required. |
| 4 | `src/polisyos/runtime/quality/workspace/foundry_consumption.py:33`, `:1024`, `:1025`, `:1030` | `policy_grammar`, `obligation_graph`, and `obligation_rules` are direction-level semantic dependencies disallowed by the current runtime policy; this requires an architecture decision, not a path exception. |
| 1 | `src/polisyos/scientist/agent/feasibility.py:231` | The consumer catches private Foundry `_SnapshotStateLayoutError`; preserve typed behavior through a public error contract or move ownership. |

The complete retained output above has full source contexts. The linter was
not replayed from the exact slice base for P41, so these 21 current violations
are **not classified as inherited**.

## Remaining 61 expiry rows

The exact 61 registry records, issuing owners, and dates are in the linked
82-row inventory and the current 61-row report above. Current source state
supports the following triage; items called candidates still need the relevant
consumer or domain gate before registry cleanup.

| Rows | Issuer(s) | Current source evidence | Minimum next evidence |
| --- | --- | --- | --- |
| 1 docs freshness | `team-docs` | Baseline expired 2026-06-30; freshness accuracy is not established by this contract scan. | Run the declared docs-accuracy check and record its current count/hash; remove only if it closes. |
| 9 complexity | `team-lex` (1), `team-scientist` (8) | `lex/interventions.py` is 545 lines (registered 1,276); `build_decision_packet.py` is a 6-line import facade. The other seven exception files are 4,000, 2,381, 2,442, 1,778, 1,686, 1,103, and 1,281 lines, each above the 1,000-line default. | Run the module-size/complexity child and remove rows only for modules that satisfy its measured property; the two smaller files are candidates, not yet gate-proven. |
| 12 shims | `team-devx` (3), `team-research` (2), `team-architecture` (6), `team-universal-compilation` (1) | Eight file-relocation rows have missing old paths and existing targets (two research scripts; six import/freeze config paths). Three product wrappers still exist at both source and target. The family fallback helper is present and called under a default-false flag. | For relocations, prove current callers and compatibility obligations at the actual path level, then get the owning team's removal decision. The existing last-mile caller script scans Python FQNs/planned moves; it does not establish closure of those six file-path rows. For wrappers and fallback, current use/feature behavior remains. |
| 1 dynamic import registry | `team-architecture` | Expired review date; current dynamic import patterns/extension slots remain registered. | Current owner review of each active slot and its verifier, then update or retire only the resolved records. |
| 6 package exceptions | `team-scientist` (4), `team-core` (1), `team-fabric` (1) | Four SLO entries remain `status=exception` with empty objectives. Two package Ruff ratchets remain represented in package and override registries. Common is marked `covered_by_dependents`, which may support a no-standalone-SLO decision but does not itself retire the duplicate expired exception rows. | Package owner supplies measured standalone SLO or explicit dependent-coverage/out-of-scope disposition; Ruff owners supply current package ratchet evidence. |
| 9 test ratchets | `team-quality` (3 including universe), `team-fabric` (2), `team-foundry` (1), `team-lex` (1), `team-runtime` (1), `team-scientist` (1) | The universe and package mirror/strict-mirror exception fields remain in `architecture/tests/ratchets.toml`; no ratchet report was run. | Run the test-ratchet child over its full configured roots; remove a field only where its measured baseline is met or the exact test slice has an owner-approved disposition. |
| 4 static-analysis overrides | `team-fabric` (2), `team-ir` (2) | All four `override_scope` records remain `report_only`; current effective override use is not established here. | Run the dead-overrides report plus the exact Ruff/mypy package checks; prune only proven-unused entries or return an owner-specific cleanup plan. |
| 10 observability exceptions | `team-core`, `team-architecture` (2), `team-foundry`, `team-security` (same five owners duplicated across component and ops indexes) | Both registries still carry expired exception metadata. Their SLO files are stubs with `status: exception`, expired date, and `objectives: []`. | Produce actual SLO objectives/operability evidence or a precise owner decision that the component is outside standalone service scope, then reconcile both registries. |
| 5 runbook/SLO exceptions | `team-core`, `team-security`, `team-foundry`, `team-architecture` (2) | Runbook coverage rows still carry expired exception fields; the corresponding SLO files remain exception stubs. | Tie each row to the observed service surface, real SLO, and runbook coverage; if no standalone service exists, record the owner's scoped disposition rather than extending the date. |
| 4 name-registry rows | `team-architecture` (discovery, errors), `team-foundry/team-scientist` (runtime), `team-foundry` (causal) | `core/discovery` and `foundry/runtime` still exist; the scientist discovery path moved. The supposedly empty Foundry causal path still contains `README.md` and `_facade.py`. For errors, both the old and proposed fixture directories are absent. | Architecture/package owners resolve the remaining contexts. For errors, verify data/caller references and determine whether the backlog row is obsolete before removing it. |

The inventory's issuer field is the accountable source owner, not authorization
to renew. Minimum issuance is fresh property evidence from the relevant child
gate plus a disposition from that owner; where the source property is resolved,
remove its obsolete row and mirrored record instead of changing the clock.

## Pattern and closeout status

- `P35`: 82/61 counts come from complete JSON reports; the 82 row-level issuer
  mapping is retained once, not duplicated here.
- `P38`: the contract-only expiry gate measures the expiry field, not whether
  the underlying SLO, shim, module, or ratchet obligation is resolved. The
  existing Python caller report does not cover the file-path relocation rows.
- `P41`: no exact slice-base replay and complete-denominator zero-intersection
  proof was done for the 21 current live import violations; no inherited debt
  is claimed.
- This was not a native SOTA run. Root should perform the single composed
  native wave after source/review freeze with full child-output receipts.

# Original CI findings: repair decisions and bounded local receipts

Stage 1, 2026-09-11. Slice base `cc74d6581`, attached
`codex/instrument-honesty`. Execution follows the committed/read-back decisions
and follows invocation and dashboard implementation. Root serializes shared
files. This decision does not claim hosted CI success.

## Evidence identity and the unit of work

The triage is C-CI in
`docs/superpowers/specs/2026-09-10-apparatus-station-and-ci.md@cc74d6581`.
Its concrete finding IDs are `CI-F*`, `CI-S*`, `CI-R*`, `CI-B*`, `CI-C*`;
those identities, not the parent debt row's prose, drive this work. All five
original failed-job logs were downloaded again using ordinary read-only `gh`
commands. The complete bytes match the five SHA256 values recorded by C-CI.
They are retained in `docs/superpowers/journals/instruments/root/raw/` as
`run-<id>-failed.log`. Run IDs: Fast 34196405835, Standard 34196405796,
Runtime 34196405891, Fabric 34196405795, Canary 34196405782. Historical commit
is `20082e545ba89cefc2fd913e1723f6ef7c63df39`. No other lane branch is needed.

CI-RESEARCH-01: decoding complete JSON objects in the original Fast log finds
the primary package report's full 243-member findings array. Its owner field is
`check`; grouping by another guessed key would produce a meaningless count.
CI-RESEARCH-02: every final FAILED line in the original Runtime log gives six
test nodes, including both inadequate metrics collaborators. CI-RESEARCH-03:
the Standard log includes interpreter failure for S01/S03 and executable
provenance mismatch for S02. They are distinct classes. CI-RESEARCH-04: seven
publication-aware Docs Contract links fail even though the separate Link Check
succeeds. Raw source files, generated source owners and new command receipts
will decide the current state; these historical facts do not establish it.

Do not add counts from test nodes, package findings, jobs and derived aggregates.
Compare complete identities/classes before drawing a change conclusion. A
traceback or unequal provisioning makes an aggregate comparison inadmissible.
Current targeted replay is bounded local evidence, never a substitute for a
cancelled hosted job. Historical ownership is not_established unless the exact
slice-base replay and a complete disjoint-input proof both establish it.

## Strategy and non-test callers

Reuse current owners first; most findings are failures of existing contracts,
not justification for new subsystems. Repair real producer/consumer defects at
their owning seams, then regenerate only the affected outputs through canonical
commands. For inaccurate instruments, preserve real findings while naming what
their scan did not measure. Do not quiet a scanner through thresholds, expiry
extensions, allowlist additions, skipped files, or new marker conventions.

Existing production paths to compose:

* `execute_live_catalog_acquisition` is called by the acquisition runtime's
  catalog flow. Compose Core's `ArtifactStoreConfig`/`build_artifact_store` and
  existing injectable registry providers, keeping quarantine/admission semantics.
* `ConnectionConfig.redacted` -> `scan_secret_and_pii` -> `PromptSanitizer` is
  consumed by connector logging and connection-configuration custody hashes.
  Preserve scanner-owned redaction vocabulary and immutable Mapping output;
  never replace a redacted credentials mapping with an apparently empty one.
* Runtime container overrides feed application construction, CAS metrics and
  JWT/cell middleware. Test collaborators must satisfy that actual protocol;
  adding production `getattr` fallbacks would hide the failed contract.
* OpenAPI examples/types are emitted by `runtime/http/openapi_contract.py` and
  canonical schema/type generators, then consumed by clients and strict contract
  tests. Fix clocks/fixtures at their owner before regenerating; status and epoch
  semantics are not snapshot conveniences.
* `tools/ci/check_scientist_phase1_gate.py` is already invoked by
  `polisyos-tools ci check-scientist-phase1-gate` and Core Runtime workflow. Its
  current deep-copy predicate searches an exact substring, although its key
  claims absence of live hot-path copies. AST source analysis can measure
  syntactically explicit copy requests, not liveness or execution cost. Preserve
  the copy finding, make that limitation explicit and test whitespace/alias/
  dynamic-argument cases. Never remove defensive nested-copy isolation merely
  to satisfy a source-string check.
* Package/import, directory, docs accuracy, generated tool-reference and broad
  exception owners already have CLI consumers. Extend them only when an actual
  current falsifier identifies a measurement defect. No new path-only executable
  is planned; anything new must first receive a discoverable non-test caller in
  an addendum committed before its source implementation.

## Finding-by-finding decisions

| C-CI IDs | Owner / seam / decision | Deciding falsifier and bounded outcome |
| --- | --- | --- |
| F01 | Workflow policy; retain current valid workflows. | Revalidate each workflow actually changed; no historical green claim about future edits. |
| F02 | `architecture/imports/exceptions.toml` and exception validator. | Full current expired-exception identity set; an expired still-used exception stays rejected. Do not extend dates without architectural validity evidence. |
| F03 | Import boundary owner and current edge graph. | Compare edge identities, distinguish permitted import from increased hidden coupling; no baseline acceptance by count. |
| F04 | Dynamic import discovery/registration owner. | Reconcile full current AST-derived source and registered set; unresolved receiver/module remains explicitly unmeasured. No sampled registration patch. |
| F05 | Cycle graph owner. | Real reachable SCC identities versus scanner representation; no removal of an edge from inventory to erase a cycle. |
| F06 | Shim policy/expiry owner. | Exact expired shim and actual legacy consumer; remove migrated legacy or hand back a dated architect decision, never renew by convenience. |
| F07/F08 | Importable-root classifier. | Tracked Python under architecture/docs is non-product source; ignored raw scratch must not become committed-tree evidence. Real absent policy must remain visible. |
| F09/S05 | Existing vendor directory owner. | Admit the actual vendor role only if its documented wheel custody policy supports it; never erase the dependency. |
| F10/F11 | Non-product-root availability classifier. | Empty clean checkout separately lacking production_data and runs must name absent optional mounts, not assert they were measured. |
| F12 | Common package/root policy and `common/llm_json.py`. | Inspect real canonical ownership and consumers; use an existing home or supported facade, not a catch-all exception. |
| F13 | Single-file-shell policy. | Reconcile all four historical identities to current source; intentional shell requires its real role/test, not a baseline number. |
| F14/F15/F16/F17 | Module-size producer and builder/lifecycle/advisor/OpenAPI owners. | Current subject-to-logical-metric findings, preserving their distinct limits. No raw-line compression, limit increase or unrelated decomposition. Required decomposition/limit adjudications are explicit architecture handback with actual findings. |
| F18 | Deep-import owner. | Exact current edge; new module creep is complete-pending-an-architect-decision. Never run sync. |
| F19/F20/F21/F22 | Changed-source docs/security/runbook contracts. | Actual range and source-impact coverage; a local later range cannot retroactively establish historical documentation. Repair current missing required docs only at their owner. |
| F23 | Auto-discovered tools reference. | Regenerate from CLI registry after new invocation command, `polisyos-tools docs --check --output docs/reference/tools.md`; corrupt copied output must reject. |
| F24/F25/F26 | Hosted ABI/dependency/aggregate workflow states. | Retain skipped/event-conditional/derived semantics. No local pass can repair the absent hosted verdict. |
| S01/S03 | Dashboard Python-child station. | Exact automated-capture/workflow test files and their corruption/source-flip negatives using current local interpreter. Existing base repair is reverified, not assumed from triage. |
| S02 | Evidence producer/consumer executable provenance. | Reconciliation test file rejects a different executable even if schema/content look valid. Do not count S02 as a third missing-package case. |
| S04/R04 | OpenAPI snapshot and generated TS producer. | Current exact hardening node and canonical drift checker; compare same provisioned source, correct owner before regeneration. |
| S06/S07/S09 | Dashboard fixture roles. | Actual two directories versus declared fixture role; the count is a derived aggregate, not a third missing fixture. |
| S08 | Directory documentation denominator. | Complete tracked subtree inventory and actual missing README; preserve floors and distinguish untracked raw content. |
| S10/S11/S12/S13 | Hosted cancelled/skipped jobs. | Explicit unmeasured omission in the local completion report; no full replacement suites are authorized. |
| S14/S15/S16 | Historical smoke/performance/aggregate. | No new repair inferred from successes or dependency failure. |
| R01 | Core artifact-store factory and acquisition executor. | Exact architecture node plus real injected-store acquisition failure/success witnesses; constructor relocation must preserve artifact custody. |
| R02 | Registry provider and acquisition executor. | Exact architecture node plus injected absent/valid source-profile behavior; no inline singleton under a different spelling. |
| R03 | Epoch batch example owner. | Exact strict owner-derived example node; explain stale/review_required through fixed clock/expiry, not expectation weakening. |
| R05/R06 | Runtime test metrics collaborator. | Both named original nodes plus actual counter use/injection identity; align collaborator protocol rather than production fallback. |
| R07/R08 | ADR index generator/publishing policy. | Both links must resolve in published page universe, or become accurate source-only references; actual link checker rejects excluded-target fixture. |
| R09/R10/R11/R12 | Brand source-of-truth publication. | Four distinct links and target publication decision; no broad exclusion. |
| R13 | Research-pipeline documentation publication. | Correct published reference or explicit repository-source link; no inference from local file existence. |
| R14 | Existing mutation runner/CLI. | Preserve current fail-closed unsupported-platform UNRUN and Linux evidence distinction; do not claim native mutant execution from skipped tests. |
| R15 | Phase 1 source-copy scanner. | AST variations preserve findings, unknown dynamic deep argument is named unresolved, absent source is UNRUN; defensive clone behavior stays intact. Liveness/hotness remains explicitly unmeasured even with clean syntax scan. |
| R16/R17/R18/R19/R20 | Hosted typing/phase0/link/performance/review state. | Keep cancelled/success/skipped classes; no broader local testing inferred. |
| B01/B02 | Connector/scanner redaction composition. | Two original exact nodes plus immutable mapping and arbitrary credential-key secret witnesses; original source remains immutable, output retains redaction evidence. |
| B03/B04 | Segments/snapshots exception hygiene. | Classify each actual broad-handler site and preserve storage cleanup/rethrow semantics; no baseline-number refresh. |
| B05/B06 | Historical race/leak/performance successes. | No repair or current verdict inferred. |
| C01 | Canonical setup action/canary orchestration. | Reverify named current orchestration nodes; absence of requested prerequisites is UNRUN before workload. No live-provider invocation. |
| C02 | Credential/event quarantine. | Intentional hosted omission stays named, not a product pass. |

## Shared changes and effects on the other lanes

All edits to pyproject, lockfiles, lefthook, workflows and architecture files go
through root. None is pre-authorized as a blanket baseline refresh. Targeted
architecture role/documentation repairs may alter gate inputs for every lane;
the final frozen receipts must all use that same state. No import exception
expiry, size limit, coverage floor, delta tolerance or deep-import baseline will
be increased by this plan. Dependency provisioning is frozen at the slice lock;
an online cache refill is station repair and does not edit the lock.

Invocation auto-discovery adds a tools-reference row, so the docs owner must
regenerate after its source is final. Coverage script/config changes can alter
executable provenance dependencies; existing producer/consumer negatives decide
whether regenerated evidence is admissible. The unchanged coverage floor is
binding. Runtime/Fabric fixes can alter owner-derived hashes in OpenAPI/schema
surfaces; use the real producer, retain complete before/after class sets, declare
any governed epoch transition relative to `cc74d6581`, and never declare an epoch
merely because a generated file changed. No hosted workflows are dispatched.

## Execution and receipt protocol

First finish independent invocation and coverage source work, review it, and
freeze. Then repair CI items, with red tests immediately preceding source edits.
Existing exact failing tests are admissible red witnesses; no constructor-only
replacement. Root may delegate nonoverlapping Runtime/Fabric and scanner/docs
repairs once the first workstreams finish, keeping at most three concurrent
workstreams and retaining sole ownership of shared files.

Final runner names every test file and node explicitly. Eight initial original
nodes are the six Runtime contract nodes and two Fabric nodes listed in C-CI;
no directory-wide pytest, backend verify or CI parity. Python AST enumerates
definitions including async, TS AST counts calls. Dashboard full coverage is
the sole full-suite exception, with complete output in ignored raw/.

Every gate is the only command in its shell invocation. Capture its actual exit
status, full output, elapsed time and provisioning identity. No `gate; echo $?`.
The completion journal quotes every touched instrument's actual omission
sentence and negative. CLI FAILED means completed rejected measurement;
UNRUN means no complete verdict and findings beside it are partial. Existing
instrument-specific result carriers are preferred over a new CI orchestrator.
Hosted cancelled/skipped scopes are explicitly omitted in that local receipt.

Source freeze -> all reviews -> expensive coverage wave once. Any new blocking
review after freeze is batched before rerun. Changes commit at clean boundaries;
branch attachment and branch readback are checked each time. No stash storage,
history rewriting, push, other lane branch, DEBT-REGISTER or LEDGER edits.

## Pattern pass and stopping property

P05/P04/P09: status and failure semantics must not become green by omission.
P29/P32/P33: behavior and negative evidence, including present-but-fake inputs,
not existence of marker words. P35/P36: original complete logs and finding IDs,
never debt narrative as evidence. P37/P38: provisioning and proxy predicates
must disclose their limits. P31/P40: bucket a finding before repair; a second
same-class escape widens the owner mechanism or establishes a bounded residual
with its smallest missing capability and falsifier, not endless local patches.
P41: inherited is not established without exact-base replay and disjointness.

Existing capability chains are production-wired but have verification/protocol/
surface gaps identified above; no new policy authority is built. Developer CLI
and audit receipts are the external surface; policy dashboard/API changes beyond
the named existing paths are `surface_out_of_scope`. Missing hosted execution
remains `verification_missing`. Required architecture approvals are handback
items labelled complete-pending-an-architect-decision, not blocked and not fixed.

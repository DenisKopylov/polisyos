# GY-N13b Evidence-Driven Resumption and Contract Closure Plan

> **Execution rule:** this plan continues the accepted implementation at commit `17639f540`.
> Previously green workstreams are inputs, not rewrite targets. Every new stream is RED-first,
> focused-verified, and committed before the next live authorization. Shared `.tmp` validators run
> strictly serially. No full pytest, rebase, merge, or production-data write is permitted.

**Goal:** Carry the paid World Bank evidence through the single-transform D6 route, freeze the true
live/local/derived/re-entry result, and close the missing generated-artifact lifecycle without
weakening any admission, provenance, baseline, route, or journal fence.

**Governing contract:** GY plan Rev 18, `GY-N13b` and sections 3.5.6, 3.5.7, 3.5.9,
3.5.10, 3.5.11, and 3.5.12 D1-D6. The historical implementation plan remains
`docs/superpowers/plans/2026-07-17-gy-n13b-acquisition-executor.md`; its stop-law receipt remains
valid evidence. This document is the architect-authorized continuation after the required owner
evidence became obtainable.

**Status (2026-07-19):** `closed_typed_deeper_terminal`; implementation and frozen contract are at
`6280e487f`, targeted closeout verification is complete, architect review is pending, and the branch
must not be merged. The result is an implemented executor/audit capability with zero admitted
epochs, not a world-growth claim.

## Resumption preflight and R1 receipt

- Branch/worktree: `codex/gy-n13b-acquisition-executor` in `.worktrees/gy-n13b`, clean at
  `17639f5403de916113390652cd998202930a5461` before resumption.
- Read-only merge assessment: merge base `a906ed7c1cef91813cca7b1488544454a48de925`;
  `git merge-tree` found zero conflict markers; main and branch have zero overlapping changed paths.
- Protected Atlas and production-data paths remain untouched.
- R1 made zero network calls. The 85-byte CAS object resolves through the journal owner to raw event
  `sha256:3748d96fdefb6a20b075501985bef3da7ba3c3e22cf7ce0ef818f267af8052ab` and body
  `sha256:244e629ceec4b53324246967388d17b706efe2207744b8148d60ea52dbccd264`.
- The decoded body is `[metadata(total=0), null]`, therefore exactly
  `no_data_for_scope`. It is not evidence that the carrier is retired. Carrier liveness remains
  undecided and conditionally authorizes R2.
- Journaled maximum elapsed evidence is `6.945391583998571` seconds for attempt 001 and
  `15.766325374999724` seconds for attempt 002. Any later timeout cap must be a deterministic
  function of these measurements and the source-profile cap.

## Hard live-call budget

The resumption budget is six calls total. The ledger is append-only and each row requires its own
E7 receipt, journaled request/transport/heartbeats/raw evidence, and terminal before another call.

1. R2 exact indicator-metadata call for `GC.BAL.CASH.CD`, only because R1 left liveness undecided.
2. R3 primary series call, only after the recomputing selector proves a D6 route.
3. R3 GDP-current-US$ auxiliary call, only after its exact catalog basis edge and E7 receipt pass.
4. R4 deflator call, only after the acceptance selector proves a compatible catalog carrier.
5. Reserved for one evidence-derived alternative carrier when a prior terminal authorizes an
   honest lever; never a blind retry.
6. Reserved under the same rule.

Unused calls remain unused. A terminal at any node is frozen; it does not automatically authorize
the next reserved call.

## Pattern and capability pass

- Relevant patterns: P01/P02/P12 (producer/bridge reality), P04/P05/P09/P15
  (status/authority/speculation), P07/P08 (replay and epoch time), P10/P14 (semantic adequacy and
  evidence strength), P27/P28 (single owner/strangle), and P29-P34 (behavioral proof,
  content-bound provenance, class repair, trust-by-form resistance, adversarial variation, and
  honest isolation).
- Existing accepted owners: canonical catalog graph, acquisition authority provision, append-only
  journal, one-shot executor, CAS/snapshot quarantine, admission passport, immutable overlay/read
  union, generic last-mile field edge, and content-addressed derivation certificate.
- Remaining capability labels: `artifact_missing`, `lifecycle_registration_missing`,
  `consumer_missing` for certified derived overlay matching, and `semantic_test_missing` for the
  real re-entry/acceptance cases.
- Smallest closure pattern: extend the existing World Bank family and journal owners for a distinct
  metadata call class; select D6 inputs from catalog+liveness evidence; extend the existing
  derivation owner with one certified fiscal transform; admit observed inputs and certified derived
  output through one overlay; then recompute the demanding N7 path and one frozen contract.
- Acceptance signal: every attempted carrier has paid evidence and a typed terminal; admitted rows
  are passport-backed epochs; the derived row binds one content-addressed recipe and never appears
  observed; N7 re-entry reads the existing union path; the artifact rederives every decisive class.

## Workstream R2 — metadata-class liveness and recurring census evidence

- [ ] RED tests for a generic exact-indicator metadata request: distinct call class, one variable,
  one transport, owner profile limits, request-side-only semantics, journal-first raw bytes, and a
  target-specific REPLAY interception receipt. A data-fetch receipt cannot authorize metadata and
  a metadata receipt cannot authorize data fetch.
- [ ] Extend the existing `WorldBankConnector` family with an exact indicator-metadata operation;
  do not add a connector class or hardcode an indicator list.
- [ ] Extend the Fabric evidence-journal owner with a metadata authorization/characterization
  projection while preserving all existing journal bytes and terminal resolution.
- [ ] Extend the N13a census owner with a recurring carrier-follow-up projection that recomputes
  `carrier_retired_or_invalid`, `no_data_for_scope`, or `response_shape_unclassified` from raw
  bytes. It consumes both paid data terminals plus the metadata probe and derives the carrier's D3
  tier-decay finding; no hand-edited scorecard row.
- [ ] Freeze the R1 forensic projection and zero-network metadata E7 receipt, byte-stable twice;
  run focused tests, N13a `--check`, Ruff, and guardrails.
- [ ] Commit: `feat: characterize stale acquisition carriers`.
- [ ] Only after the commit, spend call 1 through the one-shot metadata command. Persist the raw
  bytes and terminal immediately; commit the paid evidence separately as
  `data: preserve acquisition metadata evidence`.

## Workstream R3a — evidence-derived D6 route and exact carrier owners

- [ ] RED selector tests fold R1/R2 dispositions into the complete catalog candidate denominator.
  The old USD carrier remains preferred only if it has data for scope; otherwise the selector may
  choose exactly one certified transform, never a chain.
- [ ] Derive the primary `percent_of_gdp` and auxiliary `current_usd` basis edges from catalog
  title/description/connector ownership. Verify open license, no auth, parser support,
  transport-ready tier, schema profile, and exact country/period scope. Indicator IDs are expected
  hypotheses, not constants.
- [ ] Emit a typed `D6DerivationRequirement` carrying the demanded L6 USD basis, exact input
  carriers, formula semantics `share_percent * GDP_current_USD / 100`, and refusal codes when any
  edge is absent or ambiguous.
- [ ] Derive separate target registries, provisions, and exact E7 receipts for primary and
  auxiliary calls. The timeout cap is recomputed from R1 elapsed evidence and bounded by the source
  profile; it is never an arbitrary bump.
- [ ] Focused selector/authority tests, byte-stability twice, Ruff, N13a check, and guardrails.
- [ ] Commit: `feat: derive single-transform fiscal acquisition route`.

## Workstream R3b — bounded observed acquisitions and epoch admission

- [ ] For each selector-authorized series, run one exact E7 REPLAY receipt and one journal-first
  live attempt, one variable at a time. Preserve every terminal and stop that node without retry.
- [ ] For successful carriers, reopen CAS/DataSnapshot bytes, measure under quarantine, derive the
  complete passport, and admit only observed rows at fresh overlay epochs through the existing
  baseline-fenced owner.
- [ ] Prove baseline SHA-256 before/after, raw-to-normalized equality, country/year scope, schema,
  license, PII, checksum/watermark, L5 cap, field edge, and no quarantine visibility.
- [ ] Commit each paid result promptly: `data: preserve fiscal primary acquisition evidence`, then
  `data: preserve fiscal auxiliary acquisition evidence`. A terminal result still receives its
  scoped evidence commit.

## Workstream R3c — certified fiscal transform and basis-aware overlay match

- [ ] RED tests for exact-year share×GDP derivation, `/100` semantics, missing-year refusal,
  input-hash/parameter tamper, authority inflation, chain insertion, derived-as-observed, and an
  uncertified basis match.
- [ ] Extend `derived_observations.py`, not a sibling engine, with a content-addressed fiscal
  single-transform recipe/certificate. Reuse the existing CAS verification, manifest graph,
  authority projection, cache, and consumption receipt machinery.
- [ ] Add the derived-overlay admission path to the existing `CatalogAcquisitionOverlay`. It must
  resolve and verify the recipe, certificate, input passports/epochs, weakest-input authority,
  source watermarks, and `derived` provenance before persisting. Model outputs remain forbidden.
- [ ] Basis-aware matching resolves the L6 USD requirement only through that certificate; without
  it, return typed `basis_mismatch` and a derivation requirement.
- [ ] If either live input is terminal, freeze the exact deeper state instead of constructing a
  recipe or overlay row.
- [ ] Focused derivation/overlay/availability tests, Ruff, and guardrails.
- [ ] Commit: `feat: certify fiscal balance derivations`.

## Workstream R4 — real-terms acceptance case

- [ ] Recompute the full eligible input denominator: first prefer an admitted nominal monetary
  acquisition plus a transport-ready catalog deflator whose declared basis supports the same
  country/year; if unavailable, inspect all owner-admissible local monetary/deflator pairs. Do not
  reuse the 0/15 backlog result as a conclusion about this broader denominator.
- [ ] If a live pair is authorized, acquire the deflator under its own E7 receipt and one call.
  Deflator choice and base year are derived from catalog/metadata and declared in the certificate.
- [ ] Materialize exactly one CPI/GDP-deflator real-terms recipe, then have two distinct method lanes
  consume the same certificate. The second materialization must be a verified CAS cache hit
  (`hit == rebuild`).
- [ ] Bind the measured `basis_mismatch` refusal and add a behavioral negative with no certified
  transform. Bind the class-(iv) model-output passport refusal.
- [ ] If no owner-admissible pair exists, freeze `acceptance_inputs_inadmissible` with the complete
  denominator and reasons; never synthesize inputs.
- [ ] Focused acceptance tests, Ruff, and guardrails.
- [ ] Commit: `feat: prove cached real-terms derivation acceptance` (or
  `data: freeze inadmissible derivation inputs` for an honest terminal).

## Workstream R5 — demanding-stage re-entry

- [ ] Capture pre-reentry L1 availability for `government.balance` through
  `data_state_substrate` and the existing baseline+overlay union.
- [ ] Re-run the real N7 acquisition/re-entry stage with the same requirement identity and overlay
  path. Record planner route, basis matcher, availability counts/epochs, and the next typed state.
- [ ] Done outcome is either a measurable availability/gap closure or an evidence-derived deeper
  state. Adjacent data may not alter any of the three N13a capstone route classes.
- [ ] Negative test removes the real union or certified transform while retaining marker fields;
  re-entry must turn RED.
- [ ] Focused generation-cycle/acquisition-planner/data-state tests and Ruff.
- [ ] Commit: `feat: reenter N7 against acquired world epochs`.

## Workstream R6 — frozen N13b contract and lifecycle closure

- [ ] RED-first strict contract/writer/checker over narrow projections: committed infrastructure
  identities; local 0/15 rights refusal; R1/R2 carrier evidence; every live attempt; D3 tier decay;
  passports/quarantine; overlay epochs; derivation certificates/consumers; re-entry; capstone route
  projection; and the true world-growth result.
- [ ] Deferred lifecycle registration derives acquired snapshot/canonical-provision registrations
  from their real manifests and receipts, closing `owner_registration_derivation_missing`.
  Journal refs/CAS identities close `journal_raw_evidence_persistence_missing`.
- [ ] Implement `--check`, `--write`, `--rederive`, byte-stability twice, decisive nested corrupt
  field, and restoring behavioral flips: baseline mutation, fabricated fetch, forged passport or
  watermark, laundered canonical value, journal tamper, recipe input/parameter tamper,
  derived-as-observed, trust-root drift, terminal relabel, epoch removal, capstone-route laundering,
  and lifecycle-registration forgery.
- [ ] Register the contract, checker, overlay, journal/CAS manifest projection, and derived artifacts
  in `architecture/generated_artifacts.toml` through the canonical writer; no manual receipt pinning.
- [ ] Run serial census -> N4 -> N8 -> composition -> capstone -> disposition-ledger checks. Any
  honest census ripple is written through its owner and audited leaf-by-leaf before proceeding.
- [ ] Focused checker tests, source flips, Ruff, 39-validator import census, guardrails, and
  `git diff --check`.
- [ ] Commit: `feat: freeze acquisition executor contract`.

## Workstream R7 — closeout ledger and architect handoff

- [ ] Reopen the failure register and record the after-state capability/pattern pass.
- [ ] Re-run only the fresh focused suites and all consumed frozen-artifact checks serially.
- [ ] Audit the six-call budget, baseline hash, protected-path/production-data diff, capstone route
  projection, clean tree, scoped commits, and read-only merge-tree drift.
- [ ] Update the execution journal with exact call economics, epochs, availability delta,
  certificates/cache proof or typed refusal, re-entry verdict, artifact/checker hashes, flips, and
  inherited HTTP-redaction failure isolation.
- [ ] Commit: `docs: close GY-N13b acquisition executor ledger`.
- [ ] Stop for architect review. Do not merge.

# Current-source G questions index

Date: 2026-10-27. This packet is a decision input, not source acceptance. For this handoff: architecture_selection=pending_G, code_acceptance=false, closure_ids=[]. No source code or tests were changed or run.

## Decision set

### CAN-01 — preserve or refuse raw mappings that collide with recognized .2 tags

Open API-domain choice: should ordinary input mappings with exact _type values reserved by the selected .2 owner remain representable as mappings in persistence and cache inputs (Option A: a versioned lossless mapping escape), or be rejected before persistence and cache lookup under .2 (Option B)?

Reuse the existing draft and its inputs/evidence as written: [CAN decision draft](../canonical-raw-mapping-20261026/README.md) and [source/readout pins](../canonical-raw-mapping-20261026/inputs.json). The current-source consumer oracle is here (`../../raw/root-ir-transport-composition-20261024-r1/g-native-priority-20261025-r1/can-composed-consumer-oracle-20261027-r1/can-current-source-oracle.md`; unavailable in this checkout). This packet does not copy or replace them. The decision remains pending G. Do not reopen AD-E02-05's shared-mechanics/Core-vs-IR separation or IR-Q1/Q2's typed owner admission, already selected in local G docs at 978921662b2d89006759cdd2ae96dbccc9bdcf11.

### TC-01 — define the request time scope named by ADR-0148

Open scope choice: does ADR-0148's generic time_context_ref mean the existing runtime request TemporalScope bitemporal cursor (valid_at and tx_at), with policy/data/legal roles remaining separately typed, or does it require a new exhaustive time-role bundle?

Recommendation: reuse TemporalScope for the explicit request cursor; keep policy_time, data requirement time_role, source time, and legal valid time separate. Independently, apply one typed owner/wire and profile-bound SameInputClosure identity rule to every selected CAS-view pointer, not only time_context_ref. Legal snapshot remains governed by the independent Lex barrier.

Source/readiness input: TimeContext compatibility and falsifier record (`../../raw/root-ir-transport-composition-20261024-r1/g-native-priority-20261025-r1/time-context-existing-contract-prototype-20261027-r1/implementation-readiness.md`; unavailable in this checkout). This is a narrow owner decision, not permission to treat prototype compatibility as an ordinary POST or authority proof.

## G and source state

The selected canonical/IR decision docs are locally available at G HEAD 978921662b2d89006759cdd2ae96dbccc9bdcf11. The current G remote pointer origin/codex/e02-integration is 2a07cd8a16bad0191b302f71c699b3bf9082ebac, an ancestor; local is five commits ahead and the selected docs are not yet on that remote pointer. No merge is part of this handoff. The original oracle reviewed owned postimages at fb39cc71; those source bytes are now committed in implementation checkpoint 647ec5df86707adfdb3b06d7b9dbd77a3c65380b. At publication preparation, the branch is 7a4c713186188f5795da3a8745e42843443dcd88 / tree f49503f969b9a3d68bf82d23e0c8435e9d20c847. All 13 TimeContext source pins match committed branch bytes. The separate Ruff helper delta changes none of this readset. CAN has 21 of 22 exact source pins unchanged; its runner serializer differs only in the already-reviewed ArtifactRef facade import. See inputs-limits.json for the exact readset and bounded transfer.

## Status boundary

Neither question has G closure or current-source code acceptance. TimeContext prototypes are temporary CAS/API-compatibility checks only: they did not exercise ordinary POST, create producer authority, or establish a published authority escape. The distinct-profile/bare-ID case is a bounded falsifier for the SameInputClosure identity mechanism. The accepted legal barrier remains independent; no legal fact is requested or inferred.

The G remote/local graph above records the observed session checkpoint; it is not a guarantee about subsequent G publication. Read [the TimeContext choice](time-context-decision.md) for its explicit acceptance path. Continue the already-selected IR/PAG/B09/native work independently.

Independent document review: GO after the source-frame and link rebind recorded in inputs-limits.json. The linked historical readiness phrase “six envelopes” is not a completeness denominator for this packet; no six-item test coverage is asserted.

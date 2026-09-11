---
title: Foundry runtime authority capability construction
owner: Foundry catalog/discovery boundary
status: proposed
---

# Foundry runtime authority capability construction

## FR-AUTH-01 — construct the authority boundary, retain candidate non-decisiveness

**Status:** proposed; engineering execution not started. This actual task is created
by the user-authorized producers-verification lane at merge base
`a534024ee28dfd9ac4fd21be1ff769b253722d8e`. Architect acceptance, accountable engineering
allocation, and the `foundry-runtime-authority-capabilities-absent` row link are
outstanding. This document is a scheduling proposal, not an architect act, institutional
appointment, completed producer, or authority receipt. The lane does not edit the debt
register or LEDGER. An institutional prerequisite limits authority claims; it does not
prevent engineering construction and negative testing.

**Decision basis:**
`docs/superpowers/specs/2026-09-10-producers-foundry-authority.md` findings describe the
measured nearest existing producers, refusal authorities and missing chain. Use those
source findings rather than the debt row's missing labels. Reconcile actual current
source again at task start, because a later lane may already have delivered a part.

**Scope owner:** Foundry catalog/discovery boundary. Runtime is the consumer; platform
and production-data owners supply typed trust evidence rather than silently delegating
institutional authority to a writer. Coordinate those contracts explicitly before their
admission predicates are implemented.

**Prerequisite design decisions:** define the writer threat model and the independently
controlled runtime source denominator; identify accountable cutoff issuer and verifier
trust boundaries; specify exact resolution-receipt custody and replay; choose actual
platform/toolchain and production-data trust evidence. These are unresolved research
questions, not new code contracts fixed by this proposal. Inspect existing ports and
reuse their semantics before extending types.

**Ordered work:**

1. Reconcile the full tracked source denominator and the real dependency-authority
   factory/consumer chain; test candidate non-decisiveness before constructing anything.
2. Build `owner_enforced_runtime_subtree_cutoff` against an actual writer-independent
   source boundary. The source writer must not be able to alter the admitted set while
   retaining a green cutoff receipt. A self-authored path list, hash, or independent
   second walk by the same writer does not supply this property.
3. Build `owner_resolved_resolution_receipt_store`: admit exact persisted resolution
   bytes through owner verification; bind their content, policy version, provenance,
   purpose and time semantics; resolve and replay the same receipt without re-signing
   or accepting a caller-provided lookup result as authority.
4. Build `platform_toolchain_admission` and `production_data_trust_policy` on independently
   controlled evidence. Explicitly distinguish recomputed content, independently
   reconciled trust and institutionally supplied claims. The last may not alone carry
   an authority gate; missing/unverifiable/incorrectly scoped evidence must refuse.
5. Wire the existing Foundry production factory and Runtime consumer after the chain
   is complete. Before each new producer is written, record its concrete non-test
   caller and discoverable entry point. Register operator commands in polisyos-tools
   when an operator workflow is required; otherwise name and test the actual existing
   caller. A loose main guard or test import is not a scheduled production invocation.
6. Persist exact receipts and read them back through their true consumer. Preserve
   candidate observations and their non-decisive diagnostic route throughout migration.
   Any governed epoch transition is declared from this task's eventual merge base.
7. Run explicit-node semantic tests and removal probes, then submit the accountable
   owner review and proposed registry transition. Do not mark a capability implemented
   from its schema or a reviewer identity alone.

**Acceptance:** all four capabilities have a typed contract, real production producer,
persisted artifact/receipt, exact reader, orchestration bridge, consumer, verification,
audit/API surface (or explicit out_of_scope) and a negative/e2e test. Every new producer
has an identified production caller and its registration decision. Falsify the declared
cutoff basis while retaining the declaration; writer action cannot preserve authority.
Corrupt a real receipt, use an unrelated trusted key, substitute a scope/epoch, omit trust
or data evidence, and require the exact refusal. Removing the producer or admission
binding must make an unchanged negative red. A positive candidate observation must never
be accepted as platform/data/cutoff authority merely because it was recomputed twice.

**Pattern pass:** P01/P02/P27 require complete chains on existing owners; P05/P15/P37
forbid candidate or institutional self-attestation carrying an authority gate; P29/P32
require content/verifier substance; P35 requires a complete denominator with a second
independent cross-check; P38 distinguishes writer-independent control from an observed
path list; P40 bounds repeated escapes of that same trust class. Current capability
state remains `absent/unallocated` where measured. A proposed plan is not `contract_only`
implementation. The acceptance signal is a real writer-independent cutoff and downstream
receipt consumption, not this task's presence in a plan.

**Requested architect action:** accept or amend FR-AUTH-01, allocate accountable owners
and order it in the execution plan, then link the debt row to this actual task if choosing
the scheduling closure route. Until that separate act, the route is proposed and the row
closure is not claimed. No consumer may treat a recomputed runtime observation as authority.

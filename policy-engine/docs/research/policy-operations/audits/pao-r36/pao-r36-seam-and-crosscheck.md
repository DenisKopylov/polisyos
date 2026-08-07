---
title: PAO-R36 - Seam and Crosscheck
status: delivered_independent_audit
audit_id: PAO-R36
verified_commit: 1bccc012b636d6a13930735a4f748d1f8cf7b9cf
pinned_repository_commit: 1a7a2d05ebba22fae80e9934329e4b880806588e
audit_branch: research/pao-r36-independent-audit
research_only: true
authoritative_for:
  - pao_r36_pass_vii_kernel_conformance
  - pao_r36_pass_viii_seam_crosscheck
  - pao_r36_dependency_boundary_dispositions
may_not_use_for:
  - production implementation authorization
  - final wire, schema, package, database, serialization, media-type, or API contract
  - canonical owner, vendor, custodian, or service appointment
  - authority grant
  - capability claim
  - legal-sufficiency or jurisdictional conclusion
  - permission to publish or open a gate
  - automatic amendment of any plan, backlog, or system-design decision
---

# PAO-R36 seam and crosscheck

## 1. Scope

This document audits PAO-R36 against the already-ratified semantic kernels and checks three declared
interfaces: OPS-R14, INT-R6, and INT-R7. OPS-R14 is read only to test closure of the seam; this audit
does not adjudicate OPS-R14's quality or adopt its standing.

## 2. Pass VII — ratified-kernel conformance

### 2.1 `PV-K02` and `S0-K08`

`PV-K02` establishes that historical authenticity and current authority are distinct, non-erasing
propositions. `S0-K08` establishes that correction appends and history is not rewritten. PAO-R36 does
not re-argue either rule. It treats them as fixed at
`pao-r36-public-correction-and-durable-notice.md:84-109` and
`pao-r36/ordered-fanout-and-completeness-contract.md:41-58`.

More importantly, it makes violations observable:

- F02 queries every controlled surface for predecessor-current after `t_authority`;
- F03 compares the original identity/content before and after correction and requires a distinct
  successor edge;
- F07 requires archives to preserve identities and bidirectional correction relations;
- F09 separates issuance-time authenticity, compromise certainty, key status, and current authority;
  and
- F11 forbids recovery from restoring predecessor-current.

### `PAO-R36-VII-001` — commendation — the non-erasure law becomes falsifiable

The research does what the commission required: it does not merely quote the prohibition; it defines
identity, relation, currentness, archive, key-status, and recovery observations that can contradict
it.

### 2.2 `PV-K04`

`PV-K04` permits loss of detail only when protected meaning is preserved and authority, currency,
certainty, and permission are not amplified. PAO-R36 applies it to a correction notice at
`pao-r36-public-correction-and-durable-notice.md:382-426` and
`pao-r36/ordered-fanout-and-completeness-contract.md:468-510`.

The notice must retain predecessor/successor identity, changed proposition and reasons, claim
basis/scope/conditions/limitations, current/effective state, denied uses, dissent/contest/recourse,
adverse-risk direction, old-version significance, language status, archive limitations, and relevant
INT-R7 key-status distinctions. F06 drops a retained limitation or denied use and requires rejection
or fail-closed repair.

### `PAO-R36-VII-002` — commendation — notice compression is bounded by protected queries

This is a faithful operational use of `PV-K04`. The detailed retained-item list and F06 make
amplification/omission detectable rather than editorially discretionary.

### 2.3 `PV-K01`

PAO-R36 keeps current authority as a separately reportable `as_of` proposition throughout the
observer predicate, hard cases, machine-feed requirements, and F09/F13. It does not infer currentness
from signature validity or historical use.

The one caveat is the formal-order finding `PAO-R36-III-005`: `as_of` selection is specified, but the
append order and displayed effective-time order are not yet themselves falsified.

### 2.4 `INT-K05`, P27/P28, and GY-N12

`INT-K05` directly governs confidence-scope composition, not correction. PAO-R36 uses the same-owner
principle only as an ownership analogy. It routes:

- canonical evolution to `policy-engine/src/polisyos/core/contracts/rule_evolution.py`;
- current head/current authority/epochs/reissue to GY-N12;
- notice projection to `projection_semantics.py`; and
- public packaging to `public_export.py`

at `pao-r36/repository-integration-and-dependencies.md:31-103`.

It explicitly forbids a PAO-specific chronology, `correction_evolution.py`, second currentness owner,
or fifth audience.

### `PAO-R36-VII-003` — commendation — no parallel currentness/evolution owner

The owner-first handoff conforms to P27/P28 and the GY-N12 boundary. No owner is appointed by
research, and GY-N12 remains labelled undelivered/contract-only.

## 3. Pass VIII-A — OPS-R14 seam

### 3.1 PAO-R36 side

PAO-R36 declares five interface requirements at
`pao-r36/repository-integration-and-dependencies.md:132-183`:

1. restore/replay must never make the predecessor current again;
2. correction-event order, version relations, notices, receipts, and cutoffs survive;
3. legal hold/retention must not sever the chain;
4. signing-right expiry/renewal exposes an authenticated status outcome without PAO defining expiry;
   and
5. drills expose the bounded semantic result while OPS owns objectives/mechanics.

F11 is the sharpest verifier-facing attack.

### 3.2 OPS-R14 side at `3a694212a`

OPS-R14 preserves the ownership split in frontmatter: its artifacts may not design PAO-R36 correction,
notice, subscriber fan-out, or feed semantics. Its relevant responses are:

| PAO interface | OPS-R14 response | Closure |
| --- | --- | --- |
| Never un-correct | RP-10 says recovery of an old version must not render it current merely because its signature verifies (`ops-r14/long-term-replay-and-preservation.md:184-201`). | Closed at research-interface level. |
| Preserve versions, relation, public head, completion evidence | RP-10 requires every version, relation, public head, and completion receipt to be preserved (`:184-201`). | Closed; PAO retains notice/fan-out meaning. |
| Omitted completion evidence must not manufacture current/effective publication | RP-10 verifier restores both versions while omitting PAO completion evidence; historical versions remain verifiable, current head/fan-out completion is not established, and publication mutation stays blocked (`:194-201`). | Closed and directly testable. |
| Legal hold cannot sever correction | OPS-R14 LH-01..LH-04 block destructive operations and explicitly say a hold cannot suspend correction/append-only supersession or change historical/current status (`ops-r14/watched-dependency-and-legal-hold-semantics.md:363-420`). | Closed without PAO defining hold mechanics. |
| Expiring signing right | OPS-R14 WD-01..WD-07 makes expiring rights append-only watched dependencies, separates expiry/revocation/supersession, and requires admissible renewal evidence; PAO consumes only the status result (`watched-dependency-and-legal-hold-semantics.md:1-120`). | Closed without PAO selecting expiry/grace/renewal semantics. |
| Drill result | RP-10 supplies the specific restore verifier; OPS-R14 separately owns disaster fixtures and drill evidence. | Interface declared; quality remains for the independent OPS-R14 audit. |

### `PAO-R36-VIII-001` — commendation — the OPS-R14 seam closes in both directions

PAO-R36 specifies the semantic state that must survive. OPS-R14 specifies preservation/recovery,
watched-dependency, hold, and drill mechanics while explicitly refusing to design correction
protocol. Neither task crosses the declared seam.

The formal defect in PAO's own ordering does not reopen the seam: OPS-R14 can preserve only the
correction order PAO ultimately settles.

## 4. Pass VIII-B — INT-R6 seam

INT-R6 is unresearched. PAO-R36 requires only an interface:

- one language-invariant correction semantic identity;
- parity over claim type, corrected scope, reasons, conditions, limitations, denied uses,
  currentness, adverse-risk direction, old-version significance, and recourse;
- no amplification of authority/permission/certainty/currency;
- a frozen authoritative-language denominator and cutoff; and
- fail-closed divergence/unavailability.

It expressly refuses to define translation workflow, reviewers, terminology, translation memory,
model use, release order, or equivalence algorithm
(`pao-r36/repository-integration-and-dependencies.md:112-131`). F01 names the protected queries and
expected red outcome but says the pass condition is “under the INT-R6 interface.”

### `PAO-R36-VIII-002` — commendation — F01 does not smuggle a parity mechanism

The fixture defines what divergence must do, not how equivalence is established. Atlas D4 fixes only
the exposure posture (`uk`, `en`, frozen legacy `ru`); INT-R6 remains the mechanism owner.

## 5. Pass VIII-C — INT-R7 seam

PAO-R36 consumes INT-R7 for issuance-time authorization, retirement/revocation/compromise intervals,
preservation signer versus issuer, and separate historical/current outcomes. It does not choose
algorithms, key providers, certificate authorities, logs, witnesses, or status services.

INT-R7 is append-only research. Its terminal controlling layer is §18 of
`policy-engine/docs/research/policy-operations/int-r7/public-verification-profile.md:620-760`, which
supersedes earlier collapsed outcomes and requires five separately reportable dimensions:
`IssuerIssuanceAuthentic`, `ProjectionFaithful`, `PublicHistoryEstablished`,
`DurablyVerifiableAt(t_v)`, and `CurrentAuthorityAsOf(t_q)`.

PAO-R36's substance conforms: its revoked-key fixture separates content match, issuance-time
authorization, compromise certainty, and current authority, and its public-current outcome depends on
GY-N12. The citation practice is weaker than the semantics: several PAO passages cite only
`int-r7/public-verification-profile.md:250-405`, which is historical profile text and not the terminal
controlling amendment.

### `PAO-R36-VIII-003` — minor — cite the controlling INT-R7 layer

Retain the useful issuance/revocation rows, but add a controlling citation to INT-R7 §18 whenever PAO
states the final public verification/current-authority decomposition. This is a P36 correction, not a
semantic redesign.

## 6. Seam conclusion

All three seams are correctly drawn. The OPS-R14 closure is particularly strong: RP-10 turns
“recovery must never un-correct” into a restore fixture with a bounded negative result. INT-R6 remains
a declared unresearched dependency, and INT-R7 remains the delivered key/proof profile. The only seam
revision required is citation to INT-R7's terminal controlling section.

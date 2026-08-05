---
title: INT-R7 — Citizen Verification UX Requirements
research_id: INT-R7
status: delivered
result_standing: GO_WITH_REVISIONS
repository: https://github.com/DenisKopylov/polisyos
repository_branch_inspected: main
pinned_repository_commit: 02c5b8d23c757c92b9231e6e1e802d5701588908
inspection_date: 2026-08-04
amended_after_audit: research/int-r7-independent-audit@54e8f41d790cb257a616c5bb5f96d996fbe3e9db
research_only: true
int_r8_seam: proof_only
may_not_use_for:
  - production implementation authorization
  - final wire, schema, package, database, serialization, or API contract
  - canonical owner appointment
  - authority grant
  - capability claim
  - benchmark passage
  - legal compliance or institutional competence conclusion
  - permission to publish a governed result
  - automatic amendment of any plan or system-design decision
---

# Citizen verification UX requirements

## 1. Boundary

This artifact specifies the behavior of **verification outcomes** for a citizen, journalist, another agency, court, archive, or machine. It does not decide what policy content is included in the public view. INT-R8 owns retained content, redaction, compression-loss semantics, and disclosure composition.

The UX translates the predicate vector from `PublicVerificationProfile` into bounded human outcomes without collapsing historical authenticity, current authority, freshness, common view, projection validity, or preservation into one green badge.

The current browser route does the opposite: it accepts a public-salt 32-bit FNV value recomputed over attacker-chosen JSON and renders a positive `Verified` state (`policy-engine/apps/runtime-dashboard/src/features/runs/domain/publicationPacket.ts:240-247, 357-369, 1050-1188`; `PublicDecisionViewerPage.tsx:1-53 @ 02c5b8d`). The requirements below are the behavioral strangle target.

## 2. Citizen task model

A non-expert must be able to perform one of four tasks without understanding cryptographic terminology.

### UX-T01 — open a public record

The user opens a URL or scans a QR code. The verifier:

1. treats every network response and embedded status flag as untrusted input;
2. obtains or invokes an independently authenticated verifier/trust context;
3. verifies the record and proof predicates;
4. displays a bounded outcome and `as_of` time;
5. offers evidence details, a machine report, and an offline copy.

### UX-T02 — verify a downloaded record offline

The user selects a downloaded proof closure or opens it in a verifier. The verifier:

1. explicitly enters offline mode;
2. performs no undisclosed network calls;
3. validates the package against independently authenticated trust/policy/checkpoint material;
4. states the status snapshot cutoff;
5. never upgrades `current as of t_q` to `current now`.

### UX-T03 — check whether an old record is still current

The user sees two independent questions:

- “Was this record authentically issued?”
- “Is it current as of the latest authenticated status available here?”

The answers may differ. A withdrawn or superseded record may pass the first and fail the second.

### UX-T04 — understand or challenge a failure

The user receives:

- one plain-language result;
- a stable reason code;
- the failed/unknown predicates;
- evidence cutoff and source roles;
- a copyable report;
- a public records/access/challenge channel designated by competent governance.

The challenge channel must not imply that PolicyOS itself adjudicates citizen cases or legal rights.

## 3. Information hierarchy

Every verification result has four visible layers.

### Layer 1 — bounded outcome

One of the outcomes in §5, never an unqualified `Verified`.

### Layer 2 — time and scope

Always visible:

- authenticated `as_of` time and timezone;
- whether verification was online or offline;
- claim class: procedural custody claim, honest refusal, bounded `delta`, or another ratified class;
- issuing authority role and jurisdiction as evidenced, not merely display text;
- whether result is historical, current, stale, withdrawn, superseded, or incomplete.

### Layer 3 — reasons and dependencies

Expandable summary:

- signature/content result;
- authority-at-issuance result;
- trusted-time/revocation result;
- transparency/common-view result;
- GY-N12 epoch/currentness result;
- INT-R8 projection result;
- preservation/algorithm result;
- freshness/offline closure result.

### Layer 4 — evidence and machine report

Provide:

- evidence identifiers and policy/profile versions;
- original issuer versus preservation/witness roles;
- checkpoint and witness details;
- challenge/withdrawal/successor links;
- exact reason codes;
- downloadable/copyable machine report;
- verifier revision/environment where relevant to `S0-K16`.

Layer 4 may be technical; Layers 1–2 must not require specialist knowledge.

## 4. Visual and language rules

### UX-R01 — no color-only meaning

Every state uses text, iconography, and programmatic accessibility labels. Green/red/amber alone are insufficient.

### UX-R02 — no authority inflation

Use “Authentically issued” or “Current as of …” only when the corresponding predicates pass. Never use “Government approved,” “Legally valid,” “True,” “Safe,” or “Official” unless a separately authorized semantic profile actually proves that proposition.

### UX-R03 — role labels are explicit

Display separately:

- original issuing authority role;
- preservation custody role;
- transparency-log role;
- checkpoint witness role;
- status/currentness source.

A preservation signature must never be visually presented as the original issuer's signature.

### UX-R04 — uncertainty is not success

Missing, conflicting, unsupported, or temporally indeterminate evidence yields a non-positive outcome. Do not show a green heading with a warning footnote.

### UX-R05 — currentness is time-bounded

Every current result says `Current as of <authenticated time>`. Offline results also show snapshot age and freshness limit.

### UX-R06 — historical records remain legible

Withdrawal or supersession does not replace the original with an error page. The original remains viewable with a prominent non-current status and successor/history link.

### UX-R07 — negative terminals receive equal integrity

Honest refusals, dissent, challenge, invalidation, and published negatives use the same proof/history affordances as positive records. They are not visually demoted to ephemeral notices.

### UX-R08 — semantic parity

Human-readable, localized, accessible, and machine outcomes must map to the same reason codes and predicates. Translation cannot omit the relative-basis rider or turn `authentic historical` into `current`.

### UX-R09 — no forced trust in the current server

A server-rendered result is accompanied by independently verifiable evidence or an explicit statement that verification was not completed. A server-supplied Boolean is never the proof.

### UX-R10 — no hidden network fallback

When offline mode is selected, the verifier discloses all attempted dependencies and performs zero network calls. If required material is absent, show `OFFLINE_CLOSURE_INCOMPLETE`.

## 5. Required outcome behaviors

## 5.1 `VERIFIED_CURRENT_AS_OF`

### Heading

**Verified current as of `<date-time>`**

### Required visible explanation

- The exact record was authentically issued by the evidenced authority role.
- Trusted time/status evidence supports issuance before the relevant revocation or compromise cutoff.
- The record is in the witnessed append-only public history.
- The authenticated GY-N12 status snapshot says it is current at the displayed cutoff.
- INT-R8's projection relation passed.

### Mandatory limitation

“This verifies the named record and status as of the displayed time. It does not by itself prove legal sufficiency, policy effectiveness, or truth beyond the signed claim.”

### Never infer

- current after the displayed cutoff;
- legal validity in every jurisdiction;
- substantive correctness;
- completeness beyond INT-R8.

## 5.2 `AUTHENTIC_HISTORICAL_WITHDRAWN`

### Heading

**Authentically issued in the past — withdrawn as of `<date-time>`**

### Required behavior

- Show original issuance evidence and date.
- Show withdrawal effective time, reason category/evidence reference where public, and current=false.
- Keep original record accessible.
- Link to challenge/adjudication/successor history.
- Do not use a broken-signature or “fake” visual treatment unless content/signature also failed.

### Never represent

- withdrawn record as current;
- withdrawal as proof the original signature was forged;
- original record as deleted or rewritten.

## 5.3 `AUTHENTIC_HISTORICAL_SUPERSEDED`

### Heading

**Authentically issued in the past — superseded**

### Required behavior

- Show successor record/epoch link and effective time.
- Show that the old record remains historically reproducible.
- Make the successor the default “current record” navigation target without hiding the old record.
- Preserve the old record's own basis and epoch.

### Never represent

- successor as if it were the original signature;
- old epoch without a superseded marker;
- rewritten old claim basis.

## 5.4 `AUTHENTIC_HISTORICAL_STALE`

### Heading

**Authentically issued — revalidation required**

### Required behavior

- Explain that a revision trigger or status freshness rule was crossed.
- Show the last authenticated status cutoff.
- Do not label current.
- Offer current status refresh only as a separate, visible action.

### Never represent

- stale epoch with a green current badge;
- an untrusted live response as a silent refresh.

## 5.5 `AUTHENTIC_HISTORICAL_AS_OF`

### Heading

**Authentically issued — current status not established beyond `<date-time>`**

### Required behavior

- State that historical issuance verifies.
- State why currentness is unavailable or snapshot is too old.
- Preserve the exact offline `as_of` cutoff.
- Offer evidence export.

### Never represent

- “current” or “still valid” without a fresh authenticated status source.

## 5.6 `TEMPORAL_VALIDITY_INDETERMINATE`

### Heading

**Signature found, but issuance time cannot be placed safely relative to key compromise or revocation**

### Required behavior

- Explain the uncertainty interval in non-technical language.
- Show that signature mathematics may pass while historical authority is unresolved.
- Show affected key/credential and evidence cutoff.
- Treat as non-current and non-verified.

### Never represent

- as a warning beneath `Verified`;
- as “probably valid” without a ratified probabilistic profile.

## 5.7 `COMMON_VIEW_NOT_ESTABLISHED`

### Heading

**Record appears in one publication history, but a common public view was not established**

### Required behavior

- Distinguish signature validity from log/witness failure.
- Show missing, conflicting, or insufficient witness/checkpoint evidence.
- Provide checkpoint identifiers for monitors/journalists.
- Do not claim the record is absent or forged solely from this failure.

### Never represent

- one log's inclusion proof as proof every verifier saw the same history.

## 5.8 `AUTHORITY_NOT_ESTABLISHED`

### Heading

**Signature is present, but authority to issue this claim was not established**

### Required behavior

- Show whether failure concerns credential chain, mandate, role, purpose, jurisdiction, interval, or succession.
- Avoid naming a person as unauthorized when the evidence is merely unavailable.
- Preserve signature-math detail in the expanded report.

### Never represent

- possession of a key, domain, OIDC account, or certificate as sufficient government authority.

## 5.9 `PROJECTION_RELATION_NOT_ESTABLISHED`

### Heading

**The public view could not be verified against the governed retained-claim contract**

### Required behavior

- Name INT-R8 proof absence/failure without attempting to classify omitted content.
- Do not expose restricted governed content as a debugging shortcut.
- Block the positive public outcome.

### Never represent

- valid signature as curing projection loss;
- an INT-R7 guess about `lossy_but_safe` or material omission.

## 5.10 `BASIS_INCOMPLETE`

### Heading

**The numeric claim is missing its signed basis**

### Required behavior

- Suppress any positive interpretation of `delta`.
- Identify the missing or mismatched obligation set, maintained assumptions, or relative-basis rider.
- Offer the complete historical statement if available.

### Never represent

- a bare `delta` as a smaller or approximate version of the complete claim.

## 5.11 `PROCEDURAL_HISTORY_NOT_ESTABLISHED`

### Heading

**The signed statement does not establish the claimed procedure**

### Required behavior

- Identify missing/contradicted sealing, firstness, chronology, substitution, adjudication, dissent, or published-negative evidence.
- Distinguish statement signature from history proof.
- Do not introduce a probability score.

### Never represent

- signer-controlled `signed_at` as proof of prospectivity;
- a later archive signature as the original seal.

## 5.12 `PRESERVATION_CHAIN_BROKEN`

### Heading

**Long-term verification evidence is incomplete or was renewed too late**

### Required behavior

- Show which certificate/status/hash/signature/timestamp/format link failed.
- Show original bytes if safe and available, but do not imply authenticity.
- Distinguish unsupported verifier from proven tamper.
- Provide preservation-event history.

### Never represent

- visible document readability as cryptographic continuity;
- a later re-sign as retroactive repair after algorithm failure.

## 5.13 `TAMPERED_OR_SIGNATURE_INVALID`

### Heading

**This record did not pass integrity/signature verification**

### Required behavior

- Stop all positive authority/currentness claims.
- Identify whether content commitment, required signature, canonicalization, or proof binding failed.
- Preserve diagnostic evidence without executing untrusted content.
- Offer a safe source/retrieval path designated by governance.

### Never represent

- attacker-recomputed FNV as valid;
- package-supplied replacement key as trust.

## 5.14 `PROFILE_OR_ALGORITHM_UNSUPPORTED`

### Heading

**This verifier cannot safely evaluate the record's proof profile**

### Required behavior

- Name profile/algorithm/policy version.
- Distinguish unsupported from invalid.
- Never fall back to a default algorithm or signature-only mode.
- Offer a verifier update path without automatically trusting the record's own code.

## 5.15 `OFFLINE_CLOSURE_INCOMPLETE`

### Heading

**Offline verification could not be completed**

### Required behavior

- List missing trust/status/timestamp/log/witness/epoch/projection/preservation material.
- Confirm that no network fallback occurred.
- Preserve any predicates that did pass without producing a positive top-level result.

## 6. Current client-side FNV strangle behavior

Any legacy packet whose only “verification” is the public-salt FNV mechanism must produce:

- outcome: `LEGACY_SELF_CONSISTENCY_NOT_AUTHORITY` or `TAMPERED_OR_SIGNATURE_INVALID` according to migration policy;
- historical authenticity: not established;
- current authority: not established;
- citizen text: “This older link contains a self-consistency code, not a cryptographic public proof.”

It must never produce:

- `Verified`;
- `Verified current`;
- `Authentically issued`;
- a green authority badge;
- a hidden compatibility pass.

The packet builder may continue to supply rendering data only after its result is fully dominated by the new verifier output.

## 7. Phone and low-bandwidth requirements

### UX-M01 — first screen is bounded and useful

Within the first viewport, show:

- outcome heading;
- issuer role;
- record identifier/title as supplied by the public content contract;
- historical/current distinction;
- authenticated `as_of`;
- one-sentence limitation.

### UX-M02 — progressive evidence loading

A positive result must not depend on optional visual expansion. Verification completes before the badge/heading appears. Evidence details may load progressively only when their commitments were already verified or the UI clearly remains pending.

### UX-M03 — offline indicator

Persistent indicator states:

- offline verification active;
- snapshot `as_of`;
- freshness threshold and whether exceeded;
- no network was contacted.

### UX-M04 — accessibility

- WCAG-compatible semantic headings and live-region announcements for state changes;
- keyboard and screen-reader access to every reason/evidence detail;
- text alternatives for proof-history visualizations;
- no motion-dependent or color-only status;
- dates shown in local format plus unambiguous ISO timestamp/offset in details;
- plain-language glossary for “withdrawn,” “superseded,” “stale,” and “historically authentic.”

### UX-M05 — safe handling

- do not execute scripts/macros from downloaded records;
- cap proof/package resource use;
- treat malformed archives and recursive structures as invalid/unreadable, not as partial success;
- do not upload offline records to a server without explicit user action and disclosure.

## 8. Journalist, agency, court, and machine affordances

### Journalist/monitor mode

Provide:

- checkpoint/tree size/root;
- witness set and independence policy;
- inclusion and consistency proof export;
- detected split-view evidence;
- bulk verification with per-record outcomes;
- stable public record and successor identifiers.

### Agency relying-party mode

Provide:

- credential path/policy;
- authority mandate/purpose/jurisdiction/interval;
- recognition-policy decision;
- currentness cutoff;
- succession evidence.

### Court/archive mode

Provide:

- original bytes and fixity;
- signing-time validation closure;
- compromise/revocation interval evidence;
- preservation and format migration lineage;
- original issuer versus preservation signers;
- verifier/policy versions and limitations.

### Machine mode

Provide a deterministic result containing:

- top-level outcome code;
- complete predicate vector;
- reason codes;
- `as_of` and verification time;
- profile/canonicalization/algorithm policy versions;
- evidence identifiers;
- no unsigned `verified` shortcut.

The final serialization is not selected here.

## 9. Challenge, access, and evidence acquisition

Every non-positive or historical-only outcome must provide a route to:

- download the verification report and proof evidence permitted for public release;
- request accessible or alternative-format evidence;
- locate the competent records/access/FOI channel;
- submit a technical discrepancy report;
- identify the current/successor record where one exists.

The UX must distinguish:

- technical discrepancy;
- public-record access request;
- challenge to current authority/status;
- substantive disagreement with policy.

PolicyOS must not imply it adjudicates categories owned by another institution.

## 10. Behavioral acceptance criteria

### UX-A01 — forged packet

Given attacker-chosen JSON and a correctly recomputed legacy FNV code, the page never shows any positive authenticity/currentness label.

### UX-A02 — replaced payload

Given a valid proof closure whose record bytes are changed, the first visible terminal is `TAMPERED_OR_SIGNATURE_INVALID`; no stale positive badge remains during or after verification.

### UX-A03 — package self-key substitution

Given payload, signature, and public key replaced together inside the package, verification fails authority/trust; package-relative signature math cannot produce a positive result.

### UX-A04 — revoked after valid issuance

Given trusted issuance before prospective revocation and current status that leaves the record current, UI may show current while clearly separating retired/revoked key status from record status.

### UX-A05 — forged after compromise

Given trusted issuance at/after compromise cutoff, UI never shows authentic historical or current.

### UX-A06 — uncertain compromise interval

Given overlapping issuance and compromise intervals, UI shows `TEMPORAL_VALIDITY_INDETERMINATE`, not a green result plus warning.

### UX-A07 — withdrawn record

Given historical authenticity and authenticated withdrawal, UI shows `AUTHENTIC_HISTORICAL_WITHDRAWN`, preserves original access, and shows current=false.

### UX-A08 — superseded epoch

Given old and successor epochs, opening the old record prominently shows superseded status and successor link; the old record remains reproducible.

### UX-A09 — stale status snapshot

Given an offline snapshot outside the freshness rule, UI states the last authenticated cutoff and never claims current now.

### UX-A10 — split view

Given internally valid but conflicting log checkpoints without witness reconciliation, UI shows `COMMON_VIEW_NOT_ESTABLISHED`.

### UX-A11 — wrong audience/jurisdiction

Given a valid signature replayed under a non-permitted audience or recognition policy, UI shows binding/policy mismatch and no positive result.

### UX-A12 — bare `delta`

Given a numeric value with missing/mismatched obligation-set or assumption commitment, UI shows `BASIS_INCOMPLETE` and does not foreground the number as verified.

### UX-A13 — procedural backdating

Given a signed narrative but no trusted prospective seal/chronology evidence, UI shows `PROCEDURAL_HISTORY_NOT_ESTABLISHED`.

### UX-A14 — timely archival renewal

Given deprecated original algorithms and a complete timely renewal chain, UI can show the historical/current result while clearly displaying preservation lineage.

### UX-A15 — late/missing renewal

Given algorithm failure before renewal, UI shows `PRESERVATION_CHAIN_BROKEN` even if a later signature exists.

### UX-A16 — offline isolation

Network-denied verification of a complete closure yields the same semantic predicate vector as online verification at the same authenticated snapshot, with offline labeling.

### UX-A17 — locale parity

Every supported locale maps the same machine outcome and preserves the `delta` rider, historical/current distinction, and `as_of` cutoff.

### UX-A18 — original versus preservation signer

A record renewed by a successor archive displays the predecessor as original issuer and successor as preservation custodian; they are never merged into one “signed by” label.

## 11. Prohibited representable states

The UI/data flow must make the following states structurally impossible:

1. forged or attacker-recomputed legacy packet showing `Verified`;
2. replaced payload showing a stale cached positive badge;
3. package-supplied replacement key establishing trust;
4. signature-valid but authority-invalid record showing “official”;
5. revoked/compromised-after-cutoff signature showing historical authenticity;
6. revoked-key record shown current merely because signature math passes;
7. withdrawn record shown current;
8. stale GY-N12 epoch shown without staleness;
9. offline result shown current beyond its authenticated `as_of`;
10. one log's inclusion proof shown as common view;
11. bare `delta` shown as verified;
12. procedural claim shown verified without history/chronology predicates;
13. preservation signer shown as original issuer;
14. unsupported algorithm silently treated as Ed25519/default;
15. INT-R8 proof failure hidden behind cryptographic success;
16. unsigned server Boolean treated as verifier evidence;
17. legal compliance, substantive truth, or institutional competence inferred from cryptographic validity;
18. a human translation conveying a stronger status than the machine result.

## 12. UX result standing

These requirements are implementable as a behavioral projection over the semantic predicate vector. They do not authorize the current route to publish and do not select a UI framework or API. At the pinned commit the public viewer's positive state is `verification_missing` and `semantic_test_missing`; DS12 must strangle the FNV predecessor before any positive public outcome can exist.

## 13. Post-audit controlling UX amendment

This section supersedes the two-question model in UX-T03, the aggregate uses of “historical authenticity” in §§3, 5, 10–12, and the capability labels in §12. It executes `R1`, `R2`, `R7`, `R8`, `R15`, `R18`, and `R19` for the human/machine surface.

### 13.1 Five visible questions plus evidence access

A non-expert result answers six bounded questions, all backed by the same machine report:

1. **Was this exact issuer-side statement authentically issued?** (`IssuerIssuanceAuthentic`)
2. **Does this public view faithfully correspond to the governed bound object?** (`ProjectionFaithful`)
3. **Was the bounded public history/common view established?** (`PublicHistoryEstablished`)
4. **Can the evidence still be verified at this evaluation time?** (`DurablyVerifiableAt(t_v)`)
5. **Is the record current under the latest applicable authenticated status as of the displayed cutoff?** (`CurrentAuthorityAsOf(t_q)`)
6. **Can the user obtain the permitted evidence needed to reproduce the result?** (`EvidenceObtainability`)

The first five are separately reportable dimensions, not logically independent predicates. A public-current positive requires all five to be established; the sixth must be `public_available` or `records_process_available` for a claim of independent citizen verifiability.

### 13.2 Information hierarchy amendment

Layer 2 shows the five dimensions in plain language and states the snapshot-selection result. Layer 3 shows evidence obtainability and every non-positive dimension. Layer 4 exposes exact machine results, evidence identifiers, snapshot/head provenance and access/restriction routes.

A single top-level heading may summarize the conjunction, but it must never hide an issuer-side positive behind a projection/log/archive failure or hide a projection/log/archive failure behind issuer authenticity.

### 13.3 `VERIFIED_CURRENT_AS_OF` amended behavior

The heading is permitted only when:

- `IssuerIssuanceAuthentic = established`;
- `ProjectionFaithful = established`;
- `PublicHistoryEstablished = established`;
- `DurablyVerifiableAt(t_v) = established`;
- `CurrentAuthorityAsOf(t_q) = established` using `latest_established_under_policy`;
- freshness is bounded to `t_q`;
- evidence obtainability is `public_available` or `records_process_available`.

Because INT-R8 is unaudited and GY-N12 is planned, no such positive is established by this research amendment.

### 13.4 New and corrected non-positive behaviors

#### `ISSUANCE_TEMPORALLY_UNAUTHORIZED`

**Heading:** **Signature mathematics passed, but issuance occurred after the applicable authorization boundary.**

Show `SignatureValid = established`, the effective revocation/compromise boundary, trusted issuance time and `IssuerIssuanceAuthentic = contradicted`. Never call it tampered or signature-invalid unless content/signature math also fails.

#### `STATUS_SNAPSHOT_ROLLBACK_DETECTED`

**Heading:** **The supplied status is authentic but not the latest applicable status.**

Show the supplied and later authenticated heads, block currentness, preserve issuer/projection/history/durability results, and offer a safe refresh or evidence route. An older authentic snapshot may be used only for an explicitly historical query.

#### `EVIDENCE_NOT_OBTAINABLE`

**Heading:** **The evidence needed to reproduce this result could not be obtained.**

Distinguish:

- no public or competent records route (`not_established`);
- competent lawful restriction (`competently_restricted`), with authority, scope, review route and effect on verification;
- temporary access failure, without converting it into evidence of tamper.

Do not claim independent public verifiability.

### 13.5 Existing outcomes under decomposition

- `COMMON_VIEW_NOT_ESTABLISHED` shows whether issuer issuance remains established and explicitly says public history/common view is non-positive.
- `PROJECTION_RELATION_NOT_ESTABLISHED` shows issuer issuance separately and blocks only projection-dependent/public-current reliance.
- `PRESERVATION_CHAIN_BROKEN` shows the issuer-side result separately and marks `DurablyVerifiableAt(t_v)` non-positive.
- `AUTHENTIC_HISTORICAL_WITHDRAWN` and `AUTHENTIC_HISTORICAL_SUPERSEDED` preserve original issuer attribution, durable evidence and current=false; projection and public-history dimensions remain visible.
- `TEMPORAL_VALIDITY_INDETERMINATE` remains non-positive where event ordering cannot be established; it differs from the definite `ISSUANCE_TEMPORALLY_UNAUTHORIZED` result.

### 13.6 Evidence obtainability task

Every result offers one of these explicit routes:

- direct public download or mirror;
- competent records/access/FOI process;
- competent restriction notice and review route;
- `not_established` when no dependable route is evidenced.

The route must identify expected evidence classes without exposing restricted content. PolicyOS does not adjudicate the access right; it reports the technical consequence of what is or is not obtainable.

### 13.7 Additional behavioral acceptance criteria

#### UX-A19 — split view preserves issuance result

Given valid issuer-side issuance and conflicting witness checkpoints, the UI shows `IssuerIssuanceAuthentic = established`, `PublicHistoryEstablished = not_established`, and no current/public positive.

#### UX-A20 — authentic snapshot rollback

Given an authentic older snapshot and a later authenticated applicable head, the UI shows `STATUS_SNAPSHOT_ROLLBACK_DETECTED`, never current.

#### UX-A21 — positive lawful succession

Given valid predecessor issuance plus a competent successor custody/preservation statement, the UI retains the predecessor as original issuer, labels the successor as custodian/preservation signer, and shows canonical current/superseded status separately.

#### UX-A22 — conflicting succession

Given two individually valid but conflicting succession statements without competent adjudication, the UI reports succession/current authority not established; it does not choose a winner.

#### UX-A23 — selective negative-terminal withholding

Given a procedural claim whose required negative/refusal terminal is omitted from the released history, `ProceduralHistoryBound` and `ProjectionFaithful` are non-positive, even when signature mathematics and other chronology edges pass.

#### UX-A24 — unavailable evidence

Given a proof reference that cannot be obtained publicly or through a competent records process, the UI shows `EVIDENCE_NOT_OBTAINABLE` and does not describe the record as independently citizen-verifiable.

### 13.8 Corrected pinned capability statement

At `02c5b8d`, the legacy FNV viewer exists and must be strangled. The replacement public predicate evaluator and citizen outcome projection are **absent/unallocated at pinned commit**. The real public-export producer exists, while its production route remains `bridge_missing`. No `verification_missing` or `semantic_test_missing` label is used to imply that the proposed replacement chain is already wired.

### 13.9 Anti-wire-format warning

Outcome names, dimension names, layer descriptions and function-like terms are behavioral semantics, not a UI component API, response schema, enum or serialization. Human and machine implementations may differ structurally only if their observable meanings, reason codes and failure ordering remain equivalent.
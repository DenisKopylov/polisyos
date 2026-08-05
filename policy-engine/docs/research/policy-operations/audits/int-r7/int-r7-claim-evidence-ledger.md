---
title: INT-R7 — Independent Claim–Evidence Ledger
verified_commit: f5671253b51554dde2dd22a6aef2ef827c5bd9dd
pinned_repository_commit: 02c5b8d23c757c92b9231e6e1e802d5701588908
authoritative_for:
  - audit mapping of every materially distinct load-bearing INT-R7 claim to offered evidence
  - independent support, narrowing, correction, or non-establishment verdicts
  - consolidation guidance on claims that should survive unchanged or only after revision
may_not_use_for:
  - production implementation authorization
  - adoption or ratification of INT-R7
  - final schema, wire, package, serialization, database, or API contract
  - owner, vendor, authority, service, witness, archive, or key-custodian appointment
  - legal sufficiency or jurisdictional compliance conclusion
  - claim that any missing dependency or capability has been delivered
research_only: true
---

# INT-R7 independent claim–evidence ledger

## 1. Selection method and denominator

The audit read all **10/10** files added by the audited branch and collapsed repeated prose
into **46 materially distinct load-bearing propositions**. A proposition is load-bearing when
removing or reversing it would change the selected profile, first-signature gate, repository
classification, seam allocation, or `GO_WITH_REVISIONS` standing. Decorative explanations,
examples, and repeated source summaries are not separate rows.

Verdicts:

- `supported` — evidence supports the claim as written;
- `supported_with_narrowing` — core claim survives after an explicit scope/assumption limit;
- `conditional` — coherent contract, but positive satisfaction depends on an undelivered input;
- `material_revision` — the claim's current formulation changes an important result;
- `minor_revision` — wording, metadata, or citation correction without changing the decision;
- `not_established` — evidence does not warrant the claim at the pinned state.

## 2. Complete load-bearing claim ledger — 46/46

| ID | Load-bearing claim in INT-R7 | Evidence offered by the audited work | Independent verdict | Audit disposition |
| --- | --- | --- | --- | --- |
| CL-01 | A mathematically valid signature is not equivalent to a governed `Verified` result. | Threat model, formal predicate vector, PKI/Sigstore/eIDAS transfer ledger, current FNV/Ed25519 source inspection. | **supported** | Preserve verbatim in consolidation. It correctly separates a key/bytes proposition from truth, competence, currentness, and disclosure safety. |
| CL-02 | Verification must expose multiple failure-visible dimensions rather than one Boolean. | Predicate catalogue and citizen result taxonomy. | **supported_with_narrowing** | Preserve the vector; replace “independent predicates” with “separately reportable dimensions” because several are derived or dependent. |
| CL-03 | The existing `signing.py` leaves `signed_at` and `signer_identity` outside the signed canonical statement. | `signing.py:62-94, 291-302, 409-441 @ 02c5b8d`. | **supported** | Registrable repository defect. |
| CL-04 | The existing revoked-key directory cannot distinguish genuine pre-revocation issuance from post-compromise backdated forgery. | Timeless set membership in `signing.py:444-517, 583-610`; mutable time metadata. | **supported** | Preserve precise formulation; it is not an attack on Ed25519 itself. |
| CL-05 | The browser FNV packet mechanism is forgeable by construction and must never produce authority. | Public salt/FNV/sign/verify path and positive viewer badge. | **supported** | Preserve; F-01 is a strong permanent negative. |
| CL-06 | `build_public_export_bundle` is a real projection producer, while the production publication/proof bridge is absent. | Definition, two tool callers, two test callers, one re-export, no evidenced production route. | **supported_with_narrowing** | Preserve `bridge_missing`; do not quote an independently audited exhaustive five-file denominator until the AST walk is retained. |
| CL-07 | The standalone verifier is reusable execution substrate but package-contained keys are not independently trustworthy. | `standalone_verifier_template.py` loads package keys and verifies against them. | **supported** | Preserve; independent trust distribution remains a new dependency. |
| CL-08 | `rotation.py` is the canonical nearby lifecycle owner but does not implement public-record temporal proof. | Runtime/JWT/local-key active/next/retired/revoked semantics. | **supported** | Preserve owner-first extension boundary without treating the module as capability. |
| CL-09 | Fulcio/keyless signing is a transferable identity pattern but not public administrative authority. | OIDC/ephemeral certificate implementation and Sigstore threat/security sources. | **supported** | Preserve the non-substitution limit. |
| CL-10 | Under `INT-K06`, the first likely public object is a procedural custody claim carrying no probability. | Binding ratification `INT-K06`; profile claim classes. | **supported** | Preserve as primary use case rather than a late special case. |
| CL-11 | A procedural claim's content is a history, so chronology, prospectivity, firstness, and anti-backdating are security semantics. | `INT-K06`; A-06/A-10; procedural profile; F-12. | **supported** | Preserve. A signature over an unproved narrative is not sufficient. |
| CL-12 | A `delta` is incomplete without its declared obligation set, maintained assumptions, and rider. | Binding `INT-K02`; `BasisBound`; F-11. | **supported** | Preserve as semantic substitution/security failure, not presentation quality. |
| CL-13 | Correction, challenge, withdrawal, and supersession append; prior bytes remain historically reproducible. | `INT-K01`, `S0-K08`; lifecycle state machine; F-17. | **supported** | Preserve. |
| CL-14 | Historically authentic issuance and current authority must be separate results. | Ratified append-only semantics, revocation cases, citizen UX, F-05/F-07/F-17. | **supported** | Preserve as one of the strongest findings. |
| CL-15 | Institutional authority requires role, mandate/delegation, jurisdiction, audience, purpose, and interval evidence beyond key possession. | Comparative PKI/Federal PKI/eIDAS analysis and profile authority boundary. | **supported_with_narrowing** | Preserve; configured technical policy cannot settle a disputed legal competence question and must return not established. |
| CL-16 | Trusted issuance time must be independent of signer-controlled `signed_at`. | RFC 3161, eIDAS/ETSI temporal validation, source defect. | **supported** | Preserve. |
| CL-17 | Signing-time credential/key status must be retained separately from current status. | RFC 5280/6960, RFC 3161, ETSI validation, Canadian guidance. | **supported** | Preserve. |
| CL-18 | Normal retirement, prospective revocation, known compromise, and uncertain compromise interval need different outcomes. | Lifecycle tables, source standards, F-05/F-06. | **supported** | Preserve. |
| CL-19 | Overlap with an unresolved compromise interval must be a non-positive indeterminate terminal. | Threat model and F-06. | **supported** | Preserve. |
| CL-20 | Merkle inclusion and consistency inside a presented tree do not establish common view. | RFC 9162 and split-view threat/F-08. | **supported** | Preserve. |
| CL-21 | Common-view evidence needs independently obtained checkpoints under a declared independence/non-collusion policy. | RFC 9162 limit, Sigstore threat model, witness element. | **supported_with_narrowing** | Preserve as INT-R7 design inference; RFC 9162 does not itself standardize the quorum or governance. |
| CL-22 | GY-N12 is the sole owner of epoch/currentness; INT-R7 only binds and verifies its output. | GY plan, profile dependency, no second lattice. | **conditional** | Ownership is coherent; no currentness-positive result exists until GY-N12 is delivered. |
| CL-23 | INT-R8 owns retained claims, projection/compression-loss semantics, and disclosure composition. | Repeated seam prohibitions and required interface. | **supported** | Preserve owner boundary. |
| CL-24 | INT-R7 may block public proof issuance when the required INT-R8 relation is absent or fails. | Profile proposition, baseline B0, dependency table. | **conditional** | Correct as public-projection gate; do not let this erase issuer-side issuance authenticity. |
| CL-25 | `ProjectionRelationValid` belongs inside `StatementComplete` and therefore inside `IssuanceAuthentic`. | Formal formula in threat-model artifact. | **material_revision** | False composition boundary. Split issuer statement completeness from public projection faithfulness. |
| CL-26 | `HistoricalAuthenticity` should require public history, preserved evidence, and algorithm-policy success. | Formal aggregate. | **material_revision** | As named, overbroad. Those controls are necessary for a durable public verification result, but their later loss must not rewrite the fact of issuer-side issuance. Rename/split the aggregates. |
| CL-27 | The selected long-term layer needs trusted time, retained validation material, and timely recursive renewal. | eIDAS/ETSI, RFC 4998, Canadian guidance, lifecycle profile. | **supported** | Preserve. |
| CL-28 | Renewal after the prior primitive has already lost trust cannot retroactively repair history. | RFC 4998 transfer, algorithm policy, F-15. | **supported** | Preserve. |
| CL-29 | A preservation attestation never replaces the original signature or makes its custodian the original issuer. | Role section, migration rules, F-14/F-18. | **supported** | Preserve. |
| CL-30 | Offline verification needs a complete closure and trust inputs authenticated independently of the package. | Standalone verifier defect, Sigstore bundle pattern, profile closure. | **supported** | Preserve. |
| CL-31 | Offline currentness is only “as of” an authenticated cutoff and must not be presented as current now. | Status predicates, citizen UX, F-16. | **supported** | Preserve, but add authentic-old-snapshot rollback handling. |
| CL-32 | The vector is complete for public verification. | Eleven headline dimensions and detailed predicates. | **material_revision** | Near-complete but missing a separately visible authentic-snapshot selection/anti-rollback result and a public evidence-obtainability result. |
| CL-33 | No single surveyed model supplies the entire lifecycle. | Nine-model comparative table with eliminating property for each. | **supported** | Preserve. Rejections are property-based, not codebase-convenience based. |
| CL-34 | The ten-element composite profile allocates one job to each mechanism. | Comparative/profile/lifecycle artifacts. | **supported_with_narrowing** | Preserve after correcting aggregate boundaries and labelling GY-N12/INT-R8 as undelivered gates. |
| CL-35 | PKI, qualified signatures, blockchain, and Sigstore do not by themselves establish administrative competence, currentness, legal sufficiency, or projection safety. | RFC/eIDAS/NIST/Sigstore/public-sector transfer ledger. | **supported_with_narrowing** | Correct as a non-sufficiency/non-substitution claim. Do not state that these regimes can never contribute to legal or administrative validity. |
| CL-36 | Public verification must handle organizational succession without rewriting predecessor attribution. | A-09, lifecycle succession, F-18, OAIS/NARA-style continuity. | **supported** | Preserve; add a positive lawful-succession and conflicting-successors case. |
| CL-37 | Public verification must be usable by a citizen/journalist with a phone and no institutional trust anchor. | Citizen task model, offline closure, QR/file import, human/machine twin. | **supported_with_narrowing** | Design target is sound; no implemented independently authenticated trust distribution exists. |
| CL-38 | Privacy-safe locators/commitments and offline status can reduce enumeration and query leakage. | A-12, profile addressing rules, transparency/privacy discussion. | **supported_with_narrowing** | Preserve as requirements; INT-R8 still decides disclosed content and no concrete commitment format is selected. |
| CL-39 | A Public Verification Custody Owner role and operating 10–30 year preservation lifecycle are required before first public signature. | OAIS/PREMIS, eIDAS/ETSI/NARA/Canada, first-signature gate. | **supported_with_narrowing** | Correct for first public authority-bearing issuance, not candidate/test signatures. The role is a requirement, not an appointment. |
| CL-40 | A real disconnected recovery drill must precede first public issuance. | Preservation gate and S0-K16-bounded recovery result. | **supported_with_narrowing** | Use representative non-authoritative/ceremonial records through the real path before first live issuance; otherwise wording can be circular. Add cross-custody and anti-rollback outcomes. |
| CL-41 | Passing the frozen suite requires strict `18/18` with zero unexpected positives, offline network contacts, or human/machine divergence. | Frozen rules and exact result block. | **supported as conformance policy** | Preserve. It has not run and cannot run on the pinned repository. |
| CL-42 | The 18 cases are executable as written and exact expected vectors are defined. | YAML cases and equality harness. | **material_revision** | At least 7/18 contain disjunctive/conditional predicate values; several cases combine mutations. Split and type the expectations before calling the suite executable. |
| CL-43 | The frozen 18 cases are complete enough to gate first issuance. | Threat coverage and metamorphic extensions. | **material_revision** | Add signer+TSA collusion, authentic-snapshot rollback, conflicting succession, parser/canonicalization differential, and selective negative-terminal withholding. |
| CL-44 | Suite passage is bounded to the named implementation, revision, environment, evaluator, policy, and fixtures under `S0-K16`. | Freeze rule 9 and scope section. | **supported** | Preserve. |
| CL-45 | New capability classes N-01 through N-07 and the public proof/verifier handoff are correctly labelled with repository missing-state vocabulary. | Repository integration table. | **material_revision** | The repository vocabulary requires prerequisites such as an existing consumer, producer/consumer pair, or wired chain. Those prerequisites are not evidenced for the new capability classes; relabel from pinned evidence or state absent/unallocated. |
| CL-46 | Overall standing is `GO_WITH_REVISIONS`, not `NO_GO` or unconditional acceptance. | Coherent composite design plus explicit missing dependencies, institutional decisions, implementation, and tests. | **supported** | Preserve. The blocking maturity label prevents consolidation of the capability table but does not refute the research architecture. |

## 3. Evidence conflicts and adjudication

### 3.1 Source implementation versus audited prose

The source wins on the repository defect. It confirms the audited prose: metadata is outside
the signed statement and revocation is timeless. No conflicting source evidence was found.

### 3.2 Formal definition versus lifecycle narrative

The narrative repeatedly says historical issuance and current/public outcomes remain distinct.
The formal formula makes projection, log/common view, and preservation prerequisites of
`HistoricalAuthenticity`. The formula is the more precise object and therefore exposes a real
conflict. Revision must change the formal aggregate, not merely add explanatory prose.

### 3.3 Repository vocabulary versus capability table

The canonical vocabulary owner says `producer_missing` requires a consumer expecting an
artifact. The capability table offers no deployed consumer for N-01 through N-07 and no wired public proof/temporal-verifier chain for the downstream labels it uses. The owner
vocabulary wins; the research labels must change.

### 3.4 External standards versus public-administration transfer

Technical standards support the component constructions. They do not automatically support
institutional competence, current record authority, or universal legal effect. INT-R7 mostly
states this honestly. The NARA and Federal PKI rows require the narrower current/historical and
subject-matter limits recorded in the citation audit.

## 4. Consolidation boundary

Claims CL-01, CL-03–CL-24, CL-27–CL-31, CL-33–CL-41, CL-44, and CL-46 survive in their
supported or explicitly narrowed form. CL-02, CL-25–CL-26, CL-32, CL-42–CL-43, and CL-45
require revision before their current wording or tables should be adopted.

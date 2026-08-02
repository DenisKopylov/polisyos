---
title: S0-GAP-01 — Minimum Policy Subject Reference and Semantic-Owner Decision
status: delivered
kind: architecture-research
research_task: S0-GAP-01
result_type: accepted_profile_with_owner_role_only
repository: https://github.com/DenisKopylov/polisyos
repository_branch: research/s0-gap-01-subject-reference-owner
repository_base_branch: research/stage0-anchor-amendments
repository_base_commit: fd4e32b44c9f7fe8fec5c3b8d493c2efbe7e8b65
historical_repository_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
inspection_date: 2026-07-29
authoritative_for:
  - research-level subject-reference compatibility decision
  - research-level semantic-owner role decision
  - bounded input to later Wave-2 and H2 architecture research
may_not_use_for:
  - PolicyMatter implementation
  - production code or schema authorization
  - canonical package placement unless separately ratified
  - registry or resolver implementation
  - identity adjudication
  - split or merge adjudication
  - legal succession inference
  - evidence applicability
  - authority grant
  - migration of existing identifiers
  - mandatory policy_matter_ref
  - public identifier deployment
  - production capability claim
research_only: true
---

# S0-GAP-01 — Minimum Policy Subject Reference and Semantic-Owner Decision

## Executive Finding

| Boundary | Verdict |
|---|---|
| **OWN** | PolicyOS owns the ability to refer consistently to the subject of its own justification-custody claims; the correctness and scope of associations between its cases, claims, artifacts, publications, and that reference; append-only preservation and correction of those associations; tenant- and authority-safe use; non-reinterpretation of existing identifiers; and truthful projection of references it publishes. |
| **INTEGRATE** | PolicyOS may admit provenance-bearing assertions from competent external owners about official identifiers, renames, transfers, continuation, replacement, split, merger, succession, competence, jurisdictional identity, and public-record identity. PolicyOS owns admission for a declared custody purpose and the reaction of its own claims, not the external institutional truth. |
| **OBSERVE** | Names, URLs, descriptions, embeddings, similarity scores, LLM classifications, announcements, and unadmitted metadata may propose candidate associations. They cannot mint identity, admit a relation, pool evidence, or create public authority. |
| **OUT_OF_SCOPE** | PolicyOS does not establish legal or institutional sameness, operate an authoritative external-entity registry, assign another authority's official identifiers, adjudicate merger or succession, or infer evidence inheritance from reference continuity. |

**Result: `accepted_profile_with_owner_role_only`.** A reference above `case_id` is functionally required, but the repository does **not** yet justify a shared typed or persisted subject-reference ABI, canonical package, global issuer, central registry, or resolver. The accepted research-level profile is deliberately smaller:

1. The subject is a **PolicyOS custody subject**: the opaque target to which PolicyOS attaches its own justification-custody records across cases. It is not, by definition, a legal matter, programme, institution, instrument, or administrative case.
2. Minimum reference identity is **assigning system plus opaque local value**. A raw unqualified token is unsafe.
3. Tenant or authority-domain qualification must accompany comparison and persistence whenever the assigning system is not proved globally unique and cross-tenant safe. Qualification may be carried by the enclosing association; it need not be embedded in the token.
4. Reference equality proves only the same token under the same assigning system and compatible qualification context. It proves no legal continuity, evidence applicability, claim authority, public currentness, or permission to combine records.
5. Cardinality is expressed through repeatable scoped associations, preserving one-to-many, many-to-one, and many-to-many cases.
6. Association correction is append-only and preserves stable assertion identity, actor, reason, transaction visibility, prior assertion, deterministic cutoff reconstruction, and affected-claim review. Signed and content-addressed bytes are not rewritten.
7. The selected semantic vocabulary/profile owner is the repository's cross-package architecture-governance role: `@architecture-owners` / `team-architecture`, with mandatory affected-owner review. This is a semantic and compatibility role, not a code package, issuer, registry, resolver, or runtime owner.
8. No package is selected. PDC is an integration neighborhood; `core.contracts` is only a possible future mechanical host; runtime quality is a verifier/adapter; core artifacts and audit preserve bytes and history. None is the canonical semantic owner.
9. Current compatibility posture is **adapter-local references plus explicit mappings constrained by this profile**. Promotion to a shared ABI requires real cross-family consumers, issuer/namespace rules, tenant/federation tests, no-rewrite adoption evidence, and a ratified package decision.

`PolicyMatter` remains a provisional historical term. It is unsafe when it implies a complete external legal or administrative ontology. Downstream work should use “PolicyOS custody subject” unless and until a separately ratified ontology proves a stronger term.

## 1. Task and Boundary

### Research question

What is the minimum implementation-neutral subject-reference compatibility contract, and which semantic owner is competent to issue and govern it, without fixing PolicyMatter cardinality, relation adjudication, evidence applicability, or package layout prematurely?

The question decomposes into four decisions: whether an above-case attachment concept is needed; what equality may safely mean; which role governs cross-package semantics; and whether that semantic decision warrants a shared type, issuer, registry, resolver, or migration now.

### Four-way boundary verdict

The verdict in the Executive Finding is controlling. In operational terms, PolicyOS may allocate an internal custody reference only under an explicitly governed PolicyOS or tenant assigning system; may retain externally supplied identifiers only as qualified aliases or mappings; and may record relation assertions only as provenance-bearing, correctable assertions whose adjudication and downstream effects remain with competent owners.

### Standing and non-authorizations

S0-GAP-01 is a temporary research identifier created by Stage-0 cross-audit synthesis. This report remains `research_only`; it is not inserted into an authoritative backlog, completion ledger, ADR corpus, production plan, schema catalog, or capability register. It authorizes no implementation, migration, public identifier, registry, resolver, legal conclusion, evidence inheritance, or production claim.

## 2. Repository Baseline

### Historical and current commits

| Baseline | Exact resolution | Effect on this inquiry |
|---|---|---|
| Historical Stage-0 baseline | `main` at `4813b49f6ce14e8debf3aaea096f0967d38d9768` | Ratified the PolicyOS identity/custody boundary and is also current `main`. |
| Current `main` | `4813b49f6ce14e8debf3aaea096f0967d38d9768` | No current-main delta. |
| Recorded amendment head | `290725446b8c073eb577f421ae2056986fbfcafb` | Task-supplied baseline. |
| Resolved amendment head | `fd4e32b44c9f7fe8fec5c3b8d493c2efbe7e8b65` | Four commits ahead, zero behind. Later changes only corrected two external-source links and expanded the conformance source audit; they do not change owner, ABI, cardinality, or attachment conclusions. |
| PR #5 | Open draft, unmerged and unratified | Used as amended research guidance only. |
| S0-GAP-01 branch | `research/s0-gap-01-subject-reference-owner` from exact `fd4e32b...` | Independent parallel lane. |
| Optional OPS-R4 | PR #6 head `6eafee90e20053f05a6d31b9d2e5dd8d67996e36` | Used only for compatible append-only correction and historical-cutoff assumptions; no owner or wire sketch inherited. |

The comparison is recorded in GitHub's commit view: <https://github.com/DenisKopylov/polisyos/compare/290725446b8c073eb577f421ae2056986fbfcafb...fd4e32b44c9f7fe8fec5c3b8d493c2efbe7e8b65>.

### Stage-0 inputs

The amended PAO-R0, PAO-R1, OPS-R15, source manifest, amendment disposition ledger, conformance report, all Stage-0 consolidation documents, and the independent PAO-R0 audit were read in full. Their common controlling result is:

- stable attachability above one case is a functional requirement;
- PDC is a likely integration neighborhood but not a proved semantic owner;
- no canonical issuer, namespace, schema, registry, or migration is established;
- fixture-local subjects and adapter seams are permitted;
- family owners retain payload, lifecycle, evidence, and authority semantics;
- a universal envelope, common status lattice, and automatic evidence inheritance are rejected.

Where the amended PAO-R0 differs from its original, the amendment controls current Stage-0 guidance; the original is treated as research history. Repository instructions and ownership rules were inspected at `AGENTS.md`, `policy-engine/CONTRIBUTING.md`, `docs/reference/ownership.md`, `.github/CODEOWNERS`, `architecture/imports/policy.toml`, `architecture/public_surface/contract.toml`, and `docs/adr/README.md`. The requested `policy-engine/AGENTS.md` is absent at the pinned tree; no nonexistent local instruction was inferred.

### Independent identifier/reference census

The census searched every required vocabulary family, including `PolicyMatter`, `policy_matter`, `matter_id`, `matter_ref`, subject/entity/resource/object/case/run/job/decision/policy/portfolio/tenant/cell/jurisdiction IDs, namespace/issuer/authority/external/canonical/alias/relation/correction terms, and artifact/resource/entity references. Names were not treated as semantics.

| Symbol/path | Current owner | Object identified; namespace/issuer/scope/stability | Exposure and equality semantics | Persistence, producers, consumers, correction | Capability state; collision/safe-reuse verdict; why not custody-subject identity |
|---|---|---|---|---|---|
| `PolicyMatter`, `policy_matter*`, `matter_id`, `matter_ref` | None in implementation | No typed or persisted implementation occurrence; research vocabulary only | No executable equality | None | `research_only`; no reusable implementation. |
| `case_id` across case/corpus/runtime families | Family-local case owners | One case/fixture token; namespace usually implicit; often tenant-qualified only by enclosing payload | Equality proves same local case token only | Family DTOs, corpora and runtime records; local producers/consumers; replacement rules vary | `implemented` locally; collision risk when owner/tenant context is dropped; cannot represent several cases concerning one continuing subject. |
| `run_id`, `job_id` | Runtime/control plane | One execution or job; operational issuer; run/job scope | Equality proves same operational token | Runtime logs, PDC, workflow artifacts | `implemented`; not lifetime identity. |
| `RuntimePolicyDesignCase.graph_id`, `graph_ref` | `polisyos.pdc` plus artifacts | Compiled case graph and its bytes; run-derived or CAS-qualified | Same compiled graph token/bytes, not same real-world subject | PDC compiler and CAS; runtime/Atlas consumers | `implemented`; safe only for graph identity. |
| `ArtifactID`, `ArtifactRef` | `core.artifacts` | Immutable bytes; `sha256` assigning algorithm; global-by-content | Equality proves byte identity and compatible ref metadata | CAS/manifests/signing/audit; append by new artifact | `implemented`; identical bytes can concern different subjects, and wrong associations do not change byte integrity. |
| `ArtifactOwnershipClaim` | Artifacts/security | Tenant/cell access claim over bytes | Same artifact may have separate ownership claims | Ownership index; access-control consumers | `implemented`; authority isolation, not subject identity. |
| `ProvenanceCoreRef` | `core.contracts` mechanical ABI; family producer | Minimal provenance link with owner-local string fields | Equality follows supplied strings only | Embedded DTO | `contract_only`; no global issuer or resolver. |
| `decision_lineage_key` | `core.contracts` + Scientist validation | One decision-packet lineage; caller-supplied raw key, locally hashed for storage | Equality proves same supplied lineage key; current local storage is tenant-blind | `decision_validity/lineages/<hash>.json`; Scientist producer; runtime/governance consumers | `implemented`; collision/authority risk if treated globally; not a custody subject. |
| `PolicySpec.policy_id`, intervention IDs | IR governance | Authored proposal/intervention nodes inside an IR payload | Same candidate token in authoring context | IR artifacts; compilers and analysis consumers | `implemented` locally; candidate identity, not continuing custody identity. |
| `PolicyPortfolio.portfolio_id` | IR loading | Candidate policy set/portfolio | Same portfolio token in context | IR payload/artifact | `implemented`; grouping, not external or custody subject. |
| IR world document/claim/event IDs | IR world/Fabric/Lex bridges | Deterministic hashes of canonicalized source locator, claim, event, or bytes | Equality proves same normalized payload under algorithm | World store/fact log; Fabric/Lex producers | `implemented`; content/source identity does not establish competent legal or policy identity. |
| Lex `LegalEntity.entity_id`, `LegalFact.subject_id/object_id` | Lex legal knowledge graph | Graph node or triple endpoint; graph-local/versioned issuer | Equality proves node token in that KG | KG store/index; Lex consumers | `implemented`; explicitly not legal-person adjudication or PolicyOS custody subject. |
| Lex legal document official ID/canonical URL | External legal source, integrated by Lex/Data Forge | Source-local document identifier/locator; jurisdiction/source qualified | Equality follows external convention only | Corpus manifests and legal evaluation | `external_dependency`/`implemented` adapter; document identity is not policy-subject identity. |
| Data Forge catalog `entity_id`, `external_id`, aliases | Data Forge source/catalog owner | Source-local catalog mapping; provider/dataset qualified; mutable mapping | Unqualified equality unsafe | DuckDB mapping tables; ingestion/catalog consumers | `implemented_but_not_orchestrated` for this purpose; reusable only as an external-alias pattern. |
| `tenant_id` | Security/runtime/data owners | Tenant authority and persistence partition | Equality proves same tenant under tenancy contract | Ownership claims, DTOs, paths, audit | `implemented` but inconsistent across families; qualification context, not the real-world subject. |
| `cell_id` | Owner-local locations | Cell, observation scope, or future authority subdivision depending on owner | No repository-wide equality meaning | Embedded owner-local fields | `partial_owner`; do not invent a universal authority domain. |
| `jurisdiction` | Lex/capability/applicability owners | Legal or operating scope assertion | Same label does not prove identity or competence | Owner-native evidence and scopes | `implemented` in parts; authority/applicability context, not identity. |
| Public/export identifiers and URLs | Runtime/Atlas/public-record producers | Projection/deep-link token | Equality proves same projection token under issuer/version | Public bundles/routes/caches | `projection_only`; Atlas cannot mint, merge, or adjudicate identity. |

No current identifier can be promoted safely by renaming. The strongest reusable patterns are: algorithm-qualified immutable artifact IDs; tenant-separated ownership claims; owner-local source identifier plus source/namespace; append-only audit records; additive sidecars; and projection-only authority boundaries.

### Existing capability chains

| Candidate model | Contract → issuer → persistence → association → consumer → verifier → correction/history → projection | State |
|---|---|---|
| PDC-owned | PDC graph contracts exist; no subject issuer, namespace, association store, correction path, or non-PDC consumer contract | `integration_neighborhood`; `issuer_missing`, `persistence_missing`, `bridge_missing` |
| `core.contracts` ABI | Mechanical shared DTO package exists; no semantic issuer, persistence, correction, or compatibility governor for this meaning | `contract_only`; `partial_owner` at most |
| Architecture-governed semantic profile | Ratified cross-package review role and Stage-0 owner map exist; profile can constrain adapters; code/issuer/persistence intentionally absent | `research_only` semantic owner role; suitable for this result, not production capability |
| Adapter-local references | Multiple owner-local IDs and mapping patterns exist; explicit cross-family subject mappings do not | `implemented` locally, `bridge_missing` across families |
| Central registry/resolver | No contract, producer, store, verifier, or consumer requirement | `blocked` / unjustified new gravity |

### Current defects separated from research

Repository-wide import-gate drift, public-surface snapshot drift, a tenant-private reference redaction failure, and tenant-blind local decision-lineage persistence were identified by the PAO-R0 audit. They are relevant warnings, not substitutes for the semantic-owner decision. This report does not convert existing defects into a reason to choose or reject a subject-reference owner; it requires future adoption tests to demonstrate collision and leakage safety independently.

## 3. Conceptual Separations

### Subject

The narrow accepted subject is the **opaque target of PolicyOS justification custody**. It can be associated with interventions, programmes, instruments, initiatives, problems, institutions, or public representations, but none of those is definitionally identical to it.

### Reference

A subject reference is a technical identifier pair used by PolicyOS records to point toward that custody subject. It is not the subject and has no authority effect by itself.

### Namespace and issuer

The assigning system defines uniqueness and allocation rules; the issuer/assigner allocates a local value under those rules. Semantic ownership governs meaning and compatibility. These roles may be different. An external authority may issue an official alias while PolicyOS architecture governance defines how PolicyOS records that alias without making it canonical.

### Association

An association is a scoped, provenance-bearing assertion that a case, claim, artifact, or public record concerns a reference for a declared role. It carries cardinality, provenance, correction, and historical-view obligations that do not belong inside the reference token.

### Relation and adjudication

An identity relation connects references using an asserted relation such as candidate continuation, replacement, split, merger, predecessor, or related subject. The assertion producer is not necessarily the competent adjudicator. Relations are correctable records, not fields that upgrade equality.

### Evidence applicability

Evidence applicability is a separate decision owned by canonical evidence/claim owners and future OPS-R2 work. A subject association or relation may trigger review; it never grants support, transportability, inheritance, or claim authority.

### Public identity

A public identifier is a governed projection. It may differ from internal identity to prevent enumeration, tenant leakage, correlation, or disclosure of sensitive subject existence. Public projection does not acquire issuer or semantic-owner powers.

### Artifact identity

Artifact identity is immutable byte identity. Association correctness, authority, and currentness are separate. A signed artifact may remain cryptographically valid while its subject association is wrong or later superseded.

The owner-role decomposition is therefore mandatory:

| Role | Governs |
|---|---|
| Functional custody owner | Why PolicyOS needs above-case attachment and which PolicyOS records may use it |
| Semantic vocabulary/profile owner | Meaning, equality limits, compatibility and promotion rules |
| Package owner | Location and mechanical evolution of a code type, if ratified later |
| Issuer/assigner | Allocation under one assigning system |
| Namespace governor | Uniqueness, retirement, collision and reuse rules for that system |
| Persistence owner | Storage/index of references or associations |
| Resolver owner | Current or historical lookup response, if any |
| Association owner | Scoped assertion from a PolicyOS object to a reference |
| Relation assertion owner | Provenance-bearing relation proposal/assertion |
| Relation adjudicator | Competent acceptance, dispute or rejection |
| Evidence-applicability owner | Whether evidence may support a claim after an association/relation |
| Verification owner | Syntax, qualification, collision, scope and history checks |
| Projection owner | Privacy-safe public representation without minting semantic identity |

Four separate predicates are required:

- `same_reference(a,b,context)`: same assigning system, local value, and compatible qualification.
- `same_asserted_subject(a,b,assertion)`: a provenance-bearing assertion says two references concern one custody subject; it may be disputed or corrected.
- `related_subjects(a,b,relation_assertion)`: an explicit typed relation exists; relation presence is not equality.
- `legally_continuous(a,b,competent_evidence)`: a competent external process supports legal continuity; PolicyOS may admit the evidence for a purpose but does not mint the conclusion from token equality.

Similarity can propose candidates but cannot upgrade any predicate to authority.

## 4. External Research Baseline

### Persistent-identifier governance

| Primary/canonical model | Useful lesson | Limit for PolicyOS |
|---|---|---|
| RFC 3986, URI syntax — <https://www.rfc-editor.org/rfc/rfc3986> | Identifier syntax and comparison are scheme-dependent; a URI can identify without guaranteeing dereference. | URI form does not establish competent authority or legal identity. |
| RFC 8141, URNs — <https://www.rfc-editor.org/rfc/rfc8141> | Namespace identifier plus namespace-specific string separates assignment rules from local value. | A URN-shaped value does not justify a PolicyOS global namespace or resolver. |
| DOI Handbook — <https://www.doi.org/the-identifier/resources/handbook/>; Handle — <https://www.handle.net/> | Persistence depends on governance, registration obligations, metadata and resolution operations, not syntax alone. | DOI governance does not prove PolicyOS needs a global registry. |
| ARK Alliance principles — <https://arks.org/about/> | Persistence is an organizational commitment; resolution and identity may survive location changes. | ARK syntax would not adjudicate custody-subject continuity. |
| HL7 FHIR `Identifier` and `Reference` — <https://hl7.org/fhir/R5/datatypes.html#Identifier>; <https://hl7.org/fhir/R5/references.html> | Distinguishes an identifier assigned by a system from a literal/logical reference and carries `system + value`. | Healthcare semantics, status and resource cardinality are not imported. |

### Legal/public-record identity

| Model | Useful lesson | Limit |
|---|---|---|
| OASIS Akoma Ntoso naming — <https://docs.oasis-open.org/legaldocml/akn-nc/v1.0/akn-nc-v1.0.html> | Separates legal work, expression, manifestation and item identifiers; versions and manifestations should not be collapsed. | Legal-document identity does not determine PolicyOS custody-subject cardinality. |
| European Legislation Identifier — <https://eur-lex.europa.eu/eli-register/about.html> | Assigning jurisdictions govern legal-resource identifiers and metadata; multiple manifestations may represent one legal resource. | ELI cannot be reused as a generic policy-subject identifier. |
| NARA local identifier guidance — <https://www.archives.gov/research/catalog/lcdrg/elements/localidentifier.html> | Local identifiers require organizational context and may not be globally unique. | A local record number is an alias, not universal sameness. |
| Library of Congress persistent identifier guidance — <https://www.loc.gov/preservation/digital/formats/fdd/fdd000308.shtml> | Persistent naming and resolution are institutional commitments with preservation implications. | Resolution availability is not identity truth. |

### Provenance and archival relations

| Model | Useful lesson | Limit |
|---|---|---|
| W3C PROV-O — <https://www.w3.org/TR/prov-o/> | Entities, activities, agents, attribution and derivation can preserve who asserted a mapping and how it changed. | Provenance of an assertion does not prove the assertion's legal correctness. |
| ICA Records in Contexts Ontology — <https://www.ica.org/standards/RiC/ontology> | Record identity, agents, functions and relations can remain many-to-many and historically contextual. | RiC is not a PolicyMatter ontology or runtime schema. |
| PREMIS Data Dictionary — <https://www.loc.gov/standards/premis/> | Preservation events, agents, objects and outcomes support append-only correction and durable interpretation. | PREMIS event structures are not a universal PolicyOS event envelope. |
| RFC 7089 Memento — <https://www.rfc-editor.org/rfc/rfc7089> | Current and historical representations require explicit time negotiation and stable original-resource identity. | A resolver's current response cannot rewrite the mapping visible at an earlier decision cutoff. |
| DataCite relation types — <https://datacite-metadata-schema.readthedocs.io/en/4.5/properties/relationType/> | Typed relations such as `IsVersionOf`, `IsNewVersionOf`, and `IsIdenticalTo` should remain explicit rather than collapsed into identifier equality. | DataCite relations do not adjudicate legal continuation or evidence inheritance. |
| PRONOM — <https://www.nationalarchives.gov.uk/PRONOM/> | Registry persistence can support interpretation of external formats after producers disappear. | It illustrates resolver/registry operations, not a requirement for a subject registry. |

### Federation and resolution

External models converge on a minimum discipline: preserve assigning system, local value, issuer provenance, and relation semantics; do not infer global equality from matching local values; and do not make successful resolution a prerequisite for historical interpretation. Federation is an admitted mapping problem, not string comparison.

### Limits of imported models

No external model is imported wholesale. In particular: DOI does not prove a global registry; resolvable URIs do not prove authority; Akoma Ntoso does not fix PolicyMatter cardinality; FHIR does not define PolicyOS subjects; and an `owl:sameAs`-style assertion would be too strong for legal or institutional continuity without competent evidence and purpose-scoped admission.

## 5. Requirements and Falsifiers

### Functional need

Case-local identity cannot represent original design, revalidation, incident review and correction as separate cases concerning one continuing custody subject without reusing `case_id` dishonestly. It also cannot represent one case concerning two independently accountable interventions. Therefore the above-case concept is needed. What is not yet proved is a shared ABI: adapter-local references plus explicit associations can satisfy the current research requirement.

### Tenant and namespace safety

Unqualified equality is prohibited unless the assigning system's uniqueness and federation rules are known. Identical `PROGRAMME-17` values in two tenants remain distinct by default. Cross-tenant sameness requires an explicit mapping, source/issuer provenance, admission purpose, authority boundary, correction history and verifier decision. Matching aliases never pool evidence automatically.

### Cardinality compatibility

The profile permits:

- one case to one or many subjects;
- many cases to one subject;
- many cases to many subjects;
- one artifact to several subjects with explicit scopes;
- one subject to several legal instruments and public representations;
- one legal instrument to several subjects.

No singular `policy_matter_ref` field is authorized. Associations require a role/scope external to the reference identity so claims and evidence can remain separately scoped.

### Correction and replay

A correctable association must have stable assertion identity independent of insertion order; actor; reason; transaction-visible time; target object and association scope; asserted reference; provenance; optional prior assertion/correction link; and deterministic cutoff ordering. The current view is derived from append-only assertions. Old artifacts, signatures, hashes and prior cutoff views remain unchanged.

### Privacy and public projection

Internal identifiers should not be public by default. A projection owner may emit a separate non-enumerable public ID or qualified external alias, bound to an immutable/public record and correction history. Atlas consumes admitted projections; it cannot allocate, merge, split or canonicalize identity. Public-ID rotation must not rewrite internal custody history.

### Authority non-inference

The following are falsifiers and hard vetoes: reference equality grants legal continuity, evidence applicability, claim authority, public currentness or combination permission; similarity mints identity; unresolved aliases fail open; split/merge copies evidence automatically; resolver current state rewrites historical replay; or a public surface creates identity.

### Minimum-profile necessity ledger

| Candidate component | Failure prevented / fixture | Existing owner or context alternative | Cost | Verdict |
|---|---|---|---|---|
| Opaque local value | Distinguishes tokens inside one assigning system; S-16 | None | Minimal | **Mandatory identity component** |
| Assigning system / namespace | Prevents equal local tokens from colliding; S-01, S-13, S-16 | Cannot be inferred reliably from consumer package | Minimal | **Mandatory identity component** |
| Issuer | Needed to evaluate authority of allocation or alias; S-18 | May be governed by assigning-system metadata or association provenance | Coupling if embedded everywhere | **Required for issuance/admission, not intrinsic equality field** |
| Tenant scope | Prevents cross-tenant collision/leakage; S-01, S-14 | Enclosing authority-bound association may carry it | Privacy/coupling | **Mandatory qualification when namespace is not globally safe; context-carried preferred** |
| Cell/authority scope | Prevents collision only where an existing owner defines the domain | Existing ownership/authority container | High ambiguity | **Context-carried only; never invented globally** |
| Jurisdiction | Qualifies authority or external alias; S-09–S-11 | Legal/applicability evidence | Overstates identity | **Outside identity; context/evidence only** |
| Reference version | Needed only if serialization semantics change | Contract/versioned container | ABI gravity | **Outside minimum identity** |
| Subject kind | Could prevent category confusion but no current fixture requires a stable closed taxonomy | Association role/owner-native payload | Ontology lock-in | **Excluded from minimum; optional adapter metadata** |
| Public representation | Prevents leakage while preserving links; S-14 | Projection record | Privacy if conflated | **Separate projection, not identity component** |
| Provenance reference | Needed to assess association/alias assertions | Association record and audit | Duplication if on every token | **Required on assertions, not bare reference** |
| Created/transaction time | Needed for cutoff replay; S-12, S-17 | Owner-native association history; OPS-R4-compatible roles | Temporal envelope risk | **Required for history, outside reference** |
| Resolver URL | Convenience only; S-13 requires survival without it | Optional resolver metadata | Operational coupling | **Not required** |
| Aliases | External interoperability; S-05, S-13, S-18 | Explicit alias mappings | Can leak/link records | **Separate mappings** |
| Status | No identity failure prevented; creates parallel lattice | Canonical family lifecycle owners | High gravity | **Excluded** |
| Relation list | Split/merge/continuation need assertions; S-05–S-09 | Dedicated correctable relation records | Authority laundering if embedded | **Excluded from reference** |
| Correction link | Needed for deterministic history | Association/relation record | Minimal local cost | **Required in owner-native history, excluded from identity profile** |

Removing either assigning system or local value produces a concrete collision. Removing tenant/authority qualification where the namespace is local produces false cross-tenant equality. No other field is necessary to define reference identity itself.

## 6. Comparative Owner Models

### PDC-owned extension

PDC already composes case graphs and is the closest attachment neighborhood. It can carry repeatable association edges without changing case identity. It is rejected as semantic owner because its README limits authority to graph structure, its current graph identity is run/case-derived, non-PDC consumers would depend upward on a case package, and no issuer/namespace/history chain exists. Selecting it would make a case package own lifetime identity and create P27 duplication with family owners.

### `core.contracts` shared ABI

`core.contracts` is dependency-stable and can reduce import cycles, but shared placement is not semantic competence. A DTO there could become ownerless, attract lifecycle/evidence/public fields, and expose a broad public ABI before issuer and consumer chains exist. It remains a possible mechanical host only after semantic ratification and real consumer proof.

### Dedicated bounded semantic owner

A bounded architecture-governance semantic profile is justified; a new code package, registry, issuer, resolver or service is not. The governance role can define equality limits, mandatory qualification, compatibility tests and promotion gates while leaving persistence and issuance with competent owners. This separates semantic ownership from implementation gravity.

### Adapter-local references

Adapter-local references with explicit mappings minimize current coupling and match existing source-local identifier patterns. They risk identity islands and repeated adapters, so they are acceptable only under the common profile: system+value, explicit qualification, no inference, append-only mappings, and cross-family compatibility fixtures. This is the current implementation posture.

### No shared reference yet

Pure case-local/fixture-local identity is too weak for above-case custody and H2 planning. The “no shared ABI yet” part is accepted; the “no shared semantic concept” part is rejected. A profile without a shared type is sufficient now.

### Decision matrix

Ratings are `strong`, `qualified`, `weak`, or `veto`; no numerical total hides vetoes.

| Criterion | A PDC | B `core.contracts` | C governance profile; no package/service | D adapter-local + mappings | E case/fixture only |
|---|---|---|---|---|---|
| Semantic competence | weak: graph owner | weak: mechanical ABI | **strong: cross-package boundary role** | qualified: owner-local | weak |
| Dependency direction | weak for non-PDC consumers | strong mechanically | strong; no import | strong locally | strong |
| Consumer reach | qualified but PDC-biased | strong if adopted | strong as guidance | qualified through adapters | weak |
| Issuer enforceability | missing | missing | qualified: can set gates, not allocate | owner-local | missing |
| Tenant isolation/federation | not established | type cannot enforce alone | **strong requirements; implementation pending** | qualified if mappings comply | weak |
| Cardinality openness | qualified via graph edges | qualified if list/edge external | **strong** | strong | weak for cross-case |
| Historical correction/replay | missing owner-native chain | missing | **strong obligations; storage-neutral** | qualified by adapter history | weak |
| Authority safety | PDC gravity risk | shared-envelope risk | **strong explicit non-inference** | qualified | weak due implicit identity |
| Privacy/public separation | projection risk | ABI exposure risk | **strong separation** | qualified | weak |
| Migration/no rewrite | qualified if sidecars | risk of mandatory field migration | **strong no-rewrite rule** | strong | strong short-term |
| Public projection | PDC/Atlas coupling risk | broad surface risk | **governed derivative only** | qualified | weak |
| P13 gravity | high | high | low while profile-only; veto package/service creep | medium adapter repetition | low now, high future debt |
| P27 duplication | high | medium/high | low with affected-owner review | medium | medium future islands |
| Operational burden | medium | low initially, high later | **low** | medium | low |
| Testability | qualified | strong syntax, weak semantics | **strong semantic fixtures** | strong adapter fixtures | weak cross-case |
| Reversibility | medium | medium once public | **high** | high | high |
| Disposition | reject owner role | reject now; future host candidate | **select semantic-owner role only** | **select current posture** | reject as complete answer |

Veto conditions apply to every model: no competent semantic governor; forced one-case/one-subject cardinality; unqualified tenant collisions; required rewrite of signed/CAS artifacts; relation/evidence/authority fields in the identity token; projection-owned minting; or a registry without a proved consumer chain.

## 7. Owner-Role Decision

### Functional owner

The ratified functional boundary is the PolicyOS identity/custody decision under architecture governance: PolicyOS owns honest attachment of its own custody records above one case. It does not own external institutional truth.

### Semantic owner

The semantic vocabulary/profile owner is `@architecture-owners` / `team-architecture`, acting through normal architecture review and affected-owner participation. This role governs only the meaning, equality limits, compatibility obligations, promotion gates and non-authorizations in this report.

### Issuer

No universal issuer is selected. PolicyOS-internal or tenant issuers may allocate values only under an explicit assigning-system policy. External official identifiers remain external aliases. Deterministic/content-derived generation is not identity adjudication; random generation is acceptable only inside a governed namespace. Federated assignment requires a future pilot and governance decision.

### Namespace governance

Each assigning system's competent governor owns allocation, collision, retirement and non-reuse. Architecture governance owns the compatibility rule that the assigning system must travel with the value and that local systems require qualification.

### Persistence and resolution

No registry or resolver is required. References may be embedded in owner-native artifacts; associations may later use sidecars, append-only records, owner-native events or projection mappings. Storage topology is deferred. A resolver, if later justified, is a projection of admitted mappings and must support historical cutoffs; it is not identity truth.

### Association and relation ownership

The producer that creates a case/claim/artifact/public record owns the correctness and correction of its association. Relation assertions belong to the family recording the assertion and its evidence. Competent external/legal adjudicators remain outside PolicyOS; PolicyOS admission and downstream claim reaction remain separate.

### Verification and projection

Runtime quality may verify profile conformance, qualification, collision, no-inference and cutoff behavior, but cannot issue or adjudicate references. Core artifacts preserve immutable bytes; core audit preserves actor/tenant/action history. Atlas/public surfaces project admitted references and privacy-safe public IDs without minting identity.

| Responsibility | Selected owner or status | Evidence | Rejected non-owner alternatives | Required review |
|---|---|---|---|---|
| Functional custody ownership | PolicyOS architecture boundary | Ratified identity/custody decision; amended Stage-0 | External registry, PDC alone | Architecture |
| Semantic vocabulary/profile | `@architecture-owners` / `team-architecture` | Cross-package ownership and ADR rules | PDC, `core.contracts`, runtime, Atlas | Affected package/security/audit/public owners |
| Shared code contract | **Unresolved; none selected** | No complete consumer/issuer/history chain | Premature PDC/core/new package | Separate ADR and import/public-surface review |
| Reference issuance | Owner-local under explicit assigning system; no global issuer | Existing owner-local ID practice | Architecture task, runtime quality, Atlas | Namespace owner + security |
| Namespace governance | Competent assigning-system governor; compatibility rules by architecture | PID/FHIR patterns; tenant fixtures | Consumer package | Architecture/security |
| Association production | Canonical producer of case/claim/artifact/public record | Family ownership | Central registry | Family owner |
| Association persistence | Deferred owner-native sidecar/event/store | Additive sidecar and audit precedents | Mandatory central registry | Family/storage owner |
| Resolution | Not required; future projection owner if proved | S-13/S-17 | Semantic owner or Atlas as truth | Architecture/audit/privacy |
| External alias admission | Integrating family plus admission owner | Lex/Data Forge source patterns | String matching | Source/claim owner |
| Identity-relation assertion | Family recording provenance-bearing assertion | PROV/RiC/DataCite patterns | Reference field | Family owner |
| Relation adjudication | Competent external/institutional authority; PolicyOS records admission only | Identity boundary | LLM, PDC, runtime | INT-R5/legal owner |
| Evidence-applicability reaction | Canonical evidence/claim owners; OPS-R2 | Stage-0 separation | Reference or relation owner | Evidence/claim owner |
| Verification | Runtime quality plus family semantic tests | Existing verifier role | Issuer | Runtime/family owners |
| Audit/history | Core audit plus owner-native history | ADR-0101, artifact/audit primitives | Resolver current view | Audit/storage owners |
| Public projection | Public-record owner/Atlas as consumer | Atlas constitution | Atlas as issuer | Privacy/public owners |
| Future H2 consumption | H2 may consume profile and associations only | Stage-0 handoff | H2 as owner/registry | Architecture + H2 owner |

## 8. Minimum Compatibility Profile

### Necessity derivation

The profile is semantic, not a DTO. A conforming reference comparison must receive:

- an opaque local value;
- its assigning system;
- sufficient enclosing qualification to prevent false equality under local/tenant/authority-scoped systems.

A conforming association must additionally identify the PolicyOS object, association role/scope, provenance/actor, and history coordinates required by its canonical owner. Those are not reference identity fields.

### Mandatory properties

1. `assigning_system` is explicit, stable or durably interpretable, governed against silent reuse, and preserved if retired.
2. `opaque_local_value` is compared only according to that system's rules; consumers do not parse semantics from it.
3. Qualification is explicit wherever system+value is not globally safe; matching tenant-local tokens across tenants are unequal by default.
4. Existing identifiers are never reinterpreted as custody-subject identifiers.
5. Equality has no authority, relation, applicability or lifecycle effect.
6. Associations are repeatable and scoped, preserving N:M cardinality.
7. Association/relation correction is append-only and cutoff-reconstructable without rewriting protected bytes.
8. Unknown or unresolved references fail closed for authority-dependent use.

### Context-carried properties

Tenant, authority/cell scope where already meaningful, issuer provenance, jurisdiction, association role, evidence source, transaction visibility, correction reason/actor, resolver metadata and public representation belong to enclosing owner-native records when needed. Context-carried does not mean optional for a use that needs them; it means they are not universal identity components.

### Explicitly excluded properties

The shared profile contains no status lattice, lifecycle state, evidence support, evidence applicability, claim authority, legal continuity, competent authority conclusion, jurisdictional truth, relation list, alias list, resolver URL, public URL, display name, created time, universal transaction time, subject-kind ontology, artifact hash, case ID, or storage location.

### Equality semantics

`same_reference` is true only when assigning systems are equal under their governed comparison, local values are equal under system rules, and qualification contexts are compatible. Different references may be asserted to concern one custody subject; one reference may later be related to successor references; neither changes token equality. Legal continuity and evidence applicability require separate competent evidence and owner decisions.

### Serialization posture without schema freeze

No URI/URN, tuple JSON, class, schema version, field names or package import is ratified. Adapters may serialize system+value as a tuple, qualified string, URI/URN, embedded object or owner-native mapping if round-trip preservation and equality rules are testable. Serialization must not hide tenant qualification, reinterpret retired namespaces, or make resolver availability part of identity.

## 9. Tenant, Federation, and Public Representation

### Collision prevention

Tenant is primarily an authority and isolation boundary, and conditionally an identity qualifier. It need not be embedded in globally governed references, but it must qualify local namespaces. Cell/authority domain is used only where an existing owner defines it. Jurisdiction remains authority/applicability evidence unless the external assigning system itself defines jurisdiction-qualified identifiers.

### Cross-tenant mappings

Cross-tenant collaboration uses explicit admitted mapping assertions with both qualified references, source/issuer evidence, purpose, actor, transaction visibility and correction history. A mapping may be candidate, admitted for a narrow purpose, disputed or corrected; this report creates no shared runtime relation-status lattice.

### External aliases

External aliases retain assigning system, value, issuer/source, tenant/import context, provenance and admission purpose. An unconfirmed assigning authority leaves the alias observed or quarantined. Matching aliases across tenants do not establish equality or evidence pooling.

### Public/private identifiers

Internal references are non-public by default. A governed public projection may use a separate random/non-enumerable identifier, an admitted official alias, or a stable public record handle. Its mapping is append-only and signature-bound where required. Public-ID rotation or correction preserves archived records and internal history.

### Resolver and namespace failure

Namespace retirement, issuer disappearance or resolver outage does not erase identity. Historical interpretation relies on retained assigning-system metadata, provenance and cutoff-visible mappings. Current resolver output is never substituted into an old decision replay. Duplicate allocation or collision triggers quarantine, new allocation/mapping and affected-claim review, not silent merge.

## 10. Correction and Migration Obligations

### Append-only associations

An association correction appends a new assertion that targets a stable prior assertion ID. The prior assertion remains visible at earlier cutoffs. The current projection chooses deterministically by transaction-visible order and stable tie-breaker; insertion order is not semantics.

### Historical replay

Replay must reconstruct which reference/mapping was visible and admitted at the decision cutoff, not today's resolver answer. OPS-R4 may later supply canonical temporal roles; this report requires only transaction-visible association history and exact cutoff semantics, not a universal event envelope.

### Alias and namespace correction

Retired namespaces are retained as historical assigning systems. Alias correction does not mutate the internal reference. Issuer replacement creates provenance-bearing mapping or governance succession; it does not silently transfer authority. Public ID replacement preserves old signed/public records and an explicit supersession mapping.

### No-rewrite migration posture

Adoption is `mapping-only` or `adoption-compatible` when new sidecars/associations can point to existing cases, claims and artifacts. It becomes `migration-required` only if a future ABI demands rewriting existing payloads; that posture is blocked by this report for signed/CAS artifacts. No current identifier is migrated or reinterpreted. Existing public records and decision-lineage keys remain unchanged.

## 11. Fixtures and Metamorphic Properties

### S-01–S-18

| Fixture | Setup and references | Required invariant | Prohibited result | Current primitive / missing capability / executability |
|---|---|---|---|---|
| S-01 Same external ID in two tenants | T1 and T2 ingest `PROGRAMME-17` under source-local system | No unqualified equality; explicit admitted federation mapping only | Cross-tenant pooling | Tenant/CAS isolation and source-local IDs; mapping owner missing; conceptual executable |
| S-02 One case, two subjects | One PDC covers two accountable interventions | Repeatable scoped associations; claim/evidence scope retained | Singular matter field or evidence union | PDC graph can model edges but no canonical subject edge; research-only |
| S-03 Several cases, one subject | Design, revalidation, incident and correction cases | One qualified reference may be associated with several cases without case equality | Reusing one `case_id` | Case IDs/PDC exist; above-case mapping missing; conceptual executable |
| S-04 Same name, different authority | Same display name/URL pattern; different mandates/populations | Similarity remains observation | Automatic merge | Anti-LLM/projection boundaries exist; identity verifier missing; research-only |
| S-05 Rename with continuation evidence | Name and agency change; competent continuation evidence | Relation/admitted mapping representable; reference alone proves nothing | Token equality as legal conclusion | Lex/provenance primitives; adjudicator external; research-only |
| S-06 Pilot scales nationally | Pilot and national programme related | Separate references/relations possible; evidence reviewed separately | Automatic evidence transport | Claim/applicability owners exist; relation bridge missing |
| S-07 Split | Parent becomes two accountable successors | Parent history retained; children separately referenceable | Copy all evidence/erase parent | Append-only lifecycle precedents; relation/adjudication missing |
| S-08 Merge | Two predecessors, one asserted successor | Predecessors retained; competent relation evidence | History collapse/evidence union | Same as S-07 |
| S-09 Repeal and reenactment | Similar legal text after repeal | Text/hash similarity does not establish sameness | Legal-document ID reused as subject | Lex document identity exists; continuity external |
| S-10 One subject, multiple instruments | Instruments change over time | Subject association distinct from instrument identity | Instrument change forces subject change | Lex source refs + mappings missing |
| S-11 One instrument, multiple subjects | One law governs several programmes | Instrument ID cannot be custody-subject ID | One law = one subject | Lex graph primitives; mapping missing |
| S-12 Signed artifact, wrong association | Valid bytes/signature associated to wrong subject | Integrity remains valid; append correction; claim review | Re-sign/rewrite original bytes | ArtifactID/signing/audit implemented; association sidecar missing; conceptual hash probe passed |
| S-13 Namespace retirement | External system disappears | Historical system/value/provenance remain interpretable | Resolver outage erases identity | Artifact/provenance storage patterns; namespace record missing |
| S-14 Public/private separation | Internal ref exposes tenant/sensitive subject | Separate governed public ID allowed; Atlas consumes only | Publish internal ref or Atlas minting | Projection authority boundaries; known redaction defect blocks production |
| S-15 Malicious split | Actor allocates new token to evade incident history | New token does not erase candidate predecessor relation or review duty | History detachment by allocation | Audit/claim lifecycle precedents; relation verifier missing |
| S-16 Adapter-local collision | Two adapters allocate `17` | Assigning system/qualification prevents equality | Raw-token equality | Source-local ID patterns; conceptual collision probe passed |
| S-17 Resolver current mapping changes | Current mapping differs from earlier decision | Earlier cutoff uses prior visible mapping | Current answer rewrites replay | Audit/OPS-R4-compatible cutoff; historical resolver absent; conceptual probe passed |
| S-18 Unresolved external alias | Source ID has unknown assigning authority | Observed/quarantined; no inheritance | Fail-open admission | Source/provenance fields exist; alias-admission owner missing |

### Metamorphic properties

The profile requires all of the following:

1. changing display name does not change reference equality;
2. changing URL does not change equality;
3. adding an alias does not change the internal reference;
4. matching aliases across tenants creates no equality;
5. changing qualification can change unqualified comparison behavior;
6. duplicating a case need not create a subject;
7. adding a second subject does not erase the first association;
8. changing a legal instrument does not automatically change the subject;
9. identical content hashes do not establish subject identity;
10. correcting an association does not change old artifact bytes;
11. resolver availability does not change historical identity;
12. similarity-score changes do not change authority;
13. reference equality does not increase evidence applicability;
14. a split does not delete parent history;
15. a merge does not delete predecessor history;
16. public-ID rotation does not rewrite internal history;
17. mapping insertion order does not alter a correctly cutoff current view;
18. lowering namespace/issuer certainty cannot increase authority;
19. current resolver output cannot replace historical cutoff-visible mapping;
20. an unresolved alias cannot move from observed to admitted without an explicit admission act.

### Executability classification

A temporary, uncommitted conceptual probe exercised collision, N:M associations, stable correction targeting, deterministic cutoff projection and artifact hash non-rewrite. The first design failed because corrections targeted insertion indexes; the second failed because equal-time insertion order affected projection. After requiring stable assertion IDs and deterministic tie-breaking, 18/18 probe properties passed. This is research evidence, not a production implementation. PDC, artifacts, audit, tenant and claim-lifecycle repository tests provide reusable patterns but do not prove a subject-reference capability.

## 12. P13 and P27 Review

| Model | P13 gravity risk | P27 duplicate-owner risk | Explicit veto |
|---|---|---|---|
| PDC-owned | Pulls identity, relation and lifecycle into case graph; creates non-PDC dependency | Pre-empts claim, artifact, Lex and future H2 owners | Veto semantic ownership; permit adapter edge only |
| `core.contracts` ABI | Shared DTO attracts issuer, status, provenance, public and lifecycle fields | Makes mechanical host appear semantic owner | Veto until ratified semantic owner and two real consumers |
| New package/service/registry | Becomes central identity/master-data gravity and migration source | Duplicates PDC/artifact/audit/Lex/Data Forge responsibilities | Veto package/service/registry now |
| Adapter-local + mappings | Repeated adapters and identity islands | May duplicate mapping logic | Accept only under shared profile and conformance fixtures |
| Governance-only profile | Low while implementation-neutral | Low if affected owners retain payload/lifecycle | Veto any expansion into issuer, store, status lattice or envelope |
| Case/fixture only | Low immediate gravity | Defers duplication into every family | Reject as complete posture; acceptable only in isolated fixtures |

The selected result avoids P13 by governing only equality, qualification, non-inference and promotion. It avoids P27 by leaving issuance, persistence, relations, evidence, legal evaluation, artifacts, audit and projection with existing/future competent owners.

## 13. Downstream Handoffs

### OPS-R2

May assume a stable semantic predicate for qualified reference equality and explicit scoped associations. Must not assume evidence inheritance, affected-set calculation, materiality, transportability, claim reaction or authority propagation.

### OPS-R4

May supply owner-native append-only temporal roles and historical cutoff semantics. Must not turn this profile into a universal event envelope or make one resolver response authoritative for all time.

### INT-R5

Must identify competent actors/evidence for continuation, split, merger, succession and transfer. S0-GAP-01 does not decide legal competence.

### PAO-R36 / INT-R7 / INT-R8 / Atlas

May assume internal/public identity separation and immutable historical mapping requirements. Must not let Atlas or a public route mint, merge or adjudicate identity; complete public correction, privacy, cache and cryptographic lifecycles remain downstream.

### OPS-R15 / S0-GAP-02

Fixtures may use qualified opaque subject references, N:M association graphs, separate relation assertions and no-rewrite correction invariants. They may not claim a production oracle, canonical package or executable registry.

### H2

H2 planning may assume a long-lived PolicyOS custody subject concept, system+value reference identity, explicit qualification, scoped associations, append-only correction and family-owned storage. It must not assume a field named `policy_matter_ref`, one-subject-per-case, a central registry/service, a shared API, public ID, resolver, legal continuity or evidence inheritance.

## 14. Promotion and Kill Rules

| Promotion state | Minimum evidence |
|---|---|
| Research-only semantic guidance | This report, reviewed against Stage-0 and owner boundaries |
| Accepted architecture input | Architecture-owner acceptance plus affected-owner review; no implementation claim |
| Prototype allowance | At least two independent family consumers; explicit issuer/namespace policy; tenant collision and N:M fixtures; sidecar/no-rewrite design |
| Production ABI | Ratified package ADR, import/public-surface review, versioning/migration policy, producer/consumer/verifier chain, semantic tests and rollback |
| Public identifier | Privacy threat model, non-enumeration/correlation tests, archive/signature binding, correction/rotation and projection ownership |
| Federated resolver | Real institutional pilot, governance/availability model, historical cutoff behavior, dispute/correction process and fail-closed semantics |

Promotion is killed if any of the following occurs: reference equality grants continuity, applicability or authority; one case is forced to one subject; tenants can collide; an alias becomes globally canonical without assigning-system basis; signed/CAS bytes must be rewritten; similarity mints identity; a projection creates/merges identity; the owner cannot govern consumers; package owner is confused with semantic owner; an existing owner is duplicated; a registry has no proved consumer need; public exposure leaks tenant/sensitive existence; relation state becomes a cross-product lattice; split/merge transports evidence; current resolver output rewrites replay; unresolved references fail open; or the design depends on unratified H2 architecture.

## 15. Open Questions

1. Which two real cross-family consumers first require a common mechanical type rather than adapters?
2. Which existing package, if any, can host that type without upward imports, public-surface expansion or semantic-owner confusion?
3. Which tenant or institution may issue internal custody references, and what allocation/non-reuse rules apply?
4. Is any current `cell_id` an authoritative domain qualifier, or should tenant plus assigning system remain sufficient for the first pilot?
5. Which owner persists association assertions and transaction visibility in the first pilot?
6. Which competent external evidence and reviewer admit continuation/split/merge relations for a declared purpose?
7. Which public use case proves a separate public identifier or resolver is necessary?
8. How should federation disputes and issuer disappearance be governed in a real multi-institution pilot?

## 16. Direct Answers

### Verification record

| Command or probe | Baseline | Result | Pass/failure/skip | Effect on conclusion |
|---|---|---|---|---|
| GitHub resolve/search branches and commits | Remote repository, 2026-07-29 | Current main `4813b49...`; amendment head `fd4e32b...`; branch created from exact head | Pass | Pins all findings |
| Compare `290725...` → `fd4e32...` | Amendment branch | Four commits ahead; only three Stage-0 docs changed as described | Pass | Task remains valid |
| Repository-wide identifier/reference search and targeted file reads | Historical/current main and amended research head | No implemented PolicyMatter; owner-local IDs and package boundaries confirmed | Pass | Rejects identifier-by-name reuse |
| Import/public-surface/ownership/ADR inspection | Pinned tree | PDC and `core.contracts` are not proved semantic owners; architecture review owns cross-package boundary decisions | Pass | Selects owner role, leaves package unresolved |
| Temporary conceptual probe `/tmp/s0_gap_01_probe.py` | Research model only | First two variants exposed unstable correction target and insertion-order tie; final 18/18 properties passed | Pass after two research corrections | Requires stable assertion IDs and deterministic cutoff projection |
| Local Markdown/frontmatter/reference validation | Final report | Required frontmatter/sections, 18 fixtures, 20 metamorphic properties and direct answers present; internal link/reference checks passed | Pass | Artifact ready for review |
| `git diff --check` on one-file synthetic staged diff | Final report only | Clean | Pass | No whitespace error |
| PAO-R0 audit: PDC compiler | Historical/current main | 4 passed | Inherited, not rerun here | Confirms graph/projection patterns only |
| PAO-R0 audit: PDC projection | Historical/current main | 37 passed | Inherited | Confirms projection cannot mint authority |
| PAO-R0 audit: targeted capability batch | Historical/current main | 54 passed, 1 reproducible public-export redaction failure | Inherited failure | Blocks public-ID promotion; does not change semantic owner |
| PAO-R0 audit: tenant CAS isolation | Historical/current main | 1 targeted cross-tenant test passed | Inherited | Reusable isolation pattern, not federation proof |
| PAO-R0 audit: PDC directory | Historical/current main | 122 passed, 1 shim-induced failure | Inherited limitation | No subject capability proved |
| PAO-R0 audit: signing/offline audit | Historical/current main | 3 passed | Inherited | Confirms byte integrity separation |
| PAO-R0 audit: runtime lineage | Historical/current main | Collection blocked by missing `jaxlib` | Blocked; not claimed passed | Runtime lineage remains unproved here |
| PAO-R0 audit: architecture gates | Historical/current main | 2 passed, 2 baseline failures | Inherited baseline debt | Reinforces need for package/import review |
| Broad unrelated suites | N/A | Not run | Intentional skip | Scope discipline |

Environment blockers are recorded honestly: the available container lacked an authenticated Git checkout and could not clone the repository over DNS; GitHub connector reads/writes were used for repository evidence and publication. Dynamic repository tests were not rerun and are labelled inherited from the independent PAO-R0 audit rather than claimed as S0-GAP-01 passes.

### Plain answers

| Question | Answer |
|---|---|
| Does PolicyOS need a reference above `case_id`? | Yes, as a semantic attachment concept; not yet as a shared typed/persisted ABI. |
| What exact object does it concern? | The opaque PolicyOS custody subject to which PolicyOS attaches its own justification-custody records. |
| Is PolicyMatter correct? | Provisional historical shorthand; unsafe if read as legal/administrative ontology. Prefer “PolicyOS custody subject.” |
| Does PolicyOS need a shared ABI now? | No. `shared_abi_not_yet_justified` is the ABI verdict inside the overall `accepted_profile_with_owner_role_only` result. |
| Could adapter-local references and mappings suffice? | Yes, now, if constrained by the shared semantic profile and explicit append-only mappings. |
| What is the minimum compatibility profile? | Assigning system + opaque local value; explicit qualification when needed; non-reinterpretation; authority non-inference; repeatable scoped associations; append-only correction. |
| Which properties are mandatory? | System, value, safe qualification, opaque comparison, no authority inference, N:M association compatibility, stable history and fail-closed unresolved use. |
| Which properties remain outside? | Status, lifecycle, relations, aliases, evidence support/applicability, claim authority, legal continuity, jurisdictional truth, provenance/time/public ID/resolver as universal identity fields. |
| Is a raw opaque token sufficient? | No. S-01 and S-16 produce false equality. |
| Is a namespace/assigning system necessary? | Yes. |
| Must tenant qualification be part of value or context? | It must be present when the assigning system is not globally safe; context is preferred over embedding. |
| Is jurisdiction part of identity or authority scope? | Authority/applicability scope or external-alias qualification, not intrinsic custody-subject identity. |
| Is subject kind necessary? | Not in the minimum profile; no concrete failure requires a frozen taxonomy. |
| Is a resolver necessary? | No. |
| Is a central registry necessary? | No; no consumer chain proves it. |
| What does equality prove? | Same local value under the same assigning system and compatible qualification. |
| What does it not prove? | Legal/institutional identity, continuity, competence, evidence applicability, claim authority, currentness, or permission to combine records. |
| Who is the ratified functional owner? | PolicyOS under the ratified architecture identity/custody boundary, limited to its own custody attachments. |
| Who should own the semantic vocabulary? | `@architecture-owners` / `team-architecture`, with affected-owner review. |
| Which package should own shared code? | None selected; package placement remains unresolved. |
| Who may issue references? | Owner-local PolicyOS/tenant issuers under an explicit assigning system; external authorities issue external aliases. No global issuer selected. |
| Who owns namespace governance? | The competent governor of each assigning system; architecture governs cross-system compatibility rules. |
| Who owns association production? | The canonical producer of the associated case, claim, artifact or public record. |
| Who owns association correction? | That association owner, using append-only owner-native history and audit. |
| Who owns relation adjudication? | Competent external/institutional authorities; PolicyOS owns only admission and record of its reliance. |
| Who owns evidence applicability? | Canonical evidence/claim owners and future OPS-R2 work. |
| Who owns public projection? | Public-record/Atlas projection owners as consumers, never identity issuers. |
| Is PDC the canonical semantic owner? | No; it is an integration neighborhood. |
| Is `core.contracts` the canonical semantic owner? | No; it may later host a mechanical ABI only after ratification. |
| Is a dedicated bounded owner justified? | A governance-only semantic owner role is justified; a new package/service/registry is not. |
| What role remains for runtime quality? | Conformance verification, collision/qualification checks, orchestration and diagnostics; no issuance or adjudication. |
| What role remains for core artifacts and audit? | Immutable byte identity, signatures, ownership isolation, append-only actor/tenant/action history and offline verification. |
| How are N:M cases represented? | Repeatable scoped association assertions/edges, not a singular field. |
| How are tenant collisions prevented? | Qualified equality: system+value plus tenant/authority context when required. |
| How are federated mappings admitted? | Explicit provenance-bearing, purpose-scoped, correctable mapping assertions with competent review. |
| How are aliases represented? | Separate qualified external-alias mappings preserving system, value, issuer/source, provenance and admission purpose. |
| How are incorrect associations corrected? | Append a correction targeting a stable assertion ID; retain actor, reason, prior assertion and cutoff visibility. |
| How is replay preserved? | Deterministic transaction-cutoff projection over append-only history; current resolution cannot rewrite the past. |
| Can signed/CAS artifacts remain unchanged? | Yes; this is a mandatory no-rewrite invariant. |
| Does adoption require migration? | No for the accepted posture; use mappings/sidecars. Any rewrite migration is blocked. |
| What may OPS-R2 assume? | Qualified reference equality and explicit scoped associations only. |
| What may OPS-R15 fixtures assume? | Fixture-local qualified refs, N:M graphs, separate relations and no-rewrite corrections. |
| What may H2 assume? | A long-lived custody-subject concept and this semantic profile, not storage/API/registry/package topology. |
| What must no downstream task assume? | Mandatory `policy_matter_ref`, one subject per case, legal continuity, evidence inheritance, central registry, public resolver, canonical package or production capability. |
| What would falsify the decision? | A real cross-family pilot proving adapters insufficient and identifying a competent issuer/package, or evidence that system+value cannot support required equality without a stronger minimal component. It is also falsified negatively if the profile cannot prevent tenant collision, authority inference or historical rewrite. |
| What is the final result type? | `accepted_profile_with_owner_role_only`. |

This is a bounded Stage-0 architecture-research decision prepared for owner and team-architecture review. It is not implementation approval, a final PolicyMatter contract, identity adjudication, legal certification, or production readiness.

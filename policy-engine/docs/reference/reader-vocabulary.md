---
search:
  boost: 1.2
---

# Reader Vocabulary and Search Routes

Owner: `@docs-owners`
Source of truth: `docs/index.md`, `docs/reference/index.md`,
`docs/explanation/architecture.md`,
`docs/reference/e02-documentation-snapshot.md`,
`docs/system-design-decisions/policyos-identity-and-custody-boundary.md`,
`docs/explanation/ir-design.md`, `docs/reference/ir/index.md`,
`docs/reference/api/auth-tenant-model.md`, `docs/reference/local-runtime-state.md`,
`docs/reference/fabric/lineage.md`,
`docs/reference/scientist/current-workflows.md`,
`docs/reference/foundry/index.md`,
`docs/reference/canonical-vocabulary-crosswalk.md`,
`docs/reference/contributor-start-here.md`, and
`docs/reference/documentation-verification.md`.
Related pages: [Documentation index](../index.md), [Reference index](index.md),
[Contributor Start Here](contributor-start-here.md), and
[Documentation Verification](documentation-verification.md).

This page is a non-normative reading aid. **English is the sole official language
of PolicyOS documentation.** This governs official reader-facing wording; it does
not promote a document, ratify a decision, or establish the truth of a claim.
Authority and evidence remain governed by each claim's designated source and
owner, the record's status, and its cited evidence. A historical or primary-source
English document does not become a current contract merely because it uses the
official language. If localized reading aids are added later, they should be
clearly marked as non-authoritative and link back to the English source; they
must not define a parallel contract or vocabulary.

Use the routes below to find the canonical page for a question. This page does
not create terms, statuses, API contracts, or implementation claims. For a
source-backed statement, follow the destination page's owner and evidence-level
notes, and check its source pin when present. A source pin records the revision
inspected; it does not prove that the page is current against later E02 work or
that cited tests ran.

## Acronym routes

| Query term | Reader cue | Canonical route |
| --- | --- | --- |
| `E02` | Integration handoff, evidence cuts, and reconciliation status. The label is not a claim that integration is complete. | [E02 documentation snapshot](e02-documentation-snapshot.md) |
| `IR` | Intermediate Representation: typed contracts and selected validation. A valid object does not establish semantic adequacy, admissibility, or publishability. | [IR reference](ir/index.md), then [IR design](../explanation/ir-design.md) |
| `JWT` | JSON Web Token: runtime authentication and tenant or cell routing behavior. | [Runtime auth and tenant model](api/auth-tenant-model.md) |
| `CAS` | Content-addressed storage and artifact-store behavior: stored bytes, manifests, and identity boundaries. A digest does not establish authorship or authority. | [Local runtime state](local-runtime-state.md), [CAS and Storage](operations/cas-storage.md), and [IR design](../explanation/ir-design.md) |

The [canonical vocabulary crosswalk](canonical-vocabulary-crosswalk.md) is the
only machine-backed crosswalk for the specific source vocabularies it names.
Use its scope and limitations rather than treating this reading aid as an
additional glossary or a general-purpose term registry.

## Ten search questions and expected destinations

These are English query prompts with the expected canonical destination. They
are a source-routing set for future search and reader reviews; they do not record
measured search ranking, human usability results, or a browser test.

| Search question | Expected destination | Why this is the first stop |
| --- | --- | --- |
| “Is PolicyOS end to end yet?” | [Documentation index](../index.md) | States the current end-to-end limitation and routes readers to the inspected component paths. |
| “What is the current E02 documentation status, and which source maps drifted?” | [E02 documentation snapshot](e02-documentation-snapshot.md) | Separates the evidence cuts and records the bounded source-drift comparison and re-review needs. |
| “Why is an LLM result or typed proposal still only a candidate?” | [Identity and custody boundary](../system-design-decisions/policyos-identity-and-custody-boundary.md) | Owns the ratified authority and signature boundary. |
| “What does IR validation prove, and what does it not prove?” | [IR design](../explanation/ir-design.md) | Distinguishes representation, structural validation, linking, admission, authority, and time semantics. |
| “Where are the runtime JWT, tenant, and cell-routing rules?” | [Runtime auth and tenant model](api/auth-tenant-model.md) | Describes the inspected middleware order, identity modes, routing, and authorization behavior. |
| “Does lineage automatically connect ingestion, claims, world facts, and queries?” | [Fabric lineage](fabric/lineage.md) | Describes the bounded captured path and explicitly names missing producer bridges. |
| “Which Scientist workflow currently hands off evidence, and where are its gaps?” | [Current Scientist workflows](scientist/current-workflows.md) | Maps the observed workflow paths and their unresolved evidence handoffs. |
| “What do Foundry compilation and simulation establish?” | [Foundry reference](foundry/index.md) | Routes to compile, execution, binding, and simulation boundaries without treating prediction as observed effect authority. |
| “Where are canonical source terms and candidate mappings maintained?” | [Canonical vocabulary crosswalk](canonical-vocabulary-crosswalk.md) | Points to the bounded machine reference and its source-specific limitations. |
| “How do I update a documentation page and choose checks?” | [Contributor Start Here](contributor-start-here.md), then [Documentation Verification](documentation-verification.md) | The contributor page routes the task; the verification contract explains command scope and what results establish. |

## Reading order when pages disagree

Start with the page that owns the question, then follow its `Source of truth`
and source-pin metadata to the implementation or ratified decision. Generated
references own generated inventories; manually maintained maps explain selected
behavior and its limits. A design decision describes intended boundaries, while
an implementation map describes what was inspected in its pinned source. Keep
those evidence roles separate when the wording differs, and send unresolved
conflicts to the listed owner rather than inferring that the newer-looking page
overrides the source owner.

# R13 red-team review: capture and custody

Review basis: final `policy-engine/_build/post-e02-r13-solutions-20261022/capture-proposal.json` (CAP-01–06), final `policy-engine/_build/post-e02-r13-solutions-20261022/custody-proposal.json` (LIF-01–05), the native rows in `policy-engine/docs/plans/active/post-e02-r9-unified-implementation/tasks.json`, and that plan's `solutions/README.md` plus `solutions/00-shared-decisions.md`. The assigned denominator is **11 task IDs**: six CAP and five LIF; it is not the 109-task plan denominator. Proposal JSON references below use the `task_solutions[task_id=…].field` selector; `capture-proposal.json` and `custody-proposal.json` refer to the full paths above. Native task references use `tasks[id=…].field` in the full `tasks.json` path above. Unless otherwise expanded, `PLAN` means `policy-engine/docs/plans/active/post-e02-r9-unified-implementation/` and `SRC` means `policy-engine/src/polisyos/`; `solutions/…` and `architecture/…` paths below are relative to `PLAN`.

This is a documentation-only review. I did not run tests, imports, builds, installs, or product execution, and I did not inspect protected data. Code observations mentioned below are bounded to the proposal's historical observation pin `dccea950845cda5b38f026e7770c07819d31f4d9`; they are not an accepted-source rebind. Primary protocol sources were checked for the narrow claims cited below. They establish only the documented external behavior, not PolicyOS implementation, rights, or custody.

## Findings

### RCC-01 — CAP-03 makes query-only raw persistence contradictory
**Severity: high. Task: CAP-03. Bucket: same declared P05/P32 copy-and-use boundary, one level deeper; not a new class.**

**References:** `capture-proposal.json` `CAP-03.preferred_solution` says “Keep bytes immutable in CAS”; `CAP-03.composition_contracts[3]` requires query-only raw bytes not persist in CAS and other sinks. Native `tasks.json` `CAP-03.positive` and `CAP-03.adversarial` require allowed derived output/receipt to remain usable while restricted raw bytes do not persist. The same boundary is explicit in `solutions/00-shared-decisions.md` §S06 ¶1 and `architecture/01-integration-boundaries.md:24`.

**Counterexample:** A selected query-only profile permits a derived result and minimal receipt but forbids retaining the source response body. Following the unconditional preferred solution writes that body into CAS, even though the composition contract rejects that sink.

**Smallest correction:** Scope CAS retention to profiles that authorize a managed raw copy. For query-only, do not create a raw CAS root; retain only the permitted result/receipt and binding evidence. If the claim requires unavailable raw bytes for replay, surface that as a replay limitation or refuse that claim.

**Remaining external input:** The selected source's raw/result/receipt permissions and the actual sink/custody inventory for the chosen profile. The proposal already recognizes these; the preferred path needs to obey the profile condition.

### RCC-02 — “Opaque query-binding digest” has no privacy semantics
**Severity: medium. Task: CAP-01. Bucket: same declared S06 minimization/P05/P32 class; not a new class.**

**References:** `capture-proposal.json` `CAP-01.implementation_steps[2]`, `composition_contracts[0]`, and `acceptance_discriminators[3]` require and expose an “opaque query-binding digest” without defining whether it is a raw deterministic hash, keyed token, or access-controlled reference. S06 says a source may prohibit revealing even a locator or hash.

**Counterexample:** A stable, unkeyed digest of a query drawn from a small set (for example, a known list of institution/policy questions) permits offline guesses and cross-recipient linkage. Calling it opaque does not prevent either. This is a conditional risk: the proposal does not say it must be unkeyed.

**Smallest correction:** Define the exposed binding as an access-controlled random reference or a scoped keyed MAC, with key/version and recipient/purpose separation as needed; keep any canonical query projection in its authorized protected store. Do not emit even that reference where the source profile prohibits locator/hash disclosure. A MAC is an option, not a universal required mechanism; [RFC 2104](https://www.rfc-editor.org/rfc/rfc2104.html) defines HMAC as a secret-key construction.

**Remaining external input:** Whether the source permits a reference, hash, or other receipt field to leave its boundary, and the approved logging/audience profile.

### RCC-03 — CAP-01 changes the native authorization alternative into a conjunction
**Severity: medium. Task: CAP-01. Bucket: same declared authority/gate-scope P38 class; not a new class.**

**References:** Native `tasks.json` `CAP-01.requires_other_mechanisms[0]` says query-disclosure authority resolves through the selected provider/source/use contract **or** accountable custodian evidence via its native verifier. The proposal's `CAP-01.genuine_external_inputs[1]` requires a selected search-provider contract **plus** accountable source/custodian permission, and the preferred path likewise names the source/custodian permission.

**Counterexample:** A public or caller-owned, nonsensitive query is sent to an already approved search provider under a provider/source/use contract that the native verifier determines is sufficient for that projection. A separate source custodian may not exist or have a relevant permission to grant. Requiring both inputs blocks a query that the native rule permits.

**Smallest correction:** Preserve the task's OR as alternative evidence paths for the native verifier. Require a separate provider logging/retention contract only when that is an independently applicable recipient constraint; do not require an unrelated custodian grant for every query. Unknown sensitivity, recipient, or authority still blocks egress. This is an overconstraint correction, not permission to infer public rights from caller labels.

**Remaining external input:** The actual query projection, competent authority for it, provider/logging terms, and selected recipient. Which evidence path suffices is a source/use-specific decision.

### RCC-04 — CAP-01 no-hit discriminator can suppress the request that establishes no-hit
**Severity: medium. Task: CAP-01. Bucket: same declared P38 predicate/proxy class; not a new class.**

**References:** Proposal `CAP-01.acceptance_discriminators[1]` says “no-hit” produces “no … live fetch.” Native `CAP-01.positive` requires an allowed minimal query to reach its admitted recipient, while native `CAP-01.adversarial` repeats the no-hit wording.

**Counterexample:** A permitted search query returns zero candidates. No-hit is known only after the search-provider call. A test interpreting “no live fetch” as “no provider request” cannot exercise the stated result and conflicts with the positive path; a test interpreting it as no later candidate-source fetch is coherent.

**Smallest correction:** Say explicitly: the exact query must first pass disclosure admission; if it returns no hits, persist a no-hit candidate receipt and perform no candidate/source fetch or admitted use. If disclosure admission fails, the provider and its logs receive no protected query. Because this ambiguity is inherited from the native task, update that discriminator too rather than making the proposal appear to repair it.

**Remaining external input:** Provider query/response and logging behavior for the selected search profile; no new legal authority is implied.

### RCC-05 — CAP-02 continuation rule rejects an explicitly permitted CDN hop
**Severity: medium. Task: CAP-02. Bucket: same AP05 recipient/transport boundary, not a new class.**

**References:** Proposal `CAP-02.implementation_steps[3]` accepts continuation only “within the admitted source origin and query.” Native AP05 in `policy-engine/docs/research/universal-policy-design/external-foundations/acquisition/05-implementation-and-review.md:60` allows a “permitted CDN bound,” while rejecting private/foreign hops without allowance. The selected task requires per-hop DNS/socket/proxy/credential policy, not literal same-origin equality. If “source origin” means a profile-approved set rather than the literal URL origin, the proposal should name that set.

**Counterexample:** A source profile explicitly admits a CDN origin for page continuation, but the proposal rejects it solely because it differs from the initial origin. [RFC 8288](https://www.rfc-editor.org/rfc/rfc8288.html) permits link targets expressed as URI references; that does not authorize following them, but it does not impose this product's same-origin rule either.

**Smallest correction:** Bind continuation targets to a source-profile allowlist of admitted origins/recipients, including any explicitly permitted CDN; validate each hop at DNS/socket/proxy boundaries and scope credentials to their audience. Continue to reject unlisted/private destinations and never trust an arbitrary page-supplied URL.

**Remaining external input:** The source's endpoint/CDN set, provider continuation semantics, and credential audience. The policy remains scoped to the selected source; no global network barrier follows.

### RCC-06 — CAP-02 collapses provider-valid overlap and conflicting replay into “duplicate page”
**Severity: medium. Task: CAP-02. Bucket: same declared P07 provider replay/completeness class; not a new class.**

**References:** Proposal `CAP-02.acceptance_discriminators[1]` treats a “duplicate page” as partial/unavailable without defining page identity or overlap. CAP-04's composition and acceptance explicitly allow provider-event replays to be idempotently reconciled. Native AP04 distinguishes repeated pages, missing pages, and stable snapshot semantics.

**Counterexample:** Microsoft Graph documents that the same entity can appear multiple times in a delta response and can appear anywhere in an `@odata.nextLink` sequence; clients are instructed to handle this in merge logic ([Microsoft Graph delta-query overview](https://learn.microsoft.com/graph/delta-query-overview)). A consumer that treats any repeated entity/overlap as an incomplete page rejects a provider-valid sequence. Separately, retrying an already persisted identical continuation receipt is an at-least-once replay, not automatically a conflicting new page.

**Smallest correction:** Define provider-specific identity and distinguish: (a) identical persisted token/page/root replay, which can be reconciled idempotently; (b) valid repeated entities/overlap, which follows the provider's merge semantics; and (c) conflicting reuse of a token/cut, no-progress cycles, or missing required pages, which remains partial/unavailable. The Graph behavior is an example for that provider class, not a universal rule.

**Remaining external input:** The selected provider's duplicate/overlap, cursor, snapshot, and reset semantics. A provider that does not define them cannot support a stronger completeness claim.

### RCC-07 — CAP-02 omits the task's selected LIF-08 second-source producer slice
**Severity: medium. Task: CAP-02. Bucket: existing producer/bridge scope omission (P01/P02); not a new class.**

**References:** Native `tasks.json` `CAP-02.deliverable` requires “the explicitly selected second-source producer sub-slice required by LIF-08” and says first-route completion does not cover a new page/range/parser behavior. Proposal `CAP-02.preferred_solution`, implementation steps, composition, and acceptance describe the selected bounded HTTP route and conditional pagination/range but never identify or accept that LIF-08 slice.

**Counterexample:** The first-route source passes the one-response test; a consumer then composes LIF-08 with a second source whose producer/receipt is not covered by that route. The solution's generic source-profile/free-grow statement does not identify the required producer or prove the sub-slice was accepted.

**Smallest correction:** Name the selected second-source producer sub-slice and its receipt/consumer contract, or state the exact generic profile conformance that satisfies it. Keep pagination/range/parser changes separately scoped as the task requires; do not make the first bounded route wait on an unrelated global mechanism.

**Remaining external input:** The selected source and its provider-native capture/completeness semantics if the LIF-08 slice needs them.

### RCC-08 — LIF-05 says “one existing rights/privacy owner” without binding the owner
**Severity: medium. Task: LIF-05. Bucket: same declared P27 owner-bypass/duplicate-owner class; not a new class.**

**References:** Proposal `LIF-05.preferred_solution` says “Extend one existing rights/privacy owner,” but `reuse_anchors` names request `AccessScope`, `RetentionPlanner`, artifact references, and storage readers without naming the canonical grant/revoke and AP07 composition decision owner. CAP-03/06 are told to consume “this same” owner, so this unresolved mapping determines whether the solution reuses or creates a second rights ledger. At the proposal's historical code pin, `SRC/core/security/access_scope.py:11-19` is request scope; `SRC/fabric/security/retention.py:64-97` records deletion impact and resolves retention defaults; `SRC/fabric/security/governed_artifacts.py:21-68` applies retention/encryption. `SRC/core/artifacts/ownership.py:1184-1187` describes public-read closure as owner-internal and conditional on separate ownership-root custody. These anchors do not prove no canonical rights owner exists.

**Counterexample:** An implementation treats `AccessScope` as the grant source or expands `RetentionPlanner` into a grant/disclosure authority to satisfy CAP. The pinned APIs describe different properties: AccessScope is per-request identity/scope; RetentionPlanner resolves retention/encryption defaults; governed-artifact resolution applies those outputs. None of those descriptions alone establishes source-use authority or AP07 composition. The proposal's own reuse note says retention planning is not physical purge proof.

**Smallest correction:** At accepted-source rebind, map the existing owners by responsibility: competent external rights evidence and verifier; one native source-use/AP07 decision/composition owner; local managed placement/write/delete/restore owners; and retention policy. Name the single canonical decision API CAP-03/06 consume. If no such owner exists, carry `absent/unallocated` or `bridge_missing` and provide an integration contract; do not place that authority in RetentionPlanner or create a private ledger. This is an owner-resolution gap, not proof that no owner exists.

**Remaining external input:** Actual grant/revocation authority and effective time; provider and backup placement/restore evidence. Owner resolution itself is an engineering rebind, not an external dependency.

### RCC-09 — README links to solution artifacts absent from the reviewed tree
**Severity: low. Scope: solutions README. Bucket: documentation accuracy; no product-class claim.**

**References:** `solutions/README.md:10,12` links `index.md`, `preferred-solutions.json`, and `sources.json`. The reviewed `solutions/` directory contains only `README.md` and `00-shared-decisions.md`.

**Counterexample:** A reader follows the documented execution path and cannot open the task index or the machine-readable recommendation/source records the README says to use.

**Smallest correction:** Either add those artifacts as part of this solution package or change the reader instructions to the files currently present. Do not leave the links looking like already-delivered artifacts.

**Remaining external input:** None.

## Candidates evaluated but not raised as findings

- **LIF-01 exact ArtifactRef-to-bytes:** `LIF-01.preferred_solution` and `implementation_steps[0]` are ambiguous, but not necessarily incompatible with query-only. If the exact referenced artifact is the authorized result/receipt (or source-native receipt), content resolution can be satisfied without retaining original raw bytes. Clarify that raw bytes are required only when the selected predicate needs them; otherwise admit the lawful receipt and preserve the replay limitation. Do not impose an exact-raw-byte prerequisite by implication.
- **LIF-02 signed cutoff:** The row already scopes evaluation/enrollment to source cut C and high-water W, requires source-supported continuity, rejects caller-asserted completeness for protected publication, and emits an explicit bounded cutoff. I found no separate barrier defect. Keep the signature as cutoff provenance/authenticity only; it does not itself establish completeness or currentness.
- **CAP-03/06 and shared AP07:** The design correctly keeps one LIF-05 composition owner, allows idempotent replay of the same permitted output to the same audience, and distinguishes a fresh draw/new recipient. The correction in RCC-01 is only to make raw persistence conditional.
- **Scheduling:** These findings concern specific selected profiles/owners. They do not require a global barrier and do not change R12 progressive rebind or conditional composition.

## Limits

The review examined the complete assigned set of 11 task IDs and both proposal files, but did not validate the full 109-task plan, accepted E02 tree, product behavior, or any selected deployment's external contracts. External documentation was used only to test narrow protocol claims: Graph's documented duplicate-entity behavior, RFC 8288 link target syntax, and RFC 2104 keyed-MAC semantics. None is evidence that PolicyOS implements the behavior or has the required rights. Product execution remains unrun.

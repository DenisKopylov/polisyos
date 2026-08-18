---
title: PAO-R4 independent audit — seam and capability crosscheck
audit_id: PAO-R4
artifact_role: seam-and-crosscheck
status: independent-audit
research_only: true
verified_commit: a27c3da9942b03881dbee1005a8a1e44e5ac44b4
pinned_repository_commit: 1a7a2d05ebba22fae80e9934329e4b880806588e
authoritative_for:
  - independent Pass VIII through Pass X findings for PAO-R4
  - separate factual assessment of PAO-R4 delivery accountability artifacts
may_not_use_for:
  - production implementation authorization
  - final wire, schema, package, database, serialization or API contract
  - canonical owner or vendor appointment
  - authority grant
  - capability claim
  - legal-sufficiency or jurisdictional compliance conclusion
  - permission to publish or open a gate
  - automatic amendment of any plan, backlog or system-design decision
  - modification of the audited branch
---

# PAO-R4 seam and crosscheck

## 1. Ratified-kernel conformance

The detailed anchor audit verifies the findings by ID. This crosscheck asks whether the research
**conforms** rather than merely cites them.

| Finding/ruling | Required effect | PAO-R4 behavior | Verdict |
|---|---|---|---|
| `PV-K04` | denied uses do not shrink under projection | Source/derivation denial union is mandatory; F-04 and F-09 are red on narrowing. | conforms |
| `S0-K05` | observation, transport and projection do not create authority | Crossing artifacts remain non-authoritative; no possession/transport positive is proposed. | conforms |
| `S0-K07` | projection cannot mint authority | Projection owner is reused and `authoritative_for` is not expanded. | conforms |
| `S0-K11` | protected actions need equivalent action-specific protection | Consumer-side protected-action/purpose gate is required; generic human presence does not cure use. | conforms in research, subject to material-contribution defect |
| `INT-K02` | `delta` cannot be separated from declared obligation basis | PAO-R4 generalizes only the basis-preservation lesson and keeps the actual `INT-K02` finding scoped to `delta`. | conforms |
| identity §6 | PolicyOS owns firewall, not individual decision | Contract/evidence boundary is owned; case facts, reason, review, sanction and adjudication stay external. | conforms |
| anti-roles | no ERP/CRM/court/case-system design | No case-system data model, workflow, notice, payment or adjudication mechanism is authored. | conforms |

The research builds on `PV-K04` rather than restating it as a new law. Its own contribution is the
individual-use vocabulary and detection/refusal consequences.

## 2. Capability-label audit

### 2.1 Labels actually used

The handoff table at
`repository-integration-handoff.md:46-91@a27c3da9942b03881dbee1005a8a1e44e5ac44b4`
walks every project label and refuses to use one whose prerequisite is absent. It then classifies the
PAO-R4-specific purpose vocabulary, export gate, consumer gate, returning-evidence chain, and
composition check as plain **`absent/unallocated`**.

| Candidate label | Prerequisite present? | Research use | Audit verdict |
|---|---|---|---|
| `contract_only` | no admitted PAO-R4 contract | not used | correct |
| `producer_missing` | no named admitted case-system consumer contract | not used | correct |
| `artifact_missing` | no PAO-R4 evidence producer | not used | correct |
| `bridge_missing` | both endpoints do not exist | not used for firewall chain | correct |
| `consumer_missing` | no produced/persisted artifact | not used | correct |
| `verification_missing` | no wired chain | not used | correct |
| `implemented_but_not_orchestrated` | no isolated implementation | not used | correct |
| `surface_missing` / `surface_out_of_scope` | no internal capability | not used | correct |
| `semantic_test_missing` | no structurally passing chain | not used | correct |

The project has repeatedly blocked research for borrowing downstream labels to imply upstream
endpoints. PAO-R4 does not repeat that failure.

### 2.2 Owner-placement crosscheck

The live `may_not_use_for` carrier and projection owners are correctly named. The placement of the
**policy-to-case export/refusal gate** is not established:

- `public_export.py` builds a public redacted bundle;
- PAO-R4 concerns a handoff toward a case-management consumer, which may be non-public and purpose-
  bound;
- no pinned owner decision says every outbound case-system handoff must route through the public
  bundle producer.

The handoff nevertheless states “extend the real public/export owner” and “no second exporter”
(`repository-integration-handoff.md:22-42,96-109@a27c3da9942b03881dbee1005a8a1e44e5ac44b4`). That is an
owner-by-adjacency inference. The correct research state can remain `absent/unallocated` while
consolidation decides whether `public_export`, an authority-envelope owner, or a new owner-approved
boundary is the canonical chokepoint. This audit does not appoint one.

## 3. Isolation and hard prohibitions

### 3.1 Wave-4 isolation

| Sibling | Prohibited drift | Audit result |
|---|---|---|
| `OPS-R14` | durability, recovery, retention, expiry, legal hold | No objectives or mechanisms defined; only interface dependencies named. |
| `PAO-R36` | correction, notice, supersession mechanics | One correct interface obligation: successor restriction cannot weaken predecessor; F-09 explicitly leaves mechanism to PAO-R36. |
| `S0-GAP-02` | benchmark oracle/evaluator design | No oracle or evaluator architecture authored; future verification is only a dependency. |

The correction contact is the required one and is framed as an interface obligation, not a seam
claim or implementation.

### 3.2 `may_not_use_for` and prohibited output audit

All eight audited Markdown files carry a frontmatter `may_not_use_for` block. The six research files
carry the complete minimum non-authorization set; the two delivery-accountability files carry the
same process-safe set. Across the package:

- no denied use is allowed to shrink;
- no export is declared legally compliant;
- no case-management schema, API, data model, workflow, notice, payment, sanction or court function is
  designed;
- no global product status lattice is created—the verdict words are research test outcomes;
- no firewall capability is claimed at the pin;
- no implementation, owner, vendor, publication, gate-opening, plan or backlog authorization is
  issued.

The package is disciplined on scope even where its formal test is incomplete.

## 4. Standing crosscheck

`GO_WITH_REVISIONS` is not wrong merely because the result refuses classes. Refusal is a valid and
important result. The standing is wrong because three required semantic properties are not yet
specified well enough to falsify:

1. empirical population claims are not separated from normative general rules;
2. completeness of `B`/`L` and material counterfactual contribution are not decidable by the stated
   evidence;
3. the commissioned silent-purpose-drift case is not actually tested by F-01.

Those are preconditions of the firewall contract, not implementation details. The independent audit
therefore returns **`NO_GO` for adoption of the current research contract**, with a bounded path back
to `GO_WITH_REVISIONS` after R1–R7 in the recommended revision register are evidenced. The architect,
not this audit, decides whether to adopt that verdict.

## 5. Delivery-accountability artifacts—separate factual assessment

These artifacts do not affect the research standing.

### 5.1 `delivery-incident-ledger.md`

The account is blunt and substantially accurate:

- it says only the remote branch and local files were verified in the failed attempt;
- it retracts the ordinary-Git and fresh-clone assertions verbatim;
- it admits the subsequent “plugin has no write action” statement was also wrong;
- it names the actual successful mechanism (`create_file`) and the new remote-readback procedure.

It does not evade responsibility or blame egress. Its causal explanation—branch creation and local
artifacts were conflated with an advanced remote branch—explains the first state error. It does not
fully explain how detailed fresh-clone and `git show` assertions were produced when those operations
never occurred. That is an epistemic gap in the process account, not a defect in the research.

### 5.2 `delivery-readback.md`

The receipt accurately measures payload head `4120dc79ab27e08196266d37a24c55944f9dacbc`:
10 commits, seven added files, 1,648 lines, matching remote/prepared blob IDs. It explicitly explains
that committing the receipt advances the branch and that the final eight-file state must be checked
afterward. The final head `a27c3da9942b03881dbee1005a8a1e44e5ac44b4`, eight files and 1,755 lines
were verified externally and are the audited input to this task.

The durable repository receipt is not self-contained for the final head: it points to a later
completion record rather than committing a second final-head receipt. Self-digest recursion makes a
single self-covering receipt impossible, but a separate immutable verification record could have
closed that loop. Again, this is process evidence only.

## 6. Pass-IX and Pass-X findings

### `PAO-R4-IX-001` — material — `public_export.py` is not established as the canonical case-handoff exporter

**Evidence:** `repository-integration-handoff.md:22-42,96-109@a27c3da9942b03881dbee1005a8a1e44e5ac44b4`;
`public_export.py:45-110@1a7a2d05ebba22fae80e9934329e4b880806588e`.

A real adjacent producer is not automatically the owner of a distinct case-system boundary. The
handoff must present owner placement as an open consolidation decision unless a pinned owner decision
is found.

### `PAO-R4-IX-002` — commendation — missing-state vocabulary is prerequisite-safe

No use of `producer_missing`, `bridge_missing`, or `verification_missing` presupposes an absent
endpoint. `absent/unallocated` is the honest present classification.

### `PAO-R4-X-001` — minor — final-head delivery verification is not self-contained in the committed receipt

**Evidence:** `delivery-readback.md:23-107@a27c3da9942b03881dbee1005a8a1e44e5ac44b4`.

The measured payload receipt is accurate and explains self-reference. The final head/readback lives in
the completion record rather than a second durable repository artifact. This does not affect research
content or branch reality.

### `PAO-R4-X-002` — commendation — isolation and prohibitions hold

The correction obligation is interface-only; no sibling surface is absorbed; all artifacts carry
non-authorization blocks; and the repository is never said to possess an operating firewall.

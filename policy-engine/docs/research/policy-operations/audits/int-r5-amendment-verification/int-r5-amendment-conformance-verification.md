---
title: "INT-R5 — Stage 4 amendment conformance verification"
verification_id: INT-R5-AMENDMENT-VERIFY
stage: amendment_verification
amendment_head_verified: 70f2db6d3a4330664c981721a9305f16bffe369b
audit_head: 247f89f016f71ee603ed76ef6dbb6403f7e651a0
package_head: 02e203de90d51280d569e7f641a158569ae4df39
base_main: dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f
verdict: CONFORMS_WITH_GAPS
research_standing: accepted_narrow_scope
capability_standing: absent/unallocated
gate_standing: NO_GO
---

# INT-R5 Amendment Conformance Verification

## 1. Scope and pins

This Stage 4 pass asks only whether the Stage 3 amendment closed the Stage 2 findings. It does not
improve the package, decide open legal questions, appoint an owner, or authorize implementation.

Every repository statement below is a **GitHub connector observation** pinned to amendment commit
`70f2db6d3a4330664c981721a9305f16bffe369b`, unless a verification-branch receipt explicitly names a
later SHA. The governing instrument is
`audits/int-r5/int-r5-recommended-revision.md`, especially §§2–5. Repository search-index results were
not used to settle any zero.

Initial containment used GitHub `compare_commits`. For each base `X` and verification head `Y`,
`merge_base_commit.sha == X` and `behind_by == 0`; this is exactly equivalent to
`git merge-base --is-ancestor X Y` exiting `0`.

## 2. Verdict vector

```yaml
verdict: CONFORMS_WITH_GAPS
delivery_and_containment: conforms
disposition_reconciliation: conforms
stage_contract_conformance: conforms
finding_closure: 17 closed / 1 partially_closed / 0 not_closed / 0 not_assessable
commendation_preservation: 9 of 9 preserved
lift_conditions: 7 of 9 met
no_go_conditions: 0 of 9 triggered
disclosure_accuracy: branch delivery conforms; Stage-3 conversational hand-back is inaccurate
conditional_post_revision_GO: not_granted
research_standing: accepted_narrow_scope
capability_standing: absent/unallocated
gate_standing: NO_GO
```

The only substantive closure gap is `INT-R5-A-005`: exact survey identities and bytes were
independently resolved, but the branch alone does not supply a third-party retrievable archive or all
source passages needed for full replay.

## 3. Finding closure table

| Finding | Severity | Claimed disposition | Audit closure criterion | Package file(s) and amended line range | Closed? |
|---|---|---|---|---|---|
| `INT-R5-A-001` | material | `accepted` | Permit unchanged histories; replace universal inequality with two-history non-inferability. | `int-r5-decision-authority-validity.md:297-318`; `int-r5/decision-authority-specification.md:76-113`; `int-r5/external-evidence-ledger.md:189-210` | **closed** — equality is expressly allowed and the surviving “theorem” occurrence says the result is *not* a theorem. |
| `INT-R5-A-002` | material | `accepted` | State acquisition is DS20-only and name the absent PA2/DS9 bridge/consumer. | main `83-101,180-193,569-580`; `int-r5/repository-baseline.md:140-179,236-272`; fixtures `433-465` | **closed** — pinned route and service recheck matches the amended topology. |
| `INT-R5-A-003` | material | `accepted_with_variation` | Derive a complete closure **or narrow the denominator and withdraw repository-wide zeroes**. | main `153-179,204-232`; baseline `1-31,54-82,180-219,273-284` | **closed** — ten files are a selected slice; six negatives are slice non-observations, not repository zeroes. The separate §5.1 complete-denominator lift condition remains unmet. |
| `INT-R5-A-004` | material | `accepted` | Name independent producers for time/effect/profile fields; hashing must not establish semantics. | main `331-351`; specification `114-155,245-332`; fixtures `98-164,357-403` | **closed** — producer, verifier, requester control and fail-closed mutation are explicit. |
| `INT-R5-A-005` | material | `accepted_with_variation` | A branch-only reader must identify exact surveys, verify bytes or durable archive identity, and locate every load-bearing source passage. | `int-r5/survey-source-manifest.md:1-173`; external ledger `1-40,285-295`; main `244-253` | **partially_closed** — identities, denominators and hashes are genuine, but `file_…` is connector-private rather than a durable branch locator; §4 contains paraphrased extracts and omits several load-bearing ranges. |
| `INT-R5-A-006` | material | `accepted` | Namespace/version local reasons, define crosswalk ownership, prevent negative upgrade. | main `393-404`; specification `493-532`; fixtures `1-38` | **closed** — candidate IDs are `polisyos.int_r5.reason.<slug>@0.1.0-candidate`; eval-safety stale is a sibling, not an alias. |
| `INT-R5-A-007` | material | `accepted` | Require PAO-R4 as a conditional conjunct and prove non-substitution in both directions. | main `130-150,569-580`; specification `16-75`; fixtures `404-432` | **closed**. |
| `INT-R5-A-008` | minor | `accepted` | Cure output must state temporal legal effect without mutating historical certificate. | main `421-434`; specification `559-594`; fixtures `283-356`; external ledger `89-123` | **closed** — prospective, relation-back, saved-act, limited and unresolved are represented. |
| `INT-R5-A-009` | minor | `accepted` | Separate two closure violations from DS20 feed drift and acquisition integration. | main `62-82`; baseline `32-53` | **closed**. |
| `INT-R5-A-C01` | commendation | `accepted` | Preserve honest delivery/evidence-class reporting. | main `1-45`; manifest `1-17` | **closed** — branch text is bounded; the inaccurate conversational hand-back is graded separately. |
| `INT-R5-A-C02` | commendation | `accepted` | Preserve named measurement holder and rejection of search-index zeroes. | main `153-179`; baseline `1-31,273-284` | **closed**. |
| `INT-R5-A-C03` | commendation | `accepted` | Preserve 34/34 parity and classify 33 as historical drift. | main `194-203`; baseline `120-139` | **closed**. |
| `INT-R5-A-C04` | commendation | `accepted` | Preserve bounded conflict claim; never disprove hidden/off-system conflict. | main `365-380`; specification `400-451`; external ledger `161-188` | **closed**. |
| `INT-R5-A-C05` | commendation | `accepted` | Preserve profile-relative forum, quorum, presence, vote and cure. | main `351-365`; fixtures `220-282`; external ledger `124-160` | **closed**. |
| `INT-R5-A-C06` | commendation | `accepted` | Preserve red-first fixtures, near-passes and mutation families. | main `435-461`; fixtures `1-534` | **closed**. |
| `INT-R5-A-C07` | commendation | `accepted` | Preserve typed missing-holder result without borrowed authority or disabled demo lane. | main `405-420`; specification `533-558`; fixtures `466-475` | **closed**. |
| `INT-R5-A-C08` | commendation | `accepted` | Preserve PAO-R4 ownership and conceptual non-substitution. | main `130-150`; specification `16-75`; fixtures `404-432` | **closed**. |
| `INT-R5-A-C09` | commendation | `accepted` | Preserve immutable replay and no fictional rollback. | main `421-434`; specification `446-463,559-594`; fixtures `283-356,480-490` | **closed**. |

## 4. Verdict-lift conditions from audit §5.1

- [x] All seven material and two minor findings are explicitly dispositioned.
- [x] Revisions occur in package files, not only in `amendment-ledger.md`.
- [x] Severity arithmetic is row-based and closes: `0 + 7 + 2 + 9 = 18`.
- [x] Corrected acquisition topology was rechecked at the amendment pin.
- [ ] A complete executable/authority denominator was independently rerun. The amendment deliberately
      chose the audit-permitted narrow-slice alternative; that closes A-003 but not this stricter GO lift.
- [ ] Source-manifest anchors resolve for **branch-only** independent replay. Exact external objects
      resolved through the private Files connector, not from the branch alone, and passage coverage is incomplete.
- [x] Producer walk covers every decisive field named by A-004.
- [x] PAO-R4 two-direction negatives are specified.
- [x] All nine commendation properties survive.

Result: **7/9 met. Conditional post-revision `GO` is not granted.**

## 5. Conditions that force `NO_GO` from audit §5.2

- [ ] Acquisition adjacency is presented as a live institutional call edge — **not triggered**.
- [ ] Universal check/use inequality remains — **not triggered**.
- [ ] The ten-file sample is still called complete — **not triggered**.
- [ ] Caller-selected time/effect/profile becomes decisive through hashing — **not triggered**.
- [ ] Branch replay is asserted with no source identities — **not triggered**; identities exist and
      hashes verify, while accessibility/passage coverage is reported as an A-005 gap.
- [ ] A second global lattice or unmapped bare duplicate codes is introduced — **not triggered**.
- [ ] PAO-R4 is absorbed or weakened — **not triggered**.
- [ ] Relation-back is universally denied — **not triggered**.
- [ ] Capability or gate standing is upgraded — **not triggered**.

Result: **0/9 triggered.**

## 6. Stage-contract conformance

Pipeline §3.3 defines a closed amendment vocabulary:
`accepted`, `accepted_with_variation`, `declined_with_reason`. The amendment ledger contains 18 unique
rows and uses only those values:

```text
accepted                 16
accepted_with_variation   2  (A-003, A-005)
declined_with_reason      0
total                    18
```

Pipeline §2 topology holds: the verification branch descends from the exact amendment head, which
descends from the audit and package heads. The audit/package/base compare predicates were exact
ancestor predicates, not approximations. The amendment delta touched seven Markdown paths: five
package modifications and two additions; no audit artifact, source, workflow, binary, `AGENTS.md` or
pattern register changed.

## 7. Findings and residual band

### Finding `INT-R5-V-001` — A-005 remains partially closed

The five manifest IDs, titles, line counts, byte counts and SHA-256 values were independently resolved
and matched. This proves content binding in the authenticated Files environment. It does not make a
`file_…` identity a durable branch-accessible archive. A branch-only reader also receives paraphrased
extracts rather than the exact passages, and §4 omits portions of four §3 anchor families:
`S1:382-409`, `S3:136-178`, `S4:377-550`, and `S5:172-236`. Those ranges contain substantive cure,
transaction-level SoD, revocation/checkpoint and act-type-degradation evidence.

### Disclosure axis

The branch delivery is stronger than the Stage-3 conversational hand-back. The branch has seven changed
paths, dispositions `16/2/0`, and reason namespace
`polisyos.int_r5.reason.<slug>@0.1.0-candidate`. The hand-back reported six paths, `17/1/0`, and a
different namespace. These reporting errors neither remove delivered work nor earn closure.

### Residuals not treated as defects

- Full repository closure and runtime implementation were not claimed and were not verified.
- Legal sufficiency in any jurisdiction was not evaluated.
- No institutional holder, adjudicator, signer or owner was appointed.
- The recursive Git tree response was connector-clamped before its `truncated` field could be observed;
  no denominator or zero relies on that response.
- A commit cannot contain its own final SHA without changing that SHA. Inline receipts therefore bind
  the amendment pin and verification-content heads; the exact branch tip is reported by the final
  post-write connector readback.

## 8. Connector observations

At amendment pin `70f2db6d3a4330664c981721a9305f16bffe369b`:

- GitHub `compare_commits`: amendment/audit/package/base are exact ancestors of the verification branch.
- GitHub Contents API: `services/control/` contains 15 Python files and no child directory.
- GitHub raw-file reads plus full-response scans: `HumanDecisionService` occurs in **0/15** files.
- GitHub `fetch_file`: `routes/control.py::ingest_data` uses the DS20 authorization and step-up
  dependencies and calls `run_data_ingestion`.
- GitHub `fetch_file`: `run_data_ingestion` dispatches connector/Fabric ingestion and contains no PA2,
  human-decision, currentness or custody gate.
- Files connector: all five manifest external IDs resolved; their exact byte lengths and SHA-256 values
  matched the committed manifest.

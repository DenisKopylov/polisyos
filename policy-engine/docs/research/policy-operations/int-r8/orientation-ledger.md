---
title: "INT-R8 orientation ledger — compression loss and disclosure composition"
research_id: INT-R8
artifact_role: orientation-ledger
status: accepted_narrow_scope
research_only: true
repository: DenisKopylov/polisyos
baseline_ref: main
baseline_commit: 02c5b8d23c757c92b9231e6e1e802d5701588908
prepared_at: 2026-08-04
may_not_use_for:
  - production_implementation_authorization
  - final_wire_schema_package_database_serialization_or_api_contract
  - canonical_owner_appointment
  - authority_grant
  - capability_claim
  - benchmark_passage
  - legal_compliance_or_institutional_competence_conclusion
  - permission_to_publish_a_governed_result
  - automatic_amendment_of_any_plan_or_system_design_decision
  - signature_algorithm_or_key_policy_selection
  - numeric_disclosure_bound
---

# INT-R8 orientation ledger

## 1. Audit scope and method

This ledger records Pass I of INT-R8. It verifies the orientation facts supplied in the commission against the exact Git object `02c5b8d23c757c92b9231e6e1e802d5701588908`. No repository statement below is inferred from a moving branch. The GitHub exact-ref interface was used because ordinary outbound Git/GitHub DNS was unavailable in the execution environment. The research branch was created from the exact commit, not from the then-current textual name `main`.

Set-level claims use complete-set denominators. For the two largest set claims, the complete result was partitioned into disjoint paths so that connector page limits could not silently turn a sample into a denominator:

- `may_not_use_for`: `runtime` (67 files) + `scientist` (12 files) + all remaining `policy-engine/src/polisyos` paths excluding those two disjoint roots (27 files) = **106/106 Python files returned by the complete exact-token census**;
- `build_public_export_bundle` production-source presence: the complete `policy-engine/src` token-containing set is **2/2 files** — the definition and the `runtime/quality/__init__.py` re-export. Tooling and tests contain invocations, but no `runtime/http` binding exists.

The pinned repository itself defines P35 as the prohibition on sampled-denominator generalization and P36 as the prohibition on authority by adjacency; this audit applies those findings by ID and not by nearby prose (`policy-engine/docs/reference/policy-design-case-failure-patterns.md:170-260`).

## 2. Orientation findings

| ID | Supplied fact | Independent result | Evidence at pinned commit | Consequence for INT-R8 |
|---|---|---|---|---|
| OR-001 | `projection_semantics.py` is 3,763 lines. | **Confirmed.** The final executable/export line is line 3,763. | `policy-engine/src/polisyos/runtime/quality/projection_semantics.py:3758-3763` | Treat it as a substantial canonical substrate, not a seed to replace. |
| OR-002 | The named omission, redaction, gap, limitation, contest, recourse, participation, visibility, invariant and audit helpers exist. | **Confirmed.** The projection builder invokes the named helpers and keeps the projection explicitly non-authoritative. | `policy-engine/src/polisyos/runtime/quality/projection_semantics.py:80-760` | `CompressionLossReceipt` must extend this owner and reuse its identifiers. |
| OR-003 | Four audiences are canonical. | **Confirmed exactly:** `PUBLIC`, `REVIEWER`, `EXPERT`, `MACHINE`. | `policy-engine/src/polisyos/runtime/quality/projection_semantics.py:648-655` | No fifth audience is admissible in this research. |
| OR-004 | Per-projection consumer contracts S9-S14 and authority-laundering checks already exist. | **Confirmed.** The verifier family rejects projection-specific hidden blockers, missing omissions, contested-state loss and authority laundering. S14 additionally checks hidden/gold payload. | `policy-engine/src/polisyos/runtime/quality/projection_semantics.py:760-2400`; `:1900-2250` | INT-R8 adds material-loss and transcript composition checks; it does not duplicate S9-S14. |
| OR-005 | `_s14_contains_hidden_or_gold_payload` exists. | **Confirmed.** It participates in the S14 issue path. | `policy-engine/src/polisyos/runtime/quality/projection_semantics.py:1900-2250` | Hidden held-out content remains a pre-existing per-view firewall; cross-view reconstruction is the missing delta. |
| OR-006 | `public_export.py` is 2,103 lines. | **Confirmed.** | `policy-engine/src/polisyos/runtime/quality/public_export.py:2098-2103` | The export producer is mature enough to consume a loss verdict but does not currently produce one. |
| OR-007 | Public export already manifests omitted claims and canonical redaction reasons. | **Confirmed.** `_assert_public_claim_omissions_manifested` compares omitted IDs found recursively in artifacts to claim IDs in the projection omission manifest; `_canonical_redaction_reason` emits three canonical scanner-derived reasons. | `policy-engine/src/polisyos/runtime/quality/public_export.py:1691-1875`; `:300-650` | Existing omission and redaction metadata are reused. Materiality, class of loss and cross-release effect are new. |
| OR-008 | Public export already has candidate-firewall and replay-drift gates. | **Confirmed.** | `policy-engine/src/polisyos/runtime/quality/public_export.py:1760-1970` | New checks must compose with these gates, not bypass them. |
| OR-009 | Exact public-export token census: `omitted_claim` 8; `projection_faithfulness` 13; `redaction_reason` 2; `omissions_manifested` 2; `lossy`, `blocked_material`, `compression`, `retained_limitation` 0. | **Confirmed by exact-literal scan of the complete 2,103-line file.** Denominator: one complete file, 2,103 lines. | `policy-engine/src/polisyos/runtime/quality/public_export.py:1-2103` | The measured delta is loss typing and composition, not omission discovery. |
| OR-010 | `build_public_export_bundle` has no HTTP caller. | **Confirmed with qualification.** Within `policy-engine/src`, the complete token-containing set is 2/2 files: `public_export.py` and `runtime/quality/__init__.py`. Tests and an operations runner call it, but no `runtime/http` path does. | `policy-engine/src/polisyos/runtime/quality/public_export.py:1-650`; `policy-engine/src/polisyos/runtime/quality/__init__.py:900-1150` | Producer present; surface binding is `bridge_missing`, not `producer_missing`. |
| OR-011 | No disclosure-budget owner exists in source. | **Confirmed.** Complete searches of `policy-engine/src` for `disclosure_budget`, `composition_budget`, `privacy_budget`, `compression_loss`, and `CompressionLoss` return zero source files. | Complete exact-token source-tree census at the pinned commit. | A scalar budget cannot be treated as latent infrastructure. |
| OR-012 | `CompressionLoss` appears nowhere. | **Qualified.** It appears in research/planning prose, including the planned GY-PA3 entry, but in **zero source files**. | `policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:2300-2400`; complete `policy-engine/src` census | The planned producer is not a present capability. |
| OR-013 | `may_not_use_for` is live and occurs in 106 Python files. | **Confirmed: 106/106 files in the complete exact-token census.** Disjoint partition: runtime 67, scientist 12, remainder 27. The set includes the three examples named in the commission. | `policy-engine/src/polisyos/core/contracts/runtime.py`; `policy-engine/src/polisyos/core/contracts/rule_evolution.py`; `policy-engine/src/polisyos/evidence/portfolio/conflict_records.py`; complete census | Denied-use is a first-class retained semantic, never optional prose. |
| OR-014 | The frontend publication packet is 1,214 lines and is consumed by the public viewer. | **Confirmed.** The viewer decodes and renders that packet through `PublicationPacketPanel`. | `policy-engine/apps/runtime-dashboard/src/features/runs/domain/publicationPacket.ts:1208-1214`; `policy-engine/apps/runtime-dashboard/src/features/runs/routes/PublicDecisionViewerPage.tsx:1-65` | The packet is a rendering consumer and current compression point, never the semantic owner. |
| OR-015 | Frontend compression currently drops semantics without a receipt. | **Confirmed and sharpened.** The packet preserves only a narrow projection subset; `publicText` truncates to 320 characters, `publicRef` to 96, deterministic explanations cap metrics with `slice(0, 4)`, and `buildProjectionSemantics` does not carry the existing omission manifest, redaction summary, projection gaps, contested records, recourse pointer, participation surface, deficit register or audit refs. | `policy-engine/apps/runtime-dashboard/src/features/runs/domain/publicationPacket.ts:336-460`; `:621-735`; `:889-1018` | This is the de facto unreceipted editorial-compression comparator. It is not evidence that every current packet is materially false; it is evidence that material loss is not detectable from the packet contract. |
| OR-016 | The deep link embeds the packet. | **Confirmed.** `signPublicDecisionPacket` serializes the packet, base64url-encodes it and places the payload in `/public/decisions/{signedId}`; verification is client-side. | `policy-engine/apps/runtime-dashboard/src/features/runs/domain/publicationPacket.ts:1019-1214` | URL, browser history, referrer, logs, screenshots and copied links are disclosure channels and must enter the transcript threat model. Proof construction remains INT-R7's scope. |
| OR-017 | Atlas DS12, DS13 and DS14 consume the result; DS12 gates the first public record on INT-R8. | **Confirmed.** DS12 retains the packet only as a rendering view model and names INT-R1, INT-R9, INT-R7 and INT-R8 as pre-publication research inputs; DS13 owns accountability-history surfaces; DS14 consumes compression-loss work. | `policy-engine/docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md:1100-1800` | INT-R8 is a binding research input, not an implementation or plan amendment. |
| OR-018 | The Atlas reconnaissance Publication row says no authoritative public-record producer/verifier exists. | **Confirmed.** | `policy-engine/docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md:175-260` | Frontend integrity cues cannot satisfy INT-R7 or INT-R8. |
| OR-019 | GY-PA3 is the planned compression-loss producer and G6 has no compression ledger. | **Confirmed as plan text, not capability.** The entry names the desired receipt and red-first conditions and says to reuse `projection_semantics` and `public_export`. | `policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:2300-2400` | Reality label remains `producer_missing`; INT-R8 defines semantics before that producer may close. |
| OR-020 | The two ratification records are 264 and 379 lines and change the task. | **Confirmed.** The authority-band lens is in the Stage-0 record; INT-K02, K04, K05, K06, K07 and K08 are in the INT-wave record. | `policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:35-92,258-264`; `policy-engine/docs/system-design-decisions/int-wave-claim-semantics-ratification.md:77-245,373-379` | Bare `delta` and hidden negative terminals are categorical blocked omissions; a no-number custody claim is a first-class compression target; current numeric composition is not justified. |

## 3. Public-export census detail

### 3.1 Exact literal census

The complete-file denominator is `public_export.py` at 2,103 lines. Counts are case-sensitive literal occurrences, not semantic aliases:

| Literal | Count | Interpretation |
|---|---:|---|
| `omitted_claim` | 8 | Omitted-claim discovery and manifest enforcement exist. |
| `projection_faithfulness` | 13 | S9 faithfulness is already integrated. |
| `redaction_reason` | 2 | Canonical redaction reason production exists. |
| `omissions_manifested` | 2 | The fail-closed omission-manifest assertion exists and is called. |
| `lossy` | 0 | No safe-loss outcome exists. |
| `blocked_material` | 0 | No material-omission outcome exists. |
| `compression` | 0 | No compression semantic exists in this owner. |
| `retained_limitation` | 0 | No explicit retained-limitation accounting exists. |

The census supports a narrow gap statement only: `public_export.py` can detect some silent omitted-claim IDs, but cannot classify whether loss is materially safe, account for limitations/attacks/denied uses/counterevidence as retained versus dropped, or compose several releases.

### 3.2 Caller census

The source-tree denominator is every file below `policy-engine/src`. Exactly two source files contain `build_public_export_bundle`:

1. `policy-engine/src/polisyos/runtime/quality/public_export.py` — definition;
2. `policy-engine/src/polisyos/runtime/quality/__init__.py` — re-export.

Calls in tests and `policy-engine/tools/ops_runners/runtime/canary_evidence.py` prove test/operations use, not an HTTP publication surface. No `policy-engine/src/polisyos/runtime/http/**` caller exists. Therefore the reality statement is exactly:

- public-export producer: present;
- HTTP/public-surface binding: `bridge_missing`;
- compression-loss receipt producer: `producer_missing`;
- material-loss verifier: `verification_missing`;
- required mutation and cross-view tests: `semantic_test_missing`.

## 4. Frontend compression delta

The current packet is safer than an unconstrained free-form summary in several respects: it carries explicit non-authority framing, preserves projection `may_not_be_used_for`, masks a limited set of textual patterns, presents an argument map, and rejects malformed client packets. Those strengths must survive consolidation.

The packet nevertheless cannot establish semantic parity:

1. `buildDecisionSummary` maps a larger decision view into `runId`, `verdict`, `confidence`, `generatedAt`, a headline and one already-authored `policySummary` (`publicationPacket.ts:410-445`). It has no retained/dropped inventory.
2. `publicText` and `publicRef` perform length truncation after pattern replacement (`publicationPacket.ts:354-409`). A qualifier after the cut point can disappear without a typed omission.
3. `buildDeterministicExplanations` uses only the first four metrics (`publicationPacket.ts:621-735`). There is no materiality test for later metrics.
4. `buildProjectionSemantics` copies authority role, closeout truth, display states, evidence class, time, denied uses, policy, provenance kind and surface, but not the canonical omission, gap, contest, recourse, limitation and audit structures (`publicationPacket.ts:889-956`).
5. The model-card limitation sentence says restricted notes, raw values and embargoed evidence are excluded, but does not identify affected claim IDs, category, disposition or semantic effect (`publicationPacket.ts:735-840`).
6. The deep link contains the serialized packet itself (`publicationPacket.ts:1019-1165`). This makes the URL a disclosure artifact; it does not by itself prove a private leak, but it invalidates any threat model that analyzes only visible DOM text.
7. `packetContainsPrivateContext` searches five string needles (`publicationPacket.ts:1195-1214`). It is a narrow heuristic, not a complete privacy or cross-view proof.

These are not findings that the frontend should become an authority owner. They establish why the future receipt must be produced upstream and merely rendered downstream.

## 5. Ratified constraints applied by ID

- **S0-K07:** a projection cannot mint authority. The receipt classifies content loss; it does not confer publication or closeout authority.
- **INT-K02:** a `delta` claim without its declared obligation set, maintained assumptions and relative-basis rider is a different false claim. Dropping that basis is always `blocked_material_omission`.
- **INT-K04:** a number over several events requires prospectively fixed local bounds and owner-reproducible membership, chronology, current heads and assumptions.
- **INT-K05:** there is one confidence owner and no parent scope or second confidence ledger. A disclosure quantity, if later justified, must be distinct and must not shadow confidence authority.
- **INT-K06:** a falsifiable procedural custody claim may carry no probability. INT-R8 uses this as the present composition alternative.
- **INT-K07:** adaptive event selection needs a valid guarantee for the actually history-selected mechanism and a pathwise bound.
- **INT-K08:** refusal, void, dispute, terminal no-attempt and exhaustion are completed governed outcomes. Compression may not turn their absence of a positive result into silence.

Primary source: `policy-engine/docs/system-design-decisions/int-wave-claim-semantics-ratification.md:77-245`.

## 6. Orientation verdict

No supplied fact was false in a way that changes the commission. Two qualifications matter:

1. “zero `CompressionLoss` files” is true for `policy-engine/src`, not for the whole repository, because plans already name GY-PA3;
2. “two callers” is true for the production source surface; tests and tooling also invoke the function, while no HTTP caller exists.

The verified architecture delta is therefore:

> PolicyOS already has canonical four-audience projections, omission manifests, canonical scanner reasons, authority-laundering checks, candidate firewalls and public-export construction. It does not have a producer or verifier for typed material compression loss, does not analyze the union and temporal transcript of releases, and has no owner or theorem for a numeric repeated-disclosure budget.

## 7. Hostile-audit reproduction recipe

The following is a reproduction recipe for an auditor with an exact checkout. It is included to make the denominator explicit; it is not an implementation authorization.

```bash
git checkout --detach 02c5b8d23c757c92b9231e6e1e802d5701588908
wc -l \
  policy-engine/src/polisyos/runtime/quality/projection_semantics.py \
  policy-engine/src/polisyos/runtime/quality/public_export.py \
  policy-engine/apps/runtime-dashboard/src/features/runs/domain/publicationPacket.ts \
  policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md \
  policy-engine/docs/system-design-decisions/int-wave-claim-semantics-ratification.md

python - <<'PY'
from pathlib import Path

root = Path("policy-engine/src")
public_export = root / "polisyos/runtime/quality/public_export.py"
text = public_export.read_text(encoding="utf-8")
for token in (
    "omitted_claim",
    "projection_faithfulness",
    "redaction_reason",
    "omissions_manifested",
    "lossy",
    "blocked_material",
    "compression",
    "retained_limitation",
):
    print(token, text.count(token))

python_files = sorted((root / "polisyos").rglob("*.py"))
may_not_files = [
    path for path in python_files
    if "may_not_use_for" in path.read_text(encoding="utf-8")
]
print("may_not_use_for_files", len(may_not_files), "denominator", len(python_files))

caller_files = [
    path for path in sorted(root.rglob("*.py"))
    if "build_public_export_bundle" in path.read_text(encoding="utf-8")
]
print("source_token_files", len(caller_files))
for path in caller_files:
    print(path)

for token in (
    "disclosure_budget",
    "composition_budget",
    "privacy_budget",
    "compression_loss",
    "CompressionLoss",
):
    hits = [
        path for path in sorted(root.rglob("*"))
        if path.is_file() and token in path.read_text(encoding="utf-8", errors="ignore")
    ]
    print(token, len(hits))
PY
```

The intended audit comparison is against the counts and qualifications above, not against an unpinned future branch.

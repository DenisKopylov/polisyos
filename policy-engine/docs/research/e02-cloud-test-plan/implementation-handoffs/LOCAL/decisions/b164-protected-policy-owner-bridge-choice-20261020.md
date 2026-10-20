# B164 Level 6: G architecture-choice packet (R2)

**Status:** revised author packet responding to the independent HOLD. This is a request for a narrow G architecture choice only. It is not G adjudication, source acceptance, issuer appointment, permit issuance, or production permission. B164 remains held; production permission and production revocation/currentness remain `not_established`.

## Decision requested from G

Given the current Level 6 boundary, choose one architecture disposition:

**A — Keep protected L6 promotion out of scope until an actual owner contract is supplied.** Preserve `bridge_missing` for any protected effect. Candidate evaluation and source-custody work may continue with the unknown carried forward; this does not ban exploration or candidate outputs.

**B — Authorize a bounded, costed integration design to reuse or minimally extend an existing external owner contract at that owner’s real writer.** The design is limited to the existing L6 path and must specify its cost, exact owner-contract surface, and bounded migration before implementation. If the owner contract or required evidence is absent, malformed, stale, or unverifiable, the behavior remains `bridge_missing`. This option does not appoint an owner, create an issuer, create a PolicyOS-owned permission/writer, or authorize any production positive.

No response or a deferred decision leaves the present state unchanged: B164 held, protected L6 effect blocked with `bridge_missing`, candidate work allowed. The choice is about whether to authorize the bounded integration design in B; it is not a vote on external facts.

### External evidence G cannot invent

The following are not questions for G to answer by architectural judgment. They must come from the authentic permission/write owner before a production bridge can be designed or admitted: owner and issuer identity/appointment; the existing purpose-bound permit reference/schema and signature-verification basis; independently owned verifier and currentness/revocation source; candidate/run/ticket/action/purpose/policy-version subject binding; the actual effectful target, prepared payload, and effect oracle; and the owner’s transaction/serialization protocol that makes revocation and the final check atomic with the write. A G choice cannot supply or imply any of these.

## Evidence and limits retained from R1

The original B164 criterion requires mode/operation checks before effect and a real write owner to recheck generation, current authority, and constraints at commit (`source/B_r19_original.md`, lines 4201–4212). The reviewed route currently returns `defer_to_human` / `bridge_missing` when an admitted promotion result is absent; the configured coordinator does not commit the autotune champion pointer. Existing source custody, HTTP caller roles, agent-action delegation, and verifier appointments have different purposes and do not provide a candidate/run-bound L6 permit or the owner’s commit-time revocation fence.

The retained local prototype is a negative/mechanics witness only. It shows a configured local source signature can establish source custody while promotion authority stays `not_established`, and L6 remains `bridge_missing` with zero runner effects. A separate in-memory revocation fixture sharing the `ChampionRegistry` lock can refuse a direct pointer-write probe; it is not the L6 policy writer, a production issuer, or an external revocation source. Do not select `ChampionRegistry` as the policy writer from this result.

The historical D record’s selected direction is an owner-issued typed permit with independent currentness verification and a final check serialized at the actual writer; it explicitly says the issuer/verifier API is not appointed and to fail closed with `bridge_missing` until then. This is a D design direction, not evidence that an owner/API exists and not G closure. The bounded C05 evidence update likewise says B164 remains held and G closure not adjudicated. Its adjacent EvalSafety finding remains separate and is not folded into B164.

The prior C11 limitation is retained: a terminal `promotion_result` mapping is not evidence of a committed protected effect. Widen only if a consumer is shown to interpret that mapping as authority.

## If G selects B: bounded follow-on and falsifier

Only after the owner supplies the listed evidence, freeze the exact owner contract and the real L6 write route. Prefer reuse of that contract; extend only the adapter/commit boundary required to bind the owner’s subject and currentness at its actual serialized writer. Keep legacy booleans, callbacks, and prepared-payload history non-authoritative/read-only. Do not design a new sovereign permission subsystem or public schema before the real contract is known.

The deciding test must call the actual owner-backed writer and inspect its durable consumer effect: one valid, independently verified, current permit produces only its specifically authorized effect; absent, fake, wrong-issuer, wrong-subject/run/ticket/action, expired, stale-generation, or revoked-before-commit permits produce zero effects while truthy legacy markers remain present. The verifier/revocation check and the effect must share the owner’s real commit linearization boundary. Until this test and the owner evidence exist, the capability is not closed and no production positive may be claimed.

## Binding, current status, and patterns

The reviewed R1 packet is bound to HEAD `10a9e80e47a3623cc271fcb9db0a7007e3ebadec`, tree `9c9c37014ffe86051839bda93dc64306807ffa11`. The independent review is bound to `cbd061390e4867befa5ef85af83ccde6639fa57a`, tree `c902d76fbeeea6d1c39680558d39444e6bcfdbca`, and returns HOLD. The current observed source frame is branch `codex/e02-unified-local-20261009`, HEAD `3a16ebfb87f11ae8bd95d55e36ce9e8f67ef351c`, parent `cbd061390e4867befa5ef85af83ccde6639fa57a`, tree `88f3b0698f892e9c82fc8ada52f24f903426449d`. The root journal records that candidate/tree and `G_acceptance=false`, `closure_ids=[]`, `source_freeze=false`.

Pathwise readback of the original packet’s 19 source pins found all 19 current filesystem bytes still match: 17 tracked source pins match both current HEAD blobs and worktree bytes; two local evidence inputs match their pinned bytes but are not in HEAD. The only tracked worktree modifications observed were `policy-engine/tests/unit/runtime/quality/test_generation_cycle.py` and `policy-engine/tests/unit/scientist/search/funnel/test_orchestrator.py`; neither belongs to those 19 pins. This is a B164-scoped binding, not a claim that the full checkout is clean or frozen.

The governing boundary is Stage-0 S0-K04 (external acts remain external), S0-K05 (no authority by observation, transport, or projection), and S0-K06 (fail closed on protected action while candidate work may proceed with an explicit unknown); the identity decision’s four-way test classifies a validity-changing external function as INTEGRATE through our typed evidence contract, or otherwise OUT_OF_SCOPE. Relevant failure/repair patterns are P05, P31, P32, P37, P38, P40, and P41. This review is the same B164 owner-permission class one level deeper, not a new boolean-gate instance: do not open another local gate round; widen only when a real owner contract and writer exist.

Current capability labels remain: `producer_missing` (promotion-purpose permission), `artifact_missing` (persisted typed permit), `verification_missing` (independent promotion-purpose currentness/revocation), `bridge_missing` (L6 to named protected writer), `consumer_missing`, `surface_missing`, and `semantic_test_missing` for the real owner-backed positive/revoked-before-commit property.

## Exact source references

- R1 packet and manifest: `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/b164-l6-owner-permit-bridge-prototype-r1-20261020/decision-packet.md` SHA-256 `e1d548b2e7ea0b8ec789d1309d76531e35d946997223d070328b3a2c235f9a2c`; `manifest-v2.json` SHA-256 `e197725438de9ce629693cccb59e2159684105e7e64f8ca95166a2c6739aa05d`.
- Independent HOLD: `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/b108-g-decision-packet-independent-review-20261020-r1/b164-review.json` SHA-256 `0bebdfec5d747f6fbec780ac9b39ac3b5563797b89f38c153a9c4e89454c3847`; its `manifest.json` SHA-256 `9903bf62b7d951fc04732bd93797b1bd4357e47d5cd19095efc1b35570a47fff`.
- Historical B164 D choice: `policy-engine/docs/research/e02-cloud-test-plan/closure-decisions/D.md`, lines 203–221, current HEAD blob `d659d75f03d8bbd126a845bb7b66d854730e2ad1`, file SHA-256 `06841343da151a210d00462b58b99985f9366a0330801586be7be2e9137551c2`.
- Held minimum owner input: `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/D/recovery-20261008/B164-minimum-owner-input.json`, file SHA-256 `8f650bdd0891f8f6f41ff602c2251a941a3ce8aa089989cea39438ae9ed77bf4`.
- Stage-0 ratification: `policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md`, S0-K04/K05/K06, current HEAD blob `6397ec2b9ba043c742f096813a0229418721fbfb`, file SHA-256 `a8410cddf3e2c8b7f4c194d06d0c38523fb64634f247e6baf96dfd6359197ea7`.
- Identity/custody boundary: `policy-engine/docs/system-design-decisions/policyos-identity-and-custody-boundary.md`, §5, current HEAD blob `873198b24d7fe8edf204be44374d20c9256cd24e`, file SHA-256 `f9b3776032e88190ac8d29f60d9623450f4d734e163cc16ae53f49b0f2a77bce`.
- Original B164 criterion: `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/B_r19_original.md`, lines 4201–4212, blob `d800082eebfc12eaf647b0c0257c4f06e135d25a`, file SHA-256 `9c98584cbfa72996b058abf127f6c689f919a3421cdd563a82c84a7324ab39b5`.
- B164/C05 author evidence update: `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/decisions/b164-current-l6-bridge-c05-composition-20261015.md`, SHA-256 `74e029ed109fd93c5a0141f07c7e6ec042a0cb4b65b9da1b7408fcdf1be2466f`; it remains an untracked local evidence input.
- Source-frame journal: `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/root-known-source-frame-journal-20261019/frames.jsonl` SHA-256 `8e099bd69dc1ecd012d456fb2b408db88d9330b8bcaf82a8980de1b141154b7a`; latest entry SHA-256 `e3a740668b75cb02b64996d393000ffd1661d83361b7e83cbad404fda593e914`.

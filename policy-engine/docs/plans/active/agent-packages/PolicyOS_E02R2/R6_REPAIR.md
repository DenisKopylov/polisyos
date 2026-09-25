# R6 — foreign-context N5 world identity

**Property.** N5 may use the active context's world-model record for a
candidate-unbound resolution only when the resolution is valid and bound to
that exact context, problem, candidate and world content. A valid context
alone never repairs a failed candidate binding. A genuine same-context
refusal remains eligible for candidate-grade `simulation_pending_n5`.

**Production route.** `RecursiveGenerationCycleController.route` creates the
generation controller and its default `JointSimulationPort`. In the
request-missing branch, `_boundary_world_model_record` resolves the active
candidate against the context. The prior catch block revalidated only the
enclosing context after that resolution failed and reattached its world-model
record. Status projection then treated record presence as permission to
continue. R6 removes this fallback; the original typed
`world_identity_unresolved` diagnostic remains and the simulation stays
blocked. It uses the existing identity resolver rather than creating a
parallel owner.

| Witness | Result | Receipt |
| --- | --- | --- |
| Test-first: same-context control and foreign, missing, malformed negatives | 1 pass, 3 fail on the unrepaired implementation | `/Users/deniskopylov/.codex/scratch/e02-r6-foreign-context-20260925/R6-test-first-red.junit.xml@sha256:36be0656744f20d53b66990f6c67ff0b1571b6b0472661342b3cb3fe3c79761b` |
| Repaired focused group | 4 pass / 4 | `/Users/deniskopylov/.codex/scratch/e02-r6-foreign-context-20260925/R6-restored-four.junit.xml@sha256:4a8705967978899957fbec2b226b190753f409e23e6673c12c862f687932405d` |
| Marker-preserving removal of the failed-binding guard | same-context control passes; all three negatives turn red | `/Users/deniskopylov/.codex/scratch/e02-r6-foreign-context-20260925/R6-removal-probe.junit.xml@sha256:28b1d9f7985134790277703bf45506f26e4e389db56cb6fd77d699154e1867b3` |
| Exact-parent whole-file replay, 103 shared tests | zero pass→fail, four fail→pass, two new tests pass | `/Users/deniskopylov/.codex/scratch/e02-r6-foreign-context-20260925/R6-exact-parent-full-diff.json@sha256:d1929995c0834aa453db1ba26ab32a6061c40d28a5edf91c2b2a397a1555de01`; parent JUnit `/Users/deniskopylov/.codex/scratch/e02-r6-foreign-context-20260925/R3-parent-full.junit.xml@sha256:fd70f1fef200f6c0d348a22ab4c12ffb6c1dacfd4a02bfdf8f5e9ec2c18a16c2`, R6 JUnit `/Users/deniskopylov/.codex/scratch/e02-r6-foreign-context-20260925/R6-current-full.junit.xml@sha256:e75d29a5020769cff4da76cdf2146f0002db31e304d7b46d95860b20c7c63174` |

The removal mutant was reversed after its run. The repaired source hash before
and after the probe is identical:
`policy-engine/src/polisyos/runtime/quality/generation_cycle.py@sha256:82ae8a716984b63d634372951ebd8af8048109ad05bd6f25184323b2c713187d`.
The original foreign-context case passes on the execution base and main, then
fails on E02 and Phase 0. The complete-file JUnits are:

- Execution base: `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/raw/p41-custom-20260924T224937Z-20241/cells/e02_execution_base/test_generation_cycle-3cf6fe052862.junit.xml@sha256:fe589600ed09509caa7bf0dcdd1c26c30a923fee611784cef481e922a46b711e`.
- E02 head: `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/raw/p41-custom-20260924T224937Z-20241/cells/e02_head/test_generation_cycle-3cf6fe052862.junit.xml@sha256:9910c0bf5e1190c1fb832a43ef011880ca73bf52753a4c33d0b37a2c18f6df4d`.
- Main: `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/raw/p41-20260924T084614Z-77175/cells/main/test_generation_cycle.junit.xml@sha256:57ac434bef63674628bd8019e0d7e8fc0f5f2f323a459c7e05fc0fab5829d9ad`.
- Phase 0: `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/raw/p41-custom-20260924T224937Z-20241/cells/phase0_merge/test_generation_cycle-3cf6fe052862.junit.xml@sha256:8a3b792073f37f4ac6a4546854e26e07038ddde65ee143f860034552ecc62cac`.

**P37/P38.** The exact candidate-context relation is recomputed by
`resolve_candidate_lever_world_identity`. The old implementation tested the
cheaper fact that the context itself was valid and then inferred candidate
identity from the presence of a world record. The divergent case is a
content-valid refusal from another context: its own context is valid, but it
cannot shape the active world. The negative, its absent and malformed
siblings, and the same-context control exercise both sides of the boundary.

Independent runtime review:
`/Users/deniskopylov/.codex/scratch/e02-r6-foreign-context-20260925/R6_INDEPENDENT_RUNTIME_REVIEW.md@sha256:e85a91b185bb239c0e5ecf57ec74d65443e63ea9f2cefc95bb360de6f9ba2d50`
(GO before whole-file replay).
Final independent review after whole-file replay:
`/Users/deniskopylov/.codex/scratch/e02-r6-foreign-context-20260925/R6_FINAL_INDEPENDENT_REVIEW.md@sha256:ead9739629a76136df54f4ff43e653bf27e7982e651a47d457005c5c3ebb5c42`
(GO for this bounded commit). Its caution about the post-N9 derived summaries
is resolved by distinguishing their baselines: the exact-parent diff does not
list this test because it fails at both R3 and R6; the Phase-0-to-R6 diff does
list it because it passes at Phase 0. All three JUnits establish those states.

**Attribution and limits.** The exact parent file at R3 commit `79fac987e`
has 103 tests: 92 pass, 11 fail. R6 has 105 tests: 98 pass, 7 fail. The
`test_post_n9_packet_binds_exact_subject_and_gate_receipt` case passed at
Phase 0 but fails already on R3's parent of R6, even with the R6 source
temporarily reversed. That exact probe is
`/Users/deniskopylov/.codex/scratch/e02-r6-foreign-context-20260925/R3-parent-post-n9-probe.junit.xml@sha256:5a2ddd6d1d80da4eb7d705b69c0612cea8829055d90916c7891ced4ca9ff93fb`.
It is a new R3/N9 scope-seam red, not an R6 red; the R4 candidate's focused
diagnostic pass is pending final integration evidence. The R6 source was
restored byte-exactly after the parent replay. Ruff reports three unchanged
diagnostics in `generation_cycle.py` and one unchanged diagnostic in its test,
with zero new findings against exact parent:
`/Users/deniskopylov/.codex/scratch/e02-r6-foreign-context-20260925/R6-ruff-head-diff.json@sha256:f136fdc4ee1a112e6bc2e6e4cd6d654e1f2f904c7221918a338585cec777c960`.

The final four-base post-repair replay remains open. R6 does not claim to
establish the separate R13 world-growth admission or N7 tenant custody.

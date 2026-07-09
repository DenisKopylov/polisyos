# GY-N10a Second-Domain Pack Design

## Goal

Prove or falsify data-only free growth for a second, non-Ukraine-economics
domain. The deliverable is owner-derived evidence, not an asserted capability:
all committed pack facts must be re-derived from DCAT, the scholar KG, the
existing S0 builder, or a real N6 run.

## Measured decision

The census queries health, education, and environment/energy-transition.
Health is ineligible because every measured outcome satisfies N8's panel
threshold. Education is the selected domain because it has the strongest L1
coverage among eligible candidates (1,165,054 observations / 3,244 datasets)
and three non-panel variables (`school_quality`, `years_of_schooling`, and
`stem_graduates`), while L2 still has 438 causal claims, 1,962 parameter
estimates, 422 transport scores, and owner-derived education intervention
concepts. Environment/energy-transition remains a measured runner-up.

## Architecture

One data-only builder/validator owns five generated artifacts: a census, pack
manifest, strict `DesignProblem`, N6 terminal trace, and free-grow-gap report.
It reads L1 and L2 in read-only mode through the existing substrate-path owner,
calls the existing S0 registry builder, and runs the existing N6 controller.
All generated JSON is canonically serialized and content-addressed. Runtime
timings are reported by the command result rather than frozen into artifacts,
preserving byte stability.

The pack contains L1 outcome and context facts plus L2 grounding and candidate
lever facts. It deliberately does not create a second registry or hand-write
an S0/L6 lever row. Existing N7 only synthesizes in-memory registrations and
does not persist raw evidence or rederive a registration from L2/L3; CG3 is
shadow-only; and default N4/N5 ignore persisted free-grown inputs. These are
typed gaps, not implementation targets in GY-N10a.

## Failure-pattern pass

- Relevant: P01, P02, P03, P05, P07, P10, P12, P27, P29, P31, P32, P33.
- Existing anti-patterns: synthesized N7 registrations, shadow-only CG3 patch,
  fixed Ukraine L6/WMR intake, and a N6 one-terminal validator mismatch.
- Target pattern: owner query/response hash -> content-addressed artifact ->
  rederive audit -> typed gap or typed N6 terminal.
- Missing labels: `artifact_missing`, `bridge_missing`,
  `producer_missing`, `receipt_persistence_missing`, and
  `semantic_test_missing` where applicable.
- Acceptance: a rederive audit reconstructs all pack facts from owners; a
  hand-authored entry, first-vertical contamination, crash/mismatch trace, or
  engine-code diff is red.

## Scope boundaries

No `src/polisyos/**` changes are permitted. A local ignored owner-data mount
may be used only to make the existing canonical production-data paths visible
to the isolated worktree; it is not a repository artifact. A typed block is a
successful empirical result when an existing owner cannot honestly absorb the
second-domain fact.

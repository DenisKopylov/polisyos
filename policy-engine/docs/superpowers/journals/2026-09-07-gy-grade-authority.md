# GY grade authority — investigation and local handback

Date: 2026-09-07. Worktree: `/Users/deniskopylov/polisyos/.worktrees/gy`.
Branch: `codex/gy-grade-authority`. Slice base: `f4815387063`.
No push, GitHub tools, stash, history rewrite, or stale-branch mutation is authorized.

## Investigation (recorded before behavioral measurements)

The four requested debt rows were read as specifications, including their closure
signals. Neither the debt register nor LEDGER is a verification oracle; their
checker is excluded. The task's invariant is: **a grade is not issued by the party
whose claim it grades**. Findings beyond that invariant are proposals, not repairs.

### gy-census-decisive-property-unmeasured

The actual debt concerns evidence for task completion, not whether an artifact has
a field named standing. GY §8.5 and Task Q's investigation distinguish a selected
Done-when predicate from all conjuncts of completion. The historical population
must be recovered from the complete plan change, independently cross-checked,
and joined to current task rows by identity. No search-match total proves it.

Hypothesis before testing: a source-bound measurement can refute a task's
completion claim even when its self-written status remains `executed`; conversely,
one passing delegation test cannot establish the independently correct judgments
required by GY-C2. A runtime receipt verifier cannot by itself establish this
Markdown census. The CR5 routing may therefore need narrowing instead of a shared
wrapper. Cheapest honest close: enumerate the exact population, preserve per-
predicate scope and every unmeasured conjunct, and make the owning plan explicit
about which status is and is not established. Test this reading before deciding.

### GY-PA1

The closure asks for the S8 authorization/request and schedule production,
persistence, resolution and ranked-consumer chain, with the no-schedule and
wrong-authority negatives. GY §8.5 subsequently moves its engineering half to
GY-PR1a; the old PA1 scheduling verdict and missing capability are different facts.

Hypothesis before testing: the current S8 factory admits caller-declared
mandate/status/role references while archive creation always rejects a ranked
case with `p20_value_schedule_resolver_absent`. A green unauthorized-schedule
negative behind that unconditional refusal would measure the wrong property.
Cheapest honest close must wire an independent evidence resolver to the existing
ranking boundary and persist an explicit refusal request, without minting a
mandate or manufacturing an N8 receipt. The investigation must locate the exact
engineering/appointment/data boundary before sizing that repair.

### GY-DEF22

The current closure leaves the appointed Foundry catalog/discovery owner's
acceptance of six bounded claims outstanding. It expressly says no engineering
work is owed. The previous review-subagent ACCEPT is not such an appointment.

Hypothesis before testing: the existing non-decisive diagnostic changes its own
result on environment drift while governing N8/N10a/chronology bytes remain
equivalent to diagnostic removal. Removing the actual generic discriminator,
while keeping its DTOs and marker strings, should make its CB-I02 witness fail.
Cheapest honest close: remeasure that property, retain a typed-empty acceptance
slot, and hand the six claims back for an appointed signature. No self-countersign.

The alleged CR5 witness at `dependency_authority.py:3085` is a private success
payload behind a fieldless token. The visible result union also has rejected and
unestablished arms. This is a counter-hypothesis to the register's isolated-Literal
reading, not yet a behavioral verdict. Follow complete issuance/consumption paths.

### adjudication-and-champion-chain-is-forgeable

The row requires an independently appointed evaluator receipt, a non-producing
authenticator, recomputation from bound observations and champion replay before
any publication projection. Shape and matching manifest labels do not meet it.

Hypothesis before testing: `ClaimAdjudicationRuntime.admit_champion` checks
self-written evaluation metrics, guardrails and provenance strings without an
authenticated observation receipt. A coherently fabricated evaluation passes.
Separately, DataForge's `load_admitted_claim_adjudication_batch` admits a fabricated
batch from matching labels and lineage; `materialize_claim_adjudication_result`
can call it without the Scientist runtime. Thus repairing only Scientist's entry
point leaves a sibling emission path. The single intake must be closed at that
loader too. This path lies outside the allowed edit set, which must be verified
as a real row blocker rather than used to justify a symptom-only fix.

## Execution plan and pattern pass

1. Independently investigate PA1, DEF22 and the stale branch while the coordinator
   investigates census membership and the adjudication chain. No concurrent writer
   shares a source or governed artifact.
2. Record hypotheses first; run focused behavioral stations. Enumerate full path
   sets, compare identities in both directions, classify unreadable cases ambiguous.
3. Implement only an established mechanism within the approved paths. Preserve
   negative and unavailable outcomes, leaving institutional signature slots empty.
4. Freeze changes, review the delta, run blast-radius tests and appropriate
   recomputing validators once. Commit clean boundaries after checking attachment;
   read committed files back from the branch. Stop before push.

Relevant patterns: P05/P15 (authority), P29/P32 (behavior/content versus markers),
P31 (single intake/emission), P35/P36 (whole-set and finding-bound evidence),
P37/P38 (predicate provenance/proxy), P40 (same-class finding bucket), P41 (no
unproved inherited-red claims). A second finding of the same class widens the
mechanism or yields a measured bounded residual; it does not start a patch ladder.
Acceptance: actual consumer refusal of self-issued labels, favorable/unfavorable
results through real paths, and at least one property-removal red per measured row.
Missing capability labels are assigned after tracing, not inferred from prose.

## Stations and environment

- Auxiliary worktrees: none created.
- `git status -sb` after setup: `## codex/gy-grade-authority`.
- `uv sync --offline --frozen --extra lint --extra test --extra runtime` failed
  because the pinned odfpy wheel is not cached. Minimal offline install also lacked
  cached pytest metadata. These are tooling non-receipts, not product findings.
- A local CPython 3.14.3 venv reads the existing main venv's dependency directory
  through local `gy_reused_dependencies.pth`; no sibling file is modified. Tests
  use `PYTHONPATH=src` and local `python -m pytest`, with import origin verified.
- Scratch is under this worktree's `policy-engine/_build/gy-grade-authority/`.
  No shared production data writes or fixed-port/browser stations are planned.

## Measurements, changes, probes and remaining work

Pending the stations above. No row is claimed closed by this initial record.

## codex/gy-def6-e11 analysis

Read-only analysis is running in parallel. Its commits and `.e11/gy-def6.ledger`
are evidence of that branch's intent and recorded stop, never authority to merge
or recover it during this task.

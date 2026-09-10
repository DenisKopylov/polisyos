# GY lattice and custody — execution and completion journal

Date: 2026-09-10. Immutable lane merge base: `992aa493f`.
Local branch: `codex/gy-lattice-and-custody`.
Worktree: `/Users/deniskopylov/polisyos/.worktrees/gy-lattice`.
No push, history rewrite, stash storage, or other branch modification.

This is the lane's single completion journal. Work is in progress; no task is
declared executed by this initial entry. Final deciding receipts and standings
will replace the pending entries after integrated verification and branch readback.

## Stage boundaries and scope

`f51b85b0a` is the first commit. Its only change adds
`policy-engine/docs/superpowers/journals/gy-lattice/**/raw/` to `.gitignore`.
The initial commit attempt failed because the fresh checkout lacked lefthook;
`corepack pnpm install --frozen-lockfile` supplied the workspace dependencies,
and the ordinary hook then completed. No hook was bypassed.

`950c6a57f` commits the complete Stage-1 decision set before any source or test
change. All five files were read back from the attached branch and compared
byte-for-byte to the worktree. The user's prompt supplied execution authorization;
there was no intermediate approval pause.

| Task | Decision at Stage-1 commit | Current evidence status |
| --- | --- | --- |
| GY-VC1 | `docs/superpowers/specs/2026-09-10-gy-vc1-decision.md@950c6a57f` | Stage 2 in progress |
| GY-AS1 | `docs/superpowers/specs/2026-09-10-gy-as1-decision.md@950c6a57f` | Stage 2 in progress |
| GY-CR2 | `docs/superpowers/specs/2026-09-10-gy-cr2-decision.md@950c6a57f` | Stage 2 in progress |
| GY-CR3 | `docs/superpowers/specs/2026-09-10-gy-cr3-decision.md@950c6a57f` | Stage 2 in progress |
| GY-CR5 | `docs/superpowers/specs/2026-09-10-gy-cr5-decision.md@950c6a57f` | Existing mechanism located; final verification pending |

Concurrency is bounded to three workstreams: VC1; CR2/CR3; AS1. Root completed
CR5's architectural investigation before starting the third agent and coordinates
shared work and separately authors AS1's oracle. Root serializes commits,
README/initializer changes, the plan table and this journal. Source and fixtures
are exclusively assigned by path. No shared DuckDB, fixed port or browser station
is used. Reviewers classify new versus repeated classes before proposing repair.

## Findings that determine execution

**GL-CR5-01 — the historical defect was already repaired in the supplied base.**
The initial `GGA-ADJ-01` witness is followed in its own journal by `GGA-ADJ-02`,
`GGA-GATE-02` and `GGA-PA1-05`. Those findings and commit `d421575d3` deliver the
shared non-producing verifier, both production intakes, retained predecessor
replay and complete consumer-subject binding. Reading only the beginning of that
journal would have rebuilt a closed mechanism. The CR5 decision therefore chooses
fresh behavioral and removal verification. No CR5 production source edit is
planned. The source owner is
`src/polisyos/data_forge/domains/academic/batch/claim_adjudication_verifier.py@992aa493f`.

The five explicitly selected baseline test functions collected 17 parameterized
cases and passed in 29.62 seconds, exit 0. Full output:
`gy-lattice/root/raw/cr5-baseline.txt`. This preliminary count is not a claim about
all grade consumers or complete CR5 acceptance.

**GL-TABLE-01 — the complete initial standing table matches the prompt.**
Two separately written parsers (anchored regex over the entire section and a
line-state/cell parser) agree on all identities and statuses in the single
Markdown file's complete §8.5: 74 = 50 executed + 17 not_started + 5 blocked +
2 not_executed. Every commissioned row starts `not_started`. Initial parser
attempts exposed the heading level and bold-wrapped status cells and refused;
neither was counted as a census. The final delivery checker must compare full
rows against the lane base and permit movement only in the five commissioned IDs.

**GL-ARCH-BASE-01 — full architecture gate ran; freshness could not run.**
The sole gate command was:

```sh
PATH="$PWD/.venv/bin:$PATH" PYTHONPATH=.:src .venv/bin/python -m tools.cli architecture guardrails check > docs/superpowers/journals/gy-lattice/root/raw/architecture-base.txt 2>&1
```

Exit 1. The emitted finding is `required_freshness_environment` /
`probe_environment_preparation_failed`: the gate-created interpreter aborts with
SIGABRT because `@rpath/libpython3.14.dylib` cannot be found. Required generated
freshness is **unrun**, neither passed nor skipped. The complete output is retained
at `gy-lattice/root/raw/architecture-base.txt`. This lane does not repair or sync
the gate, conceal the failure, or invoke the debt-ledger checker. A final gate
will inspect the frozen integrated source; new deep-import creep is a stop.

The local offline `uv sync --frozen --extra lint --extra test --extra runtime`
could not find cached jaxlib. The isolation-local CPython 3.14 environment instead
reads the existing dependency directory through a local `.pth`, as prior lanes
did. Import-origin verification resolves `polisyos` to this worktree, with pytest
9.0.2 and Pydantic 2.12.5. This dependency reuse does not establish that the gate's
separately created environment can build.

## Closeout obligations

**GL-AS1-ORACLE-01 — independent expectation seal, before subject execution.**
Root authored the complete 63-row TSV from research and reviewed stimulus inputs,
without reading the new subject source or observing its answers. Two independent
input-ID walks (JSON structure and lexical case keys) reconcile with the separately
expanded expected family set. The expectation SHA-256 is
`ed74752c6e965bc5aabc4c0f8cd6d111ccf4f227646d46433223307bc001a3e0`;
the input corpus SHA-256 is
`84de2b1384f0a6262398620491113bf4d55449667b847b4dbbd9e84120d00f99`.
The checker must appoint these literal identities rather than compute a trusted
identity from whichever file it happens to read. These seals freeze the synthetic
assurance manifest, not a governed institutional epoch or authority artifact.

The isolated oracle shares no decoder, fixture loader or comparator with the
subject. An actual readable subject-source probe and forbidden JSON import prove
the process boundary. Removing that boundary yields
`oracle_isolation_not_enforced:subject_read`; decoder, loader and comparator
dependency attempts each refuse before grading. All ten targeted oracle tests
passed, exit 0, and ruff passed. Complete deciding outputs are
`gy-lattice/root/raw/as1-oracle-tests.txt`, `as1-oracle-ruff.txt`, the four
`oracle-{decoder,loader,comparator,unconfined}.txt` probes, and
`as1-oracle-seal.txt`. These checks do not yet establish that the subject passes.

Two stimulus-review findings were the same P32/P37 witness-binding class. The
first required substantive finite terminal witnesses; the second widened binding
to the complete demand, actual assessed objects and actual finite alternative set.
The bounded residual is explicit: finite synthetic proof is not completeness of
the real world's causal models, institutions or providers. Further examples of
that residual do not trigger an open-ended institutional subsystem build.

**GL-AS1-INPUT-02 — the independent oracle caught a malformed adversary.**
The first live subject run failed with 24 field differences over all eight form
cases. The fixture generator had aliased candidate facts and owner requirements;
removing a candidate fact also removed the corresponding demand. This is a new
fixture-construction class, distinct from the bounded terminal-proof residual.
The correction restores the eight complete owner requirements while preserving
the missing candidate fact and plausible signature. Root checked every restored
key set against the eight distinct substantive obligations. The expectation file
and all case IDs remain unchanged. The corrected input SHA-256 is
`5ba11a2f0d80dca0fca8ff30f6544d01b79e7e0be412e0eb8d0c5498ea22ad13`;
the failed deciding output is `gy-lattice/as1/raw/baseline-first.txt`.

Commit `30dd80249` contains the oracle program/tests and the initial seal record;
the TSV itself was omitted because the existing broad `*.tsv` ignore matched it.
An append-only correction adds a narrow tracked-artifact exception and the sealed
TSV. Branch readback identified the omission before any delivery claim.

**GL-CR2-01 — expansion is a state property, not an event label.**
Root independently adjudicated the restart review against OPS-R5 `AUD-F06`,
`amendment-state-invariants.md`: `protected_restart_or_expansion_has_fresh_restart_evidence`
applies to actual exposure expansion even when an event is named `observe`.
The oracle revision is authorized by that explicit conjunct, not by agreement
with the implementation. Same-class deeper P37/P38 correction widens the gate;
no competent external restart authority is inferred.

Each task still needs its exact Done conjunction, binding falsifier and actual
non-test caller verified. Retain complete deciding gate and removal output, cite
tracked source as `path@sha`, and keep oversized raw evidence ignored. The final
runner must list every test file/node explicitly. No broad suite, guardrail sync,
DEBT-REGISTER/LEDGER edit, or completed-task repair is authorized. No governed
epoch or artifact reissue is planned; any change must be declared from
`992aa493f` before mutation. All incidental findings receive named routes in the
final entry, including refused institutional and external-execution claims.

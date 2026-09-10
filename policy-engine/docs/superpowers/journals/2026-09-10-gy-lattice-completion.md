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

Each task still needs its exact Done conjunction, binding falsifier and actual
non-test caller verified. Retain complete deciding gate and removal output, cite
tracked source as `path@sha`, and keep oversized raw evidence ignored. The final
runner must list every test file/node explicitly. No broad suite, guardrail sync,
DEBT-REGISTER/LEDGER edit, or completed-task repair is authorized. No governed
epoch or artifact reissue is planned; any change must be declared from
`992aa493f` before mutation. All incidental findings receive named routes in the
final entry, including refused institutional and external-execution claims.

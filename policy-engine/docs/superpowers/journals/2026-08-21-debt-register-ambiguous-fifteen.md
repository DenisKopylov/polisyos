# Re-measuring the fifteen ambiguous GY debts

**Date:** 2026-08-21 · **Base:** `main` `c270b46c5`, bound as the merge base of a fresh attached
worktree on `codex/debt-register-census` · **Output:** `DEBT-REGISTER.md` Rev 2 ·
**Result:** 14 of 15 resolved; `GY-DEF9` stays `ambiguous`; four new rows registered.
**Rounds consumed: 0 of 2.** No repair was attempted, so no round was spent.

## The method, and why the prose was never consulted

The Rev-1 census failed twice on prose, so prose was excluded as a source outright. Each block was
resolved from two things only: **the commits, branches and paths it cites**, checked against git;
and **its own executable witness**, run at the base. A verdict was recorded only where those two
agreed. Where the witness could not reach its own predicate, the item stayed `ambiguous` — which
is a complete result, not a failure.

That method worked. **26 of 27 cited commits are ancestors of `c270b46c5`**, and the 27th
(`ba5946ebc`) is one the plan itself declares *not* an ancestor — so the blocks are accurate even
about their negatives. The checkable structural claims reproduce exactly: `70a3f3d15` is 61
commits and 29 paths; `GY-DI4`'s lane is 15 files with 0 under `src/`; `GY-DEFC-4`'s delta has 0
paths under `src/polisyos/data_forge/`.

## What actually made the fifteen ambiguous

Not one cause. Two proxy failures, both `P38` at their own boundary, both cheap to fix:

1. **Source A keys on one marker spelling.** `GY-DEF10` says `**CLOSED at 431bcd798…**` and
   `GY-DEF13` says `**Execution standing (f015e6631…): defect_standing = closed**`. Neither is
   `**STANDING RECORDED**`, so both read as "no standing marker at all". Five of the fifteen were
   ambiguous for this reason alone — the standings were there and were correct.
2. **Source B misses the repo's own commit idiom.** `GY-DI4`'s four closing commits are subjects
   like `fix(gy-di4): admit a timing sample on completion, not on exit_code == 0` — lowercase
   kebab in a conventional-commit scope, not the token `GY-DI4`. An exact-ID scan reported "no
   matching commit" for an item that has four, all ancestors.

The transferable form: **an identifier scan must search the naming conventions a repository
actually uses, and a standing scan must search for the *shape* of a standing, not one spelling of
its header.** Both proxies were measuring their own vocabulary, not the repository.

## The one that did not resolve

`GY-DEF9`. Its witness — `test_governed_owner_history_independence.py::
test_real_governed_owner_bytes_ignore_incompatible_durable_history`, five parameterized cases —
landed at `3af775d8e`, an ancestor. Run at the base, **all 5/5 terminate
`ConfidenceLedgerError: canonical_loaded_runtime_mismatch` inside `_run_owner`**, before the
fresh-versus-incompatible governed-byte comparison that is the whole point of the witness.

A completed failure is a receipt; this is a failure of a **prerequisite**. The DEF9 predicate was
never evaluated, so neither `open` nor `closed` is supportable, and reading it as a regression
would be exactly the error the register exists to prevent.

## The finding worth the task: the canonical environment is broken

`policy-engine/.venv` — the environment that holds every example plugin distribution and is the
only interpreter these witnesses are written for — resolves `policy-engine 0.1.0` through an
editable `.pth` pointing at
`/Users/deniskopylov/polisyos/.worktrees/gy-gap1-obligation-instance-identity/policy-engine`,
**a worktree that no longer exists**. `import polisyos` raises `ModuleNotFoundError` in the
canonical interpreter. Only `pytest` recovers, by rootdir insertion.

This is `GY-DEF13`'s own subject one level up — an editable install binds an *address*, and the
address went away — and it has three consequences the register now carries as rows:

- every canonical validator CLI is unrunnable as invoked;
- `GY-DEF9`'s witness dies at a deployment-identity gate rather than at its own assertion;
- any `--check` result taken today is a `PYTHONPATH` **proxy**, and since deployment identity is
  computed over the *authority import closure*, the proxy can change the very quantity being
  compared. So the one drift this census observed is registered as a row to re-measure, never as
  a verdict. Saying `not_established` costs nothing and claiming otherwise would have been `P38`
  committed knowingly.

Two witnesses are broken in their own right and are now rows. `test_real_plugin_postures_verify_
n8_n10a_and_depth_n` hardcodes `REPO_ROOT/.venv/bin/python` and a bare `timeout=240`; it
`TimeoutExpired` at load ~7 **and again serialized at load ~1.9**, so the cap is undersized for
this host rather than contended. That is `GY-DI4`'s own ruling — a killed run measures the cap,
not the lane — violated inside a witness, four days after `GY-DI4` closed.

## What the register cannot hold

Three things had to be expressed as a token plus prose. All three are proposed in the vocabulary
section, none adopted:

- **`closed_by_successor`** — `GY-DEFC-1`'s cold axis was met by `GY-DEFC-6`, not by itself. Plain
  `closed` credits the wrong row; `open` is false. `closed_by` names a commit and cannot name a
  debt.
- **`closed_per_axis`** — `status` is one token while the `GY-DEFC` family is declaredly two-axis.
  Rev 2 widened the table to two columns instead, because any single token re-commits the original
  error. Collapsing two axes to keep a table tidy is how `executed` came to read as `closed`.
- **`closed_unreproducible`** — a closure receipted at a named head that cannot be re-derived today
  because the verifier is broken. The register's rule ("a regression is a new row") covers
  regressions; an unrunnable verifier is not one.

## Discipline notes

- **Environment appointed, never modified.** The fresh worktree had neither `production_data` nor
  a `.venv`; 29 of 29 `test_second_domain_pack.py` failures were a single
  `OwnerDataUnavailableError`. Both were appointed with **git-ignored symlinks** to the main tree —
  the `GY-N12` precedent. `git status` stayed clean; no tracked byte moved for measurement.
- **Wrong-interpreter results were discarded, not reconciled.** The first batch ran on the homebrew
  interpreter, which holds no `polisyos` distribution. `test_value_gate.py` showed ~10 failures
  there and **86/86 green** on the canonical venv. Reporting the first run would have registered
  five closed debts as open.
- **Non-receipts recorded as such:** a 10-minute wrapper kill; a 77-minute hang with no terminal;
  and the two `TimeoutExpired` posture runs. Every bundled gate was judged by its own predicate,
  never by a composite exit code.
- Nothing measured was repaired. Measuring and fixing in one pass turns a census into a rewrite.

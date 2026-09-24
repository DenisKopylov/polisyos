# Uninvoked mechanisms implementation plan

**Goal:** close the uninvoked class through runnable negative custody/admission
routes, named institutional caller tasks, and a source-derived recurrence check.

**Architecture:** route existing closed owners through new internal module CLIs;
persist and consume exact typed negatives. Keep static call evidence explicitly
weaker than exercised, load-bearing invocation.

**Stack:** Python 3.14, AST/tokenize, existing Pydantic/CAS/epoch owners, pytest.
**Specs:** `../specs/2026-09-10-uninvoked-ds15.md`,
`../specs/2026-09-10-uninvoked-ds18.md`, `../specs/2026-09-10-uninvoked-gy.md`.

## Global constraints and pattern pass

- Base `c49449343`, worktree `.worktrees/uninvoked`, branch `codex/uninvoked-plane`.
- Commit decisions before product source edits. No pause between stages.
- No push, other branch, history rewrite, stash storage, closed-task source edits,
  DEBT-REGISTER or LEDGER edits. Root owns commits, READMEs and `__init__.py`.
- Three workstreams maximum: DS15, DS18, root/GY+census. No shared runtime stores;
  every test uses its own tmp CAS/database. Git/index/README writes are serialized.
- Targeted test files/nodes only. Each deciding gate is the sole shell command.
- Raw output is gitignored under `docs/superpowers/journals/uninvoked/**/raw/`
  from the first commit. One completion journal cites complete outputs by hash.
- No governed reissue is planned. Any discovered transition uses the lane base
  and is coordinated through root. Final scope checks compare against that base.
- P01/P02/P03: caller + receipt + actual runnable consumer; P29/P33: unchanged
  negatives fail when invocation is removed; P35/P38: full syntax denominator
  is not runtime proof; P05/P37: institutional absence never becomes authority.
- Review bucket: classify new class versus same class deeper before repair;
  second same-class escape widens the mechanism or establishes a bounded residual.

## Ordered execution

1. Commit `.gitignore`, the three decisions, this plan and the research census.
   Reread source path delta and documents from the attached branch. No source
   change may precede this commit.
2. DS15 owns `src/polisyos/runtime/quality/acquisition_epoch_admission.py` and
   mirrored `tests/unit/runtime/quality/test_acquisition_epoch_admission.py`.
   Add the actual CLI test first; observe missing entry point; route the existing
   producer; inspect full persisted owner receipt; reject mutated returned
   receipt and invalid requests; remove only the new invocation and run the
   unchanged negative; restore bytes and rerun green. Full interface and
   required existing owners are in the DS15 decision. No shared edits/commits.
3. DS18 independently owns `src/polisyos/runtime/quality/epoch_custody_audit.py`
   and mirrored `tests/unit/runtime/quality/test_epoch_custody_audit.py`.
   Red actual module CLI; wire the production factory/protocol; exact canonical
   CAS readback and role-separated no-holder refusal; malformed/context negatives;
   call removal under unchanged input; restore and targeted green. No shared edits.
4. Root owns `src/polisyos/runtime/quality/production_invocation.py` and
   `tests/unit/runtime/quality/test_production_invocation.py`. A temporary tracked
   repo contains `verify()` called in tests, then an uncalled wrapper; both must
   refuse. Adding `if __name__ == '__main__': main()` and its real call chain
   must produce a static path. Test imports, aliases, class definition/construction
   without method call, named deferral, regression against base and corrupted
   receipt. Implement only after the CLI test is red. Remove assessment under
   unchanged orphan input; keep complete deciding output; restore and green.
5. Root checks the integrated diff and reviews both workers' exact new files.
   Workers cross-review new code only; report classified findings. Root adds
   nearest README entries and the caller-before-code rule to existing P01/P02
   maintenance guidance. Freeze the integrated source, then run the targeted
   wave once, individual Ruff commands and architecture checks as proportionate.
   Never launch a directory suite. Check governed source closure from lane base.
6. Commit clean implementation boundaries. Re-run the full source census on the
   committed source. Persist/check the recurrence receipt; preserve all outputs.
   Write one `docs/superpowers/journals/uninvoked/completion.md`: five outcomes,
   explicit termini/deferrals, discrepancies, complete census provenance,
   unchanged-negative removal evidence, excluded signer behavior and unchanged
   positive-transition blockers. Commit and reread from the branch before delivery.

## Acceptance matrix

| Row | Intended close | Decisive evidence |
| --- | --- | --- |
| DS18 independent holder | wired for bounded no-holder audit | real CLI → provider evaluation → exact CAS readback; call removal breaks unchanged negative |
| DS15 signed mandate owner | deferred: DS15-MANDATE-INTAKE | real DS20 route proof and institutional evidence intake missing; exact future served caller named |
| DS15 semantic epoch | wired for durable negative admission | real CLI → existing complete producer → exact persisted receipt; call removal breaks unchanged negative |
| GY verifier unconsulted | wired standing recurrence checker; existing repaired owners preserved | general source-derived orphan/orphan-wrapper controls, runnable CLI and receipt; existing selected seam negatives |
| GY builders no caller | deferred: GY-CB2 and GY-ML2 | current whole-source census plus institutional caller charters; existing three repairs separately traced |

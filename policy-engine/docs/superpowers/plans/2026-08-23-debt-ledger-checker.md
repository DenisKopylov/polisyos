# Debt Ledger Checker Implementation Plan

> **Execution boundary:** implement on attached branch `codex/debt-ledger-checker` from immutable base `94cdbd345`; root edits, read-only reviewers, no merge or push.

**Goal:** Generate the open-work/open-debt ledger from its published sources and add a reporting-only reconciler that exposes denominator or lifecycle drift without becoming an authority gate.

**Architecture:** A single read-only scanner builds typed source snapshots for the debt register, GY plan, Atlas master plan, slice plans, and frontend disposition register. The same snapshot renders `LEDGER.md` and validates the committed rendering. Source counts remain compared with the published denominator constants; a disagreement is emitted as a finding and never normalized away.

**Tech stack:** Python 3.12, standard library, pytest, ruff, existing workspace `CommandSpec` CI orchestration.

## Pattern pass

- `P29`: falsifiers execute every guarded property; no marker-only success test.
- `P35`: every count comes from a complete source walk and carries its file-type denominator.
- `P37`: parsed standing provenance is frozen as recognized, absent, or ambiguous; candidate ownership cannot become ownership.
- `P38`: no free-prose non-closure inference and no dependency edge substituted for a measured unblocking property.
- `P40`: findings are bucketed by rule. Two review rounds maximum; a second finding in one class widens the mechanism or becomes a bounded residual.
- `P41`: verification receipts name the exact attached branch and base; inherited source drift is reported, not repaired.
- Capability state during this delivery: `verification_missing` for gate promotion. Producer, artifact, CI bridge, consumer, and report surface exist, but two or three clean real slice closures have not yet occurred.

## Task 1: Freeze source contracts and test seams

**Files:**
- Create: `tests/repo_quality/tools/test_debt_ledger_checker.py`
- Reference: `docs/plans/active/DEBT-REGISTER.md`
- Reference: `docs/plans/active/layer3-slices/GY-engine-subordination.md`
- Reference: `docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md`
- Reference: `docs/plans/active/frontend-disposition-register.json`

1. Add a subprocess smoke test proving the checker path is absent/red before implementation.
2. Add a minimal repository fixture with an attached `main` branch and real commits.
3. Add eight falsifiers: dropped row, status flip, non-ancestor closure, plan-less owner, missing `file:line`, G/open duplicate, merged-without-CLOSED, and omitted declared non-closure.
4. Add real-tree replay assertions for six standing histories, fifteen GY ids absent from the register and closed, and DS5 11-of-27 plan-less routes.
5. Run the targeted test after each behavioral group and preserve the failing receipt before production code.

## Task 2: Implement the bounded reconciler

**Files:**
- Create: `tools/quality/validation/check_debt_ledger.py`

1. Define strict typed records for debts, work rows, standing hits, source counts, and findings.
2. Parse all 54 canonical register ids, retain the irregular section-E branch row as a typed branch record, and detect G/open conflicts.
3. Parse 36 canonical GY blocks, all six standing forms plus genuine absence, choose the last hit, expose hit count/line, and retain unknown forms as `ambiguous`.
4. Enumerate Atlas debt rows, slice-plan ownership across both plan roots, explicit machine-readable non-closures, and frontend disposition rows.
5. Verify closure commit ancestry against `main`, `file:line` existence, candidate ownership, merged-row closure, and ledger/source equality.
6. Implement deterministic `--write`, strict `--check`, and `--report-only` exit downgrading for CI while preserving diagnostics.
7. Keep the final module at or below 600 physical lines; stop rather than split semantics into an unreviewed helper.

## Task 3: Generate the surface and lifecycle contract

**Files:**
- Create: `docs/plans/active/LEDGER.md`
- Modify: `docs/plans/active/DEBT-REGISTER.md`

1. Append task and debt lifecycle tables under “The rules this register enforces”; each transition names loss mode and gate.
2. Generate the ledger from the scanner, sorted by status then id, with source anchors and branch links.
3. Include open work stages, measured DS16 property/date, plan-less unblocked rows, all non-closed debts, and denominator/status footer.
4. Read the generated file back and run `--check` against it.

## Task 4: Wire reporting-only CI

**Files:**
- Modify: `tools/devx/workspace/ci_parity.py`
- Modify: `architecture/gates/report_only.toml`
- Modify: `tests/repo_quality/tools/test_workspace_ci_parity.py`

1. Red-first assert the CI command is registered with `--check --report-only`.
2. Add the command to the last-mile policy list without changing blocking semantics of other commands.
3. Register its evidence/source contracts and a promotion condition requiring clean observation across two or three real closures.

## Task 5: Freeze, review, and verify

1. Run both independent denominator derivations and compare each with 54/36/13/217; preserve disagreement findings.
2. Run the eight falsifiers and three replay tests.
3. Run targeted tests, changed-file ruff, architecture/report-only contract tests, and a measured `uptime` before/after pair.
4. Freeze source, request review round 1, bucket findings under P40, repair only blocking findings, and request delta-only round 2 if needed.
5. Re-run the bounded verification wave once after final source freeze.
6. Commit at clean boundaries, verify branch attachment before every commit, and hand back the attached branch with exact receipts, no merge and no push.

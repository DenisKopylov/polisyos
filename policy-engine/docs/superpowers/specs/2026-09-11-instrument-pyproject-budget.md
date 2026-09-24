# Pyproject measurement and the claim it can support

Stage 1 decision, 2026-09-11. Slice base: `cc74d6581`; attached branch:
`codex/instrument-honesty`. Root owns this workstream and every shared file.

## Question, measured evidence, and decision

The subject is `pyproject-exceeds-its-declared-line-budget`. The binding owner is
`tools/quality/validation/repository_structure_phase0.py`, specifically
`DEFAULT_MAX_PYPROJECT_LINES`, `collect_inventory`, `gate_pyproject_size`, and
the existing command's `main`. Reading its implementation establishes a 300
**physical-line** ceiling, counting comments and blank lines. Reading every line
of `pyproject.toml` on the slice base establishes 307. The actual gate exits 1
and emits the same 307/300 finding; its complete output is in
`docs/superpowers/journals/instruments/root/raw/pyproject-baseline.log`.

The September 10 change is two physical lines, not one: the requirement
`policy-engine[test]` and the explanatory comment immediately above it. Reading
the patch of `054d3f94c` and its parent establishes 305 -> 307. Neither the old
305 nor the new 307 fits 300; the new dependency did not create the exceedance.
This establishes arithmetic and change identity, not historical ownership of
the excess. The recorded baseline JSON is a generated historical artifact, not
evidence of the live file.

Physical size is a legitimate observation of reading volume. It is the wrong
instrument for deciding dependency correctness, dependency count, resolver cost,
configuration cohesion, or whether extraction would improve maintainability.
The manifest composes mandatory PEP project/build metadata, named entry points,
uv source selection, Hatch build configuration and reusable dependency groups.
The September 10 addition illustrates the divergence: reusing one test-extra
owner improves consistency while making the raw-line instrument worse. Deleting
its comment or packing arrays onto one line changes this metric without changing
any of those properties. No such compression is authorized by this decision.

**Decision:** retain the 300 ceiling and its visible exceeded finding; make its
claim explicitly bounded in the instrument output. Do not promote the warning
to a complexity proof, silently raise the budget, delete required metadata, or
invent a new semantic budget without an owner decision and measurements. This
lane closes the measurement-honesty defect; the actual 307/300 excess remains a
named architecture disposition, not an assertion of a green size gate.

## Owners composed and seams preserved

Reuse `collect_inventory`'s tracked input boundary and the existing gate mapping.
Reuse `RepositoryInputError` handling for absent tracked configuration. Extend
the existing command's report with explicit measurement scope and verdict;
do not create a second scanner or a manifest-rewriting producer. The production
caller is `polisyos-tools validation repository-structure-phase0 gate --gate
pyproject_size --json`, discovered by the existing tools CLI registry. The same
`main` serves direct legacy calls. The final runner must exercise the registered
command, not merely import a helper.

The JSON report should distinguish completed measurement with findings, bounded
measurement without findings, and unavailable required input. Human output must
also say physical lines include comments/blank lines and name the unmeasured
semantic properties. The negative removes the manifest in a temporary real Git
station, preserving the declared measurement request: it must report UNRUN/no
complete measurement (exit 2), never zero lines or passed. Findings beside missing
inputs must be labelled partial, and report-only mode cannot turn unavailable
input into completed measurement. A long comment-only manifest remains visibly
over budget while a compact manifest still prints the same semantic omissions.

No pyproject, dependency, lock, hook, workflow or architecture-policy mutation is
planned. Therefore invocation/coverage/CI lanes keep exactly their dependency
selection, entry points, floor, lock identities and architecture budgets. Changes
to gate JSON are additive; unavailable-input exit changes from artifact-failure
1 to UNRUN 2. Existing station tests and any consumers of that exit are part of
the targeted blast radius. Other gate IDs retain their own finding semantics.

## Falsifiers and execution sequence

1. Add CLI tests in `tests/repo_quality/architecture/` using real temporary Git
   stations: 300/301 physical lines, comment/blank-line inflation, absent tracked
   manifest, malformed TOML if the measured path parses it, and report-only
   absence. Each test inspects the real command's output and process status.
2. Run each named new node red with complete output retained. Missing Python
   prerequisites are UNRUN evidence, never the intended red test.
3. Extend the existing reporting seam with bounded measurement text, then run
   those nodes and affected station-input nodes explicitly. Keep the old excess
   visible and retain the current real gate's complete output.
4. Negative removal probe must fail to establish a measurement even when the
   untracked station supplies a replacement manifest. Do not rewrite tracked
   baseline inventories as a side effect of running the gate.
5. Review, freeze, targeted Ruff and applicable architecture guardrails; record
   any deep-import growth as complete-pending-an-architect-decision without sync.

The final runner will enumerate node IDs through Python AST including async
definitions, and name the selected IDs literally. Mandatory decision/journal/
test companions are outside any mechanism-file budget (P39).

## Pattern pass and capability accounting

P18/P38: raw line count is a proxy for semantic complexity; name the divergent
comment/dependency case rather than treating an exact count as that property.
P35/P36: count the full file, read back the patch; do not cite a register row as
tree evidence. P37: input availability is established by the tracked input owner,
not by a local file's presence. P29/P33: subprocess tests remove actual input and
vary formatting; tests of output markers alone would not close the defect.
P13/P27: extend one producer/consumer chain rather than introduce another budget.

Existing chain: strict tracked inputs -> inventory -> findings -> CLI/JSON
consumer -> retained gate output. Measurement-limit surface and negative exit
distinction are `verification_missing`/`surface_missing` until the new tests pass.
Product runtime/API authority is `surface_out_of_scope`; this is a developer
instrument, not policy admissibility. Architecture owns a future substantive
budget decision; this lane must hand back the retained excess explicitly.

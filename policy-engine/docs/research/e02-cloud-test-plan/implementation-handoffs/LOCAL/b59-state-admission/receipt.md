# B59 producer-state admission repair receipt

## Finding and disposition

The admitted property is that producer-state admission completes before snapshot or attachment copying can invoke callbacks from unsupported runtime data. The old walk checked model hooks and recursed through mapping/sequence shapes, then accepted every other leaf. A nested object with `__deepcopy__` therefore passed admission and ran during the later snapshot.

This is the second finding in the same producer-state callback/admission class, one level below the prior model-hook checks (`P40`). The repair widens the generic recursive admission quantity to the full state graph. It admits exact builtin containers and finite canonical scalar values, recursively validates ordinary Pydantic model fields, allows the internal tracked container types through builtin iteration, and rejects unknown leaves, custom container/scalar subclasses, non-string mapping keys, non-finite numbers, cycles, and over-depth graphs before copying.

The property test is behavioral: the real sequential and asynchronous workflow entrypoints receive a post-construction nested poison leaf; admission rejects it, its copy callback count remains zero, the producer call count remains zero, and cache/completion publication events are absent. A real producer also attempts to attach the poison leaf through its declared tracked branch; rejection leaves state and journal unchanged and the producer's later ordinary finite output still succeeds. Adversarial cases also put custom leaves below ordinary model fields and spoof `__class__`; positive contours exercise JSON state, typed refs, finite tagged scalars, and ordinary models through cache replay.

The pre-fix red run had 10 failures in `test_state_branching.py` for the custom leaf, branch attachment, non-finite/non-JSON values, and custom container iteration. The first actual-workflow red run failed in both contours after the poison leaf was admitted and reached snapshot/persistence. The final suite is the remove-the-property falsifier: without the recursive rejection, those tests fail while their test names and assertions remain.

## Verification

- `.venv/bin/python -m pytest tests/unit/scientist/orchestration/engine/test_state_branching.py tests/unit/scientist/orchestration/engine/test_producer_scope_reconciliation.py -q` — exit 0; complete output: `focused-tests.log`.
- `.venv/bin/python -m ruff check` on the three changed Python files — passed.
- `.venv/bin/python -m ruff format --check` on the three changed Python files — passed.
- `tomllib` parse of the new release fragment — passed.

The focused suite output includes 93 tests total (72 at 77%, then 21 to 100%). Existing Pydantic serializer/deprecation and Torch Python-version warnings remain in the full output; no test failed.

## Bounded source hashes

SHA-256 is over the current file bytes; these are not Git object IDs.

| Path | SHA-256 |
| --- | --- |
| `src/polisyos/scientist/orchestration/engine/state_branching.py` | `490d05e758b8ab6cdca12dc37bddd9085dfd7987e86feb9fb4cc49db4db01666` |
| `tests/unit/scientist/orchestration/engine/test_state_branching.py` | `f6bf62a8a7cf7b9861bda09e3022c7620368cbc2e06051fc97cd1353e4ee6069` |
| `tests/unit/scientist/orchestration/engine/test_producer_scope_reconciliation.py` | `7ed69a33cb1b73057179fb52d1f10df8788c5c957fe27c8b0bbffb28f84416c7` |
| `src/polisyos/scientist/orchestration/engine/README.md` | `0fe5716fcbb1c01a4f855ccbf2d9c904e9d0534f0f5cec7f70c49049d2e24640` |
| `release-fragments/unreleased/2026-10-09-e02-b59-producer-state-finite-admission.toml` | `990a2e7fe08035bcddab6841d3126aa9a5ef6f0a1917579ec074e719697be002` |

## Limits

This is finite-data admission, not a Python sandbox. Explicit base-class mutators, reflection, and external side effects from assignment validators remain out of scope. The repair adds no global Array restrictions or scientific model changes. No Git operation was performed.

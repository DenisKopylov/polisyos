# C95 code-object observation: marshal instability

This is a test-instrument repair for `LA-017@LEX-01` (canonical pointer
`#/findings/241/criterion_refs/0`). It does not alter the Lex product or assign
G acceptance. The previous C95 harness, its receipt and its RAW smoke remain
historical facts as described in `C95-actual-triplet-r2.md`.

At commit `870855f3ca83fcb32d4bb91d00d34daab3151032`, tree
`18a3178510405de4fcd8e6ce7dbc8b3d77932633`, one canonical pytest invocation of
nine parameters recorded 8 PASS, 1 FAIL, 0 ERROR and 0 SKIP. The failure was
`producer_topics` on the restored code-hash assertion. In that same PID, the
positive-before phase observed the same `_infer_candidate_topics_v1_1` owner and
source location with both marshal SHA-256 values. The SHA at phase entry was
`3449c9e74779220554536deb13f281044c6fd1a42edb681d0757550168bca4e8`; the
restored phase had
`0855c5f9b5f6fc48a1d0a9d94b09e8d0afbd4f58fe17c199b509fe2b6f98a325`. The source
callable hash matched before and after. The finite imported project Python readset
had 287 paths and zero Git mismatches. The single-invocation run does not satisfy
the separate-process-per-scenario evidence requirement, and passing-phase
stdout was captured rather than emitted. The recorded FAIL is retained; no new
product defect is inferred from it.

A separate bounded stdlib-only probe compiled the actual source file without
importing product modules and called that code object with synthetic objects. On
Python 3.14.3, the very same code object's marshal hash changed from the same
`3449c9e7…` initial value to `368831ae…` on invocation, while its object identity,
`co_code`, observed constants, names, flags and line/exception tables stayed
unchanged. This confirms that marshal bytes can differ for the same code object;
the later probe hash is not claimed to match the canonical run's second hash.
Its 30 s / 512 MiB cap was not reached. The complete original canonical deciding
output, JUnit, profile, readset, Git readback and the probe script/output are
losslessly compressed beside this note under `evidence/c95-code-identity-r3/`.

The mechanism now uses one reusable, versioned, type-tagged fingerprint of the
actual `CodeType`'s observable non-callable `co_*` fields, recursively including
nested code and immutable constants. It excludes the deprecated `co_lnotab`
alias because its modern source `co_linetable` is included. Floating-point bits,
bytes and unordered immutable sets are preserved deterministically. An unsupported
field value raises instead of being accepted through `repr`. This content witness
is not proof of semantic equivalence, source provenance, module globals, native
code or runtime specialization. The harness additionally requires that each
observed frame uses the exact current code object in the same PID, that removal
uses a different object and that the original object is restored. It retains the
same semantic property and exact reason-specific removal qualification.

The generic falsifier at `tests/unit/remediation/test_e02_lex_code_identity.py`
checks repeated execution of the same object, different constants with unchanged
bytecode, changed nested code, signed zero, unordered values, filename changes
and fail-closed unsupported constants. The tracked runner runs its five cases
first. If they fail, the six independent existing F17 selectors can still run,
but the nine controls are UNRUN until their identity witness passes. The runner
uses a fresh process for each control and `-s` so every passing and failing phase
record is retained. Keep the full output of those deciding runs and independently
reconcile phase, source and profile evidence. New tests are UNRUN at proposal
time. No eight-pass result from the old source is promoted to the new source.

This is the same P38 instrumentation class: the intended property is actual
invocation and restoration of the original callable, while the old code tested
unstable marshal serialization. The existing C93 cold observer also uses marshal
hashes; its source-binding verdicts need separate owner review and affected
qualification, without silently retagging past evidence. The general remaining
LA-017 caller/corpus and downstream comparison boundaries remain open.

# Independent frame delta review

Reviewer: `/root/adapters_probe`. Target CMP `e82ac5834ee481051f905edfe0bd68ba19dcc6ad`
against `164d7267628f83866c3440df3128352b181fe313`. Canonical Python implementation
remains `eb4a86032a5b787114c597c8a105a1f501e4abe4`. This review imports no product
or pytest modules and executes no native tests, collection or gates.

The test/documentation delta is **NONBLOCKING within its declared finite scope**.
B74 remains **LIMITED**, with a genuine unresolved ordinary regression failure.
This is acceptance of the oracle/documentation delta, not acceptance of complete
implementation identity or formal finding closure.

The complete mirrored test and its `_chain`, `_Original`, signature and
`_strict_context` dependencies were read. It invokes `CheckpointingChainExecutor`
through a real registry/composer and initialized `FileSystemCAS`; it preserves the
completed producer output6, reopens the store, loads the checkpoint and reads the
input artifact. Its original and unchanged resume both return7 and write
`original`. It then changes the helper reached through the actual
`sys._getframe().f_globals["math"]` suffix. The retained native observation returns107
and writes `replacement`, while `history_complete` and the pointer bytes stay
unchanged. It is an ordinary FAIL, with no skip/xfail decorator. Measurement is
written before the failing refusal assertion, so the actual effect remains
inspectable even though the following no-effect assertion is not reached.

This establishes an admitted builtin-returned namespace whose selected helper
is absent from the strict implementation dependency projection. The preserved
snapshot binds `sys._getframe` as a Python-version leaf; its callback captures
contain `sys` and do not bind the selected `math` helper. The current projector
walks static module attribute selections and specific direct dynamic builtins
and attributes. It does not inspect a builtin's returned runtime context.

The witness does **not** establish that the unaffected producer prefix6 is
numerically wrong, that every reflective path is admitted, or that a full cold
replacement run disagrees with this suffix execution. B74 permits an explicit
partial recomputation plan; this particular test measures the claimed strict
identity/refusal boundary and demonstrates its missing returned-context
dependency. It does not adjudicate a future explicit recomputation plan. The
README and release fragment now describe actual static/direct controls, state
the frame FAIL and require a generic dependency/refusal strategy before a full
B74 proposal. Their prior universal-reflection wording is narrowed.

The old test definitions remain AST-identical; the only test-file delta adds
the frame helpers, class, ordinary case and imports. Production `.py`/`.pyi`
paths have no delta fromeb4. Original ignored-frame and mirrored native runs are
two observations of the same class, not two new independent mechanisms or a
future combined-suite PASS. Historical109PASS remains tied to the preceding
test input. The current mirrored case has actual1FAIL.

The stdlib/Git checker re-derives the complete51-path delta, reconciles both
frame observations against XML/wrapper/measurement/stdout, binds all156 and166
author hook-time file origins to their exact Git bytes, and verifies every
preserved mirrored fixture object. The generation pointer resolves the exact
snapshot SHA; the saved producer result is6 and the effect file contains both
original lines followed by replacement. These are retained author observations,
independently reconciled here without a runtime replay. Hook-time module origin
censuses are not complete resource/network/child/memory readsets or a census
after all finalization imports.

All three replacement `JSON.text` stdout representations decode byte-for-byte
to immutable originalb940. Hashes, byte lengths and all native whitespace are
preserved. No trimming, outcome relabel or history rewrite is involved.

Pattern pass: P29/P32 distinguish the real effect from pointer/identity markers;
P35 names complete file and origin denominators; P37 keeps retained native
observations independently reconciled and reviewer runtime UNRUN; P38 identifies
the Python-version leaf versus selected helper dependency; P40 folds this frame
case into the declared returned-context residual rather than proposing another
helper-specific repair. No inherited-red/P41 waiver is claimed.

# C95: nested code falsifier correction

The R3 CodeType witness and its independent review are described in
`C95-code-identity-r3.md`. The five new falsifier tests ran on source commit
`978d9ef61f9498065d2e3ab126c769a0357970b2`, tree
`ec5fd525af9ef792b659367531d5edfb6c1e36df`: **4 PASS, 1 FAIL, 0 ERROR,
0 SKIP**. The failure was the nested-code test's final assertion that the changed
function returned 4. The finite project Python readset contained 75 paths with
zero source mismatches. The original result remains valid for that source and
is retained in full under `evidence/c95-code-identity-r4/`; it is not a helper
or product defect by itself.

A separate bounded, stdlib-only probe on Python 3.14.3 traced the actual nested
CodeType in each call. The original and mutated inner code had the same bytecode,
and the trace confirmed that the mutated object with `co_consts == (4,)` really
ran. The disassembly nevertheless showed `LOAD_SMALL_INT 3`, so both calls
returned 3. The test had changed a constant-table entry the instruction did not
read. The probe also changed a string literal consumed by `LOAD_CONST`: original
and mutant then returned `original` and `changed`, respectively, while both the
outer and inner bytecode remained unchanged. Full probe script, stdout, stderr,
and supervisor result are retained alongside the original test evidence.

This is a **new, distinct test-fixture class** for P40: the attempted witness
changed a data field without changing the executed behavior. The previous R3
finding concerned unstable marshal serialization of an unchanged object; the
older C95 finding concerned accepting a wrong exception as a removal red. All
are related to P38's distinction between a proxy and the property, but they are
not the same mechanism or a repeated repair ladder. The corrected test chooses a
consumed string constant, asserts both bytecode sequences are unchanged, obtains
the actual nested function from each outer function, confirms its `__code__` is
the respective original or changed inner object, and calls both functions to
observe the different results. Merely changing a marker or checking a hash is
insufficient. The generic code-fingerprint helper and its public test interface
are unchanged.

On the subsequently composed source, first run
`tests/unit/remediation/test_e02_lex_code_identity.py` and retain complete output.
Only after all five falsifiers pass, execute the nine Lex controls with one
process per scenario, retaining `-s` phase output, source/profile identities and
before/removal/restored observations; the six independent F17 selectors can run
regardless of the fingerprint-test outcome. The corrected tests and nine controls
are **UNRUN** at proposal time. Author proposal, independent review, actual
runtime verification and G acceptance are separate. This remains bounded to
`LA-017@LEX-01`; it does not decide legal authority/currentness, corpus coverage,
the complete downstream capability or formal closure.

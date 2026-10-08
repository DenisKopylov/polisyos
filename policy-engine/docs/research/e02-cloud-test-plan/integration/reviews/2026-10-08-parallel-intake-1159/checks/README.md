# Source-qualified G checks and recovery

All stdout/stderr and available JUnit files are retained losslessly. `execution.json`
records the exact executed script, argument vector, source/tree, environment lane,
and timing. Large loaded-origin inventories and generated fixture stores remain
ignored with path/hash references; no raw source archive is imported here.

`C08-exact` is the unmodified a5 source, 123 cases in five selected modules.
`C08-graph-hash-removal` recompiles only the named function in memory, removes its
content-mismatch rejection, and runs the exact stale-hash negative plus correct
positive. It is an expected-failure control, not an ordinary product FAIL.
Both normal selectors passed in the ordinary run. The complete executed removal
script/recipe and the exact `exact_pytest.py` origin-check harness are supplied.
For a different host, rebind the one old Mac scratch harness path in the removal
script to this sibling `exact_pytest.py` file; keep the recipe/selectors/source
unchanged. That portability-only path adaptation was not executed in this G run.

The E three scripts preserve all attempts. R1 fails on a harness attribute before
the property; R2 has no matching positive because three unrelated fixture channels
are missing. R3 supplies the same existing complete typed fixture channels to all
controls: complete admits, natural missing blocks, forged missing admits. Its final
assertion FAIL is the actual product property counterexample. No source guard is
removed in any E attempt. Synthetic context is not institutional authority.

To rerun a particular discriminator, supply a new retained scratch/CAS directory,
exact source checkout/archive and genuine configured interpreter; use the recorded
script argument order. Rebind host paths explicitly, require fresh actual-host
admission for a managed lane and confirm full loaded source origins before using
results. Do not repeat the whole catalog, old numerical waves or mutate source.
Fixture stores are retained; the probe uses mkdtemp without automatic deletion.

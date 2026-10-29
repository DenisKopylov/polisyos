# Q1 CAN.3 reader-profile source proposal — qualified continuation

Base for this continuation: `558d24d33f6bfa13d314c033c078b76959ae2d99`, tree
`23c6ec8a16651187a7b7d298f030e49b2d008cb3`. The starting C147 return is the
50,654-byte diff SHA-256 `475c098f054ff908f5d2b10471ee5af6dd76444ecc95c99c30710dae80122574`,
whose eight postimages were independently reconciled. This continuation reuses
its four source owners and three test owners rather than claiming another codec.

## Implemented source and boundaries

Common manifest parsing accepts the concrete reader's explicit supported-version
tuple. Core generic, async, bounded and frame readers and the generic IR reader
forward selected .2/.3 version and their distinct @1/@2 interpretation identities.
Unknown versions remain candidates/refusals according to each existing API.

A shared IR owned-callback codec guard now refuses unqualified .3 before owner
profile callbacks or payload reads, and repeats at the private callback decode
boundary. That path still decodes .2; generic .3 support does not qualify its
callback cohort. This is an explicit class boundary, not a per-artifact patch.
Persisted .3 JSON writers remain fenced before projection/store effects.

The extended tests specify independently authored nested raw/escape/native wire,
value types, real-CAS exact refs, async/frame reads, signed-zero carrier identity,
same-payload/different-profile policy selection, bounded exact/one-under wire
metrics with a no-value-materializer event oracle, missing-bounded-backend
refusal, IR Core-only descriptor separation, and a .3 owned callback that tries
to self-approve. Package READMEs, a qualified public read contract and release
classification accompany the change. The new IR policy constant is exported by
`canon.py.__all__`, not the top-level model-layer facade.

## Evidence classification

The original Cloud report claimed three pytest groups PASS, but their complete
stdout/stderr/JUnit/readsets/timing were not delivered. Those outcomes remain
`not_established`, not confirmed failures or passes. This continuation ran no
product imports, tests, installed/native checks, generators or removal controls.
The AST/Ruff/diff checks in the RAW continuation manifest are structural evidence
only. Exact R-version, R-map, reader wire-bound and owned-callback removal patches
and selectors are supplied as **UNRUN proposals**, not proof that removals went red.

Root must freeze and compose the postimages, run the intact focused tests with
complete candidate-bound outputs, run each removal in a distinct disposable
physical copy and retain the red/restore witnesses, then perform final shared
public-inventory and installed/rollback work. Generator effects are not inferred
from facade symbol count; the unapplied generator-impact companion names them.

## Pattern and completion

P29/P32/P33: behavioral independent value/event oracles, no claimed removal PASS.
P37/P38: reader version dispatch is real; a caller .3 label or callback True does
not prove owned-callback/writer readiness. P40: these are the existing evidence,
context-fidelity and companion classes, not new per-instance repair classes.
P39: documentation/tests/release/evidence companions are outside mechanism count.
P41: no product red is called inherited. No source-bound runtime PASS, whole-Q1
closure, authenticity, authority, currentness, installed acceptance or G acceptance
is claimed. CAN.2 Fabric and TC artifacts remain independent and unchanged.

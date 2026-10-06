# Compiled Treasury randomization

Owner: `polisyos.foundry.compile.randomization` and the native graph executor.

New Trinity compilations mark `ExecPlan.notes` with
`randomization:treasury_salts_v1`. Their execution manifest contains exactly one
`treasury_plan` input, retaining the selected CAS manifest profile. The Treasury
root seed is the compile-time `random_seed`, with an omitted seed normalized to
zero. Its existing schema 1.0, stable hash formula and serialized builder output
remain unchanged. Compilation with a nonzero seed now persists that seed's
salts rather than silently constructing root zero.

Before any native node executes, the reader verifies the selected CAS bytes and
ownership, the execution plan's program identity, both manifest program edges,
the graph's lowered-IR edge, Treasury kind/schema, root seed, and complete node
and stream salt maps recomputed from the actual graph. Missing, duplicated,
unknown-version or inconsistent inputs are refused. A valid DTO or profile note
alone does not admit a randomization plan.

Version one starts with `jax.random.PRNGKey(effective_seed)`. For each node it
folds the default stream salt, then that node's salt. Each 64-bit salt is folded
as its low 32-bit word followed by its high 32-bit word. The native mechanism
splits that node key once before its actual kernel draw. Registered method nodes
split once and retain the existing key-to-dispatch-seed conversion. Skipping an
earlier node does not advance another node's versioned stream. This profile
does not add a timestep fold: repeated calls on the same seed and graph retain
common random numbers, while state-dependent policy outputs may still differ.

The effective seed follows the existing public execution posture:
`FoundryExecConfig(seed=...)` explicitly overrides the compiled seed; otherwise
the compiled seed is used, or zero when omitted. The low-level executor applies
the same rule to its optional `seed` argument for a marked plan. An override
changes the base key; the persisted salts remain bound to the compile-time root.

Unmarked historical execution plans retain the original sequential key law.
The low-level omitted seed remains zero for those plans, and the public facade
retains its existing posture resolution. Old Treasury bytes remain readable;
they are not rewritten. Recompilation intentionally creates a marked execution
plan with new manifest lineage and possibly new Treasury content/digests.
Replay historical artifacts directly when the historical RNG law is required.

Native tests compare actual registered adaptive-agent state changes and public
execute/CAS snapshot readback with independently derived SHA-256/JAX streams.
Removal controls retain successful profile/artifact markers while deleting salt
folds; they must change the native result. Separate tests preserve old-plan
draws and builder seed/permutation/serialization behavior.

The four mechanism-family declarations are catalog and IR certificate inputs.
Their existing IC certificates do not establish executable state activation.
No family-to-runtime economic mapping is introduced by this profile. Installed
wheel/sdist layout identity and any owner-ratified family state operation have
separate acceptance evidence. All randomization claims here concern bounded
synthetic determinism, not economic validity, real policy outcomes or a general
randomness-quality proof.

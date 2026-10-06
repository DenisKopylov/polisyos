# Native fiscal calculation dtype

Owner: `@foundry-owners`

`IncomeTax` applies its rate to `agents.reported_income`. `TaxSubsidy`
applies its rate and sector weights to `agents.income`. Each calculation
materializes these inputs in the receiving income array's floating-point
dtype, with the existing minimum of float32, before multiplication. Integer
and lower-float inputs retain their historical float32 arithmetic. Agent
deltas and the government's opposite summed delta use
that calculation dtype; PatchMap application retains the existing sum rule.
Rates, active and target masks, units and random-key progression keep their
existing meanings. No monetary rounding rule is introduced.

The constructors retain the supplied floating-point precision until a state
is available, with a minimum of float32. Their public `.rate` field remains
a JAX array. With x64 disabled, Python float rates still materialize as
float32. With x64 enabled, Python float and explicit float64 rates now retain
float64 instead of being quantized to float32. This source-storage dtype
change is an explicit compatibility change. An explicitly supplied float32
rate keeps its given precision even when applied to float64 income.

For example, a Python or registered Decimal `0.10` applied to ten float64
incomes of `1000` produces revenue `1000`, rather than
`1000.0000149011612` from a rate quantized first to float32. Float32 income
still uses float32 arithmetic. Subsidy sector weights also enter that
calculation dtype, preventing their default x64 allocation from widening a
float32 patch. This explicit subsidy patch dtype correction also covers
integer and lower-float inputs under x64; their computed values are retained.

The reduction also uses that calculation dtype. In the finite 40-case
integer/lower-float comparison, 30 complete patch profiles retain dtype and
bytes. Ten x64 subsidy profiles change output from float64 to float32, with
eight government totals changing through float32 reduction: for example,
`-3.0000000968575478` becomes `-3.0`, and `-3.162499986588955` becomes
`-3.1624999046325684`. Per-agent delta values stay equal in all 40 cases.
These are declared numerical behavior changes, not ABI-neutral results or
a new currency rounding policy. The 24 complete default x64-disabled
float32 profiles retain all rate, patch, state and key bytes.

The validation helper's default float32 profile stays available. Public
`compute_tax` and `compute_income_tax` use the reported-income dtype. Rate
rebinding, differentiation and pickling use the current `.rate` parameter;
there is no second private rate cache.

An old serialized module holding a float32 rate keeps that supplied
precision when read by the new kernel. Casting it to float64 does not recover
the original Decimal or Python input. Recreate the module from its original
parameter source when that source precision is required.

The contract is native floating-point arithmetic, not decimal-exact money
arithmetic or a currency rounding policy. The finite controls cover float32
and float64 CPU execution, eager and JIT kernels, masks, accounting, real
registry/compiler/CAS replay and fresh state readers. They do not establish
real-data calibration, a welfare objective or G acceptance.

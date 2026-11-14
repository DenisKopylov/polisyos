# Policy Method Catalog

This package owns policy-analysis methods registered through the shared Foundry
`MethodRegistry`. Add methods to `_registry_boot.py::register_policy_methods()`
and expose supported public classes from `__init__.py`.

## Period Flow to Stock

`policy.accounting.period_flow_to_stock@1.0.0` applies an already materialized
USD total for one model transition as an additive delta to a model-declared
accumulated balance. It does not multiply by the step duration, read ambient
state, or establish that the target represents cash-on-hand. The model and
execution owners must verify the target's declared meaning, unit, and SUM
merge contract; method execution alone remains candidate arithmetic with
`empirical_status=not_established`.

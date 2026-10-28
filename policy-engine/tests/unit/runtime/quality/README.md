# Runtime Quality Unit Tests

Runtime-quality tests cover Policy Design Case closeout semantics, authority
composition, replay, capability graph wiring, and audit/export behavior. Keep
new tests close to the runtime-quality module they exercise, and use shared
fixtures only when the same evidence is consumed across multiple quality
surfaces.

`test_controlled_candidate_source_roots.py` checks exact selected SKG identity,
legacy and explicit input roots, and the independent generated-output root.
`tests/integration/runtime_quality/test_controlled_world_model_source_binding.py`
reopens actual configured base/child WMRs through a fresh authorized CAS handle.
These bounded fixture checks do not establish an ordinary N4/planner path or
predictive S10.

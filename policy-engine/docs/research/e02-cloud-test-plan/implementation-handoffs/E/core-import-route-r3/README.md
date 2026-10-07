# Core import routes, third continuation

Implementation `539ee6d6aad7f9db4c03dc520fc515dabef8d799` (tree `cee54ddfec357aedc96a8495b4a9fff5b5cec167`) routes seven E producer/readers through existing curated Core root module exports. Source behavior is unchanged after resolving qualified bindings. No Core/IR/schema/generated or exception/baseline file changed.

Actual affected consumers: 114 PASS. Independent candidate route/CAS tests: 3 PASS. Restoring the exact old consumer makes the route-removal control fail. Complete outputs are committed under `checks/`, `controls/`, and `independent/`.

The full architecture check is FAIL: the complete deep-import collector has 153 new violations after removing 12, with zero new ones from this slice. Remaining IR/Foundry export admission and generated OpenAPI/trust-posture boundaries have exact owner packets; patches are reviewable and not applied. The global red is not called inherited. Finding closure and G code acceptance remain separate.

`../core-import-route-r3.json` pins the implementation source, full footprint, commands, inputs, outputs and next owners. Its publication SHA is read back after the separate evidence commit.

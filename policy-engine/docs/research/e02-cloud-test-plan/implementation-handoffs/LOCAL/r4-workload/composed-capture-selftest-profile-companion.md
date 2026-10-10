# Composed capture self-test profile companion patch

Target source: `LOCAL/raw/composed_mac_capture.py` at SHA-256 `4896e0126cc742987358068d1220b338bd57ee9c5f8ec570b954feb40598654e` (matches the assigned preimage).
Patch artifact: `LOCAL/raw/composed-capture-selftest-profile-companion.patch`
Patch SHA-256: `86ecac14a379165d10a2e781e460e5a244a0db44e402756bec3ebafb5c7b0e25`

Exact preimage around the synthetic `run_one` call:

```python
    original_inspect_live_identity = globals()["inspect_live_identity"]
    identity_sequence = iter((boundary_identity_before, boundary_identity_after))
    globals()["inspect_live_identity"] = lambda *_args, **_kwargs: next(identity_sequence)
    boundary_command_dir = root / "synthetic-source-drift-command"
    boundary_command = {
        "id": "SYNTHETIC_SOURCE_DRIFT_BOUNDARY",
        "order": 1,
        "phase": "light",
        "command_type": "python",
        "argv": [sys.executable, "-c", "print('synthetic boundary stdout')"],
        "cwd": str(Path.cwd()),
        "environment": {},
        "outputs": {
            "directory": str(boundary_command_dir),
            "stdout": str(boundary_command_dir / "stdout.bin"),
            "stderr": str(boundary_command_dir / "stderr.bin"),
            "metadata": str(boundary_command_dir / "metadata.json"),
            "junit": None,
        },
        "purpose": "prove post-command source drift blocks PASS",
        "prior_wall_time": None,
    }
    try:
        boundary_result = run_one(
            boundary_command, {}, run_dir=boundary_run_dir,
            plan={"execution": {"output_root": str(root)}},
            plan_path=Path(__file__).resolve(), frozen_commit="synthetic-commit",
            frozen_tree="synthetic-tree", plan_sha="a" * 64,
            input_manifest_sha="b" * 64, versions={},
            source_manifest_path=root / "synthetic-source-input-manifest.json",
            source_manifest_sha256="c" * 64,
            expected_wrapper_sha256=tool_hash_good["actual_sha256"]["wrapper"],
            expected_plugin_sha256=tool_hash_good["actual_sha256"]["plugin"],
        )
    finally:
        globals()["inspect_live_identity"] = original_inspect_live_identity
```

The required profile digest is computed from one explicit `synthetic_source_drift` self-test profile, and a local reader mock returns that exact profile for the before/after reads. Both monkeypatched globals (`inspect_live_identity` and `read_product_python_profile`) are restored in the same `finally`. The mock is limited to this synthetic run; the real product runtime reader and profile freeze check remain unchanged. The expected outcome still asserts `FROZEN_SOURCE_IDENTITY_DRIFT` with before `PASS` and after `FAIL`.

No source changes or process/test runs were made; this is a patch artifact for parent review/application.

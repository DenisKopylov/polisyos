# Executed continuation controls, 2026-10-10

Author capture; product capability and G acceptance are not established by this harness.

Source anchor: `ae767c1360019a32496c18c77c4c691a0aa86a06` with the explicitly listed helper bytes from `raw/continuation-oracle-canonical-temp-verification-20261010/command.json`. The selected wrapper was `c9d6c5b77335e7833323f6616de94c743bc39ec05fd62f17d68f802857aac5a9`; source-before/source-after hashes match. The actual command exited 0 in 6.965 seconds.

The first run (`raw/continuation-oracle-verification-20261010`) failed before pytest because the macOS `/var` alias did not equal the resolved `/private/var` product root. One oracle fixture line now resolves its newly created temporary root. No production admission was relaxed.

The successful run used `python -B`, `PYTHONDONTWRITEBYTECODE=1`, empty `PYTEST_PLUGINS` and `PYTEST_ADDOPTS`, and one numerical thread. It executed all six scenarios through the real queue, pytest subprocess capture, origin plugin, JUnit parser, and output inventory. Source and runtime-profile admission were explicitly synthetic fixtures.

- `continue-positive`: `SELECTED_RANGE_COMPLETE_WITH_FAILURES`; first `FAIL`, second `PASS`.
- `default-stop`: `STOPPED_UNRUN_REMAINDER`; first `FAIL`, second `UNRUN`.
- `source-identity-after-command-one`: `STOPPED_UNRUN_REMAINDER`; first `FROZEN_SOURCE_IDENTITY_DRIFT`, second `UNRUN`.
- `output-inventory-incomplete`: `STOPPED_UNRUN_REMAINDER`; first `FAIL`, second `UNRUN`.
- `profile-after-command-one`: `STOPPED_UNRUN_REMAINDER`; first `FROZEN_RUNTIME_PROFILE_DRIFT`, second `UNRUN`.
- `profile-before-command-one`: `STOPPED_UNRUN_REMAINDER`; first `FROZEN_RUNTIME_PROFILE_FAIL`, second `UNRUN`.

The continuation positive retains the first FAIL and returns a nonzero queue result while allowing the second PASS. Default stop and source/output/profile corruption leave the second command UNRUN. This proves queue-control behavior, not scientific, production-currentness, or finding closure.

Full stdout: `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/continuation-oracle-canonical-temp-verification-20261010/stdout.txt@0845a2fe03c8e38b864ff19e630ed5bddf1b969859dedb22548e4e4206b8860b` (110283 bytes). Full stderr is retained and empty. Command metadata: `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/continuation-oracle-canonical-temp-verification-20261010/command.json@31c560993d6296223660612cdbe4e98b15dd9645947fb35970eeaf853974b736`.

The complete child captures, JUnit, source fixtures, plans, receipts and completion events are retained at `/private/var/folders/zm/nt7795nd0djbxr7ctd5yl4p40000gn/T/composed-continuation-oracle-f9vqb8en` and were available at readback. They are not copied into Git; the retained stdout names their individual paths and hashes.

A later self-test-only wrapper companion remains under independent review. Rebind any executed helper delta before final freeze; this receipt does not name a future receipt SHA or the final source identity.

`closure_ids=[]`; author proposals only.

## Executed wrapper V4 delta

The six controls were rerun at source anchor `9194a65fb59355ceac35270c869f429efc7482d8` with wrapper `8d4c418a7966915d45e5a4821e548fe6b80cce1cdf8fb81f7380e12b439f9454`, oracle `3adb2ebc1b2a4caca8a0f3a43c0a29b421adc2b9260f98eff869de85f63ecf31`, and origin plugin `02e43a40767d23f2e042ea8d1d0c4db3585b3697de38db50e79e6e8136175352`. The actual command exited 0 in 7.679 seconds; all three source hashes were unchanged. All six scenario outcomes above were preserved. This delta does not establish the separate full self-test or any product capability.

Complete deciding output: `raw/continuation-oracle-v4-wrapper-verification-20261010/stdout.txt@33edfed00d98eb8d26262a9dc6ae07926fe3bd936bd01df7a4116af2fa9ae078` (110283 bytes); stderr is retained and empty. The same directory contains the exact argv, numerical/environment settings, before/after hashes and output inventory in `command.json`. Final composed replay and source/input/profile freeze remain pending.

## Executed output-only binding admission delta

All six continuation controls were executed again at source anchor `9194a65fb59355ceac35270c869f429efc7482d8` with wrapper `9a3e67d963d84c9475f9f9d04df14392501bb3c43d36cfe587b45485be15de81`, oracle `8f10420960a5482a13d6985e7dc1193de499b4afd31effc09bc8cb441dbcac7a`, and the unchanged `02e43a40767d23f2e042ea8d1d0c4db3585b3697de38db50e79e6e8136175352` origin plugin. Exact before/after hashes match. Exit 0, wall 9.482 seconds; all six recorded scenario outcomes remain the same. Complete deciding stdout is `raw/continuation-oracle-output-kind-wrapper-verification-20261010/stdout.txt@298ea210feb4e39ba57ca45552d1f0888696a2f2fcd9a8c8cda752aa77a41a32` (110283 bytes); the sibling command.json retains actual argv, environments and output inventory. This remains a harness-control receipt with synthetic source/profile admission, not product closure or the complete final self-test.

# C97 immutable execution recipe r2 — not a new Cloud commission

This is a bounded future execution recipe for the repair author proposal, not permission to claim a completed installed result. It has **not been executed**. Root must publish/rebind the composed candidate and issue the eventual self-contained task. Do not run this against an arbitrary moving HEAD. The source implementation input examined here is `d9397c7c0458ec2980fa58115c5ee597eb58dbc8` / `832c6d744f3f09f261fbd8c72dc647109e2baceb`; the actual delivered new-test preimage is Git blob `38069b822aae8c0ae1ac20ec1612382ef43465d7` / SHA-256 `b6ed5965e172a12cf2344472a8efc18968733428844a9f8ed0a9f6f120d743b3`. The effective repair footprint is enumerated in the sibling RAW manifest and patch, not an invented worker commit. Original standalone commission SHA-256 `6371825f41d5643f0c7e61a24b827d1c287299bb71410dc84eb85f03a397a3eb` governs remaining C97 resource/FQN/discovery/control obligations; this recipe closes only its concrete return gaps.

## Stop conditions and inputs

Read actual branch/HEAD/tree/status first. Managed Cloud `work`, detached HEAD and no origin are valid on exact admitted identities. A source mismatch is reported with actual identities; no reset, rebase or blind branch change. Runtime source pins below must match immutable Git, not Root WIP. If Root composes different input commits, regenerate/review the commissioning pins and binding before launching. The test compares its binding to actual child-read Git HEAD/tree and loaded source blobs; it has no moving-HEAD exception or permanent historical commit assertion. No production data, credentials, private RAW/CAS/DB, VM, Colima or host history belongs in this work. Root's authentic mixed/untracked repository census is independent/local; the stopped Colima stays stopped.

Before setup measure actual total/free disk, effective cgroup RAM/available memory, CPU quota/affinity, cache/prefix/scratch growth and backend versions separately. About32GB total disk is neither RAM nor guaranteed free space. Use one measured build/install/pytest/control phase at a time initially, independent task authorship can continue. Source metadata estimate at the input is 20,696 tracked sdist-selected paths /618,224,690 bytes; inspect actual Hatch selection and available space, not this estimate alone. Set explicit measured command timeouts and numerical-thread limits; report SIGKILL/137 as its observed process outcome, not a diagnosis.

Supported existing Cloud preset is CPython3.14.x, uv0.9.21, native pytest.ini/default plugins/importlib/strict markers. Prefer existing dependency environment. If required, make at most one bounded supported `uv sync --frozen --extra lint --extra test --extra runtime` attempt; preserve exact full compact setup stdout/stderr/command/exit and policy result. Respect configured network policy; no firewall/proxy workaround, tool configuration change or alternate installer/profile to manufacture strict PASS. A403/cache gap/backend absence is setup ERROR/affected UNRUN, not product FAIL. Missing app Hatchling is not the isolated-builder result; the canonical five-wheel builder exists below. Do not install anything on Root's Mac for this recipe.

## Reuse the source-owned Q2 flow

Load only the verified `q2-packaging/raw/run.py` functions after hashing the source file; do not invoke its full historical `run_wave` (it adds unrelated GCP/worker matrices). Source is the admitted checkout itself, not a full copied source checkout. All fresh run/output/build/installed paths must be outside `policy-engine`'s native Hatch includes, and installed prefix + neutral CWD must be outside checkout ancestry to prevent `_worker_directory` ancestor fallback. No source environment recreation; fresh isolated task prefixes in Cloud are necessary artifact consumers, not copies of Root's environments.

Use the actual signatures from the pins below, in order:

1. `q2.load_source_bound_build_tools(repo, SOURCE_COMMIT, product)` validates pyproject→profile→helper→lock against Git bytes. Get the exact five-wheel closure with `buildtools.load_lock(lock_bytes, expected_sha256=...)`, then `buildtools.fetch_locked_inputs(lock, wheelhouse)` only if the verified quarantine is absent. This is the existing bounded official-artifact route (five universal wheels, max1MiB); retained quarantine goes through `validate_quarantine`. Capture actual fetch/setup errors, do not stop on `origin`403 first.
2. `q2.configure_build_env(uv, base_python, lock, buildtools, wheelhouse, run_root, env, logs)` creates the native build-tools prefix with offline/no-index/find-links/only-binary/no-deps/require-hashes. Keep its actual build-tools origin and setup outputs. Do not ask arbitrary app Python to import Hatchling instead.
3. Derive the actual assets with `packaged_resource_contract.py source --product-root <product>` and the existing Q2 asset mapping. Use `q2.run_build(..., wheel=True, sdist=True, ...)` on admitted source, `q2.verify_wheel`, `q2.verify_tar_assets`, then `q2.product_root_from_sdist` and `q2.run_build(..., wheel=True, sdist=False, ...)` for rebuilt wheel. Reject duplicate/traversal/symlink/special archive members through the existing helper. That native sdist extraction is a required build artifact, not a second working checkout. The helper may hardlink identical immutable source bytes: do not edit extracted members; bind before/after source hashes. Compare actual wheel member/content maps excluding only RECORD self-hash and documented native timestamp/container differences. Never infer equality from filenames, artifact existence or size. Preserve deciding archive inventory/comparison outputs.
4. `q2.configure_installed_env(uv, base_python, run_root, dependency_site, product, env, logs, origin_gate_source)` provisions purelib-first, dependency site appended unprocessed, no .pth processing. Use one prefix sequentially for source-wheel and rebuilt-sdist-wheel profiles. Install the selected wheel exactly with `uv pip install --offline --reinstall --no-deps --python <installed_python> <wheel>`. Check .pth absence. Existing resource/FQN/discovery consumers remain defining companions; do not narrow them to this one census test or add fake worker inputs.
5. For each artifact profile write a regular `installed-binding.json` with the fields below, derived from **actual successful build/install commands and outputs**, not a handwritten PASS declaration. Retain the hash-bound full build-chain receipt, source readback, actual archive member/content comparison and tool/profile outputs; the test cannot establish build-authority from a JSON flag. Source identity and build-chain admission are independently reconciled by the harness/reviewer, not recomputed by each census child. The child separately rereads actual wheel/installed RECORD/member bytes, actual Git HEAD/tree and each loaded product source blob; build execution and unloaded members remain the separate Q2 proof.
6. Before freezing the first installed profile, load the replacement test under an explicit task-only module name without product imports (pytest is an external locked dependency), and call its `prepare_child_observer(binding_path)` exactly once per fresh prefix. For the sequential second artifact profile reuse that exact observer/sitecustomize unchanged, create the new binding from actual artifact/install outputs and carry their measured hashes; do not call the one-time hook again. It appends a read-only observer to the Q2-created sitecustomize; it does not install or modify product source. The binding records observer/sitecustomize hashes. No root conftest, editable fallback or PYTHONPATH injection. Observer SHA-256 is `4854906bb0e6424f6079b53269a143ebe68cb7c5019ba647d9b734d7c9d1d316`. Freeze this harness source with actual source/member readsets before the expensive composed wave.

Required binding schema (absolute local task paths, never credentials):

```json
{
  "schema": "policyos.e02.c97.installed_binding.v1",
  "source_commit": "d9397c7c0458ec2980fa58115c5ee597eb58dbc8",
  "source_tree": "832c6d744f3f09f261fbd8c72dc647109e2baceb",
  "effective_source_manifest": {"path": "<actual sparse footprint/source-readback receipt>", "sha256": "<actual>"},
  "build_chain": {"outcome": "PASS", "receipt": {"path": "<regular delivered build receipt>", "sha256": "<actual>"}, "steps": ["source_wheel", "sdist", "safe_sdist_extract", "rebuilt_wheel", "member_content_comparison"]},
  "wheel": {"path": "<actual selected source or rebuilt wheel>", "sha256": "<actual full wheel hash>"},
  "prefix": "<Q2 installed prefix outside checkout>",
  "python": "<prefix>/bin/python",
  "cli": "<prefix>/bin/polisyos-tools",
  "purelib": "<actual prefix purelib>",
  "dependency_site": "<existing managed app dependency site, appended without .pth>",
  "checkout_root": "<actual admitted checkout>",
  "neutral_cwd": "<task-owned neutral directory outside checkout ancestry>",
  "output_dir": "<task-owned existing outside-checkout evidence directory>",
  "q2_origin_gate_sha256": "8acde537d5588648e042384f38e18359e6b3a103d03e8af79fca226989ae6872",
  "q2_sitecustomize_sha256": "<actual Q2 pre-observer sitecustomize hash>",
  "child_timeout_seconds": "<replace with measured positive integer; never leave this string>"
}
```

`prepare_child_observer` adds `observer_sha256` and `observed_sitecustomize_sha256`. Positive/restored bindings omit `control`; only the exact frozen installed M1 arm sets `control="M1_NUL_parser"`. Paths/bytes must exist; missing/bad inputs are ERROR/SKIP/UNRUN as applicable, never an inferred product defect. The current oracle deliberately refuses unhandled wheel `.data` remapping rather than guessing an installation layout: if actual artifacts contain it, preserve the useful result and extend the existing Q2 mapping under one owner before claiming installed proof.

## Exact bounded test execution and M1 discrimination

Do not repeat unchanged old source checks merely because documentation changed. Recover the three missing original logs if accessible; otherwise list each unavailable locator and exact missing command. The new source is unexecuted. For each selected actual artifact profile, use this test alone with an explicit fresh base-temp/cache/output and full quiet stdout/stderr/JUnit. Run the installed controller from neutral CWD with its actual installed Python, default plugin discovery and the pinned native pytest.ini. Disable only source conftest (`--noconftest`), which otherwise injects source paths; retain strict markers/importlib/plugin profile. Record this intentional installed-profile boundary; it is not the old native source-wave profile.

The command shape is:

```text
<installed_python> -I -B -X pycache_prefix=<fresh controller cache> -m pytest
  --noconftest -c <checkout>/policy-engine/pytest.ini
  --basetemp=<fresh outside-checkout fixture temp>
  -o cache_dir=<fresh outside-checkout pytest cache>
  --junitxml=<regular evidence>/installed-census.junit.xml
  <exact logical candidate test path>::test_installed_census_exact_git_denominator
```

Supply `C97_INSTALLED_BINDING` only to this task child environment, unset PYTHONPATH. The test derives the complete28-item literal cohort extent (2entrypoints×2root contexts×7scenarios); actual framework collection/JUnit is the only executed-count authority. Full node IDs, pytest-controller PID/profile/plugin/options, each actual CLI child PID/profile/origins/RECORD/member/content readset, every independent oracle's Git command/raw bytes and complete stdout/stderr are deciding evidence. Quiet means no redundant debug/payload, not altered checks. The test writes oracle bytes before semantic assertions so an intended M1 failure retains its deciding inputs. Direct console actually uses its shebang; isolated module actually reports its `-I/-B/-X` flags. Missing observer report is red, not caller-assumed origin.

Run positive → **same exact assertion under frozen M1** → restored-positive using fresh interpreters/cache each arm. Retain original installed scanner and installed RECORD bytes in task-owned bounded control storage, not a full prefix copy. Reconstruct M1 from the frozen control recipe: rename only `_git_status_paths` to `_c97_preserved_git_status_paths`, insert the frozen naive `.splitlines()` wrapper. Required original scanner hash `c12cefb7dda1b82ef0f7e309421c5cbccc6804a3ab60bf27d1aa674f43df7e1a`, M1 hash `26fcae7b668aa91a9ca8c6b63ddc02ff673812e340f5b547e87e679630e377fa`. Reconcile only that installed file's RECORD hash/size and declare the exact M1 override so origin integrity cannot steal the semantic discriminator. Confirm the child origin report passes in the mutant arm; at least an actual `working_tree_changes` equality must then be red, not a fixture/setup/missing-backend failure. Preserve actual failing node/output. Restore exact source and original RECORD, omit control, fresh same positive must pass. If M1 remains green, the oracle is still inadequate: report that actual result, do not edit the mutant to teach the test.

M2 resource removal, M3 dynamic-callable origin, FQN/registry/model resources, actual discovery/bootstrap and ordinary native worker-resource readers remain separate from this scanner test. Reuse the existing original C97 obligations and Q2 consumers; do not claim these finished from28census cases. In particular M3 must return one legitimate ConnectorComponent; an empty fake factory is insufficient. No real DoWhy/GCM fixture is supplied here; numerical worker result stays UNRUN. Do not lease canonical Core/IR/lifecycle/shared owner without Root's exact separate lease.

## Delivery / failure policy

Managed snapshot/diff delivery is primary. Before costly work prove a tiny regular source/new-file/receipt/evidence byte transfer through that channel; an origin fetch/push failure does not block managed delivery. All necessary bytes, including full deciding output, must reach Root and be rehashed; a Cloud ignored path plus SHA is not delivery. Keep exact moderate regular files under an explicit allowlist, or losslessly gzip full deciding logs when useful. Class A (implementation/reproduction/G-decision) and D (irreproducible deciding witness) must be delivered through an actually available channel. Class B reproducible wheel/sdist/env/checkout/dependencies/cache/fixtures → recipe/Git identities, not copied artifacts; C noise/duplicates → exclude. If a particular wheel byte is decisive and unreconstructible, state that bounded A/D exception and prove transport first. No entire RAW/tmp/case archive, symlinks, source/environment copies, CAS/DB or credentials.

Deliver replacement source diff/new files, compact receipt, exact delivered-file uncompressed inventory (relative path, bytes, SHA-256, kind), command/profile/setup/resource/readset receipts, full deciding stdout/stderr/JUnit and control/restoration outputs. Publish no fake final commit: report actual entry/final commit/tree and any uncommitted effective footprint; if normal authorized topic commit succeeds, hooks run normally and managed diff/remote readback remains checked. No origin/push prerequisite, main/integration/G edit or new Cloud task from this recipe.

An unsupported setup stops only the affected phase: preserve error, attempted supported route and available useful partial; do not invent backend, authority, log bytes or product FAIL. Routine bounded fixes under the oracle owner are allowed by the eventual commission; shared owner conflicts or true architecture choices return a concrete question and useful result, without waiting for midrun Root messaging. Outcome categories PASS/FAIL/ERROR/SKIP/UNRUN remain separate, authored versus independent versus G. `G_acceptance=false`, `closure_ids=[]`.

## Immutable source pins inspected for this proposal

The complete explicit pin denominator here is20regular Git files (19 inherited pins plus the actual source entrypoint owner), not a runtime closure. No product import or command from them ran during preparation. Read all mandatory companions and actual executed finite imports when qualifying the future run.

| Path | Git blob | SHA-256 | Bytes |
| --- | --- | --- | --- |
| `AGENTS.md` | `0f724f52375e8e08321e3f12fcd5244a799e01b8` | `424b84e3280df143219fe27e28149088f9e92b947e4956b2103388e11849e65c` | 22824 |
| `policy-engine/CONTRIBUTING.md` | `8ff414198e306e671abff1f76f31330a1f29d765` | `e78f1bdb99a900f6426f9f451b7e9cbc0e21007eb12012eaf209d89c505f3a1f` | 12253 |
| `policy-engine/docs/research/e02-cloud-test-plan/execution-prompts/HANDOFF.md` | `b9f1a717049d9e30f68bf291e3f8321013abf83e` | `8519f95eb0ff2ec2c64caa4497eb58b957fe7cd47a0a6955bad98a2c20795d3b` | 20260 |
| `policy-engine/docs/reference/policy-design-case-failure-patterns.md` | `7c9ad5e7232cf57723fdb5bc0d79bfd683df7ad1` | `2f354479f1556d18b3761bc5b0672b6857fc683cb7de4c2d829b71823b6896fa` | 76242 |
| `policy-engine/docs/how-to/author-measurement-instruments.md` | `87e53083e82965c1af418e1db62b56e50610e440` | `aff79970df5d0ba029e4fd3bc519e91210a4cbb4c4e6d36efd2cfee1f57d49dc` | 5387 |
| `policy-engine/tools/quality/validation/schema_fqn_census.py` | `247f7d3517146a04bf908b6167e835f020f6c9b9` | `c12cefb7dda1b82ef0f7e309421c5cbccc6804a3ab60bf27d1aa674f43df7e1a` | 53134 |
| `policy-engine/tests/unit/remediation/test_dfk_01.py` | `1148ccda5ee8188639a5e6411beab3112a380ecf` | `7dbe0afc7a53521c7919376c80820b2677e1f9aad70d1c42e2ddd4228b0b5031` | 82470 |
| `policy-engine/tools/lib/fs.py` | `e0c3311b75bf07863695b9b6220fa8c1ec26869e` | `0ddf42f824ddfe55386f5d5d63b39cacfb53f73dad03d8d2158f19a6b9a15119` | 35453 |
| `policy-engine/pytest.ini` | `f6b18091a37290d7b5c375b3aef44ffebc0a293a` | `61270205a9f573a090b3c051a4b78351e67308a49e21660dbf33e76186d799eb` | 1021 |
| `policy-engine/pyproject.toml` | `e4bb0ae9d77ae3bbb4b961ddd8f5f7e2e597ca51` | `5f65308cb088086b6fc0aa40a5bae6ed852ae3a2e261103bd0d4158d97c1e8f2` | 11241 |
| `policy-engine/hatch.toml` | `1355bf80299b4d3f37cdf915d75c00987742ae1d` | `b30a89dcdcfba3e94915be920d2a060fe991f7364c4501a66e529b4bed812bef` | 2443 |
| `policy-engine/uv.lock` | `c34f9273799807fbf0bb95a30668f75a4c4e69a9` | `ccfdca0e741dc77795f5af61871af5d62e73feebf55c7ffb28cd16e55fe207e9` | 808851 |
| `policy-engine/tools/quality/validation/q2_build_tool_wheel_lock.py` | `0a1a91a52bb05ef5f190d50c718813518df2aab0` | `86f31671b26c84baa9a7a1647553d8e42d5d8cab154097c285393742738ec8bd` | 47766 |
| `policy-engine/architecture/packaging/q2_build_tools.toml` | `6cfc6b37405d8f71057de279096557974ca99770` | `d2fb004d6c274e85ba2f45f051f4fad9a05fc62da3d598bad4be76eaa5bef6da` | 973 |
| `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/builder-inputs/hatchling-1.27.0-wheel-lock-r1.json` | `ab000778e6f18d7bd5368b5473ab528835bfa503` | `51eeac7775d87981a1da901ac23c1e86a666cb149234265b4a3c8b24ff4c93ad` | 9415 |
| `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/raw/run.py` | `cd11f63f5ea64a1a0982790692e421e6b4297773` | `174a9547ce879ed8487185415de1aaf4f65299f5bab35d3ebcf6c724bdaee693` | 129299 |
| `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/raw/installed_origin_gate_r4.py` | `2cc9a824c439f56ef67c9a6e6654d4dbb8641633` | `8acde537d5588648e042384f38e18359e6b3a103d03e8af79fca226989ae6872` | 15945 |
| `policy-engine/tools/quality/validation/packaged_resource_contract.py` | `e10b67a161b5b712a2e3b5c2fa156cfe4a61dfac` | `567db40d937a281f7edfcfc420d51022dca9240c6357eb7512bde1b8995fd226` | 30711 |
| `policy-engine/tests/integration/fabric_ir/test_fabric_installed_provider_origin.py` | `c4a545ef4b20eb2e8c19466bd7359962c76a4158` | `9a6c187334d9286405d980bc93843fe0ac616ae4555c5570e33a2e2d492d8765` | 28214 |
| `policy-engine/tools/cli.py` | `eecca6679e79a9335187a57db58b3eec386c5d2e` | `c8050cd2ab1bc46bd3792ba772470e758efdb8c35bcb28b110eb3ba558b501c9` | 25923 |

## R2 entrypoint profile reconciliation

This revision is a source correction for `C97-R1-ENTRY-01`; r1 is immutable. The actual source-owned declaration is pyproject `polisyos-tools = "tools.cli:main"`, with the wheel's real entry_points.txt reconciled against it. `tools.cli` is a source module (`tools/cli.py`) at this input, not a `tools/cli` package. Use the same two actual CLI commands above; do not import the canonical alias as a workaround for `-m`, add a package stub, change invocation to make a guessed path true or drop its binding.

For `-m`, the observer binds the real `__main__` spec/origin/standard-source-loader/member/RECORD/Git bytes through an explicitly labelled Q2 entry-module view; it does not require `tools.cli` to exist in the module cache. Preserve all genuine cached module subjects separately. For the direct console script, bind the actual loaded declaration target through that same module invariant, while retaining the real wrapper's installed RECORD/shebang and callable identity. It is installer-generated code, not a wheel/Git module. Add exactly the small actual `<prefix>/bin/polisyos-tools` regular-file bytes once per artifact profile to the deciding delivery allowlist, along with its hash/size/installed RECORD key and installer version; do not copy the prefix.

No runtime was run during r2 preparation. Root still owes physical logical-path Ruff/format and typed release-fragment validation before publication, and the future exact actual installed positive/M1/restored execution. Those are current UNRUN checks; the old32PASS/3SKIP records and unavailable logs are unchanged.

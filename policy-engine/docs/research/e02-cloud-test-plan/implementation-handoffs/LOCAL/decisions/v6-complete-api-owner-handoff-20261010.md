# V6 fresh-reader container owner handoff

Status: patch-only test-fixture proposal. No test/source file was changed and no test was rerun. The patch keeps the real tenant ownership checks and all source-status assertions intact.

## Retained failure

The exact replay is retained under `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/v6-owned-local-withholding-fresh-reader-verification-20261010/`:

- `command.json` SHA256 `bb2d4177144c16e70f99d15543135f884c2fe18ed2fe47e2b131c2d73d1cdd4e`
- `junit.xml` SHA256 `289a2363c5c5cc519ff56660d09c1fa60585c7591fcd218f6dafe84a9ef45913`
- `stdout.txt` SHA256 `9016f391a03b4fe82ab37990595be8e53c1ba2f3c8f773f9d0c29a46ab02c3b6`
- `stderr.txt` SHA256 `bce3b97547bcc01a83cb0e9b1e29bce5515c3c8d10cef56cecba29e696c5c466`

The pinned command ran two fresh-reader tests and both failed at `create_runtime_api_app` before GET assertions. `RuntimeServiceContainer.build` constructs `PromotionRuntime`; `PromotionRuntime.__init__` writes its verifier-provenance bytes to the app store. The blob `sha256:6d7a8b8916a5e3ae26d61ec5fb8fe5f2daf5c69682ad35feeb778fc4bde21ab0` already had fixture-tenant owner claims. App construction was outside any tenant scope, so the ambient CAS had no active owner and correctly refused the write with `ArtifactOwnershipError: ... has tenant ownership claims; an active owner is required for write`.

Relevant current source paths and hashes:

- `tests/unit/runtime/http/test_control_service_di.py` — `eb124217b23c0a6a9d71b0290497ca3f39be3190aabd6dd96fb8efff25e6db76`
- `src/polisyos/runtime/http/app.py` — `b726343afe9b1a57fed71c78b733bfd5e606d0ffebbb2d7fa84b67ed8b6a9ba0`
- `src/polisyos/runtime/http/container.py` — `9b96fa1cd315b5ebe715352232ddeddb3a0ce874798e36f75344ed714a31a29a`
- `src/polisyos/runtime/http/dependencies.py` — `cbb66e72eadfa8add29f26480a1966c2aa5f831cb82c3f199986e5b0105f1cba`
- `src/polisyos/runtime/quality/open_world_risk.py` — `1f6a6fd281cc580b112092a6913fb45ae7d8b2819f6af2e78e6939273a15dbcd`
- `src/polisyos/runtime/http/services/control/generation_cycle.py` — `c4492d44e17df4c18364bf1e23aee3dd9c346d3a12f3b689e341e86c288f35c9`

`create_runtime_api_app` already accepts `RuntimeContainerOverrides`, but the container context and services require exact store identity; injecting the independently built fixture `ControlPlaneService` alone would not preserve those bindings. `build_runtime_api_context` constructs its ambient-owner store from the configured CAS root. The existing `tenant_scope(None, tenant_id=..., cell_id=...)` is already used by the controlled fixture and is the existing ambient owner source read by `FileSystemCAS._resolve_owner`.

## Minimal patch and classification

Patch: `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/v6-owned-local-withholding-fresh-reader-verification-20261010/v6-complete-api-owner-handoff.patch`, SHA256 `8b71d2c2d72a4914178f58e77537278b695cbffa68c659dec71976c492d4d0fb`. It only wraps each of the two existing `create_runtime_api_app` calls in the same declared `tenant-fixture/cell-fixture` context as the artifacts being inspected. It creates no owner claim and does not change the source store, container, or runtime guards.

This is P40 **same class, one level deeper**: the first mismatch was unscoped fixture writes; this one is fresh-container initialization with no active owner after those tenant-owned writes. The relevant P38 property is authorization by the current owner index, not the presence of matching tenant strings in a manifest. The test context makes the already-declared fixture owner active during the constructor write, allowing the existing CAS owner check to govern it.

The prior patch remains part of the target fixture state: the producer CAS is tenant-scoped before profile/source/context writes, the exact root source resolves under that scope, and a foreign tenant/cell view refuses the same ref. The fresh GET must continue to report `resolved` for the scoped source while preserving the producer's `generation_unavailable` result, no recursive child bindings, and the separate historical L2 confidence-withheld N5 assertions. No positive recursive-child or V6 closure claim follows from this test-only owner handoff.

The patch is not applied or tested; its behavioral effect remains unverified.

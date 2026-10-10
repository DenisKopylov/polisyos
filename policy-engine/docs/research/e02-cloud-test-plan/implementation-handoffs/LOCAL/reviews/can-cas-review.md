# Independent CAN/CAS foundation review

Target: commit `a35aff3bc320150aa58273149db0e58ce96c5156`, tree
`3d12461ad6345bf0f664c8b26e4084db1b49705d`, parent
`e89927b645469f1981750e7d13ae5cdfc590b7e7`. Review was read-only for
production code and tests.

## Finding

**F-01 — Medium, high confidence — P37/P38; same-class P40 unbound-import
admission.** The committed Core artifacts guide says scoped imports require the
manifest tenant/cell to equal the active owner and that unbound imports refuse
(`src/polisyos/core/artifacts/README.md:135-142`). In code,
`_require_bound_context_for_owner` accepts `context is None` unless
`require_bound=True` (`src/polisyos/core/artifacts/store.py:2781-2802`), while
both intake and staged-publication callers omit that flag (`store.py:2973-2976,
3222-3225`).

I reproduced the divergent case against this commit with real `FileSystemCAS`
instances: an unscoped source exported an artifact with `tenant_context=None`,
then an empty target scoped to tenant B/cell B imported it with
`verify_integrity=True`. Import succeeded with two published files; the target
manifest still had no tenant context, tenant B could read the bytes, and B
received ownership/view claims. This is the property/code divergence if the
guide's fail-closed rule is intended. The local CAS receipt instead says absent
context does not block a first claim. The two sources therefore disagree about
the intended contract; the committed code implements first-claim adoption.

This is the **same unbound-import admission class**, one level deeper, rather
than a new class. Per P40, do not add a narrow instance patch before resolving
the policy. The smallest closure is either (a) require a matching bound context
for new unclaimed imports at both admission and publication, retaining any
explicitly intended exact-owned unbound no-op, or (b) ratify first-claim
adoption and amend the Core guide to say that only an explicitly foreign bound
context refuses. If (b) is selected, add a real-CAS test pinning the first
claim's ownership while proving the manifest remains unbound.

## Other reviewed properties

- **Mapping options:** the Core-to-IR adapter projects the complete declared
  `ArtifactWriteOptions` field set, rejects unknown fields, and validates
  supplied mapping values before the Core write (`core/artifacts/ir_adapter.py`).
  The test writes a `MappingProxyType` through a real CAS and checks every field;
  malformed and unknown mappings assert no artifact was published.
- **Raw profile law:** the IR reader requires raw manifest bytes, rejects
  duplicate JSON keys and non-JSON constants, requires every profile field,
  rejects profile-less history, and decodes/re-encodes with byte equality
  (`ir/artifacts/io.py:95-212`). Selected refs are forwarded unchanged for both
  profile and payload reads. The IR README correctly says a profile is a
  decoding declaration, not producer provenance. It also explicitly preserves
  the Core/IR tag-family boundary: Core-only `float_hex`, `bytes_hex`, and
  `array_digest` remain unsupported despite the shared name/version.
- **Selected cache refs:** write-through reads resolve the remote owner's exact
  view before checking a local hit; raw manifest reads go to the owner, and
  exact-view cache population imports original manifest/signature bytes. The
  selected-view and durable-owner tests exercise those paths.
- **CAS admission/report behavior:** the committed real-CAS fixture covers
  directory, archive, and exact imports against an existing foreign owner,
  with and without a cell; it captures persisted state and fresh public
  readbacks before asserting refusal. Its property-removal run demonstrates the
  actual escape: a new selected manifest and tenant-B reader/owner claim appear.
  Content damage, truncation, post-intake source mutation, and a fresh-process
  read/corruption check are also covered.

## Verification

Ran the normal project harness on the pinned commit:

```text
.venv/bin/python -m pytest -o 'addopts=-ra --import-mode=importlib --strict-markers --benchmark-storage=file://./_cache/benchmarks' \
  tests/unit/core/artifacts/test_ir_adapter.py \
  tests/unit/core/artifacts/test_bound_import_preservation.py \
  tests/unit/core/artifacts/test_transfer_import_fresh_process.py \
  tests/unit/core/artifacts/test_multi_tenant_shared_cas.py \
  tests/unit/core/artifacts/backends/test_caching_store.py
112 passed in 4.27s
```

The root-provided property-removal receipt shows the test fails when claimed
admission is removed while markers remain. Root's composed Ruff and format
checks passed for nine files. No production, test, or configuration files were
changed by this review.

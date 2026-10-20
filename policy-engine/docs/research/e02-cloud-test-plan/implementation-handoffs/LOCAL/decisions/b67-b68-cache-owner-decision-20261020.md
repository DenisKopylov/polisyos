# B67/B68 cache-owner bounded witness — candidate packet

Status: **candidate for G review; not accepted**. Independent review marked the test-only candidate `GO_BOUNDED_TEST_WITNESS`. That verdict permits adopting one local integration witness; it does not establish production cache authority, a G acceptance, or B68 closure.

## Source and witness

The proposed adoption base is `ed5b52bc3db64ca477929a605f148d2140fe3955` (tree `0ce131a0928a23e7d2c003277b9766729bf3c691`), branch `codex/e02-unified-local-20261009`. The independent candidate was reviewed at `6dad99365eda4907b7128a24b1ab5c85ccc72d44` / `8dc7412484fa26c1b6211ae95477e7e5ca49959c`. The 34 reviewed source inputs were checked at d643, then rechecked at this adoption frame in `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/b67-b68-cache-owner-adoption-20261020-r1/source-advance-recheck-v1.json`@`066ca91a3b31a28cddb07e42ff7df16813fa9e0becd428f415a4a36aa4691811`. This is a bounded input check, not a whole-tree freeze.

The proposed test row is `policy-engine/tests/unit/scientist/orchestration/llm/test_factory_cache_composition.py`: preimage SHA `870e06c613de8f4c877f99f214d62e15c2bb73b29812460353ef66c45eaabbf6`, postimage SHA `89c39efbb7a0ebbf9168be0ec1b6bf0a37ca01f85378ef332339acd45bbedb13`. Independent replay: 2 passed, 0 failures, 0 errors, 0 skips; 2.892 seconds; max RSS 149,405,696 bytes. Review: `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/b67-b68-r2-independent-review-20261020/review-v1.json`@`b420c71b271d929508cf081e95a14e828aa1168d8e8b9161b1a5b9c30b69643c` and its Markdown companion.

The case exercises the actual factory and `CachingLLMClient`, a loopback provider, a fixture-owned currentness authorizer and FileSystemCAS snapshot, observer, budget middleware, durable ledger, and a fresh ledger reader. Four same-scope concurrent calls share one in-flight provider request and return distinct responses; reuse events are zero-cost and origin-linked. Removing the fixture grant and changing its epoch makes the same request miss. The owner/provider are local fixtures and cache state is per client. This establishes no deployment owner, live provider, production right, or cross-instance behavior.

## Product state and G choice

The last source census was at d643: 2,792 tracked Python files under `policy-engine/src/polisyos`, 10 factory invocations, and zero callers passing `cache_reuse_authorizer` (`policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/b67-b68-cache-owner-adoption-20261020-r1/current-source-qualification-v1.json`@`7a13dd445710da7f1fa06879a63542ba4ca4d681c8b8a4d61d050370a5aa10f1`). That denominator/callsite scan is not recomputed at this adoption base.

- **B67:** `producer_missing` and `bridge_missing`; no production producer/caller supplies the owner.
- **B68:** bounded local test evidence is ready for adoption; production-owner verification remains `verification_missing`, and formal closure is false.

`AccessScope` is principal context. It does not prove a cache-purpose grant, CAS binding, content right, or current grant epoch. `G_acceptance` remains `false`; `closure_ids` is empty. Option A is recommended now: keep the provider-miss default until an accountable owner exists. Option B is the preferred path when that owner and producer are supplied: wire them through the existing optional port. Option C requires an explicit G choice to add typed `llm_snapshot_reuse` permission, verified caller context, exact CAS binding, and a current grant/revocation source.

A positive production reuse needs an accountable owner/verifier and accepted trust root; exact actor/tenant/cell/scope/purpose; producer-owned immutable CAS reference/version and resolved bytes/hash; current rights for that snapshot and purpose; a live expiry/currentness/revocation or grant revision check per positive read; and owner-supplied issuer/revision bound to model and request digest. Those inputs are not established here. Live owner availability outside reviewed source/config was not queried.

Pattern pass: P05, P12, P27, P32, P37, P38, P40, P41. This is the same bounded local-owner/cache-reuse class, not a new production-authority class.

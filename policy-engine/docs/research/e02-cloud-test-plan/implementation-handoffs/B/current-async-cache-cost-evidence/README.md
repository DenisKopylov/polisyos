# B52 finite cache cost observations

The two native cases execute the real AsyncWorkflowExecutor and FileSystemCAS.
Each records one cold execution and twelve consumers that reopen both the CAS
and executor, while keeping a separate coroutine timer runnable. Cache-only
I/O has a 12 ms injected delay and still delegates to the filesystem backend.
Every successful consumer verifies the actual output, reads the cache bytes,
applies native state intent and preserves current unrelated state. One fsynced
producer effect per input distinguishes a hit from a declaration.

The full individual monotonic samples, complete stdout/JUnit and selected real
cache bytes/manifests are committed. Empirical nearest-rank p95/p99 measure the
finite 1 KiB and 64 KiB profiles. Warm return time includes recovery, validation,
read/apply, state/report persistence and finalization. These values establish
neither a latency SLA nor CPU serialization speedup. The native metrics consumer
records cache_hit; the local oracle separately measures neighbour wait and
serialized volume. A production dashboard for these new quantities is outside
this test slice.

The literal property removal changes four cache run_blocking_async call sites
only in memory. The same real cache, producer, trace events and verified reopened
cache entry remain, but cache I/O occupies the loop and no neighbour tick occurs
inside that write. Its native assertion fails. The auxiliary readback's first
incorrect field lookup is preserved as a harness ERROR, followed by the corrected
actual NodeCacheEntry.idempotency_key consumer. It is not a product failure.

The complete derived tracked-input and imported-module inventories remain at
their exact raw path/hash references. The transferable literal child reconstructs
and checks the source denominator from pinned Git objects. Committed compact
summaries do not replace those actual raw observations with new runtime claims.
Baseline cells and full job-context locators are navigation only; their archives
were not transferred. The candidate observations belong to c0431c5b0, not a
future integrated root source. Root/G must repeat the affected native file on
the final composed candidate and decide the full B52 criterion separately.

# R20 / G decision: separate producer implementation identity from execution cache state

**Request:** select the semantic boundary for source-bound MethodJob evidence. This is a decision packet, not an implementation receipt. The existing SourceUnit law is unchanged. Nothing here grants score, GP, warm-start, promotion, or publication authority.

## Decision to make

Should a MethodJob's producer identity bind a static, selected implementation/environment basis while a separate per-attempt witness binds the exact fit inputs and cache result used by that execution?

**Recommended selection:** yes. Treat producer implementation identity and run-scoped cache/fit state as separate typed predicates, joined at the MethodJob attempt. The proposed MethodJob join would require both at its named source-admission consumer. Current source admission does not yet enforce this pair; see 02-current-consumers.md.

This is one narrow boundary: the current fingerprint folds a long-lived global fit cache into the static producer identity. It is not a proposal to trust or ignore runtime globals generally.

## Deciding evidence

R20's actual current-profile run is at:

/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/root-ir-transport-composition-20261024-r1/g-native-priority-20261025-r1/dynamic-author/r20-cache-state-diagnostic-r1/execution-r3/

- lifecycle.json SHA256 9e73808b57f7506e0948fae379073167848c9e51a91216e207ee4894d149ed47
- cache-lifecycle.stdout.txt SHA256 9ff4031ada1bb8595fa8ddd8ede11831235e89c26e164b3fe8ec4b287bd96d22
- supervisor-result.json SHA256 f9467b0e7fd9af442d5bf167dc776a46b478f780f4ece466a6dd360bbcc31d0d
- source-profile-freeze.json SHA256 bad7699889f48395abf62ed39cc8873bf27d7ffa927365a3d0714dce34947e46

The cold process had no cache entries and its in-memory diagnostic fingerprint was present. One real 120-row fit produced one _ATENuisanceFitCore; the actual same-study warm read reused its fit identity; a second distinct 120-row study produced a second core. With no cache clear, the fingerprint was unavailable after the first fit and remained unavailable after warm reuse and the second fit. The in-memory classifier admitted only the exact loaded builtin _thread.RLock; this demonstrates that an RLock exception alone cannot restore identity.

The selected file readset stayed unchanged during this run, at HEAD 1fd513e8b2a7e3405d61023c2dffa22ce9a88447, tree c3c614e7d34d33abcc9a11a2ce0b847615e24cbc.

## Current owner path and divergence

Current R19 candidate code is scientist/methods/autotune/registry.py::_methodjob_producer_dependency_fingerprint. It computes producer code/global closure and serializes supported live globals; unsupported objects return unavailable. After a real fit, tmle_core.py's _SHARED_NUISANCE_CACHE maps keys to _ATENuisanceFitCore objects, so a static source fingerprint now depends on process-local data it cannot encode.

The runtime cache has a meaningful existing owner basis:

- _fit_identity(X, T, Y, contract) recomputes hashes of the actual three input arrays and the selected nuisance fit contract.
- _shared_nuisance_cache_key includes that identity and an optional caller label.
- _cache_put stores _ATENuisanceFitCore.from_bundle.
- The core uses byte-backed read-only numeric arrays and a frozen dataclass, but nested scaler/metadata values are mutable. _cache_get returns by key without checking core identity or content. The precomputed-bundle branch does recompute the fit identity and resolves a controlled cached core by identity.
- Existing tests already cover cold/warm reuse, reader isolation, changed input/contract identity, and precomputed-bundle identity. They do not prove that every live core's content remains untampered.

Thus the cache cannot be silently ignored or assumed immutable. It needs a separate, current-execution proof or the execution remains unavailable.

## Proposed contract split

Keep the existing SourceUnit law. Define two versioned identities and join them for a single attempt:

1. **Producer implementation identity (static):** selected producer code/source plus interpreter/runtime profile and exact selected dependency artifact identity. This answers which implementation was loaded. A repository lock is a build input, not proof of which artifacts a wheel process loaded.
2. **Execution fit/cache witness (per attempt):** attempt/evaluation identity; recomputed X/T/Y and nuisance-contract fit identity; observed cache hit/miss/produce state; exact selected core identity and content digest; and linkage to the result produced from that material. This answers which runtime state participated in this result. Capture only the selected fit entry, not all unrelated cache entries.

Under the proposed law, the MethodJob source-admission consumer would recompute and bind the producer identity and per-run witness before treating that result as source-bound. This pair is not the current invariant; current consumers and status effects are pinned in 02-current-consumers.md. Missing, malformed, mismatched, or unverifiable present state is unavailable/rejected under the current status vocabulary. The witness is not proof of scientific correctness, a source issuer, a publisher signature, or a new authority. It does not bypass the selected schema, method law, unit law, suite/candidate lineage, or any existing evidence requirement.

### Reuse-first owner candidates

- foundry/methods/artifacts/_fingerprint.py::compute_source_fingerprint already owns reachable producer source/module hashes, with Git identity or file hash. It does not identify dependency artifacts or installed distribution origin.
- foundry/methods/catalog/dependency_profile.py already owns selected dependency-profile and installed-environment reconciliation. Its current declared pyproject/lock references are stale against current bytes, so it cannot be admitted without refreshed exact refs.
- core/components/_provider_origin.py demonstrates a loaded module RECORD origin versus explicit canonical editable source. Its current scope is provider-entrypoint-specific; reuse its typed pattern, not a private cross-boundary call.
- The existing MethodJobExecutionWorkPacket is a typed, persisted, diagnostic-only execution observation. It may be the run-witness attachment point if its owner and current consumer permit; do not silently promote its diagnostic status or add authority through adjacency. A new version needs strict reader/writer and replay tests.

### Wheel and editable-source boundary

The R17 source-identity audit is installed-source-identity-oracle-20261027-r1/source-identity-audit-r1/report.md SHA256 d450b8d9eaf509ed675c4e675ea2942b1522b35d7ac52b36f16ce3720268b725; its addendum is SHA256 dae64bbad2095da7c5707ed7874bbeb73af1fcd6f5f3445674709e3b156110e8.

The inspected venv is editable source for this checkout, not wheel evidence. Its distribution RECORD has 29 rows and does not list the MethodJob registry source. In an ordinary wheel installed outside the checkout, nearest-ancestor uv.lock lookup yields no project lock; a lock found from the current working directory or a neighboring directory is not a substitute. Producer identity must stay unavailable until an admitted owner binds the actual loaded module origin/source bytes to exact installed artifact data and a current selected dependency profile. RECORD proves local file-to-distribution association, not publisher authenticity. This remains a distinct missing input from the cache-state defect.

## Alternatives and consequences

| Choice | Consequence | Disposition |
|---|---|---|
| Keep traversing the complete live global graph as source identity | Cold identity fails after the cache is populated; unrelated prior studies affect later identity; exact later replay requires the whole live cache/order. | Reject as the general contract. |
| Exclude the cache from static fingerprint without a run witness | Static identity stays stable, but a result can depend on an unchecked mutable cache object. Existing code does not establish full content integrity. | Reject as an unproved bypass. |
| Split static implementation identity and per-attempt cache/fit witness | Adds a versioned evidence shape and reader-first migration; keeps source and execution predicates separate and independently recomputable. | Recommend for G selection. |
| Admit all runtime globals by broad mutable-state exemption | Turns this one cache issue into a generic trust bypass. | Reject. |

## Required falsifiers

1. **Cold/warm/second study:** cold empty process; one actual fit; same-study cache hit; second distinct study. Static identity must remain stable; each run's selected witness must bind its own fit identity and core.
2. **Key is not content:** keep a cache key and fit identity while mutating a core array, scaler, metadata, or core type. Consumer must refuse or detect the changed content. Test removal, wrong-key binding, and a conflicting duplicate identity as well.
3. **Cache scope:** add/reorder an unrelated study entry. It must not change static identity or the first run's selected proof.
4. **Inputs and contract:** mutate X, T, Y, random seed/folds/model/split. The recomputed fit identity/witness must change or refuse, retaining current test_tmle_fit_contract.py controls.
5. **Installation identity:** test an editable source install and a wheel outside a checkout. A neighboring or CWD uv.lock must not change either source identity. Alter/miss the selected RECORD/source or dependency artifact and require refusal.
6. **Reader/history:** new reader understands old records but does not infer a runtime witness from old producer hashes; a new writer emits the new schema only after supported readers; rollback stops new writes but preserves readability of existing new records. Historical rows without the new basis remain inspectable and not established for new eligibility.

## Migration, status, and authority

- Version the producer identity/run witness contract rather than rewriting old hashes. Old records remain readable as historical evidence; they are not retroactively upgraded or promoted.
- Deploy readers before writers. A reader seeing a new writer schema it does not support must refuse typed admission. Rollback disables new writes while keeping new readers capable of reading stored records.
- Keep current unavailable/rejected behavior when code origin, dependency artifacts, selected fit identity, or exact core content is absent or inconsistent. Do not convert missing proof to a default or a fresh fit solely to create a green gate.
- Bind both observations to the actual evaluation attempt and result artifact refs. Preserve the existing diagnostic-only status until the current source/unit/evaluation law independently admits stronger use. No dates, publisher facts, installation-readiness facts, or scientific authority are inferred here.

## Decision and remaining evidence

**Requested G choice:** ratify the split between static producer implementation identity and the per-attempt fit/cache witness, with both required at the named MethodJob source-admission boundary if G selects the new law. Decide separately whether GP/warm-start eligibility requires that same joined proof. Leave the narrow artifact/field placement to its existing owner after semantic selection; do not grant authority to an existing diagnostic artifact. The diagnostic-only work packet cannot acquire authority by itself.

**Not established by this packet:** a normal wheel's installed-source/dependency identity; complete _ATENuisanceFitCore content-verification mechanism; a producer-unit binding; or GP/warm-start score admission. A source-frozen implementation and focused tests are required after this choice. No full repository or native GP run was performed here.

## Editorial qualification

Derived from the immutable R21 RAW memo and corrected by R23: the static-identity/cache pair is a proposed MethodJob law, not a current consumer invariant. 02-current-consumers.md names the current paths. Inputs pin the original bytes; they remain retained. This document makes no code, wheel, GP, warm-start, provenance, promotion, or G acceptance claim.

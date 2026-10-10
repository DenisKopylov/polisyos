# I4 C12 Legal slice evidence

Read-only source was pinned at G `93d6aa62a8d236667fdf322a5fc17962523b185e` on
`codex/e02-integration`. The authoring lane is `codex/e02-unified-local-20261009`,
based on that G checkpoint. This receipt was recorded against candidate HEAD
`a76bbfaef5be8362c2393802c497866b79df4d9e`; root owns any commit or integration.

## Source selection

`TASKS.json#/I4` requires an actual request-to-profile-to-encoder-to-fresh-reader
path, with refusal for missing or wrong profiles, and names LA-033, LA-046,
LA-028, LA-032, and LA-040. `INPUTS.json` records C12-own `a47ec396` as not yet
accepted into G. Its history contains the Legal generation/profile implementation
(`c60e37e`, `677e609`, `fd3898a`) and the final `a47ec396` scalar-bound fix.
The compatible source selected here is the Legal owner and producer API, composed
surgically into G's current contract and HTTP serving path; the broad old branch
is not imported. `a47ec396` also fixes a concrete G regression: parsing `0.0` via
`str(value or "")` erased the numeric bound. That exact scalar behavior and its
24 persisted-consumer cases are retained in this slice.

`fcf164eb` is an evidence/proposal commit, not a source implementation. Its C10
typed-call and public-facade patches are explicitly unapplied; its report keeps
the served caller on text search and selected-G supplier/caller acceptance open.
No proposal or receipt is treated as a G closure.

## Implemented property

The Legal batch producer uses one loaded encoder to generate vectors and derive
its asset identity, then passes that same live encoder to the shared generation
builder, which recomputes and checks the supplied identity. The request carries
a frozen selected-generation ID and full inventory snapshot. The fresh Legal
store resolves that current selection, recomputes complete projected-member content,
checks saved matrix against native
HNSW, validates model/device/dimension and loaded encoder assets, then encodes.
Missing, stale, malformed, or mismatched intent returns a typed refusal. The
runtime container accepts only an exact `LegalQueryEncoderProvider` instance;
provider absence is the default. The HTTP caller preserves real text results and
the refusal code when vector admission is unavailable. It reports vector mode
only when the hybrid path completes without a typed refusal.

The native HTTP witness builds selected generations with one deterministic local
encoder, snapshots the producer-selected inventories into immutable request
intent, and searches through a fresh graph/store and native HNSW index. It covers
vector success, changed provider assets falling back to text, and the default
provider-absent text fallback. This is a compatibility witness only; it asserts
no production-corpus, model-quality, or legal-authority claim.

## Pattern and predicate pass

P01/P02: test the complete local producer → generation artifact → immutable
request → runtime bridge → fresh consumer → HTTP response path. P05/P10: query
results remain search output and receive no legal authority. P27: reuse the Legal
producer, graph, store and search owners. P32/P33: selected profile and content
are resolved and recomputed, with malformed/stale/provider-negative cases.
P37: generation/member and matrix/HNSW correspondence are recomputed; model
asset identity is recomputed from loaded weights/config/tokenizer. The executable
behavior of `encode` is `not_established`. P38 divergence: replacing `encode`
while preserving weights/config/tokenizer leaves provider admission green and
can return a decoy HNSW neighbor. P40 class: executable behavior versus asset
identity; this is the already-declared same class at a deeper provider boundary,
so it is a bounded residual rather than another local patch.

The smallest capability that would close that residual is a trusted executable
identity bound to the loaded model. No such code-provenance owner exists in this
runtime. The test `test_runtime_asset_provider_cannot_detect_same_asset_query_callable_swap`
is the falsifier. The provider is runtime configuration, not proof of production
authority.

## Verification

Full moderate outputs are in [`checks/`](checks/):

- `emb-03-and-native-http.log`: 45 passed.
- `served-lex-pipeline.log`: 6 passed.
- `legal-producer.log`: 1 passed.
- `benchmark-caller.log`: 2 passed.
- `ruff.log`: Ruff passed for the I4 Legal paths.
- `compile-toml-diff-check.log`: compileall, release TOML parse, and diff check
  passed.

The focused pytest commands used `-c /dev/null --noconftest -p no:cacheprovider`;
the broad suite and architecture guardrails were not run. The marker warning in
`test_emb_03.py` is due to deliberately bypassing project pytest configuration.
No files were staged or committed by this slice.

## Remaining integration check

The Legal store and runtime encoder provider now route projection, selected
generation, encoder identity, generation-basis, and HNSW correspondence helpers
through `data_forge.read_api.legal`. No Lex knowledge/runtime path imports these
helpers directly from `data_forge.kernel`. The facade exports were added by the
shared-kernel owner; the broader I4 Catalog profile integration remains owned by
its separate I1/C05 lane.

After the facade reroute, the combined focused replay passed 54 tests. Ruff's
lint passed; its first format check found two files needing formatter output,
which was applied before closeout. The full replay and final format/compile/diff
receipts are in `checks/facade-focused-tests.log` and the companion refreshed
logs. The initial facade-reroute checkpoint was HEAD
`a76bbfaef5be8362c2393802c497866b79df4d9e`. The live-encoder adjustment
and its verification ran after HEAD advanced to
`314dc4100a1982cac1d2ddcdde230f2b9ba71a06`; the Legal slice files and receipt
updates remain in the working tree for root to commit.

After the producer now passes the live encoder object into the shared builder,
the normal project pytest harness passed 52 producer, Legal consumer, and served
pipeline tests (`checks/legal-encoder-live-replay.log`).

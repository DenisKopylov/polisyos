# GY-PA2 Delegation Gate Execution Journal

Date: 2026-08-19

Branch: `codex/gy-pa2-delegation-gate`

Dedicated worktree:
`/Users/deniskopylov/polisyos/.worktrees/gy-pa2-delegation-gate`

Base: `bedd4750331846257d412e41d478c0b33321094a`. The branch was attached and the
worktree was clean at entry. All tracked writes in this journal are root-authored; read-only agents
used only this worktree. `[P37: recomputed]`

## Interruption and refusal receipt

The first attempt entered the shared checkout at `/Users/deniskopylov/polisyos`. Before the pre-edit
measurement, that checkout moved to `codex/gy-def4-time-source-authority` and `git status --short`
showed five modified paths belonging to that lane. GY-PA2 did not switch, clean, stash, edit, or
measure against that state; it stopped under GY plan §3.5.13 and the append-only history/work
preservation rules. No GY-PA2 mechanism existed, so the stop consumed no P40 repair round. Work
resumed only after the dedicated worktree above was supplied and independently verified at the
required branch/base with an empty status. `[P37: recomputed]`

## Toolchain baseline gate

The fresh worktree did not have a trustworthy environment. The first bootstrap created `.venv` but
stopped at the inherited non-default Git hook configuration; this was a tooling non-receipt, not a
product finding. A second guarded bootstrap used `workspace bootstrap --skip-hooks
--skip-playwright --skip-doctor`, completed `uv sync` and `corepack pnpm install
--frozen-lockfile`, and returned `0` in 6.24 s. Python is 3.14.0, pytest 9.0.2, and Ruff 0.14.10.
`workspace doctor --skip-playwright --skip-contract-checks` returned `0` in 1.44 s. The full doctor
returned `1` in 27.67 s only for the base's generated schema-catalog reference drift; Python, Node,
uv, locks, runtime OpenAPI, and frontend contracts passed. The exact untouched base reproduces that
drift, so it is a P41 inherited non-receipt, not a GY-PA2 product red. Four lanes were live; measured
timeouts use the instructed 1.6–2.0× contention regime. `[P37: recomputed]`

## Pre-edit governed-artifact blast radius

A complete tracked `git grep` for `DelegationContract` returned 17 inbound paths with denominator
`json=2, md=8, py=5, toml=2`. An independent complete `rg -l` walk excluding environment and package
trees returned the same 17 paths and distribution. The set includes the canonical source and test,
the runtime-quality export, the S7 manifest/readiness validator, two architecture maps, and eight
plans/decisions/research documents. `DelegationContract` had 22 fields and was strict/frozen before
the edit. `[P37: recomputed; P35 denominator reconciled]`

Frozen architecture receipts before the first tracked edit:

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `architecture/policy_design_case/layer2_s7_delegation_manifest.json` | 2,168 | `7190f764d907f745854fc5c5cb5190afc7b8c2a95eb327369d3438f41b000a6a` |
| `architecture/policy_design_case/layer2_artifact_traceability.toml` | 7,164 | `fb1bd3c86b1b4f821659584ee10ab0c191f9f83c1db9871115ec56edb82b7347` |
| `architecture/policy_design_case/layer2_readiness_manifest.json` | 1,278 | `5734bd4d66e924f0a11eb93a4216f9f27a0ab77ba02f928747cdb734f656a2ea` |
| `architecture/policy_design_case/layer2_floor_governance.toml` | 3,957 | `8f1e1cd0049a38c381d6a4aa81fd7a5f6ce47d3651a3d36b2fb9d88ed17f24e0` |
| `architecture/policy_design_case/cluster_ownership_map.toml` | 47,839 | `b9409bc276d77d60919fab996ced4d01189c276eb38edad1eaa23e831edd69f4` |
| `architecture/policy_design_case/wave12d_universal_outcome_corpus_run_manifest.json` | 3,080 | `653da20da88bac529cda0ff41eebf4807b1a7786621f61923e2b158a7e1663cd` |

The measured S7 manifest corrects the handed 1,955-byte figure: this branch contains 2,168 bytes.
It contains `DelegationContract` once and contains `envelope`, `operation`, and `permission` zero
times, case-insensitively. `S7_REQUIRED_ARTIFACTS` is a set of artifact names, not model fields.
The read-only Layer-2 readiness validator returned `status=pass`, 13 S7 cases, precision/recall/
integrity all 1.0, all false-clear counts zero, exit `0`, in 6.30 s. An additive optional contract
field is predicted not to move these artifacts, but that prediction grants nothing: every hash above
must be re-read after the mechanism, and any moved governed byte is the task's mandatory stop.
`[P37: recomputed]`

The live GY-GAP1 writer changes 29 normalized paths from the PA2 base. The exact planned-fence
intersection is the GY plan only. Its plan hunks are around lines 2635, 3623, and 4001; PA2's standing
is under the GY-PA2 row around line 2465, so the shared path is region-disjoint but not a zero-path
overlap. GY-GAP1 also changes `layer2_design_search.py`, which PA2 does not touch. `[P37:
recomputed]`

## Structural external-effect denominator — typed non-closure

DS20's spine was read before design. It recursively enumerates the live FastAPI route table, selects
every `POST|PUT|PATCH|DELETE`, and requires exactly one direct real `ActionPermissionDependency`,
rejecting markers and duplicates. Its dynamic sibling and late-handler tests prove that property for
unsafe HTTP routes. That predicate is `recomputed` for the route table and `not_established` for the
different property “every agent external effect passes the PA2 producer.” `[P37/P38: recomputed]`

The complete source denominator is 2,559 tracked `.py` files under `src/polisyos`. A Python AST walk
found 50 direct HTTP-session `get`/`post`/`head` calls. An independent textual walk found 48; its two
misses were `fabric/connectors/sources/graphql_api.py:167` and
`runtime/http/deployment_security.py:393`, where statement shape differs. The reconciled 50-site
bounded HTTP census is:

- catalog/academic batch: `harvester.py:1689,1741,1796,1934,1964,1989,2004,2034,2077,2092,2133`,
  `fulltext_resolver.py:829,931,1032,1211,1414`, `doc_normalize.py:356,390,419`,
  `core_sources/loaders.py:756,781,1818`, and `core_sources/transformers.py:372`;
- fabric connectors: `reference/sdmx.py:356,641,700`, `reference/static_csv.py:221,262`,
  `reference/rest_json.py:306,538`, `sources/_file_common.py:150`,
  `sources/ckan_resource.py:139`, `sources/eurostat.py:475`, `sources/graphql_api.py:167`,
  `sources/http_base.py:442`, `sources/sdmx_source.py:802`, and `sources/sparql.py:163,228`;
- model/vendor: `spo_client.py:489`, `article_extractor.py:1341`, `llm_extractor.py:176`,
  `_resolve_extract_providers.py:919,981`, and `scientist/orchestration/llm/gateway_client.py:289,393,445`;
- other HTTP: `core/security/authz.py:353`, `runtime/http/deployment_security.py:393`,
  `data_forge/domains/academic/openalex/client.py:83`, and `scholar/search/providers.py:591`.

This is not the complete external-effect set. Separate live families include direct URL fetch,
S3/DynamoDB/Redis/PostgreSQL, subprocess, Temporal/Dask, and WebSocket emission. More decisively,
`scientist/agent/tools/registry.py:182-227` invokes an arbitrary registered callable; live agent
entrypoints reach it through `tool_loop.py:254,670` and `supervisor.py:298,304`. A plugin handler can
perform network/process I/O without a statically resolvable Python call graph. `draft` has no proven
delivery sink; local public projection is not external delivery, while a dynamic tool may still
deliver it. Therefore an honest full-denominator coverage gate does not exist in this repository.

Typed finding `GY-PA2-COV-1`: the universal external-effect authorization/receipt chain is
`absent/unallocated`; after this slice the producer itself may be present, but live call-site wiring
remains `bridge_missing` / `implemented_but_not_orchestrated`. The smallest closing capability is one
server-owned external-effect intake used by every transport/registry adapter, plus (1) an AST/import-
resolution sink census and (2) a runtime registry/transport harness reconciled against it. A list of
declared action rows or unsafe HTTP routes is a P38 proxy and cannot close this finding. This task
reports and registers the gap; it does not absorb the universal transport refactor. `[P37:
not_established for universal coverage; recomputed for the bounded censuses]`

## P40 ledger

Mechanism rounds remain 0/2. The six approved amendments preceded mechanism entry and consume no
round. Findings above are pre-edit measurements or scope limitations, not review findings against an
implemented mechanism.

## Red-first receipt

Before any producer code existed, the new behavioral file was registered in
`architecture/production_quality/ci_tiers.toml` and run by exact path. It collected 12 tests,
printed `FFFFFFFFFFFF`, and returned exit `1` in 10.56 s. The failures were the missing
`DelegatedActionEnvelope` and missing `agent_action_authority` producer, not a harness/import setup
error. The suite includes zero-effect refusals for wrong-role human action, expired delegation,
search-permission/data-request separation, memory-as-fact, missing tool admission, candidate input,
caller-supplied widened envelope, and widened draft scope; it also pins recorded refusal shape,
record-before-effect, an unrecordable allow, unknown action fail-closed, data-only free growth, and
the decisive remove-the-envelope mutation. `[P37: recomputed]`

## Independent-review repair ledger — append-only correction

The initial `0/2` line above records entry state, not final round use. Three read-only reviews then
froze the implementation at `e4c40beac` before any repair. The first review found two Blocking new
classes: caller-provided contract/human resolvers could self-attest authority (`P32/P37`), and an
arbitrary non-throwing recorder plus arbitrary effect callable was used as a persistence/effect
predicate (`P29/P31/P38`). This consumed mechanism round 1. A second review independently reproduced
both and added invocation-replayed human approval, malformed inner DS20 fields, raw influence
summaries, and missing decision/effect receipt binding. Those are the same two classes one level
deeper, so P40 stops per-instance repair and widens the authority-owner intake and governed dispatch
quantities; they consume no additional round. `[P37: independently_reconciled]`

The artifact review confirmed all six frozen governed artifacts byte-identical and the readiness
validator green, then found one distinct Important new class: envelope-bearing fields were serialized
under the legacy `DelegationContract` v1 schema identity without a forward-reader contract. This
consumed mechanism round 2. Its content-hash and `model_copy(update=...)` sightings are the same
compatibility class at depth and must be closed by a symmetric v1/v2 discriminator plus raw
deserialization/content-binding witnesses. Mechanism rounds are therefore **2/2**; any further new
Blocking or Important class is a stop, while worked examples of these declared classes fold into the
single widening. `[P37: independently_reconciled]`

## Review-derived red receipt

Eight exact behavioral nodes were added before the repair. They assert zero effects for a
caller-minted contract (through a real `ToolRegistry` handler), a no-op recorder, a valid-looking
receipt for a different decision, a search decision pointed at a data-request callable, a human
approval replayed after invocation-content mutation, malformed inner DS20 roles, unpersisted
memory/input summaries, and an envelope-bearing v1 contract. They printed `FFFFFFFF` and returned
exit `1` in 12.27 s: five reached the forbidden effect, one raised `AttributeError` before any
recorded refusal, one accepted raw influence summaries, and one accepted the old schema identity.
An attempted `--timeout=30` run returned exit `4` because pytest-timeout is not installed; it changed
no bytes and is a tooling non-receipt. The measured 12.27 s run under four-lane 1.6–2.0x contention
sets a 30 s per-node review timeout for environments that provide the plugin. `[P37: recomputed]`

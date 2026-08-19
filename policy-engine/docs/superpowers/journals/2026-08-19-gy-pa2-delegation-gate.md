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

## Mechanism delivery receipt

The mechanism now has a strict `AgentActionIntent`, signed `AgentActionAdmissionBundle`, frozen
`AgentActionEffectBinding`, replay-linked `AgentActionAuthorityDecision`, and composition-root
`AgentActionAuthorityGateway`. The gateway owns exact CAS, durable event-log, idempotency-store,
signature-verifier, mandate-contract/admission-ref mappings, effect bindings, and the exact DS20
`BoundActionPermissionVerification` captured at request construction. A dispatch candidate cannot
supply or select its own envelope, source contract, admission, clock, permission proof, or gateway;
the producer resolves signed artifacts from owner mappings in one ambient scope, content-binds the
operation/invocation/intent/effect/permission inputs, and recomputes all five conjuncts. The live
clock is read once for the decision and again immediately before the effect. `[P37: recomputed]`

Every refusal is a completed governed result: the same decision schema as an allow carries
`outcome=refused`, replay refs, predicate provenance, refusal reasons, and its typed
`HumanDecisionRequest`; it is written, content-hash checked, reconciled, reloaded, and tied to a
durable event before `AgentActionAuthorityRefused` is raised. Allows are likewise persisted and then
single-use consumed before the registered handler is called. The only out-of-envelope override is a
mandate-owner-signed `HumanDecisionRecord` whose request link, exact invocation binding, TTL/role,
and all five rights are revalidated. Memory, input influence, and tool-ledger surfaces are admitted
only through the signed bundle and are candidate-firewall checked. `[P37: recomputed and
independently_reconciled]`

`DelegationContract` now has a symmetric schema discriminator: v1 rejects owner/envelope extensions
and retains byte-stable legacy serialization, v2 requires both a mandate owner and envelope data,
and unknown versions fail closed. The guarded predicate is data-defined: action kinds remain opaque
validated strings, owner-declared envelope rows are iterated generically, a new
`counterfactual_probe_v17` row works without mechanism code changes, and a caller-invented kind not
present in the owner contract records a refusal. `draft` alone has the required audience/externality
shape and grants no authority. `[P29/P35/P37: recomputed]`

## Post-edit governed-artifact receipt

All six frozen S7/readiness artifacts were re-read after the final source change. Their sizes and
SHA-256 values are exactly the six values in the pre-edit table above: 2,168 / 7,164 / 1,278 / 3,957
/ 47,839 / 3,080 bytes and no hash changed. The Layer-2 readiness validator again returned
`status=pass`, zero issues, all S7 precision/recall/integrity metrics 1.0, and exit `0` in 12.36 s.
No governed byte moved. `[P37: recomputed]`

One early measurement command accidentally assigned zsh's special `path` variable, removed the
command search path for that process, and exited `127` before reading or writing a governed byte.
The corrected command used `artifact_path`; the failed invocation is a tooling non-receipt, not an
artifact finding.

## Structural denominator correction and bounded residual

**Append-only correction:** the earlier `2,559` tracked-Python / `50` AST / `48` text figures are
superseded and must not be cited. Independent review classified that numeric receipt as a new P35
documentation/inventory class, not a mechanism finding. The exact PA2 base contains 2,560 tracked
`src/polisyos/**/*.py` files; final HEAD contains 2,561 because PA2 adds the producer module.

At final source pin `132bcf00736f01ab961908b3fe967dd2c10ac181`, one script consumed the complete
sorted `git ls-files src/polisyos` Python denominator, parsed all 2,561 files, and selected `ast.Call`
nodes whose method is `get|post|head` and whose receiver terminal is `session` or ends in
`_session`. It found 49 bounded direct-session sites. An independent line scanner for
`session\.(get|post|head)\s*\(` found 50 candidates. Set reconciliation produced
`AST-minus-text = ∅`; the sole text-only row is
`src/polisyos/fabric/connectors/testing/simulator.py:314`, a docstring explaining simulated session
calls. The reconciled bounded direct-session denominator is therefore 49. `[P35: complete tracked
file denominator and independent set reconciliation]`

That 49-site set is still not the property “all external effects.” `ToolRegistry` accepts arbitrary
callables and the repository has multiple network, process, database, queue, and socket effect
families with no owner-authenticated common intake. The declared P38 residual was falsified on final
HEAD with a signed/allowed binding labelled `search` whose handler invoked a real registered
`data_request` tool: output was `actual_registered_effects=['DATA_REQUEST']`, then the zero-effect
assertion failed, exit `1`, in 14.60 s. The first ad-hoc harness load failed before reaching the
mechanism because Python 3.14 requires a dynamically loaded dataclass module to be registered in
`sys.modules`; the corrected replay above is the receipt. This is the same exact-effect-binding
class one level deeper at rounds 2/2, so P40 forbids another per-instance repair. `GY-PA2-COV-1`
remains `bridge_missing` / `implemented_but_not_orchestrated`, and universal coverage remains
`not_established`. The smallest closing capability is one server-owned external-effect intake with
authenticated adapter/deployment identity, plus an AST/import sink census reconciled against a
runtime registry/transport harness. `[P37: not_established; P38 falsified]`

## DS20 permission denominator and reuse receipt

The permission denominator is DS20's one owner, not a PA2 list: `RuntimePermission` has exactly 33
unique members/values. The focused server-vocabulary stability test, live OpenAPI enum projection
test, and generated-client union comparison all passed (3 tests, exit `0`, 65.69 s under the
four-lane contention regime). PA2 stores and rechecks the exact required/granted enum values and
resource digest from the request-owned `BoundActionPermissionVerification`; it never infers
permission from the DS20 audit event and never mints a new permission. `[P35/P37: independently
reconciled]`

## Final P40 review ledger

The widened owner intake closed the round-1 caller-resolver/recorder class; the v1/v2 discriminator
closed the round-2 schema-identity class. Later reviews found two same-class deeper cases: a
caller-supplied historical clock and a well-typed caller-minted DS20 proof. Both were folded into the
quantity of the existing repair: producer-owned live clock reads now occur at decision and
immediately before effect, and the gateway now captures the exact composition-root DS20 object and
canonical hash, which the signed admission also binds. Their behavioural reds pass. Artifact review
returned GO with all governed hashes unchanged; authority API review returned GO for both widened
repairs and found no new Blocking/Important class. The callable-semantics P38 residual above remains
the declared bounded limit. Final mechanism rounds are **2/2**. `[P40: independently_reconciled]`

## Duplication and phantom findings — report only

A complete set comparison found 33 server-owned `RuntimePermission` values and 15 hand-authored
dashboard `PERMISSION_KEYS`: 12 overlap and 21 server values are absent from the dashboard list.
The 12 overlapping literals are P27 canonical-owner duplication/projection drift risk; PA2 did not
repair them. The remaining dashboard-only values are `collaboration.comment`,
`collaboration.share`, and `collaboration.view`. They occur only in the dashboard permission list,
have no server `RuntimePermission`, and match none of the 91 committed OpenAPI paths. They are not a
duplicated server vocabulary; they are `producer_missing` orphan/phantom permissions.

The handed historical `/api/v1/collaboration/*` UI transport does not reproduce in current source:
the dashboard now opens `/api/v1/review/live`, and the server owns that WebSocket at the
`/api/v1/review` router plus `/live`. The orphan permission literals remain disconnected from that
transport. This is DS4/DS5 debt and was reported without repair. `[P35: complete set comparison]`

## Targeted verification receipt

- The final PA2 behavioural file expanded to 32 parametrized cases and passed, exit `0`, in 24.28 s.
  Its refusal witnesses cover wrong role, TTL at decision and immediately before effect, search ↛
  data request, memory/input/tool admission, caller envelope provenance, draft scope, forged owner
  artifacts/proofs, replay, malformed DS20 data, recording failure/wrong receipt, and single-use.
  Every refusal helper checks zero effects and a reconciled durable refusal artifact.
- The existing mandate-bounded-delegation unit file passed 14 tests, exit `0`, in 31.43 s. The
  readiness validator passed in 12.36 s. The six corpus-backed S7 tests remain unavailable in this
  fresh worktree because the repository's untracked `production_data/manifest.json` is absent; that
  earlier combined run failed before the touched models and no other lane's data was borrowed.
- Ruff on every changed Python/test path passed; `py_compile` and the Core-root facade import probe
  passed. No full pytest run was performed, as required.
- The final architecture guardrail ran in 42.69 s and returned exit `1` only for six deep-import
  additions and three removals in `runtime/http/services/channel_contracts.py`, the two Lex control
  services, `scientist/orchestration/engine/checkpoint.py`, `runtime/http/execution_policy.py`, and
  `runtime/http/routes/runs.py`. PA2's initially reported three edges are absent after routing through
  the existing Core root and runtime security facades. The exact scanner was replayed from an
  isolated archive of base `bedd47503` (including `.github`) and reproduced the same deep-import
  diff and exit `1`; the PA2 changed-path intersection with those paths is empty. This is therefore
  a P41 inherited architecture red. No baseline was synced and no exception was added.

No frontend surface was built. The GY-DEF4 overlap file
`src/polisyos/runtime/quality/authority.py` is not in the PA2 diff. Line 7 of the GY plan was not
changed.

## Final audit stop — append-only correction

The final independent audit returned **NO-GO** with one **NEW Blocking P38/P33 class**. Memory
admission is a fixed-key proxy: `memory_influence_claim_evidence_issues()` examines the declared
`CLAIM_EVIDENCE_SLOT_KEYS`, while `AgentActionAdmissionBundle.memory_claim_payload` accepts a generic
dictionary. The gate applies no generic candidate firewall to the remaining memory payload before
allow.

The exact final-HEAD falsifier signed an otherwise-valid bundle containing
`{"policy_fact_ref": "memory-influence:prior-policy-fact"}`. Dispatch printed
`dispatch_result='search' effects=['search']`; its required `effects == []` assertion failed, exit
`1`, in 10.25 s. This violates the binding deliverable “a memory record masquerading as a policy
fact does not pass the gate.” It is not the earlier caller-authority, persistence/effect-receipt, or
schema-identity class; it is a new proxy-key/generalization class. Rounds were already 2/2, so P40
requires stop/report rather than a third-round instance repair. No mechanism code changed after the
finding. The earlier statements that all memory refusals produce zero effects and that the local
guarded adapter's required reds pass are superseded. The producer remains present, but GY-PA2 is not
admissible for completion. `[P33/P38/P40: falsified, NEW Blocking, stop]`

Smallest class-level repair: replace the fixed evidence-slot key proxy with a generic governed
memory-admission boundary over the full payload grammar, then add generated novel-key, synonym,
nested, and present-but-fake variants plus the remove-the-property mutation. That repair is not
attempted after the P40 stop.

Minor factual correction: the earlier mechanism paragraph says v2 requires both a mandate owner and
envelope data. The model actually requires the v2 mandate owner but permits an empty envelope tuple;
dispatch then fails closed with `unknown_action_kind`. This claim/model mismatch is recorded and was
not repaired because it is not the Blocking stop class.

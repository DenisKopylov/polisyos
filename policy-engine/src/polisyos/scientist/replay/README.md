# Scientist Replay

Replay owns deterministic re-execution, dead-letter replay, semantic diffs, and
replay verification reports for Scientist runs.

Use this hub for:

- deterministic replay planning, completeness, and verification contracts in
  `deterministic.py`;
- replay backend execution and dead-letter inspection;
- semantic diff models and comparators;
- replay verification reports and registries.

`polisyos.runtime.replay` is a compatibility facade over `deterministic.py`.
New first-party replay consumers use the Scientist-owned module directly.

The Runtime root retains its ten lazy exports; `runtime.replay` retains the twenty
identity-preserving compatibility aliases. No retirement of those exports is implied
by a successful source census. External callers remain unknown. Runtime's historical
`RunManifest` 1.0 reader is a different owner from Core's run manifest and
`runtime.quality.replay`; the source-qualified protocol-4 fixture under
`tests/fixtures/package_path_compatibility/` preserves one finite historical model
sample, not a production run corpus or a converter between those owners.

## Compatibility support record (REQ-REP-01-03)

The finite export denominator is the Python `__all__` in
[Runtime root](../../runtime/__init__.py) (10 names) and
[Runtime replay facade](../../runtime/replay.py) (20 names).
[The REP-01 compatibility tests](../../../../tests/unit/remediation/test_rep_01.py)
spell out both complete name sets and require object identity with the Scientist
owner; these are export counts, not caller counts. Both interfaces remain supported
until a separately approved API retirement and caller window. The dated package-layout
exception below is a separate policy. A source move or successful installed run does
not authorize removal.

### First-party release census

For C77-G02/G03, the source census is pinned to commit
`27958f89d976466fcc321fec28e06469de435a6b`, tree
`6b38f1f8ab02d1bdcf9ed6545f8a317c5657c4ad`. It read every selected Git blob
and verified its Git SHA-1 identity before searching; it did not import or execute
product code. This is a lexical/static caller census, not runtime or installed PASS.

The path denominator is **11,483 regular tracked files / 225,143,667 bytes**.
Within `policy-engine/`: `src` 3,072; `tools` 628; `tests` 3,734;
`benchmarks` 160; `packages` 111; `apps` 1,348; `workers` 8; `examples` 45;
`dev-oracles` 5; `architecture` 702; `ops` 270; `schemas` 174; `release` 8;
`release-fragments` 543; maintained `docs` 605; `design` READMEs 2; four Hatch-included static catalog
YAML resources. Root/product immediate files and repository CI contribute 61;
the product `.cursor`, `.devcontainer` and `.vscode` trees add three (one each).

The file-type denominator is `.py` 7,116, `.pyi` 5; `.ts` 548, `.tsx` 733,
`.js` 4, `.mjs` 41, `.cjs` 9; `.md` 1,094, `.mdc` 1, `.txt` 3;
`.toml` 724, `.json` 912, `.jsonc` 1, `.yaml` 73, `.yml` 75, `.ini` 11,
`.cfg` 1, `.lock` 3, `.example` 3; `.sh` 45, `.sql` 6, `.cypher` 2, `.tf` 1, `.rego` 23,
`.tmpl` 7, `.tpl` 1, `.html` 3, `.css` 17; `.typed` 2,
`.reproducible` 1 and 18 extensionless files. All 7,121 selected Python/pyi
blobs were AST-parsed with Python 3.14.3, with no read, identity, decoding or
syntax failure. Selector corrections changed only non-Python text; that complete Python blob set
remained unchanged (Git-manifest SHA-256
`81ad2ceaad726149f2888552f56cdd368886ba95fb8788e77249e0120ecc77da`).

History/payload exclusions are `docs/{research,archive,plans,superpowers,backlog}`,
any nested `docs/**/archive/`, `architecture/baselines`, non-code test/architecture
fixture and golden payloads (except the retained `package_path_compatibility`
fixtures), other data, CSV/TSV tabular references, SVG/PNG visual assets, `.retired`
historical source, fixture/report payloads (`.content`, `.fixture`, `.jsonl`,
`.blob`, `.duckdb`, `.pkl`), vendor/dependencies, binary archives and
untracked/ignored state. Code, owner READMEs, maintained docs/configs, root instructions, packaging
manifests, generated package/app clients and extensionless launchers are included
by the exact selector below; an excluded tree is not evidence of zero usage.

The complete, path-byte-sorted Git manifest `(mode SP blob-id TAB path NUL)` has
SHA-256 `2524c7685d5e68c1f94949dc66a42676c2def7d8279dc5a8a9d6413caada521a`.
The actual-read manifest adds `TAB SHA256(content)` before each NUL and has
SHA-256 `b7368a757c10cc95cbe1cead2e0d2b15f7f39b98e42015da05b5683e41e27ffb`.
The pin and recipe recover every path/blob identity without another inventory file.

Literal dotted/slashed owner names, `runtime_replay`, direct Runtime imports and
their case-insensitive forms yielded **44 candidate files**. AST import/load
inspection and direct source review reconcile them as six owner/import/load
files, ten replay test files, fifteen metadata/guard files, four documentation
files, eight telemetry/owner-label files and one unrelated Runtime import.
These are candidate-path classes, not 44 executing callers or capabilities.
Paths below are relative to `policy-engine/` except `.github/...`.

| Role | Positive paths and disposition |
| --- | --- |
| Source imports/FQNs and literal loads (6) | `src/polisyos/runtime/{__init__.py,replay.py}`, `src/polisyos/core/components/_cli_replay.py`, `src/polisyos/scientist/replay/{backend.py,verification.py}`, `benchmarks/advanced/common.py`. Runtime facades preserve identity; the CLI literal target and benchmark use the Scientist owner. |
| Replay/test consumers (10) | `tests/integration/test_c7_synthetic_full_pipeline.py`; `tests/unit/core/components/test_cli_replay.py`; `tests/unit/remediation/test_rep_01.py`; `tests/unit/runtime/{test_replay_runtime.py,test_replay_input_bindings_completeness.py}`; `tests/unit/scientist/replay/{test_deterministic_compatibility.py,test_profileless_replay_basis.py,test_replay_backend.py,test_runtime_replay_measurement.py,test_verification_owner_admission.py}`. These retain actual ABI, planning and consumer witnesses; this census does not rerun them. |
| Strings, public/package contracts and guards (15) | `.github/workflows/core-runtime-release-gate.yml`; `architecture/imports/dynamic.toml`; `architecture/packages/{layout.toml,scientist.toml}`; `architecture/public_surface/{contract.toml,inventory.json}`; `architecture/policy_design_case/layer3_gy_confidence_ledger_contract.json`; `architecture/tooling/ruff/{per-file-ignores/80-runtime-core-ir.toml,workspace_root.toml}`; `ruff.generated.toml`; `release/core-runtime-closeout.ledger.toml`; `release-fragments/unreleased/{2026-10-11-e02-existing-facade-routing.toml,2026-10-16-e02-c05-selected-consumer-composition.toml}`; `tests/repo_quality/architecture/test_repository_best_in_class_phase6_1_import_gate_conversion.py`; `tests/unit/data_forge/test_phase6_read_api_consolidation.py`. They declare surfaces/targets or assert ownership; membership alone is not execution evidence. |
| Maintained documentation (4) | `src/polisyos/{runtime,scientist/replay}/README.md`, `docs/adr/0009-decision-packet-replay-protocol.md`, `docs/reference/public-surface.md`. The ADR's historical owner wording is a reference, not a new relocation or retirement decision. |
| Same-spelling labels (8) | `architecture/production_quality/invariant_registry.toml`; `schemas/runtime_api_v1.openapi.json`; `src/polisyos/runtime/{http/openapi_contract.py,http/services/control/response_shapes.py,http/services/control_plane_store.py,quality/replay.py,quality/scorecard.py}`; `tools/quality/validation/production_quality_evidence_inventory_reports.py`. Their `runtime_replay`/`runtime.replay` values are telemetry or owner labels, not imports of the moved API. |
| Other Runtime import (1) | `tests/unit/remediation/test_migration_dispatch_contract.py` imports `manifest_migrations`; it is not a root10/shim20 replay consumer. |
| Monkeypatch/reflective consumers | The reviewed REP-01/Core CLI tests patch the delayed importer, stream boundary or default-workflow selector. Those test seams do not establish external monkeypatch compatibility with the moved API. Arbitrarily computed/aliased targets remain unresolved by this static pass. |
| Package/entrypoint selection | `pyproject.toml` scripts and every declared plugin group, `hatch.toml` wheel/sdist/force-include rules, and selected package/app manifests/generated clients were read. The wheel includes `src/polisyos` and `tools`; `polisyos` routes to `tools.ops_runners.runtime_cli:main`, and `polisyos-tools` to `tools.cli:main`. File selection is separate from actual installed origin/import/consumer qualification. |

`architecture/packages/layout.toml` retains the `team-runtime` root-file exception
for `src/polisyos/runtime/replay.py`, with `sunset = "2026-07-31"` and the reason
that the facade remains while replay state migration policy is exercised. That
dated package-layout policy is distinct from API/shim retirement approval; this
record grants neither removal nor a replacement retirement window.

Unresolved by construction: computed FQNs, arbitrary alias/dataflow/reflection,
`__getattr__` beyond the enumerated exports, loaded third-party entrypoint
providers, encoded references/opaque payloads, excluded histories, and external
packages or monkeypatches. Their use is `not_established`, not zero. The exact
exports and provided historical reader stay supported while those unknowns
remain; no infinite external-corpus proof is required to retain them.

<details>
<summary>Reproduce the selected Git/read manifests and literal candidate paths</summary>

Run from the repository root with the existing interpreter. This reads Git objects
only and writes no files; AST parsing can be repeated separately for the unchanged
`.py`/`.pyi` set. The byte query produces candidates for the role reconciliation
above, rather than interpreting every match as a caller.

```bash
policy-engine/.venv/bin/python -B - <<'PY'
import collections, hashlib, json, re, subprocess
from pathlib import PurePosixPath
REF = "27958f89d976466fcc321fec28e06469de435a6b"
PREFIXES = tuple("policy-engine/"+p+"/" for p in ("src","tools","tests","benchmarks","packages","apps","workers","examples","dev-oracles","architecture","ops","schemas","release","release-fragments","design")) + (".github/","policy-engine/.github/","policy-engine/.cursor/","policy-engine/.devcontainer/","policy-engine/.vscode/")
EXTS = set(".py .pyi .ts .tsx .js .jsx .mjs .cjs .sh .bash .zsh .sql .rego .tmpl .tpl .md .mdx .mdc .rst .txt .html .css .scss .sass .vue .svelte .toml .json .jsonc .yaml .yml .ini .cfg .lock .cypher .tf .example".split())
CODE = set(".py .pyi .ts .tsx .js .jsx .mjs .cjs .sh .bash .zsh".split())
HISTORY = tuple("policy-engine/docs/"+p+"/" for p in ("research","archive","plans","superpowers","backlog")) + ("policy-engine/architecture/baselines/",)
FIXTURES = tuple("policy-engine/"+p+"/" for p in ("tests/fixtures","tests/golden","tests/goldens","tests/_golden","architecture/fixtures"))
RESOURCES = {"policy-engine/data/dataset_catalog/"+p+".yaml" for p in ("seed_variable_alignments","proxy_metric_alignments","wvs_indicator_registry","metrics_map")}
SPECIAL = {"py.typed",".gitignore",".gitattributes",".editorconfig",".nvmrc",".python-version",".env.example",".yamllint","LICENSE"}
def selected(path, mode, kind):
    p=path.decode("utf-8"); q=PurePosixPath(p)
    rootfile="/" not in p or (p.startswith("policy-engine/") and p.count("/")==1)
    scope=rootfile or p.startswith(PREFIXES) or p.startswith("policy-engine/docs/") or p in RESOURCES
    typed=not q.suffix or q.suffix in EXTS or q.name in SPECIAL or q.name.startswith("Dockerfile")
    payload=p.startswith(FIXTURES) and q.suffix not in CODE and not p.startswith("policy-engine/tests/fixtures/package_path_compatibility/")
    return scope and typed and not p.startswith(HISTORY) and not (p.startswith("policy-engine/docs/") and "archive" in q.parts) and not payload and kind==b"blob" and mode in (b"100644",b"100755")
rows=[]
for record in subprocess.check_output(["git","ls-tree","-rlz",REF]).split(b"\0"):
    if record:
        meta,path=record.split(b"\t",1); mode,kind,oid,size=meta.split()
        if selected(path,mode,kind): rows.append((path,mode,oid,int(size)))
rows.sort(key=lambda row:row[0])
manifest=hashlib.sha256(); reads=hashlib.sha256()
types=collections.Counter(); groups=collections.Counter(); matches=[]
pattern=re.compile(rb"(?:polisyos[./])?runtime[./]replay\b|scientist[./]replay[./]deterministic\b|\bruntime_replay\b|from\s+polisyos\.runtime\s+import\b",re.I)
reader=subprocess.Popen(["git","cat-file","--batch"],stdin=subprocess.PIPE,stdout=subprocess.PIPE)
assert reader.stdin and reader.stdout
for path,mode,oid,size in rows:
    record=mode+b" "+oid+b"\t"+path
    manifest.update(record+b"\0")
    reader.stdin.write(oid+b"\n");reader.stdin.flush()
    assert reader.stdout.readline().split()==[oid,b"blob",str(size).encode()]
    data=reader.stdout.read(size); assert len(data)==size and reader.stdout.read(1)==b"\n"
    assert hashlib.sha1(b"blob "+str(size).encode()+b"\0"+data).hexdigest().encode()==oid
    reads.update(record+b"\t"+hashlib.sha256(data).hexdigest().encode()+b"\0")
    p=path.decode();q=PurePosixPath(p);types[q.suffix or "<none>"]+=1
    groups[p.split("/")[1] if p.startswith("policy-engine/") and p.count("/")>1 else "<root>"]+=1
    if pattern.search(data): matches.append(p)
reader.stdin.close();assert reader.wait()==0
print(json.dumps({"paths":len(rows),"bytes":sum(r[3] for r in rows),"git_manifest_sha256":manifest.hexdigest(),"actual_read_manifest_sha256":reads.hexdigest(),"file_types":dict(sorted(types.items())),"groups":dict(sorted(groups.items())),"candidate_paths":matches},indent=2))
PY
```

</details>

The source-qualified historical sample used by this record is
[runtime_abi_protocol4.json](../../../../tests/fixtures/package_path_compatibility/runtime_abi_protocol4.json)
(SHA-256 `f781ebf403a265b822a3fe4eec22d0dd66adf06c0f5c8c84292481901331f83f`),
containing four objects: `RunManifest`, Runtime `ArtifactRef`, `ABIModelEntry` and
`Priority`, from source
`cf6a076a8415dc4092cfd3d4e9c8862f81c15a9a`. Their individual hashes and the historical
schema hash are retained in the fixture. The compatibility tests preserve those
bytes; the Runtime schema comparison permits only the separately identified ArtifactID
pattern/length refinement. MIG-02 derives a controlled JSON/layout sample from the
historical model without calling it an original production run. Current-writer and
synthetic quality samples are additional controls, not additional historical inputs.
This is not an exhaustive repository or historical-corpus inventory.
No external historical manifest/artifact corpus has been supplied for this record;
a claim about one requires the actual bytes, producing version and referenced
artifacts. That input gap does not invalidate the provided-model or current-reader
results. See [migration release support](../../../../tools/ops_runners/migrations/README.md).

`replay --check-only` examines the real persisted dependency graph without executing
the backend. An ordinary replay executes its selected backend and persists its result.
Execution success is separate from verification: `VerificationMode.SKIP` returns
`passed=False` and `skipped=True`, and does not make a successful execution fail.
JSON and text CLI output expose the skip. Bit-exact mode compares result references;
it is not scientific validation. CI-bounded mode currently compares persisted metrics
against a finite, nonnegative relative tolerance. Its `confidence_level` must be a
finite value strictly between 0 and 1 and is not a calibrated statistical interval;
its result explicitly reports
`scientific_qualification=UNQUALIFIED` without a separate domain oracle. Numeric
agreement alone does not establish that scientific oracle. Scientist replay also
preserves the executor's actual terminal status and any produced refs: a failed or
unknown report, or an OK report with no output, is not successful replay under SKIP.

In JSON mode the CLI keeps library diagnostics on stderr and emits one JSON value
on stdout. Human-readable output retains the ordinary diagnostic behavior.

Replay first freezes one verified selected packet manifest/payload view. Its consumed
roles retain the exact manifest `InputRef` profiles through completeness, seed and
environment reads, Foundry/Scientist input construction, and original-result metric
comparison. Conflicting IDs, multiple profiles for one role, and partly selected
bindings refuse execution. ID-only legacy packets retain their bounded compatibility
reader with an explicit `legacy_payload_reference_profiles_not_established` warning;
check-only exposes the same limitation in `reason_codes`. This does not establish
the original producer's metadata view. Child traversals share a bounded remaining
node capacity and root-relative depth. Because overlapping descendants are not
credited before their traversal, a tight capacity can conservatively refuse a
shared DAG whose final union would fit; the refusal does not claim that union was
measured and exceeded the cap. Output ID strings
remain compatible, while `replay_artifact_refs` exposes the actual selected result
views for a fresh CAS reader. A selected original SimulationResult must pass the
existing Foundry execution-source admission, and its plan, bindings, registry and
effective seed must agree with the packet. Replay reuses that admitted request;
it does not reconstruct a weaker request after a source refusal. Without an admitted
original source, the bounded candidate route remains available and reports
`original_execution_source_not_established:legacy_candidate`. Even a packet with
exact input profiles can have this separate limitation. Its output ref remains
profileless and reports `replay_output_profile_not_established:simulation_result`,
rather than claiming stronger output custody from selected inputs alone.

To resume an explicitly chosen original workflow, supply `resume --workflow-ref
sha256:<workflow-id> --workflow-profile sha256:<manifest-profile>`. The pair identifies
the exact selected CAS view. The checkpoint owner verifies and reads its typed
`WorkflowSpec`, then checks the original functional fingerprint before dispatching the
residual workflow. A content ID alone, an unavailable profile, a changed functional
workflow, or simultaneous explicit workflow object/reference is refused. Omitting
the pair preserves the existing default-workflow compatibility route. A dry run only
inspects checkpoint metadata; it does not qualify workflow or execution admission.

All execution routes that call node retry share retained-source workflow intake:
`WorkflowExecutor`, `AsyncWorkflowExecutor`, the serialized `run_node_in_worker`
entry used by local/distributed workers, and public `replay_dead_letter`. An explicit
`ExperimentState.inputs["skg_source_snapshot"]` is resolved from the full profile-bound
CAS descriptor and chunk closure, materialized under the run, and recorded as a run
input before retry. Invalid explicit refs fail closed; they do not fall back to the
current live SKG path. Workers carry only the typed state ref across the existing wire
and reopen local CAS bytes through the store's verified member-read interface; an
attempt-scoped facade may delegate those reads but retains its write revocation. A live
prepared-reader handle remains local and is not transferred to a timeout worker. This
establishes local source replay only, not issuer authenticity, production currentness, or
scientific output dependence. Dead-letter schema `2.0` stores only the selected-profile ref to the
engine-owned `RunInvocationStarted` basis and its lineage edge; it never copies invocation params
into the DLQ payload. Replay re-reads the exact run-owner chain, verifies the basis and selected
`WorkflowSpec` under current CAS access, checks its alias and component identity, then binds the
persisted `NodeInvocation.params` to the replay node. It does not use current `ExperimentState.params`
as a substitute. Older schema `1.0` or unbound records remain listable but replay fails closed with
`dead_letter_dispatch_basis_not_established`; new direct retry callers without an owner-issued attempt
also persist an explicit `not_established` source status.

Tests live under `tests/unit/scientist/replay`.

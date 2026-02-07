# Artifacts — Content-Addressable Storage

CAS хранилище с SHA256 хешированием для неизменяемых артефактов. Дедупликация, provenance tracking, криптографические подписи Ed25519, environment manifests для reproducible симуляций, dependency graph traversal.

## Архитектура

```
artifacts/
├── ids.py          # ArtifactID — SHA256-based идентификатор ("sha256:<64hex>")
├── manifest.py     # ArtifactManifest, ArtifactRef, ProducerInfo, SchemaInfo, InputRef
├── store.py        # FileSystemCAS — CAS на файловой системе, PutOptions, verify, export/import
├── signing.py      # Ed25519 подписи: Ed25519Signer/Verifier, KeyPair, detached signatures
├── environment.py  # EnvironmentManifest — fingerprinting, compatibility scoring
├── graph.py        # DependencyGraph — traversal, completeness checks, replay export
└── registry.py     # RegistryBundle, RegistryBundlePayload
```

## FileSystemCAS — основное хранилище

```python
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions

store = FileSystemCAS(Path("/tmp/artifacts"))
ref = store.put_json(data, PutOptions(kind="result", producer=info))
retrieved = store.get_json(ref.artifact_id)
```

**Layout:** `/artifacts/sha256/ab/cd/abcdef...blob` + `.manifest.json` + `.sig`

**Операции:** `put_json`, `put_bytes`, `get_json`, `get_bytes`, `get_manifest`, `verify`, `export_subgraph`, `import_subgraph`, `sign_artifact`, `verify_signature`, `sign_all_artifacts`, `verify_all_signatures`.

## ArtifactManifest и типизированные ссылки

`ArtifactManifest` — полные метаданные артефакта:
- `artifact_id`, `kind`, `media_type`, `byte_size`
- `producer` (ProducerInfo), `schema` (SchemaInfo), `canon` (CanonInfo)
- `inputs` (list[InputRef]) — provenance
- `integrity` (IntegrityInfo), `env` (EnvInfo), `git` (GitInfo)
- `warnings` (list[WarningRecord])

`ArtifactRef` — базовый класс для typed-ссылок. Контракты в `contracts/` наследуют его с `Literal` kind.

## Cryptographic Signatures (Ed25519)

Detached sidecar-подписи для артефактов:

```python
from polisyos.core.artifacts.signing import Ed25519Signer, Ed25519Verifier

signer = Ed25519Signer.from_env_or_file()
store.sign_artifact(artifact_id, signer, signer_identity="ci-prod")

verifier = Ed25519Verifier(strict_identity=True)
verifier.load_trust_dir(Path(".polisyos/keys/trusted"))
result = store.verify_signature(artifact_id, verifier)
```

**Bulk операции:** `store.verify_all_signatures(verifier, max_workers=8)`, `store.sign_all_artifacts(signer, only_unsigned=True)`.

**Protocols:** `ArtifactSigner`, `ArtifactVerifier` — расширяемые интерфейсы.

## EnvironmentManifest

Захват полного окружения для reproducible симуляций:

```python
from polisyos.core.artifacts.environment import capture_environment, compare_environments

env = capture_environment(project_root=Path("."), include_git=True, include_dependencies=True)
fingerprint = env.fingerprint           # быстрое сравнение
score = env.compatibility_score(other)  # 0.0-1.0
diffs = compare_environments(env1, env2) # анализ различий и рисков
```

**Компоненты:** CPUInfo, GPUInfo, OSInfo, PythonInfo, JAXInfo, GitInfo, DependencyInfo, ContainerInfo, SystemLibraryInfo.

**RiskLevel:** LOW, MEDIUM, HIGH — оценка рисков при различиях окружений.

## Dependency Graph

Traversal зависимостей для replay/completeness checks:

```python
from polisyos.core.artifacts.graph import resolve_dependency_graph

graph = resolve_dependency_graph(store, root_id, max_depth=200, verify_integrity=True)
assert graph.is_complete
ids = graph.all_artifact_ids()

# Export/Import для офлайн replay
bundle = store.export_subgraph(ids, Path("/tmp/replay.tar.gz"))
restored = FileSystemCAS(Path("/tmp/offline"))
restored.import_subgraph(bundle.output_path, verify_integrity=True)
```

**NodeStatus:** PRESENT, MISSING, MISSING_BLOB, MISSING_MANIFEST, CORRUPTED, SKIPPED_MAX_DEPTH.

## Использование в системе

| Модуль | Что использует |
|--------|---------------|
| **Fabric** | `store`, `ids`, evidence с provenance |
| **Foundry** | `store`, environment manifests, результаты симуляций |
| **Scientist** | `store`, `manifest`, артефакты экспериментов |
| **Lex** | `store`, `ids`, corpus, normpack assembly |
| **Runtime** | `environment`, `graph`, replay, `canon` |
| **Audit** | `graph`, `signing`, `store`, `manifest` — сборка аудит-пакетов |
| **Scholar** | `store`, `ids`, `manifest`, knowledge bundles |

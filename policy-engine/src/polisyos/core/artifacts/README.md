# Artifacts — CAS и воспроизводимость

`core.artifacts` реализует content-addressable storage (SHA-256) и метаданные артефактов: manifests, подписи, зависимости и fingerprint окружения.

## Состав

```text
artifacts/
├── ids.py               # ArtifactID
├── manifest.py          # ArtifactManifest/ArtifactRef/InputRef/SchemaInfo/...
├── store.py             # FileSystemCAS, PutOptions, verify/export/import/sign ops
├── signing.py           # Ed25519 signer/verifier + trust/revocation config
├── graph.py             # DependencyGraph + resolve_dependency_graph()
├── registry.py          # RegistryBundlePayload/RegistryBundle
├── environment.py       # facade -> environment_parts
├── environment_parts.py # public env API
└── _env_*.py            # capture/comparison/models/utils internals
```

## FileSystemCAS

Layout на диске:
- `artifacts/sha256/<ab>/<cd>/<hex>.blob`
- `artifacts/sha256/<ab>/<cd>/<hex>.manifest.json`
- `artifacts/sha256/<ab>/<cd>/<hex>.sig` (если подписан)

Базовый сценарий:

```python
from pathlib import Path

from polisyos.core.artifacts import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes

store = FileSystemCAS(Path(".polisyos"))
ref = store.put_json(
    {"status": "ok"},
    PutOptions(kind="scientist.decision_packet", media_type="application/json"),
)

payload = from_canonical_bytes(store.get_bytes(ref.artifact_id))
manifest = store.get_manifest(ref.artifact_id)
check = store.verify(ref.artifact_id)
```

Ключевые операции:
- запись: `put_bytes`, `put_json`
- чтение: `get_bytes`, `get_manifest`, `get_signature`
- целостность: `verify`
- перенос подграфа: `export_subgraph`, `import_subgraph`
- подписи: `sign_artifact`, `verify_signature`, `sign_all_artifacts`, `verify_all_signatures`

## Manifests и provenance

`ArtifactManifest` связывает payload и контекст исполнения:
- идентичность и формат (`artifact_id`, `kind`, `media_type`, `byte_size`)
- schema/canon (`SchemaInfo`, `CanonInfo`)
- происхождение (`producer`, `env`, `inputs`)
- integrity (`sha256`) и предупреждения.

`ArtifactRef` — базовый typed-link для контрактов из `core.contracts`.

## Подписи

Поддерживаются detached Ed25519 подписи и trust-модель с revocation.

Что важно:
- поддержка sign-on-put через `SigningConfig.from_env()`;
- batch-подпись/верификация для больших CAS;
- строгая проверка identity при необходимости.

## Environment manifests

`capture_environment()` и `compare_environments()` дают reproducibility fingerprint:
- runtime/platform (OS, Python, CPU/GPU, контейнер);
- зависимости и системные библиотеки;
- git/TEE контекст (если доступен);
- risk-level diff для replay/validation.

## Где используется

- `foundry`, `scientist`, `fabric`, `scholar`: хранение результатов и промежуточных артефактов.
- `registry`: registry bundle artifacts (`core.registry_bundle`, `core.registry_compose_report`).
- `audit`: сборка переносимых audit package.
- `runtime`: lineage/replay и проверки целостности.

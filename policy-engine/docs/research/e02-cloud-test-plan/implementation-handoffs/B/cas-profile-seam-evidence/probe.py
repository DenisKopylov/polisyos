from pathlib import Path
from tempfile import TemporaryDirectory
from polisyos.core.artifacts import FileSystemCAS, PutOptions, artifact_manifest_profile_projection, artifact_manifest_profile_sha256
from polisyos.core.artifacts._manifest_lifecycle import ManifestLifecycle
with TemporaryDirectory() as root:
    cas = FileSystemCAS(Path(root))
    ref = cas.put_bytes(b"profile seam", opts=PutOptions(kind="test", media_type="application/octet-stream"))
    current = cas.get_manifest(ref)
    for version in ("v1", "v2", "v3"):
        manifest = current.model_copy(update={"manifest_schema_version": version})
        if artifact_manifest_profile_projection(manifest) != ManifestLifecycle.profile_projection(manifest):
            raise RuntimeError(version)
        if artifact_manifest_profile_sha256(manifest) != ManifestLifecycle.profile_sha256(manifest):
            raise RuntimeError(version)
    print("PASS: real persisted manifest; facade projection/digest identical to canonical owner for v1/v2/v3")

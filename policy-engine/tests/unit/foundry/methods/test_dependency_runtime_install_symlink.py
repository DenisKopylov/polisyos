from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from polisyos.foundry.methods.catalog import dependency_authority as authority_module
from polisyos.foundry.methods.catalog import dependency_evidence as evidence_module
from tests.unit.foundry.methods import test_dependency_profile as fixtures


def test_candidate_runtime_installation_resolves_environment_python_symlink(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime_root, _stdlib = fixtures._candidate_runtime_tree(tmp_path / "runtime")
    environment_root = tmp_path / "environment"
    environment_python = environment_root / "bin" / "python"
    environment_python.parent.mkdir(parents=True)
    environment_python.symlink_to(runtime_root / "bin" / "python")

    _repo_root, _product_root, source_freeze = fixtures._install_clean_source_fixture(
        monkeypatch, tmp_path / "source-fixture"
    )
    source = authority_module._build_production_canonical_source_resolver().resolve(
        request=fixtures._authority_request(tmp_path, source_freeze=source_freeze)
    )
    assert isinstance(source, authority_module.CanonicalFoundrySourceAuthority)

    installation: authority_module.CandidatePythonRuntimeInstallation | None = None
    verified: authority_module.VerifiedPythonRuntime | None = None
    try:
        with authority_module._unwrap_owner_capability(
            source, authority_module._CANONICAL_SOURCE_SPEC
        ) as source_payload:
            nonce = evidence_module.domain_digest(
                evidence_module.DigestDomain.ENVIRONMENT_INSTANCE,
                b"environment-python-symlink-installation",
            )
            expected = authority_module.observe_candidate_python_runtime(
                environment_root=environment_root,
                runtime_root=runtime_root,
                environment_creation_nonce=nonce,
                executable_relative_path=evidence_module.RootedRelativePath(value="bin/python"),
                version="3.14",
                platform_tag="macosx_15_0_arm64",
                abi_tag="cp314",
                digest_registry=source_payload.digest_registry,
            )
            assert isinstance(expected, authority_module.CandidatePythonRuntimeObservation)
            source_binding = evidence_module.PythonRuntimeSourceBindingStatement(
                schema_version="polisyos.foundry.python-runtime-source-binding.v1",
                selected_artifact_ref=fixtures._c1_ref(
                    evidence_module.DigestDomain.TOOLCHAIN_SELECTED,
                    "symlink-python-artifact",
                ),
                runtime_manifest_ref=expected.root_identity.second_walk_manifest_ref,
                installation_transform="python_runtime_installation_v1",
            )
            admission = evidence_module.PythonRuntimeAdmission(
                artifact_role="python_runtime",
                version="3.14",
                platform_tag="macosx_15_0_arm64",
                selected_artifact_ref=source_binding.selected_artifact_ref,
                executable_blob_ref=fixtures._c1_ref(
                    evidence_module.DigestDomain.TOOLCHAIN_EXECUTABLE,
                    "symlink-python-executable",
                ),
                expected_runtime_manifest_ref=expected.root_identity.second_walk_manifest_ref,
                expected_runtime_source_binding_ref=authority_module.build_foundry_statement_ref(
                    evidence_module.DigestDomain.TOOLCHAIN_RUNTIME_BINDING,
                    source_binding,
                ),
                verifier_provenance_ref=fixtures._c1_ref(
                    evidence_module.DigestDomain.VERIFIER_PROVENANCE,
                    "symlink-runtime-verifier",
                ),
            )
            built = authority_module.build_candidate_python_runtime_installation(
                source_authority=source_payload,
                environment_root=environment_root,
                admission=admission,
                environment_creation_nonce=nonce,
                installer_provenance_ref=fixtures._c1_ref(
                    evidence_module.DigestDomain.VERIFIER_PROVENANCE,
                    "symlink-runtime-installer",
                ),
            )
            assert isinstance(built, authority_module.CandidatePythonRuntimeInstallation)
            installation = built
            assert built.observation.root_identity == expected.root_identity
            assert (
                built.persisted.statement.runtime_root_identity.runtime_root_path_hash
                == evidence_module.domain_digest(
                    evidence_module.DigestDomain.TOOLCHAIN_RUNTIME_ROOT_PATH,
                    str(runtime_root.resolve()).encode(),
                )
            )
            observer = authority_module._ProductionPythonRuntimeObserver(
                source_authority=source_payload
            )

        result = observer.observe_and_verify(
            environment_root=environment_root,
            installation=installation.capability,
            admission=admission,
        )
        assert isinstance(result, authority_module.VerifiedPythonRuntime)
        verified = result

        copied_runtime = tmp_path / "copied-runtime"
        shutil.copytree(runtime_root, copied_runtime)
        environment_python.unlink()
        environment_python.symlink_to(copied_runtime / "bin" / "python")
        redirected = observer.observe_and_verify(
            environment_root=environment_root,
            installation=installation.capability,
            admission=admission,
        )
        assert isinstance(redirected, authority_module.RejectedAuthorityPredicate)
        assert (
            redirected.failure_code is authority_module.AuthorityFailureCode.PYTHON_RUNTIME_MISMATCH
        )
    finally:
        if verified is not None:
            authority_module._release_owner_capability(
                verified, authority_module._VERIFIED_RUNTIME_SPEC
            )
        if installation is not None:
            authority_module._release_owner_capability(
                installation.capability, authority_module._RUNTIME_INSTALLATION_SPEC
            )
        authority_module._release_owner_capability(source, authority_module._CANONICAL_SOURCE_SPEC)

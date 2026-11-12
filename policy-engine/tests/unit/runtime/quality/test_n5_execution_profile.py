"""Tests for native N5 execution-profile observation."""

from __future__ import annotations

from email.message import Message
from importlib.machinery import ModuleSpec
from pathlib import Path
from types import ModuleType

import pytest

import polisyos.runtime.quality.n5_execution_profile as profile_module
from polisyos.runtime.quality.n5_execution_profile import (
    N5BackendObservation,
    _observe_loaded_module_images,
    bind_n5_backend_observation,
    observe_n5_native_execution_profile,
)


class _Distribution:
    def __init__(self, name: str | None, version: str | None, path: str) -> None:
        headers = Message()
        if name is not None:
            headers["Name"] = name
        if version is not None:
            headers["Version"] = version
        self.metadata = headers
        self._version = version
        self._path = Path(path)
        self._path.mkdir(parents=True, exist_ok=True)

    @property
    def version(self) -> str:
        if self._version is None:
            raise ValueError("version missing")
        return self._version


def _patch_distributions(monkeypatch: pytest.MonkeyPatch, distributions: list[object]) -> None:
    from importlib import metadata

    monkeypatch.setattr(metadata, "distributions", lambda: iter(distributions))


def _patch_module_observation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    first_party_root = _first_party_root(tmp_path)
    provider = tmp_path / "site-packages" / "profile_fixture.py"
    provider.parent.mkdir(parents=True, exist_ok=True)
    provider.write_bytes(b"fixture_provider = True\n")
    interpreter = tmp_path / "venv" / "bin" / "python"
    interpreter.parent.mkdir(parents=True, exist_ok=True)
    interpreter.write_bytes(b"fixture-interpreter-image")
    module = ModuleType("profile_fixture")
    module.__spec__ = ModuleSpec("profile_fixture", loader=None, origin=str(provider))
    observation = _observe_loaded_module_images(
        first_party_root=first_party_root,
        modules={"profile_fixture": module},
        sys_path=(str(tmp_path),),
        interpreter_path=str(interpreter),
    )
    monkeypatch.setattr(
        profile_module,
        "_observe_loaded_module_images",
        lambda **_kwargs: observation,
    )


def _first_party_root(tmp_path: Path) -> Path:
    root = tmp_path / "src" / "polisyos"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _backend() -> N5BackendObservation:
    return N5BackendObservation(
        backend_name="cpu",
        backend_version="0.0",
        device_platforms=("cpu",),
        x64_enabled=True,
        numerical_policy=(),
        observation_provenance="recomputed",
    )


def _profile_for_module_set(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    modules: dict[str, ModuleType | None],
    *,
    entrypoint_module_names: tuple[str, ...] = (),
    declared_settings: dict[str, object] | None = None,
    backend: N5BackendObservation | None = None,
    include_extra_distribution: bool = False,
):
    first_party_root = _first_party_root(tmp_path)
    provider_root = tmp_path / "site-packages"
    provider_root.mkdir(parents=True, exist_ok=True)
    interpreter = tmp_path / "venv" / "bin" / "python"
    interpreter.parent.mkdir(parents=True, exist_ok=True)
    interpreter.write_bytes(b"fixture-interpreter-image")
    observation = _observe_loaded_module_images(
        first_party_root=first_party_root,
        modules=modules,
        sys_path=(str(tmp_path),),
        interpreter_path=str(interpreter),
        entrypoint_module_names=entrypoint_module_names,
    )
    monkeypatch.setattr(
        profile_module,
        "_observe_loaded_module_images",
        lambda **_kwargs: observation,
    )
    distributions: list[object] = [
        _Distribution("demo-package", "1.0", str(tmp_path / "demo.dist-info"))
    ]
    if include_extra_distribution:
        distributions.append(
            _Distribution("reader-dependency", "2.0", str(tmp_path / "reader.dist-info"))
        )
    _patch_distributions(monkeypatch, distributions)
    profile = observe_n5_native_execution_profile(
        first_party_root=first_party_root,
        declared_settings=declared_settings or {"replications": 3, "numeric_mode": "float64"},
        entrypoint_module_names=entrypoint_module_names,
    )
    return bind_n5_backend_observation(profile, backend or _backend())


def _module(name: str, path: Path) -> ModuleType:
    module = ModuleType(name)
    module.__spec__ = ModuleSpec(name, loader=None, origin=str(path))
    return module


def _modules_with_three_provider_paths(tmp_path: Path, count: int) -> dict[str, ModuleType]:
    modules: dict[str, ModuleType] = {}
    provider_root = tmp_path / "site-packages"
    provider_root.mkdir(parents=True, exist_ok=True)
    for index in range(count):
        name = f"provider_{index}"
        origin = provider_root / f"{name}_origin.py"
        source = provider_root / f"{name}_source.py"
        bytecode = provider_root / f"{name}.pyc"
        origin.write_bytes(f"origin_{index} = True\n".encode())
        source.write_bytes(f"source_{index} = True\n".encode())
        bytecode.write_bytes(f"bytecode_{index}".encode())
        module = _module(name, origin)
        module.__file__ = str(source)
        module.__cached__ = str(bytecode)
        modules[name] = module
    return modules


def test_different_installed_inventory_changes_profile_for_same_declared_settings(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    first_party_root = _first_party_root(tmp_path)
    _patch_module_observation(monkeypatch, tmp_path)
    first = _Distribution("demo-package", "1.0", str(tmp_path / "demo-1.dist-info"))
    second = _Distribution("optional-wrapper", "2.0", str(tmp_path / "wrapper.dist-info"))
    _patch_distributions(monkeypatch, [first])
    profile_one = observe_n5_native_execution_profile(
        first_party_root=first_party_root,
        declared_settings={"replications": 3, "numeric_mode": "float64"},
    )

    _patch_distributions(monkeypatch, [first, second])
    profile_two = observe_n5_native_execution_profile(
        first_party_root=first_party_root,
        declared_settings={"replications": 3, "numeric_mode": "float64"},
    )

    assert profile_one.declared_settings == profile_two.declared_settings
    assert profile_one.content_hash != profile_two.content_hash
    assert profile_one.numerical_profile_content_hash != profile_two.numerical_profile_content_hash
    assert len(profile_two.distributions) == 2
    assert profile_two.distribution_census_status == "recomputed"
    assert profile_two.profile_identity_predicate == "not_established"
    assert profile_two.institutional_profile_admission == "not_established"


def test_operational_budget_is_not_a_profile_input(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    first_party_root = _first_party_root(tmp_path)
    _patch_module_observation(monkeypatch, tmp_path)
    _patch_distributions(
        monkeypatch,
        [_Distribution("demo-package", "1.0", str(tmp_path / "demo.dist-info"))],
    )
    profile_without_budget = observe_n5_native_execution_profile(
        first_party_root=first_party_root, declared_settings={"replications": 3}
    )
    operational_budget = {"budget_ref": "quota-1", "invocation_limit": 4}
    profile_with_budget_in_outer_request = observe_n5_native_execution_profile(
        first_party_root=first_party_root,
        declared_settings={"replications": 3},
        operational_settings=operational_budget,
    )

    assert profile_without_budget.content_hash == profile_with_budget_in_outer_request.content_hash
    assert "budget_ref" not in {
        setting.name for setting in profile_without_budget.declared_settings
    }


def test_duplicate_or_unknown_distribution_metadata_refuses_comparability(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    first_party_root = _first_party_root(tmp_path)
    _patch_module_observation(monkeypatch, tmp_path)
    duplicate_a = _Distribution("same-name", "1", str(tmp_path / "same-a.dist-info"))
    duplicate_b = _Distribution("SAME_NAME", "2", str(tmp_path / "same-b.dist-info"))
    duplicate_location = _Distribution("other-name", "3", str(tmp_path / "same-b.dist-info"))
    unknown = _Distribution(None, "3", str(tmp_path / "unknown.dist-info"))
    _patch_distributions(monkeypatch, [duplicate_a, duplicate_b, duplicate_location, unknown])

    profile = observe_n5_native_execution_profile(first_party_root=first_party_root)

    assert len(profile.distributions) == 4
    assert profile.distribution_census_status == "not_established"
    assert profile.profile_identity_predicate == "not_established"
    assert "distribution_name_ambiguous" in profile.reason_codes
    assert "distribution_location_ambiguous" in profile.reason_codes
    assert any(row.row_status == "not_established" for row in profile.distributions)


def test_backend_must_be_observed_and_is_content_bound(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    first_party_root = _first_party_root(tmp_path)
    _patch_module_observation(monkeypatch, tmp_path)
    _patch_distributions(
        monkeypatch,
        [_Distribution("demo-package", "1", str(tmp_path / "demo.dist-info"))],
    )
    native = observe_n5_native_execution_profile(first_party_root=first_party_root)
    bound = bind_n5_backend_observation(native, _backend())

    assert native.backend_predicate == "not_established"
    assert native.profile_identity_predicate == "not_established"
    assert bound.backend_predicate == "recomputed"
    assert bound.profile_identity_predicate == "recomputed"
    assert bound.content_hash != native.content_hash
    assert bound.file_backed_module_bytes_predicate == "recomputed"
    assert bound.institutional_profile_admission == "not_established"


def test_native_observer_has_no_backend_callback_or_arbitrary_environment_port() -> None:
    import inspect

    parameters = inspect.signature(observe_n5_native_execution_profile).parameters

    assert set(parameters) == {
        "first_party_root",
        "declared_settings",
        "operational_settings",
        "entrypoint_module_names",
    }
    assert "backend_observer" not in parameters
    assert "environment" not in parameters


def test_profile_dto_rejects_extra_fields(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    first_party_root = _first_party_root(tmp_path)
    _patch_module_observation(monkeypatch, tmp_path)
    from pydantic import ValidationError

    _patch_distributions(
        monkeypatch,
        [_Distribution("demo-package", "1", str(tmp_path / "demo.dist-info"))],
    )
    profile = observe_n5_native_execution_profile(first_party_root=first_party_root)
    payload = profile.model_dump(mode="json")
    payload["caller_profile_name"] = "trusted"

    with pytest.raises(ValidationError):
        type(profile).model_validate(payload, strict=True)


def test_loaded_external_file_bytes_change_with_same_module_identity(tmp_path: Path) -> None:
    first_party_root = _first_party_root(tmp_path)
    provider = tmp_path / "site-packages" / "sample_provider.py"
    provider.parent.mkdir()
    provider.write_bytes(b"provider = 'first'\n")
    interpreter = tmp_path / "venv" / "bin" / "python"
    interpreter.parent.mkdir(parents=True)
    interpreter.write_bytes(b"interpreter-image")
    module = ModuleType("sample_provider")
    module.__spec__ = ModuleSpec("sample_provider", loader=None, origin=str(provider))
    modules = {"sample_provider": module}
    profile_inputs = {
        "first_party_root": first_party_root,
        "modules": modules,
        "sys_path": (str(tmp_path),),
        "interpreter_path": str(interpreter),
    }

    before = _observe_loaded_module_images(**profile_inputs)
    provider.write_bytes(b"provider = 'second'\n")
    after = _observe_loaded_module_images(**profile_inputs)

    before_row = next(row for row in before.file_images if row.module_names == ("sample_provider",))
    after_row = next(row for row in after.file_images if row.module_names == ("sample_provider",))
    assert before_row.content_hash != after_row.content_hash
    assert before.file_backed_bytes_predicate == "recomputed"
    assert before.source_code_association_predicate == "not_established"


def test_first_party_source_is_delegated_to_production_image(tmp_path: Path) -> None:
    first_party_root = _first_party_root(tmp_path)
    source = first_party_root / "runtime.py"
    source.write_text("value = 1\n", encoding="utf-8")
    interpreter = tmp_path / "venv" / "bin" / "python"
    interpreter.parent.mkdir(parents=True)
    interpreter.write_bytes(b"interpreter-image")
    module = ModuleType("polisyos.runtime")
    module.__spec__ = ModuleSpec("polisyos.runtime", loader=None, origin=str(source))

    observation = _observe_loaded_module_images(
        first_party_root=first_party_root,
        modules={"polisyos.runtime": module},
        sys_path=(str(first_party_root.parent), str(tmp_path)),
        interpreter_path=str(interpreter),
    )

    source_row = next(
        row for row in observation.file_images if row.module_names == ("polisyos.runtime",)
    )
    assert source_row.coverage == "delegated_to_n5_production_image"
    assert source_row.content_hash is None
    assert observation.first_party_coverage == "delegated_to_n5_production_image"


def test_module_subclass_getattr_is_never_called(tmp_path: Path) -> None:
    first_party_root = _first_party_root(tmp_path)
    interpreter = tmp_path / "venv" / "bin" / "python"
    interpreter.parent.mkdir(parents=True)
    interpreter.write_bytes(b"interpreter-image")

    class CallbackModule(ModuleType):
        callbacks = 0

        def __getattr__(self, name: str) -> object:
            self.callbacks += 1
            raise AssertionError(name)

    module = CallbackModule("dynamic")
    observation = _observe_loaded_module_images(
        first_party_root=first_party_root,
        modules={"dynamic": module},
        sys_path=(str(tmp_path),),
        interpreter_path=str(interpreter),
    )

    assert type.__getattribute__(type(module), "callbacks") == 0
    assert observation.census_predicate == "recomputed"
    assert "dynamic" in observation.no_file_modules


def test_module_subclass_getattribute_is_bypassed_for_native_dict_read(tmp_path: Path) -> None:
    first_party_root = _first_party_root(tmp_path)
    interpreter = tmp_path / "venv" / "bin" / "python"
    interpreter.parent.mkdir(parents=True)
    interpreter.write_bytes(b"interpreter-image")

    class GuardedModule(ModuleType):
        callbacks = 0

        def __getattribute__(self, name: str) -> object:
            type.__setattr__(
                type(self), "callbacks", type.__getattribute__(type(self), "callbacks") + 1
            )
            raise AssertionError(name)

    module = GuardedModule.__new__(GuardedModule)
    ModuleType.__init__(module, "guarded")
    type.__setattr__(GuardedModule, "callbacks", 0)
    observation = _observe_loaded_module_images(
        first_party_root=first_party_root,
        modules={"guarded": module},
        sys_path=(str(tmp_path),),
        interpreter_path=str(interpreter),
    )

    assert type.__getattribute__(GuardedModule, "callbacks") == 0
    assert observation.census_predicate == "recomputed"
    assert observation.no_file_modules == ("guarded",)


def test_no_file_module_is_a_declared_closure_residual(tmp_path: Path) -> None:
    first_party_root = _first_party_root(tmp_path)
    interpreter = tmp_path / "venv" / "bin" / "python"
    interpreter.parent.mkdir(parents=True)
    interpreter.write_bytes(b"interpreter-image")

    observation = _observe_loaded_module_images(
        first_party_root=first_party_root,
        modules={"pending-import": None},
        sys_path=(str(tmp_path),),
        interpreter_path=str(interpreter),
    )

    assert observation.no_file_modules == ("pending-import",)
    assert observation.census_predicate == "recomputed"
    assert observation.file_backed_bytes_predicate == "recomputed"


def test_empty_module_mapping_without_interpreter_image_is_not_a_pass(tmp_path: Path) -> None:
    first_party_root = _first_party_root(tmp_path)

    observation = _observe_loaded_module_images(
        first_party_root=first_party_root,
        modules={},
        sys_path=(str(tmp_path),),
        interpreter_path="",
    )

    assert observation.loaded_module_count == 0
    assert observation.file_images == ()
    assert observation.census_predicate == "not_established"
    assert observation.file_backed_bytes_predicate == "not_established"
    assert "interpreter_binary_not_established" in observation.reason_codes


def test_module_image_cap_covers_three_paths_for_every_bounded_module(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module_limit = 4
    monkeypatch.setattr(profile_module, "_MAX_MODULES", module_limit)
    monkeypatch.setattr(
        profile_module,
        "_MAX_MODULE_FILES",
        module_limit * profile_module._MAX_PROVIDER_PATHS_PER_MODULE + 1,
    )
    modules = _modules_with_three_provider_paths(tmp_path, module_limit)
    interpreter = tmp_path / "venv" / "bin" / "python"
    interpreter.parent.mkdir(parents=True)
    interpreter.write_bytes(b"interpreter-image")

    observation = _observe_loaded_module_images(
        first_party_root=_first_party_root(tmp_path),
        modules=modules,
        sys_path=(str(tmp_path),),
        interpreter_path=str(interpreter),
    )

    expected_image_cap = 3 * module_limit + 1
    assert expected_image_cap == profile_module._MAX_MODULE_FILES
    assert len(observation.file_images) == expected_image_cap
    assert observation.census_predicate == "recomputed"
    assert observation.file_backed_bytes_predicate == "recomputed"
    assert observation.reason_codes == ()


def test_module_image_denominator_overflow_remains_not_established(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    modules = _modules_with_three_provider_paths(tmp_path, count=4)
    monkeypatch.setattr(profile_module, "_MAX_MODULE_FILES", 10)
    interpreter = tmp_path / "venv" / "bin" / "python"
    interpreter.parent.mkdir(parents=True)
    interpreter.write_bytes(b"interpreter-image")

    observation = _observe_loaded_module_images(
        first_party_root=_first_party_root(tmp_path),
        modules=modules,
        sys_path=(str(tmp_path),),
        interpreter_path=str(interpreter),
    )

    assert len(observation.file_images) == 10
    assert observation.census_predicate == "not_established"
    assert observation.file_backed_bytes_predicate == "not_established"
    assert "loaded_module_file_denominator_over_limit" in observation.reason_codes
    assert "<module-file-denominator-over-limit>" in observation.unclassified_modules


def test_profile_reconciliation_ignores_extra_ambient_provider_images(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    provider = tmp_path / "site-packages" / "selected_provider.py"
    ambient = tmp_path / "site-packages" / "reader_helper.py"
    provider.parent.mkdir(parents=True)
    provider.write_bytes(b"selected = True\n")
    ambient.write_bytes(b"reader = True\n")
    recorded = _profile_for_module_set(
        monkeypatch, tmp_path, {"selected_provider": _module("selected_provider", provider)}
    )
    current = _profile_for_module_set(
        monkeypatch,
        tmp_path,
        {
            "selected_provider": _module("selected_provider", provider),
            "reader_helper": _module("reader_helper", ambient),
        },
    )

    comparison = profile_module.reconcile_recorded_n5_profile_content(recorded, current)

    assert recorded.content_hash != current.content_hash
    assert recorded.numerical_profile_content_hash != current.numerical_profile_content_hash
    assert comparison.status == "recomputed"
    assert comparison.matched_provider_identities
    assert comparison.missing_provider_identities == ()


def test_profile_reconciliation_rejects_changed_recorded_provider_bytes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    provider = tmp_path / "site-packages" / "selected_provider.py"
    provider.parent.mkdir(parents=True)
    provider.write_bytes(b"selected = True\n")
    recorded = _profile_for_module_set(
        monkeypatch, tmp_path, {"selected_provider": _module("selected_provider", provider)}
    )
    provider.write_bytes(b"selected = False\n")
    current = _profile_for_module_set(
        monkeypatch, tmp_path, {"selected_provider": _module("selected_provider", provider)}
    )

    comparison = profile_module.reconcile_recorded_n5_profile_content(recorded, current)

    assert comparison.status == "changed"
    assert comparison.changed_provider_identities
    assert comparison.missing_provider_identities == ()


def test_profile_reconciliation_requires_recorded_provider_to_be_present(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    provider = tmp_path / "site-packages" / "selected_provider.py"
    provider.parent.mkdir(parents=True)
    provider.write_bytes(b"selected = True\n")
    recorded = _profile_for_module_set(
        monkeypatch, tmp_path, {"selected_provider": _module("selected_provider", provider)}
    )
    current = _profile_for_module_set(monkeypatch, tmp_path, {})

    comparison = profile_module.reconcile_recorded_n5_profile_content(recorded, current)

    assert comparison.status == "not_established"
    assert comparison.missing_provider_identities


def test_entrypoint_image_is_audited_but_outside_provider_identity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    host = tmp_path / "reader.py"
    host.write_bytes(b"reader = 1\n")
    first = _profile_for_module_set(
        monkeypatch,
        tmp_path,
        {"reader": _module("reader", host)},
        entrypoint_module_names=("reader",),
    )
    host.write_bytes(b"reader = 2\n")
    second = _profile_for_module_set(
        monkeypatch,
        tmp_path,
        {"reader": _module("reader", host)},
        entrypoint_module_names=("reader",),
    )

    comparison = profile_module.reconcile_recorded_n5_profile_content(first, second)

    assert first.content_hash != second.content_hash
    assert first.numerical_profile_content_hash == second.numerical_profile_content_hash
    assert first.loaded_module_observation.entrypoint_modules == ("reader",)
    assert comparison.status == "recomputed"
    assert first.institutional_profile_admission == "not_established"


@pytest.mark.parametrize(
    ("changed_fields", "expected_reason"),
    [
        ({"include_extra_distribution": True}, "profile_content_changed"),
        (
            {"declared_settings": {"replications": 4, "numeric_mode": "float64"}},
            "profile_content_changed",
        ),
        (
            {
                "backend": N5BackendObservation(
                    backend_name="gpu",
                    backend_version="0.0",
                    device_platforms=("gpu",),
                    x64_enabled=True,
                    observation_provenance="recomputed",
                )
            },
            "profile_content_changed",
        ),
    ],
)
def test_profile_reconciliation_detects_declared_profile_changes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    changed_fields: dict[str, object],
    expected_reason: str,
) -> None:
    provider = tmp_path / "site-packages" / "selected_provider.py"
    provider.parent.mkdir(parents=True)
    provider.write_bytes(b"selected = True\n")
    recorded = _profile_for_module_set(
        monkeypatch,
        tmp_path,
        {"selected_provider": _module("selected_provider", provider)},
    )
    current = _profile_for_module_set(
        monkeypatch,
        tmp_path,
        {"selected_provider": _module("selected_provider", provider)},
        **changed_fields,
    )

    comparison = profile_module.reconcile_recorded_n5_profile_content(recorded, current)

    assert comparison.status == "changed"
    assert expected_reason in comparison.reason_codes

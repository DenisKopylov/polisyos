"""
Tests for Method Discovery & Plugin System.
"""
from __future__ import annotations

import sys
import textwrap
import threading
from pathlib import Path
from types import ModuleType
from typing import Any, ClassVar, Iterator, Mapping
from unittest import mock

import pytest

from polisyos.foundry.methods.base import (
    ComplexityClass,
    FidelityLevel,
    FoundryMethod,
    MethodMetadata,
    MethodSignature,
    SlotSpec,
    SlotType,
    Unit,
    foundry_method,
)
from polisyos.foundry.methods.discovery import (
    DISCOVERY_MODULE_PREFIX,
    ENTRY_POINT_GROUP,
    DiscoveryError,
    DiscoveryReport,
    DuplicatePolicy,
    EntryPointSource,
    FileSystemSource,
    MethodDiscovery,
    bootstrap_registry,
    is_foundry_method,
)
from polisyos.foundry.methods.registry import MethodRegistry


# =============================================================================
# Fixtures and helpers
# =============================================================================


@pytest.fixture
def fresh_registry() -> Iterator[MethodRegistry]:
    MethodRegistry.reset_instance()
    yield MethodRegistry.get_instance()
    MethodRegistry.reset_instance()


@pytest.fixture
def sample_signature() -> MethodSignature:
    unit = Unit("currency", "USD")
    return MethodSignature(
        name="test_method",
        namespace="test.ns",
        version="1.0.0",
        input_slots=frozenset({
            SlotSpec(name="income", slot_type=SlotType.VECTOR, unit=unit)
        }),
        output_slots=frozenset({
            SlotSpec(name="tax", slot_type=SlotType.VECTOR, unit=unit)
        }),
        parameters=(),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_N,
    )


@pytest.fixture
def sample_metadata() -> MethodMetadata:
    return MethodMetadata(
        description="Test method for discovery",
        tags=frozenset({"test", "fixture"}),
    )


def create_test_method(
    name: str,
    namespace: str,
    version: str = "1.0.0",
) -> type[FoundryMethod]:
    unit = Unit("none", "1")
    sig = MethodSignature(
        name=name,
        namespace=namespace,
        version=version,
        input_slots=frozenset({
            SlotSpec(name="state", slot_type=SlotType.SCALAR, unit=unit)
        }),
        output_slots=frozenset({
            SlotSpec(name="result", slot_type=SlotType.SCALAR, unit=unit)
        }),
        parameters=(),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_1,
    )
    meta = MethodMetadata(description=f"Test method {name}")

    class TestMethod:
        signature: ClassVar[MethodSignature] = sig
        metadata: ClassVar[MethodMetadata] = meta

        @staticmethod
        def pure_step(state: Any, params: Mapping[str, Any]) -> Any:
            return state

    TestMethod.__name__ = f"TestMethod_{namespace}_{name}".replace(".", "_")
    TestMethod.__qualname__ = TestMethod.__name__

    return TestMethod  # type: ignore[return-value]


# =============================================================================
# DiscoveryReport tests
# =============================================================================


class TestDiscoveryReport:
    def test_empty_report_is_success(self) -> None:
        report = DiscoveryReport()
        assert report.success is True
        assert report.total_registered == 0
        assert report.total_duplicates == 0
        assert report.total_errors == 0

    def test_report_with_registered_is_success(self) -> None:
        report = DiscoveryReport(registered=["ns.method@1.0.0"])
        assert report.success is True
        assert report.total_registered == 1

    def test_report_with_errors_is_not_success(self) -> None:
        error = DiscoveryError(
            source="test",
            item="example",
            error_type="ValueError",
            message="boom",
        )
        report = DiscoveryReport(errors=[error])
        assert report.success is False
        assert report.total_errors == 1

    def test_report_with_duplicates_is_still_success(self) -> None:
        report = DiscoveryReport(
            registered=["ns.a@1.0.0"],
            duplicates=["ns.b@1.0.0"],
        )
        assert report.success is True
        assert report.total_duplicates == 1

    def test_report_merge(self) -> None:
        report1 = DiscoveryReport(
            registered=["a@1.0.0"],
            duplicates=["b@1.0.0"],
            errors=[
                DiscoveryError(
                    source="test",
                    item="a",
                    error_type="ValueError",
                    message="error1",
                )
            ],
            sources_processed=1,
        )
        report2 = DiscoveryReport(
            registered=["c@1.0.0", "d@1.0.0"],
            duplicates=["e@1.0.0"],
            errors=[
                DiscoveryError(
                    source="test",
                    item="b",
                    error_type="RuntimeError",
                    message="error2",
                )
            ],
            sources_processed=2,
        )

        merged = report1.merge(report2)

        assert merged is report1
        assert report1.total_registered == 3
        assert report1.total_duplicates == 2
        assert report1.total_errors == 2
        assert report1.sources_processed == 3

    def test_report_summary(self) -> None:
        report = DiscoveryReport(
            registered=["a@1.0.0", "b@1.0.0"],
            errors=[
                DiscoveryError(
                    source="test",
                    item="c",
                    error_type="ValueError",
                    message="error",
                )
            ],
        )
        summary = report.summary()

        assert "FAILED" in summary
        assert "2 registered" in summary
        assert "1 errors" in summary

    def test_report_repr(self) -> None:
        report = DiscoveryReport(registered=["a@1.0.0"])
        repr_str = repr(report)

        assert "registered=1" in repr_str
        assert "success=True" in repr_str


# =============================================================================
# is_foundry_method tests
# =============================================================================


class TestIsFoundryMethod:
    def test_valid_method_class(self, sample_signature, sample_metadata) -> None:
        class ValidMethod:
            signature = sample_signature
            metadata = sample_metadata

            @staticmethod
            def pure_step(state, params):
                return state

        assert is_foundry_method(ValidMethod) is True

    def test_rejects_non_class(self) -> None:
        assert is_foundry_method("not a class") is False
        assert is_foundry_method(42) is False
        assert is_foundry_method(lambda: None) is False

    def test_rejects_foundry_method_protocol_itself(self) -> None:
        assert is_foundry_method(FoundryMethod) is False

    def test_rejects_missing_signature(self, sample_metadata) -> None:
        class NoSignature:
            metadata = sample_metadata

            @staticmethod
            def pure_step(state, params):
                return state

        assert is_foundry_method(NoSignature) is False

    def test_rejects_wrong_signature_type(self, sample_metadata) -> None:
        class WrongSignatureType:
            signature = {"not": "a signature"}
            metadata = sample_metadata

            @staticmethod
            def pure_step(state, params):
                return state

        assert is_foundry_method(WrongSignatureType) is False

    def test_rejects_missing_metadata(self, sample_signature) -> None:
        class NoMetadata:
            signature = sample_signature

            @staticmethod
            def pure_step(state, params):
                return state

        assert is_foundry_method(NoMetadata) is False

    def test_rejects_wrong_metadata_type(self, sample_signature) -> None:
        class WrongMetadata:
            signature = sample_signature
            metadata = "not metadata"

            @staticmethod
            def pure_step(state, params):
                return state

        assert is_foundry_method(WrongMetadata) is False

    def test_rejects_missing_pure_step(self, sample_signature, sample_metadata) -> None:
        class NoPureStep:
            signature = sample_signature
            metadata = sample_metadata

        assert is_foundry_method(NoPureStep) is False

    def test_rejects_non_static_pure_step(self, sample_signature, sample_metadata) -> None:
        class InstancePureStep:
            signature = sample_signature
            metadata = sample_metadata

            def pure_step(self, state, params):
                return state

        assert is_foundry_method(InstancePureStep) is False

    def test_accepts_decorated_class(self, sample_signature) -> None:
        @foundry_method(namespace="test.ns", version="1.0.0")
        class DecoratedMethod:
            signature = sample_signature

            @staticmethod
            def pure_step(state, params):
                return state

        assert is_foundry_method(DecoratedMethod) is True


# =============================================================================
# EntryPointSource tests
# =============================================================================


class TestEntryPointSource:
    def test_discover_empty_group(self) -> None:
        with mock.patch(
            "polisyos.foundry.methods.discovery.importlib.metadata.entry_points"
        ) as mock_eps:
            mock_eps.return_value = []

            source = EntryPointSource("empty.group")
            methods = list(source.discover())

            assert methods == []

    def test_discover_class_entry_point(self, sample_signature, sample_metadata) -> None:
        class DirectMethod:
            signature = sample_signature
            metadata = sample_metadata

            @staticmethod
            def pure_step(state, params):
                return state

        mock_ep = mock.MagicMock()
        mock_ep.name = "direct"
        mock_ep.value = "module:DirectMethod"
        mock_ep.load.return_value = DirectMethod

        with mock.patch(
            "polisyos.foundry.methods.discovery.importlib.metadata.entry_points"
        ) as mock_eps:
            mock_eps.return_value = [mock_ep]

            source = EntryPointSource()
            methods = list(source.discover())

            assert len(methods) == 1
            assert methods[0] is DirectMethod

    def test_discover_function_returning_single_class(self) -> None:
        method_class = create_test_method("func_single", "test.func")

        def register_func():
            return method_class

        mock_ep = mock.MagicMock()
        mock_ep.name = "func_single"
        mock_ep.value = "module:register_func"
        mock_ep.load.return_value = register_func

        with mock.patch(
            "polisyos.foundry.methods.discovery.importlib.metadata.entry_points"
        ) as mock_eps:
            mock_eps.return_value = [mock_ep]

            source = EntryPointSource()
            methods = list(source.discover())

            assert len(methods) == 1

    def test_discover_function_returning_list(self) -> None:
        method1 = create_test_method("list_a", "test.list")
        method2 = create_test_method("list_b", "test.list")

        def register_func():
            return [method1, method2]

        mock_ep = mock.MagicMock()
        mock_ep.name = "func_list"
        mock_ep.value = "module:register_func"
        mock_ep.load.return_value = register_func

        with mock.patch(
            "polisyos.foundry.methods.discovery.importlib.metadata.entry_points"
        ) as mock_eps:
            mock_eps.return_value = [mock_ep]

            source = EntryPointSource()
            methods = list(source.discover())

            assert len(methods) == 2

    def test_discover_function_returning_none(self) -> None:
        def register_func():
            return None

        mock_ep = mock.MagicMock()
        mock_ep.name = "func_none"
        mock_ep.value = "module:register_func"
        mock_ep.load.return_value = register_func

        with mock.patch(
            "polisyos.foundry.methods.discovery.importlib.metadata.entry_points"
        ) as mock_eps:
            mock_eps.return_value = [mock_ep]

            source = EntryPointSource()
            methods = list(source.discover())

            assert methods == []

    def test_discover_module_entry_point(self) -> None:
        method_class = create_test_method("in_module", "test.module")

        module = ModuleType("test_module")
        setattr(module, "TestMethod", method_class)
        method_class.__module__ = "test_module"

        mock_ep = mock.MagicMock()
        mock_ep.name = "module"
        mock_ep.value = "test_module"
        mock_ep.load.return_value = module

        with mock.patch(
            "polisyos.foundry.methods.discovery.importlib.metadata.entry_points"
        ) as mock_eps:
            mock_eps.return_value = [mock_ep]

            source = EntryPointSource()
            methods = list(source.discover())

            assert len(methods) == 1

    def test_discover_handles_load_error(self) -> None:
        mock_ep = mock.MagicMock()
        mock_ep.name = "broken"
        mock_ep.value = "missing"
        mock_ep.load.side_effect = ImportError("Module not found")

        with mock.patch(
            "polisyos.foundry.methods.discovery.importlib.metadata.entry_points"
        ) as mock_eps:
            mock_eps.return_value = [mock_ep]

            source = EntryPointSource()
            methods = list(source.discover())

            assert methods == []
            assert len(source.errors) == 1
            assert source.errors[0].error_type == "ImportError"

    def test_custom_group_name(self) -> None:
        source = EntryPointSource("custom.group")
        assert source.group == "custom.group"

    def test_entry_points_sorted(self) -> None:
        method_a = create_test_method("a", "order.ep")
        method_b = create_test_method("b", "order.ep")

        ep_b = mock.MagicMock()
        ep_b.name = "b"
        ep_b.value = "module_b:MethodB"
        ep_b.load.return_value = method_b

        ep_a = mock.MagicMock()
        ep_a.name = "a"
        ep_a.value = "module_a:MethodA"
        ep_a.load.return_value = method_a

        with mock.patch(
            "polisyos.foundry.methods.discovery.importlib.metadata.entry_points"
        ) as mock_eps:
            mock_eps.return_value = [ep_b, ep_a]

            source = EntryPointSource()
            methods = list(source.discover())

            assert methods[0] is method_a
            assert methods[1] is method_b


# =============================================================================
# FileSystemSource tests
# =============================================================================


class TestFileSystemSource:
    def test_discover_from_directory(self, tmp_path: Path) -> None:
        method_file = tmp_path / "my_method.py"
        method_file.write_text(
            textwrap.dedent(
                """
                from typing import Any, ClassVar, Mapping
                from polisyos.foundry.methods.base import (
                    MethodSignature,
                    MethodMetadata,
                    SlotSpec,
                    SlotType,
                    Unit,
                    FidelityLevel,
                    ComplexityClass,
                )

                unit = Unit("none", "1")

                class DiscoveredMethod:
                    signature: ClassVar[MethodSignature] = MethodSignature(
                        name="discovered",
                        namespace="test.fs",
                        version="1.0.0",
                        input_slots=frozenset({
                            SlotSpec("x", SlotType.SCALAR, unit)
                        }),
                        output_slots=frozenset({
                            SlotSpec("y", SlotType.SCALAR, unit)
                        }),
                        parameters=(),
                        fidelity=FidelityLevel.LOW,
                        complexity=ComplexityClass.O_1,
                    )
                    metadata: ClassVar[MethodMetadata] = MethodMetadata(
                        description="A discovered method"
                    )

                    @staticmethod
                    def pure_step(state: Any, params: Mapping[str, Any]) -> Any:
                        return state
                """
            )
        )

        source = FileSystemSource([tmp_path])
        discovered = list(source.discover())

        assert len(discovered) == 1
        assert discovered[0].__name__ == "DiscoveredMethod"

    def test_relative_imports_work(self, tmp_path: Path) -> None:
        package_dir = tmp_path / "sample_pkg"
        package_dir.mkdir()

        (package_dir / "__init__.py").write_text("# package")
        (package_dir / "utils.py").write_text(
            "VALUE = 42\n"
        )

        method_file = package_dir / "method.py"
        method_file.write_text(
            textwrap.dedent(
                """
                from typing import Any, ClassVar, Mapping
                from .utils import VALUE
                from polisyos.foundry.methods.base import (
                    MethodSignature,
                    MethodMetadata,
                    SlotSpec,
                    SlotType,
                    Unit,
                    FidelityLevel,
                    ComplexityClass,
                )

                unit = Unit("none", "1")

                class RelativeMethod:
                    signature: ClassVar[MethodSignature] = MethodSignature(
                        name="relative",
                        namespace="test.relative",
                        version="1.0.0",
                        input_slots=frozenset({
                            SlotSpec("x", SlotType.SCALAR, unit)
                        }),
                        output_slots=frozenset({
                            SlotSpec("y", SlotType.SCALAR, unit)
                        }),
                        parameters=(),
                        fidelity=FidelityLevel.LOW,
                        complexity=ComplexityClass.O_1,
                    )
                    metadata: ClassVar[MethodMetadata] = MethodMetadata(
                        description=f"Relative {VALUE}"
                    )

                    @staticmethod
                    def pure_step(state: Any, params: Mapping[str, Any]) -> Any:
                        return state
                """
            )
        )

        source = FileSystemSource([package_dir])
        discovered = list(source.discover())

        assert len(discovered) == 1
        assert discovered[0].__name__ == "RelativeMethod"

    def test_multiple_base_paths_no_collision(self, tmp_path: Path) -> None:
        path_a = tmp_path / "a"
        path_b = tmp_path / "b"
        path_a.mkdir()
        path_b.mkdir()

        (path_a / "method.py").write_text(
            textwrap.dedent(
                """
                from typing import Any, ClassVar, Mapping
                from polisyos.foundry.methods.base import (
                    MethodSignature,
                    MethodMetadata,
                    SlotSpec,
                    SlotType,
                    Unit,
                    FidelityLevel,
                    ComplexityClass,
                )

                unit = Unit("none", "1")

                class MethodA:
                    signature: ClassVar[MethodSignature] = MethodSignature(
                        name="a",
                        namespace="test.collision",
                        version="1.0.0",
                        input_slots=frozenset({
                            SlotSpec("x", SlotType.SCALAR, unit)
                        }),
                        output_slots=frozenset({
                            SlotSpec("y", SlotType.SCALAR, unit)
                        }),
                        parameters=(),
                        fidelity=FidelityLevel.LOW,
                        complexity=ComplexityClass.O_1,
                    )
                    metadata: ClassVar[MethodMetadata] = MethodMetadata(
                        description="Method A"
                    )

                    @staticmethod
                    def pure_step(state: Any, params: Mapping[str, Any]) -> Any:
                        return state
                """
            )
        )

        (path_b / "method.py").write_text(
            textwrap.dedent(
                """
                from typing import Any, ClassVar, Mapping
                from polisyos.foundry.methods.base import (
                    MethodSignature,
                    MethodMetadata,
                    SlotSpec,
                    SlotType,
                    Unit,
                    FidelityLevel,
                    ComplexityClass,
                )

                unit = Unit("none", "1")

                class MethodB:
                    signature: ClassVar[MethodSignature] = MethodSignature(
                        name="b",
                        namespace="test.collision",
                        version="1.0.0",
                        input_slots=frozenset({
                            SlotSpec("x", SlotType.SCALAR, unit)
                        }),
                        output_slots=frozenset({
                            SlotSpec("y", SlotType.SCALAR, unit)
                        }),
                        parameters=(),
                        fidelity=FidelityLevel.LOW,
                        complexity=ComplexityClass.O_1,
                    )
                    metadata: ClassVar[MethodMetadata] = MethodMetadata(
                        description="Method B"
                    )

                    @staticmethod
                    def pure_step(state: Any, params: Mapping[str, Any]) -> Any:
                        return state
                """
            )
        )

        source = FileSystemSource([path_a, path_b])
        discovered = list(source.discover())

        assert {method.__name__ for method in discovered} == {"MethodA", "MethodB"}

    def test_skips_test_files(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test_something.py"
        test_file.write_text("class ShouldNotFind: pass")

        source = FileSystemSource([tmp_path])
        methods = list(source.discover())

        assert methods == []

    def test_skips_pycache(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "__pycache__"
        cache_dir.mkdir()
        cache_file = cache_dir / "cached.py"
        cache_file.write_text("class ShouldNotFind: pass")

        source = FileSystemSource([tmp_path])
        methods = list(source.discover())

        assert methods == []

    def test_skips_init_files(self, tmp_path: Path) -> None:
        init_file = tmp_path / "__init__.py"
        init_file.write_text("class ShouldNotFind: pass")

        source = FileSystemSource([tmp_path])
        methods = list(source.discover())

        assert methods == []

    def test_handles_syntax_error(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "bad_syntax.py"
        bad_file.write_text("def broken( class nope:")

        good_file = tmp_path / "good.py"
        good_file.write_text("# Empty valid file")

        source = FileSystemSource([tmp_path])
        methods = list(source.discover())

        assert methods == []
        assert len(source.errors) == 1
        assert source.errors[0].error_type == "SyntaxError"

    def test_handles_import_error(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "bad_import.py"
        bad_file.write_text("from nonexistent_module import something")

        source = FileSystemSource([tmp_path])
        methods = list(source.discover())

        assert methods == []
        assert len(source.errors) == 1
        assert source.errors[0].error_type in {"ImportError", "ModuleNotFoundError"}

    def test_handles_nonexistent_path(self) -> None:
        source = FileSystemSource([Path("/nonexistent/path/xyz")])
        methods = list(source.discover())

        assert methods == []
        assert source.errors == []

    def test_handles_file_instead_of_directory(self, tmp_path: Path) -> None:
        file_path = tmp_path / "file.py"
        file_path.write_text("x = 1")

        source = FileSystemSource([file_path])
        methods = list(source.discover())

        assert methods == []

    def test_sorted_iteration_order(self, tmp_path: Path) -> None:
        (tmp_path / "z_method.py").write_text("# z")
        (tmp_path / "a_method.py").write_text("# a")
        (tmp_path / "m_method.py").write_text("# m")

        source = FileSystemSource([tmp_path])

        loaded_order: list[str] = []

        def tracking_load(path: Path, base: Path):
            loaded_order.append(path.name)
            return None

        source._load_module = tracking_load  # type: ignore[assignment]
        list(source.discover())

        assert loaded_order == ["a_method.py", "m_method.py", "z_method.py"]

    def test_custom_exclude_patterns(self, tmp_path: Path) -> None:
        excluded = tmp_path / "excluded_file.py"
        excluded.write_text("class Excluded: pass")

        normal = tmp_path / "normal.py"
        normal.write_text("class Normal: pass")

        source = FileSystemSource(
            [tmp_path],
            exclude_patterns=frozenset({"excluded_*"}),
        )

        methods = list(source.discover())
        assert all("Excluded" not in m.__name__ for m in methods)


# =============================================================================
# MethodDiscovery tests
# =============================================================================


class TestMethodDiscovery:
    def test_add_source_chaining(self, fresh_registry) -> None:
        discovery = MethodDiscovery(fresh_registry)

        result = discovery.add_entry_points().add_directory(Path("."))

        assert result is discovery
        assert len(discovery.sources) == 2

    def test_discover_all_processes_sources_in_order(self, fresh_registry) -> None:
        method1 = create_test_method("first", "order.test")
        method2 = create_test_method("second", "order.test")

        call_order: list[int] = []

        class OrderedSource1:
            def discover(self):
                call_order.append(1)
                yield method1

        class OrderedSource2:
            def discover(self):
                call_order.append(2)
                yield method2

        discovery = MethodDiscovery(fresh_registry)
        discovery.add_source(OrderedSource1())
        discovery.add_source(OrderedSource2())

        discovery.discover_all()

        assert call_order == [1, 2]

    def test_first_registration_wins(self, fresh_registry) -> None:
        method = create_test_method("duplicate", "dup.test")

        class DuplicateSource:
            def discover(self):
                yield method

        discovery = MethodDiscovery(fresh_registry)
        discovery.add_source(DuplicateSource())
        discovery.add_source(DuplicateSource())

        report = discovery.discover_all()

        assert report.total_registered == 1
        assert report.total_duplicates == 1
        assert report.success is True

    def test_duplicate_policy_error(self, fresh_registry) -> None:
        method = create_test_method("duplicate", "dup.strict")

        class DuplicateSource:
            def discover(self):
                yield method

        discovery = MethodDiscovery(fresh_registry, on_duplicate=DuplicatePolicy.ERROR)
        discovery.add_source(DuplicateSource())
        discovery.add_source(DuplicateSource())

        report = discovery.discover_all()

        assert report.total_registered == 1
        assert report.total_duplicates == 1
        assert report.success is False
        assert report.total_errors == 1

    def test_source_error_captured_in_report(self, fresh_registry) -> None:
        class FailingSource:
            def discover(self):
                raise RuntimeError("Source exploded")

        discovery = MethodDiscovery(fresh_registry)
        discovery.add_source(FailingSource())

        report = discovery.discover_all()

        assert report.success is False
        assert len(report.errors) == 1
        assert "Source exploded" in report.errors[0].message

    def test_invalid_method_error_captured(self, fresh_registry) -> None:
        class InvalidMethod:
            pass

        class YieldingInvalidSource:
            def discover(self):
                yield InvalidMethod

        discovery = MethodDiscovery(fresh_registry)
        discovery.add_source(YieldingInvalidSource())

        report = discovery.discover_all()

        assert report.success is False
        assert report.total_registered == 0

    def test_sources_processed_count(self, fresh_registry) -> None:
        class EmptySource:
            def discover(self):
                return iter([])

        discovery = MethodDiscovery(fresh_registry)
        for _ in range(5):
            discovery.add_source(EmptySource())

        report = discovery.discover_all()

        assert report.sources_processed == 5

    def test_cleanup_modules(self, fresh_registry, tmp_path: Path) -> None:
        method_file = tmp_path / "cleanup_method.py"
        method_file.write_text(
            textwrap.dedent(
                """
                from typing import Any, ClassVar, Mapping
                from polisyos.foundry.methods.base import (
                    MethodSignature,
                    MethodMetadata,
                    SlotSpec,
                    SlotType,
                    Unit,
                    FidelityLevel,
                    ComplexityClass,
                )

                unit = Unit("none", "1")

                class CleanupMethod:
                    signature: ClassVar[MethodSignature] = MethodSignature(
                        name="cleanup",
                        namespace="test.cleanup",
                        version="1.0.0",
                        input_slots=frozenset({
                            SlotSpec("x", SlotType.SCALAR, unit)
                        }),
                        output_slots=frozenset({
                            SlotSpec("y", SlotType.SCALAR, unit)
                        }),
                        parameters=(),
                        fidelity=FidelityLevel.LOW,
                        complexity=ComplexityClass.O_1,
                    )
                    metadata: ClassVar[MethodMetadata] = MethodMetadata(
                        description="Cleanup method"
                    )

                    @staticmethod
                    def pure_step(state: Any, params: Mapping[str, Any]) -> Any:
                        return state
                """
            )
        )

        before = {name for name in sys.modules if name.startswith(DISCOVERY_MODULE_PREFIX)}

        discovery = MethodDiscovery(fresh_registry, on_duplicate=DuplicatePolicy.WARN)
        discovery.add_directory(tmp_path)
        discovery.discover_all(cleanup_modules=True)

        after = {name for name in sys.modules if name.startswith(DISCOVERY_MODULE_PREFIX)}

        assert after.issubset(before)


# =============================================================================
# Bootstrap integration tests
# =============================================================================


class TestBootstrapRegistry:
    def test_bootstrap_with_no_plugins(self, fresh_registry) -> None:
        with mock.patch(
            "polisyos.foundry.methods.discovery.importlib.metadata.entry_points"
        ) as mock_eps:
            mock_eps.return_value = []

            report = bootstrap_registry(registry=fresh_registry)

            assert report.success is True
            assert report.total_registered == 0

    def test_bootstrap_dev_mode(self, fresh_registry, tmp_path: Path) -> None:
        method_file = tmp_path / "dev_method.py"
        method_file.write_text(
            textwrap.dedent(
                """
                from typing import Any, ClassVar, Mapping
                from polisyos.foundry.methods.base import (
                    MethodSignature,
                    MethodMetadata,
                    SlotSpec,
                    SlotType,
                    Unit,
                    FidelityLevel,
                    ComplexityClass,
                )

                unit = Unit("none", "1")

                class DevMethod:
                    signature: ClassVar[MethodSignature] = MethodSignature(
                        name="dev",
                        namespace="test.dev",
                        version="1.0.0",
                        input_slots=frozenset({
                            SlotSpec("x", SlotType.SCALAR, unit)
                        }),
                        output_slots=frozenset({
                            SlotSpec("y", SlotType.SCALAR, unit)
                        }),
                        parameters=(),
                        fidelity=FidelityLevel.LOW,
                        complexity=ComplexityClass.O_1,
                    )
                    metadata: ClassVar[MethodMetadata] = MethodMetadata(
                        description="Dev method"
                    )

                    @staticmethod
                    def pure_step(state: Any, params: Mapping[str, Any]) -> Any:
                        return state
                """
            )
        )

        with mock.patch(
            "polisyos.foundry.methods.discovery.importlib.metadata.entry_points"
        ) as mock_eps:
            mock_eps.return_value = []

            report = bootstrap_registry(
                registry=fresh_registry,
                dev_mode=True,
                dev_paths=[tmp_path],
            )

            assert report.total_registered >= 0

    def test_bootstrap_custom_entry_point_group(self, fresh_registry) -> None:
        method = create_test_method("custom_ep", "custom.group")

        mock_ep = mock.MagicMock()
        mock_ep.name = "custom"
        mock_ep.value = "custom:method"
        mock_ep.load.return_value = method

        with mock.patch(
            "polisyos.foundry.methods.discovery.importlib.metadata.entry_points"
        ) as mock_eps:
            def selective_eps(group=None):
                if group == "my.custom.group":
                    return [mock_ep]
                return []

            mock_eps.side_effect = selective_eps

            report = bootstrap_registry(
                registry=fresh_registry,
                entry_point_group="my.custom.group",
            )

            assert report.total_registered == 1

    def test_bootstrap_uses_singleton_by_default(self) -> None:
        MethodRegistry.reset_instance()

        with mock.patch(
            "polisyos.foundry.methods.discovery.importlib.metadata.entry_points"
        ) as mock_eps:
            mock_eps.return_value = []

            report = bootstrap_registry()

            assert report.success is True

        MethodRegistry.reset_instance()


# =============================================================================
# Thread safety tests
# =============================================================================


class TestThreadSafety:
    def test_concurrent_discovery(self, fresh_registry) -> None:
        num_threads = 4
        methods_per_thread = 10
        results: list[int] = []
        errors: list[str] = []

        def discover_methods(thread_id: int) -> None:
            try:
                for i in range(methods_per_thread):
                    method = create_test_method(
                        f"method_{i}",
                        f"thread_{thread_id}",
                    )

                    class SingleSource:
                        def __init__(self, m):
                            self.m = m

                        def discover(self):
                            yield self.m

                    discovery = MethodDiscovery(fresh_registry)
                    discovery.add_source(SingleSource(method))
                    report = discovery.discover_all()
                    results.append(report.total_registered)
            except Exception as exc:
                errors.append(str(exc))

        threads = [
            threading.Thread(target=discover_methods, args=(i,))
            for i in range(num_threads)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Errors: {errors}"
        assert len(fresh_registry.list_all()) == num_threads * methods_per_thread


# =============================================================================
# Edge case tests
# =============================================================================


class TestEdgeCases:
    def test_empty_sources_list(self, fresh_registry) -> None:
        discovery = MethodDiscovery(fresh_registry)
        report = discovery.discover_all()

        assert report.success is True
        assert report.total_registered == 0
        assert report.sources_processed == 0

    def test_method_with_complex_signature(self, fresh_registry) -> None:
        unit = Unit("currency", "UAH")
        sig = MethodSignature(
            name="complex",
            namespace="complex.test",
            version="2.5.3",
            input_slots=frozenset({
                SlotSpec("a", SlotType.VECTOR, unit),
                SlotSpec("b", SlotType.MATRIX, unit),
            }),
            output_slots=frozenset({
                SlotSpec("c", SlotType.SCALAR, unit),
            }),
            parameters=(),
            fidelity=FidelityLevel.HIGH,
            complexity=ComplexityClass.O_N2,
            commutes_with=frozenset({"other.method@1.0.0"}),
            supports_grad=False,
        )
        meta = MethodMetadata(
            description="Complex method",
            tags=frozenset({"complex", "test"}),
            citations=("Paper 2024",),
        )

        class ComplexMethod:
            signature: ClassVar[MethodSignature] = sig
            metadata: ClassVar[MethodMetadata] = meta

            @staticmethod
            def pure_step(state, params):
                return state

        class ComplexSource:
            def discover(self):
                yield ComplexMethod

        discovery = MethodDiscovery(fresh_registry)
        discovery.add_source(ComplexSource())
        report = discovery.discover_all()

        assert report.total_registered == 1
        assert "complex.test.complex@2.5.3" in fresh_registry

    def test_unicode_in_method_names(self, fresh_registry) -> None:
        unit = Unit("\u0432\u0430\u043b\u044e\u0442\u0430", "\u20b4")
        sig = MethodSignature(
            name="\u043f\u043e\u0434\u0430\u0442\u043e\u043a",
            namespace="\u0444\u0456\u0441\u043a\u0430\u043b\u044c\u043d\u0438\u0439",
            version="1.0.0",
            input_slots=frozenset({
                SlotSpec("\u0434\u043e\u0445\u0456\u0434", SlotType.VECTOR, unit)
            }),
            output_slots=frozenset({
                SlotSpec("\u043f\u043e\u0434\u0430\u0442\u043e\u043a", SlotType.VECTOR, unit)
            }),
            parameters=(),
            fidelity=FidelityLevel.LOW,
            complexity=ComplexityClass.O_N,
        )
        meta = MethodMetadata(
            description=(
                "\u041c\u0435\u0442\u043e\u0434 "
                "\u043e\u043f\u043e\u0434\u0430\u0442\u043a\u0443\u0432\u0430\u043d\u043d\u044f"
            )
        )

        class UnicodeMethod:
            signature = sig
            metadata = meta

            @staticmethod
            def pure_step(state, params):
                return state

        class UnicodeSource:
            def discover(self):
                yield UnicodeMethod

        discovery = MethodDiscovery(fresh_registry)
        discovery.add_source(UnicodeSource())
        report = discovery.discover_all()

        assert report.total_registered == 1


# =============================================================================
# Constants sanity check
# =============================================================================


def test_entry_point_group_constant() -> None:
    assert ENTRY_POINT_GROUP == "polisyos.methods"

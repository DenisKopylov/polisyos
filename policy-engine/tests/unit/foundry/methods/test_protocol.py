"""
Tests for FoundryMethod protocol compliance and @foundry_method decorator.
"""

from __future__ import annotations

import builtins
import math
import os
import subprocess
import sys
import types
from typing import NamedTuple

import jax.numpy as jnp
import pytest

import polisyos.foundry as foundry_facade
from polisyos.foundry.methods import (
    ComplexityClass,
    FidelityLevel,
    LawViolationError,
    MethodDefinitionError,
    MethodMetadata,
    MethodSignature,
    ParameterSpec,
    SlotSpec,
    SlotType,
    check_protocol_compliance,
    foundry_method,
)
from polisyos.foundry.methods.backends import protocol as backend_protocol
from polisyos.foundry.methods.types.units import Units


class JaxState(NamedTuple):
    x: jnp.ndarray


class StrictState(NamedTuple):
    x: jnp.ndarray


class TestEmbeddingBackends:
    def test_root_facade_exports_canonical_embedding_symbols(self) -> None:
        assert foundry_facade.EmbedderProtocol is backend_protocol.EmbedderProtocol
        assert foundry_facade.TFIDFEmbedder is backend_protocol.TFIDFEmbedder
        assert (
            foundry_facade.SentenceTransformerEmbedder
            is backend_protocol.SentenceTransformerEmbedder
        )

    def test_root_facade_keeps_embedding_owner_and_optional_dependency_lazy(self) -> None:
        script = """
import sys

import polisyos.foundry as foundry

assert "polisyos.foundry.methods.backends.protocol" not in sys.modules
assert "sentence_transformers" not in sys.modules
assert foundry.TFIDFEmbedder.__module__ == "polisyos.foundry.methods.backends.protocol"
assert "polisyos.foundry.methods.backends.protocol" in sys.modules
assert "sentence_transformers" not in sys.modules
"""
        env = os.environ.copy()
        completed = subprocess.run(
            [sys.executable, "-c", script],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )

        assert completed.returncode == 0, completed.stderr

    def test_tfidf_owner_produces_normalized_vectors(self) -> None:
        assert hasattr(backend_protocol, "TFIDFEmbedder")

        embedder = backend_protocol.TFIDFEmbedder(max_features=64)
        embedder.fit(
            [
                "fiscal policy tax reform",
                "monetary policy interest rates",
                "public health spending budget",
            ]
        )

        vectors = embedder.embed(["tax reform policy"])
        assert len(vectors) == 1
        assert len(vectors[0]) == embedder.dim
        assert math.sqrt(sum(value * value for value in vectors[0])) == pytest.approx(1.0)

    def test_tfidf_requires_fit(self) -> None:
        embedder = backend_protocol.TFIDFEmbedder()

        with pytest.raises(RuntimeError, match="fit.*must be called"):
            embedder.embed(["some text"])

    def test_tfidf_empty_corpus_preserves_zero_vector_output(self) -> None:
        embedder = backend_protocol.TFIDFEmbedder()
        embedder.fit([])

        assert embedder.embed(["some text"]) == [[0.0]]

    def test_tfidf_satisfies_runtime_protocol(self) -> None:
        embedder = backend_protocol.TFIDFEmbedder()

        assert isinstance(embedder, backend_protocol.EmbedderProtocol)

    def test_sentence_transformer_dependency_remains_optional(self, monkeypatch) -> None:
        original_import = builtins.__import__

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "sentence_transformers":
                raise ImportError
            return original_import(name, globals, locals, fromlist, level)

        monkeypatch.setattr(builtins, "__import__", guarded_import)

        with pytest.raises(ImportError) as exc_info:
            backend_protocol.SentenceTransformerEmbedder()

        assert str(exc_info.value) == (
            "sentence-transformers is required for SentenceTransformerEmbedder.  "
            "Install it with: pip install sentence-transformers"
        )

    def test_sentence_transformer_preserves_model_outputs(self, monkeypatch) -> None:
        class FakeSentenceTransformer:
            def __init__(self, model_name: str) -> None:
                assert model_name == "fixture-model"

            def get_sentence_embedding_dimension(self) -> int:
                return 2

            def encode(self, texts: list[str], *, convert_to_numpy: bool):
                assert texts == ["first", "second"]
                assert convert_to_numpy is True
                return jnp.asarray([[1.0, 2.0], [3.0, 4.0]])

        fake_module = types.ModuleType("sentence_transformers")
        fake_module.SentenceTransformer = FakeSentenceTransformer
        monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)

        embedder = backend_protocol.SentenceTransformerEmbedder("fixture-model")

        assert embedder.dim == 2
        assert embedder.embed(["first", "second"]) == [[1.0, 2.0], [3.0, 4.0]]


@pytest.fixture
def base_signature() -> MethodSignature:
    return MethodSignature(
        name="test_method",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(),
        output_slots=frozenset(),
        parameters=(),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_1,
    )


class TestProtocolCompliance:
    def test_valid_class_has_required_attributes(self, valid_method_class):
        assert hasattr(valid_method_class, "signature")
        assert hasattr(valid_method_class, "metadata")
        assert hasattr(valid_method_class, "pure_step")

    def test_check_protocol_compliance_valid(self, valid_method_class):
        errors = check_protocol_compliance(valid_method_class)
        assert errors == []

    def test_check_protocol_compliance_missing_signature(self):
        class NoSignature:
            @staticmethod
            def pure_step(state, params):
                return state

        errors = check_protocol_compliance(NoSignature)
        assert any("signature" in e for e in errors)

    def test_check_protocol_compliance_missing_pure_step(self, base_signature: MethodSignature):
        class NoPureStep:
            signature = base_signature

        errors = check_protocol_compliance(NoPureStep)
        assert any("pure_step" in e for e in errors)

    def test_check_protocol_compliance_non_static_pure_step(self, base_signature: MethodSignature):
        class InstanceMethod:
            signature = base_signature

            def pure_step(self, state, params):
                return state

        errors = check_protocol_compliance(InstanceMethod)
        assert any("staticmethod" in e for e in errors)

    def test_check_protocol_compliance_wrong_signature_type(self):
        class WrongSignatureType:
            signature = "not a MethodSignature"

            @staticmethod
            def pure_step(state, params):
                return state

        errors = check_protocol_compliance(WrongSignatureType)
        assert any("MethodSignature" in e for e in errors)


class TestFoundryMethodDecorator:
    def test_decorator_populates_namespace(self, base_signature: MethodSignature):
        @foundry_method(namespace="fiscal.taxation", version="1.0.0")
        class TestMethod:
            signature = base_signature

            @staticmethod
            def pure_step(state, params):
                return state

        assert TestMethod.signature.namespace == "fiscal.taxation"

    def test_decorator_populates_version(self, base_signature: MethodSignature):
        @foundry_method(namespace="test", version="2.5.0")
        class TestMethod:
            signature = base_signature

            @staticmethod
            def pure_step(state, params):
                return state

        assert TestMethod.signature.version == "2.5.0"

    def test_decorator_default_version(self, base_signature: MethodSignature):
        @foundry_method(namespace="test")
        class TestMethod:
            signature = base_signature

            @staticmethod
            def pure_step(state, params):
                return state

        assert TestMethod.signature.version == "1.0.0"

    def test_decorator_builds_correct_fqn(self, base_signature: MethodSignature):
        @foundry_method(namespace="fiscal.taxation", version="1.2.0")
        class TestMethod:
            signature = base_signature

            @staticmethod
            def pure_step(state, params):
                return state

        assert TestMethod.signature.fqn == "fiscal.taxation.test_method@1.2.0"

    def test_decorator_creates_default_metadata(self, base_signature: MethodSignature):
        @foundry_method(namespace="test", tags={"experimental"})
        class NoMetadata:
            signature = base_signature

            @staticmethod
            def pure_step(state, params):
                return state

        assert hasattr(NoMetadata, "metadata")
        assert isinstance(NoMetadata.metadata, MethodMetadata)
        assert "experimental" in NoMetadata.metadata.tags

    def test_decorator_preserves_existing_metadata(self, base_signature: MethodSignature):
        @foundry_method(namespace="test")
        class WithMetadata:
            signature = base_signature
            metadata = MethodMetadata(
                description="Custom description",
                tags=frozenset({"custom"}),
            )

            @staticmethod
            def pure_step(state, params):
                return state

        assert WithMetadata.metadata.description == "Custom description"
        assert "custom" in WithMetadata.metadata.tags

    def test_decorator_merges_tags(self, base_signature: MethodSignature):
        @foundry_method(namespace="test", tags={"decorator_tag"})
        class WithTags:
            signature = base_signature
            metadata = MethodMetadata(
                description="Test",
                tags=frozenset({"existing_tag"}),
            )

            @staticmethod
            def pure_step(state, params):
                return state

        assert "existing_tag" in WithTags.metadata.tags
        assert "decorator_tag" in WithTags.metadata.tags

    def test_decorator_preserves_original_signature_fields(self):
        income_slot = SlotSpec(
            name="income",
            slot_type=SlotType.VECTOR,
            unit=Units.UAH,
        )
        param = ParameterSpec(name="rate", default=0.2)

        original_sig = MethodSignature(
            name="test",
            namespace="placeholder",
            version="0.0.0",
            input_slots=frozenset({income_slot}),
            output_slots=frozenset(),
            parameters=(param,),
            fidelity=FidelityLevel.MEDIUM,
            complexity=ComplexityClass.O_N,
            commutes_with=frozenset({"test.other@1.0.0"}),
            supports_grad=False,
        )

        @foundry_method(namespace="new.ns", version="3.0.0")
        class TestMethod:
            signature = original_sig

            @staticmethod
            def pure_step(state, params):
                return state

        assert TestMethod.signature.namespace == "new.ns"
        assert TestMethod.signature.version == "3.0.0"
        assert TestMethod.signature.fidelity == FidelityLevel.MEDIUM
        assert TestMethod.signature.complexity == ComplexityClass.O_N
        assert "test.other@1.0.0" in TestMethod.signature.commutes_with
        assert TestMethod.signature.supports_grad is False
        assert len(TestMethod.signature.input_slots) == 1


class TestDecoratorErrors:
    def test_rejects_missing_signature(self):
        with pytest.raises(MethodDefinitionError, match="missing 'signature'"):

            @foundry_method(namespace="test")
            class NoSignature:
                @staticmethod
                def pure_step(state, params):
                    return state

    def test_rejects_missing_pure_step(self, base_signature: MethodSignature):
        with pytest.raises(MethodDefinitionError, match="missing 'pure_step'"):

            @foundry_method(namespace="test")
            class NoPureStep:
                signature = base_signature

    def test_rejects_non_static_pure_step(self, base_signature: MethodSignature):
        with pytest.raises(MethodDefinitionError, match="@staticmethod"):

            @foundry_method(namespace="test")
            class InstanceMethod:
                signature = base_signature

                def pure_step(self, state, params):
                    return state

    def test_rejects_wrong_signature_type(self):
        with pytest.raises(MethodDefinitionError, match="MethodSignature"):

            @foundry_method(namespace="test")
            class WrongType:
                signature = {"not": "a signature"}

                @staticmethod
                def pure_step(state, params):
                    return state

    def test_error_message_includes_class_name(self, base_signature: MethodSignature):
        with pytest.raises(MethodDefinitionError, match="MyBrokenMethod"):

            @foundry_method(namespace="test")
            class MyBrokenMethod:
                signature = base_signature

                def pure_step(self, state, params):
                    return state


class TestStrictMode:
    def test_strict_mode_rejects_top_level_foundry_types(self, monkeypatch):
        monkeypatch.setenv("POLISYOS_STRICT", "1")

        @foundry_method(namespace="test")
        class StrictMethod:
            signature = MethodSignature(
                name="strict",
                namespace="",
                version="",
                input_slots=frozenset(),
                output_slots=frozenset(),
                parameters=(),
                fidelity=FidelityLevel.LOW,
                complexity=ComplexityClass.O_N,
            )

            @staticmethod
            def pure_step(state: StrictState, params: object) -> StrictState:
                return StrictState(x=state.x)

        state = StrictState(x=jnp.array([1.0]))
        params = Units.USD

        with pytest.raises(LawViolationError):
            StrictMethod.pure_step(state, params)


class TestJaxCompatibility:
    def test_pure_step_jit_compilable(self):
        import jax

        @foundry_method(namespace="test")
        class JitMethod:
            signature = MethodSignature(
                name="jit_test",
                namespace="",
                version="",
                input_slots=frozenset(),
                output_slots=frozenset(),
                parameters=(),
                fidelity=FidelityLevel.LOW,
                complexity=ComplexityClass.O_N,
            )

            @staticmethod
            def pure_step(state: JaxState, params: dict) -> JaxState:
                return JaxState(x=state.x * params["scale"])

        jit_step = jax.jit(JitMethod.pure_step)

        state = JaxState(x=jnp.array([1.0, 2.0, 3.0]))
        params = {"scale": 2.0}

        result = jit_step(state, params)
        expected = jnp.array([2.0, 4.0, 6.0])
        assert jnp.allclose(result.x, expected)

    def test_pure_step_vmap_able(self):
        import jax

        @foundry_method(namespace="test")
        class VmapMethod:
            signature = MethodSignature(
                name="vmap_test",
                namespace="",
                version="",
                input_slots=frozenset(),
                output_slots=frozenset(),
                parameters=(),
                fidelity=FidelityLevel.LOW,
                complexity=ComplexityClass.O_N,
            )

            @staticmethod
            def pure_step(state: JaxState, params: dict) -> JaxState:
                return JaxState(x=state.x + params["offset"])

        batched_step = jax.vmap(VmapMethod.pure_step, in_axes=(0, None))

        batched_state = JaxState(x=jnp.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]]))
        params = {"offset": 10.0}

        result = batched_step(batched_state, params)
        expected = jnp.array([[11.0, 12.0], [13.0, 14.0], [15.0, 16.0]])
        assert jnp.allclose(result.x, expected)

    def test_pure_step_grad_compatible(self):
        import jax

        @foundry_method(namespace="test")
        class GradMethod:
            signature = MethodSignature(
                name="grad_test",
                namespace="",
                version="",
                input_slots=frozenset(),
                output_slots=frozenset(),
                parameters=(),
                fidelity=FidelityLevel.LOW,
                complexity=ComplexityClass.O_N,
                supports_grad=True,
            )

            @staticmethod
            def pure_step(state: JaxState, params: dict) -> JaxState:
                return JaxState(x=state.x**2 * params["scale"])

        def loss_fn(x, params):
            state = JaxState(x=x)
            result = GradMethod.pure_step(state, params)
            return jnp.sum(result.x)

        x = jnp.array([2.0, 3.0])
        params = {"scale": 1.0}

        grad = jax.grad(loss_fn)(x, params)
        expected = jnp.array([4.0, 6.0])
        assert jnp.allclose(grad, expected)

#!/usr/bin/env python3
"""Re-run the C-W04 installed-wheel publication and selector-removal checks.

Build/install the wheel into an isolated target first; commands are recorded in
``dfi-emb-adjacent.txt``. This script verifies imports come from that target.
"""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import sys
import tempfile
import types
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Protocol

if TYPE_CHECKING:
    from collections.abc import Generator

import numpy as np


class _FakeSentenceTransformer:
    instances: ClassVar[list[_FakeSentenceTransformer]] = []

    def __init__(self, model_name: str, device: str | None = None) -> None:
        self.model_name = model_name
        self.device = device
        type(self).instances.append(self)

    def encode(
        self,
        texts: list[str],
        batch_size: int = 32,
        show_progress_bar: bool = False,
        normalize_embeddings: bool = True,
    ) -> np.ndarray:
        del batch_size, show_progress_bar
        offset = 1.0 if self.model_name.endswith("@v1") else 2.0
        vectors: list[np.ndarray] = []
        for text in texts:
            base = float((len(text) % 7) + offset)
            vector = np.array([base, base + 1, base + 2, base + 3], dtype=np.float64)
            if normalize_embeddings:
                vector /= np.linalg.norm(vector)
            vectors.append(vector)
        return np.vstack(vectors)


class _PytestItem(Protocol):
    name: str


class _PytestReport(Protocol):
    when: str
    failed: bool
    longrepr: object


class _PytestOutcome(Protocol):
    def get_result(self) -> _PytestReport: ...


def _emit(message: str) -> None:
    sys.stdout.write(message + "\n")


def _install_fake_encoder() -> None:
    _FakeSentenceTransformer.instances.clear()
    sys.modules["sentence_transformers"] = types.SimpleNamespace(
        SentenceTransformer=_FakeSentenceTransformer
    )


def _dataset_record(dataset_id: str, title: str, description: str) -> object:
    from polisyos.data_forge.domains.catalog.knowledge.types import (
        DatasetRecord,
        DistributionRecord,
    )

    return DatasetRecord(
        id=dataset_id,
        title=title,
        description=description,
        source="worldbank",
        dataset_id=dataset_id,
        source_dataset_id=dataset_id,
        execution_tier="transport_ready",
        distributions=[
            DistributionRecord(
                id=f"dist-{dataset_id}",
                connector_type="worldbank.wdi",
                source_locator=dataset_id,
                parser_supported=True,
                machine_readable=True,
            )
        ],
    )


def _build_graph(db_path: Path, dataset_id: str, title: str, description: str) -> None:
    from polisyos.data_forge.domains.catalog.batch.graph_builder import build_graph

    build_graph(
        records=iter([_dataset_record(dataset_id, title, description)]),
        db_path=db_path,
    )


def _assert_installed_imports(site: Path, modules: list[types.ModuleType]) -> None:
    for module in modules:
        origin = Path(inspect.getfile(module)).resolve()
        if not origin.is_relative_to(site):
            raise AssertionError(f"{module.__name__} imported outside installed target: {origin}")
        _emit(f"installed import: {module.__name__} -> {origin}")


def _read_vectors(path: Path) -> tuple[list[str], np.ndarray]:
    with np.load(path, allow_pickle=True) as payload:
        return (
            [str(value) for value in payload["ids"].tolist()],
            np.asarray(payload["vectors"], dtype=np.float32),
        )


def _search(db_path: Path, index_dir: Path, vector: np.ndarray, expected: str) -> None:
    from polisyos.data_forge.domains.catalog.knowledge.store import DatasetCatalogStore

    store = DatasetCatalogStore(db_path, index_dir)
    try:
        results = store.search_by_vector(vector, top_k=1, min_similarity=0.99)
        actual = [result.id for result in results]
        if actual != [expected] or results[0].similarity < 0.99:
            raise AssertionError(
                f"selected-generation search returned {actual}, expected [{expected}]"
            )
        _emit(f"CatalogStore.search_by_vector selected {actual[0]} at {results[0].similarity:.6f}")
    finally:
        store.close()


def _installed_publication_check(site: Path) -> None:
    site = site.resolve()
    sys.path.insert(0, str(site))

    from polisyos.data_forge.domains.catalog.batch import embedder as catalog_embedder
    from polisyos.data_forge.domains.catalog.batch import graph_builder
    from polisyos.data_forge.domains.catalog.knowledge import store as catalog_store
    from polisyos.data_forge.kernel import embeddings as kernel_embeddings

    _assert_installed_imports(
        site,
        [catalog_embedder, catalog_store, kernel_embeddings, graph_builder],
    )
    _install_fake_encoder()

    import hnswlib

    real_index_type = hnswlib.Index
    real_atomic_copy_file = kernel_embeddings._atomic_copy_file
    alias_embeddings_name = "ds_dataset_embeddings.npz"
    alias_index_name = "ds_dataset_index.hnsw"

    with tempfile.TemporaryDirectory(prefix="e02-c-w04-installed-") as temporary:
        root = Path(temporary)
        db_path = root / "catalog.duckdb"
        index_dir = root / "catalog-index"
        index_dir.mkdir()
        _build_graph(db_path, "ds-1", "Dataset", "Description")
        catalog_embedder.build_hnsw_index(
            db_path=db_path,
            index_dir=index_dir,
            embedding_model="fake-model@v1",
            embedding_dimension=4,
            embedding_device="cpu",
        )
        previous = kernel_embeddings.resolve_embedding_generation(
            index_dir,
            legacy_embeddings_path=index_dir / alias_embeddings_name,
            legacy_index_path=index_dir / alias_index_name,
        )
        if previous is None or previous.status != "complete":
            raise AssertionError("v1 generation was not selected")
        previous_selector = (
            index_dir / kernel_embeddings.GENERATION_SELECTOR_FILENAME
        ).read_bytes()
        previous_index_bytes = (index_dir / alias_index_name).read_bytes()
        old_ids, old_vectors = _read_vectors(previous.embeddings_path)
        if old_ids != ["ds-1"]:
            raise AssertionError(f"unexpected v1 inventory IDs: {old_ids}")

        class _FailingIndex:
            def __init__(self, *, space: str, dim: int) -> None:
                self._index = real_index_type(space=space, dim=dim)

            def init_index(self, **kwargs: object) -> None:
                self._index.init_index(**kwargs)

            def add_items(self, vectors: np.ndarray, labels: np.ndarray) -> None:
                self._index.add_items(vectors, labels)

            def save_index(self, path: str) -> None:
                if not Path(path).with_name("embeddings.npz").is_file():
                    raise AssertionError("early fault did not occur after NPZ staging")
                raise RuntimeError("synthetic early HNSW fault")

        hnswlib.Index = _FailingIndex
        try:
            try:
                catalog_embedder.build_hnsw_index(
                    db_path=db_path,
                    index_dir=index_dir,
                    embedding_model="fake-model@v2",
                    embedding_dimension=4,
                    embedding_device="cpu",
                )
            except RuntimeError as error:
                if "synthetic early HNSW fault" not in str(error):
                    raise
            else:
                raise AssertionError("early HNSW fault did not fire")
        finally:
            hnswlib.Index = real_index_type

        if (
            index_dir / kernel_embeddings.GENERATION_SELECTOR_FILENAME
        ).read_bytes() != previous_selector:
            raise AssertionError("early HNSW fault changed the old selector")
        still_selected = kernel_embeddings.resolve_embedding_generation(
            index_dir,
            legacy_embeddings_path=index_dir / alias_embeddings_name,
            legacy_index_path=index_dir / alias_index_name,
        )
        if still_selected is None or still_selected.generation_id != previous.generation_id:
            raise AssertionError("early HNSW fault displaced the old generation")
        _search(db_path, index_dir, old_vectors[0], "ds-1")
        _emit("early HNSW fault preserved the old selected/readable ds-1 generation")

        _build_graph(db_path, "ds-2", "New", "XYZ")
        generation_root = index_dir / kernel_embeddings.GENERATION_ROOT_DIRNAME
        prior_generation_ids = {entry.name for entry in generation_root.iterdir() if entry.is_dir()}

        def fail_legacy_index_copy(source: Path, target: Path) -> None:
            if target == index_dir / alias_index_name:
                raise OSError("synthetic late compatibility-index-copy fault")
            real_atomic_copy_file(source, target)

        kernel_embeddings._atomic_copy_file = fail_legacy_index_copy
        try:
            try:
                catalog_embedder.build_hnsw_index(
                    db_path=db_path,
                    index_dir=index_dir,
                    embedding_model="fake-model@v2",
                    embedding_dimension=4,
                    embedding_device="cpu",
                )
            except OSError as error:
                if "synthetic late compatibility-index-copy fault" not in str(error):
                    raise
            else:
                raise AssertionError("late compatibility-copy fault did not fire")
        finally:
            kernel_embeddings._atomic_copy_file = real_atomic_copy_file

        selected = kernel_embeddings.resolve_embedding_generation(
            index_dir,
            legacy_embeddings_path=index_dir / alias_embeddings_name,
            legacy_index_path=index_dir / alias_index_name,
        )
        if selected is None or not selected.selected or selected.status != "complete":
            raise AssertionError("late alias fault left no valid selected generation")
        if selected.generation_id == previous.generation_id:
            raise AssertionError("late alias fault left the prior generation selected")

        new_generation_dirs = [
            entry
            for entry in generation_root.iterdir()
            if entry.is_dir() and entry.name not in prior_generation_ids
        ]
        if len(new_generation_dirs) != 1:
            raise AssertionError(
                f"expected one published candidate directory, got {new_generation_dirs}"
            )
        new_generation_dir = new_generation_dirs[0]
        inventory_bytes = (new_generation_dir / "inventory.json").read_bytes()
        inventory = json.loads(inventory_bytes)
        if (
            inventory.get("generation_id") != new_generation_dir.name
            or inventory.get("status") != "complete"
            or inventory.get("embedding_model") != "fake-model@v2"
            or inventory.get("embedding_device") != "cpu"
            or inventory.get("ids") != ["ds-2"]
        ):
            raise AssertionError(
                f"candidate inventory does not bind the expected v2 source: {inventory}"
            )
        expected_content = "sha256:" + hashlib.sha256(b"New XYZ").hexdigest()
        if inventory.get("basis", {}).get("members") != [
            {"identifier": "ds-2", "content_identity": expected_content}
        ]:
            raise AssertionError("candidate basis does not bind the ds-2 projected source bytes")

        new_ids, new_vectors = _read_vectors(selected.embeddings_path)
        if old_ids != ["ds-1"] or new_ids != ["ds-2"]:
            raise AssertionError(
                f"generation vectors are not content-distinguished: {old_ids} -> {new_ids}"
            )
        if np.array_equal(old_vectors[0], new_vectors[0]):
            raise AssertionError("v1 and v2 vectors were indistinguishable")
        similarity = float(np.dot(old_vectors[0], new_vectors[0]))
        if similarity >= 0.99:
            raise AssertionError(
                f"old query would pass the new-generation discriminator: {similarity}"
            )
        alias_ids, _ = _read_vectors(index_dir / alias_embeddings_name)
        if alias_ids != ["ds-2"]:
            raise AssertionError(f"legacy NPZ alias did not move to ds-2: {alias_ids}")
        if (index_dir / alias_index_name).read_bytes() != previous_index_bytes:
            raise AssertionError("late index-copy fault did not preserve the old HNSW alias")

        _search(db_path, index_dir, new_vectors[0], "ds-2")
        selector_payload = json.loads(
            (index_dir / kernel_embeddings.GENERATION_SELECTOR_FILENAME).read_bytes()
        )
        if selector_payload.get("generation_id") != selected.generation_id:
            raise AssertionError("selector does not point at the consumer-read generation")
        selector_inventory = (index_dir / str(selector_payload["inventory"])).read_bytes()
        if selector_inventory != inventory_bytes or hashlib.sha256(
            selector_inventory
        ).hexdigest() != selector_payload.get("inventory_sha256"):
            raise AssertionError("selector is not byte-bound to the selected v2 inventory")
        _emit(
            "late alias fault selected v2/ds-2 with content-bound inventory; "
            f"legacy alias remains mixed; old/new cosine={similarity:.6f}"
        )

        if (
            catalog_embedder.build_hnsw_index(
                db_path=db_path,
                index_dir=index_dir,
                embedding_model="fake-model@v2",
                embedding_dimension=4,
                embedding_device="cpu",
            )
            != 1
        ):
            raise AssertionError("retry did not rebuild exactly one current dataset")
        recovered = kernel_embeddings.resolve_embedding_generation(
            index_dir,
            legacy_embeddings_path=index_dir / alias_embeddings_name,
            legacy_index_path=index_dir / alias_index_name,
        )
        if recovered is None or not recovered.selected:
            raise AssertionError("retry did not retain an active generation")
        if (
            index_dir / alias_embeddings_name
        ).read_bytes() != recovered.embeddings_path.read_bytes():
            raise AssertionError("NPZ compatibility alias did not recover")
        if (index_dir / alias_index_name).read_bytes() != recovered.index_path.read_bytes():
            raise AssertionError("HNSW compatibility alias did not recover")
        _search(db_path, index_dir, new_vectors[0], "ds-2")
        _emit(f"retry restored byte-identical aliases for generation {recovered.generation_id}")


def _removal_control(site: Path, policy_engine: Path) -> None:
    site = site.resolve()
    sys.path.insert(0, str(site))

    import pytest

    from polisyos.data_forge.kernel import embeddings as kernel_embeddings

    class _SuppressSecondSelectorWrite:
        original_write = None
        selector_writes = 0
        failed_assertion = ""

        def pytest_runtest_setup(self, item: _PytestItem) -> None:
            if item.name != "test_catalog_copy_failure_keeps_one_readable_generation_and_recovers":
                return
            self.original_write = kernel_embeddings.atomic_write_json
            original_write = self.original_write

            def suppress_second_selector(path: Path, payload: object) -> None:
                if Path(path).name == kernel_embeddings.GENERATION_SELECTOR_FILENAME:
                    self.selector_writes += 1
                    if self.selector_writes == 2:
                        return
                original_write(path, payload)

            kernel_embeddings.atomic_write_json = suppress_second_selector

        def pytest_runtest_teardown(self, item: _PytestItem, nextitem: _PytestItem | None) -> None:
            del nextitem
            if (
                item.name == "test_catalog_copy_failure_keeps_one_readable_generation_and_recovers"
                and self.original_write is not None
            ):
                kernel_embeddings.atomic_write_json = self.original_write

        @pytest.hookimpl(hookwrapper=True)
        def pytest_runtest_makereport(
            self, item: _PytestItem, call: object
        ) -> Generator:
            del item, call
            outcome: _PytestOutcome = yield
            report = outcome.get_result()
            if report.when == "call" and report.failed:
                self.failed_assertion = str(report.longrepr)

    plugin = _SuppressSecondSelectorWrite()
    basetemp_root = policy_engine / ".tmp/e02-c-w04"
    basetemp_root.mkdir(parents=True, exist_ok=True)
    basetemp = Path(tempfile.mkdtemp(prefix="receipt-removal-control-", dir=basetemp_root))
    result = pytest.main(
        [
            "-c",
            "pytest.ini",
            "-p",
            "no:cacheprovider",
            "--tb=short",
            "-q",
            "--basetemp",
            str(basetemp),
            "tests/unit/remediation/test_emb_02.py::"
            "test_catalog_copy_failure_keeps_one_readable_generation_and_recovers",
        ],
        plugins=[plugin],
    )
    expected_property_failure = "assert [] == ["
    if (
        result != pytest.ExitCode.TESTS_FAILED
        or plugin.selector_writes != 2
        or expected_property_failure not in plugin.failed_assertion
        or "ds-2" not in plugin.failed_assertion
    ):
        raise AssertionError(
            "selector-removal control did not fail the distinguishing consumer assertion; "
            f"exit={result}, write_count={plugin.selector_writes}, "
            f"failure={plugin.failed_assertion}"
        )
    _emit(
        "REMOVAL CONTROL EXPECTED RED: second selector write suppressed while staged "
        "generation and legacy aliases remain; CatalogStore's ds-2 readback assertion fails."
    )
    _emit(plugin.failed_assertion)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", type=Path, required=True, help="isolated wheel install target")
    parser.add_argument(
        "--removal-control",
        action="store_true",
        help="suppress the second selector publication and require the consumer oracle to fail",
    )
    arguments = parser.parse_args()
    policy_engine = Path(__file__).resolve().parents[5]
    if Path.cwd().resolve() != policy_engine:
        raise SystemExit(f"run from policy-engine root: {policy_engine}")
    if arguments.removal_control:
        _removal_control(arguments.site, policy_engine)
    else:
        _installed_publication_check(arguments.site)


if __name__ == "__main__":
    main()

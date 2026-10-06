from __future__ import annotations

import hashlib
import importlib
import importlib.metadata as metadata
import json
import sys
import tarfile
import types
import zipfile
from pathlib import Path
from typing import Any

import duckdb
import hnswlib
import numpy as np


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


class FixtureTokenizer:
    model_max_length = 128
    padding_side = 'right'
    truncation_side = 'right'
    init_kwargs = {'name_or_path': 'synthetic-fixture-only'}

    def get_vocab(self) -> dict[str, int]:
        return {'<unk>': 0, 'academic': 1, 'catalog': 2, 'fixture': 3}

    @property
    def special_tokens_map(self) -> dict[str, str]:
        return {'unk_token': '<unk>'}

    def get_added_vocab(self) -> dict[str, int]:
        return {}


class FixtureEncoder:
    """Deterministic encoder seam for this no-weights runtime fixture."""

    def __init__(self, model_name: str = 'synthetic-fixture-no-weights', device: str = 'cpu', **_: object) -> None:
        self.model_name = model_name
        self.device = device
        self.config = {'model_name': model_name, 'dimension': 4, 'fixture_only': True}
        self.tokenizer = FixtureTokenizer()
        self.encoded_texts: list[str] = []

    def state_dict(self) -> dict[str, np.ndarray]:
        return {'fixture.parameters': np.asarray([1.0, 2.0, 3.0, 4.0], dtype=np.float32)}

    def modules(self) -> list[FixtureEncoder]:
        return [self]

    def get_sentence_embedding_dimension(self) -> int:
        return 4

    def encode(
        self,
        texts: list[str],
        batch_size: int = 32,
        show_progress_bar: bool = False,
        normalize_embeddings: bool = True,
    ) -> np.ndarray:
        del batch_size, show_progress_bar, normalize_embeddings
        vectors: list[list[float]] = []
        for text in texts:
            value = str(text)
            self.encoded_texts.append(value)
            if 'fixture-academic-alpha' in value:
                vector = [1.0, 0.0, 0.0, 0.0]
            elif 'fixture-academic-beta' in value:
                vector = [0.0, 1.0, 0.0, 0.0]
            elif 'fixture-catalog-gamma' in value:
                vector = [0.0, 0.0, 1.0, 0.0]
            else:
                raise AssertionError(f'unmapped fixture embedding text: {value}')
            vectors.append(vector)
        return np.asarray(vectors, dtype=np.float32)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def artifact_hashes(reference: Any, index_dir: Path) -> dict[str, object]:
    paths = {
        'selector': index_dir / 'embedding_generation.json',
        'inventory': reference.inventory_path,
        'embeddings_npz': reference.embeddings_path,
        'native_hnsw_index': reference.index_path,
        'ids': reference.ids_path,
        'basis': reference.basis_path,
    }
    hashed: dict[str, object] = {}
    for label, path in paths.items():
        require(path is not None and Path(path).is_file(), f'missing selected generation artifact: {label}')
        selected = Path(path)
        hashed[label] = {'path': str(selected), 'bytes': selected.stat().st_size, 'sha256': sha256(selected)}
    return hashed


if len(sys.argv) != 5:
    raise SystemExit('usage: probe.py OUT_DIR WHEEL SOURCE_TAR OLD121_STDOUT')
OUT = Path(sys.argv[1]).resolve()
WHEEL = Path(sys.argv[2]).resolve()
ARCHIVE = Path(sys.argv[3]).resolve()
OLD121 = Path(sys.argv[4]).resolve()
OUT.mkdir(parents=True, exist_ok=False)

# Confirm the current isolated process resolves product code from the exact installed wheel.
root = OUT.parent.parent.parent.parent.resolve()
source_root = ARCHIVE.parent / 'source' / 'policy-engine' / 'src'
distribution = metadata.distribution('policy-engine')
site = Path(distribution.locate_file('')).resolve()
initial_sys_path = list(sys.path)
require(Path.cwd().resolve() == Path('/tmp').resolve(), f'expected /tmp CWD, got {Path.cwd()}')
require(not any(str(source_root) in entry for entry in sys.path), 'candidate source directory is on sys.path')
require(metadata.version('hnswlib') == '0.8.0', 'expected native hnswlib 0.8.0')
try:
    metadata.version('sentence-transformers')
except metadata.PackageNotFoundError:
    sentence_transformers_distribution = None
else:
    sentence_transformers_distribution = 'installed'
require(sentence_transformers_distribution is None, 'unexpected sentence-transformers distribution in profile')

# Academic's public wrapper constructs SentenceTransformer internally. Substitute only that
# external model boundary with the deterministic no-weights fixture; all domain producers,
# selector publication, native HNSW, and readers remain installed production modules.
fixture_module = types.ModuleType('sentence_transformers')
fixture_module.SentenceTransformer = FixtureEncoder
sys.modules['sentence_transformers'] = fixture_module

module_paths = {
    'polisyos.data_forge.domains.academic.batch.embedder': 'polisyos/data_forge/domains/academic/batch/embedder.py',
    'polisyos.data_forge.domains.academic.knowledge.embedding_projection': 'polisyos/data_forge/domains/academic/knowledge/embedding_projection.py',
    'polisyos.data_forge.domains.academic.knowledge.store': 'polisyos/data_forge/domains/academic/knowledge/store.py',
    'polisyos.data_forge.domains.catalog.batch.embedder': 'polisyos/data_forge/domains/catalog/batch/embedder.py',
    'polisyos.data_forge.domains.catalog.batch.graph_builder': 'polisyos/data_forge/domains/catalog/batch/graph_builder.py',
    'polisyos.data_forge.domains.catalog.knowledge.embedding_projection': 'polisyos/data_forge/domains/catalog/knowledge/embedding_projection.py',
    'polisyos.data_forge.domains.catalog.knowledge.store': 'polisyos/data_forge/domains/catalog/knowledge/store.py',
    'polisyos.data_forge.domains.catalog.knowledge.types': 'polisyos/data_forge/domains/catalog/knowledge/types.py',
    'polisyos.data_forge.kernel.embeddings': 'polisyos/data_forge/kernel/embeddings.py',
    'polisyos.data_forge.kernel.io.generation_basis': 'polisyos/data_forge/kernel/io/generation_basis.py',
}
old_result = json.loads(OLD121.read_text(encoding='utf-8'))
old_module_rows = {item['module']: item for item in old_result['installed_module_origins_and_source_identity']}
origin_rows: list[dict[str, object]] = []
with zipfile.ZipFile(WHEEL) as wheel, tarfile.open(ARCHIVE, 'r:') as source_archive:
    wheel_names = set(wheel.namelist())
    archive_names = set(source_archive.getnames())
    for module_name, relative_path in module_paths.items():
        module = importlib.import_module(module_name)
        origin = Path(module.__file__).resolve()
        require(origin.is_relative_to(site), f'{module_name} resolved outside site-packages: {origin}')
        wheel_member = relative_path
        archive_member = f'policy-engine/src/{relative_path}'
        require(wheel_member in wheel_names, f'{module_name} absent from CAT wheel')
        require(archive_member in archive_names, f'{module_name} absent from CAT archive')
        installed_bytes = origin.read_bytes()
        wheel_bytes = wheel.read(wheel_member)
        archive_file = source_archive.extractfile(archive_member)
        require(archive_file is not None, f'missing CAT source member: {archive_member}')
        source_bytes = archive_file.read()
        require(installed_bytes == wheel_bytes == source_bytes, f'{module_name} origin/source/wheel mismatch')
        installed_sha = hashlib.sha256(installed_bytes).hexdigest()
        old_sha = old_module_rows.get(module_name, {}).get('sha256')
        require(old_sha == installed_sha, f'{module_name} differs from recorded source-121 module bytes')
        origin_rows.append({
            'module': module_name,
            'origin': str(origin),
            'wheel_member': wheel_member,
            'archive_member': archive_member,
            'sha256': installed_sha,
            'installed_equals_CAT_wheel_and_archive': True,
            'equals_source_121_probe_module': True,
        })

from polisyos.data_forge.domains.academic.batch.embedder import build_hnsw_index as build_academic_index
from polisyos.data_forge.domains.academic.knowledge.store import ScholarKnowledgeStore
from polisyos.data_forge.domains.catalog.batch.embedder import build_hnsw_index as build_catalog_index
from polisyos.data_forge.domains.catalog.batch.graph_builder import build_graph
from polisyos.data_forge.domains.catalog.knowledge.store import DatasetCatalogStore
from polisyos.data_forge.domains.catalog.knowledge.types import DatasetRecord, DistributionRecord
from polisyos.data_forge.kernel.embeddings import resolve_embedding_generation

reference_vectors = {
    'academic-alpha': np.asarray([1.0, 0.0, 0.0, 0.0], dtype=np.float32),
    'academic-beta': np.asarray([0.0, 1.0, 0.0, 0.0], dtype=np.float32),
    'catalog-gamma': np.asarray([0.0, 0.0, 1.0, 0.0], dtype=np.float32),
}

# Academic DB fixture: exactly two works, followed by the actual public domain producer.
academic_root = OUT / 'academic'
academic_root.mkdir()
academic_db = academic_root / 'academic.duckdb'
academic_index_dir = academic_root / 'index'
with duckdb.connect(str(academic_db)) as con:
    con.execute(
        'CREATE TABLE ac_works ('
        'id VARCHAR, title VARCHAR, doi VARCHAR, abstract VARCHAR, year INTEGER, '
        'publication_date VARCHAR, language VARCHAR, work_type VARCHAR, '
        'is_retracted BOOLEAN, cited_by_count INTEGER, fwci DOUBLE, '
        'citation_percentile DOUBLE, citation_top_1 BOOLEAN, citation_top_10 BOOLEAN, '
        'journal VARCHAR, source_id VARCHAR, is_oa BOOLEAN, has_fulltext BOOLEAN, '
        'full_text_url VARCHAR, trust_score DOUBLE, study_design VARCHAR)'
    )
    con.execute('CREATE TABLE ac_topic_selections (work_id VARCHAR, topic_id VARCHAR)')
    con.execute(
        'CREATE TABLE ac_parameter_estimates ('
        'id VARCHAR, work_id VARCHAR, variable_name VARCHAR, estimate DOUBLE, '
        'ci_low DOUBLE, ci_high DOUBLE, std_error DOUBLE, unit VARCHAR, domain VARCHAR, '
        'study_design VARCHAR, sample_size INTEGER, country VARCHAR, period_start INTEGER, '
        'period_end INTEGER, trust_score DOUBLE, raw_context VARCHAR)'
    )
    con.executemany(
        'INSERT INTO ac_works (id, title, abstract) VALUES (?, ?, ?)',
        [
            ('academic-alpha', 'fixture-academic-alpha intervention', 'Alpha policy effects.'),
            ('academic-beta', 'fixture-academic-beta program', 'Beta outcomes.'),
        ],
    )
    con.execute('CHECKPOINT')

academic_count, academic_dimension = build_academic_index(
    db_path=academic_db,
    index_dir=academic_index_dir,
    embedding_model='synthetic-fixture-no-weights',
    embedding_dimension=4,
    embedding_batch_size=2,
    embedding_device='cpu',
)
academic_reference = resolve_embedding_generation(
    academic_index_dir,
    legacy_embeddings_path=academic_index_dir / 'ac_work_embeddings.npz',
    legacy_index_path=academic_index_dir / 'ac_work_index.hnsw',
)
require(academic_reference is not None and academic_reference.selected, 'academic generation not selected')
require(academic_reference.status == 'complete', 'academic generation not complete')
with np.load(str(academic_reference.embeddings_path), allow_pickle=True) as payload:
    academic_npz_ids = [str(item) for item in payload['ids'].tolist()]
    academic_matrix = np.asarray(payload['vectors'], dtype=np.float32).copy()
require(set(academic_npz_ids) == {'academic-alpha', 'academic-beta'}, 'academic NPZ membership mismatch')
academic_vectors = {identifier: academic_matrix[academic_npz_ids.index(identifier)] for identifier in academic_npz_ids}
for identifier in ('academic-alpha', 'academic-beta'):
    require(np.array_equal(academic_vectors[identifier], reference_vectors[identifier]), f'academic reference vector mismatch for {identifier}')
academic_reader = ScholarKnowledgeStore(academic_db, academic_index_dir)
try:
    academic_positive = {
        identifier: [item.id for item in academic_reader.search_works_by_vector(vector, top_k=1, min_similarity=0.0)]
        for identifier, vector in reference_vectors.items()
        if identifier.startswith('academic-')
    }
finally:
    academic_reader.close()
require(academic_count == 2 and academic_dimension == 4, 'academic producer count/dimension mismatch')
require(academic_positive == {'academic-alpha': ['academic-alpha'], 'academic-beta': ['academic-beta']}, 'academic installed reader did not resolve independent reference map')
academic_hashes = artifact_hashes(academic_reference, academic_index_dir)

# Copy the selected artifacts, remove only the selected native member, and require the actual
# reader to fail closed. Original producer artifacts remain available for the source-removal check.
import shutil
academic_missing_index_dir = OUT / 'academic-missing-index'
shutil.copytree(academic_index_dir, academic_missing_index_dir)
academic_missing_ref = resolve_embedding_generation(
    academic_missing_index_dir,
    legacy_embeddings_path=academic_missing_index_dir / 'ac_work_embeddings.npz',
    legacy_index_path=academic_missing_index_dir / 'ac_work_index.hnsw',
)
require(academic_missing_ref is not None and academic_missing_ref.index_path is not None, 'academic copied selector unresolved before removal')
Path(academic_missing_ref.index_path).unlink()
academic_missing_reader = ScholarKnowledgeStore(academic_db, academic_missing_index_dir)
try:
    academic_missing_member_results = [item.id for item in academic_missing_reader.search_works_by_vector(reference_vectors['academic-alpha'], top_k=1, min_similarity=0.0)]
finally:
    academic_missing_reader.close()
require(academic_missing_member_results == [], 'academic reader accepted selected generation after native member removal')
with duckdb.connect(str(academic_db)) as con:
    con.execute("DELETE FROM ac_works WHERE id = 'academic-beta'")
    con.execute('CHECKPOINT')
academic_removed_reader = ScholarKnowledgeStore(academic_db, academic_index_dir)
try:
    academic_removed_source_results = [item.id for item in academic_removed_reader.search_works_by_vector(reference_vectors['academic-alpha'], top_k=1, min_similarity=0.0)]
finally:
    academic_removed_reader.close()
require(academic_removed_source_results == [], 'academic reader admitted generation after source-row removal')

# Catalog graph fixture: one typed DatasetRecord, actual graph writer and embedding producer.
catalog_root = OUT / 'catalog'
catalog_root.mkdir()
catalog_db = catalog_root / 'catalog.duckdb'
catalog_index_dir = catalog_root / 'index'
catalog_record = DatasetRecord(
    id='catalog-gamma',
    title='fixture-catalog-gamma dataset',
    description='Synthetic one-record catalog reader fixture.',
    keywords=['catalog-fixture'],
    variables=['fixture_variable'],
    source='fixture_source',
    agency='fixture_agency',
    dataset_id='fixture-dataset-gamma',
    source_dataset_id='fixture-dataset-gamma',
    execution_tier='transport_ready',
    distributions=[
        DistributionRecord(
            id='catalog-distribution-gamma',
            connector_type='fixture.connector',
            source_locator='fixture-dataset-gamma',
            parser_supported=True,
            machine_readable=True,
        )
    ],
)
graph_stats = build_graph(records=[catalog_record], db_path=catalog_db)
catalog_encoder = FixtureEncoder(device='cpu')
catalog_count = build_catalog_index(
    db_path=catalog_db,
    index_dir=catalog_index_dir,
    embedding_model=catalog_encoder.model_name,
    embedding_dimension=4,
    embedding_batch_size=1,
    embedding_device='cpu',
    encoder=catalog_encoder,
)
catalog_reference = resolve_embedding_generation(
    catalog_index_dir,
    legacy_embeddings_path=catalog_index_dir / 'ds_dataset_embeddings.npz',
    legacy_index_path=catalog_index_dir / 'ds_dataset_index.hnsw',
)
require(catalog_reference is not None and catalog_reference.selected, 'catalog generation not selected')
require(catalog_reference.status == 'complete', 'catalog generation not complete')
with np.load(str(catalog_reference.embeddings_path), allow_pickle=True) as payload:
    catalog_npz_ids = [str(item) for item in payload['ids'].tolist()]
    catalog_matrix = np.asarray(payload['vectors'], dtype=np.float32).copy()
require(catalog_npz_ids == ['catalog-gamma'], 'catalog NPZ membership mismatch')
require(np.array_equal(catalog_matrix[0], reference_vectors['catalog-gamma']), 'catalog reference vector mismatch')
catalog_reader = DatasetCatalogStore(catalog_db, catalog_index_dir)
try:
    catalog_has_index = catalog_reader.has_vector_index()
    catalog_positive = [item.id for item in catalog_reader.search_by_vector(reference_vectors['catalog-gamma'], top_k=1, min_similarity=0.0)]
finally:
    catalog_reader.close()
require(catalog_count == 1 and graph_stats.datasets == 1, 'catalog producer/graph count mismatch')
require(catalog_has_index, 'catalog consumer did not recognize selected vector index')
require(catalog_positive == ['catalog-gamma'], 'catalog installed reader did not resolve independent reference map')
catalog_hashes = artifact_hashes(catalog_reference, catalog_index_dir)

catalog_missing_index_dir = OUT / 'catalog-missing-index'
shutil.copytree(catalog_index_dir, catalog_missing_index_dir)
catalog_missing_ref = resolve_embedding_generation(
    catalog_missing_index_dir,
    legacy_embeddings_path=catalog_missing_index_dir / 'ds_dataset_embeddings.npz',
    legacy_index_path=catalog_missing_index_dir / 'ds_dataset_index.hnsw',
)
require(catalog_missing_ref is not None and catalog_missing_ref.index_path is not None, 'catalog copied selector unresolved before removal')
Path(catalog_missing_ref.index_path).unlink()
catalog_missing_reader = DatasetCatalogStore(catalog_db, catalog_missing_index_dir)
try:
    catalog_missing_member_results = [item.id for item in catalog_missing_reader.search_by_vector(reference_vectors['catalog-gamma'], top_k=1, min_similarity=0.0)]
finally:
    catalog_missing_reader.close()
require(catalog_missing_member_results == [], 'catalog reader accepted selected generation after native member removal')
with duckdb.connect(str(catalog_db)) as con:
    con.execute("DELETE FROM ds_datasets WHERE id = 'catalog-gamma'")
    con.execute('CHECKPOINT')
catalog_removed_reader = DatasetCatalogStore(catalog_db, catalog_index_dir)
try:
    catalog_removed_source_results = [item.id for item in catalog_removed_reader.search_by_vector(reference_vectors['catalog-gamma'], top_k=1, min_similarity=0.0)]
finally:
    catalog_removed_reader.close()
require(catalog_removed_source_results == [], 'catalog reader admitted generation after source-row removal')

require(sys.path == initial_sys_path, 'sys.path changed during installed producer/reader probes')
output = {
    'candidate': {
        'policy_engine_distribution_version': distribution.version,
        'site_packages': str(site),
        'wheel': str(WHEEL),
        'wheel_sha256': hashlib.sha256(WHEEL.read_bytes()).hexdigest(),
        'source_archive': str(ARCHIVE),
        'source_archive_sha256': hashlib.sha256(ARCHIVE.read_bytes()).hexdigest(),
        'cwd': str(Path.cwd()),
        'python': sys.executable,
        'isolated_mode': sys.flags.isolated == 1,
        'PYTHONPATH': None,
        'candidate_source_on_sys_path': False,
        'sys_path_unchanged': True,
        'hnswlib': {'version': metadata.version('hnswlib'), 'origin': str(Path(hnswlib.__file__).resolve())},
        'sentence_transformers_distribution': sentence_transformers_distribution,
        'fixture_encoder': {'name': 'synthetic-fixture-no-weights', 'state': 'only the external model boundary was replaced', 'weights_downloaded': False, 'scientific_precision_claim': False},
    },
    'installed_module_identity': origin_rows,
    'reference_map': {key: value.tolist() for key, value in reference_vectors.items()},
    'academic': {
        'producer': 'installed polisyos.data_forge.domains.academic.batch.embedder.build_hnsw_index',
        'reader': 'installed polisyos.data_forge.domains.academic.knowledge.store.ScholarKnowledgeStore.search_works_by_vector',
        'fixture_rows': 2,
        'produced_count': academic_count,
        'dimension': academic_dimension,
        'selector_status': academic_reference.status,
        'selected': academic_reference.selected,
        'generation_id': academic_reference.generation_id,
        'npz_membership': academic_npz_ids,
        'independent_reference_map_results': academic_positive,
        'selected_artifacts': academic_hashes,
        'removed_native_index_reader_results': academic_missing_member_results,
        'removed_source_row_reader_results': academic_removed_source_results,
    },
    'catalog': {
        'producer_chain': 'installed graph_builder.build_graph -> installed catalog.batch.embedder.build_hnsw_index',
        'reader': 'installed polisyos.data_forge.domains.catalog.knowledge.store.DatasetCatalogStore.search_by_vector',
        'fixture_rows': 1,
        'graph_dataset_count': graph_stats.datasets,
        'produced_count': catalog_count,
        'selector_status': catalog_reference.status,
        'selected': catalog_reference.selected,
        'generation_id': catalog_reference.generation_id,
        'npz_membership': catalog_npz_ids,
        'has_vector_index': catalog_has_index,
        'independent_reference_map_results': catalog_positive,
        'selected_artifacts': catalog_hashes,
        'removed_native_index_reader_results': catalog_missing_member_results,
        'removed_source_row_reader_results': catalog_removed_source_results,
    },
    'fixture_scope': {'total_source_rows': 3, 'academic_rows': 2, 'catalog_rows': 1, 'external_calls': 0},
}
print(json.dumps(output, ensure_ascii=False, sort_keys=True))

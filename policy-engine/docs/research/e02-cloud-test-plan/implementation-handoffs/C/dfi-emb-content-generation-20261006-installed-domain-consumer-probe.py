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

RAW = Path('/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C2/raw/installed/dfi-12190').resolve()
FIX = RAW / 'runtime-fixtures-retry'
ROOT = Path('/Users/deniskopylov/.codex/worktrees/e02-c-dfi-emb-20261006/polisyos/policy-engine').resolve()
WHEEL = RAW / 'dist/policy_engine-0.1.0-py3-none-any.whl'
ARCHIVE = RAW / 'candidate.tar'

def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)

class FixtureTokenizer:
    model_max_length = 128
    padding_side = 'right'
    truncation_side = 'right'
    init_kwargs = {'name_or_path': 'synthetic-fixture-only'}

    def get_vocab(self) -> dict[str, int]:
        return {'<unk>': 0, 'fixture': 1, 'policy': 2}

    @property
    def special_tokens_map(self) -> dict[str, str]:
        return {'unk_token': '<unk>'}

    def get_added_vocab(self) -> dict[str, int]:
        return {}

class FixtureEncoder:
    """Small deterministic test encoder; it contains no model weights."""
    def __init__(self, model_name: str = 'synthetic-fixture-no-weights', device: str = 'cpu', **_: object) -> None:
        self.model_name = model_name
        self.device = device
        self.config = {'model_name': model_name, 'fixture_dimension': 4}
        self.tokenizer = FixtureTokenizer()

    def state_dict(self) -> dict[str, np.ndarray]:
        return {'fixture.parameters': np.asarray([4.0, 1.0], dtype=np.float32)}

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
        del batch_size, show_progress_bar
        rows = []
        for text in texts:
            base = float(sum(str(text).encode('utf-8')) % 31 + 1)
            vector = np.asarray([base, base + 1.0, base + 2.0, base + 3.0], dtype=np.float32)
            if normalize_embeddings:
                vector = vector / np.linalg.norm(vector)
            rows.append(vector)
        return np.vstack(rows)

# Academic's public builder resolves SentenceTransformer itself. Inject only a synthetic fixture
# encoder so the production producer still writes the HNSW generation via native hnswlib.
fixture_module = types.ModuleType('sentence_transformers')
fixture_module.SentenceTransformer = FixtureEncoder
sys.modules['sentence_transformers'] = fixture_module

from polisyos.data_forge.domains.academic.batch.embedder import build_hnsw_index as build_academic_index
from polisyos.data_forge.domains.academic.knowledge.store import ScholarKnowledgeStore
from polisyos.data_forge.domains.catalog.batch.config import DatasetBatchConfig
from polisyos.data_forge.domains.catalog.batch.embedder import build_hnsw_index as build_catalog_index
from polisyos.data_forge.domains.catalog.batch.graph_builder import build_graph
from polisyos.data_forge.domains.catalog.knowledge.store import DatasetCatalogStore
from polisyos.data_forge.domains.catalog.knowledge.types import DatasetRecord, DistributionRecord
from polisyos.data_forge.domains.legal.batch.embedder import build_local_embeddings_and_indexes
from polisyos.data_forge.kernel.embeddings import resolve_embedding_generation
from polisyos.lex.knowledge.store import LegalKnowledgeStore

critical_modules = {
    'polisyos.data_forge.domains.academic.batch.embedder': 'src/polisyos/data_forge/domains/academic/batch/embedder.py',
    'polisyos.data_forge.domains.academic.knowledge.embedding_projection': 'src/polisyos/data_forge/domains/academic/knowledge/embedding_projection.py',
    'polisyos.data_forge.domains.academic.knowledge.store': 'src/polisyos/data_forge/domains/academic/knowledge/store.py',
    'polisyos.data_forge.domains.catalog.batch.config': 'src/polisyos/data_forge/domains/catalog/batch/config.py',
    'polisyos.data_forge.domains.catalog.batch.embedder': 'src/polisyos/data_forge/domains/catalog/batch/embedder.py',
    'polisyos.data_forge.domains.catalog.batch.graph_builder': 'src/polisyos/data_forge/domains/catalog/batch/graph_builder.py',
    'polisyos.data_forge.domains.catalog.knowledge.embedding_projection': 'src/polisyos/data_forge/domains/catalog/knowledge/embedding_projection.py',
    'polisyos.data_forge.domains.catalog.knowledge.store': 'src/polisyos/data_forge/domains/catalog/knowledge/store.py',
    'polisyos.data_forge.domains.catalog.knowledge.types': 'src/polisyos/data_forge/domains/catalog/knowledge/types.py',
    'polisyos.data_forge.domains.legal.batch.embedder': 'src/polisyos/data_forge/domains/legal/batch/embedder.py',
    'polisyos.data_forge.domains.legal.embedding_projection': 'src/polisyos/data_forge/domains/legal/embedding_projection.py',
    'polisyos.data_forge.kernel.embeddings': 'src/polisyos/data_forge/kernel/embeddings.py',
    'polisyos.data_forge.kernel.io.generation_basis': 'src/polisyos/data_forge/kernel/io/generation_basis.py',
    'polisyos.lex.knowledge.store': 'src/polisyos/lex/knowledge/store.py',
}
dist = metadata.distribution('policy-engine')
site = Path(dist.locate_file('')).resolve()
require(Path.cwd().resolve() == Path('/tmp').resolve(), f'expected outside-checkout CWD, got {Path.cwd()}')
require(not any(str(ROOT) == entry or str(ROOT) in entry for entry in sys.path), 'candidate source root present on sys.path')
origin_rows = []
with zipfile.ZipFile(WHEEL) as wheel, tarfile.open(ARCHIVE, 'r:') as archive:
    wheel_names = set(wheel.namelist())
    archive_names = set(archive.getnames())
    for module_name, source_path in critical_modules.items():
        module = importlib.import_module(module_name)
        origin = Path(module.__file__).resolve()
        require(origin.is_relative_to(site), f'{module_name} did not import from site-packages: {origin}')
        wheel_member = source_path.removeprefix('src/')
        archive_member = f'source/policy-engine/{source_path}'
        require(wheel_member in wheel_names, f'{module_name} absent from wheel: {wheel_member}')
        require(archive_member in archive_names, f'{module_name} absent from source archive: {archive_member}')
        installed_bytes = origin.read_bytes()
        wheel_bytes = wheel.read(wheel_member)
        source_bytes = archive.extractfile(archive_member).read()
        require(installed_bytes == wheel_bytes == source_bytes, f'{module_name} is not installed from the exact candidate bytes')
        origin_rows.append({
            'module': module_name,
            'origin': str(origin),
            'sha256': hashlib.sha256(installed_bytes).hexdigest(),
            'wheel_member': wheel_member,
            'archive_member': archive_member,
            'byte_identical_to_wheel_and_frozen_source': True,
        })


def read_vectors(index_dir: Path, legacy_npz: Path, legacy_index: Path) -> tuple[Any, np.ndarray, dict[str, object]]:
    reference = resolve_embedding_generation(index_dir, legacy_embeddings_path=legacy_npz, legacy_index_path=legacy_index)
    require(reference is not None and reference.selected and reference.status == 'complete', f'no complete selected generation at {index_dir}')
    with np.load(str(reference.embeddings_path), allow_pickle=True) as data:
        ids = [str(value) for value in data['ids'].tolist()]
        vectors = np.asarray(data['vectors'], dtype=np.float32).copy()
    require(ids == list(reference.ids), f'selected ids differ from matrix ids at {index_dir}')
    return reference, vectors, reference.inventory


def fixture_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

# Academic producer -> selected HNSW generation -> real ScholarKnowledgeStore consumer.
academic_root = FIX / 'academic'
academic_db = academic_root / 'academic.duckdb'
academic_index_dir = academic_root / 'index'
fixture_db(academic_db)
with duckdb.connect(str(academic_db)) as con:
    con.execute('CREATE TABLE ac_works (id VARCHAR, title VARCHAR, doi VARCHAR, abstract VARCHAR, year INTEGER, publication_date VARCHAR, language VARCHAR, work_type VARCHAR, is_retracted BOOLEAN, cited_by_count INTEGER, fwci DOUBLE, citation_percentile DOUBLE, citation_top_1 BOOLEAN, citation_top_10 BOOLEAN, journal VARCHAR, source_id VARCHAR, is_oa BOOLEAN, has_fulltext BOOLEAN, full_text_url VARCHAR, trust_score DOUBLE, study_design VARCHAR)')
    con.execute('CREATE TABLE ac_topic_selections (work_id VARCHAR, topic_id VARCHAR)')
    con.execute('CREATE TABLE ac_parameter_estimates (id VARCHAR, work_id VARCHAR, variable_name VARCHAR, estimate DOUBLE, ci_low DOUBLE, ci_high DOUBLE, std_error DOUBLE, unit VARCHAR, domain VARCHAR, study_design VARCHAR, sample_size INTEGER, country VARCHAR, period_start INTEGER, period_end INTEGER, trust_score DOUBLE, raw_context VARCHAR)')
    con.execute('INSERT INTO ac_works (id, title, abstract) VALUES (?, ?, ?)', ['a-fixture-1', 'Fixture employment intervention', 'Observed policy and employment outcomes'])
    con.execute('CHECKPOINT')
academic_model = 'synthetic-fixture-no-weights'
academic_count, academic_dim = build_academic_index(
    db_path=academic_db,
    index_dir=academic_index_dir,
    embedding_model=academic_model,
    embedding_dimension=4,
    embedding_batch_size=1,
    embedding_device='cpu',
)
academic_ref, academic_vectors, academic_inventory = read_vectors(
    academic_index_dir,
    academic_index_dir / 'ac_work_embeddings.npz',
    academic_index_dir / 'ac_work_index.hnsw',
)
academic_reader = ScholarKnowledgeStore(academic_db, academic_index_dir)
try:
    academic_positive = academic_reader.search_works_by_vector(academic_vectors[0], top_k=1, min_similarity=0.0)
finally:
    academic_reader.close()
with duckdb.connect(str(academic_db)) as con:
    con.execute("UPDATE ac_works SET abstract = 'Changed source content after the selected generation' WHERE id = 'a-fixture-1'")
    con.execute('CHECKPOINT')
academic_stale_reader = ScholarKnowledgeStore(academic_db, academic_index_dir)
try:
    academic_stale = academic_stale_reader.search_works_by_vector(academic_vectors[0], top_k=1, min_similarity=0.0)
finally:
    academic_stale_reader.close()
require(academic_count == 1 and academic_dim == 4, 'academic producer did not build one 4D item')
require([item.id for item in academic_positive] == ['a-fixture-1'], 'academic installed reader did not consume the selected item')
require(academic_stale == [], 'academic reader admitted a stale selected basis')

# Catalog graph writer + embedding producer -> actual DatasetCatalogStore reader.
catalog_root = FIX / 'catalog'
catalog_root.mkdir(parents=True, exist_ok=True)
registry_path = catalog_root / 'source-registry.yaml'
registry_path.write_text('version: 1\nsources:\n  - name: worldbank\n    family: worldbank\n    wave: A\n    endpoint: https://example.test/worldbank\n    enabled: true\n    execution_tier: transport_ready\n    run_lane: empirical\n    publish_blocking: true\n', encoding='utf-8')
metrics_map_path = catalog_root / 'metrics_map.yaml'
metrics_map_path.write_text('{}\n', encoding='utf-8')
catalog_config = DatasetBatchConfig(snapshot_root=catalog_root / 'snapshot', registry_path=registry_path, metrics_map_path=metrics_map_path)
catalog_record = DatasetRecord(
    id='ds-fixture-1',
    title='Fixture employment dataset',
    description='Synthetic catalog fixture; no remote source was queried.',
    keywords=['employment', 'policy'],
    variables=['employment_rate'],
    source='fixture',
    agency='fixture',
    dataset_id='fixture-employment',
    source_dataset_id='fixture-employment',
    execution_tier='transport_ready',
    distributions=[DistributionRecord(
        id='dist-fixture-1',
        connector_type='worldbank.wdi',
        source_locator='fixture-employment',
        parser_supported=True,
        machine_readable=True,
    )],
)
build_graph(records=iter([catalog_record]), db_path=catalog_config.db_path)
catalog_model = FixtureEncoder('synthetic-fixture-no-weights', device='cpu')
catalog_count = build_catalog_index(
    db_path=catalog_config.db_path,
    index_dir=catalog_config.index_dir,
    embedding_model=catalog_model.model_name,
    embedding_dimension=4,
    embedding_batch_size=1,
    embedding_device='cpu',
    encoder=catalog_model,
)
catalog_ref, catalog_vectors, catalog_inventory = read_vectors(
    catalog_config.index_dir,
    catalog_config.index_dir / 'ds_dataset_embeddings.npz',
    catalog_config.index_dir / 'ds_dataset_index.hnsw',
)
catalog_reader = DatasetCatalogStore(catalog_config.db_path, catalog_config.index_dir)
try:
    catalog_has_index = catalog_reader.has_vector_index()
    catalog_positive = catalog_reader.search_by_vector(catalog_vectors[0], top_k=1, min_similarity=0.0)
finally:
    catalog_reader.close()
with duckdb.connect(str(catalog_config.db_path)) as con:
    con.execute("UPDATE ds_datasets SET description = 'Changed after catalog generation selection' WHERE id = 'ds-fixture-1'")
    con.execute('CHECKPOINT')
catalog_stale_reader = DatasetCatalogStore(catalog_config.db_path, catalog_config.index_dir)
try:
    catalog_stale = catalog_stale_reader.search_by_vector(catalog_vectors[0], top_k=1, min_similarity=0.0)
finally:
    catalog_stale_reader.close()
require(catalog_count == 1 and catalog_has_index, 'catalog producer did not publish a native selected index')
require([item.id for item in catalog_positive] == ['ds-fixture-1'], 'catalog installed reader did not consume the selected item')
require(catalog_stale == [], 'catalog reader admitted a stale selected basis')

# Legal batch producer -> actual entity/fact/provision readers over three native HNSW generations.
legal_root = FIX / 'legal'
legal_db = legal_root / 'lex.duckdb'
legal_output = legal_root / 'index'
fixture_db(legal_db)
with duckdb.connect(str(legal_db)) as con:
    con.execute('CREATE TABLE lex_entities (entity_id VARCHAR, name_en VARCHAR, name_uk VARCHAR, entity_type VARCHAR, aliases_en VARCHAR, aliases_uk VARCHAR)')
    con.execute('CREATE TABLE lex_facts (fact_id VARCHAR, subject_en VARCHAR, subject_uk VARCHAR, predicate VARCHAR, object_en VARCHAR, object_uk VARCHAR, fact_text VARCHAR, norm_type VARCHAR, action_canon VARCHAR, norm_type_canon VARCHAR, condition_text_uk VARCHAR, exception_text_uk VARCHAR, procedure_text_uk VARCHAR, thresholds_json VARCHAR, source_quote_uk VARCHAR)')
    con.execute('CREATE TABLE lex_provisions (provision_id VARCHAR, provision_text VARCHAR)')
    con.execute('INSERT INTO lex_entities VALUES (?, ?, ?, ?, ?, ?)', ['e-fixture-1', 'Synthetic agency', 'Синтетичне агентство', 'concept', '', ''])
    con.execute('INSERT INTO lex_facts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', ['f-fixture-1', 'Agency', 'Агентство', 'requires', 'Benefit', 'Пільга', 'Fixture policy benefit fact', 'obligation', 'requires', 'obligation', '', '', '', '[]', 'fixture source quote'])
    con.execute('INSERT INTO lex_provisions VALUES (?, ?)', ['p-fixture-1', 'Fixture provision text'])
    con.execute('CHECKPOINT')
legal_model = FixtureEncoder('synthetic-fixture-no-weights', device='cpu')
legal_stats = build_local_embeddings_and_indexes(
    db_path=legal_db,
    output_dir=legal_output,
    embedding_model=legal_model.model_name,
    embedding_device='cpu',
    embedding_batch_size=1,
    embedding_chunk_size=1,
    incremental=False,
    encoder=legal_model,
)
legal_generation_data = {}
for embedding_name, index_name in (
    ('lex_entity_embeddings', 'lex_entity_index'),
    ('lex_fact_embeddings', 'lex_fact_index'),
    ('lex_provision_embeddings', 'lex_provision_index'),
):
    ref, vectors, inventory = read_vectors(
        legal_output / '.legal_embedding_generations' / embedding_name,
        legal_output / f'{embedding_name}.npz',
        legal_output / f'{index_name}.hnsw',
    )
    legal_generation_data[embedding_name] = {'reference': ref, 'vectors': vectors, 'inventory': inventory}
legal_reader = LegalKnowledgeStore(legal_db, legal_output)
try:
    legal_entity_positive = legal_reader.search_entities_by_vector(legal_generation_data['lex_entity_embeddings']['vectors'][0], min_similarity=0.0)
    legal_fact_positive = legal_reader.search_facts_by_vector(legal_generation_data['lex_fact_embeddings']['vectors'][0], min_similarity=0.0, include_candidates=True)
    legal_provision_positive = legal_reader.search_provisions_by_vector(legal_generation_data['lex_provision_embeddings']['vectors'][0], min_similarity=0.0)
finally:
    legal_reader.close()
with duckdb.connect(str(legal_db)) as con:
    con.execute("UPDATE lex_entities SET name_en = 'Changed legal entity', name_uk = 'Змінена правова сутність' WHERE entity_id = 'e-fixture-1'")
    con.execute("UPDATE lex_facts SET fact_text = 'Changed legal fact text' WHERE fact_id = 'f-fixture-1'")
    con.execute("UPDATE lex_provisions SET provision_text = 'Changed legal provision text' WHERE provision_id = 'p-fixture-1'")
    con.execute('CHECKPOINT')
legal_stale_reader = LegalKnowledgeStore(legal_db, legal_output)
try:
    legal_entity_stale = legal_stale_reader.search_entities_by_vector(legal_generation_data['lex_entity_embeddings']['vectors'][0], min_similarity=0.0)
    legal_fact_stale = legal_stale_reader.search_facts_by_vector(legal_generation_data['lex_fact_embeddings']['vectors'][0], min_similarity=0.0, include_candidates=True)
    legal_provision_stale = legal_stale_reader.search_provisions_by_vector(legal_generation_data['lex_provision_embeddings']['vectors'][0], min_similarity=0.0)
finally:
    legal_stale_reader.close()
require((legal_stats.entities_embedded, legal_stats.facts_embedded, legal_stats.provisions_embedded) == (1, 1, 1), 'legal producer did not build one item per projection')
require([item.entity_id for item in legal_entity_positive] == ['e-fixture-1'], 'legal entity reader did not consume selected item')
require([item.fact_id for item in legal_fact_positive] == ['f-fixture-1'], 'legal fact reader did not consume selected item')
require([item.provision_id for item in legal_provision_positive] == ['p-fixture-1'], 'legal provision reader did not consume selected item')
require(legal_entity_stale == [] and legal_fact_stale == [] and legal_provision_stale == [], 'legal readers admitted stale selected membership')

# The selected generation results above come from native .hnsw files and these imported modules
# all resolve from site-packages. The test encoder is synthetic and supplies no model-weight claim.
output = {
    'cwd': str(Path.cwd()),
    'python': sys.executable,
    'distribution': {'name': 'policy-engine', 'version': dist.version, 'site_packages': str(site)},
    'candidate_checkout_on_sys_path': False,
    'native_hnswlib': {'version': metadata.version('hnswlib'), 'module_origin': str(Path(hnswlib.__file__).resolve()), 'extension_suffix': Path(hnswlib.__file__).suffix},
    'encoder_fixture': {'name': 'synthetic-fixture-no-weights', 'weights_downloaded': False, 'sentence_transformers_installed': False, 'scientific_precision_claim': False},
    'installed_module_origins_and_source_identity': origin_rows,
    'academic': {
        'producer': 'academic.batch.embedder.build_hnsw_index',
        'producer_rows': academic_count,
        'dimension': academic_dim,
        'selector_status': academic_ref.status,
        'generation_id': academic_ref.generation_id,
        'basis_kind': academic_inventory['basis']['basis_kind'],
        'positive_reader_ids': [item.id for item in academic_positive],
        'after_source_change_reader_ids': [item.id for item in academic_stale],
    },
    'catalog': {
        'producer': 'catalog.batch.embedder.build_hnsw_index via graph_builder.build_graph',
        'producer_rows': catalog_count,
        'has_selected_vector_index': catalog_has_index,
        'selector_status': catalog_ref.status,
        'generation_id': catalog_ref.generation_id,
        'basis_kind': catalog_inventory['basis']['basis_kind'],
        'positive_reader_ids': [item.id for item in catalog_positive],
        'after_source_change_reader_ids': [item.id for item in catalog_stale],
    },
    'legal': {
        'producer': 'legal.batch.embedder.build_local_embeddings_and_indexes',
        'producer_rows': {'entities': legal_stats.entities_embedded, 'facts': legal_stats.facts_embedded, 'provisions': legal_stats.provisions_embedded},
        'selector_statuses': {name: data['reference'].status for name, data in legal_generation_data.items()},
        'generation_ids': {name: data['reference'].generation_id for name, data in legal_generation_data.items()},
        'positive_reader_ids': {'entities': [item.entity_id for item in legal_entity_positive], 'facts': [item.fact_id for item in legal_fact_positive], 'provisions': [item.provision_id for item in legal_provision_positive]},
        'after_source_change_reader_ids': {'entities': [item.entity_id for item in legal_entity_stale], 'facts': [item.fact_id for item in legal_fact_stale], 'provisions': [item.provision_id for item in legal_provision_stale]},
    },
}
print(json.dumps(output, sort_keys=True))

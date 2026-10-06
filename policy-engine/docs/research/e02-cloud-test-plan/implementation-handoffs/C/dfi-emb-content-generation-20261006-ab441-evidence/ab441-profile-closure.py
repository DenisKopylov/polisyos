from __future__ import annotations
import importlib.metadata as md
import importlib.util
import json
import sys
from pathlib import Path
from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
import hnswlib
import numpy as np

package = md.distribution('policy-engine')
installed = {canonicalize_name(dist.metadata['Name']): dist.version for dist in md.distributions() if dist.metadata.get('Name')}
def check(extra: str) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    env = default_environment(); env['extra'] = extra
    satisfied = []; missing = []
    for raw in package.requires or []:
        req = Requirement(raw)
        if req.marker is not None and not req.marker.evaluate(env):
            continue
        name = canonicalize_name(req.name)
        version = installed.get(name)
        row = {'requirement': raw, 'name': name, 'installed_version': version}
        if version is None or (req.specifier and not req.specifier.contains(version, prereleases=True)):
            missing.append(row)
        else:
            satisfied.append(row)
    return satisfied, missing
base, base_missing = check('')
vector, vector_missing = check('vector-search')
index = hnswlib.Index(space='cosine', dim=4)
index.init_index(max_elements=2, ef_construction=40, M=8)
points = np.asarray([[1, 0, 0, 0], [0, 1, 0, 0]], dtype=np.float32)
index.add_items(points, np.asarray([41, 42], dtype=np.int64))
labels, distances = index.knn_query(points[0:1], k=1)
result = {
    'python': sys.version,
    'installed_distribution': package.version,
    'installed_root': str(Path(package.locate_file('')).resolve()),
    'installed_dist_count': len(installed),
    'base_requirement_count': len(base),
    'base_missing_or_mismatch': base_missing,
    'vector_search_requirement_count': len(vector),
    'vector_search_missing_or_mismatch': vector_missing,
    'hnswlib_version': md.version('hnswlib'),
    'hnswlib_native_origin': str(Path(hnswlib.__file__).resolve()),
    'hnswlib_native_extension_suffix': Path(hnswlib.__file__).suffix,
    'native_index_query': {'label': int(labels[0][0]), 'distance': float(distances[0][0]), 'expected_label': 41},
    'pytest_present': 'pytest' in installed,
    'sentence_transformers_present': importlib.util.find_spec('sentence_transformers') is not None,
    'transformers_present': 'transformers' in installed,
    'torch_present': 'torch' in installed,
    'duckdb_version': md.version('duckdb'),
    'extras_selected_by_sync': ['vector-search'],
    'test_extra_selected': False,
}
if base_missing or vector_missing or labels[0][0] != 41:
    raise SystemExit(json.dumps(result, sort_keys=True))
print(json.dumps(result, sort_keys=True))

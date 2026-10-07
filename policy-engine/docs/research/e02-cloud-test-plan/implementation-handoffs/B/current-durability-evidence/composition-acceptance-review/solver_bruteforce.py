"""Independent enumeration oracle for the canonical finite weighted assignment."""
from __future__ import annotations

import hashlib
import itertools
import json
import pathlib
import subprocess

from polisyos.foundry.methods.components import linker

ROOT = pathlib.Path('/workspace/e02-B-current-durability')
TARGET = '8fba148d7082089b4f5cd4979c4e0e09eefa2b6f'
OWNER = '54efb24d87ef9b50beba0e9e8d2ca5bef6bbb96f'
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() == TARGET
actual = pathlib.Path(linker.__file__).resolve()
relative = str(actual.relative_to(ROOT))
assert actual.read_bytes() == subprocess.check_output(['git', 'show', OWNER + ':' + relative], cwd=ROOT)

SOURCES = ('s0', 's1', 's2')
TARGETS = ('t0', 't1', 't2')
EDGES = tuple(itertools.product(SOURCES, TARGETS))
ASSIGNMENTS = tuple(itertools.product((None, *SOURCES), repeat=3))


def enumerate_optimal(weights, excluded=None, score_vectors=None):
    """Inspect all target→source tuples, with no augmenting paths or flow graph."""
    best_score = None
    optimal = set()
    for choices in ASSIGNMENTS:
        used = tuple(source for source in choices if source is not None)
        if len(set(used)) != len(used):
            continue
        edges = tuple((source, target) for target, source in zip(TARGETS, choices) if source is not None)
        if any(edge not in weights or edge == excluded for edge in edges):
            continue
        if score_vectors is None:
            score = (len(edges), sum(weights[edge] for edge in edges))
        else:
            totals = tuple(sum(score_vectors[edge][column] for edge in edges) for column in range(5))
            score = (len(edges), *totals)
        if best_score is None or score > best_score:
            best_score, optimal = score, {choices}
        elif score == best_score:
            optimal.add(choices)
    assert best_score is not None
    return best_score, optimal


def compare(weights, *, score_vectors=None):
    expected, optimal = enumerate_optimal(weights, score_vectors=score_vectors)
    selected, utility = linker._maximum_weight_matching(weights)
    choices = tuple(selected.get(target) for target in TARGETS)
    assert choices in optimal, (weights, expected, optimal, selected, utility)
    assert utility == sum(weights[(source, target)] for target, source in selected.items())
    found_equal_alternate = False
    for target, source in selected.items():
        edge = (source, target)
        expected_exclusion, exclusion_optimal = enumerate_optimal(weights, excluded=edge)
        other, other_utility = linker._maximum_weight_matching(weights, excluded=edge)
        assert tuple(other.get(t) for t in TARGETS) in exclusion_optimal
        assert (len(other), other_utility) == expected_exclusion
        found_equal_alternate |= (len(other), other_utility) == (len(selected), utility)
    assert found_equal_alternate == (len(optimal) > 1), (weights, optimal, selected)
    return len(selected), len(optimal) > 1


stats = {name: {'graphs': 0, 'ambiguous': 0, 'cardinalities': {str(n): 0 for n in range(4)}}
         for name in ('zero_ties', 'signed_mixed', 'unique_bit_weights', 'negative_cardinality', 'lexicographic_preferences')}
for graph in range(512):
    present = tuple(edge for position, edge in enumerate(EDGES) if graph & (1 << position))
    profiles = {
        'zero_ties': {edge: 0 for edge in present},
        'signed_mixed': {edge: (7 * SOURCES.index(edge[0]) + 5 * TARGETS.index(edge[1]) + SOURCES.index(edge[0]) * TARGETS.index(edge[1])) % 9 - 4 for edge in present},
        'unique_bit_weights': {edge: 1 << EDGES.index(edge) for edge in present},
        'negative_cardinality': {edge: -1 for edge in present},
    }
    vectors = {edge: (int(edge[0][1] == edge[1][1]), 2 * SOURCES.index(edge[0]) - TARGETS.index(edge[1]), -(SOURCES.index(edge[0]) + 2 * TARGETS.index(edge[1])) % 3, int((SOURCES.index(edge[0]) + TARGETS.index(edge[1])) % 2 == 0), -SOURCES.index(edge[0]) * TARGETS.index(edge[1])) for edge in present}
    profiles['lexicographic_preferences'] = linker._matching_utilities(vectors, 3)
    for name, weights in profiles.items():
        cardinality, ambiguous = compare(weights, score_vectors=vectors if name == 'lexicographic_preferences' else None)
        row = stats[name]
        row['graphs'] += 1
        row['ambiguous'] += int(ambiguous)
        row['cardinalities'][str(cardinality)] += 1
print(json.dumps({'outcome': 'PASS', 'target_sha': TARGET, 'owner_sha': OWNER, 'actual_module': str(actual), 'source_sha256': hashlib.sha256(actual.read_bytes()).hexdigest(), 'unique_edge_presence_graphs': 512, 'graphs_per_profile': 512, 'profiles': stats, 'graph_profile_configurations': 2560, 'reference_assignments_per_graph': 64, 'oracle': 'itertools target-source tuples + duplicate/absent-edge filter + direct lexicographic totals, independent of residual-flow implementation; every selected-edge exclusion compared to exhaustive optima; equal-optimal detection compared to count of distinct optimal assignments'}))

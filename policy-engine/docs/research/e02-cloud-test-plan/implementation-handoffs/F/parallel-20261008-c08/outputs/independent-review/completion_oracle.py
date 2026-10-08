"""Independent finite static causally sufficient partial-DAG oracle.

No PolicyOS imports. Enumerates orders, never production orientation bitmasks.
"""
from collections import Counter
from fractions import Fraction
from itertools import combinations, permutations, product
import hashlib
import json
import resource
import time


def colliders(nodes, skeleton, arcs):
    return frozenset(
        (a, b, c)
        for b in nodes
        for a, c in combinations([v for v in nodes if (v, b) in arcs], 2)
        if frozenset((a, c)) not in skeleton
    )


def completion_family(nodes, edges):
    """Edges are unordered-pair tuple and absent/undirected/forward/reverse state."""
    nodes = tuple(nodes)
    skeleton = frozenset(frozenset(pair) for pair, state in edges if state)
    fixed = frozenset(
        pair if state == 2 else pair[::-1]
        for pair, state in edges if state in (2, 3)
    )
    known_colliders = colliders(nodes, skeleton, fixed)
    admitted = set()
    for order in permutations(nodes):
        rank = {node: index for index, node in enumerate(order)}
        arcs = frozenset(
            (a, b) if rank[a] < rank[b] else (b, a)
            for pair in skeleton
            for a, b in [tuple(sorted(pair))]
        )
        if fixed <= arcs and colliders(nodes, skeleton, arcs) == known_colliders:
            admitted.add(tuple(sorted(arcs)))
    return tuple(sorted(admitted))


def truncated_binary_probability(joint, nodes, arcs, do, outcome):
    """Exact g-formula from joint law under a given complete DAG."""
    parent_sets = {n: tuple(a for a, b in arcs if b == n) for n in nodes}
    result = Fraction(0)
    for values in product((0, 1), repeat=len(nodes)):
        assignment = dict(zip(nodes, values))
        if any(assignment[n] != v for n, v in do.items()):
            continue
        mass = Fraction(1)
        for n in nodes:
            if n in do:
                continue
            parents = parent_sets[n]
            numerator = denominator = Fraction(0)
            for observed_values, observed_mass in joint.items():
                observed = dict(zip(nodes, observed_values))
                if all(observed[p] == assignment[p] for p in parents):
                    denominator += observed_mass
                    if observed[n] == assignment[n]:
                        numerator += observed_mass
            assert denominator > 0, "oracle fixtures require positive support"
            mass *= numerator / denominator
        if all(assignment[n] == v for n, v in outcome.items()):
            result += mass
    return result


def chain_joint(nodes, agreement=Fraction(4, 5)):
    return {
        bits: Fraction(1, 2)
        * (agreement if bits[0] == bits[1] else 1 - agreement)
        * (agreement if bits[1] == bits[2] else 1 - agreement)
        for bits in product((0, 1), repeat=len(nodes))
    }


def named_controls():
    pair_nodes = ('X', 'Y')
    pair = completion_family(pair_nodes, [(('X', 'Y'), 1)])
    joint_xy = {bits: Fraction(1, 2) * (Fraction(4, 5) if bits[0] == bits[1] else Fraction(1, 5))
                for bits in product((0, 1), repeat=2)}
    different = [(arcs, str(truncated_binary_probability(joint_xy, pair_nodes, arcs, {'X': 1}, {'Y': 1})))
                 for arcs in pair]
    assert sorted(value for arcs, value in different) == ['1/2', '4/5']
    chain_nodes = ('X', 'Y', 'Z')
    chain = completion_family(chain_nodes, [(('X', 'Y'), 1), (('Y', 'Z'), 1)])
    chain_values = [(arcs, str(truncated_binary_probability(chain_joint(chain_nodes), chain_nodes, arcs,
                                                           {'X': 1}, {'Z': 1}))) for arcs in chain]
    assert sorted(value for arcs, value in chain_values) == ['1/2', '1/2', '17/25']
    same_family = completion_family(chain_nodes, [(('Y', 'Z'), 1)])
    joint_same = {bits: Fraction(1, 2) * (Fraction(7, 10) if bits[1] else Fraction(3, 10))
                  * (Fraction(4, 5) if bits[1] == bits[2] else Fraction(1, 5))
                  for bits in product((0, 1), repeat=3)}
    same = [(arcs, str(truncated_binary_probability(joint_same, chain_nodes, arcs, {'X': 1}, {'Y': 1})))
            for arcs in same_family]
    assert len(same) == 2 and {value for arcs, value in same} == {'7/10'}
    triangle_nodes = ('A', 'B', 'C')
    triangle = completion_family(triangle_nodes, [(pair, 1) for pair in combinations(triangle_nodes, 2)])
    assert len(triangle) == 6
    known_path = completion_family(triangle_nodes, [(('A', 'B'), 2), (('B', 'C'), 2), (('A', 'C'), 1)])
    assert known_path == ((('A', 'B'), ('A', 'C'), ('B', 'C')),)
    known_collider = completion_family(triangle_nodes, [(('A', 'B'), 2), (('B', 'C'), 3)])
    assert known_collider == ((('A', 'B'), ('C', 'B')),)
    known_cycle = completion_family(triangle_nodes, [(('A', 'B'), 2), (('B', 'C'), 2), (('A', 'C'), 3)])
    assert not known_cycle
    return {'different_answer': different, 'same_answer': same,
            'sampled_agreement_falsifier': chain_values,
            'triangle_completions': len(triangle), 'known_path_completions': known_path,
            'known_collider_completions': known_collider, 'known_cycle_completions': known_cycle}


def main():
    start = time.monotonic()
    summary = []
    digest = hashlib.sha256()
    total_profiles = 0
    for size in range(1, 5):
        nodes = tuple('ABCD'[:size])
        pairs = tuple(combinations(nodes, 2))
        distribution = Counter()
        undirected_skeleton_dags = set()
        profile_count = 0
        for states in product(range(4), repeat=len(pairs)):
            family = completion_family(nodes, list(zip(pairs, states)))
            profile_count += 1
            distribution[len(family)] += 1
            payload = [nodes, states, family]
            digest.update(json.dumps(payload, separators=(',', ':')).encode() + b'\n')
            if all(state in (0, 1) for state in states):
                undirected_skeleton_dags.update(family)
        assert profile_count == 4 ** len(pairs)
        total_profiles += profile_count
        summary.append({'nodes': size, 'partial_profiles': profile_count,
                        'family_size_histogram': dict(sorted(distribution.items())),
                        'distinct_no_unshielded_collider_dags': len(undirected_skeleton_dags)})
    assert total_profiles == 4165
    print(json.dumps({'schema': 'e02.c08.independent_completion_oracle.v1',
                      'algorithm': 'all topological permutations; fixed arrows; exact skeleton and collider set; dedupe',
                      'profiles': summary, 'total_partial_profiles': total_profiles,
                      'complete_family_digest': digest.hexdigest(), 'named_controls': named_controls(),
                      'wall_s': time.monotonic() - start,
                      'peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                      'status': 'PASS',
                      'scope': 'static causally sufficient partial DAGs <=4 nodes, one edge per unordered pair; numerical laws synthetic only',
                      'not_established': ['genuine input graph authority', 'PAG/MGraph/latent/temporal completeness',
                                          'production estimator or consumer execution']}, indent=2))

if __name__ == '__main__':
    main()

"""Actual typed public linker refusal and explicit two-node arithmetic controls."""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys

ROOT = pathlib.Path('/workspace/e02-B-current-durability')
fixture_path = ROOT / 'policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/B/current-durability-evidence/composition-acceptance-review/successor_test_acceptance.py'
spec = importlib.util.spec_from_file_location('independent_solver_fixture', fixture_path)
fixture = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = fixture
spec.loader.exec_module(fixture)


def pair(source_names, target_names):
    calls = []
    source = fixture.method('arithmetic_pair_source', (), tuple(fixture.slot(n) for n in source_names), lambda s, p: (calls.append('source') or {source_names[0]: 7, source_names[1]: 11}))
    target = fixture.method('arithmetic_pair_target', tuple(fixture.slot(n) for n in target_names), (fixture.slot('result'),), lambda s, p: (calls.append('target') or {'result': s[target_names[0]] * 100 + s[target_names[1]]}))
    registry = fixture.registry(source, target)
    composer = fixture.MethodComposer(registry=registry, linker=fixture.SlotLinker(fixture.LinkerConfig.strict()))
    a, b = composer.add(source.signature.fqn), composer.add(target.signature.fqn)
    return source, target, registry, composer, a, b, calls


records = []
for sources, targets in [(('a', 'b'), ('left', 'right')), (('z_source', 'a_source'), ('z_target', 'a_target'))]:
    outcomes = []
    for permutation in (sources, sources[::-1]):
        source, target, registry, composer, a, b, calls = pair(sources, targets)
        mapping = dict(zip(permutation, targets))
        direct = fixture.SlotLinker(fixture.LinkerConfig.strict()).link(source.signature, target.signature, mapping)
        assert direct.binding_count == 2
        composer.connect(a, b, mapping)
        chain = composer.build(validate_semantics=fixture.Level.STRICT)
        result = fixture.execute_heterogeneous_chain(chain, state={targets[0]: 1000, targets[1]: 2000}, registry=registry)
        value = result.final_state['result']
        assert calls == ['source', 'target']
        outcomes.append(value)
    assert outcomes == [711, 1107], outcomes
    source, target, registry, composer, a, b, calls = pair(sources, targets)
    errors = []
    for operation in [lambda: fixture.SlotLinker(fixture.LinkerConfig.strict()).link(source.signature, target.signature), lambda: composer.connect(a, b)]:
        try:
            operation()
        except fixture.SlotConnectionError as error:
            assert 'Ambiguous automatic bindings' in str(error)
            errors.append({'type': type(error).__name__, 'message': str(error)})
        else:
            raise AssertionError('ambiguous automatic assignment admitted')
        assert calls == []
    records.append({'source_names': sources, 'target_names': targets, 'explicit_actual_results': outcomes, 'direct_and_composer_auto_refusals': errors, 'producer_consumer_calls_before_refusal': calls})
source, target, registry, composer, a, b, calls = pair(('left', 'right'), ('left', 'right'))
direct = fixture.SlotLinker(fixture.LinkerConfig.strict()).link(source.signature, target.signature)
assert {(binding.source_slot, binding.target_slot) for binding in direct.bindings} == {('left', 'left'), ('right', 'right')}
composer.connect(a, b)
chain = composer.build(validate_semantics=fixture.Level.STRICT)
value = fixture.execute_heterogeneous_chain(chain, state={}, registry=registry).final_state['result']
assert value == 711 and calls == ['source', 'target']
print('RESULT:' + json.dumps({'outcome': 'PASS', 'ambiguous_cases': records, 'resolved_exact_name_actual_result': value, 'resolved_calls': calls, 'semantic_premise': 'Finite named slot compatibility and exact-name operational preference; no scientific/policy authority inferred from unknown names or WARN.'}))

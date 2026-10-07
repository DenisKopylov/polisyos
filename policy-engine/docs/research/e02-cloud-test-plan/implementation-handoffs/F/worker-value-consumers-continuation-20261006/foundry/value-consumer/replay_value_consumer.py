"""Scratch-only property-removal runner for genuine current value consumers."""

from __future__ import annotations

import ast
import inspect
import sys
import textwrap

import pytest

from polisyos.ir.analytics.causal import CausalEffectReport
from polisyos.foundry.methods.components.value_evidence import project_method_value_evidence

TEST = '/tmp/e02-F-continuation-20261006/foundry/test_value_consumer_identification.py'


def remove_report_cap():
    function = CausalEffectReport.to_uncertainty_envelope
    original_identity = id(function)
    module = ast.parse(textwrap.dedent(inspect.getsource(function)))
    changed = 0
    for node in ast.walk(module):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'UncertaintyEnvelope':
            success = any(keyword.arg == 'is_heuristic_ci' and isinstance(keyword.value, ast.Constant)
                          and keyword.value.value is False for keyword in node.keywords)
            if success:
                for keyword in node.keywords:
                    if keyword.arg == 'gate_eligible':
                        keyword.value = ast.Constant(value=True)
                        changed += 1
    assert changed == 1
    ast.fix_missing_locations(module)
    namespace = dict(function.__globals__)
    exec(compile(module, '<memory-only-remove-causal-nongating-cap>', 'exec'), namespace)
    function.__code__ = namespace[function.__name__].__code__
    assert id(CausalEffectReport.to_uncertainty_envelope) == original_identity
    print('Memory-only actual report function body changed; class/function identity, SUCCESS, CI, source fields and identification reason markers retained. No source writes.')


def remove_value_guard():
    function = project_method_value_evidence
    original_identity = id(function)
    module = ast.parse(textwrap.dedent(inspect.getsource(function)))
    definition = module.body[0]
    assert isinstance(definition, ast.FunctionDef)
    changed = 0
    for node in list(definition.body):
        if not isinstance(node, ast.If):
            continue
        reasons = [item.value for item in ast.walk(node) if isinstance(item, ast.Constant) and isinstance(item.value, str)]
        if 'method_uncertainty_not_gate_eligible' in reasons:
            definition.body.remove(node)
            changed += 1
    assert changed == 1
    ast.fix_missing_locations(module)
    namespace = dict(function.__globals__)
    exec(compile(module, '<memory-only-remove-native-value-envelope-guard>', 'exec'), namespace)
    function.__code__ = namespace[function.__name__].__code__
    assert id(project_method_value_evidence) == original_identity
    print('Memory-only actual value projector gate branch removed; native declaration, owner, method/signature/function identity, estimand/content binding and all report markers retained. No source writes.')


if __name__ == '__main__':
    mode, base_temp = sys.argv[1:]
    if mode == 'report_cap':
        remove_report_cap()
        selector = 'success_ci_real_report_cas_remains_refused'
    elif mode == 'value_guard':
        remove_value_guard()
        selector = 'HEURISTIC_POST_SELECTION'
    else:
        raise ValueError(mode)
    raise SystemExit(pytest.main([TEST, '-k', selector, '-o', 'addopts=', '-p', 'no:cacheprovider',
                                 '-q', '-s', '--tb=short', '--basetemp', base_temp]))

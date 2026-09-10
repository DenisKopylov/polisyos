"""Remove actual properties in memory, retain source markers, run unchanged semantic tests."""
from __future__ import annotations

import argparse
import importlib
import inspect
import sys

import pytest

CASES = {
    'partition_union': ('polisyos.runtime.quality.operator_comprehension',
        'raise ValueError("partition_leakage:source_family_member")', 'pass',
        'tests/unit/runtime/quality/test_operator_comprehension.py::test_partition_family_union_rejects_overlap_despite_extra_members'),
    'comprehension': ('polisyos.runtime.quality.operator_comprehension',
        '        return False\n', '        return True\n',
        'tests/unit/runtime/quality/test_operator_comprehension.py::test_w5_k02_conformance_cannot_establish_human_comprehension'),
    'eligible': ('polisyos.runtime.quality.operator_comprehension',
        'result="not_established" if stop_reason else "instrument_demonstrated",',
        'result="instrument_demonstrated",',
        'tests/unit/runtime/quality/test_operator_comprehension.py::test_no_eligible_opportunity_never_reports_score'),
    'scope': ('polisyos.lex.knowledge.multilingual_assurance',
        'raise ValueError("outside_declared_denominator")', 'pass',
        'tests/unit/lex/knowledge/test_multilingual_assurance.py::test_w5_k06_certificate_cannot_be_read_outside_declared_denominator'),
    'semantic': ('polisyos.lex.knowledge.multilingual_assurance',
        'comparison="refused" if reasons else "candidate_match",', 'comparison="candidate_match",',
        'tests/unit/lex/knowledge/test_multilingual_assurance.py::test_three_ratified_semantic_promotions_fail_and_adjacent_control_compares'),
}


def main() -> int:
    """Run one single-property removal against the unchanged behavioral consumer tests."""
    parser = argparse.ArgumentParser()
    parser.add_argument('property', choices=CASES)
    args = parser.parse_args()
    module_name, old, new, test = CASES[args.property]
    module = importlib.import_module(module_name)
    source = inspect.getsource(module)
    if source.count(old) != 1:
        raise RuntimeError('removal_target_not_unique')
    exec(compile(source.replace(old, new), module.__file__, 'exec'), module.__dict__)
    print(f'property_removed={args.property}; source={module.__file__}; markers_retained=true', flush=True)
    return pytest.main([test, '-o', 'addopts=', '-q'])


if __name__ == '__main__':
    sys.exit(main())

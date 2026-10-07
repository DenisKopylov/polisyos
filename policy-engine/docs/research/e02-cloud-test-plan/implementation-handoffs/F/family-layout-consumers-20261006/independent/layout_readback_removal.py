"""Read-only-source mutation of one real slot path, retaining canonical bindings."""
from __future__ import annotations

import __future__
import ast
import hashlib
import json
import marshal
from pathlib import Path
import subprocess

ROOT = Path('/workspace/e02-F-fry-20261006')
SHA = '7f05b6259e0c78fac81a0baa4bff41e648a9d771'
PATH = 'policy-engine/src/polisyos/ir/kernel/slots.py'


def pytest_sessionstart(session) -> None:
    from polisyos.ir.kernel import slots

    raw = subprocess.check_output(['git', '-C', str(ROOT), 'show', f'{SHA}:{PATH}'])
    assert Path(slots.__file__).read_bytes() == raw
    source = ast.parse(raw.decode())
    function = next(node for node in source.body if isinstance(node, ast.FunctionDef)
                    and node.name == 'build_slot_layout')
    assignment = next(node for node in ast.walk(function) if isinstance(node, ast.Assign)
                      and any(isinstance(target, ast.Subscript) for target in node.targets))
    assert ast.unparse(assignment.value) == 'spec.state_path'
    assignment.value = ast.parse("'tax_rate' if slot_id == 'government.balance' else spec.state_path", mode='eval').body
    module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    namespace = dict(vars(slots))
    exec(compile(module, slots.__file__, 'exec', flags=__future__.annotations.compiler_flag), namespace)
    canonical = slots.build_slot_layout
    identifier = id(canonical)
    original = hashlib.sha256(marshal.dumps(canonical.__code__)).hexdigest()
    canonical.__code__ = namespace['build_slot_layout'].__code__
    assert id(slots.build_slot_layout) == identifier
    print(json.dumps({'source_sha': SHA, 'provider': PATH, 'provider_sha256': hashlib.sha256(raw).hexdigest(),
                      'canonical_function': 'polisyos.ir.kernel.slots.build_slot_layout',
                      'function_identity_retained': True, 'types_slot_ids_and_registry_preserved': True,
                      'original_code_sha256': original,
                      'removed_code_sha256': hashlib.sha256(marshal.dumps(canonical.__code__)).hexdigest(),
                      'removed_property': 'government.balance current layout resolves tax_rate instead of government_balance',
                      'source_files_written': False}, sort_keys=True))

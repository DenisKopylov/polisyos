"""Read-only independent rate precision tests at the actual fiscal consumer seam."""
from __future__ import annotations

from decimal import Decimal
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import pickle
import platform
import subprocess
import sys
import types

import equinox as eqx
import jax
import jax.numpy as jnp
import numpy as np
import pytest

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes, to_canonical_bytes
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.contracts.foundry import (
    CompileRequest, ExecuteRequest, FoundryExecConfig, FoundryInputBindings,
    FoundryInputBindingsRef, ProgramGraph, SimulationResult, StateSnapshotRef,
)
from polisyos.core.registry import build_default_registry_bundle
from polisyos.foundry._registry import create_mechanism_from_spec
from polisyos.foundry.compile.api import compile as compile_foundry
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.execute.api import execute as execute_foundry
from polisyos.foundry.execute.executor import apply_patch_map, load_state_snapshot, put_state_snapshot
from polisyos.foundry.execute.mechanisms import fiscal
from polisyos.foundry.mechanisms import fiscal as facade
from polisyos.ir.governance.policy_spec import PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.kernel.merge_rules import DEFAULT_MERGE_RULE_REGISTRY
from polisyos.ir.kernel.slots import DEFAULT_SLOT_REGISTRY
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.trinity import TrinityBundle

ROOT = Path('/workspace/e02-F-economics-20261006')
PROVIDER = 'policy-engine/src/polisyos/foundry/execute/mechanisms/fiscal.py'


def git(*argv):
    return subprocess.check_output(['git', *argv], cwd=ROOT)


@pytest.fixture(scope='session', autouse=True)
def immutable_source():
    sha = os.environ['FISCAL_REVIEW_SHA']
    assert git('rev-parse', 'HEAD').decode().strip() == sha
    before = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
              for p in json.loads(Path(os.environ['FISCAL_REVIEW_PATHS']).read_text())}
    for p in before:
        assert (ROOT / p).read_bytes() == git('show', sha + ':' + p), p
    print('RUNTIME_ENV', json.dumps({'python': platform.python_version(), 'jax': jax.__version__,
        'jaxlib': importlib.metadata.version('jaxlib'), 'equinox': importlib.metadata.version('equinox'),
        'numpy': np.__version__, 'native_backend': jax.default_backend(),
        'initial_x64': jax.config.jax_enable_x64, 'artificial_cloud_quota': False}))
    yield
    assert git('rev-parse', 'HEAD').decode().strip() == sha
    assert before == {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in before}
    imported = []
    for name, module in sorted(sys.modules.items()):
        filename = getattr(module, '__file__', None)
        if not name.startswith('polisyos') or not filename or not filename.endswith('.py'):
            continue
        path = Path(filename).resolve()
        relative = str(path.relative_to(ROOT))
        raw = path.read_bytes()
        assert raw == git('show', sha + ':' + relative), name
        imported.append({'module': name, 'path': relative, 'bytes': len(raw),
                         'sha256': hashlib.sha256(raw).hexdigest()})
    print('SOURCE_GUARD', json.dumps({'source_sha': sha, 'tree': git('rev-parse', 'HEAD^{tree}').decode().strip(),
          'guard_paths': before, 'complete_imported_python_denominator': imported}, sort_keys=True))


def fixture(dtype, values=(1000.,) * 10, active=None):
    state = GlobalState.empty(n_agents=len(values), n_firms=2)
    income = jnp.asarray(values, dtype=dtype)
    agents = state.agents.replace(income=income, reported_income=income)
    if active is not None:
        agents = agents.replace(active=jnp.asarray(active, dtype=jnp.bool_))
    return state.replace(agents=agents, government_balance=jnp.asarray(17., dtype=dtype))


def apply(state, patch):
    return apply_patch_map(state, patch, slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY, default_node_id='precision')


def tensor_bytes(value):
    a = np.asarray(value)
    return {'dtype': str(a.dtype), 'shape': list(a.shape), 'bytes': a.tobytes().hex()}


def complete_outputs(state, patch, key):
    leaves, tree = jax.tree_util.tree_flatten(state)
    return {'state_tree': str(tree), 'state_leaves': [tensor_bytes(v) for v in leaves],
            'patch': {slot: [{k: tensor_bytes(v) for k, v in row.items()} for row in rows]
                      for slot, rows in patch.items()}, 'key': tensor_bytes(key)}


@pytest.mark.parametrize('kind', ['income_tax', 'tax_subsidy'])
@pytest.mark.parametrize('compiled', [False, True])
def test_registered_decimal_native_eager_jit_exact_consumer(kind, compiled):
    with jax.enable_x64(True):
        state = fixture(jnp.float64)
        mechanism = create_mechanism_from_spec(kind, {'rate': Decimal('0.10')}, 10, 2)
        emit = jax.jit(lambda s, k: mechanism.emit_patches(s, k)) if compiled else mechanism.emit_patches
        original_key = jax.random.PRNGKey(63)
        patch, key = emit(state, original_key)
        sign = -1 if kind == 'income_tax' else 1
        np.testing.assert_array_equal(patch['agents.income'][0]['delta'], np.full(10, sign * 100., dtype=np.float64))
        assert float(patch['government.balance'][0]['delta']) == -sign * 1000.
        np.testing.assert_array_equal(key, original_key)
        result = apply(state, patch)
        np.testing.assert_array_equal(result.agents.income, np.full(10, 1000. + sign * 100.))
        assert float(result.government_balance) == 17. - sign * 1000.
        assert mechanism.rate.shape == () and mechanism.rate.dtype == jnp.float64
        assert mechanism.__class__ is getattr(facade, mechanism.__class__.__name__)


@pytest.mark.parametrize('kind', ['income_tax', 'tax_subsidy'])
def test_decimal_policy_compiler_native_execution_and_fresh_process_state(kind, tmp_path):
    with jax.enable_x64(True):
        directory = tmp_path / 'cas'
        store = FileSystemCAS(directory)
        bundle = build_default_registry_bundle(store)
        policy = TrinityBundle(
            problem_frame=ProblemFrame(problem_id='precision', domain=ProblemDomain.FISCAL),
            policy_spec=PolicySpec(policy_id='precision', interventions=[{
                'intervention_id': 'precision', 'kind': kind,
                'target': {'kind': 'predicate', 'field': 'id', 'operator': '==', 'value': 'all'},
                'schedule': {'start_step': 0, 'duration_steps': 1},
                'params': {'rate': Decimal('0.10')},
            }]),
            model_spec=ModelSpec(model_id='precision', data_snapshot_ref='sha256:' + '0' * 64,
                registry_bundle_ref=str(bundle.bundle_ref.artifact_id)),
        )
        policy_ref = store.put_json(policy, PutOptions(kind='ir.trinity_bundle', media_type='application/json',
            schema=SchemaInfo(name='polisyos.ir.TrinityBundle', version=policy.schema_version)))
        compiled = compile_foundry(store, CompileRequest(input_kind='trinity', policy_ref=policy_ref,
            registry_bundle_ref=bundle.bundle_ref))
        assert compiled.ok
        graph_ref = next(row.ref for row in compiled.derived_refs if row.role == 'program_graph')
        graph = ProgramGraph.model_validate(from_canonical_bytes(store.get_bytes(graph_ref)))
        params = [from_canonical_bytes(store.get_bytes(node.params_ref))['params']
                  for node in graph.nodes if node.params_ref is not None]
        assert params == [{'rate': Decimal('0.10')}]
        assert all(type(row['rate']) is Decimal for row in params)
        wire_params = [json.loads(store.get_bytes(node.params_ref))['params']
                       for node in graph.nodes if node.params_ref is not None]
        assert wire_params == [json.loads(to_canonical_bytes({'rate': Decimal('0.10')}))]
        state = fixture(jnp.float64)
        original_snapshot = put_state_snapshot(store, state=state, step=0)
        state_ref = StateSnapshotRef(artifact_id=original_snapshot.artifact_id)
        data_ref = store.put_json(DataSnapshot(data_ref=state_ref),
            PutOptions(kind='fabric.data_snapshot', media_type='application/json'))
        binding = store.put_json(FoundryInputBindings(data_snapshot_ref=data_ref,
            registry_bundle_ref=bundle.bundle_ref, rules=[], bound_state_snapshot_ref=state_ref),
            PutOptions(kind='foundry.input_bindings', media_type='application/json'))
        request = ExecuteRequest(exec_plan_ref=compiled.exec_plan_ref,
            input_bindings_ref=FoundryInputBindingsRef(artifact_id=binding.artifact_id),
            registry_bundle_ref=bundle.bundle_ref, exec_config=FoundryExecConfig(seed=63))
        sign = -1 if kind == 'income_tax' else 1
        _, kernel_key = jax.random.split(jax.random.PRNGKey(63))
        native = create_mechanism_from_spec(kind, {'rate': Decimal('0.10')}, 10, 2)
        patch, key = native.emit_patches(state, kernel_key)
        expected = apply(state, patch)
        expected_bytes = complete_outputs(expected, patch, key)
        for repeated_store in (store, FileSystemCAS(directory)):
            executed = execute_foundry(repeated_store, request)
            assert executed.ok
            fresh = FileSystemCAS(directory)
            result = SimulationResult.model_validate(from_canonical_bytes(fresh.get_bytes(executed.simulation_result_ref)))
            restored = load_state_snapshot(fresh, snapshot_ref=result.state_snapshot_ref)
            actual = complete_outputs(restored, patch, key)
            assert actual == expected_bytes
            assert float(restored.government_balance) == 17. - sign * 1000.
        code = '''import json,sys
import jax
jax.config.update("jax_enable_x64", True)
import numpy as np
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.foundry import StateSnapshotRef
from polisyos.foundry.execute.executor import load_state_snapshot
state=load_state_snapshot(FileSystemCAS(sys.argv[1]),snapshot_ref=StateSnapshotRef.model_validate_json(sys.argv[2]))
leaves,tree=jax.tree_util.tree_flatten(state)
print(json.dumps({"tree":str(tree),"leaves":[{"dtype":str(np.asarray(v).dtype),"shape":list(np.asarray(v).shape),"bytes":np.asarray(v).tobytes().hex()} for v in leaves]}))
'''
        reader = subprocess.run([sys.executable, '-c', code, str(directory), result.state_snapshot_ref.model_dump_json()],
            capture_output=True, text=True, check=False)
        assert reader.returncode == 0, reader.stderr
        assert not reader.stderr
        decoded = json.loads(reader.stdout)
        assert decoded == {'tree': expected_bytes['state_tree'], 'leaves': expected_bytes['state_leaves']}
        print('COMPILER_CAS_FRESH_STATE', json.dumps({'kind': kind, 'decimal': '0.10',
            'wire_params': wire_params, 'decoded_rate_type': 'decimal.Decimal',
            'government_balance': float(restored.government_balance),
            'source_state_snapshot': str(state_ref.artifact_id), 'result_snapshot': str(result.state_snapshot_ref.artifact_id),
            'fresh_process_exit': reader.returncode, 'complete_state_sha256': hashlib.sha256(reader.stdout.encode()).hexdigest()}))


def test_default_float32_complete_whole_output_baseline_matrix():
    old = types.ModuleType('polisyos.foundry.execute.mechanisms._independent_fiscal_baseline')
    baseline = git('show', os.environ['FISCAL_REVIEW_BASE_SHA'] + ':' + PROVIDER)
    exec(compile(baseline, '<pinned-baseline-fiscal>', 'exec'), old.__dict__)
    cases = []
    with jax.enable_x64(False):
        for name in ('IncomeTax', 'TaxSubsidy'):
            for rate in (0., .1, .2, .3333333, .5, 1.):
                for compiled in (False, True):
                    state = fixture(jnp.float32, (80.25, 19.75, 100.125, 1000.5), (True, False, True, True))
                    target = jnp.asarray([True, True, False, True])
                    outputs = []
                    for module in (old, fiscal):
                        mechanism = getattr(module, name)(rate=rate, n_agents=4)
                        emit = lambda s, k: mechanism.emit_patches(s, k, target_mask=target)
                        if compiled:
                            emit = jax.jit(emit)
                        patch, key = emit(state, jax.random.PRNGKey(63))
                        outputs.append({'result': complete_outputs(apply(state, patch), patch, key),
                                        'public_rate': tensor_bytes(mechanism.rate)})
                    assert outputs[0] == outputs[1], (name, rate, compiled)
                    encoded = json.dumps(outputs[1], sort_keys=True).encode()
                    cases.append({'kind': name, 'rate': rate, 'jit': compiled,
                                  'complete_outputs_sha256': hashlib.sha256(encoded).hexdigest()})
    assert len(cases) == 24
    print('COMPLETE_DEFAULT32_BASELINE_EQUIVALENCE', json.dumps({'base': os.environ['FISCAL_REVIEW_BASE_SHA'],
        'provider_base_sha256': hashlib.sha256(baseline).hexdigest(), 'cases': cases, 'all_whole_output_bytes_equal': True}))


def test_actual_jax_minfloat32_lower_integer_baseline_dispositions():
    old = types.ModuleType('polisyos.foundry.execute.mechanisms._lower_fiscal_baseline')
    exec(compile(git('show', os.environ['FISCAL_REVIEW_BASE_SHA'] + ':' + PROVIDER),
                 '<pinned-lower-baseline-fiscal>', 'exec'), old.__dict__)
    rows = []
    for x64 in (False, True):
        with jax.enable_x64(x64):
            for dtype in (jnp.int32, jnp.int64, jnp.bool_, jnp.float16, jnp.bfloat16):
                for name in ('IncomeTax', 'TaxSubsidy'):
                    for compiled in (False, True):
                        state = fixture(dtype, (1.125, 3.25, 9.5, 17.75))
                        results = []
                        for module in (old, fiscal):
                            mechanism = getattr(module, name)(rate=.1, n_agents=4)
                            emit = (jax.jit(lambda s, k: mechanism.emit_patches(s, k))
                                    if compiled else mechanism.emit_patches)
                            patch, key = emit(state, jax.random.PRNGKey(63))
                            results.append((patch, key))
                        before, after = results[0][0], results[1][0]
                        old_delta = before['agents.income'][0]['delta']
                        new_delta = after['agents.income'][0]['delta']
                        old_total = before['government.balance'][0]['delta']
                        new_total = after['government.balance'][0]['delta']
                        np.testing.assert_array_equal(old_delta, new_delta)
                        np.testing.assert_array_equal(results[0][1], results[1][1])
                        # Test actual JAX promotion; no assumed NumPy promotion law.
                        expected_dtype = jnp.promote_types(state.agents.income.dtype, jnp.float32)
                        assert expected_dtype == jnp.float32
                        assert new_delta.dtype == new_total.dtype == expected_dtype
                        rows.append({'x64': x64, 'requested_income_dtype': str(np.dtype(dtype)),
                            'actual_income_dtype': str(state.agents.income.dtype), 'kind': name,
                            'jit': compiled, 'same_agent_delta_values': True,
                            'old_delta': tensor_bytes(old_delta), 'new_delta': tensor_bytes(new_delta),
                            'old_total': tensor_bytes(old_total), 'new_total': tensor_bytes(new_total),
                            'government_value_equal': float(old_total) == float(new_total),
                            'whole_patch_bytes_equal': tensor_bytes(old_delta) == tensor_bytes(new_delta)
                                and tensor_bytes(old_total) == tensor_bytes(new_total)})
    equal = sum(row['whole_patch_bytes_equal'] for row in rows)
    changed_total = sum(not row['government_value_equal'] for row in rows)
    assert len(rows) == 40 and equal == 30 and changed_total == 8
    assert all(row['x64'] and row['kind'] == 'TaxSubsidy'
               for row in rows if not row['whole_patch_bytes_equal'])
    print('MINFLOAT32_DISPOSITIONS', json.dumps({'base': os.environ['FISCAL_REVIEW_BASE_SHA'],
        'cases': 40, 'identical_agent_delta_values': 40, 'whole_patch_bytes_equal': equal,
        'changed_government_reduction_values': changed_total,
        'scope': 'Actual lower/integer behavior comparison; no integer-income policy or monetary rounding norm.',
        'rows': rows}, sort_keys=True))


@pytest.mark.parametrize('cls', [fiscal.IncomeTax, fiscal.TaxSubsidy])
def test_explicit32_precision_and_large64_fraction_follow_source_dtype(cls):
    with jax.enable_x64(True):
        state = fixture(jnp.float64, (2 ** 24 + 1., 10 ** 12))
        supplied = jnp.asarray(.1000000001, dtype=jnp.float32)
        m32 = cls(rate=supplied, n_agents=2)
        m64 = cls(rate=jnp.asarray(.1000000001, dtype=jnp.float64), n_agents=2)
        for mechanism, rate in ((m32, float(np.float32(.1000000001))), (m64, .1000000001)):
            patch, _ = jax.jit(lambda s, k: mechanism.emit_patches(s, k))(state, jax.random.PRNGKey(0))
            np.testing.assert_array_equal(np.abs(patch['agents.income'][0]['delta']), np.asarray(state.agents.income) * rate)
            assert mechanism.rate.dtype == (supplied.dtype if mechanism is m32 else jnp.float64)
        half = cls(rate=.5, n_agents=2).emit_patches(state, jax.random.PRNGKey(0))[0]
        assert float(abs(half['agents.income'][0]['delta'][0])) == 8388608.5


@pytest.mark.parametrize('cls', [fiscal.IncomeTax, fiscal.TaxSubsidy])
def test_live_rate_tree_grad_pickle_and_float32_receiving_state(cls):
    with jax.enable_x64(True):
        state64 = fixture(jnp.float64, (1000.,))
        state32 = fixture(jnp.float32, (1000.,))
        original = cls(rate=.1000000001, n_agents=1)
        changed = eqx.tree_at(lambda m: m.rate, original, jnp.asarray(.2000000001, dtype=jnp.float64))
        reader = pickle.loads(pickle.dumps(changed))
        assert reader.__class__ is cls
        sign = -1. if cls is fiscal.IncomeTax else 1.
        delta = reader.emit_patches(state64, jax.random.PRNGKey(0))[0]['agents.income'][0]['delta']
        assert float(delta[0]) == sign * 200.0000001
        grad = eqx.filter_grad(lambda m: jnp.sum(m.emit_patches(state64, jax.random.PRNGKey(0))[0]['agents.income'][0]['delta']))(reader)
        assert float(grad.rate) == sign * 1000.
        assert grad.rate.dtype == jnp.float64
        patches = jax.jit(lambda s, k: reader.emit_patches(s, k))(state32, jax.random.PRNGKey(0))[0]
        assert patches['agents.income'][0]['delta'].dtype == jnp.float32
        assert patches['government.balance'][0]['delta'].dtype == jnp.float32
        assert fiscal._validate_rate(.1000000001).dtype == jnp.float32

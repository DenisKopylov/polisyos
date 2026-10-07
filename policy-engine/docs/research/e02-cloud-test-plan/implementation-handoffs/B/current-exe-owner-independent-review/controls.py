import asyncio
import hashlib
import importlib.metadata
import json
import pathlib
import platform
import subprocess
import sys
import types

root = pathlib.Path('/workspace/e02-B-current-execution-state')
sha = '1bd1fd11b683bbade5411a71b02706ea206b149d'
out = pathlib.Path('/workspace/e02-B-current-runtime/_build/e02-current-runtime/exe-owner-controls-v2')
paths = [
    'policy-engine/src/polisyos/scientist/orchestration/engine/async_executor.py',
    'policy-engine/src/polisyos/core/artifacts/async_store.py',
    'policy-engine/tests/unit/scientist/orchestration/engine/test_workflow_deadline_custody.py',
]
identities = {}
for path in paths:
    raw = subprocess.check_output(['git', 'show', sha + ':' + path], cwd=root)
    assert (root / path).read_bytes() == raw
    identities[path] = hashlib.sha256(raw).hexdigest()
fixture = types.ModuleType('frozen_exe_fixture')
fixture.__file__ = str(root / paths[-1])
exec(compile(raw, sha + ':' + paths[-1], 'exec'), fixture.__dict__)
from polisyos.scientist.orchestration.engine.checkpoint import CASCheckpointHook, resolve_latest_checkpoint
from polisyos.scientist.orchestration.engine.state import ExperimentState

async def probe(case):
    store = fixture.FileSystemCAS(out / case / 'cas')
    ctx, node, workflow, executor = fixture._setup(store)
    entered = asyncio.Event()
    release = asyncio.Event()
    real = CASCheckpointHook(store=store, run_dir=ctx.run.trace_path.parent)
    history = []
    class Hook:
        async def on_node_complete_async(self, **kwargs):
            entered.set()
            await release.wait()
            result = await asyncio.to_thread(real.on_node_complete, **kwargs)
            history.append('checkpoint_completed')
            return result
    executor._checkpoint_hook = Hook()
    task = asyncio.create_task(executor.execute(workflow, ExperimentState(run_id='R_deadline', params={'seed': 7})))
    await asyncio.wait_for(entered.wait(), 2)
    before = fixture._events(ctx)
    if case == 'cooperative_cancel':
        task.cancel()
    else:
        release.set()
    try:
        result = await asyncio.wait_for(task, 3)
        termination = {'type': 'returned', 'status': result.report.status, 'state_params': result.state.params}
    except BaseException as exc:
        termination = {'type': type(exc).__name__, 'message': str(exc)}
    after = fixture._events(ctx)
    resolved = resolve_latest_checkpoint(fixture.FileSystemCAS(store.root), 'R_deadline')
    checkpoint = None
    if resolved is not None:
        head, dto = resolved
        checkpoint = {'verified': store.verify(head.checkpoint_ref).ok, 'completed_nodes': dto.metadata.completed_nodes,
                      'state_params': dto.state['params'], 'cache_entries_verified': [store.verify(ref).ok for ref in dto.metadata.cache_entry_refs]}
    events = [e['event'] for e in after[len(before):]]
    refs = ctx.run.run_manifest.outputs
    row = {'case': case, 'termination': termination, 'task_cancelling': task.cancelling(), 'provider_calls': node.calls,
           'history': history, 'events_after_boundary': events,
           'run_outputs': [ref.model_dump(mode='json') for ref in refs],
           'run_outputs_verified': [store.verify(ref).ok for ref in refs], 'checkpoint': checkpoint,
           'node_artifacts_verified': [store.verify(ref).ok for ref in node.refs]}
    if case == 'cooperative_cancel':
        row['pass'] = termination['type'] == 'CancelledError' and not events and not refs and checkpoint is None and not history and node.calls == 1
    else:
        row['pass'] = termination == {'type': 'returned', 'status': 'ok', 'state_params': {'seed': 7, 'result': 14}} and events == ['RUN_OUTPUT_ADDED', 'RUN_OUTPUT_ADDED', 'RUN_FINALIZED'] and len(refs) == 2 and all(row['run_outputs_verified']) and checkpoint is not None and checkpoint['verified'] and all(checkpoint['cache_entries_verified']) and node.calls == 1
    assert all(row['node_artifacts_verified'])
    return row

async def main():
    out.mkdir(parents=True, exist_ok=True)
    rows = [await probe(case) for case in ('cooperative_cancel', 'no_cancel')]
    imported = []
    for name, module in sorted(sys.modules.items()):
        filename = getattr(module, '__file__', None)
        if not name.startswith('polisyos') or not filename:
            continue
        path = pathlib.Path(filename).resolve()
        if path.suffix != '.py':
            continue
        relative = path.relative_to(root).as_posix()
        raw = path.read_bytes()
        git_raw = subprocess.check_output(['git', 'show', sha + ':' + relative], cwd=root)
        assert raw == git_raw, relative
        imported.append({'module': name, 'path': relative, 'sha256': hashlib.sha256(raw).hexdigest()})
    config = []
    for relative in ('policy-engine/uv.lock', 'policy-engine/pyproject.toml', 'policy-engine/tests/conftest.py'):
        raw = (root / relative).read_bytes()
        assert raw == subprocess.check_output(['git', 'show', sha + ':' + relative], cwd=root)
        config.append({'path': relative, 'sha256': hashlib.sha256(raw).hexdigest()})
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    assert head == sha
    packet = {'target_sha': sha, 'target_tree': subprocess.check_output(['git', 'rev-parse', sha + '^{tree}'], cwd=root, text=True).strip(),
              'source_identity': identities, 'python': sys.executable, 'python_version': sys.version,
              'platform': platform.platform(), 'sys_path': sys.path, 'config': config,
              'distributions': {name: importlib.metadata.version(name) for name in ('pytest', 'pytest-asyncio', 'pydantic')},
              'imported_polisyos_modules': imported, 'source_unchanged': all((root / p).read_bytes() == subprocess.check_output(['git', 'show', sha + ':' + p], cwd=root) for p in paths),
              'controls': rows, 'pass': all(r['pass'] for r in rows)}
    (out / 'receipt.json').write_text(json.dumps(packet, indent=2) + '\n')
    print(json.dumps(packet, indent=2))
    assert packet['pass']
asyncio.run(main())

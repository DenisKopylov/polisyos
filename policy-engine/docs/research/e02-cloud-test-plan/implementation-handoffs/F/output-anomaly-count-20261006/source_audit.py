"""Read exact Git source and separate own implementation from carried prerequisites."""
from pathlib import Path
import hashlib
import json
import subprocess

p = Path(__file__).parent
root = Path('/workspace/e02-F-fry-20261006')
base = '7185572917f7a3db5e93385a176cb611b35aff42'
old = 'e00dd3799cf2cdd14baf4b26e175ba1e848c3a6a'
candidate = '3c152d3640f1aa9d46f4e3020cda364e25f6ef84'
def git(*args):
    return subprocess.check_output(['git', *args], cwd=root)
def ref(sha, path):
    b = git('show', sha + ':' + path)
    return {'path': path, 'git_sha': sha,
            'git_blob': git('rev-parse', sha + ':' + path).decode().strip(),
            'sha256': hashlib.sha256(b).hexdigest(), 'size_bytes': len(b)}
changed = git('diff', '--name-only', base, candidate).decode().splitlines()
read_paths = changed + [
    'policy-engine/src/polisyos/foundry/methods/components/io.py',
    'policy-engine/src/polisyos/foundry/methods/lifecycle/observability.py',
    'policy-engine/tests/unit/foundry/methods/backends/test_dispatch_output_contract.py',
    'policy-engine/tests/unit/foundry/methods/test_output_monitor.py',
    'policy-engine/tests/unit/foundry/methods/backends/test_backends.py']
refs = [ref(candidate, path) for path in read_paths]
prior_equivalence = []
for path in ['policy-engine/src/polisyos/foundry/methods/backends/dispatch.py',
             'policy-engine/src/polisyos/foundry/methods/lifecycle/output_monitor.py',
             'policy-engine/tests/unit/foundry/methods/backends/test_dispatch_output_contract.py']:
    a = ref(old, path)
    b = ref(base, path)
    assert a['git_blob'] == b['git_blob']
    prior_equivalence.append({'path': path, 'old_sha': old, 'slice_base_sha': base,
        'equal_git_blob': a['git_blob'], 'sha256': a['sha256'], 'size_bytes': a['size_bytes']})
G = '127dc7ab8365d29eb656fe32c0c894f6cc971286'
Gpath = 'policy-engine/docs/research/e02-cloud-test-plan/integration/reviews/F-delta-owner-actions-2026-10-06.md'
record = {'source_sha': candidate,
    'source_tree': git('rev-parse', candidate + '^{tree}').decode().strip(),
    'slice_base_sha': base, 'slice_base_tree': git('rev-parse', base + '^{tree}').decode().strip(),
    'old_reproduction_sha': old, 'changed_paths': changed,
    'exact_defining_source_refs': refs, 'prepatch_code_byte_equivalence': prior_equivalence,
    'G_checkpoint_owner_input': ref(G, Gpath),
    'own_source_overlap': {'canonical_runtime_files': 2, 'mandatory_implementation_companions': 3,
        'excluded': 'No common.py, Core, IR/schema, generated inventory, authority/value owner or worker source edits.'},
    'assembled_dependency_limit': 'Base718 is carried as an existing append-only dependency ancestor, not own source implementation. G should integrate commit3c152 against accepted prerequisites; do not treat cumulative branch diff as owned changes.'}
(p / 'source-audit.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps({'source_sha': candidate, 'changed_paths': changed, 'source_refs': len(refs),
                  'old_base_equal_blobs': len(prior_equivalence)}))

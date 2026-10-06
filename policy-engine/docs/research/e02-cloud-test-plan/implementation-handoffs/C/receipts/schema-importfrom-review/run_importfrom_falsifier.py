from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

candidate = Path('/Users/deniskopylov/.codex/worktrees/e02-c-schema-20261006/polisyos')
scratch = Path('/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C2/raw/schema-review/final-delta')
corpus = scratch / 'corpus-v3'
if corpus.exists():
    raise SystemExit(f'refusing to replace existing corpus: {corpus}')
corpus.mkdir(parents=True)
files = {
    'src/polisyos/data_forge/kernel/schemas/__init__.py': '',
    'src/polisyos/data_forge/kernel/schemas/codegen.py': 'class GeneratedSchemaModule: ...\n',
    'src/polisyos/data_forge/kernel/schemas/subpackage/__init__.py': '',
    'src/polisyos/data_forge/kernel/schemas/subpackage/caller.py': '',
    'src/polisyos/foundry/domain/__init__.py': '',
    'src/polisyos/foundry/domain/schema.py': 'class RegionProfile: ...\n',
}
for relative, content in files.items():
    path = corpus / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')

def run(name: str) -> tuple[dict[str, object], Path, int]:
    executable = '/Users/deniskopylov/polisyos/policy-engine/.venv/bin/python'
    script = str(candidate / 'policy-engine/tools/quality/validation/schema_fqn_census.py')
    argv = [executable, script, '--repo-root', str(corpus)]
    env = os.environ.copy()
    env['PYTHONPATH'] = f"{candidate / 'policy-engine'}:{candidate / 'policy-engine/src'}"
    completed = subprocess.run(argv, cwd=corpus, env=env, capture_output=True, text=True, check=False)
    out = scratch / f'{name}.stdout.json'
    err = scratch / f'{name}.stderr.txt'
    out.write_text(completed.stdout, encoding='utf-8')
    err.write_text(completed.stderr, encoding='utf-8')
    receipt = json.loads(completed.stdout)
    target_imports = [
        hit for hit in receipt.get('matches', [])
        if hit.get('evidence_kind') in {
            'absolute_import', 'relative_import',
            'absolute_import_child_candidate', 'relative_import_child_candidate',
        }
    ]
    summary = {
        'argv': argv,
        'cwd': str(corpus),
        'PYTHONPATH': env['PYTHONPATH'],
        'returncode': completed.returncode,
        'stdout_path': str(out),
        'stdout_sha256': hashlib.sha256(out.read_bytes()).hexdigest(),
        'stderr_path': str(err),
        'stderr_sha256': hashlib.sha256(err.read_bytes()).hexdigest(),
        'target_import_count': len(target_imports),
        'target_imports': target_imports,
        'git_head': subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=corpus, capture_output=True, text=True, check=True).stdout.strip(),
        'working_source_hashes': {
            relative: hashlib.sha256((corpus / relative).read_bytes()).hexdigest()
            for relative in files
        },
    }
    return summary, out, completed.returncode

subprocess.run(['git', 'init', '-q'], cwd=corpus, check=True)
subprocess.run(['git', 'config', 'user.name', 'Schema Falsifier'], cwd=corpus, check=True)
subprocess.run(['git', 'config', 'user.email', 'schema-falsifier@example.invalid'], cwd=corpus, check=True)
subprocess.run(['git', 'add', '.'], cwd=corpus, check=True)
subprocess.run(['git', 'commit', '-qm', 'fixture baseline'], cwd=corpus, check=True)

baseline, _, baseline_code = run('baseline-empty')

relative_init = (
    'from .codegen import GeneratedSchemaModule\n'
    'from . import codegen as relative_codegen\n'
    'from polisyos.data_forge.kernel.schemas import codegen as absolute_codegen\n'
)
(corpus / 'src/polisyos/data_forge/kernel/schemas/__init__.py').write_text(relative_init, encoding='utf-8')
(corpus / 'src/polisyos/data_forge/kernel/schemas/subpackage/caller.py').write_text(
    'from .. import codegen as parent_codegen\n'
    'from ..codegen import GeneratedSchemaModule as parent_symbol\n'
    'from polisyos.data_forge.kernel.schemas.codegen import GeneratedSchemaModule as absolute_symbol\n',
    encoding='utf-8',
)
(corpus / 'src/polisyos/foundry/domain/__init__.py').write_text(
    'from . import schema as schema_module\n', encoding='utf-8'
)
positive, _, positive_code = run('relative-init-child-direct-positive')

for relative, content in {
    'src/polisyos/data_forge/kernel/schemas/__init__.py': 'from math import sqrt\n',
    'src/polisyos/data_forge/kernel/schemas/subpackage/caller.py': 'from math import floor\n',
    'src/polisyos/foundry/domain/__init__.py': 'from math import ceil\n',
}.items():
    (corpus / relative).write_text(content, encoding='utf-8')
removal, _, removal_code = run('removal-control')

metadata = {
    'candidate_commit': subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=candidate, capture_output=True, text=True, check=True).stdout.strip(),
    'candidate_tree': subprocess.run(['git', 'rev-parse', 'HEAD^{tree}'], cwd=candidate, capture_output=True, text=True, check=True).stdout.strip(),
    'candidate_branch': subprocess.run(['git', 'branch', '--show-current'], cwd=candidate, capture_output=True, text=True, check=True).stdout.strip(),
    'tool_git_blob': subprocess.run(['git', 'rev-parse', 'HEAD:policy-engine/tools/quality/validation/schema_fqn_census.py'], cwd=candidate, capture_output=True, text=True, check=True).stdout.strip(),
    'tool_sha256': hashlib.sha256((candidate / 'policy-engine/tools/quality/validation/schema_fqn_census.py').read_bytes()).hexdigest(),
    'pytest_delta_git_blob': subprocess.run(['git', 'rev-parse', 'HEAD:policy-engine/tests/unit/remediation/test_dfk_01.py'], cwd=candidate, capture_output=True, text=True, check=True).stdout.strip(),
    'corpus': str(corpus),
    'python_version': subprocess.run(['/Users/deniskopylov/polisyos/policy-engine/.venv/bin/python', '--version'], capture_output=True, text=True, check=True).stdout.strip(),
    'corpus_files': files,
    'variants': {
        'baseline_empty': baseline,
        'relative_init_child_direct_positive': positive,
        'removal_control': removal,
    },
    'assertions': {
        'baseline_returncode_zero': baseline_code == 0,
        'baseline_no_import_hits': baseline['target_import_count'] == 0,
        'positive_returncode_zero': positive_code == 0,
        'positive_has_import_hits': positive['target_import_count'] > 0,
        'relative_direct_and_child_forms': [
            (hit['path'], hit['line'], hit['evidence_kind'], hit['target'], hit['matched_value'])
            for hit in positive['target_imports']
        ],
        'removal_returncode_zero': removal_code == 0,
        'removal_no_import_hits': removal['target_import_count'] == 0,
    },
}
metadata_path = scratch / 'probe-metadata.json'
metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + '\n', encoding='utf-8')
print(json.dumps({
    'metadata': str(metadata_path),
    'metadata_sha256': hashlib.sha256(metadata_path.read_bytes()).hexdigest(),
    'assertions': metadata['assertions'],
}, indent=2, sort_keys=True))
if not all([
    metadata['assertions']['baseline_returncode_zero'],
    metadata['assertions']['baseline_no_import_hits'],
    metadata['assertions']['positive_returncode_zero'],
    metadata['assertions']['positive_has_import_hits'],
    metadata['assertions']['removal_returncode_zero'],
    metadata['assertions']['removal_no_import_hits'],
]):
    raise SystemExit(1)

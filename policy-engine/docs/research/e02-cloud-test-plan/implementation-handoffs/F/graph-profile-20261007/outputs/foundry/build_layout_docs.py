"""Build the current maintained state page with its actual MkDocs Python handler."""
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path('/workspace/e02-F-fry-20261006')
PRODUCT = ROOT / 'policy-engine'
SCRATCH = Path(__file__).resolve().parent
PYTHON = Path('/tmp/e02-F-continuation-20261006/foundry/docs-venv/bin/python')
SOURCE = '6beacc8b42dacabff214901919203323f07d1fef'


def bound(path):
    raw = path.read_bytes()
    return {'path': str(path), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def guard():
    assert subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD']).decode().strip() == SOURCE
    assert not subprocess.check_output(['git', '-C', str(ROOT), 'status', '--porcelain'])


class Contents(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        self.ids.update(value for key, value in attrs if key == 'id')


guard()
inputs = [bound(PRODUCT / name) for name in (
    'mkdocs.yml', 'architecture/tooling/mkdocs/generated.yml',
    'docs/reference/foundry/state.md', 'src/polisyos/foundry/methods/README.md',
    'src/polisyos/foundry/methods/compiler/README.md', 'src/polisyos/ir/kernel/slots.py',
    'src/polisyos/foundry/methods/layout.py', 'src/polisyos/foundry/methods/compiler/layout.py',
    'architecture/public_surface/contract.toml')]
config = SCRATCH / 'layout-docs.yml'
config.write_text(f'''INHERIT: {PRODUCT / 'mkdocs.yml'}
docs_dir: {PRODUCT / 'docs'}
site_dir: {SCRATCH / 'layout-docs-site'}
nav:
  - Foundry State: reference/foundry/state.md
exclude_docs: |
  **
  !reference/foundry/state.md
not_in_nav: ""
''')
argv = [str(PYTHON), '-m', 'mkdocs', 'build', '--config-file', str(config), '--clean']
env = os.environ.copy()
env['PYTHONPATH'] = str(PRODUCT / 'src') + ':' + str(PRODUCT / 'tools')
env['PYTHONDONTWRITEBYTECODE'] = '1'
started = time.monotonic()
run = subprocess.run(argv, cwd=PRODUCT, env=env, capture_output=True)
for name, data in [('stdout', run.stdout), ('stderr', run.stderr)]:
    (SCRATCH / ('layout-docs.' + name + '.txt')).write_bytes(data)
output = SCRATCH / 'layout-docs-site/reference/foundry/state/index.html'
parser = Contents()
if output.exists():
    parser.feed(output.read_text())
anchors = ['polisyos.ir.kernel.slots.' + symbol for symbol in
           ('SlotLayout', 'SlotFamily', 'SlotFamilyManifest', 'build_slot_layout', 'build_slot_family_manifest')]
rendered = [anchor for anchor in anchors if anchor in parser.ids]
environment_argv = [str(PYTHON), '-c', 'import sys,importlib.metadata,json;print(json.dumps({"Python":sys.version,"packages":{n:importlib.metadata.version(n) for n in ["mkdocs","mkdocs-material","mkdocstrings","mkdocstrings-python"]}}))']
environment = subprocess.run(environment_argv, capture_output=True, check=True)
guard()
assert inputs == [bound(Path(x['path'])) for x in inputs]
report = {'schema': 'e02.F.layout.docs_build.v1', 'source_sha': SOURCE,
          'source_tree': subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD^{tree}']).decode().strip(),
          'argv': argv, 'cwd': str(PRODUCT), 'environment_argv': environment_argv,
          'environment': {**json.loads(environment.stdout), 'PYTHONPATH': env['PYTHONPATH'],
              'PYTHONDONTWRITEBYTECODE': '1', 'shared_environment_mutated': False, 'compute_quota': False},
          'input_closure': 'Full maintained state page and native API directives; repository actual theme/plugins/Markdown options inherited, only page/navigation scope narrowed.',
          'source_inputs': inputs, 'config': bound(config), 'exit_code': run.returncode,
          'wall_seconds': time.monotonic() - started,
          'outcome': 'PASS' if run.returncode == 0 and rendered == anchors else 'FAIL' if run.returncode == 1 else 'ERROR',
          'stdout': bound(SCRATCH / 'layout-docs.stdout.txt'), 'stderr': bound(SCRATCH / 'layout-docs.stderr.txt'),
          'complete_native_layout_anchors': rendered, 'html': bound(output) if output.exists() else None,
          'limits': 'Scoped actual docs build; full strict docs/project quality not inferred. All original warnings retained; no plugin/backend suppression or fake module.'}
(SCRATCH / 'layout-docs.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
if report['outcome'] != 'PASS':
    raise SystemExit(1)

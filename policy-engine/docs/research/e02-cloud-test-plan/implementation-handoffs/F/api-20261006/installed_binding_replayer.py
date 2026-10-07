"""Reconcile all installed product bytes and test retired filename behavior."""
from pathlib import Path
import hashlib
import importlib.util
import json
import zipfile

SCRATCH = Path('/workspace/e02-F-20261006-receipts/api')
SOURCE = '729d137279b7d6334230045e420255762fe55f08'
WHEEL = SCRATCH / 'candidate-dist/policy_engine-0.1.0-py3-none-any.whl'
bindings = []
with zipfile.ZipFile(WHEEL) as archive:
    names = [name for name in archive.namelist() if name.startswith('polisyos/') and not name.endswith('/')]
    for kind in ('wheel', 'sdist'):
        site = SCRATCH / f'{kind}-env/lib/python3.14/site-packages'
        for name in names:
            assert (site / name).read_bytes() == archive.read(name), (kind, name)
        bindings.append({
            'installed_site': str(site), 'all_product_files_reconciled': len(names),
            'source_sha': SOURCE,
            'direct_url': json.loads((site / 'policy_engine-0.1.0.dist-info/direct_url.json').read_text()),
        })
    controls = []
    for suffix in ('causal_engine', 'id_engine', 'interference'):
        address = 'polisyos.foundry.methods.catalog.causal.' + suffix
        spec = importlib.util.find_spec(address)
        assert spec is not None and spec.origin and spec.submodule_search_locations
        origin = Path(spec.origin)
        assert origin.name == '__init__.py'
        old = origin.parent.with_suffix('.py')
        assert not old.exists()
        assert 'polisyos/foundry/methods/catalog/causal/' + suffix + '.py' not in archive.namelist()
        old_spec = importlib.util.spec_from_file_location('e02_retired_filename', old)
        assert old_spec is not None and old_spec.loader is not None
        module = importlib.util.module_from_spec(old_spec)
        try:
            old_spec.loader.exec_module(module)
        except FileNotFoundError:
            pass
        else:
            raise AssertionError(('retired filename unexpectedly loaded', str(old)))
        controls.append({'package': address, 'origin': str(origin), 'retired_sibling_filename': str(old),
                         'exact_filename_loader': 'FileNotFoundError expected', 'ordinary_package_import': 'PASS'})
proof = {
    'source_sha': SOURCE, 'wheel_sha256': hashlib.sha256(WHEEL.read_bytes()).hexdigest(),
    'installed_product_binding': bindings, 'GRF01_LA007_LA019_companions': controls,
    'limits': ['Direct filename callers to retired empty shims must migrate; no arbitrary external loader census or primary GRF closure claimed.',
               'Installed product bytes verified; shared third-party dependencies not independently rebuilt.',
               'Family certificate witnessed in installed tests; state activation pending FRY owner.'],
}
(SCRATCH / 'installed-bindings.json').write_text(json.dumps(proof, indent=2) + '\n')
print(json.dumps({'product_files_per_install': len(names), 'installations': len(bindings), 'package_controls': len(controls)}))

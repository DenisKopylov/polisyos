"""Read-only census: family certificates do not supply native state operations."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys

raw = io.StringIO()
with contextlib.redirect_stdout(raw):
    from polisyos.foundry._registry import MECHANISM_REGISTRY, get_mechanism_class, MissingRuntimeMechanismSupportError
    from polisyos.foundry.methods.catalog.mechanism.families import mechanism_family_catalog
    rows = []
    for family in mechanism_family_catalog():
        name = family['mechanism_id']
        try:
            value = get_mechanism_class(name)
            rows.append(dict(family_id=name, runtime_class=str(value), runtime_state_operation='not_measured'))
        except MissingRuntimeMechanismSupportError as exc:
            rows.append(dict(family_id=name, exception=type(exc).__name__, message=str(exc), runtime_state_operation='unavailable'))
    runtime_ids = list(MECHANISM_REGISTRY)
paths=['src/polisyos/foundry/_registry.py','src/polisyos/foundry/methods/catalog/mechanism/families.py','src/polisyos/scientist/validation/verification/ic/service.py']
print(json.dumps(dict(scope='family-to-runtime admission refusal only; not economic semantics',
    source_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
    source_files=[dict(path=p,sha256=hashlib.sha256(Path(p).read_bytes()).hexdigest(),bytes=Path(p).stat().st_size) for p in paths],
    python=sys.version, interpreter=sys.executable, runtime_ids=runtime_ids, families=rows,
    native_stdout=raw.getvalue(), finding_state='limited', outcome='PASS' if len(rows)==4 and all(x.get('runtime_state_operation')=='unavailable' for x in rows) else 'FAIL',
    missing_input='Owner-ratified family certificate-to-state operation mapping; native IC certificate evidence remains separate'),indent=2))

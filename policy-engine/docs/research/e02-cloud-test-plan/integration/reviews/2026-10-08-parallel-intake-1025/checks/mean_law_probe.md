# Isolated G reproduction harness

The executable original and execution command remain in ignored custody.
This is the exact diagnostic recipe, not a new product module.

```python
import hashlib
import json
import subprocess
import sys
from pathlib import Path

root, checkout, out = map(Path, sys.argv[1:])
sha = '1b8c9e1c84d9f2e86d4b0900bf5aa54515487747'
sys.path.insert(0, str(checkout / 'policy-engine/src'))
from polisyos.core.artifacts.ir_adapter import build_ir_artifact_store
from polisyos.foundry.uncertainty.config import PropagationConfig
from polisyos.foundry.uncertainty.monte_carlo import MonteCarloPropagator
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily, IntervalSemantics, PosteriorSamplesCarrier,
    PropagationMethod, UncertaintyEnvelope, UncertaintySource,
    load_uncertainty_envelope, persist_uncertainty_envelope,
)

law = UncertaintyEnvelope(
    point_estimate=0.0, confidence_interval=(-1.0, 1.0),
    distribution_family=DistributionFamily.BOOTSTRAP,
    source=UncertaintySource.CALIBRATION,
    propagation_method=PropagationMethod.NONE,
    interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
    distribution_payload=PosteriorSamplesCarrier(
        samples=(-1.0, 1.0), weights=(0.9, 0.1), sample_axis='draw'),
    gate_eligible=False,
)
result = MonteCarloPropagator(PropagationConfig(mc_n_samples=100)).propagate(
    lambda x=0.0: {'y': x}, {'x': 0.0}, {'x': law}, ['y'])[0]
ref = persist_uncertainty_envelope(build_ir_artifact_store(out / 'CAS'), result.envelope)
fresh = load_uncertainty_envelope(build_ir_artifact_store(out / 'CAS'), ref)
diagnostic = fresh.metadata['mean_estimator_error']
origins = []
for name, module in sorted(sys.modules.items()):
    file = getattr(module, '__file__', None)
    if not name.startswith('polisyos') or not file:
        continue
    p = Path(file).resolve()
    relative = p.relative_to(checkout).as_posix()
    content = p.read_bytes()
    actual = hashlib.sha1(b'blob ' + str(len(content)).encode() + b'\0' + content).hexdigest()
    expected = subprocess.check_output(['git', 'rev-parse', sha + ':' + relative], cwd=root, text=True).strip()
    assert actual == expected, (relative, actual, expected)
    origins.append({'module': name, 'path': relative, 'blob': actual})
observation = {'source': sha, 'real_input_distribution_family': law.distribution_family.value,
               'real_input_carrier': type(law.distribution_payload).__name__,
               'real_input_weights': law.distribution_payload.weights,
               'persisted_envelope_ref': ref.model_dump(mode='json'),
               'fresh_diagnostic': diagnostic, 'gate_eligible': fresh.gate_eligible,
               'loaded_polisyos_module_denominator': len(origins), 'mismatches': 0}
(out / 'observation.json').write_text(json.dumps(observation, indent=2) + '\n')
(out / 'origins.json').write_text(json.dumps(origins, indent=2) + '\n')
print(json.dumps(observation))
assert diagnostic['status'] == 'unavailable' and diagnostic['standard_error'] is None
assert diagnostic['sampling_law'] != 'implemented_product_of_typed_normal_fits', 'weighted empirical replay is mislabeled as typed-Normal law'
```

from __future__ import annotations
import hashlib
import json
import math
import os
from pathlib import Path
import sys
from fractions import Fraction

from polisyos.core.artifacts.ir_adapter import build_ir_artifact_store
from polisyos.ir.analytics.uncertainty import PosteriorSamplesCarrier, load_uncertainty_envelope
from polisyos.ir.registry.refs import UncertaintyEnvelopeRef

here = Path(__file__).resolve().parent
refs = json.loads((here / 'child-inputs.json').read_text())
rows = []
for item in refs:
    ref = UncertaintyEnvelopeRef.model_validate(item['reference'])
    envelope = load_uncertainty_envelope(build_ir_artifact_store(Path(item['cas_root'])), ref)
    payload = envelope.distribution_payload
    xs = list(payload.samples) if isinstance(payload, PosteriorSamplesCarrier) else []
    digest = hashlib.sha256(json.dumps(xs, allow_nan=False, separators=(',', ':')).encode()).hexdigest()
    assert digest == item['sample_sha256']
    d = envelope.metadata['mean_estimator_error']
    assert d == item['diagnostic']
    assert envelope.gate_eligible is False and d['gate_eligible'] is False
    # The available supported-profile cases independently recompute exact arithmetic.
    if d['status'] == 'conditional_estimate' and not item['name'].startswith('removed_guard_'):
        vals = [Fraction.from_float(float(x)) for x in xs]
        mu = sum(vals) / len(vals)
        exact = sum((x - mu) ** 2 for x in vals) / (len(vals) * (len(vals) - 1))
        assert math.isclose(d['standard_error'], math.sqrt(float(exact)), rel_tol=1e-12)
    rows.append({'name': item['name'], 'artifact_id': ref.artifact_id, 'sample_sha256': digest,
                 'mean_estimator_error': d, 'gate_eligible': envelope.gate_eligible})
print(json.dumps({'pid': os.getpid(), 'python': sys.version, 'reader': load_uncertainty_envelope.__module__,
                  'ref_count': len(rows), 'records': rows, 'status': 'PASS independent child-process fresh CAS reader'},
                 sort_keys=True, indent=2, allow_nan=False))

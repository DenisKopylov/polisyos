"""Measure the actual safety semantic resolver; authenticate is not adjudicate."""

import inspect
import json

from polisyos.runtime.http.services.control import run_lifecycle as control
from polisyos.runtime.quality import evaluation_safety as safety


registry = control._ControlEvaluationSafetyVerifierRegistry()
print(json.dumps({
    "owner": "polisyos.runtime.quality.evaluation_safety.verify_evaluation_safety_requirements",
    "owner_source": inspect.getsource(safety.verify_evaluation_safety_requirements),
    "production_registry_source": inspect.getsource(type(registry)),
    "live_resolutions": {token: registry.resolve(token) for token in ("risk.bounded@1.0.0", "consent.approval@1.0.0", "sandbox.containment@1.0.0", "stop.rules@1.0.0", "harm.monitoring@1.0.0", "novel.contract@1.0.0")},
    "probe_token_authority": "These are synthetic query tokens; no canonical contract denominator or acceptance requirement is invented.",
    "mode_basis_resolver_source": inspect.getsource(control._ControlEvaluationSafetyAuthorityResolver),
    "appointment_resolver_source": inspect.getsource(control._ControlEvaluationSafetyAppointmentResolver),
    "attempt_certificate_purpose_annotation": str(safety.EvalSafetyCertificate.model_fields["authoritative_for"].annotation),
}, indent=2))

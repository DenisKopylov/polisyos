"""Cycle-free registry for deployment security composition attestations."""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from types import MappingProxyType
from typing import TYPE_CHECKING, Literal
from weakref import WeakKeyDictionary

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

DeploymentSecurityComponentName = Literal[
    "identity_provider",
    "cell_registry",
    "opa_client",
    "step_up_verifier",
    "principal_grants",
    "human_decision_custody",
]
_COMPONENT_NAMES = frozenset(
    {
        "identity_provider",
        "cell_registry",
        "opa_client",
        "step_up_verifier",
        "principal_grants",
        "human_decision_custody",
    }
)


class DeploymentSecurityAttestationError(RuntimeError):
    """The installed deployment authority no longer matches its factory proof."""


@dataclass(frozen=True, slots=True)
class _RegisteredDeploymentSecurityAttestation:
    validator: Callable[[object], None]
    components: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class _RegisteredDeploymentSecurityInstallation:
    runtime: object
    container: object


_ATTESTATIONS: WeakKeyDictionary[
    object,
    _RegisteredDeploymentSecurityAttestation,
] = WeakKeyDictionary()
_INSTALLATIONS: WeakKeyDictionary[
    object,
    _RegisteredDeploymentSecurityInstallation,
] = WeakKeyDictionary()
_ATTESTATION_LOCK = RLock()


def register_deployment_security_attestation(
    runtime: object,
    *,
    validator: Callable[[object], None],
    components: Mapping[str, object],
) -> None:
    """Register one factory identity with its validator and exact components."""
    if not callable(validator):
        raise TypeError("deployment security attestation validator must be callable")
    if set(components) != _COMPONENT_NAMES or any(
        component is None for component in components.values()
    ):
        raise TypeError("deployment security attestation components are incomplete")
    attestation = _RegisteredDeploymentSecurityAttestation(
        validator=validator,
        components=MappingProxyType(dict(components)),
    )
    try:
        with _ATTESTATION_LOCK:
            _ATTESTATIONS[runtime] = attestation
    except TypeError as exc:
        raise TypeError("deployment security factory identity is not attestable") from exc


def require_registered_deployment_security(value: object) -> object:
    """Return one intact registered factory identity or raise a typed denial."""
    try:
        with _ATTESTATION_LOCK:
            attestation = _ATTESTATIONS.get(value)
    except TypeError as exc:
        raise DeploymentSecurityAttestationError(
            "deployment security factory attestation is invalid"
        ) from exc
    if attestation is None:
        raise DeploymentSecurityAttestationError(
            "deployment security must be a registered factory identity"
        )
    try:
        attestation.validator(value)
    except Exception as exc:  # Every verifier failure becomes a typed denial.
        raise DeploymentSecurityAttestationError(
            "deployment security factory attestation is invalid"
        ) from exc
    return value


def register_deployment_security_installation(
    app: object,
    *,
    runtime: object,
    container: object,
) -> None:
    """Bind one application identity to its exact deployment composition."""
    require_registered_deployment_security(runtime)
    state = getattr(app, "state", None)
    if (
        state is None
        or getattr(state, "runtime_deployment_security", None) is not runtime
        or getattr(state, "runtime_container", None) is not container
    ):
        raise TypeError("deployment security installation is incomplete")
    installation = _RegisteredDeploymentSecurityInstallation(
        runtime=runtime,
        container=container,
    )
    try:
        with _ATTESTATION_LOCK:
            _INSTALLATIONS[app] = installation
    except TypeError as exc:
        raise TypeError("deployment security application is not attestable") from exc


def require_installed_deployment_security(subject: object) -> object | None:
    """Validate an installed bundle and all application security aliases."""
    app = getattr(subject, "app", subject)
    state = getattr(app, "state", None)
    runtime_value = getattr(state, "runtime_deployment_security", None)
    try:
        with _ATTESTATION_LOCK:
            installation = _INSTALLATIONS.get(app)
    except TypeError as exc:
        if runtime_value is None:
            return None
        raise DeploymentSecurityAttestationError(
            "deployment security application identity is invalid"
        ) from exc
    if installation is None:
        if runtime_value is None:
            return None
        raise DeploymentSecurityAttestationError(
            "deployment security bundle is not registered to this application"
        )
    if (
        runtime_value is not installation.runtime
        or getattr(state, "runtime_container", None) is not installation.container
    ):
        raise DeploymentSecurityAttestationError(
            "deployment security installation identity changed"
        )
    runtime = require_registered_deployment_security(installation.runtime)
    with _ATTESTATION_LOCK:
        attestation = _ATTESTATIONS.get(runtime)
    if attestation is None:  # pragma: no cover - guarded above under the same process
        raise DeploymentSecurityAttestationError(
            "deployment security factory attestation disappeared"
        )
    components = attestation.components
    container = getattr(state, "runtime_container", None)
    runtime_security = getattr(container, "runtime_security", None)
    if (
        getattr(state, "runtime_security", None) is not runtime_security
        or getattr(state, "runtime_deployment_principal_grants", None)
        is not components["principal_grants"]
        or getattr(runtime_security, "identity_provider", None)
        is not components["identity_provider"]
        or getattr(runtime_security, "cell_registry", None) is not components["cell_registry"]
        or getattr(runtime_security, "opa_client", None) is not components["opa_client"]
        or getattr(runtime_security, "step_up_verifier", None) is not components["step_up_verifier"]
        or getattr(runtime_security, "authz_enforce", None) is not True
        or getattr(runtime_security, "authz_shadow_mode", None) is not False
        or getattr(runtime_security, "allow_fixture_identity", None) is not False
        or getattr(runtime_security, "step_up_replay_store", None) is not None
        or getattr(runtime_security, "human_decision_custody", None)
        is not components["human_decision_custody"]
    ):
        raise DeploymentSecurityAttestationError("installed deployment security aliases changed")
    return runtime


def require_attested_deployment_component(
    subject: object,
    *,
    component_name: DeploymentSecurityComponentName,
    candidate: object,
) -> object:
    """Re-attest and return one exact component immediately before consumption."""
    runtime = require_installed_deployment_security(subject)
    if runtime is None:
        return candidate
    with _ATTESTATION_LOCK:
        attestation = _ATTESTATIONS.get(runtime)
    if attestation is None:  # pragma: no cover - guarded above under the same process
        raise DeploymentSecurityAttestationError(
            "deployment security factory attestation disappeared"
        )
    expected = attestation.components[component_name]
    if candidate is not expected:
        raise DeploymentSecurityAttestationError(
            f"installed deployment {component_name} alias changed"
        )
    return expected


def require_attested_deployment_setting(
    subject: object,
    *,
    setting_name: str,
    candidate: object,
    expected: object,
) -> None:
    """Re-attest and compare one immutable deployment perimeter setting."""
    runtime = require_installed_deployment_security(subject)
    if runtime is None:
        return
    if type(candidate) is not type(expected) or candidate != expected:
        raise DeploymentSecurityAttestationError(
            f"installed deployment {setting_name} setting changed"
        )


__all__ = [
    "DeploymentSecurityAttestationError",
    "DeploymentSecurityComponentName",
    "register_deployment_security_attestation",
    "register_deployment_security_installation",
    "require_attested_deployment_component",
    "require_attested_deployment_setting",
    "require_installed_deployment_security",
    "require_registered_deployment_security",
]

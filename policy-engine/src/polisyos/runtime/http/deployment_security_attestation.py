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


@dataclass(frozen=True, slots=True)
class _RegisteredProductionApprovalResolverInstallation:
    runtime: object | None
    container: object
    service: object
    custody: object
    verifier_epoch: str
    resolver: object


_ATTESTATIONS: WeakKeyDictionary[
    object,
    _RegisteredDeploymentSecurityAttestation,
] = WeakKeyDictionary()
_INSTALLATIONS: WeakKeyDictionary[
    object,
    _RegisteredDeploymentSecurityInstallation,
] = WeakKeyDictionary()
_PRODUCTION_APPROVAL_RESOLVERS: WeakKeyDictionary[
    object,
    _RegisteredProductionApprovalResolverInstallation,
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


def require_registered_deployment_component(
    runtime: object,
    *,
    component_name: DeploymentSecurityComponentName,
    candidate: object,
) -> object:
    """Content-bind one resolver issuer input to a registered factory bundle."""

    registered = require_registered_deployment_security(runtime)
    with _ATTESTATION_LOCK:
        attestation = _ATTESTATIONS.get(registered)
    if attestation is None:  # pragma: no cover - guarded by the call above
        raise DeploymentSecurityAttestationError(
            "deployment security factory attestation disappeared"
        )
    if attestation.components[component_name] is not candidate:
        raise DeploymentSecurityAttestationError(
            f"registered deployment {component_name} identity changed"
        )
    return candidate


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


def _register_production_approval_resolver_installation(
    app: object,
    *,
    container: object,
    service: object,
    custody: object,
    verifier_epoch: str,
    resolver: object,
) -> None:
    """Bind one application to exactly one production-approval resolver."""

    state = getattr(app, "state", None)
    if (
        state is None
        or getattr(state, "runtime_container", None) is not container
        or getattr(container, "human_decision_service", None) is not service
        or getattr(container, "production_approval_resolver", None) is not resolver
        or getattr(service, "custody", None) is not custody
        or not isinstance(verifier_epoch, str)
        or not verifier_epoch
        or getattr(resolver, "issuer_epoch", None) != verifier_epoch
    ):
        raise TypeError("production approval resolver installation is incomplete")
    runtime = require_installed_deployment_security(app)
    if runtime is None:
        if getattr(service, "available", True) is not False:
            raise TypeError("available production approval resolver requires deployment security")
    else:
        require_registered_deployment_component(
            runtime,
            component_name="human_decision_custody",
            candidate=custody,
        )
    installation = _RegisteredProductionApprovalResolverInstallation(
        runtime=runtime,
        container=container,
        service=service,
        custody=custody,
        verifier_epoch=verifier_epoch,
        resolver=resolver,
    )
    try:
        with _ATTESTATION_LOCK:
            existing = _PRODUCTION_APPROVAL_RESOLVERS.get(app)
            if existing is not None and not (
                existing.runtime is installation.runtime
                and existing.container is installation.container
                and existing.service is installation.service
                and existing.custody is installation.custody
                and existing.verifier_epoch == installation.verifier_epoch
                and existing.resolver is installation.resolver
            ):
                raise DeploymentSecurityAttestationError(
                    "production approval resolver is already installed"
                )
            _PRODUCTION_APPROVAL_RESOLVERS[app] = installation
    except TypeError as exc:
        raise TypeError("production approval resolver application is not attestable") from exc


def require_installed_production_approval_resolver(
    subject: object,
    *,
    candidate: object,
) -> object:
    """Return only the resolver registered to the exact application/container."""

    app = getattr(subject, "app", subject)
    state = getattr(app, "state", None)
    try:
        with _ATTESTATION_LOCK:
            installation = _PRODUCTION_APPROVAL_RESOLVERS.get(app)
    except TypeError as exc:
        raise DeploymentSecurityAttestationError(
            "production approval resolver application identity is invalid"
        ) from exc
    if installation is None:
        raise DeploymentSecurityAttestationError(
            "production approval resolver is not registered to this application"
        )
    container = getattr(state, "runtime_container", None)
    service = getattr(container, "human_decision_service", None)
    custody = getattr(service, "custody", None)
    if (
        container is not installation.container
        or service is not installation.service
        or custody is not installation.custody
        or getattr(container, "production_approval_resolver", None) is not installation.resolver
        or getattr(state, "_production_approval_resolver", None) is not installation.resolver
        or candidate is not installation.resolver
        or getattr(candidate, "issuer_epoch", None) != installation.verifier_epoch
    ):
        raise DeploymentSecurityAttestationError(
            "production approval resolver installation identity changed"
        )
    runtime = require_installed_deployment_security(app)
    if runtime is not installation.runtime:
        raise DeploymentSecurityAttestationError(
            "production approval resolver deployment identity changed"
        )
    if runtime is None:
        if getattr(service, "available", True) is not False:
            raise DeploymentSecurityAttestationError(
                "available production approval resolver lost deployment security"
            )
    else:
        require_registered_deployment_component(
            runtime,
            component_name="human_decision_custody",
            candidate=custody,
        )
    return candidate


def _require_registered_production_approval_resolver_instance(candidate: object) -> object:
    """Re-attest the application that owns one exact resolver instance.

    Operational consumers do not necessarily have an HTTP request or container
    handle.  Resolving the registered application here prevents a
    composition-root-shaped but uninstalled resolver from authorizing a sibling
    compiler or quality consumer.
    """

    with _ATTESTATION_LOCK:
        matches = [
            app
            for app, installation in _PRODUCTION_APPROVAL_RESOLVERS.items()
            if installation.resolver is candidate
        ]
    if len(matches) != 1:
        raise DeploymentSecurityAttestationError(
            "production approval resolver instance is not uniquely registered"
        )
    return require_installed_production_approval_resolver(
        matches[0],
        candidate=candidate,
    )


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
    "require_installed_production_approval_resolver",
    "require_registered_deployment_component",
    "require_registered_deployment_security",
]

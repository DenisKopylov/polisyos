"""Parameter codecs bridging policy dictionaries and vectorized search params."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


class ParameterCodec(Protocol):
    """Encode/decode between policy candidates and strategy parameter dictionaries."""

    def encode(self, candidate: dict[str, Any]) -> dict[str, Any]:
        """Extract searchable parameters from policy candidate."""

    def decode(
        self,
        params: dict[str, Any],
        *,
        context: dict[str, Any] | None = None,
        template: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Materialize full policy candidate from strategy parameter dictionary."""


def _get_path(payload: dict[str, Any], dotted: str) -> Any:
    current: Any = payload
    for segment in dotted.split("."):
        if not isinstance(current, dict):
            return None
        if segment not in current:
            return None
        current = current[segment]
    return current


def _set_path(payload: dict[str, Any], dotted: str, value: Any) -> None:
    current = payload
    segments = dotted.split(".")
    for segment in segments[:-1]:
        next_value = current.get(segment)
        if not isinstance(next_value, dict):
            next_value = {}
            current[segment] = next_value
        current = next_value
    current[segments[-1]] = value


@dataclass(slots=True)
class ScalarParameterCodec:
    """
    Path-based codec for scalar strategy parameters.

    - If `parameter_paths` is empty, encode/decode uses top-level keys unchanged.
    - If `parameter_paths` provided: maps strategy-param-name -> dotted path in candidate dict.
    """

    parameter_paths: dict[str, str] = field(default_factory=dict)
    default_semantic: dict[str, Any] = field(default_factory=lambda: {"interventions": []})

    def encode(self, candidate: dict[str, Any]) -> dict[str, Any]:
        if not self.parameter_paths:
            return {
                key: value
                for key, value in candidate.items()
                if key != "semantic"
            }

        params: dict[str, Any] = {}
        for param_name, path in self.parameter_paths.items():
            params[param_name] = _get_path(candidate, path)
        return params

    def decode(
        self,
        params: dict[str, Any],
        *,
        context: dict[str, Any] | None = None,
        template: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        output: dict[str, Any] = {}
        if template:
            output.update(template)
            if "semantic" in template and isinstance(template["semantic"], dict):
                output["semantic"] = dict(template["semantic"])
        if "semantic" not in output:
            output["semantic"] = dict(self.default_semantic)

        if not self.parameter_paths:
            for key, value in params.items():
                output[key] = value
            return output

        for param_name, value in params.items():
            path = self.parameter_paths.get(param_name, param_name)
            _set_path(output, path, value)
        return output


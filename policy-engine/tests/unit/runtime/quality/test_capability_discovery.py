"""Behavioral RED witness for the DS10 discovery posture composer."""

from __future__ import annotations


def test_capability_discovery_postures_use_three_independent_producers() -> None:
    """Require discovery, execution, and authority to have distinct producers."""
    calls: list[str] = []

    class Producer:
        def __init__(self, posture: str) -> None:
            self.posture = posture

        def __call__(self) -> dict[str, str]:
            calls.append(self.posture)
            return {"posture": self.posture, "producer": f"{self.posture}-producer"}

    from polisyos.runtime.quality.capability_discovery import compose_capability_postures

    result = compose_capability_postures(
        discovery=Producer("discoverable"),
        execution=Producer("executable"),
        authority=Producer("admitted_authority"),
    )
    assert calls == ["discoverable", "executable", "admitted_authority"]
    assert result == {
        "discovery": {"posture": "discoverable", "producer": "discoverable-producer"},
        "execution": {"posture": "executable", "producer": "executable-producer"},
        "authority": {
            "posture": "admitted_authority",
            "producer": "admitted_authority-producer",
        },
    }

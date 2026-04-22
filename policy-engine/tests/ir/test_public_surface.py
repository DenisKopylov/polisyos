from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import polisyos.ir as ir
import polisyos.ir.analytics as analytics
import polisyos.ir.kernel as kernel
import polisyos.ir.world as world
from polisyos.ir.public_surface import PACKAGE_FACADE_EXPORTS, PACKAGE_FACADE_IMPORT_POLICY


def _subprocess_json(script: str) -> list[str]:
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_package_facade_manifest_matches_declared_exports() -> None:
    assert analytics.__all__ == sorted(PACKAGE_FACADE_EXPORTS["analytics"])
    assert kernel.__all__ == sorted(PACKAGE_FACADE_EXPORTS["kernel"])
    assert world.__all__ == sorted(PACKAGE_FACADE_EXPORTS["world"])


def test_package_facades_import_without_eager_submodules() -> None:
    expected_empty = []
    assert _subprocess_json(
        "import json, sys; import polisyos.ir.analytics; "
        "print(json.dumps(sorted("
        "name for name in sys.modules "
        "if name.startswith('polisyos.ir.analytics.')"
        ")))"
    ) == expected_empty
    assert _subprocess_json(
        "import json, sys; import polisyos.ir.kernel; "
        "print(json.dumps(sorted("
        "name for name in sys.modules "
        "if name.startswith('polisyos.ir.kernel.')"
        ")))"
    ) == expected_empty
    assert _subprocess_json(
        "import json, sys; import polisyos.ir.world; "
        "print(json.dumps(sorted("
        "name for name in sys.modules "
        "if name.startswith('polisyos.ir.world.')"
        ")))"
    ) == expected_empty


def test_lazy_export_access_imports_only_requested_module_group() -> None:
    loaded = _subprocess_json(
        "import json, sys; import polisyos.ir.analytics as analytics; "
        "_ = analytics.HTEResult; "
        "print(json.dumps(sorted("
        "name for name in sys.modules "
        "if name.startswith('polisyos.ir.analytics.')"
        ")))"
    )

    assert "polisyos.ir.analytics.hte" in loaded
    assert "polisyos.ir.analytics.strategic" not in loaded
    assert "polisyos.ir.analytics.alignment_certification" not in loaded
    assert len(loaded) < 20


def test_analytics_facade_exports_performative_loop_contracts() -> None:
    assert "PerformativeLoopCertificate" in analytics.__all__
    assert "PerformativeShiftSummary" in analytics.__all__
    assert analytics.PerformativeLoopCertificate.__name__ == "PerformativeLoopCertificate"
    assert analytics.PerformativeShiftSummary.__name__ == "PerformativeShiftSummary"


def test_analytics_facade_exports_privacy_transportability_contracts() -> None:
    assert "DPUtilityManifest" in analytics.__all__
    assert "PrivacyAwareTransportCertificate" in analytics.__all__
    assert "PrivacyObservedMode" in analytics.__all__
    assert analytics.PrivacyAwareTransportCertificate.__name__ == (
        "PrivacyAwareTransportCertificate"
    )


def test_interference_and_maup_contracts_are_exported_from_ir_surfaces() -> None:
    analytics_exports = {
        "ExposureMappingType",
        "InteractionComplex",
        "InteractionComplexRef",
        "InterferenceCertificate",
        "InterferenceCertificateRef",
        "InterferenceEffectDecomposition",
        "InterferenceMethod",
        "MAUPInvarianceCertificate",
        "MAUPInvarianceCertificateRef",
        "MAUPPartitionCheck",
        "NetworkInterferenceReport",
        "SpatialResult",
    }
    assert analytics_exports <= set(analytics.__all__)
    assert analytics.MAUPInvarianceCertificate.__name__ == "MAUPInvarianceCertificate"
    assert analytics.SpatialResult.__name__ == "SpatialResult"
    assert analytics.InterferenceCertificateRef.__name__ == "InterferenceCertificateRef"
    assert analytics.InteractionComplexRef.__name__ == "InteractionComplexRef"
    assert analytics.MAUPInvarianceCertificateRef.__name__ == "MAUPInvarianceCertificateRef"
    assert analytics_exports <= set(ir.__all__)
    assert ir.NetworkInterferenceReport.__name__ == "NetworkInterferenceReport"


def test_network_generative_block_bridge_contracts_are_exported_from_ir_surfaces() -> None:
    bridge_exports = {
        "BlockSupportReport",
        "CausalBlockBridge",
        "CausalBlockBridgeRef",
    }
    assert bridge_exports <= set(analytics.__all__)
    assert analytics.BlockSupportReport.__name__ == "BlockSupportReport"
    assert analytics.CausalBlockBridge.__name__ == "CausalBlockBridge"
    assert analytics.CausalBlockBridgeRef.__name__ == "CausalBlockBridgeRef"
    assert bridge_exports <= set(ir.__all__)
    assert ir.CausalBlockBridge.__name__ == "CausalBlockBridge"
    assert ir.CausalBlockBridgeRef.__name__ == "CausalBlockBridgeRef"


def test_public_surface_docs_counts_match_manifest() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    docs_page = repo_root / "docs" / "reference" / "ir" / "public-surface.md"
    docs_text = docs_page.read_text(encoding="utf-8")

    for package, exports in PACKAGE_FACADE_EXPORTS.items():
        policy = PACKAGE_FACADE_IMPORT_POLICY[package]
        expected_row = f"| `polisyos.ir.{package}` | {len(exports)} | {policy} |"
        assert expected_row in docs_text


def test_ir_index_links_public_surface_reference() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    index_page = repo_root / "docs" / "reference" / "ir" / "index.md"
    assert "[Public Surface](public-surface.md)" in index_page.read_text(encoding="utf-8")

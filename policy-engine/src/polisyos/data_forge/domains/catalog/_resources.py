"""Resolve the four curated catalog defaults in source and unpacked installations.

The YAML files under ``data/dataset_catalog`` remain the only authored source.
Hatch projects their exact bytes into the installed package's private resource
directory. This module does not locate raw observations or mutable batch outputs.
"""

from pathlib import Path
from typing import Literal, get_args

CatalogDefaultResource = Literal[
    "seed_variable_alignments.yaml",
    "proxy_metric_alignments.yaml",
    "wvs_indicator_registry.yaml",
    "metrics_map.yaml",
]


def catalog_default_resource_path(name: CatalogDefaultResource) -> Path:
    """Return a durable filesystem path for one curated catalog default.

    Args:
        name: One of the four checked-in catalog YAML resource filenames.

    Returns:
        The original checked-in path in a source checkout, or the package-private
        path in an unpacked installation. A missing file stays missing so existing
        required-read and optional-fallback policies decide how to handle it.

    Raises:
        ValueError: The filename is outside the finite curated resource profile.

    Notes:
        The source profile requires the exact ``src/polisyos/.../catalog`` anchor
        and its project manifest. There is no CWD or neighbouring repository
        search, and no temporary ``as_file`` context whose returned path expires.
    """
    if name not in get_args(CatalogDefaultResource):
        raise ValueError(f"unsupported curated catalog resource: {name!r}")

    catalog_dir = Path(__file__).resolve().parent
    product_root = catalog_dir.parents[4]
    source_anchor = product_root / "src" / "polisyos" / "data_forge" / "domains" / "catalog"
    if catalog_dir == source_anchor and (product_root / "pyproject.toml").is_file():
        return product_root / "data" / "dataset_catalog" / name
    return catalog_dir / "_resources" / name

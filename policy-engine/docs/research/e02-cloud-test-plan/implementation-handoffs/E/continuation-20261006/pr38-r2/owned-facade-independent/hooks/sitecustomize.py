"""Scratch-only read-only module overlays; imported by author subprocesses."""
from __future__ import annotations
import importlib.abc
import importlib.util
import json
import os
import sys
from pathlib import Path

metadata = os.environ.get("E02_WELFARE_OVERLAY_METADATA")
if metadata:
    spec_data = json.loads(Path(metadata).read_text())
    class Overlay(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            row = spec_data.get(fullname)
            if row is None:
                return None
            package_path = [row["package_path"]] if row.get("package_path") else None
            return importlib.util.spec_from_file_location(fullname, row["source"], submodule_search_locations=package_path)
    sys.meta_path.insert(0, Overlay())

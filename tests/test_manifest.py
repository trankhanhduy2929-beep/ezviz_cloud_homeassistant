"""Validate packaging isolation from Home Assistant's built-in EZVIZ integration."""

from __future__ import annotations

import json
from pathlib import Path

INTEGRATION_ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "ezviz_cloud"


def test_manifest_does_not_install_global_pyezvizapi() -> None:
    """The custom integration must not replace the built-in integration's package."""
    manifest = json.loads((INTEGRATION_ROOT / "manifest.json").read_text())

    assert not any(
        requirement.partition("==")[0].lower() == "pyezvizapi"
        for requirement in manifest["requirements"]
    )
    assert (INTEGRATION_ROOT / "vendor" / "pyezvizapi" / "client.py").is_file()
    assert (INTEGRATION_ROOT / "vendor" / "pyezvizapi" / "LICENSE").is_file()


def test_source_does_not_import_global_pyezvizapi() -> None:
    """Every integration module must use the isolated vendored namespace."""
    offenders = [
        path.name
        for path in INTEGRATION_ROOT.glob("*.py")
        if "from pyezvizapi" in path.read_text() or "import pyezvizapi" in path.read_text()
    ]

    assert offenders == []

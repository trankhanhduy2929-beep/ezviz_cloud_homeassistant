"""Load integration helper modules without importing Home Assistant lifecycle code."""

from __future__ import annotations

import importlib
from pathlib import Path
import sys
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
COMPONENT_ROOT = ROOT / "custom_components" / "ezviz_cloud"


def _ensure_package() -> None:
    """Register namespace packages while intentionally skipping __init__.py."""
    if "custom_components" not in sys.modules:
        custom_components = ModuleType("custom_components")
        custom_components.__path__ = [str(ROOT / "custom_components")]
        sys.modules["custom_components"] = custom_components

    if "custom_components.ezviz_cloud" not in sys.modules:
        component = ModuleType("custom_components.ezviz_cloud")
        component.__path__ = [str(COMPONENT_ROOT)]
        sys.modules["custom_components.ezviz_cloud"] = component


def load_auth() -> ModuleType:
    """Return the auth helper module."""
    _ensure_package()
    return importlib.import_module("custom_components.ezviz_cloud.auth")


def load_camera_config() -> ModuleType:
    """Return camera_config with a minimal Home Assistant constants stub."""
    try:
        importlib.import_module("homeassistant.const")
    except ModuleNotFoundError:
        homeassistant = ModuleType("homeassistant")
        homeassistant.__path__ = []
        constants = ModuleType("homeassistant.const")
        constants.CONF_PASSWORD = "password"
        constants.CONF_USERNAME = "username"
        sys.modules["homeassistant"] = homeassistant
        sys.modules["homeassistant.const"] = constants

    _ensure_package()
    return importlib.import_module("custom_components.ezviz_cloud.camera_config")


def load_push() -> ModuleType:
    """Return the MQTT push normalization helper module."""
    _ensure_package()
    return importlib.import_module("custom_components.ezviz_cloud.push")

"""Regression tests for resilient EZVIZ MQTT decoding."""

from __future__ import annotations

import importlib
import json
import sys
from types import ModuleType
from typing import Any

import pytest
import requests

from .module_loader import _ensure_package


def _install_paho_stub() -> None:
    """Install a minimal paho stub for environments without the dependency."""
    paho = ModuleType("paho")
    mqtt_pkg = ModuleType("paho.mqtt")
    client_mod = ModuleType("paho.mqtt.client")

    class _Client:
        pass

    client_mod.Client = _Client  # type: ignore[attr-defined]
    client_mod.MQTTv311 = 4  # type: ignore[attr-defined]
    mqtt_pkg.client = client_mod  # type: ignore[attr-defined]
    paho.mqtt = mqtt_pkg  # type: ignore[attr-defined]
    sys.modules.setdefault("paho", paho)
    sys.modules.setdefault("paho.mqtt", mqtt_pkg)
    sys.modules.setdefault("paho.mqtt.client", client_mod)


def load_vendor_mqtt() -> ModuleType:
    """Load the vendored MQTT module with a paho stub when unavailable."""
    _ensure_package()
    if "paho.mqtt.client" not in sys.modules:
        try:
            importlib.import_module("paho.mqtt.client")
        except ModuleNotFoundError:
            _install_paho_stub()

    return importlib.import_module(
        "custom_components.ezviz_cloud.vendor.pyezvizapi.mqtt"
    )


mqtt_module = load_vendor_mqtt()

TOKEN = {
    "username": "ezviz-user",
    "session_id": "session-id",
    "service_urls": {"pushAddr": "push.example.test"},
}


class OfflineMQTTClient(mqtt_module.MQTTClient):
    """MQTT client that records a server stop without network calls."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.stop_called = False

    def stop(self) -> None:
        self.stop_called = True


class DummyMessage:
    """Minimal paho message object."""

    def __init__(self, payload: bytes) -> None:
        self.payload = payload


def _client(**kwargs: Any) -> OfflineMQTTClient:
    return OfflineMQTTClient(TOKEN, requests.Session(), **kwargs)


def test_malformed_json_drops_only_that_message() -> None:
    """A malformed payload must not stop the push listener or thread."""
    client = _client()

    with pytest.raises(mqtt_module.PyEzvizError, match="Unable to decode MQTT message"):
        client.decode_mqtt_message(b"not-json")

    assert client.stop_called is False


@pytest.mark.parametrize(
    "payload",
    [
        b"not-json",
        b"null",
        b"[]",
        b"\xff\xfe\xfd",
    ],
)
def test_invalid_payloads_are_counted_and_ignored(payload: bytes) -> None:
    """Invalid broker payloads must not terminate paho's network thread."""
    seen: list[dict[str, Any]] = []
    client = _client(on_message_callback=seen.append)

    client._on_message(None, None, DummyMessage(payload))  # type: ignore[arg-type]

    assert seen == []
    assert client.stats["received"] == 1
    assert client.stats["invalid"] == 1
    assert client.stop_called is False


def test_message_without_serial_is_forwarded_for_logging() -> None:
    """Vendor callback still receives decoded ext-less push variants."""
    seen: list[dict[str, Any]] = []
    client = _client(on_message_callback=seen.append)
    payload = {"alert": "Device notice", "ext": {"alert_type_code": 999}}

    client._on_message(None, None, DummyMessage(json.dumps(payload).encode()))  # type: ignore[arg-type]

    assert seen == [payload]
    assert client.stats["decoded"] == 1
    assert client.stats["missing_serial"] == 1
    assert client.stats["delivered"] == 1

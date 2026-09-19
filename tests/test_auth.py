"""Unit tests for token and camera-key bootstrap helpers."""

from __future__ import annotations

import importlib
import json
from types import SimpleNamespace
from typing import Any

import pytest
import requests

from .module_loader import load_auth

auth = load_auth()


def test_auth_uses_vendored_pyezvizapi_namespace() -> None:
    """The custom integration must not bind to Home Assistant's global client."""
    assert auth.EzvizClient.__module__ == (
        "custom_components.ezviz_cloud.vendor.pyezvizapi.client"
    )
    assert auth.api_endpoints.__name__ == (
        "custom_components.ezviz_cloud.vendor.pyezvizapi.api_endpoints"
    )


def test_auth_import_supports_missing_batch_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    """Older pyezvizapi builds must not prevent the config flow from loading."""
    with monkeypatch.context() as patch_context:
        patch_context.delattr(
            auth.api_endpoints,
            "API_ENDPOINT_DEVICES_ENCRYPTKEY_BATCH",
            raising=False,
        )

        reloaded_auth = importlib.reload(auth)

        assert (
            reloaded_auth.API_ENDPOINT_DEVICES_ENCRYPTKEY_BATCH
            == "/v3/devices/encryptkey/query/batch/risk"
        )

    importlib.reload(auth)


class FakeLoginClient:
    """Small client exercising the response-hook based area-id capture."""

    def __init__(self) -> None:
        self._session = requests.Session()

    def login(self, sms_code: str | int | None = None) -> dict[str, str]:
        response = requests.Response()
        response.status_code = 200
        response._content = json.dumps({"loginArea": {"areaId": "7"}}).encode()
        for hook in self._session.hooks["response"]:
            hook(response)
        return {
            "session_id": "session-token",
            "rf_session_id": "refresh-token",
            "username": "internal-user",
            "api_url": "api.example.test",
        }


def test_login_captures_area_id_and_removes_hook() -> None:
    """Login should retain APK areaId without leaving a persistent hook."""
    client = FakeLoginClient()

    result = auth.login_with_area_id(client, "001234")

    assert result.area_id == 7
    assert result.token["session_id"] == "session-token"
    assert client._session.hooks["response"] == []


def test_parse_batch_keys_filters_unknown_and_empty_values() -> None:
    """Only requested serials with successful non-empty keys are returned."""
    payload = {
        "meta": {"code": 200},
        "responseDetail": {
            "CAM-A": {"code": 0, "encryptKey": "key-a"},
            "CAM-B": {"code": 0, "encryptKey": ""},
            "CAM-X": {"code": 0, "encryptKey": "not-requested"},
        },
    }

    assert auth._parse_batch_keys(payload, {"CAM-A", "CAM-B"}) == {"CAM-A": "key-a"}


@pytest.mark.parametrize("code", [20002, 120002])
def test_parse_batch_keys_classifies_otp(code: int) -> None:
    """Both observed EZVIZ risk codes should enter one OTP step."""
    with pytest.raises(auth.EzvizKeyOtpRequired):
        auth._parse_batch_keys({"meta": {"code": code}}, {"CAM-A"})


def test_batch_error_does_not_echo_sensitive_payload() -> None:
    """Safe exceptions must not contain keys, tokens, or serials."""
    payload = {
        "meta": {"code": 500},
        "responseDetail": {
            "PRIVATE-SERIAL": {"encryptKey": "PRIVATE-KEY"},
        },
    }

    with pytest.raises(auth.EzvizKeySetupError) as raised:
        auth._parse_batch_keys(payload, {"PRIVATE-SERIAL"})

    message = str(raised.value)
    assert "PRIVATE-SERIAL" not in message
    assert "PRIVATE-KEY" not in message


def test_no_code_requests_device_encryption_otp_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """A batch risk response should request one common code, not one per camera."""
    request_calls: list[tuple[Any, str]] = []

    def raise_otp(*_: Any, **__: Any) -> dict[str, str]:
        raise auth.EzvizKeyOtpRequired

    monkeypatch.setattr(auth, "_batch_device_keys", raise_otp)
    monkeypatch.setattr(
        auth,
        "_request_device_key_otp",
        lambda client, account: request_calls.append((client, account)) or "EMAIL",
    )
    client = SimpleNamespace()

    with pytest.raises(auth.EzvizKeyOtpRequired) as raised:
        auth.fetch_device_encryption_keys(
            client,
            area_id=7,
            account="account@example.test",
            serials=["CAM-A", "CAM-B"],
        )

    assert raised.value.contact_type == "EMAIL"
    assert request_calls == [(client, "account@example.test")]


def test_one_code_is_applied_to_all_cameras(monkeypatch: pytest.MonkeyPatch) -> None:
    """The user-entered OTP should be reused automatically for every camera."""
    calls: list[tuple[str, str | None]] = []

    def fake_individual(client: object, serial: str, verification_code: str | None) -> str | None:
        calls.append((serial, verification_code))
        return None if serial == "CAM-B" else f"key-{serial}"

    monkeypatch.setattr(auth, "_individual_device_key", fake_individual)

    result = auth.fetch_device_encryption_keys(
        SimpleNamespace(),
        area_id=7,
        account="account@example.test",
        serials=["CAM-B", "CAM-A"],
        verification_code="654321",
    )

    assert result == {"CAM-A": "key-CAM-A"}
    assert calls == [("CAM-A", "654321"), ("CAM-B", "654321")]

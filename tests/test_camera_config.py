"""Unit tests for automatic local RTSP camera options."""

from __future__ import annotations

from .module_loader import load_camera_config

camera_config = load_camera_config()
constants = __import__("custom_components.ezviz_cloud.const", fromlist=["unused"])


def test_merge_camera_options_builds_ready_local_rtsp_defaults() -> None:
    """A discovered local camera and fetched key should be stream-ready."""
    cameras = {
        "CAM-A": {
            "local_ip": "192.0.2.20",
            "local_rtsp_port": 554,
        }
    }

    result = camera_config.merge_camera_options(cameras, {"CAM-A": "camera-key"})

    options = result["CAM-A"]
    assert options[constants.CONF_ENC_KEY] == "camera-key"
    assert options[constants.CONF_KEY_STATUS] == constants.KEY_STATUS_READY
    assert options[constants.CONF_FFMPEG_ARGUMENTS] == "/Streaming/Channels/102"
    assert options[constants.CONF_STREAM_MODE] == constants.STREAM_MODE_LOCAL_RTSP


def test_merge_camera_options_preserves_manual_choices() -> None:
    """Automatic refresh must not overwrite stream mode, path, or old key."""
    cameras = {
        "CAM-A": {
            "local_ip": "192.0.2.20",
            "local_rtsp_port": "554",
        }
    }
    existing = {
        "CAM-A": {
            constants.CONF_ENC_KEY: "old-key",
            constants.CONF_FFMPEG_ARGUMENTS: "/Streaming/Channels/101",
            constants.CONF_STREAM_MODE: constants.STREAM_MODE_DISABLED,
        }
    }

    result = camera_config.merge_camera_options(cameras, {}, existing)["CAM-A"]

    assert result[constants.CONF_ENC_KEY] == "old-key"
    assert result[constants.CONF_FFMPEG_ARGUMENTS] == "/Streaming/Channels/101"
    assert result[constants.CONF_STREAM_MODE] == constants.STREAM_MODE_DISABLED


def test_merge_camera_options_does_not_treat_fetch_sentinel_as_a_key() -> None:
    """Legacy fetch markers must become a missing key, never an RTSP password."""
    cameras = {
        "CAM-A": {
            "local_ip": "192.0.2.20",
            "local_rtsp_port": 554,
        }
    }
    existing = {
        "CAM-A": {
            constants.CONF_ENC_KEY: constants.DEFAULT_FETCH_MY_KEY,
            "password": constants.DEFAULT_FETCH_MY_KEY,
        }
    }

    result = camera_config.merge_camera_options(cameras, {}, existing)["CAM-A"]

    assert result[constants.CONF_ENC_KEY] == ""
    assert result["password"] == ""
    assert result[constants.CONF_KEY_STATUS] == constants.KEY_STATUS_MISSING


def test_missing_stream_keys_only_reports_enabled_local_cameras() -> None:
    """Repair issues should exclude disabled or non-local devices."""
    cameras = {
        "CAM-A": {"local_ip": "192.0.2.20", "local_rtsp_port": 554},
        "CAM-B": {"local_ip": "", "local_rtsp_port": 554},
        "CAM-C": {"local_ip": "192.0.2.30", "local_rtsp_port": 554},
    }
    options = {
        "CAM-A": {},
        "CAM-B": {},
        "CAM-C": {constants.CONF_STREAM_MODE: constants.STREAM_MODE_DISABLED},
    }

    assert camera_config.missing_stream_keys(cameras, options) == {"CAM-A"}


def test_normalize_rtsp_path_rejects_url_and_query_injection() -> None:
    """The stored field must remain an RTSP path, never a replacement URL."""
    assert (
        camera_config.normalize_rtsp_path("rtsp://attacker.invalid/live")
        == constants.DEFAULT_FFMPEG_ARGUMENTS
    )
    assert (
        camera_config.normalize_rtsp_path("/Streaming/Channels/101?token=x")
        == constants.DEFAULT_FFMPEG_ARGUMENTS
    )
    assert camera_config.normalize_rtsp_path("Streaming/Channels/101") == "/Streaming/Channels/101"

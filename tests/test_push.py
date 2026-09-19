"""Unit tests for low-latency EZVIZ MQTT push normalization."""

from __future__ import annotations

from .module_loader import load_push

push = load_push()


def test_alarm_without_image_triggers_motion_immediately() -> None:
    """The first alarm push must not wait for the cloud image field."""
    update = push.normalize_push_event(
        {
            "alert": "Person",
            "ext": {
                "device_serial": "CAM-A",
                "alert_type_code": 2403,
                "time": "2026-08-14 10:00:00",
                "msgId": "message-1",
            },
        }
    )

    assert update is not None
    assert update.event_id == "message-1"
    assert update.values["Motion_Trigger"] is True
    assert update.values["Seconds_Last_Trigger"] == 0.0
    assert "last_alarm_pic" not in update.values


def test_early_default_picture_is_used_before_final_image() -> None:
    """The earlier default picture URL should update the image entity immediately."""
    update = push.normalize_push_event(
        {
            "alert": "Motion detected",
            "ext": {
                "device_serial": "CAM-A",
                "alert_type_code": 2401,
                "default_pic_url": "https://images.example.test/preview.jpg",
            },
        }
    )

    assert update is not None
    assert update.values["last_alarm_pic"] == "https://images.example.test/preview.jpg"


def test_final_image_is_preferred_when_already_available() -> None:
    """The final image should win when both preview and final URLs are present."""
    update = push.normalize_push_event(
        {
            "alert": "Motion detected",
            "ext": {
                "image": "https://images.example.test/final.jpg",
                "default_pic_url": "https://images.example.test/preview.jpg",
            },
        }
    )

    assert update is not None
    assert update.values["last_alarm_pic"] == "https://images.example.test/final.jpg"


def test_non_alarm_push_is_ignored() -> None:
    """Generic device push messages must not create false motion."""
    assert push.normalize_push_event({"ext": {"device_serial": "CAM-A"}}) is None


def test_non_http_picture_value_is_ignored() -> None:
    """Malformed image fields must not replace the last usable alarm image."""
    update = push.normalize_push_event(
        {
            "alert": "Motion detected",
            "ext": {"default_pic_url": "preview.jpg"},
        }
    )

    assert update is not None
    assert "last_alarm_pic" not in update.values


def test_motion_clear_seconds_is_clamped_and_defaults_safely() -> None:
    """Motion auto-off options should remain within the supported range."""
    requested_seconds = 15
    assert push.normalize_motion_clear_seconds(requested_seconds) == float(requested_seconds)
    assert push.normalize_motion_clear_seconds(0) == float(push.MIN_MOTION_CLEAR_SECONDS)
    assert push.normalize_motion_clear_seconds(99999) == float(push.MAX_MOTION_CLEAR_SECONDS)
    assert push.normalize_motion_clear_seconds(None) == push.MOTION_ACTIVE_SECONDS

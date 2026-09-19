"""Validate integration translation structure and entity keys."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import string
from typing import Any

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "ezviz_cloud"
TRANSLATION_FILES = ("translations/en.json", "translations/vi.json")
ENTITY_PLATFORMS = (
    "binary_sensor",
    "button",
    "image",
    "light",
    "number",
    "select",
    "sensor",
    "siren",
    "switch",
    "text",
)


def _load_json(relative_path: str) -> dict[str, Any]:
    """Load one integration translation file."""
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


def _flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    """Flatten a nested translation mapping into dotted keys."""
    if not isinstance(value, dict):
        return {prefix: value}

    flattened: dict[str, Any] = {}
    for key, item in value.items():
        item_prefix = f"{prefix}.{key}" if prefix else key
        flattened.update(_flatten(item, item_prefix))
    return flattened


def _placeholders(value: Any) -> set[str]:
    """Return format placeholders from a translation value."""
    if not isinstance(value, str):
        return set()
    return {
        field_name
        for _literal, field_name, _format_spec, _conversion in string.Formatter().parse(value)
        if field_name
    }


def test_translations_match_strings_schema() -> None:
    """English and Vietnamese translations must mirror strings.json."""
    base = _flatten(_load_json("strings.json"))

    for relative_path in TRANSLATION_FILES:
        translated = _flatten(_load_json(relative_path))
        assert translated.keys() == base.keys()
        for key in base:
            assert "[%key:" not in str(translated[key]), key
            assert _placeholders(translated[key]) == _placeholders(base[key]), key


def test_literal_entity_translation_keys_exist() -> None:
    """Every literal entity-description translation key must be declared."""
    strings = _load_json("strings.json")["entity"]

    for platform in ENTITY_PLATFORMS:
        tree = ast.parse((ROOT / f"{platform}.py").read_text(encoding="utf-8"))
        declared = set(strings.get(platform, {}))
        used = {
            keyword.value.value
            for keyword in ast.walk(tree)
            if isinstance(keyword, ast.keyword)
            and keyword.arg == "translation_key"
            and isinstance(keyword.value, ast.Constant)
            and isinstance(keyword.value.value, str)
        }
        assert used <= declared, f"{platform}: missing {sorted(used - declared)}"

"""Helpers for Anthbot mowing parameter state."""

from __future__ import annotations

from typing import Any

NEST_VISUAL_INSPECTION_LEVEL_LOW = "Low"
NEST_VISUAL_INSPECTION_LEVEL_MEDIUM = "Medium"
NEST_VISUAL_INSPECTION_LEVEL_HIGH = "High"

NEST_VISUAL_INSPECTION_OPTIONS: tuple[str, ...] = (
    NEST_VISUAL_INSPECTION_LEVEL_LOW,
    NEST_VISUAL_INSPECTION_LEVEL_MEDIUM,
    NEST_VISUAL_INSPECTION_LEVEL_HIGH,
)

_NEST_VISUAL_INSPECTION_LEVEL_BY_OPTION: dict[str, int] = {
    NEST_VISUAL_INSPECTION_LEVEL_LOW: 0,
    NEST_VISUAL_INSPECTION_LEVEL_MEDIUM: 1,
    NEST_VISUAL_INSPECTION_LEVEL_HIGH: 2,
}
_NEST_VISUAL_INSPECTION_OPTION_BY_LEVEL: dict[int, str] = {
    value: key for key, value in _NEST_VISUAL_INSPECTION_LEVEL_BY_OPTION.items()
}


def coerce_enabled_value(value: object) -> bool:
    """Map Anthbot integer/bool/string toggles to a Python bool."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value == 1
    if isinstance(value, str):
        lowered = value.strip().lower()
        return lowered in {"1", "true", "on", "enabled", "enable"}
    return False


def raw_int_value(value: object) -> int | None:
    """Return an integer from common Anthbot shadow payload shapes."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.lstrip("-").isdigit():
            return int(stripped)
        return None
    if isinstance(value, dict):
        return raw_int_value(value.get("value"))
    return None


def custom_direction_enabled_from_state(data: dict[str, Any]) -> bool:
    """Map raw enable_adaptive_head value to custom-direction toggle state."""
    param_set = data.get("param_set")
    if not isinstance(param_set, dict):
        return False
    return not coerce_enabled_value(param_set.get("enable_adaptive_head"))


def nest_mowing_enabled_from_state(data: dict[str, Any]) -> bool:
    """Return whether base-station mowing mode is enabled."""
    if data.get("nest_switch") is None:
        return coerce_enabled_value(data.get("param_set").get("nest_switch"))
    else:
        return coerce_enabled_value(data.get("nest_switch"))


def nest_visual_inspection_enabled_from_state(data: dict[str, Any]) -> bool:
    """Return whether base-station visual inspection is enabled."""
    if data.get("nest_pobctl_switch") is None:
        return coerce_enabled_value(data.get("nest_param_set").get("pobctl_switch"))
    else:
        return coerce_enabled_value(data.get("nest_pobctl_switch"))


def nest_visual_inspection_level_from_state(data: dict[str, Any]) -> int | None:
    """Return the raw base-station visual inspection level."""
    if data.get("nest_pobctl_level") is None:
        return coerce_enabled_value(data.get("nest_param_set").get("pobctl_level"))
    else:
        return raw_int_value(data.get("nest_pobctl_level"))


def nest_visual_inspection_option_from_state(data: dict[str, Any]) -> str | None:
    """Return the labeled base-station visual inspection level."""
    level = nest_visual_inspection_level_from_state(data)
    if level is None:
        return None
    return _NEST_VISUAL_INSPECTION_OPTION_BY_LEVEL.get(level)


def nest_visual_inspection_level_from_option(option: str) -> int:
    """Map a visual inspection level option back to the raw Anthbot value."""
    return _NEST_VISUAL_INSPECTION_LEVEL_BY_OPTION[option]


def build_nest_mow_params_payload(
    data: dict[str, Any], **overrides: int | bool
) -> dict[str, int]:
    """Build a full nest payload while preserving current values."""
    cutter_height = raw_int_value(
        data.get("param_set", {}).get("cutter_height")
        if isinstance(data.get("param_set"), dict)
        else None
    )
    nest_switch = raw_int_value(data.get("nest_switch"))
    nest_mow_count = raw_int_value(data.get("nest_mow_count"))
    nest_cutter_height = raw_int_value(data.get("nest_cutter_height"))
    nest_pobctl_switch = raw_int_value(data.get("nest_pobctl_switch"))
    nest_pobctl_level = raw_int_value(data.get("nest_pobctl_level"))
    payload = {
        "nest_switch": nest_switch if nest_switch is not None else 0,
        "nest_mow_count": nest_mow_count if nest_mow_count is not None else 1,
        "nest_cutter_height": (
            nest_cutter_height
            if nest_cutter_height is not None
            else cutter_height if cutter_height is not None else 35
        ),
        "nest_pobctl_switch": (
            nest_pobctl_switch if nest_pobctl_switch is not None else 0
        ),
        "nest_pobctl_level": nest_pobctl_level if nest_pobctl_level is not None else 1,
    }
    for key, value in overrides.items():
        payload[key] = int(value) if isinstance(value, bool) else int(value)
    return payload

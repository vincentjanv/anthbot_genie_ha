"""Map parsing and rendering helpers for Anthbot Genie."""

from __future__ import annotations

import binascii
from base64 import b64decode
from collections.abc import Iterable
import math
import struct
from typing import Any
import zlib

MAX_RENDER_POINTS = 400
IMAGE_WIDTH = 800
IMAGE_HEIGHT = 560
IMAGE_PADDING = 72


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return None


def _point_pairs(value: Any) -> list[tuple[int, int]]:
    points: list[tuple[int, int]] = []
    if not isinstance(value, list):
        return points

    for item in value:
        if isinstance(item, dict):
            x_value = _coerce_int(item.get("x"))
            y_value = _coerce_int(item.get("y"))
        elif isinstance(item, list) and len(item) >= 2:
            x_value = _coerce_int(item[0])
            y_value = _coerce_int(item[1])
        else:
            continue
        if x_value is None or y_value is None:
            continue
        points.append((x_value, y_value))
    return points


def manual_zone_polygons(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract manual zone polygons."""
    zones: list[dict[str, Any]] = []
    area_definition = data.get("_area_definition", {})
    for key in ("custom_areas", "zones", "customAreas"):
        zone_list = area_definition.get(key)
        if not isinstance(zone_list, list):
            continue
        items: list[dict[str, Any]] = []
        for zone in zone_list:
            if not isinstance(zone, dict):
                continue
            points = _point_pairs(zone.get("vertexs") or zone.get("points"))
            if len(points) < 3:
                continue
            items.append(
                {
                    "id": zone.get("id"),
                    "name": zone.get("name"),
                    "points": points,
                }
            )
        if items:
            return items
    return zones


def auto_zone_points(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract auto-zone points."""
    area_definition = data.get("_area_definition", {})
    for key in (
        "region_areas",
        "regionAreas",
        "auto_regions",
        "autoRegions",
        "auto_zones",
        "autoZones",
        "regions",
    ):
        zones = area_definition.get(key)
        if not isinstance(zones, list):
            continue
        items: list[dict[str, Any]] = []
        for zone in zones:
            if not isinstance(zone, dict):
                continue
            x_value = _coerce_int(zone.get("x"))
            y_value = _coerce_int(zone.get("y"))
            if x_value is None or y_value is None:
                continue
            items.append(
                {
                    "id": zone.get("id"),
                    "name": zone.get("name"),
                    "point": (x_value, y_value),
                }
            )
        if items:
            return items
    return []


def active_zone_ids(data: dict[str, Any]) -> list[int]:
    """Return active manual zone ids."""
    active_area = data.get("active_area")
    if not isinstance(active_area, dict):
        return []
    ids = active_area.get("id")
    if not isinstance(ids, list):
        return []
    return [item for item in ids if isinstance(item, int)]


def mower_pose(data: dict[str, Any]) -> tuple[int, int] | None:
    """Return the mower pose in map coordinates if available."""
    pose = data.get("pose")
    if isinstance(pose, dict):
        x_value = _coerce_int(pose.get("x"))
        y_value = _coerce_int(pose.get("y"))
        if x_value is not None and y_value is not None:
            return (x_value, y_value)

    anti_loss_pose = data.get("anti_loss_pose")
    if isinstance(anti_loss_pose, dict):
        pose2d = anti_loss_pose.get("pose2d")
        if isinstance(pose2d, dict):
            x_value = pose2d.get("x")
            y_value = pose2d.get("y")
            if isinstance(x_value, (int, float)) and isinstance(y_value, (int, float)):
                return (int(round(x_value * 1000)), int(round(y_value * 1000)))

    return None


def _deduplicate_points(points: Iterable[dict[str, int]]) -> list[dict[str, int]]:
    deduped: list[dict[str, int]] = []
    last_xy: tuple[int, int] | None = None
    for point in points:
        x_value = point["x"]
        y_value = point["y"]
        current_xy = (x_value, y_value)
        if current_xy == last_xy:
            continue
        deduped.append(point)
        last_xy = current_xy
    return deduped


def _downsample_points(points: list[dict[str, int]]) -> list[dict[str, int]]:
    if len(points) <= MAX_RENDER_POINTS:
        return points

    step = math.ceil(len(points) / MAX_RENDER_POINTS)
    sampled = points[::step]
    if sampled[-1] != points[-1]:
        sampled.append(points[-1])
    return sampled


def _parse_point_records(
    payload: bytes,
    *,
    point_size: int,
    total_points: int | None,
) -> list[dict[str, int]]:
    if point_size not in {5, 8, 12}:
        return []

    available_points = len(payload) // point_size
    point_count = available_points
    if total_points is not None and total_points > 0:
        point_count = min(total_points, available_points)

    points: list[dict[str, int]] = []
    offset = 0
    for _ in range(point_count):
        if point_size == 5:
            x_value, y_value, point_type = struct.unpack_from("<hhB", payload, offset)
            offset += 5
            points.append({"x": x_value * 10, "y": y_value * 10, "type": point_type})
            continue

        if point_size == 8:
            x_value, y_value, point_type = struct.unpack_from("<hhi", payload, offset)
            offset += 8
            points.append({"x": x_value * 10, "y": y_value * 10, "type": point_type})
            continue

        x_value, y_value, point_type, clean_time = struct.unpack_from(
            "<hhii", payload, offset
        )
        offset += 12
        points.append(
            {
                "x": x_value * 10,
                "y": y_value * 10,
                "type": point_type,
                "clean_time": clean_time,
            }
        )

    return _downsample_points(_deduplicate_points(points))


def parse_curpath_base64(value: str | None) -> list[dict[str, int]]:
    """Parse the live curpath field from the property shadow."""
    if not isinstance(value, str) or not value:
        return []

    try:
        payload_bytes = b64decode(value)
    except (ValueError, TypeError):
        return []

    if len(payload_bytes) < 10:
        return []

    head_len = payload_bytes[0]
    if head_len <= 0 or head_len >= len(payload_bytes):
        return []

    point_payload = payload_bytes[head_len:]
    if not point_payload:
        return []

    total_points = None
    if len(payload_bytes) >= 8:
        total_points = struct.unpack_from("<I", payload_bytes, 4)[0]

    point_size = 0
    if total_points and len(point_payload) % total_points == 0:
        point_size = len(point_payload) // total_points
    else:
        for candidate_size in (5, 8, 12):
            if len(point_payload) % candidate_size == 0:
                point_size = candidate_size
                break

    if point_size == 0:
        return []

    return _parse_point_records(
        point_payload,
        point_size=point_size,
        total_points=total_points,
    )


def parse_history_path_bytes(payload_bytes: bytes | None) -> list[dict[str, int]]:
    """Parse a session path file (`path_<serial>.txt`)."""
    if not payload_bytes or len(payload_bytes) < 8:
        return []

    head_len = payload_bytes[0]
    version = payload_bytes[1]
    if head_len <= 0 or head_len >= len(payload_bytes):
        return []

    if version == 1:
        point_size = payload_bytes[2]
        if len(payload_bytes) < 9:
            return []
        total_points = struct.unpack_from("<I", payload_bytes, 5)[0]
    else:
        if len(payload_bytes) < 10:
            return []
        point_size = payload_bytes[2]
        total_points = struct.unpack_from("<I", payload_bytes, 6)[0]

    point_payload = payload_bytes[head_len:]
    return _parse_point_records(
        point_payload,
        point_size=point_size,
        total_points=total_points,
    )


def merged_session_path_points(data: dict[str, Any]) -> list[dict[str, int]]:
    """Return merged session path points from full-history + live curpath."""
    merged: list[dict[str, int]] = []
    history_points = data.get("_session_path_points")
    if isinstance(history_points, list):
        merged.extend(
            point
            for point in history_points
            if isinstance(point, dict)
            and isinstance(point.get("x"), int)
            and isinstance(point.get("y"), int)
        )

    merged.extend(parse_curpath_base64(data.get("curpath")))
    return _downsample_points(_deduplicate_points(merged))


def _zone_centroid(points: list[tuple[int, int]]) -> tuple[float, float]:
    x_total = sum(point[0] for point in points)
    y_total = sum(point[1] for point in points)
    return (x_total / len(points), y_total / len(points))


def _compute_bounds(
    manual_zones_data: list[dict[str, Any]],
    auto_zones_data: list[dict[str, Any]],
    path_points: list[dict[str, int]],
    pose: tuple[int, int] | None,
) -> tuple[float, float, float, float]:
    xs: list[float] = []
    ys: list[float] = []

    for zone in manual_zones_data:
        for x_value, y_value in zone["points"]:
            xs.append(float(x_value))
            ys.append(float(y_value))

    for zone in auto_zones_data:
        x_value, y_value = zone["point"]
        xs.append(float(x_value))
        ys.append(float(y_value))

    for point in path_points:
        xs.append(float(point["x"]))
        ys.append(float(point["y"]))

    if pose is not None:
        xs.append(float(pose[0]))
        ys.append(float(pose[1]))

    if not xs or not ys:
        return (0.0, 0.0, 100.0, 100.0)

    min_x = min(xs)
    max_x = max(xs)
    min_y = min(ys)
    max_y = max(ys)

    if math.isclose(min_x, max_x):
        min_x -= 50
        max_x += 50
    if math.isclose(min_y, max_y):
        min_y -= 50
        max_y += 50

    span_x = max_x - min_x
    span_y = max_y - min_y
    padding = max(span_x, span_y) * 0.08
    return (min_x - padding, min_y - padding, max_x + padding, max_y + padding)


def _scaler(bounds: tuple[float, float, float, float]):
    min_x, min_y, max_x, max_y = bounds
    width = max_x - min_x
    height = max_y - min_y
    scale = min(
        (IMAGE_WIDTH - (IMAGE_PADDING * 2)) / width,
        (IMAGE_HEIGHT - (IMAGE_PADDING * 2)) / height,
    )
    x_offset = (IMAGE_WIDTH - (width * scale)) / 2
    y_offset = (IMAGE_HEIGHT - (height * scale)) / 2

    def _convert(point: tuple[float, float]) -> tuple[float, float]:
        x_value = x_offset + ((point[0] - min_x) * scale)
        y_value = y_offset + ((max_y - point[1]) * scale)
        return (x_value, y_value)

    return _convert


def _new_canvas() -> bytearray:
    canvas = bytearray(IMAGE_WIDTH * IMAGE_HEIGHT * 3)
    top_color = (246, 244, 236)
    bottom_color = (237, 243, 231)
    for y_value in range(IMAGE_HEIGHT):
        ratio = y_value / max(1, IMAGE_HEIGHT - 1)
        red = int((top_color[0] * (1.0 - ratio)) + (bottom_color[0] * ratio))
        green = int((top_color[1] * (1.0 - ratio)) + (bottom_color[1] * ratio))
        blue = int((top_color[2] * (1.0 - ratio)) + (bottom_color[2] * ratio))
        row_offset = y_value * IMAGE_WIDTH * 3
        for x_value in range(IMAGE_WIDTH):
            offset = row_offset + (x_value * 3)
            canvas[offset] = red
            canvas[offset + 1] = green
            canvas[offset + 2] = blue
    return canvas


def _set_pixel(
    canvas: bytearray,
    x_value: int,
    y_value: int,
    color: tuple[int, int, int],
) -> None:
    if not (0 <= x_value < IMAGE_WIDTH and 0 <= y_value < IMAGE_HEIGHT):
        return
    offset = ((y_value * IMAGE_WIDTH) + x_value) * 3
    canvas[offset] = color[0]
    canvas[offset + 1] = color[1]
    canvas[offset + 2] = color[2]


def _draw_line(
    canvas: bytearray,
    start: tuple[float, float],
    end: tuple[float, float],
    color: tuple[int, int, int],
    *,
    thickness: int = 1,
) -> None:
    x0 = int(round(start[0]))
    y0 = int(round(start[1]))
    x1 = int(round(end[0]))
    y1 = int(round(end[1]))
    delta_x = abs(x1 - x0)
    step_x = 1 if x0 < x1 else -1
    delta_y = -abs(y1 - y0)
    step_y = 1 if y0 < y1 else -1
    error = delta_x + delta_y

    while True:
        half = max(0, thickness // 2)
        for offset_x in range(-half, half + 1):
            for offset_y in range(-half, half + 1):
                _set_pixel(canvas, x0 + offset_x, y0 + offset_y, color)
        if x0 == x1 and y0 == y1:
            break
        error_twice = error * 2
        if error_twice >= delta_y:
            error += delta_y
            x0 += step_x
        if error_twice <= delta_x:
            error += delta_x
            y0 += step_y


def _fill_rect(
    canvas: bytearray,
    left: int,
    top: int,
    right: int,
    bottom: int,
    color: tuple[int, int, int],
) -> None:
    for y_value in range(max(0, top), min(IMAGE_HEIGHT, bottom)):
        for x_value in range(max(0, left), min(IMAGE_WIDTH, right)):
            _set_pixel(canvas, x_value, y_value, color)


def _draw_grid(canvas: bytearray) -> None:
    grid_color = (214, 220, 203)
    for x_value in range(0, IMAGE_WIDTH, 80):
        _draw_line(
            canvas,
            (x_value, 0),
            (x_value, IMAGE_HEIGHT - 1),
            grid_color,
        )
    for y_value in range(0, IMAGE_HEIGHT, 80):
        _draw_line(
            canvas,
            (0, y_value),
            (IMAGE_WIDTH - 1, y_value),
            grid_color,
        )


def _fill_polygon(
    canvas: bytearray,
    points: list[tuple[float, float]],
    color: tuple[int, int, int],
) -> None:
    if len(points) < 3:
        return
    int_points = [(int(round(x_value)), int(round(y_value))) for x_value, y_value in points]
    min_y = max(0, min(y_value for _, y_value in int_points))
    max_y = min(IMAGE_HEIGHT - 1, max(y_value for _, y_value in int_points))
    for y_value in range(min_y, max_y + 1):
        intersections: list[int] = []
        for index, point in enumerate(int_points):
            next_point = int_points[(index + 1) % len(int_points)]
            x1, y1 = point
            x2, y2 = next_point
            if y1 == y2:
                continue
            if y_value < min(y1, y2) or y_value >= max(y1, y2):
                continue
            intersection = x1 + ((y_value - y1) * (x2 - x1)) / (y2 - y1)
            intersections.append(int(round(intersection)))
        intersections.sort()
        for i in range(0, len(intersections), 2):
            if i + 1 >= len(intersections):
                break
            start_x = max(0, intersections[i])
            end_x = min(IMAGE_WIDTH - 1, intersections[i + 1])
            for x_value in range(start_x, end_x + 1):
                _set_pixel(canvas, x_value, y_value, color)


def _draw_polygon(
    canvas: bytearray,
    points: list[tuple[float, float]],
    fill_color: tuple[int, int, int],
    stroke_color: tuple[int, int, int],
) -> None:
    _fill_polygon(canvas, points, fill_color)
    for index, point in enumerate(points):
        next_point = points[(index + 1) % len(points)]
        _draw_line(canvas, point, next_point, stroke_color, thickness=4)


def _draw_circle(
    canvas: bytearray,
    center: tuple[float, float],
    radius: int,
    color: tuple[int, int, int],
) -> None:
    center_x = int(round(center[0]))
    center_y = int(round(center[1]))
    radius_sq = radius * radius
    for y_value in range(center_y - radius, center_y + radius + 1):
        for x_value in range(center_x - radius, center_x + radius + 1):
            if ((x_value - center_x) ** 2) + ((y_value - center_y) ** 2) <= radius_sq:
                _set_pixel(canvas, x_value, y_value, color)


def _draw_ring(
    canvas: bytearray,
    center: tuple[float, float],
    radius: int,
    color: tuple[int, int, int],
    *,
    thickness: int = 3,
) -> None:
    center_x = int(round(center[0]))
    center_y = int(round(center[1]))
    outer_sq = radius * radius
    inner_radius = max(0, radius - thickness)
    inner_sq = inner_radius * inner_radius
    for y_value in range(center_y - radius, center_y + radius + 1):
        for x_value in range(center_x - radius, center_x + radius + 1):
            distance_sq = ((x_value - center_x) ** 2) + ((y_value - center_y) ** 2)
            if inner_sq <= distance_sq <= outer_sq:
                _set_pixel(canvas, x_value, y_value, color)


def _draw_polyline(
    canvas: bytearray,
    points: list[tuple[float, float]],
    color: tuple[int, int, int],
    *,
    thickness: int = 3,
) -> None:
    if len(points) < 2:
        return
    for index in range(len(points) - 1):
        _draw_line(canvas, points[index], points[index + 1], color, thickness=thickness)


def _encode_png(canvas: bytearray) -> bytes:
    raw = bytearray()
    row_length = IMAGE_WIDTH * 3
    for y_value in range(IMAGE_HEIGHT):
        raw.append(0)
        start = y_value * row_length
        raw.extend(canvas[start : start + row_length])

    def _chunk(chunk_type: bytes, chunk_data: bytes) -> bytes:
        return (
            struct.pack(">I", len(chunk_data))
            + chunk_type
            + chunk_data
            + struct.pack(">I", binascii.crc32(chunk_type + chunk_data) & 0xFFFFFFFF)
        )

    header = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", IMAGE_WIDTH, IMAGE_HEIGHT, 8, 2, 0, 0, 0)
    idat = zlib.compress(bytes(raw), level=6)
    return header + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", idat) + _chunk(b"IEND", b"")


def render_map_png(
    *,
    title: str,
    serial_number: str,
    manual_zones_data: list[dict[str, Any]],
    auto_zones_data: list[dict[str, Any]],
    active_zone_id_list: list[int],
    path_points: list[dict[str, int]],
    pose: tuple[int, int] | None,
    path_source: str | None,
    show_manual_zones: bool,
    show_auto_zones: bool,
    show_path: bool,
    show_pose: bool,
) -> bytes:
    """Render the mower map as a PNG image."""
    bounds = _compute_bounds(manual_zones_data, auto_zones_data, path_points, pose)
    to_image_point = _scaler(bounds)
    canvas = _new_canvas()
    _draw_grid(canvas)
    _fill_rect(canvas, 24, 20, 520, 114, (255, 253, 247))

    if show_manual_zones:
        for zone in manual_zones_data:
            polygon_points = [to_image_point(point) for point in zone["points"]]
            zone_id = zone.get("id")
            is_active = isinstance(zone_id, int) and zone_id in active_zone_id_list
            fill = (106, 159, 63) if is_active else (137, 185, 106)
            stroke = (49, 95, 29) if is_active else (78, 124, 56)
            _draw_polygon(
                canvas,
                polygon_points,
                fill,
                stroke,
            )

    if show_auto_zones:
        for zone in auto_zones_data:
            center = to_image_point(zone["point"])
            _draw_circle(canvas, center, 14, (15, 109, 140))
            _draw_ring(canvas, center, 17, (8, 59, 77), thickness=3)
        if auto_zones_data:
            point_values = [to_image_point(zone["point"]) for zone in auto_zones_data]
            _draw_polyline(canvas, point_values, (15, 109, 140), thickness=2)

    if show_path and path_points:
        path_polyline = [
            to_image_point((point["x"], point["y"]))
            for point in path_points
        ]
        _draw_polyline(canvas, path_polyline, (210, 100, 42), thickness=5)

    if show_pose and pose is not None:
        center = to_image_point((pose[0], pose[1]))
        _draw_circle(canvas, center, 13, (196, 50, 50))
        _draw_ring(canvas, center, 31, (196, 50, 50), thickness=3)

    # Minimal legend strips without text so the camera stays raster-only.
    _fill_rect(canvas, 42, 42, 76, 58, (210, 100, 42))
    _fill_rect(canvas, 42, 66, 76, 82, (15, 109, 140))
    _fill_rect(canvas, 42, 90, 76, 106, (196, 50, 50))

    return _encode_png(canvas)

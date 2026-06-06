"""
Geometric helpers for bounding-box operations.
"""
from typing import Any


def _get_bbox(obj):
    """
    Supports multiple formats:
    - (x1, y1, x2, y2)
    - {"box": (...) }
    - dict containing bbox-like tuple directly
    """

    # Case 1: raw tuple/list
    if isinstance(obj, (tuple, list)) and len(obj) == 4:
        return obj

    # Case 2: dict with "box"
    if isinstance(obj, dict):
        if "box" in obj:
            return obj["box"]
        if "bbox" in obj:
            return obj["bbox"]

    raise ValueError(f"Unsupported bbox format: {obj}")


def box_foot_x(obj: Any) -> int:
    """Horizontal centre at bottom of box."""
    x1, _, x2, _ = _get_bbox(obj)
    return int((x1 + x2) // 2)


def box_foot_y(obj: Any) -> int:
    """Bottom y-coordinate."""
    _, _, _, y2 = _get_bbox(obj)
    return int(y2)


def box_centre(obj: Any) -> tuple[float, float]:
    """Centre point of bounding box."""
    x1, y1, x2, y2 = _get_bbox(obj)
    return ((x1 + x2) / 2, (y1 + y2) / 2)


def box_area(obj: Any) -> int:
    """Bounding box area."""
    x1, y1, x2, y2 = _get_bbox(obj)
    return int(max(0, x2 - x1) * max(0, y2 - y1))

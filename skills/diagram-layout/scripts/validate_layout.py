#!/usr/bin/env python3
"""Validate a layout plan for overlaps and edge-node collisions."""

import json
import sys


def validate(plan):
    """Check layout plan for common issues."""
    warnings = []
    errors = []

    elements = plan.get("elements", [])
    canvas = plan.get("canvas", {"width": 1920, "height": 1080})

    # Collect all node bounding boxes (including container children)
    boxes = []
    container_children = set()
    container_ids = set()
    for elem in elements:
        etype = elem.get("type", "node")
        if etype in ("node", "container"):
            boxes.append({
                "id": elem["id"],
                "x": elem["x"],
                "y": elem["y"],
                "w": elem["width"],
                "h": elem["height"],
            })
            if etype == "container":
                container_ids.add(elem["id"])
                for child in elem.get("children", []):
                    container_children.add(child["id"])
                    boxes.append({
                        "id": child["id"],
                        "x": elem["x"] + child["rel_x"],
                        "y": elem["y"] + child["rel_y"],
                        "w": child["width"],
                        "h": child["height"],
                    })

    # Check node overlaps (10px margin), skip container-child pairs
    margin = 10
    for i, a in enumerate(boxes):
        for b in boxes[i + 1:]:
            # Skip: container overlapping its own children (expected)
            if a["id"] in container_ids and b["id"] in container_children:
                continue
            if b["id"] in container_ids and a["id"] in container_children:
                continue
            if _overlaps(a, b, margin):
                errors.append(
                    f"Node overlap: {a['id']} ({a['x']},{a['y']} "
                    f"{a['w']}x{a['h']}) overlaps "
                    f"{b['id']} ({b['x']},{b['y']} {b['w']}x{b['h']})"
                )

    # Check canvas bounds
    for box in boxes:
        if box["x"] < 0 or box["y"] < 0:
            warnings.append(
                f"Node {box['id']} has negative coordinates: "
                f"({box['x']}, {box['y']})"
            )
        right = box["x"] + box["w"]
        bottom = box["y"] + box["h"]
        if right > canvas["width"]:
            warnings.append(
                f"Node {box['id']} extends past canvas width: "
                f"right edge at {right} > {canvas['width']}"
            )
        if bottom > canvas["height"]:
            warnings.append(
                f"Node {box['id']} extends past canvas height: "
                f"bottom edge at {bottom} > {canvas['height']}"
            )

    # Check container bounds (children within container)
    for elem in elements:
        if elem.get("type") != "container":
            continue
        for child in elem.get("children", []):
            cx = child["rel_x"]
            cy = child["rel_y"]
            cw = child["width"]
            ch = child["height"]
            if cx < 0 or cy < 0:
                errors.append(
                    f"Container child {child['id']} has negative offset "
                    f"in container {elem['id']}"
                )
            if cx + cw > elem["width"]:
                errors.append(
                    f"Container child {child['id']} overflows container "
                    f"{elem['id']} width: {cx + cw} > {elem['width']}"
                )
            if cy + ch > elem["height"]:
                errors.append(
                    f"Container child {child['id']} overflows container "
                    f"{elem['id']} height: {cy + ch} > {elem['height']}"
                )

    # Build lookup for node geometry
    node_geom = {}
    for elem in elements:
        etype = elem.get("type", "node")
        if etype in ("node", "container"):
            node_geom[elem["id"]] = elem

    # Check edge-edge crossings (including implicit anchor segments)
    edge_segments = []
    for elem in elements:
        if elem.get("type") != "edge":
            continue
        eid = f"{elem['from']}->{elem['to']}"
        all_points = []

        # Add exit point (source anchor → first waypoint)
        src_node = node_geom.get(elem["from"])
        ep = elem.get("exit_point")
        if src_node and ep:
            all_points.append({
                "x": src_node["x"] + ep["x"] * src_node["width"],
                "y": src_node["y"] + ep["y"] * src_node["height"],
            })

        # Add explicit waypoints
        wps = elem.get("waypoints") or []
        all_points.extend(wps)

        # Add entry point (last waypoint → target anchor)
        tgt_node = node_geom.get(elem["to"])
        np_ = elem.get("entry_point")
        if tgt_node and np_:
            all_points.append({
                "x": tgt_node["x"] + np_["x"] * tgt_node["width"],
                "y": tgt_node["y"] + np_["y"] * tgt_node["height"],
            })

        for j in range(len(all_points) - 1):
            edge_segments.append((
                eid,
                all_points[j]["x"], all_points[j]["y"],
                all_points[j + 1]["x"], all_points[j + 1]["y"],
            ))

    for i, (eid_a, ax1, ay1, ax2, ay2) in enumerate(edge_segments):
        for eid_b, bx1, by1, bx2, by2 in edge_segments[i + 1:]:
            if eid_a == eid_b:
                continue
            if _segments_intersect(ax1, ay1, ax2, ay2, bx1, by1, bx2, by2):
                warnings.append(
                    f"Edge crossing: {eid_a} segment "
                    f"({ax1},{ay1})->({ax2},{ay2}) crosses "
                    f"{eid_b} segment ({bx1},{by1})->({bx2},{by2})"
                )

    # Build container parent→children map for skip logic
    container_children = {}
    for elem in elements:
        if elem.get("type") == "container":
            for child in elem.get("children", []):
                child_id = child.get("id", child) if isinstance(child, dict) else child
                container_children[child_id] = elem["id"]

    # Check edge-node clearance (crossing and near-miss)
    clearance_margin = 15
    for eid, sx1, sy1, sx2, sy2 in edge_segments:
        src_id, _, tgt_id = eid.partition("->")
        for box in boxes:
            if box["id"] in (src_id, tgt_id):
                continue
            # Skip children of containers the edge connects to
            parent_id = container_children.get(box["id"])
            if parent_id and parent_id in (src_id, tgt_id):
                continue
            if _segment_intersects_box(sx1, sy1, sx2, sy2, box, margin=0):
                errors.append(
                    f"Edge through node: {eid} segment "
                    f"({sx1},{sy1})->({sx2},{sy2}) "
                    f"crosses node {box['id']}"
                )
            elif _segment_intersects_box(
                sx1, sy1, sx2, sy2, box, margin=clearance_margin
            ):
                dist = _min_segment_box_distance(
                    sx1, sy1, sx2, sy2, box
                )
                warnings.append(
                    f"Near-miss: {eid} passes within {dist:.0f}px "
                    f"of node {box['id']} (min clearance: "
                    f"{clearance_margin}px)"
                )

    # Check for excessive bends (suboptimal exit/entry side)
    for elem in elements:
        if elem.get("type") != "edge":
            continue
        wps = elem.get("waypoints") or []
        if not wps:
            continue
        ep = elem.get("exit_point")
        np_ = elem.get("entry_point")
        src = node_geom.get(elem["from"])
        tgt = node_geom.get(elem["to"])
        if not (src and tgt and ep and np_):
            continue

        pts = []
        pts.append((
            src["x"] + ep["x"] * src["width"],
            src["y"] + ep["y"] * src["height"],
        ))
        for w in wps:
            pts.append((w["x"], w["y"]))
        pts.append((
            tgt["x"] + np_["x"] * tgt["width"],
            tgt["y"] + np_["y"] * tgt["height"],
        ))

        diagonal_segs = _count_bends(pts)
        if diagonal_segs > 0:
            warnings.append(
                f"Avoidable bend: {elem['from']}->{elem['to']} has "
                f"{diagonal_segs} non-axis-aligned segment(s). "
                f"Choose an exit/entry side that faces the target "
                f"to eliminate unnecessary turns."
            )

    return {"errors": errors, "warnings": warnings}


def _min_segment_box_distance(x1, y1, x2, y2, box):
    """Minimum distance from a line segment to a bounding box edge."""
    bx, by, bw, bh = box["x"], box["y"], box["w"], box["h"]
    distances = []
    # For axis-aligned segments (most common), compute distance to
    # the nearest box edge directly.
    if abs(x2 - x1) < 1:  # vertical segment
        x = x1
        seg_min_y, seg_max_y = min(y1, y2), max(y1, y2)
        if seg_min_y <= by + bh and seg_max_y >= by:
            distances.append(abs(x - bx))
            distances.append(abs(x - (bx + bw)))
    if abs(y2 - y1) < 1:  # horizontal segment
        y = y1
        seg_min_x, seg_max_x = min(x1, x2), max(x1, x2)
        if seg_min_x <= bx + bw and seg_max_x >= bx:
            distances.append(abs(y - by))
            distances.append(abs(y - (by + bh)))
    # Corner distances as fallback
    for px, py in [(x1, y1), (x2, y2)]:
        for cx, cy in [(bx, by), (bx + bw, by),
                       (bx, by + bh), (bx + bw, by + bh)]:
            distances.append(((px - cx) ** 2 + (py - cy) ** 2) ** 0.5)
    return min(distances) if distances else 999


def _count_bends(pts):
    """Count orthogonal bends in a path.

    If two consecutive points are not axis-aligned, that implies an
    extra bend (drawio's orthogonal router adds an L-bend).
    """
    if len(pts) < 2:
        return 0
    bends = 0
    for i in range(len(pts) - 1):
        dx = abs(pts[i + 1][0] - pts[i][0])
        dy = abs(pts[i + 1][1] - pts[i][1])
        if dx > 5 and dy > 5:
            bends += 1
    return bends


def _overlaps(a, b, margin=0):
    """Check if two bounding boxes overlap with margin."""
    return not (
        a["x"] + a["w"] + margin <= b["x"]
        or b["x"] + b["w"] + margin <= a["x"]
        or a["y"] + a["h"] + margin <= b["y"]
        or b["y"] + b["h"] + margin <= a["y"]
    )


def _segment_intersects_box(x1, y1, x2, y2, box, margin=0):
    """Check if a line segment intersects a bounding box."""
    bx = box["x"] - margin
    by = box["y"] - margin
    bw = box["w"] + 2 * margin
    bh = box["h"] + 2 * margin

    # Check if either endpoint is inside the box
    for px, py in [(x1, y1), (x2, y2)]:
        if bx <= px <= bx + bw and by <= py <= by + bh:
            return True

    # Check segment against box edges
    edges = [
        (bx, by, bx + bw, by),
        (bx + bw, by, bx + bw, by + bh),
        (bx, by + bh, bx + bw, by + bh),
        (bx, by, bx, by + bh),
    ]
    for ex1, ey1, ex2, ey2 in edges:
        if _segments_intersect(x1, y1, x2, y2, ex1, ey1, ex2, ey2):
            return True
    return False


def _segments_intersect(ax1, ay1, ax2, ay2, bx1, by1, bx2, by2):
    """Check if two line segments intersect."""
    def cross(ox, oy, ax, ay, bx, by):
        return (ax - ox) * (by - oy) - (ay - oy) * (bx - ox)

    d1 = cross(bx1, by1, bx2, by2, ax1, ay1)
    d2 = cross(bx1, by1, bx2, by2, ax2, ay2)
    d3 = cross(ax1, ay1, ax2, ay2, bx1, by1)
    d4 = cross(ax1, ay1, ax2, ay2, bx2, by2)

    if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and \
       ((d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)):
        return True
    return False


def main():
    if len(sys.argv) < 2:
        print("Usage: validate_layout.py <layout-plan.json>",
              file=sys.stderr)
        sys.exit(1)

    with open(sys.argv[1]) as f:
        plan = json.load(f)

    result = validate(plan)

    if result["errors"]:
        print(f"ERRORS ({len(result['errors'])}):", file=sys.stderr)
        for e in result["errors"]:
            print(f"  - {e}", file=sys.stderr)

    if result["warnings"]:
        print(f"WARNINGS ({len(result['warnings'])}):", file=sys.stderr)
        for w in result["warnings"]:
            print(f"  - {w}", file=sys.stderr)

    if not result["errors"] and not result["warnings"]:
        print("Layout validation passed", file=sys.stderr)

    json.dump(result, sys.stdout, indent=2)


if __name__ == "__main__":
    main()

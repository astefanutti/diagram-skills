#!/usr/bin/env python3
"""Validate a layout plan for overlaps and edge-node collisions."""

import json
import sys


def validate(plan, spec=None):
    """Check layout plan for common issues.

    When `spec` (the graph spec the plan was built from) is supplied, also
    verify no edge was dropped between authoring and layout.
    """
    warnings = []
    errors = []

    elements = plan.get("elements", [])

    # Guard against malformed plans. An empty (or missing) `elements` array
    # silently passed every check below — so a plan written in the old
    # {"nodes": [...], "edges": [...]} schema "validated clean" and then
    # render_drawio.py emitted an empty diagram. Fail loudly instead.
    if not elements:
        if plan.get("nodes") or plan.get("edges"):
            errors.append(
                "layout plan uses the wrong schema: expected a single "
                "type-tagged 'elements' array (node/container/edge), but found "
                "top-level 'nodes'/'edges'. Convert it, or render_drawio.py "
                "will emit an empty diagram."
            )
        else:
            errors.append("layout plan has no 'elements' — nothing to render.")
        return {"errors": errors, "warnings": warnings}

    canvas = plan.get("canvas", {"width": 1920, "height": 1080})

    # Collect all node bounding boxes (including nested container children).
    # Recurse so deeper nesting composes absolute coords; every box with
    # children is a container and each descendant id is a container-child.
    boxes = []
    container_children = set()
    container_ids = set()

    def _walk_boxes(elem, abs_x, abs_y):
        boxes.append({
            "id": elem["id"],
            "x": abs_x,
            "y": abs_y,
            "w": elem["width"],
            "h": elem["height"],
        })
        kids = elem.get("children", [])
        if kids:
            container_ids.add(elem["id"])
            for child in kids:
                container_children.add(child["id"])
                _walk_boxes(child, abs_x + child["rel_x"], abs_y + child["rel_y"])

    for elem in elements:
        if elem.get("type", "node") in ("node", "container"):
            _walk_boxes(elem, elem["x"], elem["y"])

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

    # Check aspect ratio vs target
    direction = plan.get("direction", "right")
    topology = plan.get("topology", {})
    target_ratio = topology.get("suggested_aspect_ratio", 2.5)
    cw, ch = canvas.get("width", 1), canvas.get("height", 1)
    if direction in ("right", "left"):
        actual_ratio = cw / max(ch, 1)
    else:
        actual_ratio = ch / max(cw, 1)
    # Missing topology is informational, not a warning — don't fail the judge
    # for missing metadata that doesn't affect layout quality.
    if actual_ratio > target_ratio * 1.5:
        warnings.append(
            f"Aspect ratio {actual_ratio:.1f}:1 exceeds target "
            f"{target_ratio:.1f}:1 by >50% — try fan-out stacking and "
            f"container grouping first, row wrapping only as fallback"
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

    # Check container bounds (children within container with padding).
    # Recurses so a nested container's own children are checked against it too.
    container_padding = 10

    def _check_bounds(cont):
        for child in cont.get("children", []):
            cx = child["rel_x"]
            cy = child["rel_y"]
            cw = child["width"]
            ch = child["height"]
            if cx < 0 or cy < 0:
                errors.append(
                    f"Container child {child['id']} has negative offset "
                    f"in container {cont['id']}"
                )
            if cx + cw > cont["width"]:
                errors.append(
                    f"Container child {child['id']} overflows container "
                    f"{cont['id']} width: {cx + cw} > {cont['width']}"
                )
            if cy + ch > cont["height"]:
                errors.append(
                    f"Container child {child['id']} overflows container "
                    f"{cont['id']} height: {cy + ch} > {cont['height']}"
                )
            if cx < container_padding:
                warnings.append(
                    f"Container child {child['id']} has only {cx}px left "
                    f"padding in {cont['id']} (min {container_padding}px)"
                )
            if cont["width"] - (cx + cw) < container_padding:
                warnings.append(
                    f"Container child {child['id']} has only "
                    f"{cont['width'] - cx - cw:.0f}px right padding in "
                    f"{cont['id']} (min {container_padding}px)"
                )
            if child.get("children"):
                _check_bounds(child)

    for elem in elements:
        if elem.get("type") == "container":
            _check_bounds(elem)

    # Build lookup for node geometry
    node_geom = {}
    for elem in elements:
        etype = elem.get("type", "node")
        if etype in ("node", "container"):
            node_geom[elem["id"]] = elem

    # Check edge-edge crossings (including implicit anchor segments).
    # Skip edges with no waypoints — draw.io routes them dynamically,
    # so the exit→entry straight line doesn't represent the actual path.
    edge_segments = []
    for elem in elements:
        if elem.get("type") != "edge":
            continue
        wps = elem.get("waypoints") or []
        if not wps:
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

    # Build child→parent map across all nesting levels for skip logic.
    parent_of = {}

    def _map_parents(cont):
        for child in cont.get("children", []):
            cid = child.get("id", child) if isinstance(child, dict) else child
            parent_of[cid] = cont["id"]
            if isinstance(child, dict) and child.get("children"):
                _map_parents(child)

    for elem in elements:
        if elem.get("type") == "container":
            _map_parents(elem)

    def _ancestors(nid):
        chain, p = [], parent_of.get(nid)
        while p is not None and p not in chain:
            chain.append(p)
            p = parent_of.get(p)
        return chain

    # Check edge-node clearance (crossing and near-miss)
    clearance_margin = 15
    for eid, sx1, sy1, sx2, sy2 in edge_segments:
        src_id, _, tgt_id = eid.partition("->")
        # Skip the endpoints and every container enclosing either endpoint: an
        # edge that starts/ends inside a container exits via its border, so it
        # must not be flagged against that container or its descendants.
        skip_ids = {src_id, tgt_id}
        skip_ids |= set(_ancestors(src_id)) | set(_ancestors(tgt_id))
        for box in boxes:
            if box["id"] in skip_ids:
                continue
            # Skip descendants of any container the edge connects to/encloses.
            if any(a in skip_ids for a in _ancestors(box["id"])):
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

    # Check edge label collision with nodes
    label_char_width = 7
    label_height = 16
    label_padding = 4
    for elem in elements:
        if elem.get("type") != "edge":
            continue
        if not (elem.get("waypoints") or []):
            continue
        label = elem.get("label", "")
        if not label:
            continue
        src = node_geom.get(elem["from"])
        tgt = node_geom.get(elem["to"])
        if not (src and tgt):
            continue
        wps = elem.get("waypoints") or []
        pts = []
        ep = elem.get("exit_point")
        np_ = elem.get("entry_point")
        if src and ep:
            pts.append((src["x"] + ep["x"] * src["width"],
                        src["y"] + ep["y"] * src["height"]))
        for w in wps:
            pts.append((w["x"], w["y"]))
        if tgt and np_:
            pts.append((tgt["x"] + np_["x"] * tgt["width"],
                        tgt["y"] + np_["y"] * tgt["height"]))
        if len(pts) < 2:
            # Fallback: midpoint between node centers
            pts = [(src["x"] + src["width"] / 2, src["y"] + src["height"] / 2),
                   (tgt["x"] + tgt["width"] / 2, tgt["y"] + tgt["height"] / 2)]
        # Find longest segment for label placement
        best_seg = 0
        best_len = 0
        for i in range(len(pts) - 1):
            dx = pts[i + 1][0] - pts[i][0]
            dy = pts[i + 1][1] - pts[i][1]
            seg_len = (dx * dx + dy * dy) ** 0.5
            if seg_len > best_len:
                best_len = seg_len
                best_seg = i
        lx = (pts[best_seg][0] + pts[best_seg + 1][0]) / 2
        ly = (pts[best_seg][1] + pts[best_seg + 1][1]) / 2
        lw = len(label) * label_char_width + label_padding * 2
        lh = label_height + label_padding * 2
        label_box = {"id": f"label({elem['from']}->{elem['to']})",
                     "x": lx - lw / 2, "y": ly - lh / 2, "w": lw, "h": lh}
        for box in boxes:
            if box["id"] in (elem["from"], elem["to"]):
                continue
            if _overlaps(label_box, box, margin=0):
                warnings.append(
                    f"Edge label collision: label \"{label}\" on "
                    f"{elem['from']}->{elem['to']} overlaps node {box['id']}"
                )
                break

    # Check for non-orthogonal segments and excessive bends.
    # Skip edges with no waypoints — draw.io's orthogonalEdgeStyle router
    # handles routing dynamically, so the exit→entry line being diagonal
    # is expected (draw.io renders it as an L-bend).
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
            errors.append(
                f"Non-orthogonal edge: {elem['from']}->{elem['to']} has "
                f"{diagonal_segs} diagonal segment(s). "
                f"Add waypoints so every segment is perfectly horizontal "
                f"or vertical."
            )

    # Edge style sanity: a full mxGraph style that sets a non-orthogonal
    # edgeStyle renders as a diagonal line and the renderer can't recover it
    # (unlike a bare type keyword, which render normalizes to orthogonal). Flag
    # only that unrecoverable case.
    for elem in elements:
        if elem.get("type") != "edge":
            continue
        style = elem.get("style", "")
        if "edgeStyle=" in style and "orthogonalEdgeStyle" not in style:
            errors.append(
                f"Edge style not orthogonal: {elem.get('from')}->{elem.get('to')} "
                f"sets a non-orthogonal edgeStyle. Use "
                f"edgeStyle=orthogonalEdgeStyle."
            )

    # Edge-preservation: every edge in the source spec must survive into the
    # layout plan (directly, or folded into a grouping container). Catches a
    # layout pass that drops edges wholesale (e.g. a diagram rendered with no
    # arrows at all).
    if spec and spec.get("edges"):
        plan_pairs = {(e.get("from"), e.get("to"))
                      for e in elements if e.get("type") == "edge"}
        parent_of = {}

        def _map_parents(cont):
            for ch in cont.get("children", []):
                cid = ch.get("id") if isinstance(ch, dict) else ch
                parent_of[cid] = cont["id"]
                if isinstance(ch, dict) and ch.get("children"):
                    _map_parents(ch)
        for elem in elements:
            if elem.get("type") == "container":
                _map_parents(elem)

        all_ids = {e["id"] for e in elements
                   if e.get("type", "node") in ("node", "container")}
        all_ids |= set(parent_of)

        def _covered(a, b):
            # direct, or via either endpoint's container (bundled edge)
            for x in (a, parent_of.get(a)):
                for y in (b, parent_of.get(b)):
                    if x and y and (x, y) in plan_pairs:
                        return True
            return False

        missing = [(e["from"], e["to"]) for e in spec["edges"]
                   if not e.get("is_back_edge")
                   and e["from"] in all_ids and e["to"] in all_ids
                   and not _covered(e["from"], e["to"])]
        if missing:
            errors.append(
                f"Dropped edges: {len(missing)} edge(s) from the graph spec are "
                f"missing in the layout plan, e.g. {missing[:5]}. The layout "
                f"must include every authored edge."
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

    # Auto-discover the graph spec next to the plan (both live in artifacts/),
    # or take an explicit --spec, to enable the edge-preservation check.
    spec = None
    spec_path = None
    if "--spec" in sys.argv:
        idx = sys.argv.index("--spec")
        if idx + 1 < len(sys.argv):
            spec_path = sys.argv[idx + 1]
    else:
        import os
        guess = os.path.join(os.path.dirname(os.path.abspath(sys.argv[1])),
                             "graph-spec.json")
        if os.path.exists(guess):
            spec_path = guess
    if spec_path:
        try:
            with open(spec_path) as f:
                spec = json.load(f)
        except (OSError, ValueError):
            spec = None

    result = validate(plan, spec)

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

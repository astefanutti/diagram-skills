#!/usr/bin/env python3
"""Programmatic post-processing for layout plans.

Three fix passes applied in sequence:
  1. Orthogonal waypoint snapping — insert corner waypoints for diagonal segments
  2. Node overlap resolution — iterative push-apart
  3. Edge-through-node rerouting — insert waypoints to route around obstructing nodes

Then re-run pass 1 to clean up diagonals introduced by pass 3.
"""

import json
import sys


# ---------------------------------------------------------------------------
# Geometry helpers (same logic as validate_layout.py, kept local to avoid
# import-path issues when the script is invoked standalone via CLI)
# ---------------------------------------------------------------------------

def _overlaps(a, b, margin=0):
    return not (
        a["x"] + a["w"] + margin <= b["x"]
        or b["x"] + b["w"] + margin <= a["x"]
        or a["y"] + a["h"] + margin <= b["y"]
        or b["y"] + b["h"] + margin <= a["y"]
    )


def _segment_intersects_box(x1, y1, x2, y2, box, margin=0):
    bx = box["x"] - margin
    by = box["y"] - margin
    bw = box["w"] + 2 * margin
    bh = box["h"] + 2 * margin

    for px, py in [(x1, y1), (x2, y2)]:
        if bx <= px <= bx + bw and by <= py <= by + bh:
            return True

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _collect_boxes(elements):
    """Build a list of node bounding boxes from the layout plan elements."""
    boxes = []
    container_ids = set()
    container_child_ids = set()
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
                    container_child_ids.add(child["id"])
                    boxes.append({
                        "id": child["id"],
                        "x": elem["x"] + child["rel_x"],
                        "y": elem["y"] + child["rel_y"],
                        "w": child["width"],
                        "h": child["height"],
                    })
    return boxes, container_ids, container_child_ids


def _node_geom_lookup(elements):
    """Build a dict of node/container geometry by ID."""
    geom = {}
    for elem in elements:
        if elem.get("type", "node") in ("node", "container"):
            geom[elem["id"]] = elem
    return geom


def _anchor_side(pt):
    """Return which box side an exit/entry point attaches to, or None.

    Returns 'top'/'bottom'/'left'/'right' for clean side anchors.
    Exact corners (both coords 0/1) return None — they are handled
    separately by fix_entry_exit.
    """
    x, y = pt.get("x"), pt.get("y")
    if y == 0 and x not in (0, 1):
        return "top"
    if y == 1 and x not in (0, 1):
        return "bottom"
    if x == 0 and y not in (0, 1):
        return "left"
    if x == 1 and y not in (0, 1):
        return "right"
    return None


def _edge_absolute_points(edge, node_geom):
    """Compute the full absolute point chain for an edge."""
    pts = []
    src = node_geom.get(edge["from"])
    tgt = node_geom.get(edge["to"])
    ep = edge.get("exit_point")
    np_ = edge.get("entry_point")

    if src and ep:
        pts.append({
            "x": src["x"] + ep["x"] * src["width"],
            "y": src["y"] + ep["y"] * src["height"],
        })

    for wp in (edge.get("waypoints") or []):
        pts.append({"x": wp["x"], "y": wp["y"]})

    if tgt and np_:
        pts.append({
            "x": tgt["x"] + np_["x"] * tgt["width"],
            "y": tgt["y"] + np_["y"] * tgt["height"],
        })

    return pts


# ---------------------------------------------------------------------------
# Pass 0a: Fix corner entry/exit points and tangential approaches
# ---------------------------------------------------------------------------

_PERPENDICULAR_OFFSET = 25


def fix_entry_exit(plan):
    """Fix corner entry/exit points and tangential edge approaches.

    Two sub-fixes:
    A) Corner anchors: entry/exit at exact corners (both coords 0 or 1)
       are snapped to the nearest side center based on approach direction.
    B) Tangential approach: when waypoints run along a node's edge instead
       of approaching perpendicularly, offset them to create a clean turn.
    """
    elements = plan.get("elements", [])
    node_geom = _node_geom_lookup(elements)
    fixes = 0

    for elem in elements:
        if elem.get("type") != "edge":
            continue

        src = node_geom.get(elem["from"])
        tgt = node_geom.get(elem["to"])
        ep = elem.get("exit_point")
        np_ = elem.get("entry_point")
        if not (src and tgt and ep and np_):
            continue

        wps = elem.get("waypoints") or []
        changed = False

        # --- Sub-fix A: Corner entry/exit points ---
        # Entry at a corner → snap to side center using node-center-to-
        # node-center direction (NOT waypoints, which were designed for
        # the wrong corner and give biased results).
        if np_["x"] in (0, 1) and np_["y"] in (0, 1):
            src_cx = src["x"] + src["width"] / 2
            src_cy = src["y"] + src["height"] / 2
            tgt_cx = tgt["x"] + tgt["width"] / 2
            tgt_cy = tgt["y"] + tgt["height"] / 2
            dx = abs(src_cx - tgt_cx)
            dy = abs(src_cy - tgt_cy)
            if dy >= dx:
                # Source is primarily above/below target → top or bottom
                np_["x"] = 0.5
            else:
                # Source is primarily left/right of target → left or right
                np_["y"] = 0.5

            # After changing entry, fix the last waypoint to approach
            # from the correct direction instead of crossing through
            # the target node.
            new_entry_x = tgt["x"] + np_["x"] * tgt["width"]
            new_entry_y = tgt["y"] + np_["y"] * tgt["height"]
            if wps:
                if np_["y"] == 1:
                    # Bottom entry → last wp below target
                    wps[-1] = {"x": new_entry_x,
                               "y": new_entry_y + _PERPENDICULAR_OFFSET}
                elif np_["y"] == 0:
                    # Top entry → last wp above target
                    wps[-1] = {"x": new_entry_x,
                               "y": new_entry_y - _PERPENDICULAR_OFFSET}
                elif np_["x"] == 1:
                    # Right entry → last wp right of target
                    wps[-1] = {"x": new_entry_x + _PERPENDICULAR_OFFSET,
                               "y": new_entry_y}
                elif np_["x"] == 0:
                    # Left entry → last wp left of target
                    wps[-1] = {"x": new_entry_x - _PERPENDICULAR_OFFSET,
                               "y": new_entry_y}
            changed = True

        # Exit at a corner → snap to side center
        if ep["x"] in (0, 1) and ep["y"] in (0, 1):
            src_cx = src["x"] + src["width"] / 2
            src_cy = src["y"] + src["height"] / 2
            tgt_cx = tgt["x"] + tgt["width"] / 2
            tgt_cy = tgt["y"] + tgt["height"] / 2
            dx = abs(tgt_cx - src_cx)
            dy = abs(tgt_cy - src_cy)
            if dy >= dx:
                ep["x"] = 0.5
            else:
                ep["y"] = 0.5

            new_exit_x = src["x"] + ep["x"] * src["width"]
            new_exit_y = src["y"] + ep["y"] * src["height"]
            if wps:
                if ep["y"] == 1:
                    wps[0] = {"x": new_exit_x,
                              "y": new_exit_y + _PERPENDICULAR_OFFSET}
                elif ep["y"] == 0:
                    wps[0] = {"x": new_exit_x,
                              "y": new_exit_y - _PERPENDICULAR_OFFSET}
                elif ep["x"] == 1:
                    wps[0] = {"x": new_exit_x + _PERPENDICULAR_OFFSET,
                              "y": new_exit_y}
                elif ep["x"] == 0:
                    wps[0] = {"x": new_exit_x - _PERPENDICULAR_OFFSET,
                              "y": new_exit_y}
            changed = True

        # --- Sub-fix B: Tangential approach ---
        # When waypoints run along a node edge instead of approaching
        # perpendicularly, offset the co-linear waypoints away from
        # the edge.
        if wps:
            entry_abs_y = tgt["y"] + np_["y"] * tgt["height"]
            entry_abs_x = tgt["x"] + np_["x"] * tgt["width"]

            if np_["y"] == 0:
                # Top entry: waypoints at the node's top y → push above
                node_top = tgt["y"]
                for wp in wps:
                    if abs(wp["y"] - node_top) < 5:
                        wp["y"] = node_top - _PERPENDICULAR_OFFSET
                        changed = True
            elif np_["y"] == 1:
                # Bottom entry: waypoints at the node's bottom y → push below
                node_bottom = tgt["y"] + tgt["height"]
                for wp in wps:
                    if abs(wp["y"] - node_bottom) < 5:
                        wp["y"] = node_bottom + _PERPENDICULAR_OFFSET
                        changed = True

            if np_["x"] == 0:
                # Left entry: waypoints at the node's left x → push left
                node_left = tgt["x"]
                for wp in wps:
                    if abs(wp["x"] - node_left) < 5:
                        wp["x"] = node_left - _PERPENDICULAR_OFFSET
                        changed = True
            elif np_["x"] == 1:
                # Right entry: waypoints at the node's right x → push right
                node_right = tgt["x"] + tgt["width"]
                for wp in wps:
                    if abs(wp["x"] - node_right) < 5:
                        wp["x"] = node_right + _PERPENDICULAR_OFFSET
                        changed = True

            # Same for exit side
            exit_abs_y = src["y"] + ep["y"] * src["height"]
            exit_abs_x = src["x"] + ep["x"] * src["width"]

            if ep["y"] == 0:
                node_top = src["y"]
                for wp in wps:
                    if abs(wp["y"] - node_top) < 5:
                        wp["y"] = node_top - _PERPENDICULAR_OFFSET
                        changed = True
            elif ep["y"] == 1:
                node_bottom = src["y"] + src["height"]
                for wp in wps:
                    if abs(wp["y"] - node_bottom) < 5:
                        wp["y"] = node_bottom + _PERPENDICULAR_OFFSET
                        changed = True

            if ep["x"] == 0:
                node_left = src["x"]
                for wp in wps:
                    if abs(wp["x"] - node_left) < 5:
                        wp["x"] = node_left - _PERPENDICULAR_OFFSET
                        changed = True
            elif ep["x"] == 1:
                node_right = src["x"] + src["width"]
                for wp in wps:
                    if abs(wp["x"] - node_right) < 5:
                        wp["x"] = node_right + _PERPENDICULAR_OFFSET
                        changed = True

        if changed:
            fixes += 1

    return fixes


# ---------------------------------------------------------------------------
# Pass 0a2: Redistribute near-corner anchors away from box corners
# ---------------------------------------------------------------------------

def fix_corner_anchors(plan, near=0.15, lo=0.3, hi=0.7):
    """Pull edge anchors that cluster near a box corner toward the side center.

    An anchor like exitY=1,exitX=0.05 attaches to the bottom edge but right
    at the left corner, which reads as a "corner connection." When two or
    more edges attach to the same side near a corner (common with
    bidirectional pairs), they cluster on top of each other. This pass
    redistributes all anchors on an affected side evenly across the central
    band [lo, hi], preserving their order, and updates the adjacent waypoint
    so the connection stays orthogonal.
    """
    elements = plan.get("elements", [])
    node_geom = _node_geom_lookup(elements)

    # Group anchors by (box_id, side)
    groups = {}
    for elem in elements:
        if elem.get("type") != "edge":
            continue
        ep = elem.get("exit_point")
        np_ = elem.get("entry_point")
        if ep:
            side = _anchor_side(ep)
            if side:
                groups.setdefault((elem["from"], side), []).append(
                    (elem, "exit"))
        if np_:
            side = _anchor_side(np_)
            if side:
                groups.setdefault((elem["to"], side), []).append(
                    (elem, "entry"))

    def _frac(elem, role, side):
        pt = elem["exit_point"] if role == "exit" else elem["entry_point"]
        return pt["x"] if side in ("top", "bottom") else pt["y"]

    fixes = 0
    for (box_id, side), members in groups.items():
        # Only act on clustered pairs (the "two arrows at a corner" case).
        # A single near-corner anchor is often intentional (fan-out offset).
        if len(members) < 2:
            continue
        # At least one anchor must sit near a corner
        if not any(_frac(e, r, side) <= near or _frac(e, r, side) >= 1 - near
                   for e, r in members):
            continue

        box = node_geom.get(box_id)
        if not box:
            continue

        members_sorted = sorted(members, key=lambda m: _frac(m[0], m[1], side))
        n = len(members_sorted)
        targets = [lo + (hi - lo) * i / (n - 1) for i in range(n)]

        for (elem, role), t in zip(members_sorted, targets):
            pt = elem["exit_point"] if role == "exit" else elem["entry_point"]
            if abs(_frac(elem, role, side) - t) < 1e-6:
                continue
            if side in ("top", "bottom"):
                pt["x"] = t
            else:
                pt["y"] = t

            # Update the adjacent waypoint so the segment stays orthogonal
            wps = elem.get("waypoints") or []
            if wps:
                wp = wps[0] if role == "exit" else wps[-1]
                if side in ("top", "bottom"):
                    wp["x"] = box["x"] + pt["x"] * box["width"]
                else:
                    wp["y"] = box["y"] + pt["y"] * box["height"]
            fixes += 1

    return fixes


# ---------------------------------------------------------------------------
# Pass 0b: Anchor alignment — snap waypoints near exit/entry points
# ---------------------------------------------------------------------------

def fix_anchor_alignment(plan, threshold=10):
    """Snap first/last waypoints to align with exit/entry absolute coords.

    When a waypoint is within `threshold` px of the exit/entry point on one
    axis, snap that axis to match exactly. This eliminates subtle diagonals
    caused by fractional anchor positions (e.g., entryY=0.75 → y=312.5 but
    waypoint at y=308).
    """
    elements = plan.get("elements", [])
    node_geom = _node_geom_lookup(elements)
    fixes = 0

    for elem in elements:
        if elem.get("type") != "edge":
            continue

        wps = elem.get("waypoints")
        if not wps:
            continue

        src = node_geom.get(elem["from"])
        tgt = node_geom.get(elem["to"])
        ep = elem.get("exit_point")
        np_ = elem.get("entry_point")
        if not (src and tgt and ep and np_):
            continue

        exit_abs_x = src["x"] + ep["x"] * src["width"]
        exit_abs_y = src["y"] + ep["y"] * src["height"]
        entry_abs_x = tgt["x"] + np_["x"] * tgt["width"]
        entry_abs_y = tgt["y"] + np_["y"] * tgt["height"]

        changed = False

        # Snap first waypoint to exit point
        first = wps[0]
        dx = abs(first["x"] - exit_abs_x)
        dy = abs(first["y"] - exit_abs_y)
        if 0 < dx <= threshold and dy > dx:
            first["x"] = exit_abs_x
            changed = True
        if 0 < dy <= threshold and dx > dy:
            first["y"] = exit_abs_y
            changed = True

        # Snap last waypoint to entry point
        last = wps[-1]
        dx = abs(last["x"] - entry_abs_x)
        dy = abs(last["y"] - entry_abs_y)
        if 0 < dx <= threshold and dy > dx:
            last["x"] = entry_abs_x
            changed = True
        if 0 < dy <= threshold and dx > dy:
            last["y"] = entry_abs_y
            changed = True

        if changed:
            fixes += 1

    return fixes


# ---------------------------------------------------------------------------
# Pass 1: Orthogonal waypoint snapping
# ---------------------------------------------------------------------------

def fix_orthogonal(plan):
    """Insert corner waypoints wherever consecutive points form a diagonal."""
    elements = plan.get("elements", [])
    node_geom = _node_geom_lookup(elements)
    boxes, _, _ = _collect_boxes(elements)
    fixes = 0

    # Build container parent map for skip logic in corner collision checks
    container_children_map = {}
    for elem in elements:
        if elem.get("type") == "container":
            for child in elem.get("children", []):
                child_id = child.get("id", child) if isinstance(child, dict) else child
                container_children_map[child_id] = elem["id"]

    for elem in elements:
        if elem.get("type") != "edge":
            continue

        src = node_geom.get(elem["from"])
        tgt = node_geom.get(elem["to"])
        ep = elem.get("exit_point")
        np_ = elem.get("entry_point")
        if not (src and tgt and ep and np_):
            continue

        wps = list(elem.get("waypoints") or [])

        # Build absolute point chain: exit → waypoints → entry
        exit_abs = {
            "x": src["x"] + ep["x"] * src["width"],
            "y": src["y"] + ep["y"] * src["height"],
        }
        entry_abs = {
            "x": tgt["x"] + np_["x"] * tgt["width"],
            "y": tgt["y"] + np_["y"] * tgt["height"],
        }

        all_pts = [exit_abs] + wps + [entry_abs]
        new_wps = []
        changed = False

        connected_ids = {elem["from"], elem["to"]}
        src_parent = container_children_map.get(elem["from"])
        tgt_parent = container_children_map.get(elem["to"])
        if src_parent and src_parent == tgt_parent:
            connected_ids.add(src_parent)

        for i in range(len(all_pts) - 1):
            p = all_pts[i]
            q = all_pts[i + 1]

            # Don't re-emit the exit point (index 0) — it's implicit
            if i > 0:
                new_wps.append({"x": p["x"], "y": p["y"]})

            dx = abs(q["x"] - p["x"])
            dy = abs(q["y"] - p["y"])

            if dx > 1 and dy > 1:
                # Diagonal detected — insert an L-bend corner
                # Option A: (p.x, q.y) — horizontal then vertical
                # Option B: (q.x, p.y) — vertical then horizontal
                corner_a = {"x": p["x"], "y": q["y"]}
                corner_b = {"x": q["x"], "y": p["y"]}
                # Pick the corner that doesn't cross any node
                a_clear = True
                b_clear = True
                for box in boxes:
                    if box["id"] in connected_ids:
                        continue
                    if _segment_intersects_box(
                        p["x"], p["y"], corner_a["x"], corner_a["y"], box
                    ) or _segment_intersects_box(
                        corner_a["x"], corner_a["y"], q["x"], q["y"], box
                    ):
                        a_clear = False
                    if _segment_intersects_box(
                        p["x"], p["y"], corner_b["x"], corner_b["y"], box
                    ) or _segment_intersects_box(
                        corner_b["x"], corner_b["y"], q["x"], q["y"], box
                    ):
                        b_clear = False

                corner = corner_a if a_clear else corner_b if b_clear else corner_a
                new_wps.append(corner)
                changed = True

        if changed:
            elem["waypoints"] = new_wps
            fixes += 1

    return fixes


def _check_nudge_safe(new_box, boxes, container_ids, container_child_ids,
                      edge_segments, margin=10, clearance=15):
    """Check if a nudged node position is safe: no overlaps, no near-misses."""
    for box in boxes:
        if box["id"] == new_box["id"]:
            continue
        if box["id"] in container_ids and \
           new_box["id"] in container_child_ids:
            continue
        if new_box["id"] in container_ids and \
           box["id"] in container_child_ids:
            continue
        if _overlaps(new_box, box, margin):
            return False

    # Check if any edge now passes too close to the nudged node
    for eid, sx1, sy1, sx2, sy2 in edge_segments:
        src_id, _, tgt_id = eid.partition("->")
        if new_box["id"] in (src_id, tgt_id):
            continue
        if _segment_intersects_box(sx1, sy1, sx2, sy2,
                                   new_box, margin=clearance):
            return False
    return True


# ---------------------------------------------------------------------------
# Pass 1b: Node alignment for straight connections
# ---------------------------------------------------------------------------

def fix_node_alignment(plan, threshold=20):
    """Nudge nearly-aligned nodes so simple edges become straight lines.

    When two nodes are connected by a single edge with exit/entry at
    matching sides (e.g., bottom→top), and their anchor points are
    within `threshold` px on the perpendicular axis, nudge the smaller
    node to align. Then remove any waypoints that were only there to
    handle the offset.
    """
    elements = plan.get("elements", [])
    node_geom = _node_geom_lookup(elements)

    # Count edges per node to identify nodes with few connections
    # (safer to move without cascading issues)
    edge_count = {}
    for elem in elements:
        if elem.get("type") == "edge":
            edge_count[elem["from"]] = edge_count.get(elem["from"], 0) + 1
            edge_count[elem["to"]] = edge_count.get(elem["to"], 0) + 1

    boxes, container_ids, container_child_ids = _collect_boxes(elements)
    margin = 10

    # Collect all edge segments for near-miss checking after nudges
    all_edge_segments = []
    for e in elements:
        if e.get("type") != "edge":
            continue
        src_n = node_geom.get(e["from"])
        tgt_n = node_geom.get(e["to"])
        ep_ = e.get("exit_point")
        np__ = e.get("entry_point")
        if not (src_n and tgt_n and ep_ and np__):
            continue
        pts = []
        pts.append({"x": src_n["x"] + ep_["x"] * src_n["width"],
                     "y": src_n["y"] + ep_["y"] * src_n["height"]})
        for w in (e.get("waypoints") or []):
            pts.append(w)
        pts.append({"x": tgt_n["x"] + np__["x"] * tgt_n["width"],
                     "y": tgt_n["y"] + np__["y"] * tgt_n["height"]})
        eid = f"{e['from']}->{e['to']}"
        for j in range(len(pts) - 1):
            all_edge_segments.append(
                (eid, pts[j]["x"], pts[j]["y"],
                 pts[j + 1]["x"], pts[j + 1]["y"]))

    fixes = 0

    for elem in elements:
        if elem.get("type") != "edge":
            continue

        src = node_geom.get(elem["from"])
        tgt = node_geom.get(elem["to"])
        ep = elem.get("exit_point")
        np_ = elem.get("entry_point")
        if not (src and tgt and ep and np_):
            continue

        # Only handle straight-through connections:
        # bottom→top (exitY=1, entryY=0) or right→left (exitX=1, entryX=0)
        is_vertical = (ep.get("y") == 1 and np_.get("y") == 0 and
                       ep.get("x") == 0.5 and np_.get("x") == 0.5)
        is_horizontal = (ep.get("x") == 1 and np_.get("x") == 0 and
                         ep.get("y") == 0.5 and np_.get("y") == 0.5)

        if not (is_vertical or is_horizontal):
            continue

        if is_vertical:
            exit_x = src["x"] + ep["x"] * src["width"]
            entry_x = tgt["x"] + np_["x"] * tgt["width"]
            offset = exit_x - entry_x

            if 0 < abs(offset) <= threshold:
                src_edges = edge_count.get(elem["from"], 0)
                tgt_edges = edge_count.get(elem["to"], 0)
                if tgt_edges <= src_edges:
                    node_to_move = tgt
                    delta = offset
                else:
                    node_to_move = src
                    delta = -offset

                # Trial move: check for overlaps and edge near-misses
                old_x = node_to_move["x"]
                node_to_move["x"] += delta
                new_box = {"id": node_to_move["id"],
                           "x": node_to_move["x"], "y": node_to_move["y"],
                           "w": node_to_move["width"],
                           "h": node_to_move["height"]}
                safe = _check_nudge_safe(new_box, boxes,
                                         container_ids, container_child_ids,
                                         all_edge_segments, margin)
                if not safe:
                    node_to_move["x"] = old_x
                else:
                    elem["waypoints"] = []
                    fixes += 1

        elif is_horizontal:
            exit_y = src["y"] + ep["y"] * src["height"]
            entry_y = tgt["y"] + np_["y"] * tgt["height"]
            offset = exit_y - entry_y

            if 0 < abs(offset) <= threshold:
                src_edges = edge_count.get(elem["from"], 0)
                tgt_edges = edge_count.get(elem["to"], 0)
                if tgt_edges <= src_edges:
                    node_to_move = tgt
                    delta = offset
                else:
                    node_to_move = src
                    delta = -offset

                old_y = node_to_move["y"]
                node_to_move["y"] += delta
                new_box = {"id": node_to_move["id"],
                           "x": node_to_move["x"], "y": node_to_move["y"],
                           "w": node_to_move["width"],
                           "h": node_to_move["height"]}
                safe = _check_nudge_safe(new_box, boxes,
                                         container_ids, container_child_ids,
                                         all_edge_segments, margin)
                if not safe:
                    node_to_move["y"] = old_y
                else:
                    elem["waypoints"] = []
                    fixes += 1

    return fixes


# ---------------------------------------------------------------------------
# Pass 1c: Container layout — equalize children and tighten bounds
# ---------------------------------------------------------------------------

def fix_container_layout(plan, bottom_pad=18, side_pad=18):
    """Tidy container interiors: equalize child sizes and hug the bounds.

    Ragged child heights leave empty gaps below the shorter ones, and a
    loose container leaves a band of empty space. For row-laid-out
    children, equalize heights to the max and align them; for columns,
    equalize widths. Then shrink the container to fit with uniform
    padding. Only shrinks (never grows) so it can't create new overlaps.
    """
    elements = plan.get("elements", [])
    fixes = 0

    for elem in elements:
        if elem.get("type") != "container":
            continue
        children = elem.get("children", [])
        if len(children) < 2:
            continue

        # Classify layout: row (side by side) vs column (stacked)
        xs = sorted(children, key=lambda c: c["rel_x"])
        row = all(
            xs[i]["rel_x"] + xs[i]["width"] <= xs[i + 1]["rel_x"] + 1
            for i in range(len(xs) - 1)
        )
        ys = sorted(children, key=lambda c: c["rel_y"])
        column = all(
            ys[i]["rel_y"] + ys[i]["height"] <= ys[i + 1]["rel_y"] + 1
            for i in range(len(ys) - 1)
        )

        top_band = min(c["rel_y"] for c in children)
        left_band = min(c["rel_x"] for c in children)

        if row and not column:
            # Equalize heights, align to the top band
            max_h = max(c["height"] for c in children)
            required_h = top_band + max_h + bottom_pad
            if required_h <= elem["height"] + 1:
                for c in children:
                    c["rel_y"] = top_band
                    c["height"] = max_h
                elem["height"] = required_h
                # Hug width to the rightmost child
                right = max(c["rel_x"] + c["width"] for c in children)
                new_w = right + left_band
                if new_w <= elem["width"] + 1:
                    elem["width"] = new_w
                fixes += 1

        elif column and not row:
            # Equalize widths, align to the left band
            max_w = max(c["width"] for c in children)
            required_w = left_band + max_w + side_pad
            if required_w <= elem["width"] + 1:
                for c in children:
                    c["rel_x"] = left_band
                    c["width"] = max_w
                elem["width"] = required_w
                bottom = max(c["rel_y"] + c["height"] for c in children)
                new_h = bottom + top_band
                if new_h <= elem["height"] + 1:
                    elem["height"] = new_h
                fixes += 1

    return fixes


# ---------------------------------------------------------------------------
# Pass 2: Node overlap resolution
# ---------------------------------------------------------------------------

def fix_overlaps(plan, margin=10, max_iters=50):
    """Push overlapping nodes apart iteratively."""
    elements = plan.get("elements", [])
    canvas = plan.get("canvas", {"width": 1920, "height": 1080})
    container_ids = set()
    container_child_ids = set()

    for elem in elements:
        if elem.get("type") == "container":
            container_ids.add(elem["id"])
            for child in elem.get("children", []):
                container_child_ids.add(child["id"])

    # Build index: id → element reference (for direct mutation)
    elem_by_id = {}
    for elem in elements:
        if elem.get("type", "node") in ("node", "container"):
            elem_by_id[elem["id"]] = elem

    fixes = 0

    for _ in range(max_iters):
        moved = False
        node_elems = [e for e in elements
                      if e.get("type", "node") in ("node", "container")]

        for i, a in enumerate(node_elems):
            for b in node_elems[i + 1:]:
                # Skip container-child pairs
                if a["id"] in container_ids and b["id"] in container_child_ids:
                    continue
                if b["id"] in container_ids and a["id"] in container_child_ids:
                    continue

                box_a = {"x": a["x"], "y": a["y"],
                         "w": a["width"], "h": a["height"]}
                box_b = {"x": b["x"], "y": b["y"],
                         "w": b["width"], "h": b["height"]}

                if not _overlaps(box_a, box_b, margin):
                    continue

                # Compute overlap on each axis
                overlap_x = (
                    min(a["x"] + a["width"], b["x"] + b["width"])
                    - max(a["x"], b["x"]) + margin
                )
                overlap_y = (
                    min(a["y"] + a["height"], b["y"] + b["height"])
                    - max(a["y"], b["y"]) + margin
                )

                if overlap_x <= 0 or overlap_y <= 0:
                    continue

                # Push apart along axis of least overlap
                if overlap_x < overlap_y:
                    shift = overlap_x / 2 + 1
                    if a["x"] <= b["x"]:
                        a["x"] -= shift
                        b["x"] += shift
                    else:
                        a["x"] += shift
                        b["x"] -= shift
                else:
                    shift = overlap_y / 2 + 1
                    if a["y"] <= b["y"]:
                        a["y"] -= shift
                        b["y"] += shift
                    else:
                        a["y"] += shift
                        b["y"] -= shift

                moved = True
                fixes += 1

        if not moved:
            break

    # Clamp nodes to positive coordinates, expand canvas if needed
    max_right = 0
    max_bottom = 0
    for elem in elements:
        if elem.get("type", "node") not in ("node", "container"):
            continue
        if elem["x"] < 0:
            elem["x"] = 30  # canvas margin
        if elem["y"] < 0:
            elem["y"] = 30
        max_right = max(max_right, elem["x"] + elem["width"])
        max_bottom = max(max_bottom, elem["y"] + elem["height"])

    if max_right + 30 > canvas.get("width", 1920):
        canvas["width"] = int(max_right + 60)
        plan["canvas"] = canvas
    if max_bottom + 30 > canvas.get("height", 1080):
        canvas["height"] = int(max_bottom + 60)
        plan["canvas"] = canvas

    return fixes


# ---------------------------------------------------------------------------
# Pass 3: Edge-through-node rerouting
# ---------------------------------------------------------------------------

def fix_edge_through_node(plan, clearance=20):
    """Insert waypoints to route edges around obstructing nodes."""
    elements = plan.get("elements", [])
    node_geom = _node_geom_lookup(elements)
    boxes, _, _ = _collect_boxes(elements)

    # Build container parent map for skip logic
    container_children = {}
    for elem in elements:
        if elem.get("type") == "container":
            for child in elem.get("children", []):
                child_id = child.get("id", child) if isinstance(child, dict) else child
                container_children[child_id] = elem["id"]

    fixes = 0

    for elem in elements:
        if elem.get("type") != "edge":
            continue

        src = node_geom.get(elem["from"])
        tgt = node_geom.get(elem["to"])
        ep = elem.get("exit_point")
        np_ = elem.get("entry_point")
        if not (src and tgt and ep and np_):
            continue

        connected_ids = {elem["from"], elem["to"]}
        # Skip the parent container if both source and target are its children
        src_parent = container_children.get(elem["from"])
        tgt_parent = container_children.get(elem["to"])
        if src_parent and src_parent == tgt_parent:
            connected_ids.add(src_parent)
        wps = list(elem.get("waypoints") or [])

        exit_abs = {
            "x": src["x"] + ep["x"] * src["width"],
            "y": src["y"] + ep["y"] * src["height"],
        }
        entry_abs = {
            "x": tgt["x"] + np_["x"] * tgt["width"],
            "y": tgt["y"] + np_["y"] * tgt["height"],
        }

        all_pts = [exit_abs] + wps + [entry_abs]

        # Check each segment for collisions and collect obstructors
        rerouted = False
        new_wps = []

        for i in range(len(all_pts) - 1):
            p = all_pts[i]
            q = all_pts[i + 1]

            if i > 0:
                new_wps.append({"x": p["x"], "y": p["y"]})

            # Find obstructing nodes for this segment
            obstructor = None
            for box in boxes:
                if box["id"] in connected_ids:
                    continue
                parent_id = container_children.get(box["id"])
                if parent_id and parent_id in connected_ids:
                    continue
                if _segment_intersects_box(
                    p["x"], p["y"], q["x"], q["y"], box, margin=0
                ):
                    obstructor = box
                    break

            if obstructor:
                # Route around: decide above or below
                node_center_y = obstructor["y"] + obstructor["h"] / 2
                edge_mid_y = (p["y"] + q["y"]) / 2

                if edge_mid_y <= node_center_y:
                    route_y = obstructor["y"] - clearance
                else:
                    route_y = obstructor["y"] + obstructor["h"] + clearance

                left_wp = {
                    "x": obstructor["x"] - clearance,
                    "y": route_y,
                }
                right_wp = {
                    "x": obstructor["x"] + obstructor["w"] + clearance,
                    "y": route_y,
                }

                # Order waypoints to match the edge's travel direction
                if p["x"] <= q["x"]:
                    bypass = [left_wp, right_wp]
                else:
                    bypass = [right_wp, left_wp]

                # Verify the bypass doesn't cross any other node
                bypass_safe = True
                bypass_pts = [p] + bypass + [q]
                for bi in range(len(bypass_pts) - 1):
                    bp = bypass_pts[bi]
                    bq = bypass_pts[bi + 1]
                    for box in boxes:
                        if box["id"] in connected_ids:
                            continue
                        parent_id = container_children.get(box["id"])
                        if parent_id and parent_id in connected_ids:
                            continue
                        if _segment_intersects_box(
                            bp["x"], bp["y"], bq["x"], bq["y"], box, margin=0
                        ):
                            bypass_safe = False
                            break
                    if not bypass_safe:
                        break

                if bypass_safe:
                    new_wps.extend(bypass)
                    rerouted = True

        if rerouted:
            elem["waypoints"] = new_wps
            fixes += 1

    return fixes


# ---------------------------------------------------------------------------
# Pass 4: Spike removal — eliminate direction reversals
# ---------------------------------------------------------------------------

def fix_spikes(plan, axis_threshold=3):
    """Remove waypoints that create direction-reversal spikes.

    A spike occurs when three consecutive colinear points (same x or y
    within threshold) reverse direction: e.g., going UP then DOWN on
    the same x. Removing the middle point eliminates the spike.
    """
    elements = plan.get("elements", [])
    node_geom = _node_geom_lookup(elements)
    fixes = 0

    for elem in elements:
        if elem.get("type") != "edge":
            continue

        wps = elem.get("waypoints")
        if not wps or len(wps) < 2:
            continue

        src = node_geom.get(elem["from"])
        tgt = node_geom.get(elem["to"])
        ep = elem.get("exit_point")
        np_ = elem.get("entry_point")
        if not (src and tgt and ep and np_):
            continue

        exit_abs = {
            "x": src["x"] + ep["x"] * src["width"],
            "y": src["y"] + ep["y"] * src["height"],
        }
        entry_abs = {
            "x": tgt["x"] + np_["x"] * tgt["width"],
            "y": tgt["y"] + np_["y"] * tgt["height"],
        }

        changed = True
        while changed:
            changed = False
            all_pts = [exit_abs] + list(wps) + [entry_abs]

            for i in range(1, len(all_pts) - 1):
                if i - 1 < 0 or i + 1 >= len(all_pts):
                    break
                a = all_pts[i - 1]
                b = all_pts[i]
                c = all_pts[i + 1]

                # Check vertical spike: same x, y reverses
                if abs(a["x"] - b["x"]) <= axis_threshold and \
                   abs(b["x"] - c["x"]) <= axis_threshold:
                    min_y = min(a["y"], c["y"])
                    max_y = max(a["y"], c["y"])
                    if b["y"] < min_y - 1 or b["y"] > max_y + 1:
                        # b is outside the y range of a and c — spike
                        wp_idx = i - 1  # index into wps array
                        if 0 <= wp_idx < len(wps):
                            wps.pop(wp_idx)
                            changed = True
                            fixes += 1
                            break

                # Check horizontal spike: same y, x reverses
                if abs(a["y"] - b["y"]) <= axis_threshold and \
                   abs(b["y"] - c["y"]) <= axis_threshold:
                    min_x = min(a["x"], c["x"])
                    max_x = max(a["x"], c["x"])
                    if b["x"] < min_x - 1 or b["x"] > max_x + 1:
                        wp_idx = i - 1
                        if 0 <= wp_idx < len(wps):
                            wps.pop(wp_idx)
                            changed = True
                            fixes += 1
                            break

    return fixes


# ---------------------------------------------------------------------------
# Pass 5: Strip redundant waypoints for editability
# ---------------------------------------------------------------------------

def fix_strip_waypoints(plan):
    """Remove waypoints that draw.io's orthogonal router handles automatically.

    draw.io's orthogonalEdgeStyle computes L-bend and S-bend routes between
    pinned exit/entry anchors. Explicit waypoints for these simple routes
    prevent nodes from being moved freely (waypoints are absolute coordinates
    that don't follow node moves). Strip them so the diagram is editable.

    Keeps waypoints for: back-edges, 3+ bend routes, edges that route around
    nodes.
    """
    elements = plan.get("elements", [])
    node_geom = _node_geom_lookup(elements)
    boxes, _, _ = _collect_boxes(elements)
    fixes = 0

    for elem in elements:
        if elem.get("type") != "edge":
            continue

        wps = elem.get("waypoints")
        if not wps:
            continue

        # Keep waypoints on back-edges (they need explicit exterior routing)
        style = elem.get("style", "")
        if "dashed=1" in style:
            continue

        src = node_geom.get(elem["from"])
        tgt = node_geom.get(elem["to"])
        ep = elem.get("exit_point")
        np_ = elem.get("entry_point")
        if not (src and tgt and ep and np_):
            continue

        # Count bends in the waypoint path
        exit_abs = {
            "x": src["x"] + ep["x"] * src["width"],
            "y": src["y"] + ep["y"] * src["height"],
        }
        entry_abs = {
            "x": tgt["x"] + np_["x"] * tgt["width"],
            "y": tgt["y"] + np_["y"] * tgt["height"],
        }
        all_pts = [exit_abs] + list(wps) + [entry_abs]

        bends = 0
        for i in range(1, len(all_pts) - 1):
            p = all_pts[i - 1]
            c = all_pts[i]
            n = all_pts[i + 1]
            # A bend occurs when direction changes axis
            seg1_horiz = abs(c["y"] - p["y"]) < abs(c["x"] - p["x"])
            seg2_horiz = abs(n["y"] - c["y"]) < abs(n["x"] - c["x"])
            if seg1_horiz != seg2_horiz:
                bends += 1

        # draw.io handles 0-2 bend routes automatically
        if bends > 2:
            continue

        # Only strip if draw.io can route this cleanly:
        # 1) Already a straight line (aligned on one axis), or
        # 2) An L-bend where both segments are clear of nodes
        connected = {elem["from"], elem["to"]}
        ex, ey = exit_abs["x"], exit_abs["y"]
        nx, ny = entry_abs["x"], entry_abs["y"]

        can_strip = False

        if abs(ex - nx) <= 1 or abs(ey - ny) <= 1:
            # Straight line — draw.io handles trivially
            can_strip = True
        else:
            # Check both L-bend options
            # Option A: horizontal then vertical (corner at entry_x, exit_y)
            # Option B: vertical then horizontal (corner at exit_x, entry_y)
            for cx, cy in [(nx, ey), (ex, ny)]:
                clear = True
                for box in boxes:
                    if box["id"] in connected:
                        continue
                    if _segment_intersects_box(ex, ey, cx, cy, box, 0) or \
                       _segment_intersects_box(cx, cy, nx, ny, box, 0):
                        clear = False
                        break
                if clear:
                    can_strip = True
                    break

        if can_strip:
            elem["waypoints"] = []
            fixes += 1

    return fixes


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _run_passes(plan, corner_anchors=True):
    """Run the full fix pipeline on a plan. Returns a summary dict."""
    summary = {}

    # Tidy container interiors first — child moves affect edge anchors
    summary["container_layout"] = fix_container_layout(plan)
    summary["entry_exit"] = fix_entry_exit(plan)
    if corner_anchors:
        summary["corner_anchors"] = fix_corner_anchors(plan)
    summary["anchor_alignment"] = fix_anchor_alignment(plan)
    summary["orthogonal_pass1"] = fix_orthogonal(plan)
    summary["spikes_pass1"] = fix_spikes(plan)
    summary["node_alignment"] = fix_node_alignment(plan)
    summary["overlaps"] = fix_overlaps(plan)
    summary["rerouted_edges"] = fix_edge_through_node(plan)
    # Re-run all edge fixes after rerouting
    summary["entry_exit_pass2"] = fix_entry_exit(plan)
    if corner_anchors:
        summary["corner_anchors_pass2"] = fix_corner_anchors(plan)
    summary["anchor_alignment_pass2"] = fix_anchor_alignment(plan)
    summary["orthogonal_pass2"] = fix_orthogonal(plan)
    summary["spikes_pass2"] = fix_spikes(plan)
    # Strip redundant waypoints last — makes edges editable in draw.io
    summary["strip_waypoints"] = fix_strip_waypoints(plan)
    return summary


def _count_issues(plan):
    """Count validator errors + warnings for a plan."""
    try:
        from validate_layout import validate
    except ImportError:
        import os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from validate_layout import validate
    result = validate(plan)
    return len(result.get("errors", [])) + len(result.get("warnings", []))


def fix(plan):
    """Apply all fix passes and return a summary.

    The corner-anchor redistribution can occasionally trade a cosmetic
    win (arrows off the box corners) for a real defect (a new crossing).
    The validator doesn't score near-corner anchors, so we run the whole
    pipeline both with and without that pass and keep whichever yields
    fewer validator issues — ties go to the corner-anchor version, which
    preserves the cosmetic improvement at no measurable cost.
    """
    import copy

    plan_with = copy.deepcopy(plan)
    summary_with = _run_passes(plan_with, corner_anchors=True)
    issues_with = _count_issues(plan_with)

    plan_without = copy.deepcopy(plan)
    summary_without = _run_passes(plan_without, corner_anchors=False)
    issues_without = _count_issues(plan_without)

    if issues_with <= issues_without:
        chosen, summary = plan_with, summary_with
    else:
        chosen, summary = plan_without, summary_without

    plan.clear()
    plan.update(chosen)

    summary["total"] = sum(summary.values())
    return summary


def main():
    if len(sys.argv) < 2:
        print("Usage: fix_layout.py <layout-plan.json> [--output <path>]",
              file=sys.stderr)
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = input_path
    if "--output" in sys.argv:
        idx = sys.argv.index("--output")
        if idx + 1 < len(sys.argv):
            output_path = sys.argv[idx + 1]

    with open(input_path) as f:
        plan = json.load(f)

    summary = fix(plan)

    with open(output_path, "w") as f:
        json.dump(plan, f, indent=2)

    if summary["total"] > 0:
        print(f"Fixed: {summary}", file=sys.stderr)
    else:
        print("No fixes needed", file=sys.stderr)

    json.dump(summary, sys.stdout, indent=2)


if __name__ == "__main__":
    main()

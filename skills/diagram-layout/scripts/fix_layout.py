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
    """Build a list of node bounding boxes from the layout plan elements.

    Recurses through nested containers, composing absolute coordinates
    (``abs = parent_abs + child.rel``) so edge-clearance and through-node
    checks account for nodes at every nesting depth. Any box with children is
    a container; every descendant id (including an intermediate container that
    is itself a child) lands in ``container_child_ids``.
    """
    boxes = []
    container_ids = set()
    container_child_ids = set()

    def _walk(elem, abs_x, abs_y):
        boxes.append({
            "id": elem["id"],
            "x": abs_x,
            "y": abs_y,
            "w": elem["width"],
            "h": elem["height"],
        })
        children = elem.get("children", [])
        if children:
            container_ids.add(elem["id"])
            for child in children:
                container_child_ids.add(child["id"])
                _walk(child, abs_x + child["rel_x"], abs_y + child["rel_y"])

    for elem in elements:
        if elem.get("type", "node") in ("node", "container"):
            _walk(elem, elem["x"], elem["y"])
    return boxes, container_ids, container_child_ids


def _node_geom_lookup(elements):
    """Map node/container id → geometry (absolute coords), including nesting.

    Top-level elements map to themselves (mutable). Nested container children
    map to a read-only proxy carrying absolute coordinates (composed down the
    parent chain) plus width/height/style, so edge-routing passes can anchor
    and route edges that touch a nested child. Node-moving passes iterate
    `elements` (top-level only), so they never reposition a nested child here.
    """
    geom = {}

    def _walk(elem, abs_x, abs_y, top_level):
        if top_level:
            geom[elem["id"]] = elem
        else:
            geom[elem["id"]] = {
                "id": elem["id"], "x": abs_x, "y": abs_y,
                "width": elem["width"], "height": elem["height"],
                "style": elem.get("style", ""),
            }
        for child in elem.get("children", []):
            _walk(child, abs_x + child["rel_x"], abs_y + child["rel_y"], False)

    for elem in elements:
        if elem.get("type", "node") in ("node", "container"):
            _walk(elem, elem["x"], elem["y"], True)
    return geom


def _ancestor_map(elements):
    """Map each nested node id → list of its ancestor container ids (inner→outer)."""
    anc = {}

    def _walk(elem, chain):
        for child in elem.get("children", []):
            cid = child["id"]
            anc[cid] = chain
            _walk(child, [cid] + chain)

    for elem in elements:
        if elem.get("type", "node") in ("node", "container"):
            _walk(elem, [elem["id"]])
    return anc


def _descendant_map(elements):
    """Map each container id → set of all descendant ids (any depth)."""
    desc = {}

    def _walk(elem):
        ids = set()
        for child in elem.get("children", []):
            ids.add(child["id"])
            ids |= _walk(child)
        if ids:
            desc[elem["id"]] = ids
        return ids

    for elem in elements:
        if elem.get("type", "node") in ("node", "container"):
            _walk(elem)
    return desc


def _edge_skip_ids(from_id, to_id, anc, desc):
    """Boxes an edge must not treat as obstacles: its endpoints, every container
    enclosing an endpoint (the edge crosses their borders), and — when an
    endpoint is itself a container — that container's descendants (the bundled
    edge leaves from the container's border, not its interior nodes)."""
    skip = {from_id, to_id}
    skip.update(anc.get(from_id, ()))
    skip.update(anc.get(to_id, ()))
    skip.update(desc.get(from_id, ()))
    skip.update(desc.get(to_id, ()))
    return skip


# A rhombus (decision node) only touches its bounding box at the four
# edge-midpoints — its vertices. Each is paired with its outward unit
# direction so an anchor can be matched to the vertex pointing at the other
# endpoint.
_DIAMOND_VERTS = [
    ((0.5, 0.0), (0.0, -1.0)),  # top
    ((0.5, 1.0), (0.0, 1.0)),   # bottom
    ((0.0, 0.5), (-1.0, 0.0)),  # left
    ((1.0, 0.5), (1.0, 0.0)),   # right
]


def _is_diamond(geom):
    """True if a node's style marks it a decision (rhombus) shape."""
    return geom is not None and "rhombus" in (geom.get("style", "") or "")


def _vertex_of(pt, tol=0.02):
    """Return the diamond vertex an anchor already sits on, else None."""
    for (vx, vy), _ in _DIAMOND_VERTS:
        if abs(pt.get("x", -9) - vx) <= tol and abs(pt.get("y", -9) - vy) <= tol:
            return (vx, vy)
    return None


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


def _edge_is_backward(src, tgt, direction):
    """True if the edge runs against the flow (a loop/feedback back-edge).

    Forward edges — including dashed connections to external services — are
    safe to simplify. True back-edges run against the flow and keep their
    explicit exterior routing.
    """
    scx, scy = src["x"] + src["width"] / 2, src["y"] + src["height"] / 2
    tcx, tcy = tgt["x"] + tgt["width"] / 2, tgt["y"] + tgt["height"] / 2
    if direction == "left":
        return tcx > scx + 5
    if direction == "down":
        return tcy < scy - 5
    if direction == "up":
        return tcy > scy + 5
    return tcx < scx - 5  # default: rightward flow


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
# Pass 0: Simplify noisy edge routes to the minimal clean orthogonal path
# ---------------------------------------------------------------------------

_SIDE_FRAC = {"left": (0, 0.5), "right": (1, 0.5),
              "top": (0.5, 0), "bottom": (0.5, 1)}


def fix_simplify_routes(plan):
    """Re-route edges to the straightest clean orthogonal path.

    The goal is the shortest, most direct connection: exit the side of the
    source that faces the target and enter the side of the target that faces
    the source. For boxes arranged side by side (or stacked) that overlap on
    the perpendicular axis, the anchors are aligned to a common coordinate so
    the edge is a single straight line. Otherwise a single L-bend is used.

    For each edge we build candidate routes in quality order — straight on
    the dominant axis first, then the two L-bends, then straight on the
    secondary axis — and pick the first that clears every other node (15px)
    and crosses no other edge. This deliberately overrides the current
    anchors when a straighter route exists (a top/bottom connection between
    two horizontally-arranged boxes becomes a clean right→left line). Edges
    that genuinely need to weave around obstacles keep their routing (no
    candidate is clean). Dashed edges (back-edges, callouts) are skipped.
    """
    elements = plan.get("elements", [])
    node_geom = _node_geom_lookup(elements)
    boxes, _, _ = _collect_boxes(elements)
    anc = _ancestor_map(elements)
    desc = _descendant_map(elements)

    def edge_segments(skip_id):
        segs = []
        for e in elements:
            if e.get("type") != "edge" or e.get("id") == skip_id:
                continue
            pts = _edge_absolute_points(e, node_geom)
            for i in range(len(pts) - 1):
                segs.append((pts[i]["x"], pts[i]["y"],
                             pts[i + 1]["x"], pts[i + 1]["y"]))
        return segs

    OVERLAP_MIN = 25      # min perpendicular overlap to align a straight line
    direction = plan.get("direction", "right")
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

        # A decision (rhombus) node anchors only at its vertices; the straighten
        # candidates below would slide the anchor along a box side to line it up
        # with the target, pushing it off the vertex. Leave diamond-connected
        # edges to the orthogonal pass (which keeps the vertex and adds a bend).
        if _is_diamond(src) or _is_diamond(tgt):
            continue

        # Skip true back-edges (their exterior routing is intentional);
        # forward dashed edges (service links) get straightened like solid.
        if "dashed=1" in elem.get("style", "") and \
                _edge_is_backward(src, tgt, direction):
            continue

        ax, ay, aw, ah = src["x"], src["y"], src["width"], src["height"]
        bx, by, bw, bh = tgt["x"], tgt["y"], tgt["width"], tgt["height"]
        dx = (bx + bw / 2) - (ax + aw / 2)
        dy = (by + bh / 2) - (ay + ah / 2)
        yov = min(ay + ah, by + bh) - max(ay, by)
        xov = min(ax + aw, bx + bw) - max(ax, bx)

        # Each candidate: (efx, efy, nfx, nfy). Built in quality order.
        straight_h = straight_v = l_hv = l_vh = None

        # Straight horizontal: boxes separated in x, overlapping in y
        if yov >= OVERLAP_MIN and xov <= 0:
            y0 = (max(ay, by) + min(ay + ah, by + bh)) / 2
            efx, nfx = (1, 0) if dx > 0 else (0, 1)
            straight_h = (efx, (y0 - ay) / ah, nfx, (y0 - by) / bh)
        # Straight vertical: boxes separated in y, overlapping in x
        if xov >= OVERLAP_MIN and yov <= 0:
            x0 = (max(ax, bx) + min(ax + aw, bx + bw)) / 2
            efy, nfy = (1, 0) if dy > 0 else (0, 1)
            straight_v = ((x0 - ax) / aw, efy, (x0 - bx) / bw, nfy)
        # L-bend, exit horizontal / entry vertical
        l_hv = (1 if dx > 0 else 0, 0.5, 0.5, 0 if dy > 0 else 1)
        # L-bend, exit vertical / entry horizontal
        l_vh = (0.5, 1 if dy > 0 else 0, 0 if dx > 0 else 1, 0.5)

        if abs(dx) >= abs(dy):
            cands = [straight_h, l_hv, l_vh, straight_v]
        else:
            cands = [straight_v, l_vh, l_hv, straight_h]
        cands = [c for c in cands if c is not None]

        connected = _edge_skip_ids(elem["from"], elem["to"], anc, desc)

        other_segs = None
        chosen = None
        for efx, efy, nfx, nfy in cands:
            ex = ax + efx * aw
            ey = ay + efy * ah
            nx = bx + nfx * bw
            ny = by + nfy * bh
            # Single corner where exit and entry axes meet; empty if straight
            if abs(ex - nx) < 1 or abs(ey - ny) < 1:
                cand_wps = []
            elif efx in (0, 1):   # exit horizontal → corner aligns to exit y
                cand_wps = [{"x": nx, "y": ey}]
            else:                 # exit vertical → corner aligns to exit x
                cand_wps = [{"x": ex, "y": ny}]

            pts = [{"x": ex, "y": ey}] + cand_wps + [{"x": nx, "y": ny}]

            clear = True
            for i in range(len(pts) - 1):
                for box in boxes:
                    if box["id"] in connected:
                        continue
                    if _segment_intersects_box(
                        pts[i]["x"], pts[i]["y"],
                        pts[i + 1]["x"], pts[i + 1]["y"], box, margin=15
                    ):
                        clear = False
                        break
                if not clear:
                    break
            if not clear:
                continue

            if other_segs is None:
                other_segs = edge_segments(elem.get("id"))
            crosses = False
            for i in range(len(pts) - 1):
                for ox1, oy1, ox2, oy2 in other_segs:
                    if _segments_intersect(
                        pts[i]["x"], pts[i]["y"],
                        pts[i + 1]["x"], pts[i + 1]["y"],
                        ox1, oy1, ox2, oy2
                    ):
                        crosses = True
                        break
                if crosses:
                    break
            if crosses:
                continue

            chosen = (efx, efy, nfx, nfy, cand_wps)
            break

        if not chosen:
            continue

        efx, efy, nfx, nfy, cand_wps = chosen
        cur = elem.get("waypoints") or []
        same = (abs(ep["x"] - efx) < 1e-6 and abs(ep["y"] - efy) < 1e-6
                and abs(np_["x"] - nfx) < 1e-6 and abs(np_["y"] - nfy) < 1e-6
                and len(cur) == len(cand_wps) and all(
                    abs(a["x"] - b["x"]) < 1 and abs(a["y"] - b["y"]) < 1
                    for a, b in zip(cur, cand_wps)))
        if same:
            continue

        elem["exit_point"] = {"x": efx, "y": efy}
        elem["entry_point"] = {"x": nfx, "y": nfy}
        elem["waypoints"] = cand_wps
        fixes += 1

    return fixes


# ---------------------------------------------------------------------------
# Pass 0a: Fix corner entry/exit points and tangential approaches
# ---------------------------------------------------------------------------

_PERPENDICULAR_OFFSET = 25


def fix_diamond_anchors(plan):
    """Snap edge anchors on decision (rhombus) nodes to a diamond vertex.

    A rhombus only touches its bounding box at the four edge-midpoints (its
    vertices). Any other fractional anchor — e.g. exitX=1,exitY=0.7 — lands in
    an empty bounding-box corner, so the edge appears to start or end off the
    shape rather than on it. Snap each off-vertex anchor to the vertex whose
    outward direction best points at the other endpoint, preferring a vertex
    not already taken by another edge on the same diamond so the connections
    fan across the four points instead of stacking on one.

    Runs before the routing passes so they build clean orthogonal routes from
    the corrected anchor; already-correct vertex anchors are left untouched.
    """
    elements = plan.get("elements", [])
    node_geom = _node_geom_lookup(elements)
    diamonds = {nid for nid, g in node_geom.items() if _is_diamond(g)}
    if not diamonds:
        return 0

    def _center(g):
        return (g["x"] + g["width"] / 2.0, g["y"] + g["height"] / 2.0)

    # Group every endpoint attached to a diamond.
    attach = {d: [] for d in diamonds}
    for elem in elements:
        if elem.get("type") != "edge":
            continue
        if elem.get("from") in diamonds and elem.get("exit_point"):
            attach[elem["from"]].append((elem, "exit"))
        if elem.get("to") in diamonds and elem.get("entry_point"):
            attach[elem["to"]].append((elem, "entry"))

    fixes = 0
    for d, members in attach.items():
        dcx, dcy = _center(node_geom[d])
        occupied = {}        # vertex -> already claimed
        pending = []
        for elem, role in members:
            pt = elem["exit_point"] if role == "exit" else elem["entry_point"]
            v = _vertex_of(pt)
            if v is not None:
                occupied.setdefault(v, True)
                # Already on the right side but a hair off the exact tip — snap
                # it precisely (keeps its route; later passes realign the
                # adjacent waypoint).
                if (pt["x"], pt["y"]) != v:
                    pt["x"], pt["y"] = v
                    fixes += 1
            else:
                pending.append((elem, role))
        if not pending:
            continue

        # Rank each pending anchor's vertices by how well their outward
        # direction matches the direction to the other endpoint.
        scored = []
        for elem, role in pending:
            other_id = elem["to"] if role == "exit" else elem["from"]
            og = node_geom.get(other_id)
            if not og:
                continue
            ox, oy = _center(og)
            dx, dy = ox - dcx, oy - dcy
            norm = (dx * dx + dy * dy) ** 0.5 or 1.0
            ux, uy = dx / norm, dy / norm
            ranked = sorted(
                _DIAMOND_VERTS,
                key=lambda vd: -(vd[1][0] * ux + vd[1][1] * uy),
            )
            best = ranked[0][1][0] * ux + ranked[0][1][1] * uy
            scored.append((best, elem, role, ranked))

        # Assign strongest preference first so the clearest direction wins its
        # vertex; weaker ones take the next free vertex (sharing only if all
        # four are taken).
        scored.sort(key=lambda s: -s[0])
        for _best, elem, role, ranked in scored:
            chosen = next(((vx, vy) for (vx, vy), _ in ranked
                           if (vx, vy) not in occupied), ranked[0][0])
            occupied.setdefault(chosen, True)
            pt = elem["exit_point"] if role == "exit" else elem["entry_point"]
            if (pt["x"], pt["y"]) != chosen:
                pt["x"], pt["y"] = chosen
                # The old waypoints were laid out for the previous anchor (often
                # on a different side); drop them so the routing passes that run
                # next rebuild a clean orthogonal route from the new vertex.
                elem["waypoints"] = []
                fixes += 1

    return fixes


def fix_assign_anchors(plan):
    """Give anchorless edges an exit/entry that faces the other endpoint.

    The LLM sometimes leaves an edge with no exit/entry point (common for edges
    into a nested container's children), so draw.io free-routes it and the path
    wanders. Assign the side facing the target (Rule 8c) so the later
    orthogonal/anchor passes can route it cleanly.
    """
    elements = plan.get("elements", [])
    node_geom = _node_geom_lookup(elements)
    fixes = 0
    for elem in elements:
        if elem.get("type") != "edge":
            continue
        if elem.get("exit_point") and elem.get("entry_point"):
            continue
        src = node_geom.get(elem["from"])
        tgt = node_geom.get(elem["to"])
        if not (src and tgt):
            continue
        scx = src["x"] + src["width"] / 2
        scy = src["y"] + src["height"] / 2
        tcx = tgt["x"] + tgt["width"] / 2
        tcy = tgt["y"] + tgt["height"] / 2
        dx, dy = tcx - scx, tcy - scy
        if abs(dx) >= abs(dy):
            exit_pt = (1.0, 0.5) if dx >= 0 else (0.0, 0.5)
            entry_pt = (0.0, 0.5) if dx >= 0 else (1.0, 0.5)
        else:
            exit_pt = (0.5, 1.0) if dy >= 0 else (0.5, 0.0)
            entry_pt = (0.5, 0.0) if dy >= 0 else (0.5, 1.0)
        if not elem.get("exit_point"):
            elem["exit_point"] = {"x": exit_pt[0], "y": exit_pt[1]}
            fixes += 1
        if not elem.get("entry_point"):
            elem["entry_point"] = {"x": entry_pt[0], "y": entry_pt[1]}
            fixes += 1
    return fixes


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
        # Never redistribute a diamond's anchors — its only valid attach points
        # are the four vertices, and spreading them across [lo, hi] would push
        # them back off the shape (handled by fix_diamond_anchors instead).
        if _is_diamond(node_geom.get(box_id)):
            continue
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

    # Ancestor/descendant maps for skip logic in corner collision checks
    anc = _ancestor_map(elements)
    desc = _descendant_map(elements)

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

        # A waypoint-free edge touching a nested container child is best left to
        # draw.io's orthogonal router: materializing a single corner here stacks
        # the corners of a fan-out and can't be stripped later (the sibling
        # container blocks the clearance check), creating crossings draw.io
        # would have avoided. Edges with explicit waypoints are still squared.
        if not wps and (anc.get(elem["from"]) or anc.get(elem["to"])):
            continue

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

        es = _anchor_side(ep)
        ns = _anchor_side(np_)

        connected_ids = _edge_skip_ids(elem["from"], elem["to"], anc, desc)

        last_i = len(all_pts) - 2
        for i in range(len(all_pts) - 1):
            p = all_pts[i]
            q = all_pts[i + 1]

            # Don't re-emit the exit point (index 0) — it's implicit
            if i > 0:
                new_wps.append({"x": p["x"], "y": p["y"]})

            dx = abs(q["x"] - p["x"])
            dy = abs(q["y"] - p["y"])

            if dx > 1 and dy > 1:
                # Diagonal — insert an L corner.
                #   corner_a = (p.x, q.y): p→corner VERTICAL, corner→q horizontal
                #   corner_b = (q.x, p.y): p→corner HORIZONTAL, corner→q vertical
                corner_a = {"x": p["x"], "y": q["y"]}
                corner_b = {"x": q["x"], "y": p["y"]}

                # Prefer the corner whose segment touching an anchor is
                # perpendicular to that anchor's side — a left/right exit must
                # leave horizontally (corner_b), not slide down its own edge
                # (corner_a); a left/right entry must arrive horizontally
                # (corner_a). Otherwise default to corner_a.
                pref = None
                if i == 0 and es in ("left", "right"):
                    pref = corner_b
                elif i == 0 and es in ("top", "bottom"):
                    pref = corner_a
                elif i == last_i and ns in ("left", "right"):
                    pref = corner_a
                elif i == last_i and ns in ("top", "bottom"):
                    pref = corner_b

                def _clear(cn, margin=0):
                    for box in boxes:
                        if box["id"] in connected_ids:
                            continue
                        if _segment_intersects_box(
                            p["x"], p["y"], cn["x"], cn["y"], box, margin
                        ) or _segment_intersects_box(
                            cn["x"], cn["y"], q["x"], q["y"], box, margin
                        ):
                            return False
                    return True

                # Honor the anchor-aware preference only when it also keeps the
                # validator's 15px clearance — otherwise a perpendicular exit
                # that skims a neighbor trades a tangential start for a
                # near-miss. When it can't, fall back to the original
                # intersection-only choice (corner_a default).
                if pref is not None and _clear(pref, margin=15):
                    corner = pref
                elif _clear(corner_a):
                    corner = corner_a
                elif _clear(corner_b):
                    corner = corner_b
                else:
                    corner = pref or corner_a
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

    def _tidy(cont):
        """Tidy one container in place. Recurses into nested child containers
        first (bottom-up) so the outer hugs an already-sized inner. Works on
        any container dict — sizing reads width/height + children rel coords,
        never the container's own x/y, so it's position-agnostic."""
        fixes = 0
        children = cont.get("children", [])
        for c in children:
            if c.get("children"):
                fixes += _tidy(c)
        if len(children) < 2:
            return fixes

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
            if required_h <= cont["height"] + 1:
                for c in children:
                    c["rel_y"] = top_band
                    c["height"] = max_h
                cont["height"] = required_h
                # Hug width to the rightmost child
                right = max(c["rel_x"] + c["width"] for c in children)
                new_w = right + left_band
                if new_w <= cont["width"] + 1:
                    cont["width"] = new_w
                fixes += 1

        elif column and not row:
            # Equalize widths, align to the left band
            max_w = max(c["width"] for c in children)
            required_w = left_band + max_w + side_pad
            if required_w <= cont["width"] + 1:
                for c in children:
                    c["rel_x"] = left_band
                    c["width"] = max_w
                cont["width"] = required_w
                bottom = max(c["rel_y"] + c["height"] for c in children)
                new_h = bottom + top_band
                if new_h <= cont["height"] + 1:
                    cont["height"] = new_h
                fixes += 1

        return fixes

    fixes = 0
    for elem in elements:
        if elem.get("type") == "container":
            fixes += _tidy(elem)
    return fixes


# ---------------------------------------------------------------------------
# Pass 1d: Gravity — pull stranded nodes toward their connections
# ---------------------------------------------------------------------------

def fix_gravity(plan, strand=40, margin=15):
    """Pull a node that's stranded far from its connections back toward them.

    A node placed well outside the span of its connected neighbors (e.g. an
    external-service box parked at the top while everything it links to sits
    in the middle) produces long, bent edges. For each plain node whose center
    falls outside its neighbors' range on an axis (by more than `strand`),
    move it toward the median of its neighbors on that axis — as far as a
    collision-free position allows. Nodes already within their neighbors'
    range are left untouched, so the semantic column structure is preserved.
    Connected edges are re-routed by the later passes.
    """
    elements = plan.get("elements", [])
    node_geom = _node_geom_lookup(elements)
    boxes, container_ids, container_child_ids = _collect_boxes(elements)

    neighbors = {}
    for e in elements:
        if e.get("type") != "edge":
            continue
        neighbors.setdefault(e["from"], set()).add(e["to"])
        neighbors.setdefault(e["to"], set()).add(e["from"])

    fixes = 0
    for elem in elements:
        # Only move plain top-level nodes — containers and their children
        # carry internal structure that shouldn't be yanked around.
        if elem.get("type") != "node" or elem["id"] in container_child_ids:
            continue
        nid = elem["id"]
        nbr = [node_geom[n] for n in neighbors.get(nid, ())
               if n in node_geom and n != nid]
        # Need 2+ neighbours for "stranded outside their span" to be
        # meaningful — otherwise leaf nodes get yanked toward their one
        # neighbour and the layout collapses.
        if len(nbr) < 2:
            continue

        cx = elem["x"] + elem["width"] / 2
        cy = elem["y"] + elem["height"] / 2
        xs = sorted(n["x"] + n["width"] / 2 for n in nbr)
        ys = sorted(n["y"] + n["height"] / 2 for n in nbr)
        medx = xs[len(xs) // 2]
        medy = ys[len(ys) // 2]

        # Only centre on the axis the neighbours actually SPAN. On the axis
        # where they're clustered (e.g. a vertical source column), the node's
        # offset is the natural fan-in direction — pulling it there would drag
        # the node on top of its neighbours.
        SPAN_MIN = 60
        tx, ty = cx, cy
        if xs[-1] - xs[0] >= SPAN_MIN and (cx < xs[0] - strand or
                                           cx > xs[-1] + strand):
            tx = medx
        if ys[-1] - ys[0] >= SPAN_MIN and (cy < ys[0] - strand or
                                           cy > ys[-1] + strand):
            ty = medy
        if abs(tx - cx) < 1 and abs(ty - cy) < 1:
            continue

        # Move as far toward the target as a collision-free spot allows
        for frac in (1.0, 0.85, 0.7, 0.55, 0.4, 0.25):
            ncx = cx + (tx - cx) * frac
            ncy = cy + (ty - cy) * frac
            nxx = ncx - elem["width"] / 2
            nyy = ncy - elem["height"] / 2
            if nxx < margin or nyy < margin:
                continue
            box = {"id": nid, "x": nxx, "y": nyy,
                   "w": elem["width"], "h": elem["height"]}
            collide = False
            for b in boxes:
                if b["id"] == nid or b["id"] in container_child_ids:
                    continue
                if _overlaps(box, b, margin):
                    collide = True
                    break
            if not collide:
                elem["x"] = nxx
                elem["y"] = nyy
                fixes += 1
                break

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
# Pass 2b: Compact large empty bands
# ---------------------------------------------------------------------------

def _find_gaps(intervals, min_gap):
    """Find empty gaps wider than min_gap between sorted 1-D intervals."""
    if not intervals:
        return []
    intervals = sorted(intervals)
    gaps = []
    cur_end = intervals[0][1]
    for s, e in intervals[1:]:
        if s - cur_end > min_gap:
            gaps.append((cur_end, s))
        cur_end = max(cur_end, e)
    return gaps


def fix_compact_gaps(plan, min_gap=120, target_gap=70):
    """Close large empty bands by sliding the far cluster inward.

    When a full-height vertical band (or full-width horizontal band) contains
    no node — only long edges spanning it — the diagram wastes space and the
    edges are needlessly long. Everything past a cut line in the band is
    shifted toward the rest by a uniform delta, which preserves orthogonality
    (horizontal segments crossing the cut just shorten; vertical segments lie
    wholly on one side) and relative order. Reverts if it worsens validation.
    """
    import copy

    elements = plan.get("elements", [])
    before_issues = _count_issues(plan)
    snapshot = copy.deepcopy(plan)
    fixes = 0

    for axis in ("x", "y"):
        dim = "width" if axis == "x" else "height"
        # Top-level node/container intervals along this axis
        intervals = []
        for elem in elements:
            if elem.get("type", "node") in ("node", "container"):
                intervals.append((elem[axis], elem[axis] + elem[dim]))
        gaps = _find_gaps(intervals, min_gap)
        # Process right-to-left so earlier shifts don't move later gaps
        for g0, g1 in sorted(gaps, reverse=True):
            delta = (g1 - g0) - target_gap
            if delta <= 0:
                continue
            cut = (g0 + g1) / 2
            for elem in elements:
                etype = elem.get("type", "node")
                if etype in ("node", "container"):
                    if elem[axis] > cut:
                        elem[axis] -= delta
                elif etype == "edge":
                    for wp in (elem.get("waypoints") or []):
                        if wp[axis] > cut:
                            wp[axis] -= delta
            fixes += 1

    if fixes and _count_issues(plan) > before_issues:
        # Compaction made things worse — revert
        plan.clear()
        plan.update(snapshot)
        return 0

    # Shrink the canvas to the compacted content
    if fixes:
        canvas = plan.get("canvas", {})
        max_right = max((e["x"] + e["width"] for e in elements
                         if e.get("type", "node") in ("node", "container")),
                        default=canvas.get("width", 0))
        max_bottom = max((e["y"] + e["height"] for e in elements
                          if e.get("type", "node") in ("node", "container")),
                         default=canvas.get("height", 0))
        canvas["width"] = int(max_right + 60)
        canvas["height"] = int(max_bottom + 60)
        plan["canvas"] = canvas

    return fixes


# ---------------------------------------------------------------------------
# Pass 3: Edge-through-node rerouting
# ---------------------------------------------------------------------------

def _seg_hits_any_node(pts, boxes, connected, margin=0):
    """Return the first node a multi-segment path passes through, or None.

    `connected` already contains the edge's endpoints, the containers enclosing
    them, and (for a container endpoint) that container's descendants, so no
    separate parent check is needed — siblings stay obstacles to route around.
    """
    for i in range(len(pts) - 1):
        for box in boxes:
            if box["id"] in connected:
                continue
            if _segment_intersects_box(
                pts[i]["x"], pts[i]["y"], pts[i + 1]["x"], pts[i + 1]["y"],
                box, margin
            ):
                return box
    return None


def _predicted_route_pts(exit_abs, entry_abs, es, ns):
    """The orthogonal point chain draw.io draws for a waypoint-free edge."""
    ex, ey = exit_abs["x"], exit_abs["y"]
    nx, ny = entry_abs["x"], entry_abs["y"]
    if abs(ex - nx) <= 1 or abs(ey - ny) <= 1:
        corner = None
    elif es in ("left", "right") and ns in ("top", "bottom"):
        corner = {"x": nx, "y": ey}
    elif es in ("top", "bottom") and ns in ("left", "right"):
        corner = {"x": ex, "y": ny}
    else:
        corner = {"x": nx, "y": ey}
    return [exit_abs] + ([corner] if corner else []) + [entry_abs]


def _corridor_route(src, tgt, boxes, connected):
    """Route through the clear gap between two non-overlapping boxes.

    For a long edge that would otherwise plow across a row of nodes (e.g. a
    row-wrap connector), exit toward the empty band between the source and
    target and run across it. Returns (exit_point, entry_point, waypoints) for
    the first gap whose 3-segment path clears every node, else None.
    """
    sx, sy, sw, sh = src["x"], src["y"], src["width"], src["height"]
    tx, ty, tw, th = tgt["x"], tgt["y"], tgt["width"], tgt["height"]
    scx, scy = sx + sw / 2, sy + sh / 2
    tcx, tcy = tx + tw / 2, ty + th / 2
    yov = min(sy + sh, ty + th) - max(sy, ty)
    xov = min(sx + sw, tx + tw) - max(sx, tx)

    candidates = []
    if yov <= 0:                       # horizontal corridor in the vertical gap
        if scy < tcy:
            band = ((sy + sh) + ty) / 2
            e_pt, n_pt = {"x": 0.5, "y": 1}, {"x": 0.5, "y": 0}
            ey0, ny0 = sy + sh, ty
        else:
            band = ((ty + th) + sy) / 2
            e_pt, n_pt = {"x": 0.5, "y": 0}, {"x": 0.5, "y": 1}
            ey0, ny0 = sy, ty + th
        pts = [{"x": scx, "y": ey0}, {"x": scx, "y": band},
               {"x": tcx, "y": band}, {"x": tcx, "y": ny0}]
        candidates.append((e_pt, n_pt,
                           [{"x": scx, "y": band}, {"x": tcx, "y": band}], pts))
    if xov <= 0:                       # vertical corridor in the horizontal gap
        if scx < tcx:
            band = ((sx + sw) + tx) / 2
            e_pt, n_pt = {"x": 1, "y": 0.5}, {"x": 0, "y": 0.5}
            ex0, nx0 = sx + sw, tx
        else:
            band = ((tx + tw) + sx) / 2
            e_pt, n_pt = {"x": 0, "y": 0.5}, {"x": 1, "y": 0.5}
            ex0, nx0 = sx, tx + tw
        pts = [{"x": ex0, "y": scy}, {"x": band, "y": scy},
               {"x": band, "y": tcy}, {"x": nx0, "y": tcy}]
        candidates.append((e_pt, n_pt,
                           [{"x": band, "y": scy}, {"x": band, "y": tcy}], pts))

    for e_pt, n_pt, wps, pts in candidates:
        if not _seg_hits_any_node(pts, boxes, connected):
            return e_pt, n_pt, wps
    return None


def fix_edge_through_node(plan, clearance=20):
    """Route edges around obstructing nodes — including waypoint-free ones.

    Waypoint-free edges are materialized to the orthogonal route draw.io would
    actually draw (which does NOT avoid nodes), so a long left-going edge that
    would plow across a row is caught. Such an edge is first re-routed through
    the clear gap between its endpoints (a row-wrap corridor); only if no gap
    is clear does it fall back to per-obstructor detours.
    """
    elements = plan.get("elements", [])
    node_geom = _node_geom_lookup(elements)
    boxes, _, _ = _collect_boxes(elements)

    # Ancestor/descendant maps for skip logic
    anc = _ancestor_map(elements)
    desc = _descendant_map(elements)

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

        connected_ids = _edge_skip_ids(elem["from"], elem["to"], anc, desc)
        wps = list(elem.get("waypoints") or [])

        exit_abs = {
            "x": src["x"] + ep["x"] * src["width"],
            "y": src["y"] + ep["y"] * src["height"],
        }
        entry_abs = {
            "x": tgt["x"] + np_["x"] * tgt["width"],
            "y": tgt["y"] + np_["y"] * tgt["height"],
        }

        # For a waypoint-free edge, check the route draw.io will actually draw.
        if wps:
            all_pts = [exit_abs] + wps + [entry_abs]
        else:
            all_pts = _predicted_route_pts(
                exit_abs, entry_abs, _anchor_side(ep), _anchor_side(np_))

        # If the (predicted) route is clear, leave the edge untouched —
        # keeps clean waypoint-free edges editable.
        if not _seg_hits_any_node(all_pts, boxes, connected_ids):
            continue

        # Prefer a clean corridor route through the gap between the endpoints
        # (handles row-wrap connectors that cross a whole row of nodes).
        corridor = _corridor_route(src, tgt, boxes, connected_ids)
        if corridor:
            e_pt, n_pt, cwps = corridor
            elem["exit_point"] = e_pt
            elem["entry_point"] = n_pt
            elem["waypoints"] = cwps
            fixes += 1
            continue

        # Fallback: per-obstructor detours along the materialized route.
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

def fix_dedup_waypoints(plan, tol=1.5):
    """Drop redundant waypoints: exact duplicates and collinear midpoints.

    Repeated passes (orthogonal, reroute, simplify) can stack several copies of
    the same corner, or leave a point sitting on a straight segment between its
    neighbors. Both are pure noise — they bloat the XML and make routes harder
    to read without changing the rendered path. Removing a duplicate or a point
    that lies on the line through its neighbors is geometry-preserving, so this
    pass can never alter validator issue counts.

    The exit/entry anchors are folded in as virtual endpoints so a waypoint
    collinear with an anchor (e.g. three points along one straight segment) is
    also collapsed.
    """
    elements = plan.get("elements", [])
    node_geom = _node_geom_lookup(elements)
    fixes = 0

    def _collinear(a, b, c):
        # b lies on segment a→c when the triangle area (cross product) is ~0.
        cross = (b["x"] - a["x"]) * (c["y"] - a["y"]) - \
                (b["y"] - a["y"]) * (c["x"] - a["x"])
        return abs(cross) <= tol * max(
            1.0,
            abs(c["x"] - a["x"]) + abs(c["y"] - a["y"]),
        )

    for elem in elements:
        if elem.get("type") != "edge":
            continue
        wps = list(elem.get("waypoints") or [])
        if not wps:
            continue

        src = node_geom.get(elem["from"])
        tgt = node_geom.get(elem["to"])
        ep = elem.get("exit_point")
        np_ = elem.get("entry_point")
        if not (src and tgt and ep and np_):
            # Without anchors, still drop exact duplicates conservatively.
            chain = wps
            endpoints = False
        else:
            chain = [{
                "x": src["x"] + ep["x"] * src["width"],
                "y": src["y"] + ep["y"] * src["height"],
            }] + wps + [{
                "x": tgt["x"] + np_["x"] * tgt["width"],
                "y": tgt["y"] + np_["y"] * tgt["height"],
            }]
            endpoints = True

        # 1) Collapse consecutive exact duplicates.
        deduped = [chain[0]]
        for pt in chain[1:]:
            prev = deduped[-1]
            if abs(pt["x"] - prev["x"]) <= tol and abs(pt["y"] - prev["y"]) <= tol:
                continue
            deduped.append(pt)

        # 2) Drop interior points collinear with their neighbors.
        cleaned = [deduped[0]]
        for i in range(1, len(deduped) - 1):
            if _collinear(cleaned[-1], deduped[i], deduped[i + 1]):
                continue
            cleaned.append(deduped[i])
        if len(deduped) > 1:
            cleaned.append(deduped[-1])

        new_wps = cleaned[1:-1] if endpoints else cleaned
        if len(new_wps) != len(wps):
            elem["waypoints"] = [{"x": p["x"], "y": p["y"]} for p in new_wps]
            fixes += 1

    return fixes


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
    anc = _ancestor_map(elements)
    desc = _descendant_map(elements)
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
        connected = _edge_skip_ids(elem["from"], elem["to"], anc, desc)
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
# Pass 0: Enforce the grouping decided by graph_analysis
# ---------------------------------------------------------------------------

_GROUP_CONTAINER_STYLE = (
    "rounded=1;whiteSpace=wrap;html=1;fillColor=#ececec;strokeColor=#333333;"
    "strokeWidth=2;container=1;collapsible=0;verticalAlign=top;spacingTop=5;"
    "fontSize=12;fontStyle=1;fontFamily=Inter,Helvetica,Arial,sans-serif;"
)


def _stack_vertical(cont, pad=14, gap=18, title=34):
    """Lay a container's children out as a single vertical column, sized to fit.

    Recurses into nested containers first, so a wide horizontally-laid container
    (e.g. a Sync Dataset with three steps side by side) becomes a narrow tall
    one — which lets it sit inside a grouping column without spanning the canvas.
    """
    children = cont.get("children", [])
    if not children:
        return
    for c in children:
        if c.get("children"):
            _stack_vertical(c, pad, gap, title)
    order = sorted(children, key=lambda c: (c.get("rel_y", 0), c.get("rel_x", 0)))
    width = max(c["width"] for c in children)
    y = title
    for c in order:
        c["rel_x"] = pad
        c["rel_y"] = y
        y += c["height"] + gap
    cont["width"] = width + 2 * pad
    cont["height"] = (y - gap) + pad


def fix_enforce_groups(plan, spec, pad=16, gap=20, title=36):
    """Force the layout to honor graph_analysis's fan-in grouping.

    graph_analysis wraps a parallel fan-in into a ``"grouped": true`` container
    and bundles its edges, but the LLM layout pass can ignore that and place the
    members flat (the grouping then silently disappears). This pass re-applies
    the structure deterministically on the already-laid-out plan: when a grouped
    container is missing, **compact** its placed members into a vertical column —
    reflowing any wide nested container narrow — and wrap them in the container,
    then replace the per-member edges to each bundled target with the single
    container→target edge recorded in the spec. Compacting (rather than wrapping
    members where the LLM scattered them) keeps the container narrow so it can't
    engulf unrelated nodes; the overlap pass that runs next nudges anything the
    new column bumps into. Idempotent: if the layout already built the
    container, it's left as-is.
    """
    if not spec:
        return 0
    grouped = [c for c in spec.get("containers", []) if c.get("grouped")]
    if not grouped:
        return 0

    fixes = 0
    for g in grouped:
        gid = g["id"]
        elements = plan.get("elements", [])
        top = {e["id"]: e for e in elements
               if e.get("type", "node") in ("node", "container")}
        if gid in top:
            continue  # layout already created the grouping container
        member_ids = [m for m in g.get("children", []) if m in top]
        if len(member_ids) < 2:
            continue
        members = [top[m] for m in member_ids]
        member_set = set(member_ids)

        ox = min(m["x"] for m in members) - pad
        oy = min(m["y"] for m in members) - title

        # Reflow any container member to a narrow vertical column, then stack
        # every member vertically so the group is a compact column.
        for m in members:
            if m.get("children"):
                _stack_vertical(m)
        order = sorted(members, key=lambda m: (m["y"], m["x"]))
        col_w = max(m["width"] for m in members)
        children = []
        ry = title
        for m in order:
            child = dict(m)
            child["type"] = m.get("type", "node")
            child["rel_x"] = pad
            child["rel_y"] = ry
            child.pop("x", None)
            child.pop("y", None)
            children.append(child)
            ry += m["height"] + gap
        container = {
            "id": gid, "type": "container",
            "x": ox, "y": oy,
            "width": col_w + 2 * pad, "height": (ry - gap) + pad,
            "label_html": f"<b>{g.get('label', gid)}</b>",
            "style": _GROUP_CONTAINER_STYLE,
            "children": children,
        }
        kept = [e for e in elements
                if not (e.get("id") in member_set
                        and e.get("type", "node") in ("node", "container"))]
        nodes_part = [e for e in kept if e.get("type", "node") != "edge"]
        edges_part = [e for e in kept if e.get("type", "node") == "edge"]
        plan["elements"] = nodes_part + [container] + edges_part

        # Bundle edges exactly as the spec recorded them for this group.
        for se in spec.get("edges", []):
            if se.get("from") != gid:
                continue
            tgt = se["to"]
            plan["elements"] = [
                el for el in plan["elements"]
                if not (el.get("type") == "edge"
                        and el.get("from") in member_set and el.get("to") == tgt)
            ]
            exists = any(el.get("type") == "edge" and el.get("from") == gid
                         and el.get("to") == tgt for el in plan["elements"])
            if not exists:
                dashed = "dashed=1;dashPattern=8 4;" if se.get("style") == "dashed" else ""
                plan["elements"].append({
                    "id": f"e_{gid}_{tgt}", "type": "edge",
                    "from": gid, "to": tgt, "label": se.get("label", ""),
                    "style": ("edgeStyle=orthogonalEdgeStyle;rounded=1;"
                              "strokeColor=#333333;strokeWidth=1.5;html=1;" + dashed),
                })
        fixes += 1

    return fixes


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _run_passes(plan, corner_anchors=True, simplify=True, gravity=True):
    """Run the full fix pipeline on a plan. Returns a summary dict."""
    summary = {}

    # Tidy container interiors first — child moves affect edge anchors
    summary["container_layout"] = fix_container_layout(plan)
    # Pull stranded nodes toward their connections before routing edges
    if gravity:
        summary["gravity"] = fix_gravity(plan)
    # Snap decision-node anchors to diamond vertices before routes are built
    summary["diamond_anchors"] = fix_diamond_anchors(plan)
    # Give anchorless edges a sensible facing anchor before routing
    summary["assign_anchors"] = fix_assign_anchors(plan)
    summary["entry_exit"] = fix_entry_exit(plan)
    if corner_anchors:
        summary["corner_anchors"] = fix_corner_anchors(plan)
    # Collapse noisy/redundant routes to the minimal clean path
    if simplify:
        summary["simplify_routes"] = fix_simplify_routes(plan)
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
    if simplify:
        summary["simplify_routes_pass2"] = fix_simplify_routes(plan)
    summary["anchor_alignment_pass2"] = fix_anchor_alignment(plan)
    summary["orthogonal_pass2"] = fix_orthogonal(plan)
    summary["spikes_pass2"] = fix_spikes(plan)
    # Collapse duplicate/collinear waypoints stacked up by the passes above
    summary["dedup_waypoints"] = fix_dedup_waypoints(plan)
    # Strip redundant waypoints — makes edges editable in draw.io
    summary["strip_waypoints"] = fix_strip_waypoints(plan)
    # Compact empty bands last, when the issue count reflects the final
    # state (its A/B guard would mis-fire mid-pipeline before cleanup).
    summary["compact_gaps"] = fix_compact_gaps(plan)
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


def fix(plan, spec=None):
    """Apply all fix passes and return a summary.

    When a graph spec is supplied, the grouping graph_analysis decided is first
    enforced on the plan (independently of whether the LLM honored it), then the
    routing/overlap passes run over the resulting structure.

    Three passes are beneficial-but-occasionally-risky: corner-anchor
    redistribution, route simplification, and gravity placement can each
    trade a visual win for a real defect (a new crossing or edge-through-node)
    that the validator doesn't always offset. So we run the whole pipeline for
    each on/off combination of the three and keep whichever yields the fewest
    validator issues. Combinations are tried most-features-first and ties go
    to the earlier (more-featured) combination, preserving cosmetic
    improvements at no measurable cost.
    """
    import copy
    import itertools

    # Re-apply the deterministic grouping before the routing passes so the
    # structure is authoritative from graph_analysis, not the LLM layout.
    enforce_count = fix_enforce_groups(plan, spec)

    best_plan = None
    best_summary = None
    best_issues = None
    # most-features-first so ties keep the richer result
    for corner_anchors, simplify, gravity in itertools.product(
        (True, False), repeat=3
    ):
        trial = copy.deepcopy(plan)
        summary = _run_passes(trial, corner_anchors=corner_anchors,
                              simplify=simplify, gravity=gravity)
        issues = _count_issues(trial)
        if best_issues is None or issues < best_issues:
            best_plan, best_summary, best_issues = trial, summary, issues

    plan.clear()
    plan.update(best_plan)

    best_summary["enforce_groups"] = enforce_count
    best_summary["total"] = sum(best_summary.values())
    return best_summary


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

    spec = None
    spec_path = None
    if "--spec" in sys.argv:
        idx = sys.argv.index("--spec")
        if idx + 1 < len(sys.argv):
            spec_path = sys.argv[idx + 1]
    else:
        # Auto-discover the graph spec next to the layout plan (both live in
        # artifacts/), so grouping is enforced even when --spec isn't passed.
        import os
        guess = os.path.join(os.path.dirname(os.path.abspath(input_path)),
                             "graph-spec.json")
        if os.path.exists(guess):
            spec_path = guess
    if spec_path:
        try:
            with open(spec_path) as f:
                spec = json.load(f)
        except (OSError, ValueError) as e:
            print(f"warning: could not read graph spec {spec_path}: {e}",
                  file=sys.stderr)

    with open(input_path) as f:
        plan = json.load(f)

    summary = fix(plan, spec)

    with open(output_path, "w") as f:
        json.dump(plan, f, indent=2)

    if summary["total"] > 0:
        print(f"Fixed: {summary}", file=sys.stderr)
    else:
        print("No fixes needed", file=sys.stderr)

    json.dump(summary, sys.stdout, indent=2)


if __name__ == "__main__":
    main()

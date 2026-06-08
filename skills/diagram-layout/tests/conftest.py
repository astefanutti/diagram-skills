"""Shared setup + tiny plan builders for the diagram-layout routing tests.

The scripts under ``scripts/`` are run standalone (no package), so make them
importable by putting that directory on ``sys.path``. Tests then ``import
fix_layout`` / ``validate_layout`` directly.
"""
import os
import sys

SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)


# --- plan builders -------------------------------------------------------
# Minimal layout-plan fragments. Geometry mirrors the real defects analysed
# from agent-eval-harness runs so the tests guard the actual regressions.

def node(nid, x, y, w, h, **extra):
    d = {"type": "node", "id": nid, "x": x, "y": y, "width": w, "height": h}
    d.update(extra)
    return d


def edge(frm, to, exit_xy=None, entry_xy=None, waypoints=None, style=""):
    e = {"type": "edge", "from": frm, "to": to, "style": style}
    if exit_xy is not None:
        e["exit_point"] = {"x": exit_xy[0], "y": exit_xy[1]}
    if entry_xy is not None:
        e["entry_point"] = {"x": entry_xy[0], "y": entry_xy[1]}
    if waypoints is not None:
        e["waypoints"] = [{"x": wx, "y": wy} for wx, wy in waypoints]
    return e


def plan(*elements, direction="right", canvas=(2600, 1800)):
    return {
        "direction": direction,
        "canvas": {"width": canvas[0], "height": canvas[1]},
        "elements": list(elements),
    }


def find_edge(p, frm, to):
    for e in p["elements"]:
        if e.get("type") == "edge" and e["from"] == frm and e["to"] == to:
            return e
    return None


def through_node_errors(result):
    """Validator errors that report an edge crossing a node."""
    return [e for e in result["errors"] if "Edge through node" in e]

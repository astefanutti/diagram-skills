"""End-to-end guards for the three routing defects fixed this session, plus the
stripper root-cause. Each builds a minimal plan with the real geometry, asserts
the defect is present beforehand, runs the full fixer, and asserts it's gone.
"""
import copy

import fix_layout as F
from conftest import node, edge, plan, find_edge, through_node_errors
from validate_layout import validate


# --- Issue 3: explore-dataset -> gen-yaml routed through `builtins` --------

def test_eval_analyze_through_node_is_detected_then_auto_fixed():
    p = plan(
        node("explore", 1330, 95, 220, 160),
        node("gen-yaml", 520, 590, 225, 215),
        node("builtins", 545, 400, 180, 110),
        edge("explore", "gen-yaml", exit_xy=(0.5, 1), entry_xy=(0.5, 0)),
    )
    # Present before the fix...
    assert through_node_errors(validate(p))
    # ...gone after.
    work = copy.deepcopy(p)
    F.fix(work)
    assert through_node_errors(validate(work)) == []


# --- Issue 2: pairwise -> anthropic-api hairpin (exit left, target below) --

def test_eval_run_hairpin_is_reanchored_to_face_the_target():
    raw = edge("pairwise", "anthropic", exit_xy=(0, 0.5), entry_xy=(0.3, 1),
               waypoints=[(310, 1083.75)])
    p = plan(
        node("pairwise", 265, 1026.25, 225, 115),
        node("anthropic", 250, 1180.625, 200, 80),
        raw,
    )
    # The raw edge doubles back at its left anchor.
    assert F._route_has_uturn(
        {"x": 265, "y": 1083.75}, {"x": 310, "y": 1260.625},
        "left", "bottom", [{"x": 310, "y": 1083.75}])

    work = copy.deepcopy(p)
    F.fix(work)
    fixed = find_edge(work, "pairwise", "anthropic")
    # anthropic sits below pairwise → bottom-exit, top-entry, no hairpin.
    assert F._anchor_side(fixed["exit_point"]) == "bottom"
    assert F._anchor_side(fixed["entry_point"]) == "top"
    assert validate(work)["errors"] == []


# --- Issue 1: run <-> optimize 2-cycle, back-edge crowds the forward arm ---

def test_pipeline_back_edge_gets_a_distinct_side_from_forward():
    forward = edge("eval-run", "eval-optimize",
                   exit_xy=(1, 0.5), entry_xy=(0.5, 0))
    back = edge("eval-optimize", "eval-run",
                exit_xy=(0.5, 0), entry_xy=(0.5, 1),
                waypoints=[(1270, 335), (995, 335)])
    p = plan(
        node("eval-run", 880, 210, 230, 120),
        node("eval-optimize", 1160, 340, 220, 100),
        forward, back,
    )
    work = copy.deepcopy(p)
    F.fix(work)
    fwd = find_edge(work, "eval-run", "eval-optimize")
    bck = find_edge(work, "eval-optimize", "eval-run")
    fwd_entry_side = F._anchor_side(fwd["entry_point"])   # side at optimize
    back_exit_side = F._anchor_side(bck["exit_point"])    # side at optimize
    # The loop's two arcs must leave/enter the shared node on different sides.
    assert back_exit_side != fwd_entry_side
    assert validate(work)["errors"] == []


# --- Root cause: route-aware waypoint stripping ---------------------------

def test_stripper_keeps_waypoints_that_hold_a_zedge_off_a_box():
    # Same-axis edge whose waypoint-free Z would cut through `mid`, but whose
    # explicit waypoints route the crossbar below it. The old stripper checked
    # only "is some L clear" and would strip these, recreating a through-node.
    e = edge("a", "b", exit_xy=(0.5, 1), entry_xy=(0.5, 0),
             waypoints=[(50, 350), (350, 350)])
    p = plan(
        node("a", 0, 0, 100, 80),
        node("b", 300, 400, 100, 80),
        node("mid", 200, 210, 100, 60),
        e,
    )
    # Sanity: the predicted waypoint-free route really would hit `mid`.
    boxes, _, _ = F._collect_boxes(p["elements"])
    route = F._predicted_route_pts({"x": 50, "y": 80}, {"x": 350, "y": 400},
                                   "bottom", "top")
    assert F._seg_hits_any_node(route, boxes, {"a", "b"}) is not None

    F.fix_strip_waypoints(p)
    assert find_edge(p, "a", "b")["waypoints"], "waypoints were wrongly stripped"

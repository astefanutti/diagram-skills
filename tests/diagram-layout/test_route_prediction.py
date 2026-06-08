"""Unit tests for the shared route-prediction model in fix_layout.

These functions are the single source of truth the validator, stripper and
rerouter all rely on, so they're tested directly.
"""
import fix_layout as F


def _xy(p):
    return (p["x"], p["y"])


# --- _predicted_route_pts: the exact path draw.io auto-draws ---------------

def test_aligned_anchors_are_a_straight_segment():
    # Same x → straight vertical, no intermediate corners.
    route = F._predicted_route_pts({"x": 100, "y": 0}, {"x": 100, "y": 200},
                                   "bottom", "top")
    assert [_xy(p) for p in route] == [(100, 0), (100, 200)]


def test_perpendicular_sides_make_a_single_corner_L():
    # right-exit + top-entry → one corner at (entry_x, exit_y).
    route = F._predicted_route_pts({"x": 0, "y": 50}, {"x": 200, "y": 300},
                                   "right", "top")
    assert [_xy(p) for p in route] == [(0, 50), (200, 50), (200, 300)]


def test_same_axis_sides_make_a_Z_with_midpoint_crossbar():
    # bottom-exit + top-entry → 3-segment Z; crossbar at the y-midpoint.
    # This is the case the old code mis-modelled as a plain L.
    route = F._predicted_route_pts({"x": 0, "y": 100}, {"x": 400, "y": 300},
                                   "bottom", "top")
    assert [_xy(p) for p in route] == [
        (0, 100), (0, 200), (400, 200), (400, 300)]


def test_left_right_same_axis_make_a_horizontal_Z():
    route = F._predicted_route_pts({"x": 100, "y": 0}, {"x": 500, "y": 200},
                                   "right", "left")
    assert [_xy(p) for p in route] == [
        (100, 0), (300, 0), (300, 200), (500, 200)]


# --- _route_has_uturn: hairpin / wrong-facing-anchor detection ------------

def test_uturn_when_exit_anchor_faces_away_from_target():
    # Exit on the LEFT but the first move goes RIGHT — the eval-run
    # pairwise->anthropic hairpin.
    exit_abs = {"x": 265, "y": 1083}
    entry_abs = {"x": 310, "y": 1260}
    wps = [{"x": 310, "y": 1083}]
    assert F._route_has_uturn(exit_abs, entry_abs, "left", "bottom", wps) is True


def test_no_uturn_for_a_clean_outward_exit():
    # Bottom exit, target below — moves outward, no reversal.
    assert F._route_has_uturn({"x": 100, "y": 200}, {"x": 100, "y": 500},
                              "bottom", "top", []) is False


def test_uturn_when_entry_anchor_is_approached_from_inside():
    # Entry on the TOP but the last point is BELOW it → arriving upward into a
    # top anchor is a reversal.
    assert F._route_has_uturn({"x": 0, "y": 0}, {"x": 100, "y": 100},
                              "bottom", "top",
                              [{"x": 100, "y": 300}]) is True


# --- _best_anchor_route: pick the cleanest facing side pair ----------------

def test_best_anchor_picks_facing_sides_for_a_target_below():
    src = {"x": 0, "y": 0, "width": 100, "height": 100}
    tgt = {"x": 0, "y": 300, "width": 100, "height": 100}
    boxes = [{"id": "s", "x": 0, "y": 0, "w": 100, "h": 100},
             {"id": "t", "x": 0, "y": 300, "w": 100, "h": 100}]
    res = F._best_anchor_route(src, tgt, boxes, {"s", "t"})
    assert res is not None
    ep, np_ = res
    assert F._anchor_side(ep) == "bottom"
    assert F._anchor_side(np_) == "top"


def test_best_anchor_avoids_entering_target_through_its_body():
    # pairwise above anthropic, slightly offset in x: a bottom->right L would
    # land its corner inside anthropic; the scorer must prefer the bottom->top
    # Z that enters cleanly from above.
    pairwise = {"x": 265, "y": 1026, "width": 225, "height": 115}
    anthropic = {"x": 250, "y": 1180, "width": 200, "height": 80}
    boxes = [{"id": "p", "x": 265, "y": 1026, "w": 225, "h": 115},
             {"id": "a", "x": 250, "y": 1180, "w": 200, "h": 80}]
    ep, np_ = F._best_anchor_route(pairwise, anthropic, boxes, {"p", "a"})
    assert F._anchor_side(ep) == "bottom"
    assert F._anchor_side(np_) == "top"


def test_best_anchor_returns_none_when_sandwiched():
    # Real eval-dataset geometry: `from-traces` sits in the column directly
    # between `expand` and `run-results`, so no side pair can avoid it.
    expand = {"x": 1145, "y": 480, "width": 225, "height": 150}
    run_results = {"x": 1160, "y": 940, "width": 195, "height": 140}
    boxes = [{"id": "expand", "x": 1145, "y": 480, "w": 225, "h": 150},
             {"id": "from-traces", "x": 1145, "y": 680, "w": 225, "h": 150},
             {"id": "run-results", "x": 1160, "y": 940, "w": 195, "h": 140}]
    assert F._best_anchor_route(
        expand, run_results, boxes, {"expand", "run-results"}) is None


def test_best_anchor_penalty_steers_away_from_forbidden_sides():
    # With clear space all around, penalizing the natural facing sides pushes
    # the choice elsewhere — the mechanism fix_cycle_anchors relies on.
    src = {"x": 0, "y": 0, "width": 100, "height": 100}
    tgt = {"x": 0, "y": 300, "width": 100, "height": 100}
    boxes = [{"id": "s", "x": 0, "y": 0, "w": 100, "h": 100},
             {"id": "t", "x": 0, "y": 300, "w": 100, "h": 100}]
    base_ep, _ = F._best_anchor_route(src, tgt, boxes, {"s", "t"})
    assert F._anchor_side(base_ep) == "bottom"
    pen_ep, _ = F._best_anchor_route(src, tgt, boxes, {"s", "t"},
                                     penalize_exit={"bottom"})
    assert F._anchor_side(pen_ep) != "bottom"

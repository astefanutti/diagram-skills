"""The validator must catch waypoint-free edges whose auto-route crosses a node
— the blind spot that let edge-through-box defects render "validation clean".
"""
from conftest import node, edge, plan, through_node_errors
from validate_layout import validate


def test_waypoint_free_edge_through_a_box_is_flagged():
    # explore-dataset -> gen-yaml (eval-analyze, issue 3): a same-axis
    # bottom->top edge whose Z crossbar/stem cut through `builtins`.
    p = plan(
        node("explore", 1330, 95, 220, 160),
        node("gen-yaml", 520, 590, 225, 215),
        node("builtins", 545, 400, 180, 110),
        edge("explore", "gen-yaml", exit_xy=(0.5, 1), entry_xy=(0.5, 0)),
    )
    errs = through_node_errors(validate(p))
    assert any("explore->gen-yaml" in e and "builtins" in e for e in errs)
    assert any("no waypoints" in e for e in errs)


def test_clear_waypoint_free_edge_is_not_flagged():
    # Same two endpoints, but nothing in between → must NOT flag.
    p = plan(
        node("explore", 1330, 95, 220, 160),
        node("gen-yaml", 520, 590, 225, 215),
        edge("explore", "gen-yaml", exit_xy=(0.5, 1), entry_xy=(0.5, 0)),
    )
    assert through_node_errors(validate(p)) == []


def test_target_box_itself_is_never_a_false_positive():
    # The route necessarily touches its own endpoints; those must be skipped.
    p = plan(
        node("a", 0, 0, 120, 80),
        node("b", 0, 200, 120, 80),
        edge("a", "b", exit_xy=(0.5, 1), entry_xy=(0.5, 0)),
    )
    assert through_node_errors(validate(p)) == []


def test_edge_into_container_child_not_flagged_against_container():
    # An edge terminating inside a container exits via the container border;
    # it must not be flagged against the container or its siblings.
    container = {
        "type": "container", "id": "grp", "x": 400, "y": 0,
        "width": 240, "height": 320,
        "children": [
            {"id": "c1", "rel_x": 20, "rel_y": 40, "width": 200, "height": 100},
            {"id": "c2", "rel_x": 20, "rel_y": 180, "width": 200, "height": 100},
        ],
    }
    p = plan(
        node("src", 0, 60, 120, 80),
        container,
        edge("src", "c2", exit_xy=(1, 0.5), entry_xy=(0, 0.5)),
    )
    # c1 is a sibling above c2; a clean left-entry into c2 shouldn't be a
    # false through-node on the container or c1.
    errs = through_node_errors(validate(p))
    assert errs == [], errs


def test_dropped_edge_check_still_runs_with_spec():
    p = plan(
        node("a", 0, 0, 100, 80),
        node("b", 300, 0, 100, 80),
        edge("a", "b", exit_xy=(1, 0.5), entry_xy=(0, 0.5)),
    )
    spec = {"edges": [{"from": "a", "to": "b"},
                      {"from": "a", "to": "c"}]}  # c->? not present
    # 'c' isn't a node in the plan, so the missing edge is skipped (only edges
    # whose endpoints exist are required). No crash, no false drop.
    res = validate(p, spec)
    assert not any("Dropped edges" in e for e in res["errors"])

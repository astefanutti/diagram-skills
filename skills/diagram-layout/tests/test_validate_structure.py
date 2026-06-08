"""Validator structural guards added during the session: edge preservation
(catches a layout that dropped edges), non-orthogonal edge styles, and the
wrong-schema / empty-plan guards.
"""
from conftest import node, edge, plan
from validate_layout import validate


def _has(result, needle):
    return any(needle in e for e in result["errors"])


# --- Edge preservation ----------------------------------------------------

def test_missing_spec_edge_is_flagged_as_dropped():
    p = plan(node("a", 0, 0, 100, 80), node("b", 300, 0, 100, 80))  # no edge
    spec = {"edges": [{"from": "a", "to": "b"}]}
    assert _has(validate(p, spec), "Dropped edges")


def test_present_spec_edge_is_not_flagged():
    p = plan(node("a", 0, 0, 100, 80), node("b", 300, 0, 100, 80),
             edge("a", "b"))
    spec = {"edges": [{"from": "a", "to": "b"}]}
    assert not _has(validate(p, spec), "Dropped edges")


def test_bundled_edge_via_container_counts_as_preserved():
    # spec has w1->db; plan folded w1 into container `grp` with a grp->db edge.
    container = {
        "type": "container", "id": "grp", "x": 0, "y": 0,
        "width": 160, "height": 200,
        "children": [{"id": "w1", "rel_x": 16, "rel_y": 36,
                      "width": 100, "height": 80}],
    }
    p = plan(container, node("db", 400, 0, 120, 80), edge("grp", "db"))
    spec = {"edges": [{"from": "w1", "to": "db"}]}
    assert not _has(validate(p, spec), "Dropped edges")


def test_back_edges_are_exempt_from_preservation():
    p = plan(node("a", 0, 0, 100, 80), node("b", 300, 0, 100, 80))
    spec = {"edges": [{"from": "a", "to": "b", "is_back_edge": True}]}
    assert not _has(validate(p, spec), "Dropped edges")


# --- Edge style sanity ----------------------------------------------------

def test_non_orthogonal_edge_style_is_flagged():
    e = edge("a", "b", style="edgeStyle=elbowEdgeStyle;rounded=0;")
    p = plan(node("a", 0, 0, 100, 80), node("b", 300, 0, 100, 80), e)
    assert _has(validate(p), "Edge style not orthogonal")


def test_orthogonal_edge_style_is_accepted():
    e = edge("a", "b", style="edgeStyle=orthogonalEdgeStyle;rounded=1;")
    p = plan(node("a", 0, 0, 100, 80), node("b", 300, 0, 100, 80), e)
    assert not _has(validate(p), "Edge style not orthogonal")


# --- Schema guards --------------------------------------------------------

def test_old_nodes_edges_schema_is_rejected():
    res = validate({"nodes": [{"id": "a"}], "edges": []})
    assert _has(res, "wrong schema")


def test_empty_plan_is_rejected():
    res = validate({"elements": []})
    assert _has(res, "no 'elements'")

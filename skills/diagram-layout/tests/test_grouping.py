"""Fan-in grouping (graph_analysis) and its deterministic enforcement
(fix_layout). The recurring concern was robustness: group genuine parallel
fan-ins, but NEVER over-group a fan-out or a single-sink convergence.
"""
import graph_analysis as G
import fix_layout as F
from conftest import node, edge, plan, find_edge


def _grouped_containers(spec):
    return [c for c in spec.get("containers", []) if c.get("grouped")]


# --- group_shared_fan_in: positive cases ---------------------------------

def test_service_group_wraps_actions_on_a_shared_external_resource():
    # ≥3 dispatcher children that all hit one role=external node (eval-mlflow):
    # build the container even though the per-action edges are labelled.
    spec = {
        "nodes": [
            {"id": "read-config"},
            {"id": "sync"}, {"id": "log-results"},
            {"id": "push-fb"}, {"id": "pull-fb"},
            {"id": "mlflow", "role": "external"},
        ],
        "edges": [
            {"from": "read-config", "to": "sync"},
            {"from": "read-config", "to": "log-results"},
            {"from": "read-config", "to": "push-fb"},
            {"from": "read-config", "to": "pull-fb"},
            {"from": "sync", "to": "mlflow", "label": "sync dataset"},
            {"from": "log-results", "to": "mlflow", "label": "log results"},
            {"from": "push-fb", "to": "mlflow", "label": "push feedback"},
            {"from": "pull-fb", "to": "mlflow", "label": "pull feedback"},
        ],
    }
    n = G.group_shared_fan_in(spec)
    assert n == 1
    groups = _grouped_containers(spec)
    assert len(groups) == 1
    assert set(groups[0]["children"]) == {"sync", "log-results",
                                          "push-fb", "pull-fb"}
    # Distinct labels → NOT bundled; every action keeps its own →mlflow edge.
    assert not any(e["from"].startswith("group-") and e["to"] == "mlflow"
                   for e in spec["edges"])
    assert sum(1 for e in spec["edges"] if e["to"] == "mlflow") == 4


def test_bundle_group_collapses_a_double_fan_in_into_one_edge_per_sink():
    # 3 independent workers → {report, db}, all unlabelled → lossless bundle.
    spec = {
        "nodes": [{"id": "src"}, {"id": "w1"}, {"id": "w2"}, {"id": "w3"},
                  {"id": "report"}, {"id": "db"}],
        "edges": [
            {"from": "src", "to": "w1"}, {"from": "src", "to": "w2"},
            {"from": "src", "to": "w3"},
            {"from": "w1", "to": "report"}, {"from": "w2", "to": "report"},
            {"from": "w3", "to": "report"},
            {"from": "w1", "to": "db"}, {"from": "w2", "to": "db"},
            {"from": "w3", "to": "db"},
        ],
    }
    G.group_shared_fan_in(spec)
    groups = _grouped_containers(spec)
    assert len(groups) == 1
    gid = groups[0]["id"]
    assert set(groups[0]["children"]) == {"w1", "w2", "w3"}
    # One bundled edge per sink, and the 6 individual member edges are gone.
    pairs = {(e["from"], e["to"]) for e in spec["edges"]}
    assert (gid, "report") in pairs and (gid, "db") in pairs
    assert not any(f in {"w1", "w2", "w3"} and t in {"report", "db"}
                   for f, t in pairs)


# --- group_shared_fan_in: must NOT over-group -----------------------------

def test_fan_out_is_not_grouped():
    # One decision → three alternatives is a fan-OUT, not a convergence.
    spec = {
        "nodes": [{"id": "assess"}, {"id": "fast"}, {"id": "full"},
                  {"id": "incremental"}],
        "edges": [{"from": "assess", "to": "fast"},
                  {"from": "assess", "to": "full"},
                  {"from": "assess", "to": "incremental"}],
    }
    assert G.group_shared_fan_in(spec) == 0
    assert _grouped_containers(spec) == []


def test_single_plain_sink_convergence_is_not_grouped():
    # 3 sources → one PLAIN sink (only one shared target, not external):
    # a container would add nothing, so it must not fire.
    spec = {
        "nodes": [{"id": "a"}, {"id": "b"}, {"id": "c"}, {"id": "merge"}],
        "edges": [{"from": "a", "to": "merge"}, {"from": "b", "to": "merge"},
                  {"from": "c", "to": "merge"}],
    }
    assert G.group_shared_fan_in(spec) == 0
    assert _grouped_containers(spec) == []


# --- fix_enforce_groups: re-apply grouping the LLM ignored ----------------

def test_enforcement_rebuilds_container_and_bundles_when_layout_is_flat():
    # spec says group-1 wraps w1..w3 with one bundled edge to db; the plan
    # placed them flat with individual edges (LLM ignored the grouping).
    spec = {
        "nodes": [{"id": "w1"}, {"id": "w2"}, {"id": "w3"}, {"id": "db"}],
        "edges": [{"from": "group-1", "to": "db", "label": "", "style": "solid"}],
        "containers": [{"id": "group-1", "label": "Workers",
                        "children": ["w1", "w2", "w3"], "grouped": True}],
    }
    p = plan(
        node("w1", 0, 0, 100, 80), node("w2", 0, 120, 100, 80),
        node("w3", 0, 240, 100, 80), node("db", 400, 120, 120, 80),
        edge("w1", "db"), edge("w2", "db"), edge("w3", "db"),
    )
    fixes = F.fix_enforce_groups(p, spec)
    assert fixes == 1

    container = next((e for e in p["elements"]
                      if e.get("id") == "group-1"), None)
    assert container is not None and container["type"] == "container"
    assert {c["id"] for c in container["children"]} == {"w1", "w2", "w3"}
    # children carry parent-relative coords now
    assert all("rel_x" in c and "rel_y" in c for c in container["children"])

    # Individual member edges folded into the single bundled edge.
    assert find_edge(p, "group-1", "db") is not None
    assert all(find_edge(p, w, "db") is None for w in ("w1", "w2", "w3"))


def test_enforcement_is_idempotent_when_container_already_present():
    spec = {
        "nodes": [{"id": "w1"}, {"id": "w2"}, {"id": "w3"}, {"id": "db"}],
        "edges": [{"from": "group-1", "to": "db", "label": "", "style": "solid"}],
        "containers": [{"id": "group-1", "label": "Workers",
                        "children": ["w1", "w2", "w3"], "grouped": True}],
    }
    container = {
        "type": "container", "id": "group-1", "x": 0, "y": 0,
        "width": 160, "height": 360, "label_html": "<b>Workers</b>",
        "children": [
            {"type": "node", "id": "w1", "rel_x": 16, "rel_y": 36,
             "width": 100, "height": 80},
            {"type": "node", "id": "w2", "rel_x": 16, "rel_y": 140,
             "width": 100, "height": 80},
            {"type": "node", "id": "w3", "rel_x": 16, "rel_y": 244,
             "width": 100, "height": 80},
        ],
    }
    p = plan(container, node("db", 400, 120, 120, 80),
             edge("group-1", "db"))
    assert F.fix_enforce_groups(p, spec) == 0

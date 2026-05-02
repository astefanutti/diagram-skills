#!/usr/bin/env python3
"""Analyze graph topology using networkx."""

import json
import sys
from collections import Counter

try:
    import networkx as nx
except ImportError:
    print("networkx not installed. Install with: pip install networkx",
          file=sys.stderr)
    sys.exit(1)


def analyze(spec):
    G = nx.DiGraph()

    for n in spec["nodes"]:
        G.add_node(n["id"], **n)
    for e in spec["edges"]:
        G.add_edge(e["from"], e["to"],
                    label=e.get("label", ""),
                    style=e.get("style", "solid"))

    # Remove back-edges for layering
    try:
        cycles = list(nx.simple_cycles(G))
    except Exception:
        cycles = []

    dag = G.copy()
    back_edges = []
    while not nx.is_directed_acyclic_graph(dag):
        try:
            cycle = next(nx.simple_cycles(dag))
            u, v = cycle[-1], cycle[0]
            dag.remove_edge(u, v)
            back_edges.append([u, v])
        except StopIteration:
            break

    # Topological layers via longest path
    layers = {}
    for node in nx.topological_sort(dag):
        pred_layers = [layers[p] for p in dag.predecessors(node) if p in layers]
        layers[node] = max(pred_layers, default=-1) + 1

    # Assign nodes without edges to layer 0
    for n in spec["nodes"]:
        if n["id"] not in layers:
            layers[n["id"]] = 0

    # Fan-out / fan-in
    fan_out = {n: list(G.successors(n))
               for n in G if G.out_degree(n) > 1}
    fan_in = {n: list(G.predecessors(n))
              for n in G if G.in_degree(n) > 1}

    # Topology class
    max_out = max((G.out_degree(n) for n in G), default=0)
    max_in = max((G.in_degree(n) for n in G), default=0)
    n_layers = max(layers.values(), default=0) + 1
    layer_counts = Counter(layers.values())
    max_per_layer = max(layer_counts.values(), default=1)

    if max_out >= 4:
        topo_class = "hub-spoke"
    elif max_out <= 1 and max_in <= 1:
        topo_class = "pipeline"
    elif len(fan_out) <= 2 and len(fan_in) <= 2:
        topo_class = "diamond"
    else:
        topo_class = "complex"

    # Suggested aspect ratio
    if topo_class == "pipeline":
        aspect = max(2.5, n_layers / max(max_per_layer, 1))
    elif topo_class == "hub-spoke":
        aspect = 1.3
    elif topo_class == "diamond":
        aspect = 2.0
    else:
        aspect = 2.0

    # Mark back-edges in the spec
    back_set = {(u, v) for u, v in back_edges}
    for e in spec["edges"]:
        if (e["from"], e["to"]) in back_set:
            e["is_back_edge"] = True

    # Nodes per layer for column planning
    nodes_by_layer = {}
    for nid, layer in layers.items():
        nodes_by_layer.setdefault(layer, []).append(nid)

    # Suggested row assignment for multi-row layouts
    # Group layers into rows of ~4-5 columns each
    max_cols_per_row = 5
    suggested_rows = {}
    for nid, layer in layers.items():
        suggested_rows[nid] = layer // max_cols_per_row

    spec["topology"] = {
        "layers": layers,
        "nodes_by_layer": nodes_by_layer,
        "suggested_rows": suggested_rows,
        "fan_out_points": fan_out,
        "fan_in_points": fan_in,
        "back_edges": back_edges,
        "topology_class": topo_class,
        "suggested_aspect_ratio": round(aspect, 1),
        "layer_count": n_layers,
        "max_nodes_per_layer": max_per_layer,
    }

    return spec


def main():
    if len(sys.argv) < 2:
        print("Usage: graph_analysis.py <graph-spec.json>", file=sys.stderr)
        sys.exit(1)

    with open(sys.argv[1]) as f:
        spec = json.load(f)

    result = analyze(spec)
    json.dump(result, sys.stdout, indent=2)


if __name__ == "__main__":
    main()

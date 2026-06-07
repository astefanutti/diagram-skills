#!/usr/bin/env python3
"""Analyze graph topology using networkx."""

import json
import re
import sys
from collections import Counter, defaultdict

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
    # Topology-aware columns per row: pipelines can be wider
    if topo_class == "pipeline":
        max_cols_per_row = 7
    elif topo_class == "complex":
        max_cols_per_row = 4
    else:
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

    group_shared_fan_in(spec)

    return spec


def _group_label(member_ids, spec):
    """Pick a label for an auto-created grouping container.

    Use a word common to every member's label if one exists; otherwise fall
    back to a generic name (the author/LLM can rename it).
    """
    labels = {n["id"]: (n.get("label") or n["id"])
              for n in spec.get("nodes", [])}
    token_sets = []
    for mid in member_ids:
        words = {w.lower() for w in re.split(r"[\s/_-]+", labels.get(mid, mid))
                 if len(w) > 2}
        token_sets.append(words)
    common = set.intersection(*token_sets) if token_sets else set()
    if common:
        return sorted(common, key=len, reverse=True)[0].capitalize()
    return "Operations"


def group_shared_fan_in(spec, min_group=3):
    """Collapse a parallel fan-in into a container with one bundled edge.

    When ≥`min_group` mutually-independent nodes (parallel siblings, not a
    chain) converge on **≥2 distinct shared targets** — the crossing-prone
    double fan-in — wrap them in a container and, for each *lossless* target
    (edges un-labelled, or all sharing one identical label), replace the N
    individual edges with a single container→target edge. This is the
    deterministic version of layout-rules Rule 5c — it removes the double
    fan-in crossings the LLM rarely fixes on its own.

    Lossless only: a fan-in whose edges carry distinct labels (e.g. parallel
    workers each writing to a database with a different operation label) is left
    as individual edges into the container's children, preserving every label.
    Members that are themselves containers are allowed (the container simply
    nests).
    """
    edges = spec.get("edges", [])
    fwd = [e for e in edges if not e.get("is_back_edge")]
    if not fwd:
        return 0

    preds = defaultdict(set)        # node -> forward predecessors
    for e in fwd:
        preds[e["to"]].add(e["from"])

    # node id -> set of labels it uses to reach a given target
    edge_labels = defaultdict(set)
    edge_styles = defaultdict(list)
    for e in fwd:
        key = (e["from"], e["to"])
        edge_labels[key].add(e.get("label", "") or "")
        edge_styles[key].append(e.get("style", "solid"))

    existing_child = set()
    for c in spec.get("containers", []):
        for ch in c.get("children", []):
            existing_child.add(ch if isinstance(ch, str) else ch.get("id"))
    taken_ids = {n["id"] for n in spec.get("nodes", [])}
    taken_ids |= {c["id"] for c in spec.get("containers", [])}

    succ = defaultdict(set)         # node -> forward successors
    for e in fwd:
        succ[e["from"]].add(e["to"])

    def _shared_targets(member_set):
        """Targets reached (forward) by ≥2 members — the convergence points."""
        counts = Counter()
        for m in member_set:
            for t in succ.get(m, set()):
                if t not in member_set:
                    counts[t] += 1
        return {t for t, c in counts.items() if c >= 2}

    # Candidate fan-in groups: per (target, label), the lossless source set.
    by_target_label = defaultdict(lambda: defaultdict(list))
    for e in fwd:
        by_target_label[e["to"]][e.get("label", "") or ""].append(e["from"])

    candidates = []
    for tgt, by_label in by_target_label.items():
        for label, srcs in by_label.items():
            members = [s for s in dict.fromkeys(srcs)
                       if s not in existing_child and s != tgt]
            if len(members) < min_group:
                continue
            ms = set(members)
            # Members must be mutually independent — parallel siblings, not a
            # chain/sequence (those link to each other). A *shared* predecessor
            # is deliberately NOT required: the LLM sometimes inserts an
            # intermediate step before one branch (dispatch → interpret → sync),
            # so the branches don't share a single predecessor even though they
            # are plainly parallel. Requiring it silently dropped the grouping.
            if any(e["from"] in ms and e["to"] in ms for e in fwd):
                continue
            # Only group a genuine multi-fan-in: the members must converge on
            # ≥2 distinct shared targets (the crossing-prone case grouping
            # solves, e.g. parallel workers → {report, database}). A set that funnels
            # to a single sink (e.g. decision branches → one node) gains nothing
            # from a container, so it's left alone. This is role-agnostic — it
            # works whether the dispatcher is modelled as a decision or not.
            if len(_shared_targets(ms)) < 2:
                continue
            candidates.append((len(members), tgt, label, tuple(members)))

    # Form groups greedily from the largest candidate; each node used once.
    candidates.sort(key=lambda c: -c[0])
    used = set()
    layers = spec.get("topology", {}).get("layers", {})
    node_order = [n["id"] for n in spec.get("nodes", [])]
    fixes = 0
    gnum = 0

    for _size, _tgt, _label, members in candidates:
        members = tuple(m for m in members if m not in used)
        if len(members) < min_group:
            continue
        member_set = set(members)
        if len(_shared_targets(member_set)) < 2:
            continue

        # Every target this exact group reaches losslessly (same label across
        # all members) becomes a bundled edge.
        bundles = []
        for cand_tgt in {e["to"] for e in fwd if e["from"] in member_set}:
            labs = set()
            ok = True
            for m in members:
                ml = edge_labels.get((m, cand_tgt))
                if not ml or len(ml) != 1:
                    ok = False
                    break
                labs |= ml
            if not ok or len(labs) != 1:
                continue
            bundles.append((cand_tgt, next(iter(labs))))
        if not bundles:
            continue

        gnum += 1
        gid = f"group-{gnum}"
        while gid in taken_ids:
            gnum += 1
            gid = f"group-{gnum}"
        taken_ids.add(gid)

        # Pull in parallel siblings that also reach a bundled target but whose
        # edge is labelled (so it can't be losslessly bundled — it's kept as an
        # individual edge into the child). This groups the whole action set, not
        # just the losslessly-bundled core (e.g. a pull-feedback that writes
        # review.yaml alongside the sync/log/push that bundle to the report).
        bundle_targets = {t for t, _ in bundles}
        container_members = set(member_set)
        for nid in node_order:
            if nid in container_members or nid in used or nid in existing_child:
                continue
            if not (succ.get(nid, set()) & bundle_targets):
                continue
            if any((e["from"] == nid and e["to"] in container_members) or
                   (e["from"] in container_members and e["to"] == nid)
                   for e in fwd):
                continue
            container_members.add(nid)

        ordered = [nid for nid in node_order if nid in container_members]
        ordered += [m for m in container_members if m not in ordered]
        spec.setdefault("containers", []).append({
            "id": gid,
            "label": _group_label(ordered, spec),
            "children": ordered,
            "grouped": True,
        })

        for cand_tgt, common_label in bundles:
            styles = [s for m in members
                      for s in edge_styles.get((m, cand_tgt), [])]
            style = "dashed" if styles and all(s == "dashed" for s in styles) else "solid"
            spec["edges"] = [
                e for e in spec["edges"]
                if not (e["from"] in member_set and e["to"] == cand_tgt
                        and not e.get("is_back_edge"))
            ]
            spec["edges"].append({
                "from": gid, "to": cand_tgt,
                "label": common_label, "style": style,
            })

        if layers:
            layers[gid] = min((layers.get(m, 0) for m in container_members),
                              default=0)
        used |= container_members
        fixes += 1

    return fixes


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

#!/usr/bin/env python3
"""Parse D2 or drawio files into a normalized graph spec JSON."""

import json
import re
import sys
import xml.etree.ElementTree as ET


def parse_d2(path):
    """Parse a D2 file into a graph spec."""
    with open(path) as f:
        content = f.read()

    nodes = {}
    edges = []
    containers = {}
    direction = "right"

    # Extract direction directive
    dir_match = re.search(r'^direction:\s*(right|down|left|up)', content, re.MULTILINE)
    if dir_match:
        direction = dir_match.group(1)

    lines = content.split("\n")
    current_block = None
    current_block_id = None
    block_depth = 0
    in_edge_block = False
    in_md_block = False
    md_node_id = None
    last_edge_idx = -1
    in_bold = False          # accumulating a multi-line **bold** title
    bold_acc = ""
    in_style_block = False   # inside the `| { ... }` style block after a |md
    style_target_id = None

    for line in lines:
        stripped = line.strip()

        if not stripped or stripped.startswith("#") or stripped.startswith("*."):
            continue

        # Inside an edge style block — look for stroke-dash
        if in_edge_block:
            if "stroke-dash" in stripped or "stroke_dash" in stripped:
                if last_edge_idx >= 0:
                    edges[last_edge_idx]["style"] = "dashed"
            if "}" in stripped:
                in_edge_block = False
            continue

        # Inside the `| { ... }` style block that follows a |md body.
        # Capture styling cues (shape, font, stroke, dash) so roles and
        # callouts can be classified, then close on the brace.
        if in_style_block:
            node = nodes.get(style_target_id)
            if node is not None:
                st = node.setdefault("_style", {})
                m = re.search(r'shape\s*:\s*([\w-]+)', stripped)
                if m:
                    st["shape"] = m.group(1)
                m = re.search(r'(?:style\.)?font\s*:\s*([\w-]+)', stripped)
                if m:
                    st["font"] = m.group(1)
                m = re.search(r'(?:style\.)?stroke-dash', stripped)
                if m:
                    st["stroke_dash"] = True
                m = re.search(r'(?:style\.)?stroke-width\s*:\s*([\d.]+)', stripped)
                if m:
                    st["stroke_width"] = m.group(1)
                m = re.search(r'(?:style\.)?stroke\s*:\s*"?(#[0-9a-fA-F]+)"?', stripped)
                if m:
                    st["stroke"] = m.group(1)
            if "}" in stripped:
                in_style_block = False
                block_depth -= 1
                if block_depth <= 0:
                    current_block_id = None
                    block_depth = 0
            continue

        # Inside a markdown (|md) content block — consume content only.
        # Never run node/edge matching on these lines: doing so is what
        # shattered callout blocks into phantom nodes (e.g. `judges: {…}`)
        # and turned `->` appearing in prose into spurious edges.
        if in_md_block:
            node = nodes.get(md_node_id)
            if stripped.startswith("|"):
                # closing pipe ends the markdown content.
                in_md_block = False
                in_bold = False
                if "{" in stripped:
                    # A `| { … }` style block follows — keep depth, capture it.
                    in_style_block = True
                    style_target_id = md_node_id
                else:
                    # Bare `|`: undo the depth increment from opening this node
                    # so an open container doesn't keep swallowing later nodes.
                    block_depth -= 1
                    if block_depth <= 0:
                        current_block_id = None
                        block_depth = 0
                continue
            # Continuation of a multi-line **bold** title (E).
            if in_bold:
                if stripped.endswith("**"):
                    bold_acc += " " + stripped[:-2].strip()
                    in_bold = False
                    if node is not None:
                        _set_md_title(node, bold_acc)
                else:
                    bold_acc += " " + stripped
                continue
            # Bold title — extract the **…** span so trailing text (F) and
            # inline content don't leak into the label.
            m = re.search(r'\*\*(.+?)\*\*', stripped)
            if m:
                if node is not None:
                    _set_md_title(node, m.group(1))
                trailing = stripped[m.end():].strip()
                if trailing and node is not None:
                    node["details"].append(trailing)
            elif stripped.startswith("**"):
                # Opening ** with no closing on this line → multi-line title.
                in_bold = True
                bold_acc = stripped[2:].strip()
            elif stripped.startswith("- "):
                if node is not None:
                    node["details"].append(stripped[2:].strip())
            else:
                # Plain content line — callout body (preserve it).
                if node is not None:
                    node.setdefault("_raw", []).append(stripped)
            continue

        # Edge chain: a -> b -> c or a <-> b, with optional label/style
        edge_match = re.match(
            r"([\w-]+(?:\s*(?:<->|->|<-)\s*[\w-]+)+)(?:\s*:\s*(.+))?$", stripped
        )
        if edge_match and re.search(r'<->|->|<-', stripped):
            chain_str = edge_match.group(1)
            label = edge_match.group(2)
            style = "solid"
            if label and "{" in label:
                if "stroke-dash" in label:
                    style = "dashed"
                label = re.sub(r"\s*\{.*", "", label).strip()
            if label:
                label = label.strip('" ')
            # Split chain into individual edges
            parts = re.split(r'\s*(<->|->|<-)\s*', chain_str)
            # parts = [node, arrow, node, arrow, node, ...]
            for i in range(0, len(parts) - 2, 2):
                left_node, arrow, right_node = parts[i], parts[i + 1], parts[i + 2]
                edge_label = (label or "") if i == len(parts) - 3 else ""
                if arrow == "<->":
                    edges.append({"from": left_node, "to": right_node, "label": edge_label, "style": style})
                    edges.append({"from": right_node, "to": left_node, "label": edge_label, "style": style})
                elif arrow == "<-":
                    edges.append({"from": right_node, "to": left_node, "label": edge_label, "style": style})
                else:
                    edges.append({"from": left_node, "to": right_node, "label": edge_label, "style": style})
            last_edge_idx = len(edges) - 1
            if "{" in stripped and "}" not in stripped:
                in_edge_block = True
            continue

        # Simple assignment: name: "value" — check BEFORE block_match
        # to avoid {field} inside quotes triggering block detection
        simple_match = re.match(r"([\w-]+)\s*:\s*\"(.+?)\"", stripped)
        if simple_match:
            node_id = simple_match.group(1)
            label = simple_match.group(2)
            if current_block_id and block_depth >= 1:
                if current_block_id not in containers:
                    containers[current_block_id] = {
                        "id": current_block_id,
                        "label": nodes.get(current_block_id, {}).get(
                            "label", current_block_id
                        ),
                        "children": [],
                    }
                containers[current_block_id]["children"].append(node_id)
            nodes[node_id] = {
                "id": node_id,
                "label": label.split("\\n")[0],
                "details": label.split("\\n")[1:],
                "role": "processing",
            }
            # Trailing { after quotes opens a style/property block
            trailing = stripped[simple_match.end():]
            if "{" in trailing and "}" not in trailing:
                block_depth += 1
            continue

        # Block start: name: label { or name: { or name {
        block_match = re.match(
            r"([\w-]+)\s*:\s*(.+?)?\s*\{?\s*$", stripped
        )
        if block_match and "{" in stripped:
            block_id = block_match.group(1)
            label = (block_match.group(2) or "").strip('" ')
            if current_block_id and block_depth == 1:
                # Child of current container
                if current_block_id not in containers:
                    containers[current_block_id] = {
                        "id": current_block_id,
                        "label": nodes.get(current_block_id, {}).get(
                            "label", current_block_id
                        ),
                        "children": [],
                    }
                containers[current_block_id]["children"].append(block_id)
                nodes[block_id] = {
                    "id": block_id,
                    "label": label.split("\\n")[0] if label else block_id,
                    "details": label.split("\\n")[1:] if label else [],
                    "role": "processing",
                }
                block_depth += 1
            else:
                current_block_id = block_id
                block_depth = 1
                nodes[block_id] = {
                    "id": block_id,
                    "label": label.split("\\n")[0] if label else block_id,
                    "details": label.split("\\n")[1:] if label else [],
                    "role": _guess_role(block_id, label or ""),
                }
            continue

        # Block with markdown content: name: |md  (or |||md etc. — D2 allows
        # any odd number of pipes so the block body can itself contain `|`).
        md_match = re.match(r"([\w-]+)\s*:\s*\|+md\s*$", stripped)
        if md_match:
            block_id = md_match.group(1)
            if current_block_id and current_block_id != block_id and block_depth >= 1:
                # markdown node nested inside an open container — register it
                # as a child (this was previously dropped, flattening the
                # container).
                if current_block_id not in containers:
                    containers[current_block_id] = {
                        "id": current_block_id,
                        "label": nodes.get(current_block_id, {}).get(
                            "label", current_block_id
                        ),
                        "children": [],
                    }
                if block_id not in containers[current_block_id]["children"]:
                    containers[current_block_id]["children"].append(block_id)
                nodes[block_id] = {
                    "id": block_id,
                    "label": block_id,
                    "details": [],
                    "role": "processing",
                }
                block_depth += 1
            else:
                current_block_id = block_id
                block_depth = 1
                nodes[block_id] = {
                    "id": block_id,
                    "label": block_id,
                    "details": [],
                    "role": _guess_role(block_id, ""),
                }
            # Markdown content (and the node's title/bullets) belongs to this
            # node, not the enclosing container.
            in_md_block = True
            md_node_id = block_id
            continue

        # Closing brace ends the current style / container block.
        if stripped == "}":
            block_depth -= 1
            if block_depth <= 0:
                current_block_id = None
                block_depth = 0
            continue
        # Any other line inside a block (style props, stray markup) is
        # ignored — only the declarations matched above contribute
        # nodes/edges/containers.

    # Pull callouts out of nodes[]; refine roles from styling + title.
    callouts = _extract_callouts(nodes, edges, containers)
    for node in nodes.values():
        node["role"] = _refine_role(node, edges)
    for node in nodes.values():
        node.pop("_style", None)
        node.pop("_raw", None)

    # Mark back-edges
    node_order = list(nodes.keys())
    for edge in edges:
        src_idx = (
            node_order.index(edge["from"])
            if edge["from"] in node_order
            else -1
        )
        tgt_idx = (
            node_order.index(edge["to"])
            if edge["to"] in node_order
            else -1
        )
        edge["is_back_edge"] = src_idx > tgt_idx if src_idx >= 0 and tgt_idx >= 0 else False

    return {
        "direction": direction,
        "nodes": list(nodes.values()),
        "edges": edges,
        "containers": list(containers.values()),
        "callouts": callouts,
    }


def parse_drawio(path):
    """Parse a drawio XML file into a graph spec."""
    tree = ET.parse(path)
    root = tree.getroot()

    nodes = {}
    edges = []
    containers = {}
    parent_map = {}

    for cell in root.iter("mxCell"):
        cid = cell.get("id", "")
        if cid in ("0", "1"):
            continue

        value = cell.get("value", "")
        style = cell.get("style", "")
        parent = cell.get("parent", "1")
        source = cell.get("source")
        target = cell.get("target")

        label = re.sub(r"<[^>]+>", " ", value).strip()
        label_lines = [l.strip() for l in label.split("  ") if l.strip()]

        geom = cell.find("mxGeometry")
        x = y = w = h = 0
        if geom is not None:
            x = float(geom.get("x", 0))
            y = float(geom.get("y", 0))
            w = float(geom.get("width", 0))
            h = float(geom.get("height", 0))

        if source and target:
            is_dashed = "dashed=1" in style
            edges.append({
                "from": source,
                "to": target,
                "label": label,
                "style": "dashed" if is_dashed else "solid",
                "is_back_edge": False,
            })
        elif w > 0:
            is_container = "container=1" in style
            node = {
                "id": cid,
                "label": label_lines[0] if label_lines else cid,
                "details": label_lines[1:],
                "role": _guess_role(cid, label),
            }
            nodes[cid] = node
            parent_map[cid] = parent

            if is_container:
                containers[cid] = {
                    "id": cid,
                    "label": label_lines[0] if label_lines else cid,
                    "children": [],
                }

    # Assign children to containers
    for cid, parent in parent_map.items():
        if parent in containers and cid != parent:
            containers[parent]["children"].append(cid)

    return {
        "nodes": list(nodes.values()),
        "edges": edges,
        "containers": list(containers.values()),
        "callouts": [],
    }


def _set_md_title(node, raw):
    """Set a node's label from a bold title, preserving extra lines.

    A `<br>` (or a title wrapped across source lines) splits into a first-line
    label plus leading detail lines, so multi-line titles aren't truncated.
    """
    parts = [p.strip() for p in re.split(r'<br\s*/?>', raw) if p.strip()]
    if not parts:
        return
    node["label"] = parts[0]
    for extra in reversed(parts[1:]):
        node["details"].insert(0, extra)


# Trailing service nouns that strongly mark a node as an external service.
# Kept conservative — these are rarely the object of an action verb, so a
# suffix match won't mislabel steps like "Clear Cache" or "Drain Queue".
_SERVICE_WORDS = ("server", "database", "registry", "gateway", "datastore")


def _refine_role(node, edges):
    """Assign a role from styling cues + the parsed title (D2 path).

    Styling beats keyword-guessing: a diamond is a decision, a dashed border
    is external/optional, a `/command` title is an entry. The external keyword
    fallback matches only a service NOUN at the end of the name ("MLflow
    Server"), never a substring ("Verify MLflow" is a processing step, not the
    server). Output is only inferred for a sink node (no outgoing edges), so
    writing steps like 'gen-report' or 'log-results' stay processing.
    """
    st = node.get("_style", {})
    nid = node["id"]
    label = (node.get("label") or "").strip()
    combined = f"{nid} {label}".lower()

    # Styling beats the /command heuristic: a dashed `/eval-run` is a
    # downstream-skill reference (external), not the diagram's entry point.
    if st.get("shape") == "diamond" or label.endswith("?"):
        return "decision"
    if st.get("stroke_dash"):
        return "external"
    if label.startswith("/") or nid.startswith("/") or "--" in combined:
        return "entry"
    # Last-resort external: the node IS a service — its name ends in a service
    # noun (suffix, not substring) so "Verify MLflow" doesn't trip it.
    words = re.split(r"[\s/_-]+", combined.strip())
    if words and words[-1] in _SERVICE_WORDS:
        return "external"
    has_outgoing = any(e["from"] == nid for e in edges)
    if not has_outgoing and any(w in label.lower() for w in ["report", "output"]):
        return "output"
    return "processing"


def _extract_callouts(nodes, edges, containers):
    """Pull callout-styled |md nodes out of nodes[] into callouts[].

    A callout uses a monospace font (code/file-tree content) or a light, thin
    border. Its raw multi-line body is preserved as content, it's linked to
    whatever node points at it (attached_to), and the connector edge is
    dropped (the link is represented by attached_to).
    """
    callouts = []
    callout_ids = set()
    for nid, node in list(nodes.items()):
        st = node.get("_style", {})
        light_border = (st.get("stroke", "").lower().startswith("#bb")
                        and str(st.get("stroke_width", "")) in ("1", "1.0"))
        if st.get("font") == "mono" or light_border:
            raw = node.get("_raw", [])
            callouts.append({
                "id": nid,
                "content": "\n".join(raw) if raw else (node.get("label") or nid),
                "attached_to": None,
                "type": "listing",
            })
            callout_ids.add(nid)
            del nodes[nid]

    for c in callouts:
        for e in edges:
            if e["to"] == c["id"] and e["from"] not in callout_ids:
                c["attached_to"] = e["from"]
                break
            if e["from"] == c["id"] and e["to"] not in callout_ids:
                c["attached_to"] = e["to"]
                break

    edges[:] = [e for e in edges
                if e["from"] not in callout_ids and e["to"] not in callout_ids]
    for cont in containers.values():
        cont["children"] = [ch for ch in cont["children"]
                            if ch not in callout_ids]
    return callouts


def _guess_role(node_id, label):
    """Heuristic role assignment (drawio path / fallback).

    External matches only a trailing service noun ("MLflow Server"), never a
    substring, so an action like "Verify MLflow" stays processing.
    """
    combined = f"{node_id} {label}".lower()
    if combined.startswith("/") or "--" in combined:
        return "entry"
    words = re.split(r"[\s/_-]+", combined.strip())
    if words and words[-1] in _SERVICE_WORDS:
        return "external"
    if any(w in combined for w in ["report", "output", "result", "extracted"]):
        return "output"
    if any(w in combined for w in ["check", "validate", "assess", "decision"]):
        return "decision"
    # find/load/read/parse steps are ordinary processing nodes. (Earlier this
    # returned "setup", which is not a valid role — entry/processing/decision/
    # output/external/optional — and forced callers to relabel every spec.)
    return "processing"


def main():
    if len(sys.argv) < 2:
        print("Usage: parse_input.py <input-file>", file=sys.stderr)
        sys.exit(1)

    path = sys.argv[1]

    if path.endswith(".d2"):
        spec = parse_d2(path)
    elif path.endswith(".drawio"):
        spec = parse_drawio(path)
    elif path.endswith((".yaml", ".yml")):
        import yaml
        with open(path) as f:
            spec = yaml.safe_load(f)
    else:
        print(f"Unsupported format: {path}", file=sys.stderr)
        sys.exit(1)

    json.dump(spec, sys.stdout, indent=2)


if __name__ == "__main__":
    main()

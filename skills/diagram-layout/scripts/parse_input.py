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

    lines = content.split("\n")
    current_block = None
    current_block_id = None
    block_depth = 0
    in_edge_block = False
    last_edge_idx = -1

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

        # Edge: a -> b or a -> b: { ... }
        edge_match = re.match(
            r"([\w-]+)\s*->\s*([\w-]+)(?:\s*:\s*(.+))?", stripped
        )
        if edge_match:
            src, tgt, label = edge_match.groups()
            style = "solid"
            if label and "{" in label:
                if "stroke-dash" in label:
                    style = "dashed"
                label = re.sub(r"\s*\{.*", "", label).strip()
            if label:
                label = label.strip('" ')
            edges.append({
                "from": src,
                "to": tgt,
                "label": label or "",
                "style": style,
            })
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

        # Block with markdown content: name: |md
        md_match = re.match(r"([\w-]+)\s*:\s*\|md\s*$", stripped)
        if md_match:
            block_id = md_match.group(1)
            if current_block_id:
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
            continue

        # Markdown content lines (inside |md block)
        if current_block_id and block_depth >= 1:
            if stripped == "|" or stripped == "| {":
                continue
            if stripped == "}":
                block_depth -= 1
                if block_depth <= 0:
                    current_block_id = None
                    block_depth = 0
                continue
            if stripped.startswith("**"):
                title = stripped.strip("*").strip()
                if current_block_id in nodes:
                    nodes[current_block_id]["label"] = title
            elif stripped.startswith("- "):
                bullet = stripped[2:].strip()
                if current_block_id in nodes:
                    nodes[current_block_id]["details"].append(bullet)

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
        "nodes": list(nodes.values()),
        "edges": edges,
        "containers": list(containers.values()),
        "callouts": [],
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


def _guess_role(node_id, label):
    """Heuristic role assignment."""
    combined = f"{node_id} {label}".lower()
    if combined.startswith("/") or "--" in combined:
        return "entry"
    if any(w in combined for w in ["server", "database", "api", "mlflow"]):
        return "external"
    if any(w in combined for w in ["report", "output", "result", "extracted"]):
        return "output"
    if any(w in combined for w in ["check", "validate", "assess", "decision"]):
        return "decision"
    if any(w in combined for w in ["find", "load", "read", "parse", "setup"]):
        return "setup"
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

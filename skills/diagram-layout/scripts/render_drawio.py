#!/usr/bin/env python3
"""Convert a layout plan JSON into drawio XML."""

import json
import re
import sys


def _escape_for_xml_attr(html_label: str) -> str:
    """Escape an HTML label for use in an XML attribute value.

    The label_html contains HTML markup (<b>, <br>, etc.) that drawio
    interprets when rendering. We need to escape this for the XML
    attribute context (value="...") without double-encoding existing
    HTML entities like &lt; which represent literal angle brackets.

    Strategy: escape & first (but not existing entities), then < > "
    """
    # Protect existing entities from double-encoding: &lt; &gt; &amp; &quot;
    # by temporarily replacing them with placeholders
    MARKER = "\x07"  # BEL character, won't appear in label text
    protected = re.sub(r'&(lt|gt|amp|quot|#\d+|#x[0-9a-fA-F]+);',
                       MARKER + r'\1' + MARKER, html_label)
    # Now escape the raw characters for XML attribute
    protected = protected.replace('&', '&amp;')
    protected = protected.replace('<', '&lt;')
    protected = protected.replace('>', '&gt;')
    protected = protected.replace('"', '&quot;')
    # Restore protected entities
    protected = re.sub(MARKER + r'([^' + MARKER + r']+)' + MARKER,
                       r'&\1;', protected)
    return protected


# "0" and "1" are draw.io's own root and default-layer cell ids; a node using
# either collides with them and silently renders an empty diagram. The rest are
# attribute/keyword names that have caused silent export failures.
_RESERVED_IDS = {"0", "1", "filter", "push", "output", "style", "parent", "source", "target", "value", "edge", "vertex"}


def _safe_id(cid, id_map):
    """Rename reserved draw.io cell IDs to avoid silent export failures."""
    if cid in _RESERVED_IDS:
        safe = f"{cid}-node"
        id_map[cid] = safe
        return safe
    return id_map.get(cid, cid)


def render(plan):
    """Generate drawio XML from a layout plan."""
    cells = []
    cell_id = 2
    id_map = {}  # original → safe ID mapping for reserved IDs

    def _emit_box(elem, parent, top_level):
        """Emit a node/container cell and recurse into its children.

        Top-level boxes are positioned with absolute x/y; children use rel_x/
        rel_y relative to their parent (draw.io child geometry is parent-
        relative), so a container nested inside another renders correctly with
        all of its descendants — the loop used to drop a nested container's
        children entirely.
        """
        nonlocal cell_id
        cid = _safe_id(elem.get("id", str(cell_id)), id_map)
        children = elem.get("children", [])
        is_container = elem.get("type") == "container" or bool(children)
        default_style = (_default_container_style() if is_container
                         else _default_node_style())
        gx = elem["x"] if top_level else elem["rel_x"]
        gy = elem["y"] if top_level else elem["rel_y"]
        cells.append(_vertex(
            cid, elem.get("label_html", ""),
            gx, gy, elem["width"], elem["height"],
            elem.get("style", default_style),
            parent=parent,
        ))
        cell_id = max(cell_id, int(cid) + 1) if cid.isdigit() else cell_id + 1
        for child in children:
            _emit_box(child, cid, top_level=False)

    for elem in plan.get("elements", []):
        etype = elem.get("type", "node")

        if etype in ("container", "node"):
            _emit_box(elem, parent="1", top_level=True)

        elif etype == "edge":
            eid = _safe_id(elem.get("id", str(cell_id)), id_map)
            src = id_map.get(elem["from"], elem["from"])
            tgt = id_map.get(elem["to"], elem["to"])
            cells.append(_edge(
                eid, src, tgt,
                elem.get("label", ""),
                elem.get("style", _default_edge_style()),
                elem.get("waypoints"),
                elem.get("exit_point"),
                elem.get("entry_point"),
            ))
            cell_id = max(cell_id, int(eid) + 1) if eid.isdigit() else cell_id + 1

    xml = (
        '<mxGraphModel adaptiveColors="auto">\n'
        '  <root>\n'
        '    <mxCell id="0"/>\n'
        '    <mxCell id="1" parent="0"/>\n'
    )
    for cell in cells:
        xml += cell
    xml += "  </root>\n</mxGraphModel>\n"
    return xml


_ABSOLUTE_ARC_RADIUS = 16  # absolute arcSize → ~8px corner radius


def _normalize_arcsize(style):
    """Force absolute corner radius so large boxes don't get large corners.

    draw.io interprets arcSize as a percentage of the box's smaller side
    unless absoluteArcSize=1 is set. A 520px-wide container then gets a
    much larger corner radius than a small node. Normalizing to an
    absolute pixel radius keeps corners consistent across all box sizes.
    """
    if "rounded=1" not in style:
        return style
    # Strip any existing arc settings
    parts = [p for p in style.split(";")
             if p and not p.startswith("arcSize=")
             and not p.startswith("absoluteArcSize=")]
    parts.append(f"arcSize={_ABSOLUTE_ARC_RADIUS}")
    parts.append("absoluteArcSize=1")
    return ";".join(parts) + ";"


def _vertex(cid, label, x, y, w, h, style, parent="1"):
    label_escaped = _escape_for_xml_attr(label)
    style = _normalize_arcsize(style)
    geom = (
        f'      <mxGeometry x="{x}" y="{y}" '
        f'width="{w}" height="{h}" as="geometry"/>\n'
    )
    return (
        f'    <mxCell id="{cid}" value="{label_escaped}" '
        f'style="{style}" vertex="1" parent="{parent}">\n'
        f'{geom}'
        f'    </mxCell>\n'
    )


def _edge(eid, source, target, label, style, waypoints=None,
          exit_point=None, entry_point=None):
    label_escaped = _escape_for_xml_attr(label) if label else ""


    # Add exit/entry points to style
    full_style = style
    if exit_point:
        full_style += (
            f"exitX={exit_point['x']};exitY={exit_point['y']};"
            f"exitDx=0;exitDy=0;"
        )
    if entry_point:
        full_style += (
            f"entryX={entry_point['x']};entryY={entry_point['y']};"
            f"entryDx=0;entryDy=0;"
        )

    value_attr = f' value="{label_escaped}"' if label_escaped else ""

    geom = '      <mxGeometry relative="1" as="geometry">\n'
    if waypoints:
        geom += '        <Array as="points">\n'
        for wp in waypoints:
            geom += f'          <mxPoint x="{wp["x"]}" y="{wp["y"]}"/>\n'
        geom += "        </Array>\n"
    geom += "      </mxGeometry>\n"

    return (
        f'    <mxCell id="{eid}"{value_attr} '
        f'style="{full_style}" edge="1" '
        f'source="{source}" target="{target}" parent="1">\n'
        f'{geom}'
        f'    </mxCell>\n'
    )


def _default_node_style():
    return (
        "rounded=1;whiteSpace=wrap;html=1;fillColor=#f5f5f5;"
        "strokeColor=#333333;strokeWidth=2;arcSize=10;"
        "verticalAlign=top;spacingTop=5;fontSize=11;"
        "fontFamily=JetBrains Mono;"
    )


def _default_container_style():
    return (
        "rounded=1;whiteSpace=wrap;html=1;fillColor=#ececec;"
        "strokeColor=#333333;strokeWidth=2;container=1;collapsible=0;"
        "verticalAlign=top;spacingTop=5;fontSize=12;fontStyle=1;"
        "fontFamily=JetBrains Mono;"
    )


def _default_edge_style():
    return (
        "edgeStyle=orthogonalEdgeStyle;rounded=1;"
        "strokeColor=#333333;strokeWidth=1.5;html=1;"
        "fontFamily=JetBrains Mono;"
    )


def main():
    if len(sys.argv) < 3:
        print("Usage: render_drawio.py <layout-plan.json> <output.drawio>",
              file=sys.stderr)
        sys.exit(1)

    with open(sys.argv[1]) as f:
        plan = json.load(f)

    # Refuse to write an empty diagram. Without this, a plan with an empty (or
    # wrong-schema) "elements" array produced a .drawio containing only the two
    # root cells — a silent failure that looked like success.
    node_like = [e for e in plan.get("elements", [])
                 if e.get("type", "node") in ("node", "container")]
    if not node_like:
        print(
            "ERROR: layout plan has no node/container elements — refusing to "
            "write an empty diagram. Check that the plan uses a single "
            "'elements' array (type-tagged node/container/edge), not "
            "top-level 'nodes'/'edges'.",
            file=sys.stderr,
        )
        sys.exit(1)

    xml = render(plan)

    with open(sys.argv[2], "w") as f:
        f.write(xml)

    print(f"Wrote {sys.argv[2]}", file=sys.stderr)


if __name__ == "__main__":
    main()

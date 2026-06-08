"""render_drawio: nested-container emission, reserved-ID remapping, and edge
keyword-style normalization — each a defect fixed during the session.
"""
import re

import render_drawio as R


# --- Nested containers: grandchildren must not be dropped -----------------

def test_nested_container_emits_all_descendants():
    plan = {"elements": [{
        "type": "container", "id": "outer", "x": 0, "y": 0,
        "width": 400, "height": 400, "label_html": "<b>Outer</b>",
        "children": [{
            "type": "container", "id": "inner", "rel_x": 20, "rel_y": 40,
            "width": 320, "height": 320, "label_html": "<b>Inner</b>",
            "children": [{
                "type": "node", "id": "run-sync", "rel_x": 20, "rel_y": 40,
                "width": 200, "height": 100, "label_html": "<b>Run Sync</b>",
            }],
        }],
    }]}
    xml = R.render(plan)
    # All three nesting levels present (grandchild used to vanish).
    assert 'id="outer"' in xml
    assert 'id="inner"' in xml
    assert 'id="run-sync"' in xml
    # Parent wiring is correct: run-sync nested under inner, inner under outer.
    assert re.search(r'id="run-sync"[^>]*parent="inner"', xml)
    assert re.search(r'id="inner"[^>]*parent="outer"', xml)


# --- Reserved draw.io IDs get remapped (avoid silent export failure) ------

def test_reserved_id_is_remapped_and_edges_follow():
    plan = {"elements": [
        {"type": "node", "id": "a", "x": 0, "y": 0,
         "width": 100, "height": 80, "label_html": "A"},
        {"type": "node", "id": "find", "x": 200, "y": 0,
         "width": 100, "height": 80, "label_html": "Find"},
        {"type": "edge", "from": "a", "to": "find"},
    ]}
    xml = R.render(plan)
    assert 'id="find-node"' in xml          # remapped vertex
    assert not re.search(r'id="find"', xml)  # no bare reserved id
    assert 'target="find-node"' in xml       # edge endpoint remapped too


def test_reserved_ids_set_includes_known_offenders():
    for rid in ("find", "push", "filter", "0", "1"):
        assert rid in R._RESERVED_IDS


# --- Edge keyword-style normalization (eval-dataset straight arrows) ------

def test_keyword_styles_normalize_to_orthogonal():
    fwd = R._normalize_edge_style("forward")
    assert "edgeStyle=orthogonalEdgeStyle" in fwd
    assert "dashed=1" not in fwd

    for kw in ("back", "conditional", "dashed", "optional", "loop"):
        s = R._normalize_edge_style(kw)
        assert "edgeStyle=orthogonalEdgeStyle" in s, kw
        assert "dashed=1" in s, kw

    callout = R._normalize_edge_style("callout")
    assert "strokeColor=#bbbbbb" in callout


def test_empty_style_falls_back_to_orthogonal_default():
    s = R._normalize_edge_style("")
    assert "edgeStyle=orthogonalEdgeStyle" in s


def test_real_style_passes_through_unchanged():
    real = ("edgeStyle=orthogonalEdgeStyle;rounded=1;strokeColor=#333333;"
            "exitX=1;exitY=0.5;")
    assert R._normalize_edge_style(real) == real


def test_non_orthogonal_real_style_is_not_rewritten():
    # render won't silently "fix" a real but wrong edgeStyle — the validator
    # is responsible for flagging it. render must pass it through verbatim.
    bad = "edgeStyle=elbowEdgeStyle;rounded=0;"
    assert R._normalize_edge_style(bad) == bad


# --- Default fonts: Inter, not JetBrains Mono -----------------------------

def test_default_styles_use_inter_font():
    for style in (R._default_node_style(), R._default_container_style(),
                  R._default_edge_style()):
        assert "fontFamily=Inter" in style
        assert "JetBrains" not in style


# --- Absolute arc radius (large boxes shouldn't get huge corners) ---------

def test_arcsize_is_normalized_to_absolute():
    out = R._normalize_arcsize("rounded=1;arcSize=50;fillColor=#fff;")
    assert "absoluteArcSize=1" in out
    assert f"arcSize={R._ABSOLUTE_ARC_RADIUS}" in out
    assert "arcSize=50" not in out


def test_arcsize_untouched_without_rounding():
    style = "fillColor=#fff;strokeColor=#333;"
    assert R._normalize_arcsize(style) == style


# --- XML attribute escaping without double-encoding -----------------------

def test_escape_raw_markup():
    assert R._escape_for_xml_attr("<b>Hi</b>") == "&lt;b&gt;Hi&lt;/b&gt;"


def test_escape_preserves_existing_entities():
    # An already-escaped entity must not become &amp;lt;.
    assert R._escape_for_xml_attr("a &lt; b") == "a &lt; b"


def test_escape_handles_raw_amp_and_quote():
    assert R._escape_for_xml_attr('x & "y"') == 'x &amp; &quot;y&quot;'

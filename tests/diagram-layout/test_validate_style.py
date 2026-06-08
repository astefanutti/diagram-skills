"""Style / label / role-consistency checks (added after a full re-author run
shipped 'validation clean' yet rendered LLM nodes two different ways across
sibling diagrams, plus older silent failures: empty styles -> plain boxes and
`label` instead of `label_html` -> empty cells). These are gated on the graph
spec being supplied (it carries per-node `role`; the pipeline always writes it
next to the plan), so the no-spec geometry fixtures are unaffected.
"""
from conftest import node, plan
from validate_layout import validate

# Canonical-ish style fragments (only the marker bits matter to the checks).
LLM_DOUBLE = ("rounded=1;whiteSpace=wrap;html=1;fillColor=#e8e8e8;"
              "strokeColor=#333333;strokeWidth=3;double=1;")
LLM_NO_DOUBLE = ("rounded=1;whiteSpace=wrap;html=1;fillColor=#e8e8e8;"
                 "strokeColor=#333333;strokeWidth=3;")
DECISION_RHOMBUS = "rhombus;whiteSpace=wrap;html=1;fillColor=#f5f5f5;"
DECISION_FLAT = "rounded=1;whiteSpace=wrap;html=1;fillColor=#f5f5f5;"
EXTERNAL_DASHED = ("rounded=1;html=1;fillColor=#e8e8e8;strokeWidth=2;"
                   "dashed=1;dashPattern=8 4;")
PLAIN = "rounded=1;whiteSpace=wrap;html=1;fillColor=#f5f5f5;strokeWidth=2;"


def _has(result, needle, where="errors"):
    return any(needle in m for m in result[where])


def _spec(*nodes):
    """A graph spec carrying per-node roles."""
    return {"nodes": list(nodes), "edges": []}


# --- Intrinsic checks (label / style) -------------------------------------

def test_empty_style_box_is_flagged():
    p = plan(node("a", 0, 0, 200, 80, style="", label_html="<b>A</b>"))
    assert _has(validate(p, _spec({"id": "a", "role": "processing"})),
                "Empty style")


def test_label_instead_of_label_html_is_flagged():
    # 'label' is the EDGE key; a box that only sets it renders value="".
    p = plan(node("a", 0, 0, 200, 80, style=PLAIN, label="A"))
    res = validate(p, _spec({"id": "a", "role": "processing"}))
    assert _has(res, "Wrong label key")


def test_missing_label_is_flagged():
    p = plan(node("a", 0, 0, 200, 80, style=PLAIN))
    assert _has(validate(p, _spec({"id": "a", "role": "processing"})),
                "Missing label")


def test_well_formed_box_passes_clean():
    p = plan(node("a", 0, 0, 200, 80, style=PLAIN, label_html="<b>A</b>"))
    res = validate(p, _spec({"id": "a", "role": "processing"}))
    assert not _has(res, "Empty style")
    assert not _has(res, "label")


# --- Role / style consistency ---------------------------------------------

def test_llm_role_missing_double_border_warns():
    p = plan(node("x", 0, 0, 200, 80, style=LLM_NO_DOUBLE, label_html="<b>X</b>"))
    res = validate(p, _spec({"id": "x", "role": "llm"}))
    assert _has(res, "Role/style mismatch", "warnings")
    assert _has(res, "double=1", "warnings")


def test_llm_role_with_double_border_is_clean():
    p = plan(node("x", 0, 0, 200, 80, style=LLM_DOUBLE, label_html="<b>X</b>"))
    res = validate(p, _spec({"id": "x", "role": "llm"}))
    assert not _has(res, "Role/style mismatch", "warnings")


def test_decision_role_missing_rhombus_errors():
    p = plan(node("d", 0, 0, 200, 80, style=DECISION_FLAT, label_html="<b>D?</b>"))
    res = validate(p, _spec({"id": "d", "role": "decision"}))
    assert _has(res, "Role/style mismatch")  # error, not just warning


def test_decision_role_with_rhombus_is_clean():
    p = plan(node("d", 0, 0, 200, 80, style=DECISION_RHOMBUS,
                  label_html="<b>D?</b>"))
    res = validate(p, _spec({"id": "d", "role": "decision"}))
    assert not _has(res, "Role/style mismatch")


def test_external_role_missing_dashed_warns():
    p = plan(node("e", 0, 0, 200, 80, style=PLAIN, label_html="<b>E</b>"))
    res = validate(p, _spec({"id": "e", "role": "external"}))
    assert _has(res, "Role/style mismatch", "warnings")


def test_role_check_recurses_into_container_children():
    # The exact gap that bit a real run: an LLM node nested in a container
    # (no `type` key on the child) was missed by a type-guarded walk.
    container = {
        "type": "container", "id": "scoring", "x": 0, "y": 0,
        "width": 400, "height": 300, "style": "container=1;",
        "label_html": "<b>Score</b>",
        "children": [
            {"id": "judge-llm", "rel_x": 20, "rel_y": 40,
             "width": 200, "height": 100, "style": LLM_NO_DOUBLE,
             "label_html": "<b>LLM Judge</b>"},
        ],
    }
    res = validate(plan(container),
                   _spec({"id": "scoring", "role": "container"},
                         {"id": "judge-llm", "role": "llm"}))
    assert _has(res, "judge-llm", "warnings")
    assert _has(res, "Role/style mismatch", "warnings")


# --- Container marker ------------------------------------------------------

def test_container_missing_container_flag_warns():
    cont = {"type": "container", "id": "grp", "x": 0, "y": 0,
            "width": 300, "height": 200, "style": "rounded=1;fillColor=#ececec;",
            "label_html": "<b>G</b>",
            "children": [{"id": "c1", "rel_x": 20, "rel_y": 40,
                          "width": 200, "height": 80, "style": PLAIN,
                          "label_html": "<b>C1</b>"}]}
    res = validate(plan(cont), _spec({"id": "grp", "role": "container"},
                                     {"id": "c1", "role": "processing"}))
    assert _has(res, "container=1", "warnings")


# --- Gating: no spec => intrinsic checks stay quiet (geometry fixtures) ----

def test_style_label_checks_skipped_without_spec():
    # Bare box (no style, no label_html) — exactly what the geometry fixtures
    # build. Without a spec these must NOT raise style/label errors, or the
    # existing no-spec suite would break.
    p = plan(node("a", 0, 0, 100, 80))
    res = validate(p)            # no spec
    assert not _has(res, "Empty style")
    assert not _has(res, "Missing label")
    assert not _has(res, "Role/style mismatch", "warnings")

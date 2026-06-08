"""export_diagram: precise failure reporting helpers.

These cover the pure logic — CLI resolution, SVG shape detection, and SVG
post-processing — without invoking the draw.io desktop app (the actual export
needs the GUI binary and isn't unit-testable here).
"""
import os

import pytest

import export_diagram as E


# --- CLI resolution: missing binary vs. real one --------------------------

def test_resolve_cli_missing_path_returns_none():
    assert E.resolve_cli("/no/such/place/draw.io-xyz") is None


def test_resolve_cli_missing_name_returns_none():
    assert E.resolve_cli("drawio-definitely-not-installed-xyz") is None


@pytest.mark.skipif(not os.access("/bin/sh", os.X_OK),
                    reason="/bin/sh not present")
def test_resolve_cli_existing_path_is_returned():
    assert E.resolve_cli("/bin/sh") == "/bin/sh"


def test_resolve_cli_finds_command_on_path():
    # `sh` is on PATH everywhere we run; resolve to an absolute path.
    resolved = E.resolve_cli("sh")
    assert resolved and os.path.isabs(resolved)


def test_candidate_cli_is_nonempty():
    assert isinstance(E.candidate_cli(), str) and E.candidate_cli()


# --- SVG shape detection (the silent-failure backstop) --------------------

def test_svg_with_path_has_shapes():
    assert E.svg_has_shapes('<svg><g><path d="M0 0 L1 1"/></g></svg>')


def test_svg_with_rect_has_shapes():
    assert E.svg_has_shapes('<svg><rect x="0" y="0" width="10" height="10"/></svg>')


def test_empty_svg_has_no_shapes():
    assert not E.svg_has_shapes('<svg xmlns="http://www.w3.org/2000/svg"></svg>')


def test_blank_svg_has_no_shapes():
    assert not E.svg_has_shapes("<svg>   \n  </svg>")


# --- SVG post-processing --------------------------------------------------

def test_postprocess_strips_light_dark():
    out = E.postprocess_svg("stroke:light-dark(#333333, #cccccc);")
    assert out == "stroke:#333333;"
    assert "light-dark" not in out


def test_postprocess_encodes_non_ascii():
    # '→' is U+2192 (8594); it must become a numeric XML entity.
    out = E.postprocess_svg("a→b")
    assert out == "a&#8594;b"


def test_postprocess_leaves_ascii_untouched():
    s = '<svg><path d="M0 0"/></svg>'
    assert E.postprocess_svg(s) == s

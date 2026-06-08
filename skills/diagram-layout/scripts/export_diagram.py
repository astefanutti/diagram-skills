#!/usr/bin/env python3
"""Export a drawio file to PNG/SVG/PDF via the draw.io CLI.

Failure reporting is deliberately precise: a genuinely missing CLI, a draw.io
non-zero exit, and an "exited 0 but produced nothing" silent failure are three
different problems with three different fixes, and conflating them (the old
version reported every launch problem as "CLI not found") sent debugging down
the wrong path.
"""

import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path


def candidate_cli():
    """The platform's expected draw.io CLI path/name (not yet verified)."""
    if platform.system() == "Darwin":
        return "/Applications/draw.io.app/Contents/MacOS/draw.io"
    elif platform.system() == "Linux":
        return "drawio"
    else:
        return "draw.io"


def resolve_cli(candidate):
    """Return a runnable path for `candidate`, or None if it isn't installed.

    Probing up front is what lets us tell a genuinely missing binary apart from
    an export that failed for another reason. draw.io can fail a render in a way
    that surfaces as a launch-time error, and the old code's bare
    `except FileNotFoundError -> "CLI not found"` then lied about the cause.
    """
    # A path (has a separator): check it directly for executability.
    if os.sep in candidate or (os.altsep and os.altsep in candidate):
        return candidate if os.access(candidate, os.X_OK) else None
    # A bare command name: search PATH.
    return shutil.which(candidate)


# Any one of these means draw.io actually rendered something. A silent failure
# (or an empty diagram) emits a well-formed but shape-less SVG wrapper; real
# diagrams always carry paths/rects (node borders, edges). Note: HTML labels
# export as <image>, and <text> is rare, so we must not depend on <text>.
_SVG_SHAPE_RE = re.compile(
    r"<(path|rect|ellipse|circle|polygon|polyline|image|text)\b"
)


def svg_has_shapes(content):
    """True if an SVG contains at least one drawn element."""
    return bool(_SVG_SHAPE_RE.search(content))


def postprocess_svg(content):
    """Make a draw.io SVG safe for <img> embedding and editor round-trips."""
    # Strip light-dark() CSS — Safari doesn't support it in <img> SVGs, so we
    # keep the light value and invert via CSS for dark mode.
    content = re.sub(r'light-dark\(([^,)]+),\s*[^)]+\)', r'\1', content)
    # Replace non-ASCII with numeric XML entities so SVGs survive draw.io web
    # editor round-trips (raw Unicode otherwise gets double-encoded).
    content = re.sub(r'[^\x00-\x7F]', lambda m: f'&#{ord(m.group(0))};', content)
    return content


def main():
    if len(sys.argv) < 3:
        print("Usage: export_diagram.py <input.drawio> <output.(svg|png|pdf)>",
              file=sys.stderr)
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]

    fmt = "png"
    if output_path.endswith(".svg"):
        fmt = "svg"
    elif output_path.endswith(".pdf"):
        fmt = "pdf"

    candidate = candidate_cli()
    cli = resolve_cli(candidate)
    if not cli:
        print(
            f"draw.io CLI not found (looked for '{candidate}'). Install the "
            f"draw.io desktop app to enable export.",
            file=sys.stderr,
        )
        sys.exit(1)

    cmd = [cli, "-x", "-f", fmt, "-b", "10"]
    if fmt == "svg":
        cmd.append("--embed-diagram")
    cmd.extend(["-o", output_path, input_path])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
    except OSError as e:
        # The binary resolved above, so this is a launch/export failure, NOT a
        # missing CLI. Report the real error instead of the install hint.
        print(f"Export failed to launch draw.io ({cli}): {e}", file=sys.stderr)
        sys.exit(1)

    if result.returncode != 0:
        detail = (result.stderr or "").strip() or (result.stdout or "").strip()
        print(f"Export failed (draw.io exit {result.returncode}): {detail}",
              file=sys.stderr)
        sys.exit(1)

    # Success exit code is not proof of a real diagram: draw.io can exit 0 yet
    # write nothing (or an empty shape-less SVG) on some failures — e.g. a
    # reserved cell id. Verify the artifact before declaring victory.
    out = Path(output_path)
    if not out.exists() or out.stat().st_size == 0:
        print(
            f"Export reported success but produced no output at {output_path} "
            f"— draw.io exited 0 without writing a file. Check the .drawio for "
            f"reserved cell IDs (filter/find/push/output) or invalid XML.",
            file=sys.stderr,
        )
        sys.exit(1)

    if fmt == "svg":
        content = out.read_text(encoding="utf-8")
        if not svg_has_shapes(content):
            print(
                f"Export produced a shape-less SVG at {output_path} — a silent "
                f"draw.io failure (often a reserved cell id like find/filter/"
                f"push/output, or an empty diagram). Not writing it as success.",
                file=sys.stderr,
            )
            sys.exit(1)
        out.write_text(postprocess_svg(content), encoding="utf-8")

    print(f"Exported {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()

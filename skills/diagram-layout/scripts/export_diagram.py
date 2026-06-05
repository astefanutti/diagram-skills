#!/usr/bin/env python3
"""Export a drawio file to PNG/SVG/PDF via draw.io CLI."""

import platform
import re
import subprocess
import sys
from pathlib import Path


def get_drawio_cli():
    if platform.system() == "Darwin":
        return "/Applications/draw.io.app/Contents/MacOS/draw.io"
    elif platform.system() == "Linux":
        return "drawio"
    else:
        return "draw.io"


def main():
    if len(sys.argv) < 3:
        print("Usage: export_png.py <input.drawio> <output.png>",
              file=sys.stderr)
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]

    fmt = "png"
    if output_path.endswith(".svg"):
        fmt = "svg"
    elif output_path.endswith(".pdf"):
        fmt = "pdf"

    cli = get_drawio_cli()

    cmd = [cli, "-x", "-f", fmt, "-b", "10"]
    if fmt == "svg":
        cmd.append("--embed-diagram")
    cmd.extend(["-o", output_path, input_path])

    try:
        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
        )
        if fmt == "svg":
            p = Path(output_path)
            content = p.read_text(encoding="utf-8")
            # Strip light-dark() CSS function — keep only the light value.
            # Safari doesn't support light-dark() in <img> SVGs, so we use
            # fixed light colors and apply a CSS invert filter for dark mode.
            content = re.sub(
                r'light-dark\(([^,)]+),\s*[^)]+\)',
                r'\1',
                content,
            )
            # Replace non-ASCII with numeric XML entities so SVGs survive
            # draw.io web editor round-trips (raw Unicode gets double-encoded).
            content = re.sub(r'[^\x00-\x7F]', lambda m: f'&#{ord(m.group(0))};', content)
            p.write_text(content, encoding="utf-8")
        print(f"Exported {output_path}", file=sys.stderr)
    except FileNotFoundError:
        print(f"draw.io CLI not found at {cli}. "
              "Install draw.io desktop app to enable export.",
              file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"Export failed: {e.stderr}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Export a drawio file to PNG/SVG/PDF via draw.io CLI."""

import platform
import subprocess
import sys


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

    try:
        subprocess.run(
            [cli, "-x", "-f", fmt, "-e", "-b", "10",
             "-o", output_path, input_path],
            check=True,
            capture_output=True,
            text=True,
        )
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

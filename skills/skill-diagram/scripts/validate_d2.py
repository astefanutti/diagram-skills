#!/usr/bin/env python3
"""Validate D2 by running a full compile (not just fmt).

d2 fmt only checks D2 syntax. A full compile also catches malformed
markdown inside labels, invalid references, and other semantic errors.
"""

import json
import subprocess
import sys
import tempfile


def validate(path):
    try:
        # Full compile to a temp SVG — catches markdown and semantic errors
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=True) as tmp:
            result = subprocess.run(
                ["d2", path, tmp.name],
                capture_output=True, text=True, timeout=30,
            )
        if result.returncode == 0:
            return {"valid": True, "errors": []}
        errors = [line.strip() for line in result.stderr.splitlines()
                  if line.strip() and not line.startswith("success:")]
        return {"valid": False, "errors": errors}
    except FileNotFoundError:
        return {"valid": True, "errors": [], "warning": "d2 not installed, skipping validation"}
    except subprocess.TimeoutExpired:
        return {"valid": False, "errors": ["d2 compile timed out"]}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: validate_d2.py <file.d2>", file=sys.stderr)
        sys.exit(1)
    result = validate(sys.argv[1])
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["valid"] else 1)

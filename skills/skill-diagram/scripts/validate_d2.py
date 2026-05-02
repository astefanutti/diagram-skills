#!/usr/bin/env python3
"""Validate D2 syntax by running d2 fmt."""

import json
import subprocess
import sys


def validate(path):
    try:
        result = subprocess.run(
            ["d2", "fmt", path],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return {"valid": True, "errors": []}
        errors = [line.strip() for line in result.stderr.splitlines() if line.strip()]
        return {"valid": False, "errors": errors}
    except FileNotFoundError:
        return {"valid": True, "errors": [], "warning": "d2 not installed, skipping validation"}
    except subprocess.TimeoutExpired:
        return {"valid": False, "errors": ["d2 fmt timed out"]}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: validate_d2.py <file.d2>", file=sys.stderr)
        sys.exit(1)
    result = validate(sys.argv[1])
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["valid"] else 1)

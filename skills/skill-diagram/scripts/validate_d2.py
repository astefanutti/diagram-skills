#!/usr/bin/env python3
"""Validate D2 by running a full compile (not just fmt).

d2 fmt only checks D2 syntax. A full compile also catches malformed
markdown inside labels, invalid references, and other semantic errors.
"""

import json
import re
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


def lint_detail(path):
    """Advisory detail checks — warnings only, never fail the build.

    Flags the common ways an auto-generated diagram comes out under-detailed:
    no callout boxes, no data-flow edge labels, or too few nodes. See
    prompts/analysis-guide.md (6b callouts, 8 data-flow, Deciding Granularity).
    """
    try:
        text = open(path, encoding="utf-8").read()
    except OSError:
        return []
    warns = []
    boxes = len(re.findall(r":\s*\|md\b", text))          # md-label boxes (nodes + children + callouts)
    callouts = len(re.findall(r"style\.font:\s*mono\b", text))  # callout boxes use a monospace font
    edges = len(re.findall(r"->", text))
    edge_labels = re.findall(r"->[^:\n{]+:\s*\"?([^\"\n{]+)", text)
    dataflow = [l for l in edge_labels
                if re.search(r"\.(ya?ml|json|html?|md|log|txt|csv|png|svg|toml|ndjson)\b", l)]
    nodes = boxes - callouts                                # rough node count, excluding callouts
    if callouts == 0:
        warns.append("no callout detail boxes (monospace) — add >=1 for the primary output "
                     "artifact's structure (schema / file-tree / config snippet); read the "
                     "actual script for real content (analysis-guide.md 6b)")
    if edges >= 8 and not dataflow:
        warns.append(f"{edges} edges but no data-flow label names an artifact (e.g. summary.yaml) "
                     "— label the handoffs (analysis-guide.md 8)")
    if 0 < nodes < 8:
        warns.append(f"only ~{nodes} step boxes — rich skills usually warrant 10-16; split "
                     "merged steps or use containers (analysis-guide.md 'Deciding Granularity')")
    return warns


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: validate_d2.py <file.d2>", file=sys.stderr)
        sys.exit(1)
    result = validate(sys.argv[1])
    result["detail_warnings"] = lint_detail(sys.argv[1])
    print(json.dumps(result, indent=2))
    # Exit reflects compile validity only; detail_warnings are advisory.
    sys.exit(0 if result["valid"] else 1)

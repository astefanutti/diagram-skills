---
name: diagram-layout
description: Generate presentation-quality flow diagrams with manual-grade layout. Use when the user wants a diagram with clean edge routing, semantic column placement, vertical stacking of alternatives, back-edge exterior routing, and container grouping. Also use to improve the layout of an existing D2 or drawio diagram. Triggers on "layout diagram", "improve diagram layout", "presentation-quality diagram", or requests to create architecture/flow diagrams that mention layout quality.
user-invocable: true
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
---

# Diagram Layout Skill

Generate presentation-quality flow diagrams that match the quality of hand-crafted manual layouts. Uses LLM-driven coordinate assignment with visual iteration to produce drawio files with clean edge routing, semantic grouping, and proper back-edge handling.

## Arguments

- `--input <path>` — D2 file, drawio file, or YAML graph spec. Omit for natural language description.
- `--output <path>` — Output .drawio path (default: derived from input name or `diagram.drawio`)
- `--format <png|svg|pdf>` — Optional export format (requires draw.io desktop app)
- `--iterate <N>` — Max visual iteration rounds (default: 3)

## Workflow

### Step 1: Parse Input

If `--input` is provided, run the parser to extract the graph specification:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/parse_input.py <input-path>
```

This outputs a normalized JSON graph spec to stdout. Save it to `artifacts/graph-spec.json`:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/parse_input.py <input-path> > artifacts/graph-spec.json
```

If no input file, construct the graph spec directly from the user's natural language description and write it to `artifacts/graph-spec.json`. The spec format is:

```json
{
  "nodes": [
    {"id": "n1", "label": "Title", "details": ["bullet 1", "bullet 2"], "role": "entry"}
  ],
  "edges": [
    {"from": "n1", "to": "n2", "label": "", "style": "solid"}
  ],
  "containers": [
    {"id": "c1", "label": "Container Title", "subtitle": "optional note", "children": ["n3", "n4"]}
  ],
  "callouts": [
    {"id": "x1", "content": "detail text", "attached_to": "n2", "type": "listing"}
  ]
}
```

Node roles: `entry`, `processing`, `decision`, `output`, `external`, `optional`.

### Step 2: Analyze Topology

Run the graph analysis script on the saved graph spec:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/graph_analysis.py artifacts/graph-spec.json > artifacts/graph-spec.json.tmp && mv artifacts/graph-spec.json.tmp artifacts/graph-spec.json
```

This uses networkx to compute topological layers, fan-out/fan-in points, back-edges, and classify the topology as `pipeline`, `diamond`, `hub-spoke`, or `complex`. It enriches the graph spec with topology annotations in place.

### Step 3: Generate Layout Plan (two passes)

Read the layout rules and coordinate system:
- `${CLAUDE_SKILL_DIR}/prompts/layout-rules.md` — the layout patterns
- `${CLAUDE_SKILL_DIR}/prompts/coordinate-system.md` — sizing tables and spacing

Split the layout into two passes to keep each thinking step focused and fast.

#### Step 3a: Place nodes and containers

Generate the layout plan with **only nodes, containers, and canvas** — no edges yet. For each node: assign x, y, width, height based on semantic column, variable sizing, and multi-row wrapping. Use the text width estimation formulas in coordinate-system.md to size each node based on its actual label content — don't guess sizes from the sizing table alone. For containers: size and position around their children.

Apply these patterns:
1. Assign nodes to semantic columns based on role
2. Stack fan-out alternatives vertically (orthogonal to the flow direction)
3. Check aspect ratio against the topology target (Rule 6a). If too elongated, first maximize fan-out stacking and container grouping — these are the primary mechanisms. Only use row wrapping as a fallback for the widest pipeline segment.
4. Size and position containers around their children (children must fit with 10px padding)
5. Position callout boxes in whitespace areas
6. Set canvas dimensions to fit the layout

Write the node-only layout plan to `artifacts/layout-plan.json`. The `elements` array should contain all nodes, containers, and callouts — but edges are omitted for now.

#### Step 3b: Route edges

Read `artifacts/layout-plan.json` back. Now add all edges with explicit waypoints, exit/entry points, labels, and styles. For each edge:
1. Choose exit/entry sides that face the target (Rule 9a — minimize bends)
2. Route back-edges around the exterior (Rule 3)
3. Compute waypoints for edges that need non-trivial routing
4. Add labels at midpoints without overlapping node bounding boxes (Rule 7)
5. Verify zero edge crossings (Rule 10)

Append the edge elements to the layout plan and write the complete `artifacts/layout-plan.json`.

The layout plan JSON format for both passes:

```json
{
  "canvas": {"width": 1400, "height": 800},
  "elements": [
    {
      "id": "n1", "type": "node",
      "x": 50, "y": 200, "width": 130, "height": 120,
      "label_html": "<b>/eval-mlflow</b><br><br>--run-id<br>--action<br>--config",
      "style": "rounded=1;whiteSpace=wrap;html=1;fillColor=#f5f5f5;strokeColor=#333333;strokeWidth=2;verticalAlign=top;spacingTop=5;"
    },
    {
      "id": "c1", "type": "container",
      "x": 300, "y": 50, "width": 600, "height": 200,
      "label_html": "<b>log-results</b>",
      "style": "rounded=1;whiteSpace=wrap;html=1;fillColor=#ececec;strokeColor=#333333;strokeWidth=2;container=1;collapsible=0;",
      "children": [
        {"id": "c1_1", "rel_x": 20, "rel_y": 40, "width": 100, "height": 80, "label_html": "Params<br>...", "style": "..."}
      ]
    },
    {
      "id": "e1", "type": "edge",
      "from": "n1", "to": "c1",
      "label": "",
      "style": "edgeStyle=orthogonalEdgeStyle;rounded=1;strokeColor=#333;strokeWidth=1.5;html=1;",
      "waypoints": []
    },
    {
      "id": "e_back", "type": "edge",
      "from": "mlflow", "to": "pull",
      "label": "",
      "style": "edgeStyle=orthogonalEdgeStyle;rounded=1;strokeColor=#333;strokeWidth=1.5;dashed=1;dashPattern=8 4;html=1;",
      "waypoints": [{"x": 900, "y": 700}, {"x": 200, "y": 700}],
      "exit_point": {"x": 0.5, "y": 1},
      "entry_point": {"x": 0.5, "y": 1}
    }
  ]
}
```

### Step 4: Programmatic Validation Loop

**Before rendering**, iterate on the layout JSON until the validator passes clean. This catches all structural defects (crossings, S-bends, near-misses) without the cost of rendering and visual inspection.

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/validate_layout.py artifacts/layout-plan.json
```

The validator checks: node overlaps, edge-through-node (errors), edge-edge crossings, near-miss clearance (15px minimum), avoidable bends, and canvas bounds.

**All edges MUST use orthogonal routing** — every segment is either perfectly horizontal or perfectly vertical. A tangent (diagonal) segment connecting to a node is a critical defect. If an edge arrives at a node at an angle, fix the exit/entry anchor points so the connection is orthogonal. This is enforced by `edgeStyle=orthogonalEdgeStyle` in the drawio style, but the layout plan coordinates must also be consistent — waypoints must share an x or y coordinate with adjacent waypoints.

**If errors or warnings**: read the validator output, apply the corresponding fix from layout-rules.md, update the layout JSON, and re-run the validator. Repeat until clean.

Fix rules by priority:
1. **Edge through node** (error) → reroute waypoints to the far exterior, enter target from the side. See Rule 9
2. **Edge crossing** (warning) → separate corridors, apply nested fan-out ordering, swap exit anchors. See Rules 9a, 10
3. **Near-miss** (warning) → nudge the nearby node away (prefer moving nodes over edges). See Rule 12. Re-check connected edges for new S-bends (Rule 11 cascading)
4. **Avoidable bend** (warning) → change exit/entry side to face the target. See Rule 9a
5. **Canvas overflow** → expand canvas or compress column spacing

**Do NOT render to drawio/PNG until the validator reports zero errors and zero warnings.** The validator is fast (milliseconds); rendering + visual inspection is slow (seconds + sub-agent). Use the validator as the tight inner loop.

### Step 5: Render

Once the validator passes clean, convert to drawio XML:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/render_drawio.py <layout-plan.json> <output.drawio>
```

If `--format` was specified, export to the requested format:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/export_png.py <output.drawio> <output.drawio.png>
```

### Step 6: Visual Validation

The visual check catches things the validator cannot: label clipping, text readability, aesthetic spacing, edge label congestion, and routing artifacts from the drawio orthogonal engine that differ from the planned waypoints.

Spawn a **sub-agent** via the Agent tool to inspect the exported PNG. **NEVER read image files (PNG, SVG, PDF, JPG) directly in the main context** — images accumulate across iterations and corrupt after context compaction, causing API errors.

The validator already checked structural defects (edge-through-node, crossings, near-misses, container overflow, edge label collisions). The visual check focuses on things the validator cannot catch:

```
Agent({
  description: "Validate diagram layout",
  prompt: "Read the image at <path-to-exported-png> using the Read tool. The programmatic validator already passed — focus on VISUAL issues only: (1) labels clipped or unreadable at the rendered size, (2) edge label congestion — multiple labels overlapping in a tight area, (3) containers not visually enclosing their children (render artifacts), (4) poor aspect ratio — is it too wide or too narrow for comfortable viewing? (5) visual hierarchy — can you tell at a glance what the important phases are? Report findings as a numbered list. If no issues, report 'Layout validation passed'. Do NOT output the image — text only."
})
```

### Step 7: Iterate on Visual Issues

If the sub-agent finds issues the validator missed:
1. Identify the specific problem from the text report
2. Adjust coordinates in the layout plan JSON
3. Re-run Step 4 (validator loop until clean) then Steps 5-6 (render + visual check)
4. Repeat until clean or `--iterate` limit is reached

Each iteration spawns a fresh sub-agent so no images accumulate in any context.

Common visual-only issues (not caught by validator):
- Label clipped → increase node width
- Edge label congestion → shift connected nodes apart to create more edge length for label placement
- Drawio routing artifact → add explicit waypoints to override the orthogonal router's choice

### Step 8: Finalize

Open the final output file (macOS: `open`, Linux: `xdg-open`):

```bash
open <output-file>  # macOS
```

Report to the user: output path, number of iterations used, and any remaining warnings from validation.

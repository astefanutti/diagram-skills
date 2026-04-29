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

This outputs a normalized JSON graph spec to stdout with nodes, edges, containers, and callouts.

If no input file, construct the graph spec directly from the user's natural language description. The spec format is:

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

Run the graph analysis script:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/graph_analysis.py <graph-spec.json>
```

This uses networkx to compute topological layers, fan-out/fan-in points, back-edges, and classify the topology as `pipeline`, `diamond`, `hub-spoke`, or `complex`. It outputs the enriched graph spec with topology annotations.

### Step 3: Generate Layout Plan

Read the layout rules and coordinate system:
- `${CLAUDE_SKILL_DIR}/prompts/layout-rules.md` — the 7 layout patterns
- `${CLAUDE_SKILL_DIR}/prompts/coordinate-system.md` — sizing tables and spacing

Using the enriched graph spec and these rules, generate a layout plan with explicit coordinates. The layout plan is a JSON object:

```json
{
  "canvas": {"width": 1920, "height": 800},
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
      "waypoints": null
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

Apply the 7 layout patterns in order:
1. Assign nodes to semantic columns based on role
2. Stack fan-out alternatives vertically at the same x
3. Route back-edges around the exterior with explicit waypoints
4. Size and position containers around their children
5. Position callout boxes in whitespace areas
6. Set canvas dimensions based on topology class
7. Place edge labels at midpoints without overlap

Write the layout plan to a temporary JSON file.

### Step 4: Render

Convert the layout plan to drawio XML:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/render_drawio.py <layout-plan.json> <output.drawio>
```

If `--format` was specified, export to the requested format:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/export_png.py <output.drawio> <output.drawio.png>
```

### Step 5: Visual Validation

First, run programmatic validation:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/validate_layout.py <layout-plan.json>
```

This checks for node overlaps, edge-node collisions, container bounds violations, and canvas overflow.

Then spawn a **sub-agent** via the Agent tool to visually inspect the exported PNG. **NEVER read image files (PNG, SVG, PDF, JPG) directly in the main context** — images accumulate across iterations and corrupt after context compaction, causing API errors.

Use the Agent tool like this:

```
Agent({
  description: "Validate diagram layout",
  prompt: "Read the image at <path-to-exported-png> using the Read tool and inspect it for layout issues. Check: (1) edges routing THROUGH nodes (worst defect — any edge segment crossing a non-connected node's body), (2) S-bends — small S-shaped wiggles on edges between nearly-aligned nodes that should be straight or L-shaped, (3) edge crossings — edges crossing each other, especially back-edges crossing forward edges, (4) back-edges not routing around the far exterior, (5) alternatives not stacked vertically at the same x-position, (6) labels not readable or clipped, (7) containers not properly enclosing their children. Report findings as a numbered list of specific issues with node/edge IDs. If no issues, report 'Layout validation passed'. Do NOT output the image — text only."
})
```

The sub-agent returns a text-only report. The main context never sees the image data.

### Step 6: Iterate

If the sub-agent report from Step 5 identifies issues:
1. Identify the specific problem from the text report (which nodes overlap, which edges cross)
2. Adjust the coordinates in the layout plan JSON
3. Re-run Steps 4 and 5 (rendering + spawning a **new** sub-agent for validation)
4. Repeat until the layout is clean or `--iterate` limit is reached

Each iteration spawns a fresh sub-agent so no images accumulate in any context.

Common adjustments (in priority order — fix worst defects first):
- **Edge through node** (worst) → reroute back-edge waypoints to the far exterior (x < leftmost_node_x - 20), enter target from the side instead of bottom. See Rule 9 in layout-rules.md
- **S-bend** → nudge node by 5-10px or adjust exit/entry anchor fractions so connection points align exactly. See Rule 8
- **Edge crossing** → separate forward and back-edge corridors. Forward edges use inter-column space; back-edges use far exterior margins. See Rule 10
- Node overlap → increase spacing or shift one node
- Container too small → increase container dimensions with 20px padding
- Label clipped → increase node width

### Step 7: Finalize

Open the final output file:

```bash
open <output-file>
```

Report to the user: output path, number of iterations used, and any remaining warnings from validation.

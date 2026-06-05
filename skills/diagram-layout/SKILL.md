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

### Step 3: Generate Layout Plan (three passes)

Split the layout into **three passes** to keep each thinking step focused and fast. Each pass reads only the references it needs.

#### Step 3a: Assign grid positions

Read `${CLAUDE_SKILL_DIR}/prompts/layout-rules.md` (Rules 1-2 and 6a only — column assignment, vertical stacking, aspect ratio).

For each node, assign a **column** (semantic role) and **row** (vertical position within that column). Output a simple grid assignment — no pixel coordinates yet.

1. Classify each node as **pipeline** (entry, processing, decision, output) or **free-floating** (external services, callouts, annotations)
2. Assign pipeline nodes to semantic columns based on role (Rule 1)
3. Within each column, stack fan-out alternatives vertically (Rule 2)
4. Check aspect ratio: if all pipeline nodes are in a single row and there are 8+ nodes, apply strip detection (Rule 6a) — stack same-column nodes or wrap the widest segment
5. Note where free-floating nodes should go (exterior, near their connections) — exact position deferred to Step 3b

Write the grid assignment to `artifacts/grid-assignment.json`:
```json
{
  "columns": [
    {"col": 0, "nodes": ["entry"]},
    {"col": 1, "nodes": ["find-skill", "load-config"]},
    {"col": 2, "nodes": ["check", "assess"]},
    {"col": 3, "nodes": ["analyze", "explore"]}
  ],
  "free_floating": ["mlflow-server", "eval-setup", "callout-1"],
  "topology": "diamond",
  "num_rows": 2,
  "wrap_at_col": null
}
```

#### Step 3b: Compute pixel coordinates

Read `${CLAUDE_SKILL_DIR}/prompts/coordinate-system.md` (sizing tables and spacing) and `artifacts/grid-assignment.json`.

Convert the grid assignment into pixel coordinates. For each node: compute x, y, width, height based on column position, sizing tier, and text content. Use the text width estimation formulas in coordinate-system.md to size each node based on its actual label content.

1. Compute column x-positions from column spacing and node widths
2. Compute row y-positions within each column
3. Size and position containers around their children (10px padding minimum)
4. Position free-floating nodes in whitespace areas where their edges won't cross the pipeline flow (Rule 1 — free-floating nodes)
5. Set canvas dimensions to fit the layout

Write the node-only layout plan to `artifacts/layout-plan.json`. The `elements` array after Step 3b contains only nodes, containers, and callouts — no edge elements. Step 3c appends edges.

#### Step 3c: Route edges

Read `artifacts/layout-plan.json` and `${CLAUDE_SKILL_DIR}/prompts/layout-rules.md` (Rules 3, 7, 8 — back-edges, labels, edge quality).

Add all edges with explicit waypoints, exit/entry points, labels, and styles. For each edge:
1. Choose exit/entry sides that face the target (Rule 8c — minimize bends)
2. Route back-edges compactly (Rule 3) — short loops route above, long ones below. Keep loops tight to the involved nodes.
3. Compute waypoints for edges that need non-trivial routing. Every segment must be perfectly horizontal or vertical — include corner waypoints for every turn (Rule 8b).
4. Add labels at midpoints along the **longest segment** of each edge, offset perpendicular. Verify no label overlaps any node bounding box — the validator checks this.
5. Verify zero edge crossings (Rule 8d)

Append the edge elements to the layout plan and write the complete `artifacts/layout-plan.json`.

#### Step 3d: Programmatic fix pass

Run the post-processing fixer to mechanically correct common layout issues before validation:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/fix_layout.py artifacts/layout-plan.json
```

This applies three deterministic fix passes:
1. **Orthogonal snapping** — inserts corner waypoints wherever consecutive edge points form a diagonal segment, producing clean L-bends
2. **Overlap resolution** — pushes overlapping nodes apart along the axis of least overlap, expanding the canvas if needed
3. **Edge-through-node rerouting** — inserts waypoints to route edges around obstructing nodes they pass through

The fixer modifies `artifacts/layout-plan.json` in place and prints a summary of fixes applied. Run this before every `validate_layout.py` call — it catches and fixes issues that would otherwise require manual LLM iteration.

The layout plan JSON format for both passes:

```json
{
  "canvas": {"width": 1600, "height": 700},
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

Each iteration runs the fixer then the validator:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/fix_layout.py artifacts/layout-plan.json
python3 ${CLAUDE_SKILL_DIR}/scripts/validate_layout.py artifacts/layout-plan.json
```

The fixer mechanically corrects orthogonal snapping, overlaps, and edge-through-node issues. The validator then checks for anything the fixer couldn't resolve: edge-edge crossings, near-miss clearance (15px minimum), avoidable bends, and canvas bounds.

**All edges MUST use orthogonal routing** — every segment is either perfectly horizontal or perfectly vertical. A tangent (diagonal) segment connecting to a node is a critical defect. If an edge arrives at a node at an angle, fix the exit/entry anchor points so the connection is orthogonal. This is enforced by `edgeStyle=orthogonalEdgeStyle` in the drawio style, but the layout plan coordinates must also be consistent — waypoints must share an x or y coordinate with adjacent waypoints. The fixer handles this automatically by inserting corner waypoints.

**If errors or warnings after the fixer**: read the validator output, apply the corresponding fix from layout-rules.md, update the layout JSON, and re-run both fixer and validator. Repeat until clean or up to **5 iterations**.

Fix rules by priority:
1. **Edge through node** (error) → reroute waypoints to the far exterior, enter target from the side. See Rule 8a
2. **Edge crossing** (warning) → separate corridors, apply nested fan-out ordering, swap exit anchors. See Rules 8c, 8d
3. **Near-miss** (warning) → nudge the nearby node away (prefer moving nodes over edges). See Rule 8e. Re-check connected edges for new S-bends (Rule 8f cascading)
4. **Avoidable bend** (warning) → change exit/entry side to face the target. See Rule 8c
5. **Canvas overflow** → expand canvas or compress column spacing

**Graceful degradation — drop secondary nodes when routing can't converge.** If after 3 iterations the validator still reports edge-through-node errors or 5+ edge crossings, the layout is too dense for clean routing. Instead of continuing to shuffle waypoints, simplify the graph:

1. Identify the lowest-priority nodes: external/optional nodes with dashed borders (downstream "suggested" skills, external services that aren't central to the flow). These are the nodes whose `style` contains `stroke-dash` or whose `role` in the graph spec is `external` or `optional`.
2. Remove those nodes and all their connected edges from the layout plan.
3. Re-run the validator on the simplified layout. The removed edges were likely causing the crossings.
4. Continue iterating on the simplified layout for the remaining 2 iterations.

A clean diagram with fewer nodes is always better than a complete diagram with edges crossing through nodes. The dropped nodes are still in the D2 source — readers can see them there. The layout's job is visual clarity, not completeness.

**Do NOT render to drawio/PNG until the validator reports zero errors and zero warnings.** The validator is fast (milliseconds); rendering + visual inspection is slow (seconds + sub-agent). Use the validator as the tight inner loop.

### Step 5: Render

Once the validator passes clean, convert to drawio XML:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/render_drawio.py <layout-plan.json> <output.drawio>
```

If `--format` was specified, export to the requested format:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/export_diagram.py <output.drawio> <output.drawio.png>
```

### Step 6: Visual Validation

The visual check catches things the validator cannot: label clipping, text readability, aesthetic spacing, edge label congestion, and routing artifacts from the drawio orthogonal engine that differ from the planned waypoints.

Spawn a **sub-agent** via the Agent tool to inspect the exported PNG. **NEVER read image files (PNG, SVG, PDF, JPG) directly in the main context** — images accumulate across iterations and corrupt after context compaction, causing API errors.

The validator already checked structural defects (edge-through-node, crossings, near-misses, container overflow, edge label collisions). The visual check focuses on things the validator cannot catch.

**Skip the visual check** for simple diagrams: if the validator passed clean on the first try AND the graph has ≤8 nodes with no containers, proceed directly to Step 8. The visual check adds 200-400s and mostly catches label clipping in complex layouts.

For diagrams that need visual validation:

```
Agent({
  description: "Validate diagram layout",
  prompt: "Read the image at <path-to-exported-png> using the Read tool. The programmatic validator and fixer already passed — focus on VISUAL issues only.\n\nCheck each category and report as JSON:\n\n| Check | What to look for |\n|-------|------------------|\n| clipped_labels | Text cut off at shape boundaries |\n| edge_label_congestion | Multiple edge labels overlapping in a tight area |\n| container_artifacts | Containers not visually enclosing their children |\n| edge_shape_overlap | An edge visually crossing through an unrelated shape (fixer may have missed edge cases) |\n| stacked_edges | Multiple edges overlapping on the same path |\n| visual_hierarchy | Can you tell at a glance what the important phases are? |\n\nThe diagram uses fan-out stacking and containers for aspect ratio control (NOT row wrapping) — do not suggest wrapping into rows unless the ratio exceeds 5:1.\n\nRespond with ONLY a JSON object:\n{\"issues\": [{\"type\": \"<category>\", \"element\": \"<node/edge id or description>\", \"fix\": \"<suggested fix>\"}], \"passed\": true/false}\n\nIf no issues, respond: {\"issues\": [], \"passed\": true}\nDo NOT output the image — JSON only."
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

Write a metrics summary to `artifacts/skill-metrics.json` with layout statistics:

```json
{
  "nodes": 12,
  "edges": 14,
  "containers": 2,
  "validation_iterations": 3,
  "visual_iterations": 1,
  "canvas_width": 1600,
  "canvas_height": 700,
  "aspect_ratio": 2.3,
  "topology": "diamond"
}
```

Open the final output file (macOS: `open`, Linux: `xdg-open`):

```bash
open <output-file>  # macOS
```

Report to the user: output path, metrics summary, and any remaining warnings.

# Layout Rules for Presentation-Quality Flow Diagrams

Apply these 7 rules in order when generating coordinates for the layout plan. Each rule builds on the previous ones.

## Rule 1: Semantic Column Assignment

Assign each node to a semantic column based on its ROLE in the pipeline, not its graph distance from entry. Standard column roles:

| Column | Role | Examples |
|--------|------|----------|
| 0 | Entry / trigger | /eval-analyze, /eval-run, /eval-mlflow |
| 1 | Setup / config loading | Find Skill, Load Config, Read Context |
| 2 | Assessment / decision | Freshness Check, Preflight, Assess Current State |
| 3 | Core processing | Deep Skill Analysis, Execute Skill, strategies |
| 4 | Validation / scoring | Validate, Score, Collect |
| 5 | Output / reporting | Generate eval.md, Report, review.yaml |
| 6 | External / optional | MLflow Server, external services |

When two nodes serve parallel roles (both are core processing, both are output generators), place them in the SAME column, stacked vertically. This is critical for fan-out patterns.

Column x-positions: `col_x = margin_left + col_index * column_spacing`, where column_spacing = max node width in that column + horizontal gap (40-60px).

When a node's role is ambiguous, consider: what does it PRODUCE? Nodes producing intermediate artifacts go in processing columns. Nodes producing final outputs go in output columns.

## Rule 2: Vertical Stacking of Alternatives

When a node fans out to N successor alternatives (same semantic role):

1. All alternatives go at the SAME x-position (same column)
2. Stack them vertically with 30-50px gaps between them
3. Center the stack vertically so the fan-out source's center y aligns with the stack's midpoint
4. Order alternatives top-to-bottom by: primary/default path first, secondary paths next, fallback/error paths last

Example from eval-dataset: Assess Current State fans out to Bootstrap (top, default), Expand (middle), From Traces (bottom, fallback). All three are at the same x.

For fan-in (multiple nodes converging to one), position the fan-in target centered vertically relative to its predecessors' y-range.

## Rule 3: Back-Edge Exterior Routing

Back-edges (loops, feedback) MUST route around the diagram exterior, never through nodes:

1. Identify the back-edge direction (typically leftward in a left-to-right diagram)
2. Choose routing side: bottom for most cases, top if bottom is crowded
3. Create waypoints forming a U-shape:
   - Exit the source node from the bottom (exitY=1) or side
   - Drop down to `route_y = max(all_node_bottom_y) + 50`
   - Travel horizontally to align with the target
   - Enter the target from the bottom (entryY=1) or side

Waypoint template for bottom-routed back-edge (left-to-right diagram):
```
exit: (source_center_x, source_bottom)
waypoints: [
  (source_center_x, route_y),
  (target_center_x, route_y)
]
entry: (target_center_x, target_bottom)
```

Where `route_y = max(all_node_bottom_y) + 50` to clear everything.

For multiple back-edges, stagger the route_y values (each 25px lower) to prevent overlapping routes.

Style back-edges with: `dashed=1;dashPattern=8 4;` to visually distinguish from forward edges.

## Rule 4: Container Grouping

Group nodes in a container when they represent a single logical unit with:
- A shared title/phase name
- Internal sub-steps that execute together
- A common processing stage

Container layout rules:
- **Padding**: left/right 15-20px, top 35-50px (for title), bottom 15-20px
- **Children positioning**: relative coordinates (origin = container top-left + padding)
- **Internal layout**: arrange children in a row if parallel, in a column if sequential
- **Container sizing**: fit all children with padding. Width = sum of children widths + gaps + side padding. Height = max child height + top padding + bottom padding (for row layout)
- **Container style**: `container=1;collapsible=0;` with subtle fill (#ececec) and border

For containers within the main flow: the container acts as a single node for column assignment. Its center should align with the flow.

For colored containers (semantic grouping like review=blue, optimize=green): use `strokeColor=#4285f4` or `strokeColor=#34a853` with `strokeWidth=2`.

## Rule 5: Callout Detail Boxes

Supplementary information goes in callout boxes connected with dashed edges:

- **Position**: below or to the side of the anchor node, in whitespace
- **Edge style**: `dashed=1;dashPattern=4 4;strokeColor=#bbbbbb;strokeWidth=1;`
- **Content types**:
  - File trees: use monospace font (`fontFamily=Courier New;fontSize=10;align=left;`)
  - YAML snippets: monospace, left-aligned
  - File listings: left-aligned with dots
- **Sizing**: fit content with 10px internal padding
- **Rule**: callouts must NOT overlap main flow nodes or edges. Place them in dead zones — areas with no forward edges passing through

## Rule 6: Aspect Ratio and Canvas Sizing

Choose canvas dimensions based on the graph topology:

| Topology | Aspect Ratio | Starting Canvas |
|----------|-------------|-----------------|
| Pipeline (linear chain, max fan-out ≤ 1) | 3:1 to 4:1 | 1920 x 600 |
| Diamond (fan-out + fan-in, ≤ 2 fan-out points) | 2:1 to 2.5:1 | 1600 x 700 |
| Hub-spoke (one central node with high degree) | 1:1 to 1.5:1 | 1200 x 900 |
| Complex (multiple fan-outs, containers, back-edges) | 2:1 | 1920 x 1000 |

After initial placement, check:
- If rightmost node x + width > canvas width → expand canvas or compress column spacing
- If bottommost node y + height > canvas height → expand canvas
- If diagram fills less than 60% of canvas → shrink canvas
- Back-edge routes at bottom may require extra canvas height (add route_y + 30)

## Rule 6a: Pipeline Wrapping for Wide Diagrams

**Maximum comfortable canvas width: ~1800px.** When a left-to-right pipeline has more than 7-8 semantic columns, a single horizontal strip becomes too wide for comfortable viewing (requires horizontal scrolling, doesn't fit on screens or slides).

**When to wrap**: if the initial column layout exceeds 1800px width, restructure the diagram into 2-3 rows:

**Preferred approach — semantic phase rows**: group related steps into horizontal phases, stacked vertically:
- **Row 1 (top)**: Setup phase — entry, config, dataset, preflight, workspace
- **Row 2 (middle)**: Execution phase — execute, hooks, collect
- **Row 3 (bottom)**: Scoring + Reporting phase — score, analyze, report, mlflow

Each row flows left-to-right. Rows connect with a vertical edge from the last node of one row to the first node of the next.

**Row-transition waypoint template**: when the last node of row N connects to the first node of row N+1 (which is back at the left side), route the edge down and left using the shared-trunk pattern:
```
exit: bottom of last node in row N
waypoints: [
  (exit_x, corridor_y),     // drop to horizontal corridor between rows
  (trunk_x, corridor_y),    // go left to exterior trunk
  (trunk_x, target_y)       // drop to target level
]
entry: left side of first node in row N+1
```
Where `corridor_y` is the y midpoint between the two rows, and `trunk_x` is to the LEFT of all nodes in both rows (x < leftmost_node_x - 15).

**Multiple row-transition edges**: when a node fans out to multiple targets at the start of the next row (e.g., mode branching), use the shared-trunk pattern — same `corridor_y` for all edges, nested `trunk_x` values (inner for closer target, outer for farther). This prevents the horizontal corridors from crossing the vertical trunks.

**Routing around containers between rows**: when an edge crosses rows and a container sits between the source and destination, route the edge OUTSIDE the container's bounding box (right or left, whichever is shorter). Add a waypoint at `container_right_edge + 15px` to clear it.

**Bidirectional subsystems**: when a step has a bidirectional relationship with a subsystem (e.g., execute ↔ tool interception), place the subsystem BELOW the caller. Use vertical edges: solid down from caller to subsystem, dashed up from subsystem back to caller. Offset the entry/exit x-positions slightly (e.g., 0.4 and 0.6) so the two vertical edges are distinguishable.

**Alternative — zigzag**: Row 1 flows left-to-right, Row 2 flows right-to-left, connected at the ends. Works for simple pipelines but confusing for complex ones with side branches.

**Column compression**: before wrapping, try compressing column spacing (reduce from 50px to 30px gaps) or merging tightly-coupled sequential steps. Only wrap if compression still exceeds ~1800px.

## Rule 6b: Variable Node Sizing by Complexity

Nodes should be sized to match their content and structural importance, not uniform across the diagram.

**Sizing tiers** (enforce these — don't make all nodes the same size):

| Tier | Width | Height | Use for | Visual weight |
|------|-------|--------|---------|---------------|
| Large | 350-550 | 120-140 | Containers (Score, Execute, Tool Interception) | Dominant — the core subsystems |
| Medium | 150-180 | 120-150 | Major processing (Load Config, Prepare Workspace) | Standard — the backbone steps |
| Small | 120-145 | 80-110 | Minor steps (Preflight, Find Dataset, Collect) | Light — validation gates, pass-through |
| Compact | 100-130 | 40-55 | External skills, downstream links (/eval-mlflow) | Minimal — just references |
| Callout | 160-220 | 150-200 | File trees, config snippets | Distinct — reference material |

**The test**: if two nodes have the same width and height but very different importance to the workflow, one of them is mis-sized. Preflight Check should NOT be the same size as Prepare Workspace.

**Anti-pattern**: making all nodes the same size. This produces a monotonous visual rhythm and fails to communicate which steps are the important ones.

## Rule 7: Edge Labels and Conditional Styling

For conditional edges (decision branches, error paths, shortcuts):

- **Label text**: short, descriptive (e.g., "FRESH + COMPLETE", "errors", "gaps found")
- **Label style**: `fontStyle=2;fontSize=11;` (italic, smaller)
- **Label position**: along the longest segment of the edge, offset 5-10px perpendicular to the edge
- **In drawio**: edge label is the `value` attribute. Position is controlled by `mxGeometry relative="1"` with x between -1 (near source) and 1 (near target)

Edge style by type:
- **Forward edge**: `strokeColor=#333333;strokeWidth=1.5;` solid
- **Conditional/optional**: `dashed=1;dashPattern=8 4;strokeColor=#333333;`
- **Back-edge/loop**: `dashed=1;dashPattern=8 4;strokeColor=#333333;` with explicit waypoints
- **Callout connection**: `dashed=1;dashPattern=4 4;strokeColor=#bbbbbb;strokeWidth=1;`

All edges use: `edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;`

## Rule 8: S-bend Elimination

Orthogonal edge routing introduces small S-shaped wiggles when source and target anchor points are nearly but not exactly aligned horizontally or vertically. These S-bends look amateurish and must be eliminated.

**Detection**: After assigning coordinates, for every edge check whether the exit point and entry point are within 15px of being horizontally or vertically aligned. If they are:

**Fix** (in priority order):
1. **Adjust the anchor point** — change exit_point or entry_point fraction so the connection points align exactly. For example, change `exitY` from `0.5` to `0.48` if that aligns with the target's entry y.
2. **Nudge the node** — shift the source or target node by a few pixels so their connection points align exactly. A 5-10px shift is invisible to the viewer but eliminates the S-bend.
3. **Set explicit exit/entry points** — on both ends of the edge to force exact alignment, overriding the router's default anchor selection.

**Rule**: every edge between nodes in the same row (same y-range) must be a straight horizontal line. Every edge between nodes in the same column (same x-range) must be a straight vertical line. Diagonal connections should be clean L-bends (one turn), never S-bends (two opposing turns).

## Rule 9: No Edge Through Node — Absolute Prohibition

Edges must NEVER pass through the bounding box of any node they are not connected to. This is the single worst layout defect — worse than overlaps, worse than crossings.

**The common trap**: back-edges that return to a target via a vertical segment at the target's center x. If there are other nodes between the routing corridor and the target, the vertical segment passes straight through them.

**Verification**: for every edge with waypoints, check that no waypoint segment intersects any non-connected node's bounding box. The `validate_layout.py` script checks this programmatically.

## Rule 9a: Minimize Bends — Exit Toward the Target

For every edge, choose the exit side that FACES the target and the entry side that FACES the source. This minimizes the number of orthogonal bends (turns).

**Scoring**: count the bends in the edge path. An optimal edge between non-adjacent nodes has exactly 1 bend (an L-shape). Each additional bend beyond the minimum is a penalty. The minimum bend count depends on the relative position of source and target:
- Target is in a cardinal direction (directly below, directly right) → 0 bends (straight line)
- Target is diagonal (below AND to the left) → 1 bend (L-shape)
- Any more bends than the minimum indicates a suboptimal exit/entry side choice

**How to choose exit/entry sides**: compute the direction from source center to target center.
- Target is primarily **below** → exit from **bottom** (`exitY=1`)
- Target is primarily to the **right** → exit from **right** (`exitX=1`)
- Target is primarily **above** → exit from **top** (`exitY=0`)
- Target is primarily to the **left** → exit from **left** (`exitX=0`)
- For the entry point, apply the same logic in reverse: if the source is above-right, enter from the **right** or **top**

**Back-edges specifically**: a back-edge from a right-side node to a lower-left node should exit from the **bottom** (target is below) and enter from the **right** (source is to the right). This gives one clean L-bend: straight down, then straight left. Exiting from the right side would add an unnecessary rightward jog before descending.

**Waypoint template for bottom-exit, right-entry back-edge**:
```
exit: source bottom (exitX=0.5, exitY=1)
waypoints: [
  (source_exit_x, target_entry_y)   // descend to target level
]
entry: target right side (entryX=1, entryY=0.7)
```

**Multiple edges from the same side — nested ordering**: when two or more edges exit from the same side of a node, order their exit points so the resulting paths are **nested** (like parentheses), not crossing. The rule: the exit point closest to the target side goes to the **closest** target, and the exit point farthest from the target side goes to the **farthest** target.

For bottom exits going down-then-left to targets at different y-levels:
- The closer target (smaller y-distance) gets the exit point nearer to the target side (smaller exitX, closer to the left where targets are)
- The farther target (larger y-distance) gets the exit point farther from the target side (larger exitX, more to the right)

This ensures the closer target's horizontal sweep stays inside the farther target's vertical descent, creating nested non-crossing paths.

**Why this works**: if the inner (closer) exit goes to the closer target, its horizontal at a higher y never reaches the outer (farther) exit's x position. The outer edge descends past the inner edge's horizontal without crossing.

Stagger `entryY` values (e.g., 0.6, 0.7) so entry points don't overlap forward-edge anchors.

## Rule 10: Edge Crossing Minimization

When back-edges share routing corridors with forward edges, they create crossings. Minimize crossings by:

1. **Enter from the source side** (Rule 9a): the single most effective technique. Right-side entry keeps back-edges entirely in the right exterior corridor, away from all forward-flow edges.
2. **Separate corridors**: forward edges use the space between columns. Back-edges use the far exterior margin (right of rightmost column).
3. **Stagger parallel back-edges**: when multiple back-edges share the exterior route, stagger their x positions by 10px and offset their entry anchor points (e.g., `entryY=0.6` vs `entryY=0.7`) to keep them visually distinct and avoid overlapping anchors with forward edges.

## Rule 11: Cascading Re-validation After Node Moves

Moving a node to fix one issue (clearance, overlap, spacing) can introduce new issues on edges connected to or passing near that node. After any node position change, re-check:

1. **S-bends on connected edges**: if the moved node is no longer center-aligned with the node at the other end of an edge, the edge gets an S-bend. Fix by setting explicit exit/entry anchor points so both anchors resolve to the same y (for horizontal edges) or same x (for vertical edges). When two nodes are offset, split the difference — compute a shared y between their centers and set anchor fractions accordingly.

2. **Near-miss clearance**: the moved node may now be closer to or farther from nearby edges. Re-run the clearance check.

3. **Edge crossings**: new anchor positions may shift edge segments into crossing paths. Re-run the crossing check.

**The general principle**: every node position change requires a full re-score of the layout. Never move a node and assume the rest of the layout is still valid.

## Rule 12: Edge-Node Clearance

Edges must maintain a minimum clearance of **15px** from the bounding box of any non-connected node. An edge passing within this margin looks like it almost touches or belongs to the node, creating visual confusion.

**Detection**: `validate_layout.py` checks every edge segment against every non-connected node with a 15px margin. Near-misses are flagged as warnings with the exact distance.

**Fix — prefer moving the node, not the edge**: when a near-miss is detected, first check whether the nearby node has room to shift away from the edge. Nodes that are loosely constrained (output nodes centered on their source, callout boxes) can often shift 15-25px without disrupting the layout. Only adjust the edge routing if the node is tightly constrained.

**Why move the node**: edge routing is determined by anchor points and waypoints that serve structural purposes (avoiding crossings, minimizing bends). Adjusting them to dodge a nearby node often introduces new problems. Moving the node is a local, safe fix.

## Rule 12: Draw.io Reserved Identifiers

The draw.io export CLI silently fails when a cell uses certain reserved identifiers. Known reserved IDs:
- `push`

**Fix**: never use bare reserved words as cell IDs. Append a suffix (e.g., `pushfb`, `push_node`, `push1`).

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

**Free-floating nodes** — external services, callouts, and file annotations do NOT participate in the pipeline flow. They have no sequence constraints (no "must come after step X"). This means they are NOT bound to column assignment — position them wherever minimizes edge crossings and maximizes routing clarity. Treat their placement as a routing optimization problem, not a semantic column decision.

Examples of free-floating nodes: MLflow Server, API gateways, databases, file-tree callouts, config-snippet callouts, schema annotations. These nodes connect to pipeline steps but are not steps themselves.

**Placement strategy**: after placing all pipeline nodes (steps 1-2), position free-floating nodes in the remaining whitespace. For each free-floating node, consider all candidate positions (above, below, left margin, right margin) and pick the one where its edges don't cross any existing edges or pass through any pipeline nodes. Common good positions:
- A service connected to many nodes on the right side → place it far right, vertically centered among its connections
- A callout connected to one node → place it directly below or beside that node, in nearby whitespace
- A service connected to nodes across the full width → place it above or below the entire flow, not in the middle

## Rule 2: Vertical Stacking of Alternatives

When a node fans out to N successor alternatives (same semantic role):

1. All alternatives go at the SAME x-position (same column)
2. Stack them vertically with 30-50px gaps between them
3. Center the stack vertically so the fan-out source's center y aligns with the stack's midpoint
4. Order alternatives top-to-bottom by: primary/default path first, secondary paths next, fallback/error paths last

Example from eval-dataset: Assess Current State fans out to Bootstrap (top, default), Expand (middle), From Traces (bottom, fallback). All three are at the same x.

For fan-in (multiple nodes converging to one), position the fan-in target centered vertically relative to its predecessors' y-range.

**Beyond fan-out**: also stack nodes vertically when they share the same semantic column even if they're not strict alternatives. If two nodes are both "core processing" (column 3), stack them rather than placing them in separate columns. This compresses width and improves aspect ratio — the primary mechanism for avoiding overly wide diagrams.

## Rule 3: Back-Edge Exterior Routing

Back-edges (loops, feedback) MUST route around nodes, never through them:

1. Identify the back-edge direction (typically leftward in a left-to-right diagram)
2. Choose routing side: **top is preferred** for short back-edges (adjacent nodes), bottom for long back-edges that span many columns
3. **Keep loops compact** — route only as far below/above as needed to clear the nodes between source and target, not the entire diagram. For a back-edge between adjacent nodes, route just 30-40px above or below them.

Waypoint template for **top-routed** short back-edge (the most common case — validation retry loops):
```
exit: (source_center_x, source_top)
waypoints: [
  (source_center_x, route_y),
  (target_center_x, route_y)
]
entry: (target_center_x, target_top)
```

Where `route_y = min(source_top, target_top) - 30` — just above the involved nodes.

For **long back-edges** spanning many columns, use bottom routing:
```
route_y = max(source_bottom, target_bottom) + 40
```

The key principle: route_y should be relative to the **involved nodes**, not the entire diagram. A validation retry loop between two adjacent nodes should be a tight arc, not a wide sweep across the full canvas. Specifically: `route_y` should be at most 60px beyond the involved nodes' bounding box. A back-edge that routes 200+ pixels away from its source and target is a "wide open loop" defect — it wastes space and makes the edge hard to follow.

For multiple back-edges, stagger the route_y values (each 25px lower) to prevent overlapping routes.

**Vertically stacked nodes** — when source and target share the same x-range (same column, stacked vertically), route the back-edge on the right exterior:
```
exit:  (source_right, source_center_y)     exitX=1, exitY=0.5
waypoints: [
  (source_right + 20, source_center_y),
  (source_right + 20, target_center_y)
]
entry: (target_right, target_center_y)     entryX=1, entryY=0.5
```
NEVER use `entryX=1, entryY=1` (bottom-right corner) for vertically stacked back-edges — this forces the edge to detour around the bottom of the target node, creating a U-shaped path that crosses under the target. Always enter from the right side at the target's vertical center.

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

## Rule 5b: Shared Fan-in Target Placement (hub-spoke)

When several parallel operations each feed the **same** downstream target(s) — a "fan-in" — place those shared targets **adjacent to the operations column**, vertically centered on the operations they receive from. Do NOT push them to the canvas extremes.

This pattern is common in hub-spoke diagrams: a config/dispatch node fans out to N operations, and those N operations all converge on one or two shared targets (e.g., a Report node and an external Server). The failure mode is placing the shared target in the far "output" column (Rule 1 column 5/6) when there is nothing between it and the operations — this creates a wide empty band and N long parallel edges crossing it.

Rules:
1. **Distance**: a shared fan-in target sits one column-gap (40-60px) to the right of the **widest** operation in the column, not at the canvas edge. If the operations column's right edge is at x=R, the target's left edge is at ~R+50, regardless of where other "output" nodes sit.
2. **Vertical centering**: center the target on the y-midpoint of the operations that feed it, so the convergence edges are short and symmetric rather than long diagonals-turned-L-bends.
3. **Two shared targets** (e.g., Report on the right, Server below): place one to the right of the operations (vertically centered) and the other directly below the operations (horizontally centered), each hugging the column. Avoid putting one at the far right AND one at the far bottom — that maximizes edge length and whitespace.
4. **Downstream of the target**: if the shared target has its own downstream nodes (e.g., Report → review/optimize), place those immediately beyond the target in the same direction, so the target + its satellites form one compact cluster — never leave the target stranded far from its sources to make room for its satellites.

The test: if you can draw a large empty rectangle (no nodes, only edges) between a fan-out column and its shared fan-in target, the target is too far away — pull it in.

## Rule 5c: Two shared sinks → opposite sides (avoid the double-fan-in crossing)

When the **same** group of N operations each connect to **two** shared targets (e.g. every operation links to both a Report and an external MLflow Server), placing both targets on the **same side** of the operations column forces edge crossings — the edges to the near target cross the edges to the far one. This subgraph (N sources × 2 sinks) is planar, so the crossings are avoidable.

Place the two sinks on **opposite sides** of the operations group:
- one to the **right** of the column, the other to the **left** (or one **above**, one **below** for a horizontal source row). Each operation then sends one edge left and one edge right — no crossings.

Critically, "opposite side" must be free of **edges**, not just nodes. The side an incoming pipeline feeds from (e.g. a dispatch node fanning into the operations from the left) is full of fan-out edges; dropping a sink there trades hub-vs-hub crossings for sink-vs-fan-out crossings. So:
- If the operations are fed from the left, keep one sink on the right and route the pipeline so the **other side is genuinely clear** — e.g. enter the operations from the **top** (so the left and right are both free for the two sinks), or
- **Group the operations** into a container and connect the two sinks to the *container* (one bundled edge per sink, on opposite sides) instead of N separate edges to each sink — this collapses the 2N fan-in edges to 2 and removes the crossings entirely. Use this when the per-operation edge labels aren't essential.

If neither is possible (sinks boxed in on the same side), separate them vertically and accept the residual **perpendicular** crossings (one edge horizontal, one vertical) — these read as a clean X and are the least disruptive crossing, acceptable per the graceful-degradation guidance.

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

## Rule 6a: Aspect Ratio Control

After initial placement, check the aspect ratio against the target for the topology class (Rule 6). If the diagram is too elongated, apply these strategies in priority order — each one compresses width and increases height naturally. Most diagrams need only strategies 1-2.

**Strategy 1 — Fan-out stacking (primary).** This is the most effective aspect ratio control. Parallel alternatives at the same pipeline stage stack vertically at the same x-position (Rule 2). Every fan-out cluster compressed this way reduces width by one column and increases height. The gold standard diagrams achieve good ratios entirely through this mechanism.

**Strategy 2 — Container grouping.** Group 3+ related steps into containers (Rule 5). A container with internal layout is more compact than the same steps laid out individually. Containers also communicate semantic grouping to the reader.

**Strategy 3 — Spacing compression.** Reduce column spacing from 50px to 30px gaps, or merge tightly-coupled sequential steps into single nodes. This can recover 100-200px of width without changing the topology.

**Strategy 4 — Row wrapping (fallback only).** If strategies 1-3 still leave the aspect ratio >50% above target, break the pipeline into rows. Each row flows left-to-right. Rows are stacked top-to-bottom with vertical transition edges. Wrap incrementally — identify the widest pipeline segment, wrap only that segment into a new row, then re-check. Don't wrap the entire diagram at once.

**Strip layout detection**: after initial placement, check if all forward-flow nodes share roughly the same y-row (y values within 50px). This is a "strip layout" — a long horizontal band that's hard to read. A strip with 8+ nodes always needs correction. Apply strategies 1-3 first (stacking and containers usually suffice), then strategy 4 if still needed. The goal is that the layout uses at least 2-3 distinct y-levels for forward-flow nodes.

**Bidirectional subsystems**: when a step has a bidirectional relationship with a subsystem (e.g., execute ↔ tool interception), place the subsystem on the orthogonal axis (below for `direction: right`, to the right for `direction: down`).

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

**Container child sizing**: container children must fit entirely within the container's bounding box. After placing children, verify:
- No child's text overflows its box (estimate text width: ~7px per character at font-size 13)
- No child extends beyond the container's right or bottom edge
- The container has at least 10px padding on all sides around its children
If children overflow, either widen the child nodes or expand the container. Never let text clip.

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

**Edge label collision avoidance**: after placing all edge labels, verify that no label overlaps a node's bounding box. Labels on horizontal edge segments are placed along the segment — if the segment passes near a node, the label will overlap it. Fix by:
1. Moving the label to a different segment of the same edge (prefer the longest segment)
2. Adjusting the label's offset perpendicular to the edge (increase from 5px to 15-20px)
3. If the edge has only one short segment near a node, shorten the label text

This is especially important in compact layouts where edges run close to unconnected nodes.

## Rule 8: Edge Quality

All edge quality rules are enforced by `validate_layout.py`. Run the validator after every layout change — it catches these issues programmatically.

### 8a. No Edge Through Node

Edges must NEVER pass through the bounding box of any node they are not connected to. This is the single worst layout defect.

**The common trap**: back-edges that return to a target via a vertical segment at the target's center x. If there are other nodes between the routing corridor and the target, the vertical segment passes straight through them.

**Verification**: for every edge with waypoints, check that no waypoint segment intersects any non-connected node's bounding box. The `validate_layout.py` script checks this programmatically.

### 8b. Orthogonal Connection and S-bend Elimination

**Every edge segment must be perfectly horizontal or vertical** — no diagonal segments. The last waypoint before a target node must share either the same x (for top/bottom entry) or same y (for left/right entry) as the entry anchor point. If the last waypoint is at (1050, 588) and the entry point is the left side at (1050, 707), the edge needs a horizontal segment from (1050, 588) to (1050, 588) then vertical to (1050, 707) — but drawio may render this as a diagonal if the waypoints don't include the corner. **Always include the corner waypoint** so every turn is an explicit right angle.

**Common defect**: fan-out edges that exit the source at different y-positions and enter targets at `entry={x:0, y:0.5}` (left side). The last waypoint's y rarely matches the target's left-center y. Fix: add a final waypoint at `(target_x, target_center_y)` so the last segment is a straight horizontal line into the left side.

S-bends are small S-shaped wiggles when source and target anchor points are nearly but not exactly aligned. Fix by adjusting anchor point fractions so connection points align exactly, or nudge the node by a few pixels.

Every edge between nodes in the same row must be a straight horizontal line. Every edge between nodes in the same column must be a straight vertical line. Cross-row connections should be clean L-bends (one turn), never S-bends.

### 8c. Minimize Bends — Exit Toward the Target

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

**Decision (rhombus) nodes — anchor only at the four vertices**: a diamond touches its bounding box solely at the edge-midpoints — top `(0.5, 0)`, bottom `(0.5, 1)`, left `(0, 0.5)`, right `(1, 0.5)`. These are the ONLY valid exit/entry points on a decision node. Any other fraction (e.g. `exitX=1, exitY=0.7`) lands in an empty corner of the bounding box, so the edge appears to start off the shape. Pick the vertex facing the other endpoint, and fan a decision node's branches across distinct vertices (e.g. default branch down, alternative branch right) rather than crowding one side.

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

### 8d. Edge Crossing Prevention

Edge crossings are a critical defect — second only to edges passing through nodes. The goal is ZERO crossings, not "minimized" crossings. Every crossing makes the diagram harder to follow.

**Prevention strategy** (apply in order):
1. **Separate corridors**: forward edges use the space between columns. Back-edges use the exterior margins (top or bottom).
2. **Choose the less crowded side**: back-edges route above (top) or below (bottom) the main flow — pick the side with fewer existing edges.
3. **Enter from the source side** (Rule 9a): right-side entry keeps back-edges entirely in the exterior corridor, away from all forward-flow edges.
4. **Stagger parallel back-edges**: when multiple back-edges share the exterior route, stagger their y positions (top-routing) or x positions (bottom-routing) by 15px.
5. **Reorder nodes vertically**: if two forward edges cross, swap the vertical positions of the target nodes to uncross them. This is always preferable to complex waypoint routing.

**Hub-spoke fan-out**: when one node (e.g., "config") fans out to 3+ targets stacked vertically, and those targets also connect to a shared service node, the service-bound edges will cross the fan-out edges unless you: (1) place the service node on the exterior (Rule 1 — shared service nodes), (2) route service edges through the exterior corridor (top or bottom), and (3) stagger the exit points on the fan-out source so inner targets use inner exit points and outer targets use outer exit points (Rule 8c nested ordering).

**Verification**: after laying out all edges, check every pair of edge segments for intersections. If any crossing exists, resolve it before proceeding to rendering. The `validate_layout.py` script flags crossings as errors.

### 8e. Edge-Node Clearance

Edges must maintain **15px** minimum clearance from any non-connected node. Fix by nudging the nearby node away (prefer moving nodes over adjusting edge routes — node moves are local and safe, edge route changes can cascade).

### 8f. Cascading Re-validation

Every node position change requires a full re-run of the validator. Moving a node to fix one issue can introduce S-bends on connected edges, new near-misses, or new crossings. Never move a node and assume the rest is still valid.

## Note: Draw.io Reserved Identifiers

The draw.io export CLI silently fails when a cell uses certain reserved identifiers. Known reserved IDs: `push`. Fix: append a suffix (e.g., `pushfb`, `push_node`, `push1`).

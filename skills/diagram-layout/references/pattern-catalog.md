# Pattern Catalog — Annotated Manual Diagram Examples

Real coordinate examples from 5 hand-crafted diagrams. Use these as reference when choosing positions.

## 1. eval-analyze — Pipeline with Conditional Branching

**Topology**: Pipeline with one decision fan-out (3 paths) and one validation loop.
**Canvas**: ~1600 x 600. Aspect ratio ~2.7:1.

### Column assignment (semantic, left-to-right)

| Column | x | Nodes | Role |
|--------|---|-------|------|
| 0 | 150 | /eval-analyze (110x120) | Entry |
| 1 | 300 | Find Skill (120x120) | Setup |
| 2 | 460 | Freshness Check (130x120) | Decision |
| 3 | 690 | Deep Skill Analysis (200x160), Dataset Exploration (200x120) | Processing |
| 4 | 960 | Generate eval.yaml (210x140) | Output |
| 4b | 1040 | Validate eval.yaml (130x100) | Validation |
| 5 | 1240 | Generate eval.md (150x130) | Output |
| 6 | 1450 | Report (130x120) | Final |

### Key pattern: Vertical stacking of alternatives

Deep Skill Analysis and Dataset Exploration are both at x=690 (same column), stacked vertically:
- Deep Skill Analysis: y=120 (top)
- Dataset Exploration: y=330 (bottom)
- Vertical gap: 330 - (120+160) = 50px

This creates a clear "parallel processing" visual. The fan-out source (Freshness Check at y=220) is vertically centered between them.

### Key pattern: Back-edge routed below

The "FRESH + COMPLETE" shortcut from Freshness Check to Report:
- Exits Freshness Check (x=460) downward
- Waypoints: (525, 550), (1410, 550), (1410, 320)
- Route y=550 is well below all nodes (lowest node bottom: 330+120=450)
- Clearance: 550 - 450 = 100px below lowest node

The validation error loop (Validate → Generate):
- Waypoint: (1015, 450) — routes below both nodes
- Short back-edge, just dips below the pair

### Key pattern: Node sizing scales with content

| Node | Content | Size |
|------|---------|------|
| /eval-analyze | title + 3 args | 110x120 |
| Freshness Check | title + 3 checks | 130x120 |
| Deep Skill Analysis | title + subtitle + 5 bullets | 200x160 |
| Validate eval.yaml | title + 3 items | 130x100 |

---

## 2. eval-dataset — Fan-out with Fallback Chains

**Topology**: Diamond — fan-out to 3 strategies, convergence at Generate Cases.
**Canvas**: ~1400 x 700. Aspect ratio ~2:1.

### Column assignment

| Column | x | Nodes |
|--------|---|-------|
| 0 | 50 | /eval-dataset (140x100) |
| 1 | 225 | Read Context (170x120), Parse Schema (170x120), No eval.yaml? (160x90) |
| 2 | 440 | Assess Current State (150x100) |
| 3 | 660 | Bootstrap (180x150), Expand (180x135), From Traces (180x140), MLflow Server (180x50) |
| 4 | 880 | Generate Cases (150x135) |
| 5 | 1070 | Validate (140x120) |
| 6 | 1250 | Report (150x120) |

### Key pattern: Three strategies stacked vertically at x=660

- Bootstrap: y=50 (top — default path)
- Expand: y=242 (middle — gap-filling path)
- From Traces: y=440 (bottom — production data extraction)
- MLflow Server: y=630 (external, below From Traces)

All at x=660. Vertical ordering follows priority: default first, fallback last.

Assess Current State (x=440, y=260) fans out to all three. Its center y=310 is between Bootstrap center (125) and From Traces center (510), creating a balanced visual spread.

### Key pattern: Fallback chain routing

From Traces has a "no traces fallback" back-edge to Expand:
- Waypoints: (785, 410), (785, 410) — a short loop-up on the right side
- This routes on the RIGHT side of the strategy column, not through the center

MLflow Server is below From Traces, connected with a short forward+back edge pair:
- From Traces → MLflow: waypoints (750, 610) — routes right side down
- MLflow → From Traces: waypoints (620, 655), (620, 510) — routes left side up
- This creates a small closed loop at the bottom of column 3

### Key pattern: Error/missing loop at column 1

No eval.yaml? (y=80) connects to Read Context (y=250) via back-edge:
- Waypoints: (190, 125), (190, 210), (260, 210), (260, 250)
- Routes on the LEFT side of column 1, using the margin space

---

## 3. eval-mlflow — Hub-and-Spoke with Central Server

**Topology**: Hub-spoke — /eval-mlflow fans out to 5 actions, all data flows through MLflow Server.
**Canvas**: ~1100 x 850. Aspect ratio ~1.3:1 (more square due to hub-spoke).

### Column assignment

| Column | x | Nodes |
|--------|---|-------|
| 0 | 60 | /eval-mlflow (120x110) |
| 1 | 360 | log-results container (550x130), from-traces (200x130), sync-dataset (200x120), pull-feedback (200x120), push-feedback (200x130) |
| 2 | 710-720 | Extracted Cases, eval/dataset/cases, MLflow Dataset, review.yaml, Trace Feedback |
| 3 | 930 | MLflow Server (160x60) |

### Key pattern: Shared trunk for fan-out edges

All 5 edges from /eval-mlflow (x=60, y=320) share a common trunk:
- Entry exits at x=180 (right side of entry node)
- All edges pass through waypoint (230, 375) — a shared junction point
- Then each edge diverges vertically to its target's y-position

This creates a clean tree-like branching pattern from a single point, not 5 separate edges crossing each other.

Waypoint routing from junction (230, 375):
- → log-results: (230, 110) — goes UP
- → from-traces: (230, 270) — goes up slightly
- → sync-dataset: (230, 430) — goes down slightly
- → push-feedback: (230, 705) — goes DOWN

The vertical ordering of actions minimizes crossings by matching the output positions.

### Key pattern: Actions stacked vertically at x=360

| Action | y | Connected output | Output x |
|--------|---|-----------------|----------|
| log-results | 40 | (container with 5 children) | — |
| from-traces | 205 | Extracted Cases at (710, 190) | 710 |
| sync-dataset | 370 | MLflow Dataset at (720, 405) | 720 |
| pull-feedback | 528 | review.yaml at (720, 590) | 720 |
| push-feedback | 690 | Trace Feedback at (720, 765) | 720 |

Each action has its output directly to its right at nearly the same y-position. This prevents edge crossings between actions and their outputs.

### Key pattern: Back-edges from MLflow Server

MLflow Server (930, 468) connects back to pull-feedback and from-traces:
- → pull-feedback: waypoints (620, 498), (620, 560), (560, 560) — routes LEFT below the main flow
- → from-traces: waypoints (1010, 270) — routes UP along the right edge, then left

The back-edge to from-traces routes around the RIGHT side. The back-edge to pull-feedback routes through the MIDDLE but below the forward edges.

### Key pattern: Callout detail boxes

Two filesystem callout boxes:
- eval/runs/{id}/ (590, 655, 120x110) — positioned below push-feedback
- eval/dataset/cases/ (710, 290, 150x80) — positioned between from-traces output and sync-dataset

Both are connected with dashed light edges and positioned in whitespace areas.

---

## 4. eval-review-optimize — Two Phased Containers with Feedback Loop

**Topology**: Two parallel pipelines (review + optimize) with feedback loops between them.
**Canvas**: ~1200 x 700. Aspect ratio ~1.7:1.

### Layout structure: Two horizontal containers

| Container | Position | Size | Color |
|-----------|----------|------|-------|
| /eval-review | (480, 30) | 690x160 | Blue stroke |
| /eval-optimize | (480, 410) | 690x180 | Green stroke |

Inputs on the left (Baseline at 230,73; /eval-run at 230,230; Run Results at 235,440).
Callout on the right (review.yaml at 715,230).

### Key pattern: Container children in a row

/eval-review children (all at similar y within container):
- Present: rel_x=20, rel_y=35 (81x88)
- Human Review: rel_x=132, rel_y=43 (112x71)
- Analyze Patterns: rel_x=274, rel_y=42 (132x74)
- Propose Changes: rel_x=446, rel_y=43 (112x71)
- Save: rel_x=589, rel_y=52 (81x53)

Arranged left-to-right, sequential pipeline within the container. Each child is ~130px apart.

### Key pattern: Back-edge routed around container exterior

The optimize loop (Check → Identify Failures):
- Check is at rel_x=520 within the container (absolute: ~1000)
- Identify Failures is at rel_x=20 (absolute: ~500)
- Waypoints: (596, 40), (92, 40), (92, 63) — routes ABOVE the container, across the top, then down to the first child
- This routes on the TOP side of the /eval-optimize container

The "update if improved" edge (Check → Baseline):
- Waypoints: (1076, 650), (180, 650), (180, 110)
- Routes BELOW the optimize container (y=650 > container bottom ~590), then up the left side
- U-shape: right side down, across bottom, left side up

### Key pattern: Cross-container back-edge

Re-run → /eval-run:
- Waypoints: (931, 620), (200, 620), (200, 295)
- Routes below the optimize container, left along the bottom, up to /eval-run on the left

All three back-edges use the diagram exterior (above, below, or sides) — never through the containers.

---

## General Principles Extracted

### Edge fan-out from a single node

When one node connects to 3+ targets, create a shared junction point:
1. Exit the source from its right side (or bottom for vertical layouts)
2. Move to a junction point 30-50px past the source
3. From the junction, branch vertically to each target's y-level
4. Then horizontally to each target

This produces a clean tree shape instead of a fan of diverging lines.

### Vertical ordering to minimize crossings

Order nodes vertically so that their connections don't cross:
- If node A connects to output at y=200 and node B connects to output at y=400, place A above B
- Match the vertical order of sources to the vertical order of targets

### Container internal layout

For sequential children:
- Arrange in a row (horizontal)
- Equal spacing between children (~110-140px apart)
- Children height slightly smaller than container height minus top padding
- Title goes in the container's top padding area

For parallel children:
- Arrange in columns within the container
- Equal widths

### Back-edge clearance values

From the examples:
- Below-diagram routing: 50-100px below lowest node
- Above-container routing: 20-30px above container top
- Side routing: 20-30px to left or right of outermost node
- Multiple back-edges: stagger by 25px

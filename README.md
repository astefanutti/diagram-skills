# Diagram Skills for Claude Code

Two [Claude Code skills](https://docs.anthropic.com/en/docs/claude-code/skills) for creating presentation-quality diagrams as draw.io files.

## Skills

### `/drawio` — Draw.io Diagram Generation

Generate draw.io diagrams as native `.drawio` files with optional export to PNG, SVG, or PDF. Handles draw.io CLI detection across macOS, Linux, Windows, and WSL2.

**Triggers on**: requests to create diagrams, flowcharts, architecture diagrams, ER diagrams, mockups, wireframes, or any mention of draw.io / `.drawio` files.

### `/diagram-layout` — Presentation-Quality Layout

Generate flow diagrams with manual-grade layout quality using LLM-driven coordinate assignment and visual iteration. Produces drawio files with clean edge routing, semantic grouping, and proper back-edge handling.

**Triggers on**: "layout diagram", "improve diagram layout", "presentation-quality diagram", or diagram requests that mention layout quality.

**Features**:
- Semantic column placement by node role
- Vertical stacking of fan-out alternatives
- Back-edge exterior routing with nested ordering
- Container grouping for sub-processes
- Programmatic validation (overlaps, crossings, clearance, bend detection)
- Visual iteration via sub-agent inspection

## Installation

Copy the skills to your Claude Code skills directory:

```bash
# Global (available in all projects)
cp -r skills/drawio ~/.claude/skills/drawio
cp -r skills/diagram-layout ~/.claude/skills/diagram-layout
```

### Dependencies

- **draw.io desktop app** — required for PNG/SVG/PDF export ([download](https://github.com/jgraph/drawio-desktop/releases))
- **Python 3** — for layout scripts
- **networkx** — for topology analysis (`pip install networkx`)

## Layout Rules

The diagram-layout skill encodes 13 layout rules in `skills/diagram-layout/prompts/layout-rules.md`:

| Rule | Purpose |
|------|---------|
| 1. Semantic columns | Assign nodes by role, not graph distance |
| 2. Vertical stacking | Fan-out alternatives at same x |
| 3. Back-edge exterior routing | Loops route around the diagram |
| 4. Container grouping | Related sub-steps in titled containers |
| 5. Callout detail boxes | Supplementary info in whitespace |
| 6. Aspect ratio | Canvas sized by topology class |
| 7. Edge labels | Conditional styling and label placement |
| 8. S-bend elimination | Align anchors to remove wiggles |
| 9. No edge through node | Absolute prohibition, the worst defect |
| 9a. Minimize bends | Exit toward target, nested fan-out |
| 10. Edge crossing minimization | Separate forward/back-edge corridors |
| 11. Cascading re-validation | Full re-score after node moves |
| 12. Edge-node clearance | 15px minimum tangent distance |
| 13. Reserved identifiers | Avoid draw.io reserved cell IDs |

## How It Works

1. **Parse** — D2, drawio, or natural language to normalized graph spec
2. **Analyze** — networkx topology (layers, fan-out, back-edges, topology class)
3. **Plan** — LLM assigns explicit (x, y, width, height) coordinates following the layout rules
4. **Render** — JSON layout plan to drawio XML
5. **Validate** — programmatic checks (overlaps, crossings, clearance, bends)
6. **Inspect** — sub-agent reads exported PNG and reports issues as text (images never enter main context)
7. **Iterate** — fix issues and re-render until clean

## License

MIT

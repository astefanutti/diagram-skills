# Diagram Layout Skill for Claude Code

A [Claude Code skill](https://docs.anthropic.com/en/docs/claude-code/skills) that generates presentation-quality draw.io diagrams with LLM-driven coordinate layout, programmatic validation, and visual iteration.

## `/diagram-layout`

Generate flow diagrams with manual-grade layout quality. Produces drawio files with clean edge routing, semantic grouping, and proper back-edge handling.

**Triggers on**: "layout diagram", "improve diagram layout", "presentation-quality diagram", or diagram requests that mention layout quality.

**Features**:
- Semantic column placement by node role
- Vertical stacking of fan-out alternatives
- Back-edge exterior routing with nested ordering
- Container grouping for sub-processes
- Programmatic validation (overlaps, crossings, clearance, bend detection)
- Visual iteration via sub-agent inspection (images never enter the main context)

## Installation

Install via a Claude Code plugin marketplace, or manually:

```bash
cp -r skills/diagram-layout ~/.claude/skills/diagram-layout
```

### Companion: `/drawio`

For quick diagram generation without the full layout pipeline, install the official [drawio skill](https://github.com/jgraph/drawio-mcp/tree/main/skill-cli) from jgraph. It handles draw.io XML generation and CLI export across all platforms.

> **Image isolation note**: when iterating on diagrams, always inspect exported PNGs via a sub-agent (Agent tool) — never read image files directly in the main context. Images accumulate across iterations and corrupt after context compaction. The `/diagram-layout` skill enforces this automatically.

### Dependencies

- **draw.io desktop app** — required for PNG/SVG/PDF export ([download](https://github.com/jgraph/drawio-desktop/releases))
- **Python 3** — for layout scripts
- **networkx** — for topology analysis (`pip install networkx`)

## Layout Rules

The skill encodes 13 layout rules in `skills/diagram-layout/prompts/layout-rules.md`:

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
| 9a. Minimize bends | Exit toward target, nested fan-out ordering |
| 10. Edge crossing minimization | Separate forward/back-edge corridors |
| 11. Cascading re-validation | Full re-score after any node move |
| 12. Edge-node clearance | 15px minimum tangent distance |
| 13. Reserved identifiers | Avoid draw.io reserved cell IDs |

## How It Works

1. **Parse** — D2, drawio, or natural language to normalized graph spec
2. **Analyze** — networkx topology (layers, fan-out, back-edges, topology class)
3. **Plan** — LLM assigns explicit (x, y, width, height) coordinates following the layout rules
4. **Render** — JSON layout plan to drawio XML
5. **Validate** — programmatic checks (overlaps, crossings, clearance, bends)
6. **Inspect** — sub-agent reads exported PNG and reports issues as text
7. **Iterate** — fix issues and re-render until clean

## License

MIT

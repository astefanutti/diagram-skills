# Diagram Skills for Claude Code

[Claude Code skills](https://docs.anthropic.com/en/docs/claude-code/skills) for creating presentation-quality flow diagrams.

## Skills

### `/skill-diagram` — Generate D2 from a Skill

Analyze a Claude Code skill directory and generate a D2 flow diagram capturing its workflow, decision branches, LLM steps, and external dependencies.

**Triggers on**: requests to visualize a skill's architecture, understand its flow, or create documentation diagrams from a skill directory.

**Options**:
- `--skill <path>` — skill directory to analyze
- `--output <path>` — output D2 file (default: `<skill-name>-flow.d2`)
- `--direction <right|down>` — flow direction (default: `right`)
- `--detail <high|low>` — bullet detail level (default: `high`)
- `--layout` — also run `/diagram-layout` on the result

### `/diagram-layout` — Presentation-Quality Layout

Take a D2 file (or natural language description) and produce a draw.io diagram with manual-grade layout quality.

**Triggers on**: "layout diagram", "improve diagram layout", "presentation-quality diagram", or diagram requests that mention layout quality.

**Features**:
- Semantic column placement by node role
- Vertical stacking of fan-out alternatives
- Back-edge exterior routing with nested ordering
- Container grouping for sub-processes
- Programmatic validation (overlaps, crossings, clearance, bend detection)
- Visual iteration via sub-agent inspection (images never enter the main context)

## Typical Pipeline

```
/skill-diagram --skill path/to/my-skill --layout
```

This analyzes the skill, generates a D2 flow diagram, and passes it through `/diagram-layout` for presentation-quality drawio output — all in one invocation.

Or step by step:
```
/skill-diagram --skill path/to/my-skill     # produces my-skill-flow.d2
# review and edit the D2 if needed
/diagram-layout --input my-skill-flow.d2     # produces my-skill-flow.drawio
```

## Installation

Install via a Claude Code plugin marketplace, or manually:

```bash
cp -r skills/skill-diagram ~/.claude/skills/skill-diagram
cp -r skills/diagram-layout ~/.claude/skills/diagram-layout
```

### Companion: `/drawio`

For quick one-off diagram generation without the layout pipeline, install the official [drawio skill](https://github.com/jgraph/drawio-mcp/tree/main/skill-cli) from jgraph.

> **Image isolation note**: when iterating on diagrams, always inspect exported PNGs via a sub-agent — never read image files directly in the main context. The `/diagram-layout` skill enforces this automatically.

### Dependencies

- **draw.io desktop app** — required for PNG/SVG/PDF export ([download](https://github.com/jgraph/drawio-desktop/releases))
- **Python 3** — for layout scripts
- **networkx** — for topology analysis (`pip install networkx`)

## Layout Rules

The diagram-layout skill encodes 13 rules in `skills/diagram-layout/prompts/layout-rules.md`:

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

## License

MIT

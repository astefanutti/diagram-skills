---
name: skill-diagram
description: Analyze a Claude Code skill and generate a D2 flow diagram of its workflow. Use when the user wants to visualize a skill's architecture, understand its flow, or create documentation diagrams from a skill directory.
---

# Skill Diagram

Analyze a Claude Code skill directory and generate a D2 flow diagram capturing its workflow, decision branches, LLM steps, and external dependencies.

## Arguments

- `--skill <path>` — path to skill directory (must contain SKILL.md). If omitted, prompt the user.
- `--output <path>` — output D2 file path (default: `<skill-name>-flow.d2` in the current directory)
- `--direction <right|down>` — flow direction (default: `right`)
- `--detail <high|low>` — `high` shows per-script bullets; `low` shows phase-level summaries (default: `high`)
- `--layout` — after generating D2, invoke `/diagram-layout` on the output

## Workflow

### Step 1: Read the Skill

Read the full contents of the skill directory:
1. `SKILL.md` — the primary source of workflow structure
2. `scripts/` — each script is a potential processing node; read docstrings, function names, and main() flow
3. `prompts/` — prompt files indicate LLM steps
4. `references/` — reference docs may reveal architectural context
5. Any other files (agents/, templates/, etc.)

Build a mental model of: what does this skill do, in what order, with what branches?

### Step 2: Analyze the Flow

Read `${CLAUDE_SKILL_DIR}/prompts/analysis-guide.md` for the extraction framework.

Identify:
- **Entry point**: skill name + CLI arguments
- **Sequential steps**: follow the numbered workflow in SKILL.md
- **Decision branches**: if/else conditions, strategy selection, conditional paths
- **LLM/agent steps**: anything using Agent tool, sub-agents, prompt files, or direct LLM calls
- **External dependencies**: other skills invoked (Skill tool), services (MLflow, APIs), external CLIs
- **Containers**: groups of related sub-steps that execute as a unit
- **Output artifacts**: files produced, reports generated, things opened
- **Back-edges**: validation→retry loops, feedback cycles, fallback paths

For each node, capture:
- A short title (2-4 words)
- 2-5 bullet points describing what happens (for `--detail high`)
- The node type: `entry`, `processing`, `llm`, `external`, `output`
- Connections to other nodes, with edge labels for conditions

### Step 3: Generate D2

Read `${CLAUDE_SKILL_DIR}/prompts/d2-conventions.md` for the style guide.

Generate a D2 file following these conventions:
1. Set `direction` per the `--direction` argument
2. Set global styles (border-radius, font-size, fill, stroke)
3. Declare nodes in flow order with markdown labels
4. Declare edges with conditions as labels
5. Use containers for grouped sub-steps
6. Use proper styles for each node type (LLM = double-border, external = dashed, etc.)

Write the D2 file to the `--output` path.

### Step 4: Output

Report to the user:
- Output file path
- Number of nodes and edges
- Any notable structural features (fan-out count, back-edges, containers)

If `--layout` was specified, invoke the `/diagram-layout` skill on the output D2 file:

```
Skill({ skill: "diagram-layout", args: "--input <d2-file>" })
```

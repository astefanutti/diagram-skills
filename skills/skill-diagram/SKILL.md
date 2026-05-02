---
name: skill-diagram
description: Analyze one or more Claude Code skills and generate a D2 flow diagram of their workflow. Use when the user wants to visualize a skill's architecture, understand its flow, create documentation diagrams, or show how multiple skills connect in a pipeline. Also trigger on "how does this skill work", "show me the flow", "what's the pipeline", "diagram this", "draw the workflow", or when the user is examining a SKILL.md and asks about understanding its structure.
---

# Skill Diagram

Analyze Claude Code skill directories and generate a D2 flow diagram capturing workflow, decision branches, LLM steps, external dependencies, and cross-skill connections.

## Arguments

- `--skill <path>` — path to skill directory (must contain SKILL.md). Repeat for multiple skills: `--skill <path1> --skill <path2>`. If omitted, prompt the user.
- `--output <path>` — output D2 file path (default: `<skill-name>-flow.d2` in the current directory)
- `--direction <right|down>` — flow direction (default: `right`)
- `--detail <high|low>` — `high` shows per-script bullets; `low` shows phase-level summaries (default: `high`). `low` also forces pipeline mode for multi-skill diagrams.
- `--layout` — after generating D2, invoke `/diagram-layout` on the output
- `--validate` — run `d2 fmt` on the output to check D2 syntax before reporting success

## Mode Selection (multi-skill)

When multiple `--skill` flags are provided, the diagram mode is selected automatically:

- **Detailed mode** (≤5 skills, or `--detail high`): each skill becomes a **container** with its internal workflow steps as child nodes. Cross-skill edges show shared data flows and Skill tool invocations between skills.
- **Pipeline mode** (>5 skills, or `--detail low`): each skill becomes a **single node** with a 3-5 bullet summary. Edges show the pipeline flow between skills with artifact names as labels. External services (MLflow, APIs) shared by multiple skills become separate nodes.

## Workflow

### Step 1: Read the Skill(s)

For each `--skill` path, read SKILL.md first — it's almost always sufficient for the flow structure. Only read `scripts/` if the SKILL.md references specific scripts by name (e.g., "run validate_eval.py") or if the workflow is too sparse to determine the flow from SKILL.md alone. Prompt and reference files rarely add nodes.

Build a mental model of: what does this skill do, in what order, with what branches?

For multi-skill diagrams, additionally scan each SKILL.md for:
- **Skill tool invocations**: references to other skills being invoked (these become cross-skill edges)
- **Shared artifacts**: files read/written by multiple skills (eval.yaml, SKILL.md, summary.yaml)
- **Shared services**: external services referenced by multiple skills (MLflow, APIs)

### Step 2: Analyze the Flow

Read `${CLAUDE_SKILL_DIR}/prompts/analysis-guide.md` for the extraction framework.

Run `python3 ${CLAUDE_SKILL_DIR}/scripts/extract_steps.py <SKILL.md>` to get a structured skeleton of steps and skill invocations. Use this as the starting point for your analysis — it catches step headings and skill references that are easy to miss in a long SKILL.md.

If the SKILL.md doesn't use `### Step N` headings, look for: numbered lists (`1. First`, `2. Second`), phase headings (`## Phase 1`), or a `## Workflow` section with prose. The extract_steps.py script handles the common patterns; for freeform prose, identify the sequence yourself from the narrative flow.

#### Single skill

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

#### Multi-skill (detailed mode, ≤5 skills)

Analyze each skill individually using the single-skill approach above. Then:
1. **Detect cross-skill edges**: which steps in skill A produce artifacts consumed by skill B? Which steps invoke other skills via the Skill tool?
2. **Identify shared resources**: config files, data stores, or services referenced by multiple skills
3. **Build the combined graph**: each skill is a container with its steps as children. Cross-skill edges connect specific steps across containers. Shared services become standalone external nodes.

#### Multi-skill (pipeline mode, >5 skills)

For each skill, extract:
- A 3-5 bullet summary of what the skill does
- Its role: `entry` (no upstream), `processing`, `output` (terminal), `external` (optional/side-channel)
- Which other skills it invokes or depends on

Then:
1. **Infer pipeline order**: skills with no upstream dependencies are entry points. Follow Skill tool invocations and artifact flows to determine the sequence.
2. **Detect feedback loops**: bidirectional dependencies (e.g., run ↔ review, run ↔ optimize)
3. **Identify external services**: services not in the skill list (MLflow, APIs) become separate external nodes with dashed borders
4. **Build a compact graph**: one node per skill, edges labeled with the primary data flow or invocation

### Step 3: Generate D2

Read `${CLAUDE_SKILL_DIR}/prompts/d2-conventions.md` for the style guide.

Generate a D2 file following these conventions:
1. Set `direction` per the `--direction` argument
2. Set global styles (border-radius, font-size, fill, stroke)
3. Declare nodes in flow order with markdown labels
4. Declare edges with conditions as labels
5. Use containers for grouped sub-steps (or for each skill in detailed multi-skill mode)
6. Use proper styles for each node type (LLM = double-border, external = dashed, etc.)

For multi-skill detailed mode: prefix node IDs with the skill name to avoid collisions (e.g., `review.step1`, `optimize.step1`). Use the skill name as the container label.

For multi-skill pipeline mode: use the skill name as the node ID.

Write the D2 file to the `--output` path.

If `--validate` was specified (or always, as a good practice), check the D2 syntax:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/validate_d2.py <output.d2>
```

If errors are found, fix them before proceeding.

### Step 4: Output

Report to the user:
- Output file path
- Number of skills, nodes, and edges
- Mode used (single/detailed/pipeline)
- Any notable structural features (cross-skill edges, feedback loops, external services)

If `--layout` was specified, invoke the `/diagram-layout` skill on the output D2 file:

```
Skill({ skill: "diagram-layout", args: "--input <d2-file>" })
```

If `/diagram-layout` fails or times out, the D2 file is still useful — it can be rendered directly with `d2 --layout elk <file>.d2 <file>.svg`. Report this to the user with the D2 file path as a fallback.

# Skill Analysis Guide

How to extract a flow diagram from a Claude Code skill directory.

## Reading Order

1. **SKILL.md** — the primary source. Read it fully. The workflow section defines the step sequence.
2. **scripts/** — each script often maps to one node. Read docstrings and `main()` to understand purpose.
3. **prompts/** — each prompt file indicates an LLM step. The filename hints at purpose.
4. **references/** — background docs that may clarify architecture but rarely add nodes.
5. **agents/** — sub-agent definitions indicate LLM delegation steps.

## Extraction Framework

### 1. Entry Point

Always the first node. Extract from SKILL.md:
- Skill name (from frontmatter `name` field or the `# Title`)
- CLI arguments (from an `## Arguments` section, or inferred from the workflow)
- The entry node uses the skill's invocation name: `/eval-run`, `/diagram-layout`, etc.

### 2. Sequential Steps

Follow the numbered workflow in SKILL.md (e.g., "### Step 1", "### Step 2"). Each step becomes a node unless it's trivially small (a single line that's part of a larger step).

**Merging**: if two consecutive steps are tightly coupled (e.g., "read file" then "parse file"), merge them into one node with combined bullets.

**Splitting**: if one step contains distinct sub-operations (e.g., "validate, then score, then report"), split into separate nodes.

### 3. Decision Branches

Look for:
- Explicit conditions: "if X, do A; otherwise do B"
- Strategy selection: "choose between bootstrap, expand, or from-traces"
- Optional steps: "if `--flag` is set, also do X"
- Error paths: "if validation fails, retry"

Map each branch to an edge with a label describing the condition. Short labels work best: `"< 5 cases"`, `"errors"`, `"--update"`, `"missing"`.

### 4. LLM / Agent Steps

Identify nodes that use LLM capabilities:
- Direct LLM calls or prompt files in `prompts/`
- Agent tool invocations (sub-agents, Explore agents)
- Prompt-based generation or analysis
- Judge/evaluation steps that use LLM scoring

These get `style.double-border: true` and `style.fill: "#e8e8e8"`. Add "LLM" or "agent" to the subtitle if helpful.

### 5. External Dependencies

Things outside the skill that it calls or depends on:
- Other skills invoked via the Skill tool
- External services (MLflow, APIs, databases)
- CLI tools (draw.io, d2, git)
- Other processes (servers, background tasks)

These get `style.stroke-dash: 3` (dashed border).

### 6. Containers

Group related sub-steps when:
- A step has 3+ internal sub-operations that are worth showing individually
- The sub-steps share a title/phase name (e.g., "Scoring" contains inline/LLM/external)
- The grouping clarifies the architecture

Use D2 nested blocks. Container children are simpler nodes (shorter labels, fewer bullets).

### 7. Output Artifacts

The final step(s) that produce results:
- Files written (summary.yaml, report.html, etc.)
- Reports displayed or opened
- Data pushed to external systems

### 8. Back-Edges

Loops and retry patterns:
- Validation → retry on failure
- Iteration loops (generate → check → adjust)
- Feedback cycles (push → pull)

Use `style.stroke-dash: 3` on the edge. Add a short label: `"errors"`, `"retry"`, `"iterate"`.

## Deciding Granularity

**Too few nodes** (3-4): the diagram doesn't convey workflow structure. Split major steps.

**Too many nodes** (15+): the diagram becomes a wall of boxes. Merge trivial steps, use containers.

**Sweet spot** (7-12 nodes): enough to show the flow without overwhelming.

**Rule of thumb**: if a step takes more than 2 bullets to describe and involves a distinct operation (reading, computing, writing, deciding), it deserves its own node.

## Naming Nodes

- Use the function/script name when one exists: `validate`, `score`, `collect`
- Use the action verb when no script: `read-config`, `find-dataset`, `gen-yaml`
- Prefix with the phase if disambiguation is needed: `pre-validate`, `post-collect`
- Avoid generic names: `process`, `handle`, `do-stuff`

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

### 6. Containers for Composite Subsystems

Group related sub-steps into containers when:
- A step has 3+ internal variants or sub-modes the reader would benefit from seeing individually
- The sub-steps share a title/phase name (e.g., "Scoring" contains inline/LLM/external)
- The grouping clarifies the architecture — showing that these are components of one subsystem, not independent steps

**Common container patterns in skills:**
- **Scoring/judging systems**: multiple judge types (inline, LLM, pairwise, external) as children of a "Score" container
- **Tool/hook systems**: multiple interceptors (AskUserQuestion, Bash, MCP tools) as children of a "Tool Interception" container
- **Execution with mode variants**: case mode, batch mode, and the headless runner as children of an "Execute Skill" container. This is always a container — it's the core of any evaluation skill.
- **Multi-format output**: multiple output artifacts grouped under a "Report" container

Use D2 nested blocks. Container children are simpler nodes (shorter labels, fewer bullets). The container itself has just a title.

**Anti-pattern**: collapsing a composite subsystem into a single flat node with many bullets. If you find yourself writing 6+ bullets for one node, it probably should be a container with children.

**In-container annotations**: containers can include short annotation text that explains the mechanism, not just the children. Examples: "answers.yaml + input.yaml = LLM context" inside a Tool Interception container, "conditional if/host + skip judge per case" near a Score container. These explain HOW the subsystem works, complementing the children which show WHAT it contains.

### 6a. Mode Branching

When a step has distinct execution modes, show them as alternative sub-nodes rather than collapsing into one box. Look for:
- If/else on mode flags (e.g., `case` mode vs `batch` mode)
- Distinct code paths triggered by arguments (e.g., `--strategy bootstrap` vs `--strategy expand`)
- Different argument handling or data flow per mode

Model these as fan-out alternatives at the same column, stacked vertically, with edge labels naming the mode. The viewer should see at a glance that there are N distinct paths.

### 6b. Callout Detail Boxes

Generate callout boxes for concrete examples that ground abstract steps in tangible detail. Look for:
- **File trees** created by scripts (e.g., workspace directory structure)
- **Config snippets** documented in SKILL.md or references (e.g., eval.yaml structure)
- **YAML/JSON structures** that are central to the skill's data model

Callout boxes connect to their anchor node with a dashed line and sit in whitespace near it. They use monospace font, left-aligned text, and a light border. They make the diagram more useful as a reference doc — without them, the diagram stays abstract.

**Quality bar for callouts**: read the actual script that creates the structure (e.g., `workspace.py`) to extract the real directory tree, not an approximation. Include inline annotations explaining each file's purpose (e.g., `settings.json  ← perms + hooks`, `hooks.py  ← PreToolUse`, `batch.yaml  ← batch mode`). Show nesting accurately. A skeletal callout with wrong paths is worse than no callout.

### 7. Output Artifacts

The final step(s) that produce results:
- Files written (summary.yaml, report.html, etc.)
- Reports displayed or opened
- Data pushed to external systems

### 8. Data-Flow Edge Labels

Beyond condition labels ("missing", "< 5 cases"), label edges with what data flows through them. This makes the diagram informative — the reader can trace what artifacts move between steps.

Look for:
- Files passed between steps: "summary.yaml", "tool_handlers.yaml", "batch.yaml"
- Data structures: "answers.yaml + input.yaml = LLM context"
- Decisions: "allow / deny per tool call"
- Return values: "run_result.json", "collection.json"

**Rule**: if a step produces a named artifact that the next step consumes, label the edge with that artifact name. If the relationship is just "A then B" with no specific data handoff, leave the edge unlabeled.

### 9. Upstream and Downstream Skills

Always check if the skill invokes other skills via the Skill tool (look for `Skill tool`, `invoke /skill-name`, or `Use the Skill tool`). Show these as:
- **Dashed-border external nodes** connected to the step that invokes them
- Edge labels describing the trigger condition ("missing config", "no cases", "optional")

Also check the skill's suggested "next steps" — these are downstream skills that complete the pipeline. Show them at the end with dashed optional edges.

This provides pipeline context — the reader sees not just what the skill does, but where it fits in the larger workflow.

### 10. Back-Edges

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

**Over-splitting warning**: don't split tightly-coupled terminal steps into separate nodes. "Interpret results" and "generate report" are one step — the analysis feeds directly into the report with no branching or decision between them. Splitting them adds a node without adding clarity. Merge into a single "Report" node that mentions both analysis and HTML generation.

## Naming Nodes

- Use the function/script name when one exists: `validate`, `score`, `collect`
- Use the action verb when no script: `read-config`, `find-dataset`, `gen-yaml`
- Prefix with the phase if disambiguation is needed: `pre-validate`, `post-collect`
- Avoid generic names: `process`, `handle`, `do-stuff`

# Skill Analysis Guide

How to extract a flow diagram from a Claude Code skill directory.

## Detail Floor (non-negotiables)

A `--detail high` single-skill diagram is under-detailed — and reads as a
generic outline rather than a useful reference — unless it clears ALL of these.
Treat them as the acceptance bar, not aspirations:

- **≥1 callout detail box** grounding the skill in concrete structure — above all
  the **primary output artifact's** schema/fields, plus any central file tree or
  config snippet (§6b). Read the actual script that writes it; do not approximate.
- **Data-flow edge labels**: name the artifact that flows between steps
  (`summary.yaml`, `collection.json`) on ≥1 edge (§8), not just conditions.
- **Composite subsystems as containers** (§6), nested where a member is itself
  multi-step — never collapse a multi-variant step into one flat node.
- **Decision branches and back-edges preserved** — mode branches (§6a), retry
  loops, and cache/fast-path short-circuits are structure, not noise.
- **~10-16 boxes** for a rich skill (see "Deciding Granularity"), with 2-5
  concrete bullets per node (real script/flag/file names, not generic verbs).

`scripts/validate_d2.py` emits advisory `detail_warnings` for the first three.
The rest of this guide explains how to satisfy each.

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
- The entry node uses the skill's invocation name: `/build`, `/deploy`, etc.

### 2. Sequential Steps

Follow the numbered workflow in SKILL.md (e.g., "### Step 1", "### Step 2"). Each step becomes a node unless it's trivially small (a single line that's part of a larger step).

**Merging**: if two consecutive steps are tightly coupled (e.g., "read file" then "parse file"), merge them into one node with combined bullets.

**Splitting**: if one step contains distinct sub-operations (e.g., "validate, then score, then report"), split into separate nodes.

### 3. Decision Branches

Look for:
- Explicit conditions: "if X, do A; otherwise do B"
- Strategy selection: "choose between fast, full, or incremental"
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

### 5. External Dependencies and Integration Points

Things outside the skill that it calls or depends on:
- Other skills invoked via the Skill tool
- External services (databases, APIs, message queues)
- CLI tools (draw.io, d2, git)
- Other processes (servers, background tasks)

These get `style.stroke-dash: 3` (dashed border).

**Always surface integration points**: if the skill connects to an external service (database, API endpoint, message broker), show it as a separate dashed-border node even if the skill treats it as incidental. Integration points are high-value information for readers — they show where the skill crosses system boundaries. Look for: environment variable checks, server URLs, API client initialization, health checks.

**Granularity for external nodes**: show services and skills, not scripts. A script like `fetch_records.py` is an implementation detail — the reader cares that the skill "pulls records from the database", not which Python file does it. External nodes should be at the same abstraction level as the workflow steps: services (a Database), skills (/test), or CLI tools (draw.io) — never individual script files.

### 6. Containers for Composite Subsystems

Group related sub-steps into containers when:
- A step has 3+ internal variants or sub-modes the reader would benefit from seeing individually
- The sub-steps share a title/phase name (e.g., "Scoring" contains inline/LLM/external)
- The grouping clarifies the architecture — showing that these are components of one subsystem, not independent steps
- **Operations on the same resource**: when multiple steps all act on the same entity (e.g., several operations that all read/write the same database or service), group them in a container named after the resource. Compare with the gold standard if available — if it groups operations, your diagram should too.

**Common container patterns in skills.** These patterns produce better diagrams because they show internal structure that a single flat node hides. When a skill matches one of these patterns, the container version is almost always clearer:
- **Scoring/judging systems**: multiple judge types (inline, LLM, pairwise, external) → "Score" container
- **Tool/hook systems**: multiple interceptors (AskUserQuestion, Bash, MCP tools) → "Tool Interception" container
- **Execution with mode variants**: case mode, batch mode, headless runner → "Execute" container
- **Configuration/setup groups**: multiple config steps (credentials, env vars, directories) → "Configuration" container
- **Multi-format output**: multiple output artifacts → "Report" container

Use D2 nested blocks. Container children are usually simpler nodes (shorter labels, fewer bullets), and the container itself has just a title.

**Exception — keep a composite member nested, don't flatten it.** Grouping operations on a shared resource must NOT erase the internal structure of an operation that has its own. If a grouped member is itself a multi-step process (e.g. a "sync" operation that reads a schema, generates a mapping, then runs the sync), author it as its **own sub-container** with those steps as children — a nested container — not a single node with the steps reduced to bullets. Containers nest; only flatten members that are genuinely single steps. (This is the common failure: grouping four same-resource operations into one container and collapsing each — including a 3-step one — into a flat node, losing the detail the reader needs.)

**Anti-pattern**: collapsing a composite subsystem into a single flat node with many bullets — whether it's top-level OR a member of a larger group. If you find yourself writing distinct sequential sub-steps as 4+ bullets for one node, it should be a (possibly nested) container with children.

**In-container annotations**: containers can include short annotation text that explains the mechanism, not just the children. Examples: "answers.yaml + input.yaml = LLM context" inside a Tool Interception container, "conditional if/host + skip judge per case" near a Score container. These explain HOW the subsystem works, complementing the children which show WHAT it contains.

### 6a. Mode Branching

When a step has distinct execution modes, show them as alternative sub-nodes rather than collapsing into one box. Look for:
- If/else on mode flags (e.g., `case` mode vs `batch` mode)
- Distinct code paths triggered by arguments (e.g., `--strategy fast` vs `--strategy full`)
- Different argument handling or data flow per mode

Model these as fan-out alternatives at the same column, stacked vertically, with edge labels naming the mode. The viewer should see at a glance that there are N distinct paths.

### 6b. Callout Detail Boxes

Generate callout boxes for concrete examples that ground abstract steps in tangible detail. Look for:
- **Primary output artifacts**: the skill's main output file (e.g., `config.yaml`, `results.yaml`, `report.yaml`) deserves a callout showing its structure — key fields, nesting, what each section contains. These are the most valuable callouts because they show the reader what the skill actually produces.
- **File trees** created by scripts (e.g., workspace directory structure)
- **Config snippets** documented in SKILL.md or references (e.g., config.yaml structure)
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

**Fan-out deduplication**: when one step fans out to N downstream steps and the same artifact flows to all of them (e.g., a build step produces results.yaml consumed by publish, review, and deploy), do NOT repeat the artifact name on every fan-out edge. Instead, attach the artifact as a callout box to the source node, and leave the fan-out edges unlabeled or labeled with the specific action each target takes. Repeated identical labels on fan-out edges create visual clutter and waste space.

**Most skills have data-flow labels** — look harder if you find none. Common artifacts that flow between steps: config files (`config.yaml`, `settings.json`), output files (`results.yaml`, `report.html`, `collection.json`), data structures (`run_result.json`, `graph-spec.json`), and log files (`stdout.log`). The edge_quality judge checks for at least one data-flow label with a file extension in diagrams with ≥8 edges.

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

## Multi-Skill Analysis

When diagramming multiple skills together, apply the single-skill extraction to each, then perform cross-skill analysis.

### Cross-Skill Edge Detection

Scan each skill's SKILL.md and scripts for references to other skills in the set:
- **Skill tool invocations**: `Skill({ skill: "test" })` or "invoke /test" — these are direct edges
- **Shared artifacts**: files written by one skill and read by another (e.g., skill A writes `results.yaml`, skill B reads it)
- **Shared config**: files like `config.yaml` that multiple skills read or modify
- **Suggested next steps**: many skills end with "suggest /deploy or /review" — these are downstream pipeline edges

### Pipeline Order Inference

1. Skills with no upstream dependencies are **entry points** (e.g., `/setup`)
2. Follow Skill tool invocations and artifact flows to determine the sequence
3. Skills that are invoked by others but invoke nothing are **terminal** (e.g., `/review`)
4. Bidirectional dependencies indicate **feedback loops** (e.g., `/test` ↔ `/deploy`)

**Fan-out detection is critical.** When a skill invokes or feeds into multiple downstream skills, show ALL downstream connections as a fan-out — not a linear chain. A linear chain `A → B → C` means B must complete before C starts. A fan-out `A → B` and `A → C` means both B and C are downstream of A independently.

Concrete example: `/test` feeds into three downstream skills:
- `/test → /publish` (log results)
- `/test → /review` (human sign-off)
- `/test → /deploy` (automated promotion)

These are three separate edges from /test, not a chain `/test → /publish → /review → /deploy`. Missing a fan-out is a structural error — it misrepresents the pipeline topology.

How to detect: scan each skill's "Next Steps", "Suggest", or final step for references to other skills. If a skill suggests 3 downstream skills, it has fan-out degree 3.

### External Service Detection

Services referenced by multiple skills but not in the skill list become shared external nodes:
- A database (referenced by /setup, /publish, /test)
- APIs, message queues, or CLI tools used across skills

These get a single dashed-border node with edges from each referencing skill.

### Mode Selection

- **Detailed mode** (≤5 skills): one D2 container per skill with internal steps as children. Cross-skill edges connect specific steps (e.g., `review.save-feedback -> deploy.identify-failures: "feedback.yaml"`). Node IDs are prefixed with the skill name to avoid collisions.
- **Pipeline mode** (>5 skills): one node per skill with 3-5 bullet summary. Edges show primary data flow between skills. No internal steps visible — the diagram shows orchestration, not implementation.

### Granularity in Pipeline Mode

In pipeline mode, each skill collapses to a single node. The node label should capture:
- The skill's invocation name (bold)
- 3-5 bullets describing what it does (the key actions, not the implementation)
- The node type based on the skill's overall character (entry, processing, external, output)

Aim for 7-12 total nodes including external services. If the pipeline has 15+ skills, group related skills into containers (e.g., "Data Preparation" containing fetch + validate + transform).

# D2 Conventions for Skill Flow Diagrams

## Global Setup

Every diagram starts with:

```d2
direction: right

*.style.border-radius: 8
*.style.font-size: 13
*.style.fill: "#f5f5f5"
*.style.stroke: "#333333"
```

**Default to `direction: right`** — diagrams read best in landscape, and it keeps a plugin's diagrams visually consistent. A long sequential pipeline is NOT a reason to switch to `direction: down`: that produces a tall, hard-to-read vertical strip. Keep `direction: right` and let the layout step wrap a long chain into stacked rows. Reserve `direction: down` for the rare diagram whose source genuinely models a top-to-bottom flow.

## Node Types and Styles

### Entry Node

The skill invocation. Bold name, CLI args as bullets.

```d2
entry: |md
  **/skill-name**

  - --arg1
  - --arg2
  - --arg3
| {
  shape: rectangle
  style.fill: "#f5f5f5"
  style.stroke: "#333333"
  style.stroke-width: 2
}
```

### Processing Node

Standard workflow step. Bold title, action bullets.

```d2
load-config: |md
  **Load Config**

  - config.yaml
  - validate inputs, schema
  - resolve dependencies
| {
  shape: rectangle
  style.fill: "#f5f5f5"
  style.stroke: "#333333"
  style.stroke-width: 2
}
```

### LLM / Agent Node

Steps that use LLM calls, agents, or prompts. Darker fill, double-border.

```d2
skill-analysis: |md
  **Deep Skill Analysis**
  LLM agent (Explore)

  - read SKILL.md
  - follow sub-skill chains
  - identify I/O, pipeline
  - suggest judges
| {
  shape: rectangle
  style.fill: "#e8e8e8"
  style.stroke: "#333333"
  style.stroke-width: 2
  style.double-border: true
}
```

### External Service / Dependency

Services, other skills, external CLIs. Dashed border.

```d2
database: |md
  **Database**
| {
  shape: rectangle
  style.fill: "#f5f5f5"
  style.stroke: "#333333"
  style.stroke-width: 2
  style.stroke-dash: 3
}
```

### Output / Report Node

Final output step. Standard fill, lists what's produced.

```d2
report: |md
  **Report**

  - summary.yaml
  - report.html
  - open in browser
| {
  shape: rectangle
  style.fill: "#f5f5f5"
  style.stroke: "#333333"
  style.stroke-width: 2
}
```

### Container

Groups related sub-steps. Children are nested D2 blocks.

```d2
scoring: Score {
  style.fill: "#ececec"
  style.stroke: "#333333"
  style.stroke-width: 2

  inline: "Inline Checks\nPython scripts"
  llm-judge: "LLM Judge\nprompt evaluation"
  external: "External\nmodule/function"
}
```

### Multi-Skill Container (detailed mode)

When diagramming ≤5 skills in detailed mode, each skill becomes a container. Prefix child node IDs with the skill name to avoid collisions. Cross-skill edges connect specific steps.

```d2
review: "review" {
  style.fill: "#ececec"
  style.stroke: "#333333"
  style.stroke-width: 2

  review.load: |md
    **Load Results**

    - results.yaml
    - config.yaml context
  |
  review.walk: |md
    **Walk Items**

    - present results
    - collect feedback
  |
  review.save: |md
    **Save Feedback**

    - feedback.yaml
  |
  review.load -> review.walk
  review.walk -> review.save
}

deploy: "deploy" {
  style.fill: "#ececec"
  style.stroke: "#333333"
  style.stroke-width: 2

  deploy.failures: |md
    **Identify Failures**

    - failure map
    - read feedback.yaml
  |
  deploy.edit: |md
    **Apply Fixes**

    - targeted config changes
  |
  deploy.failures -> deploy.edit
}

# Cross-skill edge
review.save -> deploy.failures: "feedback.yaml"
```

### Callout Detail Box

Concrete example grounding an abstract step (file tree, config snippet, YAML structure). Light border, monospace, connected by dashed line.

```d2
workspace-tree: |md
  /tmp/agent-eval/{id}/
  case-001/
    input.yaml
    answers.yaml
  settings.json
  CLAUDE.md
  hooks.py
  tool_handlers.yaml
  batch.yaml
| {
  shape: rectangle
  style.fill: "#f5f5f5"
  style.stroke: "#bbbbbb"
  style.stroke-width: 1
  style.font: mono
  style.font-size: 10
}

workspace -> workspace-tree: {
  style.stroke: "#bbbbbb"
  style.stroke-dash: 4
  style.stroke-width: 1
}
```

## Edge Types

### Forward Edge (default)

```d2
load-config -> find-dataset
```

### Data-Flow Edge

Label with the artifact or data that flows between steps.

```d2
scoring -> analyze: "summary.yaml"
collect -> scoring: "collection.json"
hooks -> execute: "allow / deny\nper tool call"
```

### Conditional / Branch Edge

Label with the condition that selects this branch.

```d2
assess -> fast: "< 5 items"
assess -> full: "gaps found"
assess -> incremental: "--strategy\nincremental"
```

### Optional / Fallback Edge

Dashed styling for optional paths, fallbacks, or "if not found" branches.

```d2
report -> database: optional {
  style.stroke-dash: 3
}
```

### Back-Edge (Loop / Retry)

Dashed styling for loops, validation retries, feedback cycles.

```d2
validate -> gen-yaml: errors {
  style.stroke-dash: 3
}
```

## Node ID Conventions

- Lowercase with hyphens: `load-config`, `find-dataset`, `gen-yaml`
- Short and descriptive: prefer `assess` over `assess-current-state`
- Avoid D2 reserved words and draw.io reserved IDs (e.g., `push`)
- Containers use the group name: `scoring`, `workers`

## Label Detail Levels

### High Detail (default)

Each node gets 2-5 bullets describing the specific actions:

```d2
workspace: |md
  **Prepare Workspace**

  - /tmp/agent-eval/{id}
  - copy inputs, symlinks
  - .claude/settings.json
  - permissions + hooks
  - case or batch mode
|
```

### Low Detail

Each node gets just the title and a one-line summary:

```d2
workspace: |md
  **Prepare Workspace**

  set up execution environment
|
```

## Layout Hints

- Declare nodes in the order they appear in the flow — the dagre layout engine uses declaration order as a hint for vertical positioning. The ELK engine (used for report SVG rendering) uses its own algorithm and may order differently — write clear edge declarations to guide layout rather than relying on declaration order alone.
- When a node fans out to multiple alternatives, declare the alternatives in top-to-bottom order (primary first, fallback last)
- Keep edge declarations after all node declarations, grouped by phase
- Use comments (`#`) to separate phases/sections

## Pipeline Fan-Out Example

In pipeline mode (>5 skills), show fan-out as separate edges from one source to multiple targets — NOT a linear chain:

```d2
# Correct: fan-out from one source
test -> publish: "log results"
test -> review: "human sign-off"
test -> deploy: "auto-promote"
```

```d2
# Wrong: linear chain misrepresents the topology
test -> publish -> review -> deploy
```

## Complete Example

A representative example exercising all conventions (a generic data-processing
flow — entry, config, an assessment, a strategy fan-out, generation, report):

```d2
direction: right

*.style.border-radius: 8
*.style.font-size: 13
*.style.fill: "#f5f5f5"
*.style.stroke: "#333333"

# --- Entry ---

args: |md
  **/process**

  - --count N
  - --strategy
  - --config
| {
  shape: rectangle
  style.fill: "#f5f5f5"
  style.stroke: "#333333"
  style.stroke-width: 2
}

# --- Config ---

read-config: |md
  **Read Context**

  - config.yaml (schema,
    rules, execution)
  - spec.md (analysis)
| {
  shape: rectangle
  style.fill: "#f5f5f5"
  style.stroke: "#333333"
  style.stroke-width: 2
}

# --- Assessment ---

assess: |md
  **Assess Input**

  - count existing items
  - read a sample
  - identify coverage
| {
  shape: rectangle
  style.fill: "#f5f5f5"
  style.stroke: "#333333"
  style.stroke-width: 2
}

# --- Strategies (fan-out) ---

fast: |md
  **Fast**
  (default, < 5 items)

  - 1 simple item
  - 1 complex item
  - 1 edge item
| {
  shape: rectangle
  style.fill: "#e8e8e8"
  style.stroke: "#333333"
  style.stroke-width: 2
  style.double-border: true
}

full: |md
  **Full**
  (fill coverage gaps)

  - read existing items
  - compare vs rules
  - generate gap-filling
| {
  shape: rectangle
  style.fill: "#e8e8e8"
  style.stroke: "#333333"
  style.stroke-width: 2
  style.double-border: true
}

# --- Output ---

generate: |md
  **Generate Output**

  - item-NNN-slug/
  - input.yaml
  - reference.md
| {
  shape: rectangle
  style.fill: "#f5f5f5"
  style.stroke: "#333333"
  style.stroke-width: 2
}

report: |md
  **Report**

  - N items generated
  - next: /test
| {
  shape: rectangle
  style.fill: "#f5f5f5"
  style.stroke: "#333333"
  style.stroke-width: 2
}

# --- Flow ---

args -> read-config
read-config -> assess

assess -> fast: "< 5 items"
assess -> full: "gaps found"

fast -> generate
full -> generate

generate -> report
```

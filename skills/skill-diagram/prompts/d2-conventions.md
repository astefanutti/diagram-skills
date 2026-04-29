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

Use `direction: down` only when the flow is primarily vertical (many sequential steps, few branches).

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

  - eval.yaml
  - validate skill, dataset
  - resolve models
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
mlflow: |md
  **MLflow Server**
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
assess -> bootstrap: "< 5 cases"
assess -> expand: "gaps found"
assess -> from-traces: "--strategy\nfrom-traces"
```

### Optional / Fallback Edge

Dashed styling for optional paths, fallbacks, or "if not found" branches.

```d2
report -> mlflow: optional {
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
- Containers use the group name: `scoring`, `logresults`

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

- Declare nodes in the order they appear in the flow — D2 layout engines use declaration order as a hint for vertical positioning
- When a node fans out to multiple alternatives, declare the alternatives in top-to-bottom order (primary first, fallback last)
- Keep edge declarations after all node declarations, grouped by phase
- Use comments (`#`) to separate phases/sections

## Complete Example

See the eval-dataset diagram as a representative example of all conventions:

```d2
direction: right

*.style.border-radius: 8
*.style.font-size: 13
*.style.fill: "#f5f5f5"
*.style.stroke: "#333333"

# --- Entry ---

args: |md
  **/eval-dataset**

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

  - eval.yaml (schema,
    judges, execution)
  - eval.md (skill analysis)
| {
  shape: rectangle
  style.fill: "#f5f5f5"
  style.stroke: "#333333"
  style.stroke-width: 2
}

# --- Assessment ---

assess: |md
  **Assess Current State**

  - count existing cases
  - read sample case
  - identify coverage
| {
  shape: rectangle
  style.fill: "#f5f5f5"
  style.stroke: "#333333"
  style.stroke-width: 2
}

# --- Strategies (fan-out) ---

bootstrap: |md
  **Bootstrap**
  (default, < 5 cases)

  - 1 simple case
  - 1 complex case
  - 1 edge case
| {
  shape: rectangle
  style.fill: "#e8e8e8"
  style.stroke: "#333333"
  style.stroke-width: 2
  style.double-border: true
}

expand: |md
  **Expand**
  (fill coverage gaps)

  - read existing cases
  - compare vs judges
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
  **Generate Cases**

  - case-NNN-slug/
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

  - N cases generated
  - next: /eval-run
| {
  shape: rectangle
  style.fill: "#f5f5f5"
  style.stroke: "#333333"
  style.stroke-width: 2
}

# --- Flow ---

args -> read-config
read-config -> assess

assess -> bootstrap: "< 5 cases"
assess -> expand: "gaps found"

bootstrap -> generate
expand -> generate

generate -> report
```

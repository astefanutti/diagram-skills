# Expected Diagram: eval-dataset Skill Flow

## Overview

The eval-dataset skill generates evaluation test cases for a skill. It reads the skill analysis and eval config, parses the dataset schema into a generation template, assesses current state, chooses a strategy, generates cases, validates them, and reports. The diagram should show a 7-step pipeline with a strategy branching point.

## Expected Nodes

### Top-Level Steps (main flow)

- **Step 0: Parse Arguments** -- Parse `--config`, `--count`, `--strategy` flags.
- **Step 1: Read Context** -- Read eval.yaml and eval.md. Extract: skill purpose, execution mode, dataset schema, output schema, judge criteria. Build list of judge-driven requirements. If eval.yaml missing, invoke `/eval-analyze` via Skill tool.
- **Step 2: Parse Schema into Template** -- Extract from `dataset.schema`: required files, required fields per file, optional fields, field semantics, naming patterns, argument field placeholders from `execution.arguments`.
- **Step 3: Assess Current State** -- List existing cases, count them, read one sample, identify coverage gaps.
- **Step 4: Choose Strategy** -- Branch into one of three strategies based on `--strategy` flag and current state.
- **Step 5: Generate Cases** -- Create case directories with input.yaml, optional answers.yaml, optional annotations.yaml, optional companion files. Follow naming convention `case-NNN-description/`.
- **Step 6: Validate** -- Read back a generated case, check file counts match schema, verify argument placeholders present in input.yaml, check for empty/placeholder content.
- **Step 7: Report** -- Summarize: cases generated, strategy used, coverage, gaps, next steps.

### Strategy Branches (children of Step 4)

- **Bootstrap** -- Generate N cases from scratch. Design: 1 simple, 1 complex, 1 edge case, remaining mapped to judge criteria.
- **Expand** -- Read existing cases, identify gaps by comparing against skill capabilities and judge criteria, generate complementary cases.
- **From-Traces** -- Run `from_traces.py` to extract real inputs from MLflow traces. Fall back to Expand if no traces found.

### External Services / Tools (dashed border)

- **eval-analyze skill** -- Invoked via Skill tool if eval.yaml is missing
- **from_traces.py** -- MLflow trace extraction script (used by from-traces strategy)
- **MLflow** -- External service providing production traces (dashed border)

### LLM/Agent Steps (double-border)

- None -- this skill does not use sub-agents or LLM calls directly. The generation is done by the main agent.

## Expected Containers

- **Step 4: Choose Strategy** should be a container with three children: Bootstrap, Expand, From-Traces, showing the branching logic.
- **Step 5: Generate Cases** could be a container showing the per-case file creation: input.yaml, answers.yaml (conditional), annotations.yaml (conditional), companion files (conditional).

## Expected Edges (data flow)

- Step 0 --> Step 1: `config path, count, strategy`
- Step 1 --> Step 2: `eval.yaml + eval.md content`
- Step 1 --> eval-analyze: `missing config` (conditional edge to external skill)
- Step 2 --> Step 3: `generation template (required files, fields, semantics)`
- Step 3 --> Step 4: `current state (case count, coverage gaps)`
- Step 4 (Bootstrap) --> Step 5: `case designs (simple, complex, edge, judge-targeted)`
- Step 4 (Expand) --> Step 5: `gap analysis + new case designs`
- Step 4 (From-Traces) --> from_traces.py --> Step 5: `extracted trace inputs`
- Step 5 --> Step 6: `generated case directories`
- Step 6 --> Step 5: `validation failures` (back-edge for fixes)
- Step 6 --> Step 7: `validated cases`

## Back-Edges and Loops

- Step 6 back to Step 5: fix validation failures in generated cases
- Step 1 to eval-analyze: conditional delegation when eval.yaml is missing (then returns to Step 1)

## Callout Boxes

- **Case directory structure**: Callout showing a sample case directory with files: `input.yaml`, `answers.yaml`, `annotations.yaml`, companion files
- **Generation template**: Callout showing the extracted checklist: required files, required fields, optional fields, argument placeholders
- **Strategy decision**: Callout showing when each strategy applies (bootstrap: <5 cases, expand: cases exist but thin, from-traces: MLflow available)

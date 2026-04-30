# Expected Diagram: eval-run Skill Flow

## Overview

The eval-run skill is the most complex skill in the harness. It executes a skill against test cases, scores with judges, and generates an HTML report. The diagram should show an 8-step pipeline with background execution monitoring, a two-phase scoring stage (judges + pairwise), and an optional MLflow logging step.

## Expected Nodes

### Top-Level Steps (main flow)

- **Step 0: Parse Arguments and Load Config** -- Parse flags (`--config`, `--model`, `--run-id`, `--case`, `--baseline`, `--no-judge`, `--gold`, `--effort`). Check config exists; if missing, invoke `/eval-analyze`. Persist flags via `state.py init`.
- **Step 1: Find Dataset** -- Read `dataset.path` from eval.yaml. Verify directory exists and contains case subdirectories. Apply `--case` filter if specified. Stop if no cases found.
- **Step 2: Preflight Check** -- Run `preflight.py` to verify artifact directories are clean. Gate: CLEAN proceeds, DIRTY asks user (force clean / change run-id / abort).
- **Step 3: Prepare Workspace** -- Run `workspace.py` to create isolated workspace with test cases and output directories. Outputs: workspace path, case count, batch path. Reports hook count if `inputs.tools` configured.
- **Step 3b: Resolve Tool Interception** -- Mandatory if `inputs.tools` configured. Read `tool_handlers.yaml`, resolve each handler's prompt into concrete runtime checks (AskUserQuestion 3-tier answering, service interception input_filters, blocking patterns). Write updated handlers back.
- **Step 4: Execute Skill** -- Run `execute.py` in background. Handles CLI construction, streaming progress, result capture. Monitor via periodic `tail` of output file. Read `run_result.json` after completion for exit_code, duration, cost, turns.
- **Step 5: Collect Artifacts** -- Run `collect.py` to distribute workspace outputs into per-case directories. Read `collection.json` for per-case artifact counts.
- **Step 6: Score** -- Two sub-phases: (1) Run `score.py judges` for all configured judges. (2) If `--baseline` specified, run `score.py pairwise` for comparison. Read `summary.yaml` for results.
- **Step 7: Interpret and Report** -- Analyze results (aggregate scores, failure patterns, regressions, root causes, cost attribution). Write `analysis.md` with YAML frontmatter. Generate HTML report via `report.py --open`. Optionally save gold references if `--gold`.
- **Step 8: Log to MLflow** -- Optional. If `mlflow.experiment` configured, invoke `/eval-mlflow --action log-results`.

### External Scripts (dashed border)

- **preflight.py** -- Pre-run cleanliness check
- **workspace.py** -- Workspace creation, batch.yaml, symlinks
- **execute.py** -- Skill execution via agent runner
- **collect.py** -- Artifact collection + case mapping
- **score.py** -- Scoring: inline checks, LLM judges, pairwise
- **report.py** -- HTML report generation
- **tools.py** -- PreToolUse hook for tool interception
- **state.py** -- Shared state persistence

### External Skills (dashed border)

- **eval-analyze** -- Invoked via Skill tool if config is missing
- **eval-mlflow** -- Invoked via Skill tool for MLflow logging (optional)

### LLM/Agent Steps (double-border)

- **LLM Judges** (inside Step 6) -- LLM-based prompt judges and pairwise comparison judges
- **Analysis** (inside Step 7) -- The main agent's interpretation of results, writing analysis.md

## Expected Containers

- **Step 2: Preflight Check** -- Container with children: run preflight.py, gate (CLEAN/DIRTY), dirty handling (force clean / change run-id / abort).
- **Step 3b: Resolve Tool Interception** -- Container with children for each handler type: AskUserQuestion (3-tier), service interception (env_checks + input_filters), blocking (MCP patterns).
- **Step 4: Execute Skill** -- Container with children: launch execute.py (background), monitor progress (periodic tail), read run_result.json.
- **Step 6: Score** -- Container with two children: judges phase (`score.py judges`) and pairwise phase (`score.py pairwise`, conditional on `--baseline`).
- **Step 7: Interpret and Report** -- Container with children: analyze results, write analysis.md, generate HTML report, optional gold save.

## Expected Edges (data flow)

- Step 0 --> eval-analyze: `missing config` (conditional)
- Step 0 --> Step 1: `config, flags`
- Step 1 --> Step 2: `dataset path, case list`
- Step 2 --> Step 3: `CLEAN`
- Step 3 --> Step 3b: `workspace path, tool_handlers.yaml` (conditional)
- Step 3 --> Step 4: `workspace path` (if no tools configured)
- Step 3b --> Step 4: `resolved tool_handlers.yaml`
- Step 4 --> Step 5: `run_result.json, stdout.log`
- Step 5 --> Step 6: `collection.json, per-case artifacts`
- Step 6 (judges) --> Step 6 (pairwise): `summary.yaml` (conditional)
- Step 6 --> Step 7: `summary.yaml`
- Step 7 --> Step 8: `analysis.md, report.html` (conditional on MLflow config)

## Back-Edges and Loops

- Step 4 monitoring loop: periodic `tail` of execute.py output file until completion detected
- Step 2 dirty handling: may loop back to re-check after cleanup or run-id change
- Step 0 to eval-analyze: conditional delegation then return

## Callout Boxes

- **Workspace structure**: Callout showing workspace tree with cases/, outputs/, batch.yaml, tool_handlers.yaml
- **run_result.json**: Callout showing key fields: exit_code, duration_s, cost_usd, num_turns, per-model token usage
- **summary.yaml**: Callout showing three sections: judges (per-judge mean, pass_rate), per_case (per-case value+rationale per judge), pairwise (wins_a, wins_b, ties)
- **Judge types**: Callout showing the three judge types: inline check scripts, LLM prompt judges, external module/function
- **3-tier AskUserQuestion**: Callout showing the answer resolution: case_overrides --> LLM call (models.hook) --> fallback to first option

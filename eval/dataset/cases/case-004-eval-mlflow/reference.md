# Expected Diagram: eval-mlflow Skill Flow

## Overview

The eval-mlflow skill bridges the evaluation harness with MLflow. It has four distinct actions (sync-dataset, log-results, push-feedback, pull-feedback) that can run independently or as a combined "all" action. The diagram should show a linear pipeline with four parallel action branches.

## Expected Nodes

### Top-Level Steps (main flow)

- **Step 0: Parse Arguments** -- Parse `--action`, `--config`, `--run-id` flags. Actions: sync-dataset, log-results, push-feedback, pull-feedback, all.
- **Step 1: Verify MLflow** -- Check MLflow server reachability via `ensure_server()`. Report tracking URI. If not configured, suggest `/eval-setup`.
- **Step 2: Read Configuration** -- Read eval.yaml for `mlflow.experiment`, `dataset.path`, `dataset.schema`, `judges`.

### Action Branches

- **Step 3: Sync Dataset** -- Two-phase: (a) Read schema + sample case, build schema_mapping.json mapping inputs/expectations to source files. (b) Run `sync_dataset.py` with mapping. Preview before sync.
- **Step 4: Log Run Results** -- Run `log_results.py`. Logs params (skill, runner, model), metrics (per-judge mean/pass_rate, execution metrics), artifacts (summary.yaml), table (per-case results), traces (from stdout.log), tags.
- **Step 5: Push Feedback** -- Run `attach_feedback.py --source all`. Pushes judge feedback (source_type=CODE) and human feedback from review.yaml (source_type=HUMAN) to MLflow traces.
- **Step 6: Pull Feedback** -- Run `attach_feedback.py --action pull`. Pulls annotations from MLflow UI back into review.yaml under `mlflow_feedback` section.

- **Step 7: Report** -- Summarize what each action did: cases synced, results logged, feedback pushed/pulled. Show MLflow UI URI.

### External Services (dashed border)

- **MLflow Server** -- External tracking server (dashed border). Connected to all action branches.
- **sync_dataset.py** -- Dataset sync script
- **log_results.py** -- Result logging script
- **attach_feedback.py** -- Bidirectional feedback script (push and pull)

### LLM/Agent Steps (double-border)

- **Schema Mapping** (inside Step 3a) -- The main agent interprets `dataset.schema` and sample case to build the schema_mapping.json. This is an LLM reasoning step.

## Expected Containers

- **Step 3: Sync Dataset** -- Container with two children: Step 3a (read schema, build mapping) and Step 3b (run sync_dataset.py).
- An overarching container or branching structure showing that Steps 3-6 are independent actions gated by the `--action` flag.

## Expected Edges (data flow)

- Step 0 --> Step 1: `action, config path, run-id`
- Step 1 --> Step 2: `MLflow OK / not reachable`
- Step 2 --> Step 3: `dataset.schema, dataset.path` (if action = sync-dataset or all)
- Step 2 --> Step 4: `mlflow.experiment, run-id` (if action = log-results or all)
- Step 2 --> Step 5: `run-id, judges` (if action = push-feedback or all)
- Step 2 --> Step 6: `run-id` (if action = pull-feedback)
- Step 3a --> Step 3b: `schema_mapping.json`
- Step 3b --> MLflow: `dataset records`
- Step 4 --> MLflow: `params, metrics, artifacts, traces, tags`
- Step 5 --> MLflow: `judge feedback, human feedback`
- MLflow --> Step 6: `UI annotations`
- Step 6 --> review.yaml: `mlflow_feedback section`
- Steps 3-6 --> Step 7: `action summaries`

## Back-Edges and Loops

- Step 3a to Step 3b: if sync preview looks wrong, adjust mapping and re-run (implied loop)
- No major back-edges -- the actions are mostly linear

## Callout Boxes

- **schema_mapping.json**: Callout showing the mapping format with inputs/expectations sections, field-to-file mappings (e.g., `"input.yaml:prompt"`, `"reference.md:__file__"`)
- **MLflow logged data**: Callout showing what gets logged -- params (skill, runner.type, model), metrics (per-judge mean/pass_rate), artifacts (summary.yaml), table (per-case results)
- **Feedback direction**: Callout showing bidirectional flow -- push (harness --> MLflow traces) vs pull (MLflow UI --> review.yaml)
- **URI resolution order**: `mlflow.tracking_uri` in eval.yaml > `MLFLOW_TRACKING_URI` env var > `http://127.0.0.1:5000`

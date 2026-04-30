# Expected Diagram: eval-setup Skill Flow

## Overview

The eval-setup skill is the simplest in the harness. It is an optional environment configurator that verifies dependencies, configures MLflow tracking, checks API keys, and sets up the runs directory. The diagram should show a mostly linear 7-step flow with conditional branches for MLflow setup options.

## Expected Nodes

### Top-Level Steps (main flow)

- **Step 0: Parse Arguments** -- Parse `--tracking-uri`, `--skip-mlflow`, `--runs-dir` flags.
- **Step 1: Install Dependencies** -- Fallback for mid-session installs. Check and install: pyyaml (required), mlflow[genai] (unless --skip-mlflow), anthropic[vertex] (for LLM judges and hooks).
- **Step 2: Run Preflight Checks** -- Run `check_env.py --fix`. If all pass, skip to Step 6.
- **Step 3: Configure MLflow Tracking** -- Skipped if `--skip-mlflow`. Three options: (a) Local server (mlflow server --port 5000), (b) Local file store (sqlite:///mlflow.db), (c) Remote server (user-provided URI). Also mention per-project pinning via `mlflow.tracking_uri` in eval.yaml.
- **Step 4: Configure API Keys** -- Check ANTHROPIC_API_KEY and ANTHROPIC_VERTEX_PROJECT_ID. Guide user to export the appropriate key.
- **Step 5: Configure Runs Directory** -- Check AGENT_EVAL_RUNS_DIR (default eval/runs). Use `--runs-dir` if provided.
- **Step 5b: Check Skill-Specific Env Vars** -- If eval.yaml exists with `execution.env` entries using `$VAR` references, verify those variables are set. Warn about unset vars.
- **Step 6: Create MLflow Experiment** -- Skipped if `--skip-mlflow`. If eval.yaml exists with `mlflow.experiment`, call `setup_experiment()`.
- **Step 7: Final Verification** -- Re-run `check_env.py` to confirm. If eval.yaml exists, validate config. Report final status and suggest next steps in the pipeline.

### External Services / Tools (dashed border)

- **check_env.py** -- Preflight environment check script
- **MLflow Server** -- External service (local or remote)
- **pip** -- Package installer for dependencies

### LLM/Agent Steps (double-border)

- None -- this skill is purely procedural with no LLM/agent delegation

## Expected Containers

- **Step 1: Install Dependencies** -- Container with three children: pyyaml check/install, mlflow check/install (conditional), anthropic check/install.
- **Step 3: Configure MLflow Tracking** -- Container with three children: Local server, Local file store, Remote server. These are mutually exclusive options presented to the user.

## Expected Edges (data flow)

- Step 0 --> Step 1: `flags (skip-mlflow, tracking-uri, runs-dir)`
- Step 1 --> Step 2: `dependencies installed`
- Step 2 --> Step 6: `all checks pass` (early skip to Step 6)
- Step 2 --> Step 3: `checks failed`
- Step 3 --> Step 4: `MLFLOW_TRACKING_URI set`
- Step 4 --> Step 5: `API key configured`
- Step 5 --> Step 5b: `AGENT_EVAL_RUNS_DIR set`
- Step 5b --> Step 6: `env vars verified`
- Step 6 --> Step 7: `experiment created`

## Back-Edges and Loops

- Step 2 early skip to Step 6: if all preflight checks pass, skip Steps 3-5b entirely
- No true loops -- the flow is linear with conditional skips

## Callout Boxes

- **Pipeline overview**: Callout showing the full eval pipeline path: `/eval-setup` --> `/eval-analyze` --> `/eval-dataset` --> `/eval-run` --> `/eval-review` or `/eval-optimize`
- **MLflow URI resolution**: Callout showing priority order: `mlflow.tracking_uri` in eval.yaml > `MLFLOW_TRACKING_URI` env var > `http://127.0.0.1:5000`
- **Dependencies**: Callout listing: pyyaml>=6.0, mlflow[genai]>=3.5, anthropic[vertex]>=0.40

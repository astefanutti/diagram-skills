# Expected Diagram: Full Eval Pipeline (7 skills)

## Overview

This diagram covers all 7 skills in the agent-eval-harness as a high-level pipeline. With >5 skills, this triggers **pipeline mode**: each skill is a single node with a bullet summary, not a container with internal steps. The focus is on the orchestration flow between skills.

## Expected Nodes (8 total: 7 skills + 1 external service)

- **setup** (`/eval-setup`): dependencies, MLflow config, directories. Entry point, optional/setup role (dashed border).
- **analyze** (`/eval-analyze`): analyze skill, generate eval.yaml, suggest judges. Processing node.
- **dataset** (`/eval-dataset`): generate test cases, fill coverage gaps. Processing node.
- **run** (`/eval-run`): execute eval, collect artifacts, score with judges. Central processing node.
- **eval-mlflow** (`/eval-mlflow`): sync dataset, log results, push traces. Optional/side-channel (dashed border).
- **review** (`/eval-review`): human review, feedback collection. Processing node.
- **optimize** (`/eval-optimize`): automated skill improvement, re-run eval. Processing node.
- **mlflow** (MLflow Server): external service, not a skill. Dashed border.

## Expected Edges

### Main pipeline (linear)
- setup → analyze → dataset → run → eval-mlflow

### MLflow connections (dashed)
- setup → mlflow: "setup"
- eval-mlflow → mlflow: "sync, log, feedback"
- mlflow → dataset: "datasets"

### Feedback loops (bidirectional)
- run ↔ review
- run ↔ optimize

## Key Visual Properties

- Pipeline mode: one node per skill, no internal steps
- Direction: right (left-to-right flow)
- External services (MLflow) and optional skills (setup, eval-mlflow) use dashed borders
- Feedback loops shown as bidirectional edges
- Edge labels indicate primary data flow
- 8 nodes, ~10 edges — compact pipeline overview

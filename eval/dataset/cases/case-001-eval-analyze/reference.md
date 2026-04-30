# Expected Diagram: eval-analyze Skill Flow

## Overview

The eval-analyze skill reads a target skill deeply (including sub-skills), explores existing test cases, and generates `eval.yaml` -- the evaluation configuration. The diagram should show a 7-step linear pipeline with two agent delegations and a validation loop.

## Expected Nodes

### Top-Level Steps (main flow)

- **Step 0: Parse Arguments** -- Parse `--skill`, `--config`, `--update` flags. Persist to state file via `state.py init`.
- **Step 1: Find Target Skill** -- Run `find_skills.py --name <skill>` to locate SKILL.md. If no `--skill` flag, list all project skills and auto-select or ask user.
- **Step 2: Check If Analysis Needed** -- Check if eval.yaml exists, validate it with `validate_eval.py config`, check if eval.md is fresh via `validate_eval.py memory`. Gate: if FRESH and complete config, exit early.
- **Step 3: Deep-Read the Skill** -- LLM/agent step (double-border). Launch Explore sub-agent with `analyze-skill.md` prompt. Recursive analysis follows sub-skill chains (up to 5 levels). Returns structured YAML: purpose, inputs, outputs, sub_skills, flags, pipeline, quality_criteria, suggested_judges.
- **Step 4: Explore the Dataset** -- Check `dataset.path` from eval.yaml. Search for case directories via Glob. Read one sample case to understand structure (file names, field names, formats).
- **Step 5: Generate eval.yaml** -- Combine skill analysis + dataset exploration. Read `eval-yaml-template.md` for guidance. Write the full config: execution mode, arguments, runner, models, permissions, dataset schema, outputs, judges, thresholds.
- **Step 5b: Validate Generated Config** -- Run `validate_eval.py config <config>`. Fix errors, report warnings.
- **Step 6: Generate eval.md** -- Compute SKILL.md hash. Write eval.md with YAML frontmatter (skill, analyzed_at, skill_hash) and analysis narrative.
- **Step 7: Report** -- Summarize what was generated: eval.yaml status, eval.md cached, suggest next steps.

### External Services / Tools (dashed border)

- **find_skills.py** -- Skill discovery script (reads plugin.json for paths)
- **validate_eval.py** -- Config and memory validation script
- **state.py** -- Shared state persistence (key-value store)

### LLM/Agent Steps (double-border)

- **Explore Sub-Agent** -- The agent launched in Step 3 that recursively reads SKILL.md files and sub-skills

## Expected Containers

- **Step 2: Check If Analysis Needed** should be a container with children for the three checks (config exists?, validate config, eval.md fresh?) and the early-exit gate.
- **Step 5: Generate eval.yaml** could be a container with children for: read template, set execution mode, set models, write judges, write config file.

## Expected Edges (data flow)

- Step 0 --> Step 1: `--skill flag`
- Step 1 --> Step 2: `SKILL.md path`
- Step 2 --> Step 3: `STALE / NO_CONFIG` (conditional -- only if analysis needed)
- Step 2 --> Step 7: `FRESH` (early exit path, back-edge or skip-edge)
- Step 3 --> Step 4: `skill analysis YAML`
- Step 4 --> Step 5: `dataset structure`
- Step 3 --> Step 5: `skill analysis YAML` (both Step 3 and Step 4 feed into Step 5)
- Step 5 --> Step 5b: `eval.yaml`
- Step 5b --> Step 5: `validation errors` (back-edge for fix loop)
- Step 5b --> Step 6: `validated eval.yaml`
- Step 6 --> Step 7: `eval.md`

## Back-Edges and Loops

- Step 5b back to Step 5: validation error fix loop (if `validate_eval.py` returns errors, fix and re-validate)
- Step 2 early exit to Step 7: skip the analysis if config is fresh and complete

## Callout Boxes

- **eval.yaml structure**: A callout showing the key sections of the generated config (skill, execution, runner, models, dataset, outputs, judges, thresholds)
- **Explore Agent output**: A callout showing the structured YAML returned by the sub-agent (purpose, inputs, outputs, sub_skills, pipeline, suggested_judges)
- **Validation outcomes**: FRESH/STALE/NO_CONFIG decision tree

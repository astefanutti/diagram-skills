# Expected Diagram: eval-review + eval-optimize Combined Flow

## Overview

This diagram covers two complementary skills: eval-review (human-in-the-loop interactive review) and eval-optimize (automated improvement loop). They share the same inputs (eval run results) and both produce SKILL.md changes, but differ in their approach: review collects human feedback then proposes changes, while optimize acts autonomously by reading judge rationale and transcripts. The diagram should show both flows side by side or sequentially, highlighting their shared data and different feedback sources.

## Expected Nodes -- eval-review

### Top-Level Steps

- **Step 0: Parse Arguments** -- Parse `--run-id` (required), `--config`, `--case` filter.
- **Step 1: Load Results** -- Read `summary.yaml` via state.py. Read eval.yaml for skill context, dataset schema, judge types.
- **Step 2: Present Overview** -- Show HTML report link if available. Display pass rates per judge, pass/fail case counts, pairwise comparison results. Ask user: "review all, only failures, or specific cases?"
- **Step 3: Walk Through Cases** -- For each case: present judge scores + rationale, summarize output files, ask for human feedback. Collect per-case feedback notes.
- **Step 4: Check Transcripts** -- Delegate to Agent (sub-agent, double-border) to read stdout.log for reviewed cases. Agent reports: multiple approaches tried? unnecessary tools? error recovery? wasted turns?
- **Step 5: Save Feedback** -- Write `review.yaml` with run_id, reviewed_cases count, feedback_cases count, reviewer, per-case feedback strings. Use Write tool directly (not state.py).
- **Step 6: Analyze Patterns** -- Read `review-results.md` prompt. Identify: judge-human alignment (do complaints match failures?), systematic issues (same complaint across cases), new judge candidates.
- **Step 7: Propose Changes** -- Read SKILL.md via `find_skills.py`. Identify instructions related to complaints. Show before/after diffs. Ask user approval before applying edits. Optionally propose new judges for eval.yaml.
- **Step 8: Next Steps** -- Suggest: re-run with baseline, eval-optimize, eval-dataset expand, eval-mlflow push-feedback.

## Expected Nodes -- eval-optimize

### Top-Level Steps

- **Step 0: Parse Arguments** -- Parse `--config`, `--model`, `--max-iterations` (default 3), `--run-id`, `--target-judge`.
- **Step 1: Initial Eval Run** -- If no recent results, invoke `/eval-run` via Skill tool. Read `summary.yaml`. If all judges pass, exit early.
- **Step 2: Identify Failures** -- From summary.yaml: which judges failed, on which cases, with what rationale. Check for review.yaml (human feedback) and mlflow_feedback. Build failure map: judge_name --> [case_ids] --> rationale.
- **Step 3: Analyze Root Causes** -- Read SKILL.md via `find_skills.py`. Delegate transcript analysis to Explore sub-agent (double-border). Delegate output examination to Explore sub-agent. Form hypotheses connecting judge rationale + transcript evidence + output analysis to specific SKILL.md sections.
- **Step 4: Edit the Skill** -- Apply targeted, evidence-grounded edits to SKILL.md. Surgical changes, explain the why, avoid overfitting to single cases.
- **Step 5: Re-Run and Verify** -- Invoke `/eval-run` via Skill tool with `--baseline` pointing to previous iteration. Check: targeted failures fixed? Regressions? Score improvement?
- **Step 6: Handle Regressions** -- Assess severity: minor (net positive, continue), major (revert edit, try different approach), stuck (report to user, suggest /eval-review).
- **Step 7: Iterate or Report** -- If failures remain and iterations < max: loop back to Step 2. If all pass: report success. If max reached: report what was fixed and what remains.

### External Skills (dashed border)

- **eval-run** -- Invoked via Skill tool for initial run (Step 1) and re-runs (Step 5)
- **eval-mlflow** -- Suggested for logging optimization results

### LLM/Agent Steps (double-border)

- **Transcript Agent** (eval-review Step 4, eval-optimize Step 3) -- Explore sub-agent reading stdout.log
- **Output Analysis Agent** (eval-optimize Step 3) -- Explore sub-agent examining failing case outputs
- **Human Feedback** (eval-review Steps 3, 7) -- User interaction points (distinct visual treatment)

## Expected Containers

- **eval-review** -- Top-level container encompassing Steps 0-8 of the review flow
- **eval-optimize** -- Top-level container encompassing Steps 0-7 of the optimize flow
- **eval-optimize Step 3: Analyze Root Causes** -- Container with children: read SKILL.md, transcript agent, output agent, form hypotheses
- **eval-optimize iteration loop** -- Visual indication of the Step 2 --> Step 7 loop (up to max-iterations)

## Expected Edges (data flow)

### eval-review edges
- Step 1 --> Step 2: `summary.yaml, eval.yaml context`
- Step 2 --> Step 3: `user's selection (all/failures/specific)`
- Step 3 --> Step 4: `reviewed case IDs`
- Step 3 --> Step 5: `per-case feedback`
- Step 4 --> Step 6: `transcript findings`
- Step 5 --> Step 6: `review.yaml`
- Step 6 --> Step 7: `pattern analysis`
- Step 7 --> SKILL.md: `approved edits` (conditional on user approval)

### eval-optimize edges
- Step 1 --> eval-run: `invoke /eval-run` (conditional)
- Step 1 --> Step 2: `summary.yaml`
- Step 2 --> Step 3: `failure map (judge --> cases --> rationale)`
- Step 2 --> review.yaml: `read human feedback` (if exists)
- Step 3 --> Step 4: `hypotheses (judge + transcript + output evidence)`
- Step 4 --> SKILL.md: `targeted edits`
- Step 4 --> Step 5: `edited SKILL.md`
- Step 5 --> eval-run: `invoke /eval-run --baseline`
- Step 5 --> Step 6: `new summary.yaml + regression check`
- Step 6 --> Step 4: `revert + retry` (if major regression, back-edge)
- Step 7 --> Step 2: `iterate` (back-edge, if failures remain)

### Cross-skill edges
- eval-review Step 5 (review.yaml) --> eval-optimize Step 2: `human feedback informs optimize`
- Both skills --> SKILL.md: `proposed/applied edits`

## Back-Edges and Loops

- **eval-optimize main loop**: Step 7 back to Step 2 (up to max-iterations)
- **eval-optimize regression revert**: Step 6 back to Step 4 (revert and try different approach)
- **eval-review**: no loops, linear with user interaction gates

## Callout Boxes

- **review.yaml structure**: Callout showing: run_id, reviewed_cases, feedback_cases, reviewer, feedback (per-case strings)
- **Failure map**: Callout showing the data structure: judge_name --> [case_id, ...] --> rationale for each
- **Iteration tracking**: Callout showing run-id naming: `<id>-iter-0`, `<id>-iter-1`, ..., `<id>-iter-N`
- **Edit principles**: "Ground in evidence, be surgical, explain the why, don't overfit"

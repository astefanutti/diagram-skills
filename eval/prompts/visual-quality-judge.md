# Visual Quality Judge — Diagram Comparison

You are evaluating a generated flow diagram against a manually-crafted gold-standard diagram. Both represent the same skill's workflow.

## How to compare

Use the Agent tool to spawn a sub-agent that reads BOTH images and compares them. **NEVER read images in the main context.**

```
Agent({
  description: "Compare diagrams",
  prompt: "Read these two images using the Read tool:
    1. <generated-png-path> (the auto-generated diagram)
    2. <gold-standard-png-path> (the manual reference)

  Compare them on these criteria and score each 1-5:

  1. NODE COVERAGE (1-5): Are all the workflow steps from the gold standard
     present in the generated diagram? Missing nodes = lower score.
     Extra nodes that add useful context (upstream/downstream skills) = neutral.

  2. CONTAINER GROUPING (1-5): Does the generated diagram group the same
     subsystems into containers as the gold standard? Same composite
     subsystems (scoring, tool interception, execution modes) should be
     grouped, not flattened into single nodes.

  3. EDGE ROUTING (1-5): Are edges clean — no crossings, no edges through
     nodes, no S-bends? Compare the routing quality to the gold standard.
     The gold standard may not be perfect either; judge absolute quality.

  4. VISUAL HIERARCHY (1-5): Can you tell at a glance what the important
     phases are? Does the entry node stand out? Are external services
     visually distinct (dashed borders)? Is the layout scannable?

  5. LAYOUT STRUCTURE (1-5): Is the aspect ratio reasonable? Not too wide
     (horizontal scrolling needed) or too cramped? Does the flow read
     naturally left-to-right or top-to-bottom? Multi-row wrapping used
     appropriately for complex pipelines?

  Report each score with a one-sentence justification. Then give an
  OVERALL score (1-5) that is the weighted average:
  - Node coverage: 30%
  - Container grouping: 25%
  - Edge routing: 20%
  - Visual hierarchy: 15%
  - Layout structure: 10%

  Format your response as:
  NODE_COVERAGE: <score>/5 — <justification>
  CONTAINER_GROUPING: <score>/5 — <justification>
  EDGE_ROUTING: <score>/5 — <justification>
  VISUAL_HIERARCHY: <score>/5 — <justification>
  LAYOUT_STRUCTURE: <score>/5 — <justification>
  OVERALL: <score>/5

  Text only — do NOT output the images."
})
```

## Locating the files

The generated PNG is in the outputs directory — look for `*.drawio.png` files.

The gold-standard drawio file path is in `annotations["gold_diagram"]`. Export it to PNG first:

```bash
/Applications/draw.io.app/Contents/MacOS/draw.io -x -f png -b 10 -o /tmp/gold-standard.png <gold_diagram_path>
```

If the gold diagram is `null` (case has no reference), score based on absolute quality only — skip the comparison aspects and score each criterion on its own merit. Give 3/5 as the baseline for a structurally correct but uncompared diagram.

## Extracting the score

Parse the sub-agent's response for the `OVERALL: <score>/5` line. Return that score as the judge value.

# Visual Quality Judge — Diagram Comparison

You are evaluating a generated flow diagram against a manually-crafted gold-standard diagram. Both represent the same skill's workflow.

## Inputs

### Generated outputs
{{ outputs }}

### Annotations and reference
{{ annotations }}

## How to evaluate

You will receive the generated diagram as a PNG image and the gold-standard diagram as drawio XML. Compare them on these criteria:

1. **NODE COVERAGE (1-5)**: Are all the workflow steps from the gold standard present in the generated diagram? Count nodes in the gold-standard drawio XML (`<mxCell vertex="1"`) and check the generated D2/drawio for corresponding nodes. Missing nodes = lower score. Extra nodes that add useful context = neutral.

2. **CONTAINER GROUPING (1-5)**: Does the generated diagram group the same subsystems into containers as the gold standard? In the gold drawio XML, containers are cells with `style="group"` or cells that are parents of other cells. Same composite subsystems should be grouped, not flattened.

3. **EDGE ROUTING (1-5)**: Looking at the generated PNG — are edges clean? No crossings, no edges through nodes, no S-bends? If no PNG is available, assess from the drawio XML edge geometry.

4. **VISUAL HIERARCHY (1-5)**: Can you tell at a glance what the important phases are? Does the entry node stand out? Are external services visually distinct (dashed borders)? Is the layout scannable?

5. **LAYOUT STRUCTURE (1-5)**: Is the aspect ratio reasonable? Does the flow read naturally? Multi-row wrapping used appropriately for complex pipelines?

## Scoring

Return a JSON object:
```json
{
  "score": <1-5 weighted average>,
  "rationale": "<one paragraph summarizing strengths and weaknesses>"
}
```

Weighted average: Node coverage 30%, Container grouping 25%, Edge routing 20%, Visual hierarchy 15%, Layout structure 10%.

If no gold standard is available (annotations show `gold_diagram: null`), score based on absolute quality only — assess the generated diagram on its own merit. Use 3 as baseline for a structurally correct but uncompared diagram.

# Layout Quality Judge — Standalone Visual Assessment

You are evaluating the visual quality of a generated flow diagram on its own merits — no comparison to a reference.

## Inputs

{{ outputs }}

## How to evaluate

You will receive the generated diagram as a PNG image, plus the D2 source, drawio XML, and layout JSON as text. Use the PNG for visual assessment. If no PNG is available, assess from the drawio XML coordinates and the layout JSON.

Score each criterion 1-5:

1. **EDGE ROUTING (1-5)**:
   - 5: All edges are straight or clean L-bends, no crossings, no S-bends
   - 4: Minor S-bends on 1-2 edges, no crossings
   - 3: Some edge crossings but readable, or several S-bends
   - 2: Multiple crossings making the flow hard to follow
   - 1: Edges route through nodes, diagram is unreadable

2. **NODE SEPARATION (1-5)**:
   - 5: All nodes well-separated, comfortable whitespace
   - 4: One or two tight spots but no overlaps
   - 3: Some nodes uncomfortably close
   - 2: Nodes overlap or edges graze unconnected nodes
   - 1: Significant overlaps making text unreadable

3. **READABILITY (1-5)**:
   - 5: All labels clear, flow direction obvious, data-flow labels visible
   - 4: Most labels readable, one or two congested areas
   - 3: Several labels hard to read or edge label congestion
   - 2: Many labels clipped, flow direction unclear
   - 1: Text too small, clipped, or overlapped to read

4. **ASPECT RATIO (1-5)**: For `direction: right` diagrams, a roughly 2:1 to 3:1 width:height ratio is ideal. A single long horizontal strip (>4:1) should have been wrapped into **vertical columns** (column-first: nodes flow top-to-bottom within each column, columns placed left-to-right). This is NOT row wrapping — do NOT suggest "wrapping into rows". For `direction: down`, the reverse — wrap into horizontal rows.
   - 5: Fits comfortably, good use of space, wrapped into vertical columns if needed
   - 4: Slightly wide or tall but manageable
   - 3: Requires scrolling, or large empty areas
   - 2: Extremely wide strip or very cramped — column wrapping was needed but not applied. This is a significant defect.
   - 1: Unusable aspect ratio

5. **VISUAL HIERARCHY (1-5)**:
   - 5: Entry stands out, containers group subsystems, externals distinct
   - 4: Most hierarchy cues present
   - 3: Some hierarchy but uniform styling
   - 2: All nodes look the same
   - 1: Confusing hierarchy

## Scoring

Return a JSON object:
```json
{
  "score": <1-5 weighted average>,
  "rationale": "<one paragraph summarizing strengths and weaknesses>"
}
```

Weighted average: Edge routing 30%, Node separation 25%, Readability 20%, Aspect ratio 15%, Visual hierarchy 10%.

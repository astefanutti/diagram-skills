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

4. **ASPECT RATIO & COMPACTNESS (1-5)**: For `direction: right` diagrams, a roughly 2:1 to 3:1 width:height ratio is ideal. But ratio alone isn't enough — a 2000px-wide diagram at 2.7:1 is still too wide to scan comfortably. Complex diagrams (12+ nodes, containers) should use multi-row wrapping to stay under ~1400px wide. Judge both the ratio AND the absolute canvas width relative to the diagram's complexity.
   - 5: Compact, fits comfortably, wrapping used when beneficial
   - 4: Slightly wide but manageable, <1600px for complex diagrams
   - 3: Wide (>1600px) or requires scrolling, wrapping would help but wasn't applied
   - 2: Very wide (>1800px) or extremely cramped — wrapping was clearly needed but not applied
   - 1: Unusable — >2000px wide single strip or severe cramping

5. **GRID ALIGNMENT (1-5)**: Nodes in a well-laid-out diagram follow a clean grid — nodes at the same pipeline stage share the same x-coordinate, nodes in the same row share the same y-coordinate. A "diagonal flow" where each successive node drifts lower-right (or upper-right) instead of following clean horizontal/vertical lines is a significant layout defect.
   - 5: All nodes snap to a clear grid; rows and columns are perfectly aligned
   - 4: Minor alignment drift on 1-2 nodes
   - 3: Noticeable diagonal drift — the flow goes downhill/uphill rather than straight across
   - 2: Most nodes are misaligned; no clear rows or columns
   - 1: No discernible grid structure

6. **VISUAL HIERARCHY (1-5)**:
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

Weighted average: Edge routing 25%, Node separation 20%, Readability 15%, Aspect ratio 15%, Grid alignment 15%, Visual hierarchy 10%.

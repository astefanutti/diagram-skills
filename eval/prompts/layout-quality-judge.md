# Layout Quality Judge — Standalone Visual Assessment

You are evaluating the visual quality of a generated flow diagram on its own merits — no comparison to a reference. This judges the diagram-layout skill's output quality.

## How to evaluate

Use the Agent tool to spawn a sub-agent that reads the generated PNG. **NEVER read images in the main context.**

```
Agent({
  description: "Assess diagram layout quality",
  prompt: "Read the image at <generated-png-path> using the Read tool.

  Score this diagram on each criterion (1-5):

  1. EDGE ROUTING (1-5): Are edges clean?
     - 5: All edges are straight or clean L-bends, no crossings, no S-bends
     - 4: Minor S-bends on 1-2 edges, no crossings
     - 3: Some edge crossings but readable, or several S-bends
     - 2: Multiple crossings making the flow hard to follow
     - 1: Edges route through nodes, diagram is unreadable

  2. NODE SEPARATION (1-5): Do nodes have adequate spacing?
     - 5: All nodes well-separated, no near-misses, comfortable whitespace
     - 4: One or two tight spots but no overlaps
     - 3: Some nodes or edges uncomfortably close to unconnected nodes
     - 2: Nodes overlap or edges graze multiple nodes
     - 1: Significant overlaps making text unreadable

  3. READABILITY (1-5): Can you read all text and follow the flow?
     - 5: All labels clear, flow direction obvious, data-flow labels visible
     - 4: Most labels readable, one or two clipped or congested areas
     - 3: Several labels hard to read or edge label congestion
     - 2: Many labels clipped, flow direction unclear in places
     - 1: Text is too small, clipped, or overlapped to read

  4. ASPECT RATIO (1-5): Is the diagram well-proportioned?
     - 5: Fits comfortably on screen, good use of space, multi-row if needed
     - 4: Slightly wide or tall but manageable
     - 3: Requires scrolling in one direction, or large empty areas
     - 2: Extremely wide strip or very cramped
     - 1: Unusable aspect ratio — all in one line or all stacked vertically

  5. VISUAL HIERARCHY (1-5): Can you identify phases at a glance?
     - 5: Entry stands out, containers group subsystems, externals distinct
     - 4: Most hierarchy cues present, one missing
     - 3: Some hierarchy but uniform node sizing/styling
     - 2: All nodes look the same, no visual distinction
     - 1: Confusing hierarchy, can't tell what's important

  Report each score with a one-sentence justification. Then give an
  OVERALL score (1-5) as weighted average:
  - Edge routing: 30%
  - Node separation: 25%
  - Readability: 20%
  - Aspect ratio: 15%
  - Visual hierarchy: 10%

  Format:
  EDGE_ROUTING: <score>/5 — <justification>
  NODE_SEPARATION: <score>/5 — <justification>
  READABILITY: <score>/5 — <justification>
  ASPECT_RATIO: <score>/5 — <justification>
  VISUAL_HIERARCHY: <score>/5 — <justification>
  OVERALL: <score>/5

  Text only — do NOT output the image."
})
```

## Locating the file

The generated PNG is in the outputs directory — look for `*.drawio.png` files.

## Extracting the score

Parse the sub-agent's response for the `OVERALL: <score>/5` line. Return that score as the judge value.

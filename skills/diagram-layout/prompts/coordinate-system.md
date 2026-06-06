# Coordinate System and Sizing Reference

## Canvas

- Origin (0, 0) is top-left
- x increases rightward, y increases downward
- All coordinates are in pixels
- Default margin: 30px from canvas edges

## Node Sizing

Base node sizes by content volume:

| Content | Width | Height | Use for |
|---------|-------|--------|---------|
| Title only | 110-140 | 50-70 | Simple process steps |
| Title + 2-3 bullets | 140-180 | 100-130 | Standard action nodes |
| Title + 4-6 bullets | 180-220 | 130-170 | Detailed action nodes |
| Title + subtitle + 5+ bullets | 210-260 | 150-200 | Major processing steps |
| Entry node with CLI args | 120-150 | 130-200 | Skill entry points |

Container children (smaller, inside containers):

| Content | Width | Height |
|---------|-------|--------|
| Title + 2-3 lines | 90-130 | 70-95 |
| Title + 4+ lines | 110-160 | 85-110 |

Callout boxes:

| Content | Width | Height |
|---------|-------|--------|
| Short listing (3-5 items) | 180-230 | 120-170 |
| File tree (5-10 entries) | 220-270 | 200-280 |
| YAML/code snippet | 190-240 | 130-200 |

## Spacing

| Between | Gap |
|---------|-----|
| Columns (horizontal between nodes) | 40-60px |
| Stacked alternatives (vertical) | 30-50px |
| Container internal padding (left/right) | 15-20px |
| Container internal padding (top, for title) | 35-50px |
| Container internal padding (bottom) | 15-20px |
| Container children (horizontal) | 15-25px |
| Container children (vertical) | 15-20px |
| Back-edge route clearance below diagram | 40-60px |
| Multiple back-edge routes (stagger) | 25px |
| Callout from anchor node | 20-40px |
| Canvas margin | 30px |

## Style Palette

### Node styles

Font stack: Inter (optimized for small screen sizes) with Helvetica/Arial fallback.
Callout boxes use JetBrains Mono for code/file tree content.

**Corner radius**: `render_drawio.py` normalizes every rounded box to an
absolute corner radius (`absoluteArcSize=1`) at render time, so the radius is
a fixed pixel value regardless of box size. Without this, draw.io treats
`arcSize` as a percentage of the box's smaller side, making large containers
get disproportionately large corners. Don't rely on a specific `arcSize` in
the styles below — it is overridden during rendering.

```
# Standard node
rounded=1;whiteSpace=wrap;html=1;fillColor=#f5f5f5;strokeColor=#333333;strokeWidth=2;arcSize=10;verticalAlign=top;spacingTop=5;fontSize=11;fontFamily=Inter,Helvetica,Arial,sans-serif;

# Emphasized node (external systems, key outputs)
rounded=1;whiteSpace=wrap;html=1;fillColor=#e8e8e8;strokeColor=#333333;strokeWidth=2;arcSize=10;verticalAlign=middle;fontSize=11;fontFamily=Inter,Helvetica,Arial,sans-serif;

# LLM / agent reasoning step (role `llm`, parsed from a double-border cue) —
# emphasized fill plus a thicker stroke so reasoning steps stand out from
# ordinary processing boxes.
rounded=1;whiteSpace=wrap;html=1;fillColor=#e8e8e8;strokeColor=#333333;strokeWidth=3;arcSize=10;verticalAlign=top;spacingTop=5;fontSize=11;fontFamily=Inter,Helvetica,Arial,sans-serif;

# Optional/external node (dashed border)
rounded=1;whiteSpace=wrap;html=1;fillColor=#e8e8e8;strokeColor=#333333;strokeWidth=2;arcSize=10;dashed=1;dashPattern=8 4;verticalAlign=middle;fontSize=11;fontFamily=Inter,Helvetica,Arial,sans-serif;

# Light output node
rounded=1;whiteSpace=wrap;html=1;fillColor=#f5f5f5;strokeColor=#999999;strokeWidth=1;arcSize=10;verticalAlign=middle;fontSize=11;fontFamily=Inter,Helvetica,Arial,sans-serif;

# Callout detail box (monospace for code/file trees)
rounded=1;whiteSpace=wrap;html=1;fillColor=#f5f5f5;strokeColor=#bbbbbb;strokeWidth=1;arcSize=6;verticalAlign=top;spacingTop=5;align=left;spacingLeft=8;fontSize=10;fontFamily=JetBrains Mono,Courier New,monospace;

# Container (group)
rounded=1;whiteSpace=wrap;html=1;fillColor=#ececec;strokeColor=#333333;strokeWidth=2;container=1;collapsible=0;verticalAlign=top;spacingTop=5;fontSize=12;fontStyle=1;fontFamily=Inter,Helvetica,Arial,sans-serif;

# Container (review phase - blue)
rounded=1;whiteSpace=wrap;html=1;fillColor=#ececec;strokeColor=#4285f4;strokeWidth=2;container=1;collapsible=0;verticalAlign=top;spacingTop=5;fontSize=12;fontStyle=1;fontFamily=Inter,Helvetica,Arial,sans-serif;

# Container (optimize phase - green)
rounded=1;whiteSpace=wrap;html=1;fillColor=#ececec;strokeColor=#34a853;strokeWidth=2;container=1;collapsible=0;verticalAlign=top;spacingTop=5;fontSize=12;fontStyle=1;fontFamily=Inter,Helvetica,Arial,sans-serif;
```

### Edge styles

```
# Forward edge (solid)
edgeStyle=orthogonalEdgeStyle;rounded=1;strokeColor=#333333;strokeWidth=1.5;html=1;fontFamily=Inter,Helvetica,Arial,sans-serif;

# Conditional/optional edge (dashed)
edgeStyle=orthogonalEdgeStyle;rounded=1;strokeColor=#333333;strokeWidth=1.5;dashed=1;dashPattern=8 4;html=1;fontFamily=Inter,Helvetica,Arial,sans-serif;

# Back-edge / feedback loop (dashed, with waypoints)
edgeStyle=orthogonalEdgeStyle;rounded=1;strokeColor=#333333;strokeWidth=1.5;dashed=1;dashPattern=8 4;html=1;fontFamily=Inter,Helvetica,Arial,sans-serif;

# Callout connection (light dashed)
edgeStyle=orthogonalEdgeStyle;rounded=1;strokeColor=#bbbbbb;strokeWidth=1;dashed=1;dashPattern=4 4;html=1;fontFamily=Inter,Helvetica,Arial,sans-serif;

# Data flow hint (very light)
edgeStyle=orthogonalEdgeStyle;rounded=1;strokeColor=#999999;strokeWidth=1;dashed=1;dashPattern=4 4;html=1;fontFamily=Inter,Helvetica,Arial,sans-serif;
```

### Label HTML patterns

```html
<!-- Entry node with title + args -->
<b>/skill-name</b><br><br>--arg1<br>--arg2<br>--arg3

<!-- Action node with title + bullets -->
<b>Action Name</b><br><br>bullet 1<br>bullet 2<br>bullet 3

<!-- Container child (compact) -->
<b>Sub-step</b><br>detail 1<br>detail 2

<!-- Output node (centered) -->
<b>Output Name</b><br>description line
```

## Estimating Text Width

For sizing nodes to fit their content (Inter/Helvetica):
- Average character width at fontSize=11: ~6.5px
- Average character width at fontSize=12: ~7px
- Average character width at fontSize=13: ~7.5px
- Line height: ~16px for fontSize=11, ~18px for fontSize=12-13
- Add spacingTop (5px) + spacingBottom (5px) + border (4px)
- Minimum internal padding: 10px left + 10px right

Formula: `node_width = max(title_width, max_bullet_width) + 30` (left+right padding+border)
Formula: `node_height = title_height + gap + (n_bullets * line_height) + 20` (top+bottom padding)

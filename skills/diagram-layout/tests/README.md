# diagram-layout routing tests

Non-regression tests for the diagram-layout scripts in `../scripts/`
(`fix_layout.py`, `validate_layout.py`, `graph_analysis.py`, `render_drawio.py`).
They encode the defects analysed and fixed across the session: edge-through-node,
anchor hairpins, cramped loop/retry back-edges, the route-unaware waypoint
stripper, fan-in grouping (and not over-grouping), deterministic group
enforcement, nested-container rendering, reserved-ID remapping, edge-style
normalization, and the validator's structural guards.

## Run

```bash
python3 -m pytest skills/diagram-layout/tests/
```

No config or install needed — `conftest.py` puts `../scripts` on `sys.path`, and
`pytest` is the only dependency.

## What's covered

- **`test_route_prediction.py`** — the shared route model every layer relies on:
  `_predicted_route_pts` (straight / L / Z), `_route_has_uturn` (hairpins),
  `_best_anchor_route` (facing-side selection, inside-box avoidance, the
  sandwiched no-route case, side penalties).
- **`test_validate_routing.py`** — the validator flags waypoint-free edges whose
  auto-route crosses a node, with no false positives on clear edges, the edge's
  own endpoints, or edges into container children.
- **`test_fix_scenarios.py`** — end-to-end guards for the three reported defects
  (eval-analyze through-node, eval-run hairpin, pipeline 2-cycle) plus the
  route-aware stripper root-cause. Each asserts the defect is present, runs the
  full fixer, and asserts it's gone.
- **`test_grouping.py`** — `graph_analysis.group_shared_fan_in` (service +
  bundle groups), the two *must-not-over-group* cases (fan-out, single-sink
  convergence), and `fix_layout.fix_enforce_groups` rebuilding/bundling a group
  the layout placed flat (plus idempotence).
- **`test_render.py`** — `render_drawio`: nested-container emission (no dropped
  grandchildren), reserved-ID remapping, edge keyword-style normalization,
  Inter default font, absolute arc-size, and XML-attr escaping.
- **`test_validate_structure.py`** — validator structural guards: edge
  preservation (dropped / present / bundled-via-container / back-edge exempt),
  non-orthogonal edge style, and the wrong-schema / empty-plan rejections.
- **`test_corpus_regression.py`** — runs `fix_layout` over the historical
  `eval/runs/**/layout-plan.json` corpus and asserts the baseline holds
  (improved ≥ 8, regressed ≤ 1). **Skips** when the corpus is absent, since
  `eval/runs/` is gitignored (present only on a machine that has run the eval).

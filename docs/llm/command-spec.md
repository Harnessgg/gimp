# Command Spec (LLM)

## Global rules
1. Every CLI command emits exactly one JSON object to stdout.
2. Bridge-backed commands return `BRIDGE_UNAVAILABLE` when bridge is not reachable.
3. Start bridge with `harness-gimp bridge start`.
4. Use `.xcf` as working format for multi-step layer workflows.

## Bridge commands
- `harness-gimp bridge start [--host <ip>] [--port <int>]`
- `harness-gimp bridge serve [--host <ip>] [--port <int>]`
- `harness-gimp bridge status`
- `harness-gimp bridge stop`
- `harness-gimp bridge verify [--iterations <int>] [--max-failures <int>]`
- `harness-gimp bridge soak [--iterations <int>] [--action <method>] [--action-params-json <json>]`

## Full editing surface
Reference: `docs/human/commands.md`

Agent-relevant commands:
- Project safety: `inspect`, `validate`, `diff`, `snapshot`, `undo`, `redo`, `clone-project`
- Core transforms: `resize`, `crop`, `rotate`, `flip`, `canvas-size`
- Adjustments: `brightness-contrast`, `levels`, `curves`, `hue-saturation`, `color-balance`, `color-temperature`, `invert`, `desaturate`
- Filters: `blur`, `gaussian-blur`, `sharpen`, `unsharp-mask`, `noise-reduction`
- Layers: `layer-list`, `layer-add`, `layer-remove`, `layer-rename`, `layer-opacity`, `layer-blend-mode`, `layer-duplicate`, `layer-merge-down`, `layer-reorder`
- Selections/masks: `select-all`, `select-none`, `invert-selection`, `feather-selection`, `select-rectangle`, `select-ellipse`, `add-layer-mask`, `apply-layer-mask`
- Text/annotation: `add-text`, `update-text`, `stroke-selection`
- Batch: `run-macro`, `list-presets`, `apply-preset`

## Parameter compatibility notes
- `curves --points-json` accepts either `[{ "x": 0, "y": 0 }, ...]` or `[[0,0], ...]`.
- `add-layer-mask`, `apply-layer-mask`, `update-text` accept `--layer-index` and `--layer-id` aliases.
- `add-text --font` falls back to current GIMP context font if named font is unavailable.

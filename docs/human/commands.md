# Commands

## Bridge
- `harness-gimp bridge serve [--host <ip>] [--port <int>]`
- `harness-gimp bridge start [--host <ip>] [--port <int>]`
- `harness-gimp bridge stop`
- `harness-gimp bridge status`
- `harness-gimp bridge verify [--iterations <int>] [--max-failures <int>]`
- `harness-gimp bridge soak [--iterations <int>] [--action <method>] [--action-params-json <json>]`
  Note: `bridge start` persists the selected URL/port for later commands unless `HARNESS_GIMP_BRIDGE_URL` is set. Use `HARNESS_GIMP_STATE_DIR` to override state-file location.

## System
- `harness-gimp actions`
- `harness-gimp doctor [--verbose]`
- `harness-gimp version`
- `harness-gimp plan-edit <image> <action> [--params-json <json>]`

## Project and Safety
- `harness-gimp open <image>`
- `harness-gimp save <image> <output>`
- `harness-gimp export <image> <output>`
- `harness-gimp montage-grid --images-json <json-list> --rows <int> --cols <int> --tile-width <int> --tile-height <int> --output <path> [--gutter <int>] [--background <hex>] [--fit-mode cover|contain]`
- `harness-gimp clone-project <source> <target> [--overwrite]`
- `harness-gimp inspect <image>`
- `harness-gimp validate <image>`
- `harness-gimp diff <source> <target>`
- `harness-gimp snapshot <image> <description>`
- `harness-gimp undo <image>`
- `harness-gimp redo <image>`

## Transform
- `harness-gimp resize <image> --width <int> --height <int> [--output <path>]`
- `harness-gimp crop <image> --x <int> --y <int> --width <int> --height <int> [--output <path>]`
- `harness-gimp crop-center <image> --width <int> --height <int> [--output <path>]`
- `harness-gimp rotate <image> --degrees <90|180|270> [--output <path>]`
- `harness-gimp flip <image> --axis horizontal|vertical [--output <path>]`
- `harness-gimp canvas-size <image> --width <int> --height <int> [--offset-x <int>] [--offset-y <int>] [--output <path>]`

## Tone and Color
- `harness-gimp brightness-contrast <image> [--brightness <float>] [--contrast <float>] [--layer-index <int>] [--output <path>]`
- `harness-gimp levels <image> [--black <float>] [--white <float>] [--gamma <float>] [--layer-index <int>] [--output <path>]`
- `harness-gimp curves <image> [--channel <value|red|green|blue|alpha>] --points-json <json> [--layer-index <int>] [--output <path>]`
- `harness-gimp hue-saturation <image> [--hue <float>] [--saturation <float>] [--lightness <float>] [--layer-index <int>] [--output <path>]`
- `harness-gimp color-balance <image> [--cyan-red <float>] [--magenta-green <float>] [--yellow-blue <float>] [--transfer-mode <str>] [--layer-index <int>] [--output <path>]`
- `harness-gimp color-temperature <image> --temperature <float> [--layer-index <int>] [--output <path>]`
- `harness-gimp invert <image> [--layer-index <int>] [--output <path>]`
- `harness-gimp desaturate <image> [--mode <luma|average|lightness>] [--layer-index <int>] [--output <path>]`

## Filters
- `harness-gimp blur <image> [--radius <float>] [--layer-index <int>] [--output <path>]`
- `harness-gimp gaussian-blur <image> [--radius-x <float>] [--radius-y <float>] [--layer-index <int>] [--output <path>]`
- `harness-gimp sharpen <image> [--radius <float>] [--amount <float>] [--layer-index <int>] [--output <path>]`
- `harness-gimp unsharp-mask <image> [--radius <float>] [--amount <float>] [--threshold <float>] [--layer-index <int>] [--output <path>]`
- `harness-gimp noise-reduction <image> [--strength <int>] [--layer-index <int>] [--output <path>]`

## Layers
- `harness-gimp layer-list <image>`
- `harness-gimp layer-add <image> --name <str> [--position <int>] [--output <path>]`
- `harness-gimp layer-remove <image> --layer-index <int> [--output <path>]`
- `harness-gimp layer-rename <image> --layer-index <int> --name <str> [--output <path>]`
- `harness-gimp layer-opacity <image> --layer-index <int> --opacity <0-100> [--output <path>]`
- `harness-gimp layer-blend-mode <image> --layer-index <int> --mode <name> [--output <path>]`
- `harness-gimp layer-duplicate <image> --layer-index <int> [--position <int>] [--output <path>]`
- `harness-gimp layer-merge-down <image> --layer-index <int> [--output <path>]`
- `harness-gimp layer-reorder <image> --layer-index <int> --index <int> [--output <path>]`

## Selection and Masks
- `harness-gimp select-all <image> [--output <path>]`
- `harness-gimp select-none <image> [--output <path>]`
- `harness-gimp invert-selection <image> [--output <path>]`
- `harness-gimp feather-selection <image> --radius <float> [--output <path>]`
- `harness-gimp select-rectangle <image> --x <int> --y <int> --width <int> --height <int> [--output <path>]`
- `harness-gimp select-ellipse <image> --x <int> --y <int> --width <int> --height <int> [--output <path>]`
- `harness-gimp add-layer-mask <image> --layer-index <int> [--layer-id <int>] [--mode <str>] [--output <path>]`
- `harness-gimp apply-layer-mask <image> --layer-index <int> [--layer-id <int>] [--output <path>]`

## Text and Annotation
- `harness-gimp add-text <image> --text <str> --x <int> --y <int> [--font <str>] [--size <float>] [--color <hex>] [--output <path>]`
- `harness-gimp update-text <image> --layer-index <int> [--layer-id <int>] --text <str> [--output <path>]`
- `harness-gimp stroke-selection <image> --width <float> [--color <hex>] [--layer-index <int>] [--output <path>]`

## Macros and Presets
- `harness-gimp run-macro <image> --macro <path-or-json-list> [--params-json <json>]`
- `harness-gimp list-presets`
- `harness-gimp apply-preset <image> <preset-name>`

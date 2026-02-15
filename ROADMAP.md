# END.md

Comprehensive feature target for a GIMP-equivalent CLI package.

Goal: if implemented, a user can perform essentially all GIMP workflows from terminal commands, scripts, CI, and agents.

Status legend (audit date: 2026-02-15):
- [implemented] Directly supported by current CLI/bridge behavior.
- [partial] Some related support exists, but not full GIMP-equivalent coverage.
- [missing] Not currently supported.

## 1. CLI Foundations

- [implemented] Stable root command (for example: `harness-gimp`)
- [partial] Consistent subcommand grammar (`<domain> <action>`)
- [implemented] JSON output mode for all commands
- [missing] Human-readable output mode for all commands
- [partial] `--help` on every command with examples
- [missing] Dry-run mode that validates without mutating files
- [missing] Global `--input`, `--output`, `--overwrite`, `--force` flags
- [missing] Global `--format` and `--quality` flags where applicable
- [partial] Global `--profile`/`--preset` flag to apply saved settings
- [missing] Global `--seed` for deterministic randomized operations
- [partial] Global `--verbose`, `--quiet`, `--log-file` controls
- [implemented] Rich error codes and machine-readable diagnostics
- [partial] Command alias support
- [missing] Auto-completion scripts (bash, zsh, fish, PowerShell)

## 2. Project and Session Management

- [partial] Create/open/save project documents (`.xcf`)
- [partial] Save-as and versioned save
- [partial] Auto-backup and crash recovery files
- [implemented] History snapshots and named checkpoints
- [implemented] Undo/redo stack control from CLI
- [missing] Clear history and compact project
- [missing] Project-level settings (units, precision, color management)
- [partial] Multi-document session orchestration
- [missing] Locking to prevent concurrent write corruption

## 3. File IO and Formats

- [partial] Import common raster formats (PNG, JPEG, TIFF, WebP, BMP, GIF, HEIF/AVIF)
- [missing] Import RAW via external converter bridge
- [partial] Import PDF and multi-page assets
- [partial] Import SVG/PS/EPS with rasterization options
- [missing] Import from clipboard-like temporary source files
- [partial] Export all major raster formats with advanced options
- [missing] Export ICO/CUR and multi-resolution outputs
- [missing] Export animated formats (GIF/WebP/APNG)
- [partial] Export layered formats where supported
- [partial] Bulk import/export with file globs and manifests
- [partial] Metadata read/write at import/export (EXIF, XMP, IPTC)
- [partial] Preserve or strip metadata policies
- [missing] ICC profile preserve/convert/assign on export

## 4. Canvas and Image-Level Operations

- [missing] Create new image from dimensions, color mode, fill
- [implemented] Resize image with interpolation controls
- [partial] Scale to fit/cover exact bounds
- [partial] Crop by box, center, content-aware bounds, or guides
- [partial] Canvas size change with anchor and fill policy
- [partial] Rotate image (arbitrary angle and 90-degree steps)
- [implemented] Flip image horizontal/vertical
- [missing] Shear/perspective on image scope
- [missing] Change precision (8/16/32-bit integer/float)
- [missing] Convert image modes (RGB, grayscale, indexed)
- [partial] Flatten image or merge visible layers
- [implemented] Duplicate image or clone with references

## 5. Layer System (Core GIMP Parity)

- [implemented] Create/delete/rename/reorder layers
- [missing] Layer groups create/move/nest/ungroup
- [partial] Duplicate layers and linked duplicates
- [missing] Show/hide and lock (pixels/position/alpha)
- [partial] Set active layer and batch target selectors
- [implemented] Set opacity and blend/composite mode
- [missing] Set layer size/offset and auto-crop to content
- [missing] Add/remove alpha channel
- [partial] Merge down, merge group, merge visible with options
- [missing] Anchor floating selections
- [missing] Create from selection/clipboard/file
- [missing] Layer alignment/distribution tools
- [partial] Layer style-like operations as scripted macros

## 6. Masks, Channels, and Alpha

- [partial] Add/edit/apply/delete layer masks
- [partial] Initialize masks from selection/alpha/grayscale/copy
- [missing] Invert and refine masks
- [missing] Channel create/delete/rename/reorder
- [missing] Channel to selection and selection to channel
- [missing] Save/load alpha masks from files
- [missing] Quick mask operations
- [missing] Per-channel arithmetic operations

## 7. Selections

- [partial] Rectangle/ellipse/free/polygon/path-based selections
- [missing] Select by color with threshold and feather
- [missing] Fuzzy select (magic wand) with contiguous options
- [missing] Foreground select pipeline from seed data
- [partial] Grow/shrink/border/invert selections
- [partial] Feather and sharpen selection edges
- [missing] Intersect/add/subtract/xor selection combine modes
- [partial] Select all/none/float
- [missing] Save/load named selections
- [missing] Selection transforms independent of layer pixels

## 8. Paths and Vector Tools

- [missing] Create/edit/delete Bézier paths
- [missing] Path import/export (SVG paths)
- [missing] Path to selection and selection to path
- [missing] Stroke path with brush/paint dynamics
- [missing] Fill path and offset/simplify path
- [missing] Path boolean operations where supported

## 9. Paint, Draw, and Fill Tooling

- [missing] Paint brush with brush asset, spacing, hardness, dynamics
- [missing] Pencil and airbrush parameterized strokes
- [missing] Ink and MyPaint brush support if available
- [missing] Eraser with alpha and hard/soft controls
- [missing] Bucket fill by FG/BG/pattern with threshold
- [missing] Gradient fill linear/radial/etc with stops
- [missing] Clone and heal from defined source points
- [missing] Smudge, dodge/burn, blur/sharpen tools
- [missing] Perspective clone behavior
- [missing] Warp transform brush-like operations
- [missing] Symmetry/mirror painting modes
- [missing] Scripted stroke playback from vector coordinates

## 10. Text and Typography

- [implemented] Create text layers with font family/style/size
- [missing] Paragraph text boxes with wrapping
- [missing] Kerning, tracking, baseline shift, line spacing
- [missing] Justification and alignment controls
- [missing] Text on path workflows
- [missing] Convert text to path and path to text where possible
- [missing] Font discovery/list/install helpers
- [missing] OpenType feature toggles where backend supports

## 11. Transform Tools

- [missing] Translate/scale/rotate layer or selection
- [missing] Unified transform pipeline
- [missing] Perspective and cage transform operations
- [missing] Handle transform matrices directly
- [missing] Numeric transform with pivots and bounds anchors
- [missing] Repeat last transform exactly

## 12. Color, Tone, and Exposure

- [implemented] Brightness-contrast
- [implemented] Levels and curves (per channel)
- [partial] Hue-saturation and colorize
- [partial] Color balance and channel mixer
- [missing] Shadows-highlights and exposure
- [partial] Desaturate variants and monochrome mix
- [missing] Threshold/posterize
- [partial] White balance and temperature/tint controls
- [partial] Invert and value invert
- [missing] Color lookup table (LUT) apply/export
- [missing] Sample/read color at coordinates
- [missing] Palette quantization and indexed conversion controls

## 13. Filters and Effects (GEGL/PDB Coverage)

- [missing] Full GEGL operation listing and invocation by name
- [missing] Parameter introspection for every filter
- [partial] Blur family (gaussian, motion, lens, selective)
- [partial] Noise add/reduce and despeckle tools
- [partial] Sharpen/unsharp/high-pass tools
- [missing] Distortions (lens, ripple, wave, polar, map object)
- [missing] Artistic/stylize filters
- [missing] Edge detect family
- [missing] Light and shadow effects
- [missing] Generic convolution kernels
- [missing] Frequency separation workflow helpers
- [missing] Filter stacking with named pipelines
- [missing] Non-destructive filter parameter serialization

## 14. Compositing and Blend Control

- [partial] Complete blend mode support matching GIMP
- [missing] Composite space and precision settings
- [missing] Blend-if style thresholding if available
- [missing] Per-layer clipping/masking behavior
- [missing] Advanced merge rules (visible, linked, pass-through group)
- [missing] Alpha compositing diagnostics

## 15. Guides, Grids, Snapping, Layout

- [missing] Add/remove/move horizontal and vertical guides
- [missing] Add guides by percentage or offsets
- [missing] Grid spacing/subdivisions/style controls
- [missing] Snap settings for guides/grid/path/bounds
- [missing] Slice helper commands from guides
- [missing] Safe area and template overlays as metadata

## 16. Animation and Multi-Frame Workflows

- [missing] Frame-as-layer editing model support
- [missing] Timeline-like ordering and per-frame delay settings
- [missing] Onion-skin style preview generation
- [missing] Tween/interpolation helper scripts
- [missing] Export optimized GIF/WebP/APNG animations
- [missing] Sprite sheet import/export tools

## 17. Assets and Resources

- [missing] Brushes list/import/export/create/edit
- [missing] Patterns list/import/export/create
- [missing] Gradients list/import/export/edit
- [missing] Palettes list/import/export/edit
- [partial] Dynamics and tool preset management
- [missing] Resource search by tags and properties
- [missing] Isolated per-project resource bundles

## 18. Plugin and Procedure Integration

- [partial] Discover/list all available procedures
- [missing] Introspect procedure arguments and defaults
- [missing] Invoke legacy PDB procedures safely
- [missing] Invoke GEGL ops directly
- [missing] Plugin sandboxing and trust controls
- [missing] Script-Fu/Python-Fu bridge execution
- [missing] Install/uninstall/enable/disable plugins via CLI
- [missing] Plugin compatibility reporting (version/API)

## 19. Batch, Automation, and Pipelines

- [partial] Run command pipelines from YAML/JSON manifests
- [partial] Apply operation chains across file batches
- [missing] Conditional processing rules (if width > X, etc.)
- [partial] Parameter templating with variables
- [missing] Parallel batch execution with worker limits
- [missing] Resume failed jobs from checkpoints
- [partial] Deterministic run logs and replay files
- [partial] CI-friendly non-interactive mode with strict exit codes

## 20. Inspection and Analysis

- [partial] Inspect image dimensions, mode, precision, profiles
- [partial] Inspect layer tree and properties
- [missing] Histogram and channel statistics
- [implemented] Difference metrics between two images
- [missing] Perceptual hash and similarity checks
- [missing] Edge/blur/noise analysis summaries
- [missing] Detect transparent bounds and content box
- [missing] Report invalid/missing fonts and linked assets

## 21. Color Management

- [missing] ICC profile list/install/select
- [missing] Assign vs convert profile commands
- [missing] Soft proof profile and rendering intent controls
- [missing] Black point compensation toggles
- [missing] Monitor/display profile awareness in preview renders
- [missing] Gamut warnings and out-of-gamut masks

## 22. Metadata and Provenance

- [partial] Read/write EXIF/XMP/IPTC tags
- [missing] Strip private metadata profiles for privacy
- [partial] Embed operation history into sidecar files
- [partial] Reproducible manifest export of full edit pipeline
- [missing] Content provenance (C2PA-like) hooks where available

## 23. Preview and Render Outputs

- [partial] Generate before/after preview images
- [implemented] Contact sheets and comparison grids
- [missing] Render thumbnails at multiple sizes
- [missing] Fast proxy preview mode for heavy files
- [missing] Render specific layers/groups to output targets

## 24. Performance and Reliability

- [missing] Tile cache and memory controls
- [missing] CPU/GPU backend selection where available
- [missing] Progress events and cancellable operations
- [partial] Timeout controls for long-running procedures
- [partial] Safe temp-file handling and cleanup
- [partial] Robust error recovery for partially failed pipelines
- [partial] Cross-platform parity (Windows/macOS/Linux)

## 25. Security and Safety

- [missing] Path traversal protections for output paths
- [missing] Explicit allowlist for external script execution
- [missing] Safe handling of untrusted image files
- [missing] Resource limits to prevent hostile file exhaustion
- [missing] Signed plugin verification (optional advanced mode)

## 26. Developer Experience and Extensibility

- [missing] Typed SDK for Python and JS wrappers
- [partial] OpenAPI/JSON schema for CLI command contracts
- [partial] Stable versioned command API policy
- [partial] Test fixtures for golden image regression
- [missing] Plugin authoring templates
- [missing] Event hooks/webhooks for external orchestration
- [missing] Command recording from interactive sessions to CLI scripts

## 27. Documentation Requirements

- [partial] Full command reference with parameter tables
- [missing] Cookbook for common GIMP-equivalent tasks
- [missing] Migration guide: GUI action -> CLI command mapping
- [partial] Troubleshooting guide by error code
- [missing] Performance tuning and memory guide
- [partial] Reproducibility and deterministic usage guide

## 28. Parity Tracking

- [missing] GIMP feature parity matrix (GUI feature to CLI command)
- [partial] Status labels: not started / partial / complete / blocked
- [partial] Backend capability notes per OS and GIMP version
- [missing] Automated parity test suite with expected outputs
- [missing] Public changelog section for parity milestones

## Suggested Command Namespace Shape

- `project *`
- `file *`
- `image *`
- `layer *`
- `mask *`
- `channel *`
- `select *`
- `path *`
- `paint *`
- `text *`
- `transform *`
- `color *`
- `filter *`
- `guide *`
- `anim *`
- `asset *`
- `plugin *`
- `batch *`
- `inspect *`
- `profile *`
- `meta *`
- `render *`
- `history *`

This list is intentionally expansive. Treat it as the end-state target and implement in milestones.

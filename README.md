# harness-gimp

Agent-first Python package for safe, scriptable image edits with GIMP.

- JSON-first CLI for LLM/tooling use
- Bridge-first architecture
- GIMP 3 batch execution backend
- Validation and deterministic outputs

## Install

```bash
pip install harnessgg-gimp
```

## Quick Start

```bash
harness-gimp bridge start
harness-gimp doctor
harness-gimp inspect input.jpg
harness-gimp resize input.jpg --width 1024 --height 768 --output resized.png
harness-gimp crop resized.png --x 0 --y 0 --width 800 --height 600 --output cropped.png
harness-gimp crop-center resized.png --width 800 --height 800 --output centered.png
harness-gimp export input.jpg output.webp
harness-gimp bridge status
```

All commands print one JSON object to stdout.

Note: layer-edit commands are most reliable on `.xcf` working files.
Tip: prefer `harness-gimp` or `harnessgg-gimp` CLI entrypoints over `python -m harness_gimp` in mixed environments.
Tip: `bridge start --port ...` persists the bridge URL for later commands; override anytime with `HARNESS_GIMP_BRIDGE_URL`. Set `HARNESS_GIMP_STATE_DIR` to customize where bridge state files are stored.

## Docs

- Human commands: `docs/human/commands.md`
- LLM quickstart: `docs/llm/quickstart.md`
- LLM command spec: `docs/llm/command-spec.md`
- LLM bridge protocol: `docs/llm/bridge-protocol.md`
- LLM response schema: `docs/llm/response-schema.json`
- LLM error codes: `docs/llm/error-codes.md`

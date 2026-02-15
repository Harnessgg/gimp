# LLM Quickstart

1. Start bridge:
   `harness-gimp bridge start`
2. Check environment:
   `harness-gimp doctor`
3. Inspect source:
   `harness-gimp inspect input.jpg`
4. Apply edit:
   `harness-gimp resize input.jpg --width 1024 --height 1024 --output out.png`
5. Export final:
   `harness-gimp export out.png final.webp`
6. For layer workflows, convert to XCF first:
   `harness-gimp export out.png edit.xcf`

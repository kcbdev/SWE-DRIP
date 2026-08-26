# SWE Drip — Design Style Library (inspiration source for the Design Agent)

> Pipeline roles (layered, per founder 2026-08-25):
> **1. AI Graphic Design** — `.agents/skills/ai-graphic-design/SKILL.md` (Creative Direction): tool-selection matrix (Recraft SVG, Midjourney moodboards, Nano Banana photoreal mockups, vectorizer, bg removal, upscaler), briefing frameworks (RCAO, StoryBrand), typography/composition, IP safety. Sets DIRECTION + prompt quality.
> **2. T-Shirt Design** — `.agents/skills/tshirt-design-generation/SKILL.md` (T-Shirt Designer): print-method specs (screen print 1-6 spot colors / DTG full-color / sublimation / heat transfer / vinyl), transparent-export rules, typography/vintage/minimal/illustration styles, variations. Engine: each::sense API (`EACHLABS_API_KEY`, founder-set) OR the OpenRouter image models below.
> **3. This file** — SWE Drip brand rules (2-color, named styles, prompts).
> **4. Image generation model** — table below (native-alpha verified).

## Background treatment rules (CRITICAL for POD)

| Treatment | When | How |
|---|---|---|
| **TRANSPARENT** (default) | Any design that should print directly on the shirt | Generate with `openai/gpt-5-image-mini` (native alpha) + "transparent background, PNG alpha" prompt → verify PNG colorType 6. The print lands on EVERY shirt color with no sticker box. |
| **BADGE / PATCH** | Deliberate "printed patch" look (e.g. `>_` on a rounded dark patch) | Keep the patch shape as the art itself (rounded rectangle), background transparent AROUND it. |
| **FULL BLEED** | All-over prints (rare) | Document only; DTG front-back preferred. |

## Image model (verified Aug 2026)

| Model | Alpha | Price (prompt $/M) | Notes |
|---|---|---|---|
| **openai/gpt-5-image-mini** | ✅ native RGBA | ~$0.0025 | **PRIMARY** — real alpha mask (verified 88.6% transparent on a text render), text legible, ~1024² |
| **seedream 5.0 lite** (creative) | ⚠️ PNG via sandbase.ai (`output_format:"png"`) | sandbase pricing | **Creative engine** — high-quality illustration/art. OpenRouter flattens it to JPEG (verified); use direct sandbase API (`scripts/seedream-gen.js`, `SANDBASE_API_KEY`) with output_format png. Alpha-capability pending key test — transparency prompt included; if RGB, run `scripts/bg-remove` chroma-key. |
| **sourceful/riverflow-v2.5-fast** | ❌ WebP VP8 lossy (no alpha) | ~$0.019 | Founder-picked for tee design — fast, strong art; alpha missing → only for solid-BG or badge designs, or convert via webp→png (needs converter) |
| google/gemini-3.1-flash-image | ❌ flattens | $0.0005 | Fallback — needs `node scripts/png-transparent.js` after render |
| google/gemini-3.1-flash-lite-image | ❌ flattens | $0.00025 | Cheapest, same fallback |
| google/gemini-3-pro-image | ❓ not tested | $0.002 | higher quality alternative |
| openai/gpt-5-image | ❓ not tested | $0.01 | highest quality |

FLUX models: no longer on OpenRouter (verified 0). Registry `flux.2-pro` is stale — treat gpt-5-image-mini as the runtime image model.

**Post-render verification (always):** PNG colorType must be 6 (RGBA). If 2 (RGB) → run `scripts/png-transparent.js` (alpha = luminance key) as fallback. 

## Style directions (choose one per design + never mix >2)

### 1. Terminal Log (proven — text-forward)
Flat monospace production log; the joke is in the type. Green #00FF41 on black art;
transparent background. OPTIONALLY render verbatim app logs that corrupt at the
punchline. Prompt: "flat production-log screenshot, JetBrains Mono Bold, green
#00FF41 mono glyphs, corrupting FATAL at the punchline, centered, print-safe."

### 2. Terminal Glyph (logo-forward — the `>_` language)
Single bold terminal glyph as the hero: `>_`, `$`, `#`, `exit`, `0/1`, `&&`, or a
composed glyph. Studio-grade mark: flat, centered, minimal. Good for badges or
big front prints. Prompt: "single bold terminal prompt glyph, flat vector mark,
centered, minimal, high contrast."

### 3. Pixel-Sprite (retro-dec)
8/16-bit sprite composition — a compressed cat, a rocket, or a debugger ghost
exploding into pixels. Prompt: "8-bit pixel art sprite, limited palette, CRT
green on transparent, crisp square pixels, retro game composition."

### 4. Flat Vector Scene (graphic narrative)
A single-scene illustrated gag in flat vector style: a tiny dev in a terminal
glow, a server smoking, a pile of `git stash` debris. Prompt: "flat vector
illustration, minimal shapes, 2-3 colors max, negative space, no gradients,
story in one scene."

### 5. Glitch / Corruption (texture)
Signal noise, scanlines, bit-crush, VHS artifacts around a wordmark. Use
sparingly (readability first). Prompt: "glitch artifact texture around bold
mono wordmark, scanlines, bit-crush, subtle, readable text center."

### 6. ASCII Mosaic (big-image-from-characters)
Shape built from characters (ASCII art scaled up). Prompt: "large ASCII-art
mosaic forming a simple icon, monospace, green on transparent, crisp."

### 7. Doodle / Hand-Drawn (community-sticker tier)
Mono-line doodle with dry dev humor caption. Prompt: "single-color line doodle,
marker weight, minimal doodle, small caption under."

## Prompt template (Design Agent uses this shape)

```
Style: <style-1 (or NONE)>
Subject: <exact iconography>
Text: "<exact lines — short, verbatim>"
Palette: <ink #00FF41 ONLY unless style says otherwise> on transparent
Composition: centered | badge | grid
Rendering: flat, no gradients/shadows/textures beyond style, 2048x2048 print-safe
Background: TRANSPARENT (default) | BADGE (rounded patch kept, rest transparent)
```

## Quality rules
- Text ≤ 6 words when text-forward; longer text only for Terminal Log style and
  ONLY if the render is legible (image models garble long text — the
  transparentizer + 1024px+ art mitigate; if a render fails legibility, drop to
  the punchline line only).
- Never mix green-on-black art with white/red ink; the brand is 2-color.
- Graphics must still carry the "software" story — no generic merch art.
- Validate: PNG 1024x1024+, colorType 6 (RGBA) after transparentizer, < 10MB.

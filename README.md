# Faisal Mosque — Procedural Voxel Day-Night Scene

An interactive, fully self-contained Three.js scene of the **Faisal Mosque Ensemble,
Islamabad**, built as a procedural voxel model with a complete **day-night cycle** —
the sun rises behind the Margalla Hills with golden-hour lighting, dusk into a
moonlit starfield, and a full noon.

## ▶ Live demo

**[Open the scene →](https://saadharis.github.io/faisal-mosque-voxel/)**

*(Runs entirely offline — Three.js is inlined, no CDN, no server. Needs a modern
browser with WebGL + ES-module importmaps: Chrome / Edge / Firefox / Safari 16+.)*

## Controls

- **Time-of-day slider** — scrub 00:00 → 24:00
- **Presets** — Sunrise · Golden hour · Noon · Dusk · Night
- **Play / Pause** — animate the full cycle
- **Auto-orbit** — slow cinematic flyaround
- **Drag** = orbit · **Scroll** = zoom · **Right-drag** = pan

## Files

| File | What it is |
|---|---|
| `index.html` | The scene — fully offline (Three.js inlined as base64, ~1.9 MB) |
| `cdn-version.html` | Lighter version (~177 KB) that pulls Three.js from a CDN |
| `faisal_mosque.vox` | The MagicaVoxel model (117,514 voxels, 32-colour palette) |
| `golden-hour.png` / `night.png` | Preview stills |

## How it was built

A single-file, stdlib-only Python generator produces the voxel model (octagonal
prayer hall, tent-shell roof, four pencil minarets with crescent finials, courtyard,
water pools, gardens, Gaussian Margalla Hills) and self-validates it against 24
structural checks. Surface voxels are culled and packed into the HTML; the Three.js
renderer uses instanced meshes, a custom sky-dome shader, directional sun/moon
lighting with shadow maps, ACES tone mapping, and a warm material grade for golden hour.

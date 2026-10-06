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

## The pipeline (`src/`)

Everything is reproducible from source. The build is a 4-stage chain, all Python 3
(voxel generator is **stdlib-only** — no numpy/Pillow):

```bash
cd src

# 1. Generate the voxel model + run 24 self-validation checks  -> 24/24 PASS
python faisal_mosque_voxel.py --params params_final.json --tag final

# 2. Cull interior voxels, pack surface voxels (117,514 -> 59,518) -> scene_data.json
python export_scene_data.py

# 3. Build the self-contained Three.js day-night scene (CDN importmap) -> ~177 KB
python gen_scene.py

# 4. Inline Three.js as base64 -> fully-offline single file -> ~1.9 MB
python build_standalone.py
```

| File | Role |
|---|---|
| `faisal_mosque_voxel.py` | Procedural voxel generator + `.vox` writer + stdlib PNG renderer + 24 structural checks (C1–C24) |
| `params_final.json` | The converged parameter set (spec-pinned + tuned free knobs) |
| `export_scene_data.py` | Surface-voxel culling + zlib/base64 packing |
| `gen_scene.py` | Three.js scene generator (instanced meshes, sky-dome shader, sun/moon lighting, day-night cycle) |
| `build_standalone.py` | Inlines the CDN deps into a zero-network single file |
| `three.module.js`, `OrbitControls.js` | Pinned Three.js r160 deps used by stage 4 |
| `faisal_mosque_vfinal_stats.json` | Proof: 24/24 checks, 117,514 voxels, sha256 `0eb87940…` |

The generator is deterministic: the same params reproduce a byte-identical `.vox`
(verified by the C19/C20 round-trip checks), and the full chain reproduces the
published `index.html` byte-for-byte (sha256 `9832b145…`).

### The 24 checks

Octagon invariance, not-a-dome area ratio, ridge-not-spike taper, minaret monotonic
taper, crescent connectivity, hill height bounds, door/opening counts, connected-component
counts, out-of-bounds, voxel totals, `.vox` parse round-trip, and PNG render sanity —
computed from the grid, never hard-coded.

#!/usr/bin/env python3
"""Generate a self-contained Three.js day-night scene HTML from scene_data.json."""
import json

data = json.load(open("scene_data.json"))
b64 = data["voxels_b64"]
palette = data["palette"]
GX, GY, GZ = data["grid"]

html = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Faisal Mosque Ensemble — Day-Night Voxel Scene</title>
<style>
  :root { color-scheme: dark; }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  html, body { width: 100%; height: 100%; overflow: hidden; background: #000;
    font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
  #app { position: fixed; inset: 0; }
  canvas { display: block; }
  #hud {
    position: fixed; left: 16px; bottom: 16px; z-index: 10;
    background: rgba(12,14,20,0.62); backdrop-filter: blur(10px);
    border: 1px solid rgba(255,255,255,0.12); border-radius: 14px;
    padding: 14px 16px; color: #eef1f6; width: min(440px, calc(100vw - 32px));
    box-shadow: 0 8px 30px rgba(0,0,0,0.45);
  }
  #hud h1 { font-size: 14px; font-weight: 650; letter-spacing: .02em; margin-bottom: 2px; }
  #hud .sub { font-size: 11px; color: #9aa4b2; margin-bottom: 10px; }
  .row { display: flex; align-items: center; gap: 10px; margin: 8px 0; }
  .row label { font-size: 11px; color: #c4ccd8; min-width: 74px; }
  input[type=range] { flex: 1; accent-color: #ffb454; }
  .btns { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
  button {
    font: inherit; font-size: 12px; color: #eef1f6; cursor: pointer;
    background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.16);
    border-radius: 9px; padding: 7px 11px; transition: background .15s, transform .05s;
  }
  button:hover { background: rgba(255,180,84,0.22); }
  button:active { transform: translateY(1px); }
  button.primary { background: rgba(255,180,84,0.30); border-color: rgba(255,180,84,0.5); }
  #clock { font-variant-numeric: tabular-nums; font-size: 13px; color: #ffd9a0; min-width: 64px; text-align: right; }
  #phase { font-size: 11px; color: #ffb454; min-width: 96px; }
  #hint { position: fixed; right: 16px; top: 14px; z-index: 10; font-size: 11px;
    color: #8b95a3; background: rgba(12,14,20,0.5); padding: 6px 10px; border-radius: 8px; }
  #loading { position: fixed; inset: 0; display: flex; align-items: center; justify-content: center;
    color: #cfd6e0; font-size: 14px; z-index: 20; background: #05070c; }
</style>
</head>
<body>
<div id="app"></div>
<div id="loading">Building voxel scene…</div>
<div id="hint">drag = orbit · scroll = zoom · right-drag = pan</div>
<div id="hud">
  <h1>Faisal Mosque Ensemble — Islamabad</h1>
  <div class="sub">Procedural voxel model · full day-night cycle · sun rises behind the Margalla Hills</div>
  <div class="row">
    <label>Time of day</label>
    <input id="time" type="range" min="0" max="24" step="0.01" value="6.30">
    <span id="clock">06:24</span>
  </div>
  <div class="row">
    <label>Speed</label>
    <input id="speed" type="range" min="0" max="4" step="0.05" value="1">
    <span id="phase">Golden hour</span>
  </div>
  <div class="btns">
    <button id="play" class="primary">⏸ Pause</button>
    <button id="dawn">🌅 Sunrise</button>
    <button id="golden">✨ Golden hour</button>
    <button id="noon">☀ Noon</button>
    <button id="dusk">🌆 Dusk</button>
    <button id="night">🌙 Night</button>
    <button id="orbit">🎥 Auto-orbit</button>
  </div>
</div>

<script type="importmap">
{ "imports": {
  "three": "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js",
  "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/"
}}
</script>

<script type="module">
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const DATA = {
  grid: __GRID__,
  palette: __PALETTE__,
  voxels: "__B64__"
};

// ---- decode packed voxels (x,y,z,paletteIndex) ---------------------------
async function decodeVoxels(b64) {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream('deflate'));
  return new Uint8Array(await new Response(stream).arrayBuffer());
}
const vox = await decodeVoxels(DATA.voxels);
const N = vox.length / 4;
const [GX, GY, GZ] = DATA.grid;
const CX = GX / 2, CZ = GZ / 2;

// ---- renderer / scene / camera -------------------------------------------
const app = document.getElementById('app');
const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;
renderer.outputColorSpace = THREE.SRGBColorSpace;
app.appendChild(renderer.domElement);

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(48, window.innerWidth / window.innerHeight, 0.5, 4000);
// spec framing: south side, looking north toward the Margalla Hills so the
// rising sun crests the ridge dead-center (backlit golden hour)
camera.position.set(60, 55, -180);

const controls = new OrbitControls(camera, renderer.domElement);
controls.target.set(0, 40, 30);
controls.enableDamping = true;
controls.dampingFactor = 0.06;
controls.maxPolarAngle = Math.PI * 0.495;
controls.minDistance = 40;
controls.maxDistance = 700;
controls.update();

// ---- palette helpers ------------------------------------------------------
const pal = DATA.palette.map(c => new THREE.Color(c[0]/255, c[1]/255, c[2]/255));
const WATER = 6, GOLD = 8;

// ---- instanced voxel meshes ----------------------------------------------
const box = new THREE.BoxGeometry(1.02, 1.02, 1.02);

let matteCount = 0, waterCount = 0, goldCount = 0;
for (let i = 0; i < N; i++) {
  const c = vox[i*4 + 3];
  if (c === WATER) waterCount++;
  else if (c === GOLD) goldCount++;
  else matteCount++;
}

const matteMesh = new THREE.InstancedMesh(box, new THREE.MeshStandardMaterial({
  roughness: 0.82, metalness: 0.04 }), matteCount);
const waterMesh = new THREE.InstancedMesh(box, new THREE.MeshPhongMaterial({
  color: 0x2e6e8e, specular: 0xfff0c0, shininess: 90, transparent: true,
  opacity: 0.86, emissive: 0x06202e, emissiveIntensity: 0.35 }), waterCount);
const goldMesh = new THREE.InstancedMesh(box, new THREE.MeshStandardMaterial({
  color: 0xc9a227, roughness: 0.35, metalness: 0.85,
  emissive: 0xc9a227, emissiveIntensity: 0.0 }), goldCount);

matteMesh.castShadow = matteMesh.receiveShadow = true;
waterMesh.receiveShadow = true;
goldMesh.castShadow = true;

const dummy = new THREE.Object3D();
const col = new THREE.Color();
let mi = 0, wi = 0, gi = 0;
for (let i = 0; i < N; i++) {
  const x = vox[i*4], y = vox[i*4+1], z = vox[i*4+2], c = vox[i*4+3];
  dummy.position.set(x - CX, y + 0.5, z - CZ);
  dummy.updateMatrix();
  if (c === WATER) {
    waterMesh.setMatrixAt(wi++, dummy.matrix);
  } else if (c === GOLD) {
    goldMesh.setMatrixAt(gi++, dummy.matrix);
  } else {
    matteMesh.setMatrixAt(mi, dummy.matrix);
    // per-voxel tint jitter for concrete/marble texture
    const j = 0.90 + ((i * 2654435761) % 997) / 997 * 0.12;
    col.copy(pal[c]).multiplyScalar(j);
    matteMesh.setColorAt(mi, col);
    mi++;
  }
}
matteMesh.instanceMatrix.needsUpdate = true;
matteMesh.instanceColor.needsUpdate = true;
waterMesh.instanceMatrix.needsUpdate = true;
goldMesh.instanceMatrix.needsUpdate = true;
scene.add(matteMesh, waterMesh, goldMesh);

// ---- ground plane (catches long golden-hour shadows) --------------------
const ground = new THREE.Mesh(
  new THREE.PlaneGeometry(2400, 2400),
  new THREE.MeshStandardMaterial({ color: 0x2f6a2a, roughness: 1.0 }));
ground.rotation.x = -Math.PI / 2;
ground.position.y = -0.02;
ground.receiveShadow = true;
scene.add(ground);

// ---- sky dome shader -----------------------------------------------------
const skyUniforms = {
  uSunDir: { value: new THREE.Vector3(0, 0, 1) },
  uZenith: { value: new THREE.Color(0x0a1a3a) },
  uHorizon: { value: new THREE.Color(0xff8a3d) },
  uNight: { value: new THREE.Color(0x04060f) },
  uSunTint: { value: new THREE.Color(0xffb454) },
  uSunGlow: { value: 1.0 },
};
const sky = new THREE.Mesh(
  new THREE.SphereGeometry(1800, 32, 16),
  new THREE.ShaderMaterial({
    side: THREE.BackSide, depthWrite: false, uniforms: skyUniforms,
    vertexShader: `varying vec3 vDir; void main(){ vDir = normalize(position);
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }`,
    fragmentShader: `
      varying vec3 vDir;
      uniform vec3 uSunDir, uZenith, uHorizon, uNight, uSunTint;
      uniform float uSunGlow;
      void main(){
        vec3 d = normalize(vDir);
        float h = clamp(d.y*0.5+0.5, 0.0, 1.0);
        float dayMix = smoothstep(-0.12, 0.10, uSunDir.y);
        vec3 zen = mix(uNight, uZenith, dayMix);
        vec3 hor = mix(uNight*1.4, uHorizon, dayMix);
        vec3 sky = mix(hor, zen, pow(h, 0.55));
        // sun glow bloom near the sun direction
        float sd = max(dot(d, normalize(uSunDir)), 0.0);
        float horizonHug = smoothstep(0.30, 0.02, abs(d.y - uSunDir.y));
        float glow = pow(sd, 24.0) * uSunGlow;
        float halo = pow(sd, 5.0) * 0.09 * uSunGlow * (0.35 + 0.65 * horizonHug);
        sky += uSunTint * (glow + halo);
        gl_FragColor = vec4(sky, 1.0);
      }`
  }));
scene.add(sky);

// ---- sun / moon sprites --------------------------------------------------
function makeGlow(color, size, disc) {
  const c = document.createElement('canvas'); c.width = c.height = 128;
  const g = c.getContext('2d');
  if (disc) {
    // crisp celestial disc with a soft halo
    const halo = g.createRadialGradient(64,64,22,64,64,64);
    halo.addColorStop(0, color);
    halo.addColorStop(1, 'rgba(0,0,0,0)');
    g.fillStyle = halo; g.fillRect(0,0,128,128);
    g.fillStyle = 'rgba(255,255,255,0.98)';
    g.beginPath(); g.arc(64,64,26,0,Math.PI*2); g.fill();
  } else {
    const grd = g.createRadialGradient(64,64,0,64,64,64);
    grd.addColorStop(0, 'rgba(255,120,20,1.0)');
    grd.addColorStop(0.30, 'rgba(255,95,15,0.95)');
    grd.addColorStop(0.62, 'rgba(225,60,12,0.35)');
    grd.addColorStop(1, 'rgba(0,0,0,0)');
    g.fillStyle = grd; g.fillRect(0,0,128,128);
  }
  const tex = new THREE.CanvasTexture(c);
  const sp = new THREE.Sprite(new THREE.SpriteMaterial({
    map: tex, blending: THREE.AdditiveBlending,
    depthWrite: false, transparent: true }));
  sp.scale.set(size, size, 1);
  return sp;
}
const sunSprite = makeGlow('rgba(255,110,25,0.95)', 150, false);
const moonSprite = makeGlow('rgba(200,220,255,0.55)', 120, true);
scene.add(sunSprite, moonSprite);

// ---- lights --------------------------------------------------------------
const sun = new THREE.DirectionalLight(0xffffff, 2.0);
sun.castShadow = true;
sun.shadow.mapSize.set(4096, 4096);
sun.shadow.camera.near = 1; sun.shadow.camera.far = 2600;
const S = 1200;
sun.shadow.camera.left = -S; sun.shadow.camera.right = S;
sun.shadow.camera.top = S; sun.shadow.camera.bottom = -S;
sun.shadow.bias = -0.0008;
sun.shadow.normalBias = 0.06;   // kills self-shadow acne on the dense voxel grid
scene.add(sun);
scene.add(sun.target);

const hemi = new THREE.HemisphereLight(0x88aaff, 0x2c3a26, 0.5);
scene.add(hemi);
const ambient = new THREE.AmbientLight(0x223044, 0.35);
scene.add(ambient);

// cool moonlight that turns on after dusk so the marble stays readable at night
const moonLight = new THREE.DirectionalLight(0x9fb8ff, 0.0);
moonLight.castShadow = true;
moonLight.shadow.mapSize.set(1024, 1024);
moonLight.shadow.camera.near = 1; moonLight.shadow.camera.far = 900;
moonLight.shadow.camera.left = -S; moonLight.shadow.camera.right = S;
moonLight.shadow.camera.top = S; moonLight.shadow.camera.bottom = -S;
moonLight.shadow.bias = -0.0008; moonLight.shadow.normalBias = 0.06;
scene.add(moonLight);
scene.add(moonLight.target);

// warm fill that spikes at golden hour (backlight warmth on the marble)
const warmFill = new THREE.DirectionalLight(0xff7a2a, 0.0);
scene.add(warmFill);

// camera-side sky fill so the white marble never crushes to silhouette
const skyFill = new THREE.DirectionalLight(0xbfd4ff, 0.0);
skyFill.position.set(180, 140, -220);
scene.add(skyFill);

// ---- stars ---------------------------------------------------------------
const starGeo = new THREE.BufferGeometry();
const starPos = [];
for (let i = 0; i < 3200; i++) {
  const v = new THREE.Vector3().randomDirection().multiplyScalar(1500);
  if (v.y > 0) starPos.push(v.x, v.y, v.z);
}
starGeo.setAttribute('position', new THREE.Float32BufferAttribute(starPos, 3));
const starMat = new THREE.PointsMaterial({ color: 0xffffff, size: 2.6, sizeAttenuation: false,
  transparent: true, opacity: 0 });
const stars = new THREE.Points(starGeo, starMat);
scene.add(stars);

// ---- day-night cycle -----------------------------------------------------
// t in [0,1): 0=midnight, 0.25=sunrise (behind +Z hills), 0.5=noon, 0.75=sunset
function sunDirAt(t) {
  const el = Math.sin(2 * Math.PI * (t - 0.25));       // elevation -1..1
  const az = Math.PI * (t - 0.25) / 0.5;               // 0 at sunrise (+Z) -> pi at sunset (-Z)
  const ce = Math.cos(el * Math.PI / 2);
  const se = Math.sin(el * Math.PI / 2);
  return {
    dir: new THREE.Vector3(Math.sin(az) * ce, se, Math.cos(az) * ce).normalize(),
    elev: se
  };
}

const cDayZen = new THREE.Color(0x2a6fd0), cDayHor = new THREE.Color(0xbcd4f0);
const cDuskHor = new THREE.Color(0xffa848), cDuskZen = new THREE.Color(0x2c4a7e);
const cNightZen = new THREE.Color(0x04060f), cNightHor = new THREE.Color(0x0a1226);
const cSunNoon = new THREE.Color(0xfff4e0), cSunLow = new THREE.Color(0xff6a1e);
// warm grade applied to the marble itself so golden hour reads GOLD, not pink-white
const cMarbleNeutral = new THREE.Color(1, 1, 1);
const cMarbleGold = new THREE.Color(1.0, 0.50, 0.16);
const tmp = new THREE.Color();

function updateCycle(t) {
  const { dir, elev } = sunDirAt(t);
  const day = THREE.MathUtils.smoothstep(elev, -0.06, 0.22);     // 0 night -> 1 day
  const golden = Math.exp(-Math.pow((elev - 0.08) / 0.22, 2));   // broad warm band near horizon

  // warm grade on the marble itself: gold at golden hour, cool blue at night,
  // neutral at midday. Multiplies the per-instance palette colours.
  matteMesh.material.color.copy(cMarbleNeutral)
    .lerp(cMarbleGold, golden)
    .lerp(new THREE.Color(0.55, 0.62, 0.85), (1 - day) * 0.45);

  // sun light
  sun.position.copy(dir).multiplyScalar(420);
  sun.target.position.set(0, 20, 0);
  tmp.copy(cSunLow).lerp(cSunNoon, THREE.MathUtils.smoothstep(elev, 0.18, 0.5));
  sun.color.copy(tmp);
  sun.intensity = 2.8 * THREE.MathUtils.smoothstep(elev, -0.05, 0.15);

  // warm golden-hour key light from the low sun direction, washing the marble gold
  warmFill.position.copy(dir).multiplyScalar(300);
  warmFill.color.set(0xff8a2a);
  warmFill.intensity = 2.6 * golden;

  // camera-side fill keeps the white marble readable even when backlit,
  // and carries the golden-hour warmth onto the faces the camera sees
  skyFill.intensity = 0.22 + 0.70 * day + 0.85 * golden;
  skyFill.color.copy(cNightHor).lerp(new THREE.Color(0xbfd4ff), day)
    .lerp(new THREE.Color(0xff8a35), golden);

  // hemisphere + ambient (warmed at golden hour so the whole scene glows)
  hemi.color.copy(cNightZen).lerp(cDayZen, day)
    .lerp(new THREE.Color(0xffb060), golden * 0.5);
  hemi.groundColor.copy(cNightHor).lerp(new THREE.Color(0x3a4a30), day)
    .lerp(new THREE.Color(0x4a5a28), golden * 0.4);
  hemi.intensity = 0.28 + 0.55 * day - 0.10 * golden;
  ambient.intensity = 0.20 + 0.30 * day - 0.08 * golden;
  ambient.color.copy(cNightHor).lerp(new THREE.Color(0x33445c), day)
    .lerp(new THREE.Color(0x8a5a30), golden);

  // sky
  skyUniforms.uSunDir.value.copy(dir);
  skyUniforms.uZenith.value.copy(cNightZen).lerp(cDuskZen, day)
    .lerp(cDayZen, THREE.MathUtils.smoothstep(elev, 0.12, 0.4));
  skyUniforms.uHorizon.value.copy(cNightHor).lerp(cDuskHor, golden)
    .lerp(cDayHor, THREE.MathUtils.smoothstep(elev, 0.10, 0.4));
  skyUniforms.uSunTint.value.copy(cSunLow).lerp(cSunNoon, THREE.MathUtils.smoothstep(elev, 0.05, 0.3));
  skyUniforms.uSunGlow.value = 0.2 + 0.5 * golden + 0.2 * day;

  // sun & moon sprites
  sunSprite.position.copy(dir).multiplyScalar(1400);
  sunSprite.material.opacity = 0.85 * THREE.MathUtils.smoothstep(elev, -0.12, 0.02);
  sunSprite.scale.setScalar(70 + 70 * golden);
  // moon: placed in the camera's view basis at a fixed angular offset, so it is
  // guaranteed inside the frustum and beside (not behind) the dome silhouette
  const f = new THREE.Vector3().subVectors(controls.target, camera.position).normalize();
  const rgt = new THREE.Vector3().crossVectors(f, camera.up).normalize();
  const upv = new THREE.Vector3().crossVectors(rgt, f).normalize();
  const moonDir = f.clone().multiplyScalar(1.0)
    .addScaledVector(rgt, 0.55)     // horizontal offset: beside the dome
    .addScaledVector(upv, 0.38)     // vertical offset: above the ridge
    .normalize();
  moonSprite.position.copy(camera.position).addScaledVector(moonDir, 1400);
  moonSprite.material.opacity = THREE.MathUtils.smoothstep(-elev, 0.02, 0.18);
  moonSprite.scale.setScalar(170);

  // stars
  // stars: gone once the sun clears the horizon, full at night
  starMat.opacity = 1 - THREE.MathUtils.smoothstep(elev, -0.10, 0.02);

  // moonlight: cool key light from a high camera-side angle so the marble READS
  // at night (the moon sprite sits behind the mosque for the view, but a literal
  // back-light would crush the camera-facing walls to silhouette)
  moonLight.position.set(camera.position.x * 0.9, 320, camera.position.z * 0.9);
  moonLight.target.position.set(0, 20, 0);
  moonLight.intensity = 1.7 * (1 - day);

  // gold crescents glow after dark
  goldMesh.material.emissiveIntensity = 0.15 + 1.4 * (1 - day) + 0.6 * golden;

  // fog tinted to horizon for atmospheric depth
  if (!scene.fog) scene.fog = new THREE.Fog(0x000000, 700, 2400);
  scene.fog.color.copy(skyUniforms.uHorizon.value);
  renderer.toneMappingExposure = 1.05 + 0.22 * golden;
}

// ---- UI ------------------------------------------------------------------
const timeEl = document.getElementById('time');
const speedEl = document.getElementById('speed');
const clockEl = document.getElementById('clock');
const phaseEl = document.getElementById('phase');
const playBtn = document.getElementById('play');
let playing = false;   // start paused at golden hour for a deterministic first frame
playBtn.textContent = '▶ Play';

function setClockLabel(t) {
  const h = (t * 24) % 24;
  const hh = Math.floor(h), mm = Math.floor((h - hh) * 60);
  clockEl.textContent = String(hh).padStart(2,'0') + ':' + String(mm).padStart(2,'0');
  const { elev } = sunDirAt(t);
  let ph = 'Night';
  if (elev > 0.35) ph = 'Midday';
  else if (elev > 0.12) ph = 'Morning/Afternoon';
  else if (elev > -0.02) ph = (t < 0.5 ? 'Sunrise' : 'Sunset');
  else if (elev > -0.18) ph = 'Twilight';
  phaseEl.textContent = ph;
}
timeEl.addEventListener('input', () => { updateCycle(parseFloat(timeEl.value)/24); setClockLabel(parseFloat(timeEl.value)/24); });
playBtn.addEventListener('click', () => { playing = !playing; playBtn.textContent = playing ? '⏸ Pause' : '▶ Play'; });
function jump(h){ timeEl.value = h; updateCycle(h/24); setClockLabel(h/24); }
document.getElementById('dawn').onclick   = () => jump(6.0);
document.getElementById('golden').onclick = () => jump(6.30);
document.getElementById('noon').onclick   = () => jump(12.0);
document.getElementById('dusk').onclick   = () => jump(18.1);
document.getElementById('night').onclick  = () => jump(22.0);
let autoOrbit = false;
document.getElementById('orbit').onclick = (e) => { autoOrbit = !autoOrbit;
  e.target.classList.toggle('primary', autoOrbit); };

// ---- loop ----------------------------------------------------------------
const clock = new THREE.Clock();
let t = parseFloat(timeEl.value) / 24;
updateCycle(t); setClockLabel(t);
document.getElementById('loading').style.display = 'none';

function animate() {
  requestAnimationFrame(animate);
  const dt = clock.getDelta();
  const speed = parseFloat(speedEl.value);
  if (playing) {
    t = (t + dt * speed / 40) % 1;   // full cycle ~40s at speed 1
    timeEl.value = (t * 24).toFixed(2);
    updateCycle(t); setClockLabel(t);
  }
  if (autoOrbit) {
    const a = dt * 0.12;
    const x = camera.position.x - controls.target.x;
    const z = camera.position.z - controls.target.z;
    camera.position.x = controls.target.x + x * Math.cos(a) - z * Math.sin(a);
    camera.position.z = controls.target.z + x * Math.sin(a) + z * Math.cos(a);
  }
  controls.update();
  renderer.render(scene, camera);
}
animate();

window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});
</script>
</body>
</html>
"""

html = html.replace("__GRID__", json.dumps([GX, GY, GZ]))
html = html.replace("__PALETTE__", json.dumps(palette))
html = html.replace("__B64__", b64)

open("faisal_mosque_scene.html", "w", encoding="utf-8").write(html)
print("wrote faisal_mosque_scene.html", len(html), "bytes")

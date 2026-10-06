#!/usr/bin/env python3
"""Inline the CDN Three.js deps into the scene HTML as base64 data-URL importmap
entries, producing a single fully-offline file (zero network at load)."""
import base64, re, sys

SRC = "faisal_mosque_scene.html"
OUT = "faisal_mosque_scene_standalone.html"

three_b64 = base64.b64encode(open("three.module.js", "rb").read()).decode()
orbit_b64 = base64.b64encode(open("OrbitControls.js", "rb").read()).decode()

html = open(SRC, encoding="utf-8").read()

# Replace the whole importmap block with data-URL entries.
new_map = (
    '<script type="importmap">\n'
    '{ "imports": {\n'
    f'  "three": "data:text/javascript;base64,{three_b64}",\n'
    f'  "three/addons/controls/OrbitControls.js": "data:text/javascript;base64,{orbit_b64}"\n'
    '}}\n'
    '</script>'
)
pat = re.compile(r'<script type="importmap">.*?</script>', re.DOTALL)
if not pat.search(html):
    sys.exit("importmap block not found")
html2 = pat.sub(lambda _: new_map, html, count=1)

# Sanity: no remaining external http(s) import specifiers.
leftovers = re.findall(r'from\s+["\']https?://[^"\']+["\']', html2)
assert not leftovers, f"external imports remain: {leftovers}"

open(OUT, "w", encoding="utf-8").write(html2)
print(f"wrote {OUT}  {len(html2):,} bytes  (was {len(html):,})")
print("external http imports remaining:", len(leftovers))

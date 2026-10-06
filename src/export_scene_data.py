#!/usr/bin/env python3
"""Export the converged voxel model as compact surface-voxel data for the
Three.js day-night scene. Only voxels with at least one empty 6-neighbour are
kept (interior of the hill mass and hidden shell voxels are culled), packed as
4 bytes each (x,y,z,palette_index) and base64-encoded."""
import base64
import json
import zlib
import faisal_mosque_voxel as F

P = json.load(open("params_final.json"))
m = F.Model(P)
g = F.build_grid(m)
GX, GY, GZ = P["GRID_X"], P["GRID_Y"], P["GRID_Z"]

def get(x, y, z):
    if 0 <= x < GX and 0 <= y < GY and 0 <= z < GZ:
        return g[(y * GZ + z) * GX + x]
    return 0

packed = bytearray()
counts = {}
groups = {"matte": 0, "water": 0, "gold": 0}
for y in range(GY):
    for z in range(GZ):
        for x in range(GX):
            c = g[(y * GZ + z) * GX + x]
            if not c:
                continue
            if (get(x+1,y,z) == 0 or get(x-1,y,z) == 0 or
                get(x,y+1,z) == 0 or get(x,y-1,z) == 0 or
                get(x,y,z+1) == 0 or get(x,y,z-1) == 0):
                packed += bytes((x, y, z, c))
                counts[c] = counts.get(c, 0) + 1
                if c == F.IDX["WATER"]:
                    groups["water"] += 1
                elif c == F.IDX["GOLD"]:
                    groups["gold"] += 1
                else:
                    groups["matte"] += 1

# palette RGB for indices 0..14 (index 0 unused)
palette = [[0, 0, 0]]
for name, rgb, a in F.PALETTE:
    palette.append([(rgb >> 16) & 0xFF, (rgb >> 8) & 0xFF, rgb & 0xFF])

b64 = base64.b64encode(zlib.compress(bytes(packed), 9)).decode()
out = {
    "count": len(packed) // 4,
    "groups": groups,
    "palette": palette,
    "grid": [GX, GY, GZ],
    "voxels_b64": b64,
    "compressed": True,
}
json.dump(out, open("scene_data.json", "w"))
print("surface voxels:", out["count"], "groups:", groups)
print("base64 length:", len(b64))

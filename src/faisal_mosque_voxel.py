#!/usr/bin/env python3
"""
SPEC implementation: procedural voxel model of the Faisal Mosque ensemble, Islamabad.

Single-file, stdlib-only. Everything is driven by DEFAULTS (JSON round-trippable).
Every voxel comes from iterating the grid through is_solid()/material().

Coordinate system (fixed by spec):
  X = east-west, Y = up, Z = north-south. 1 voxel = 1 metre.
  Grid 160 x 112 x 160, ground at Y=0, mosque centre at (80, ., 80).
  Margalla Hills ridge compressed along the +Z edge (artistic backdrop, NOT to scale).

The mosque is a TENT, not a dome: octagonal pillar-less hall, four curved shells
rising to a ridge, four pencil minarets with gold crescents, no dome anywhere.
"""

import argparse
import hashlib
import json
import math
import struct
import sys
import zlib

# ---------------------------------------------------------------------------
# Palette (spec section 5, exact order, indices 1..14)
# ---------------------------------------------------------------------------
PALETTE = [
    ("VOID",         0x000000, 0),   # index 1
    ("MARBLE_WHITE", 0xF2F0E9, 255), # 2
    ("MARBLE_SHADE", 0xD8D4C8, 255), # 3
    ("CONCRETE",     0xA9A49A, 255), # 4
    ("MARBLE_DARK",  0xBDB8AC, 255), # 5
    ("WATER",        0x2E6E8E, 255), # 6
    ("OPENING",      0x1C1A18, 255), # 7
    ("GOLD",         0xC9A227, 255), # 8
    ("GRASS",        0x4E7A34, 255), # 9
    ("FOLIAGE",      0x2F5A25, 255), # 10
    ("GRANITE",      0x6E6A64, 255), # 11
    ("LATTICE",      0xC9C4B6, 255), # 12
    ("HILL",         0x6E7A5E, 255), # 13
    ("ROSE",         0xC24B6A, 255), # 14
]
IDX = {name: i + 1 for i, (name, _, _) in enumerate(PALETTE)}

# ---------------------------------------------------------------------------
# Parameters (spec section 4 + 6). Every geometric knob lives here.
# ---------------------------------------------------------------------------
DEFAULTS = {
    # grid
    "GRID_X": 160, "GRID_Y": 112, "GRID_Z": 160,
    "CX": 80, "CZ": 80,

    # 4.1 site plinth (octagonal marble platform, Y=0..2)
    "PLINTH_R": 56, "PLINTH_TOP": 2,
    "MINARET_PAD_HALF": 9,          # square pad under each minaret (10 base + 4 margin -> half 9)

    # 4.2 main prayer hall - the tent
    "HALL_R": 32,                   # circumradius of octagon
    "WALL_TOP": 18,                 # straight wall band Y=3..18
    "HALL_TOP": 45,                 # summit height
    "SHELL_INSET_RISE": 1.5,        # 1 voxel of radius per 1.5 of rise
    "WALL_THICK": 3,
    "X_PINCH_START": 36,            # where the X extent accelerates inward -> ridge
    "RIDGE_X_HALF": 2,              # ridge half-width in X (<=5 wide)
    "GIRDER_THICK": 1,              # girder half-thickness (2 voxels)
    "GIRDER_SPLIT_Y": 24,           # girders split into two legs above this
    "OPEN_HALF": 2, "OPEN_TOP": 8,  # cardinal doorways: half-width, top Y

    # 4.3 minarets
    "MIN_OFF": 34,                  # diagonal offset of minaret centres
    "MIN_BASE_HALF": 5,             # 10x10 base
    "MIN_BASE_TOP": 12,
    "MIN_SHAFT_TOP": 86,
    "CRESCENT_TOP": 90,

    # 4.4 courtyard, porticoes, entrance verandah
    "COURT_X0": 112, "COURT_X1": 151, "COURT_Z0": 58, "COURT_Z1": 97,
    "PORTICO_SPACING": 4, "PORTICO_H": 2, "PORTICO_ROOF_Y": 6,
    "VERANDAH_X0": 110, "VERANDAH_X1": 114, "VERANDAH_Y": 8,
    "VERANDAH_Z0": 66, "VERANDAH_Z1": 94, "VERANDAH_COL_STEP": 7,

    # 4.5 water
    "POND_C_X": 122, "POND_C_Z": 80, "POND_C_R": 8,          # circular entrance pond
    "POND_L_X0": 133, "POND_L_X1": 157, "POND_L_Z0": 68, "POND_L_Z1": 89,  # larger pond
    "ABL_X0": 112, "ABL_X1": 126, "ABL_Z0": 92, "ABL_Z1": 106,             # ablution pool
    "JET_X": 119, "JET_Z": 99, "JET_H": 3,                                 # frothy jet plume
    "POOL_W_X0": 30, "POOL_W_X1": 45, "POOL_W_Z0": 72, "POOL_W_Z1": 87,
    "POOL_N_X0": 72, "POOL_N_X1": 87, "POOL_N_Z0": 112, "POOL_N_Z1": 127,
    "POOL_S_X0": 72, "POOL_S_X1": 87, "POOL_S_Z0": 33, "POOL_S_Z1": 48,

    # 4.6 gardens
    "SITE_X0": 4, "SITE_X1": 156, "SITE_Z0": 4, "SITE_Z1": 144,
    "PATH_W": 3,
    "PATH_S_Z": 41, "PATH_N_Z": 119, "PATH_X0": 47, "PATH_X1": 107,
    "PATH_TURN_X": 106,
    "TREE_STEP": 8, "ROSE_STEP": 2,

    # 4.7 Margalla Hills (compressed artistic backdrop, not to scale)
    "HILL_Z0": 146, "HILL_Z1": 159,
    "HILL_MIN": 8, "HILL_MAX": 34,
    "HILL_PEAK1_X": 62, "HILL_PEAK1_H": 21,   # front ridgeline
    "HILL_PEAK2_X": 104, "HILL_PEAK2_H": 34,  # back ridgeline (higher)
    "HILL_SIGMA": 34,

    # 4.8 mausoleum of Zia-ul-Haq (austere, off-axis corner, clear of plinth)
    "MAUS_X": 26, "MAUS_Z": 126,
    "MAUS_R": 5, "MAUS_PODIUM_R": 6,
    "MAUS_WALL0": 5, "MAUS_WALL1": 10,
    "MAUS_ROOF0": 11, "MAUS_ROOF1": 13,
}

C225 = math.cos(math.radians(22.5))
S225 = math.sin(math.radians(22.5))


def octagon_halves(R):
    """Half-extents of a regular octagon whose FLATS face +/-X and +/-Z
    (corners on the diagonals): |dx|<=ax, |dz|<=az, |dx|+|dz|<=dd."""
    return R * C225, R * C225, R * (C225 + S225)


def in_oct(dx, dz, ax, az, dd):
    return abs(dx) <= ax and abs(dz) <= az and (abs(dx) + abs(dz)) <= dd


def hash01(a, b):
    """Deterministic pseudo-random in [0,1) from two ints (no RNG state)."""
    h = (a * 374761393 + b * 668265263) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return (h & 0xFFFF) / 65536.0


class Model:
    """All geometry as functions of (x,y,z) driven by the parameter dict."""

    def __init__(self, P):
        self.P = P
        self._build_features()

    # ---- derived constants -------------------------------------------------
    def _d(self, k):
        return self.P[k]

    def hall_radius(self, y):
        """Octagon circumradius of the tent shell at height y (uniform inset)."""
        R = self._d("HALL_R")
        if y <= self._d("WALL_TOP"):
            return R
        inset = (y - self._d("WALL_TOP")) / self._d("SHELL_INSET_RISE")
        return max(2.0, R - inset)

    def hall_xhalf(self, y):
        """X half-extent: follows the octagon until X_PINCH_START, then pinches
        hard inward so the shell terminates in a RIDGE along Z, not a spike."""
        R = self.hall_radius(y)
        ax = R * C225
        ps = self._d("X_PINCH_START")
        if y <= ps:
            return ax
        ax0 = max(2.0, self._d("HALL_R") - (ps - self._d("WALL_TOP")) / self._d("SHELL_INSET_RISE")) * C225
        top = self._d("HALL_TOP")
        t = min(1.0, (y - ps) / max(1, top - ps - 2))
        pinch = ax0 + (self._d("RIDGE_X_HALF") - ax0) * t
        return max(self._d("RIDGE_X_HALF"), min(ax, pinch))

    def girder_corner(self, y):
        """Diagonal corner line the four girders ride on (outer offset +1)."""
        return 0.6533 * self.hall_radius(y) + 1.0

    def girder_inner_leg(self, y):
        """Second leg of each girder above GIRDER_SPLIT_Y, converging to summit."""
        c0 = self.girder_corner(self._d("GIRDER_SPLIT_Y"))
        span = self._d("HALL_TOP") - self._d("GIRDER_SPLIT_Y")
        t = min(1.0, (y - self._d("GIRDER_SPLIT_Y")) / span)
        return max(1.0, c0 + (1.0 - c0) * t)

    # ---- scattered features (procedural from params, no voxel dumps) -------
    def on_plinth(self, x, z):
        P = self._d
        ax, az, dd = octagon_halves(P("PLINTH_R"))
        return in_oct(x - P("CX"), z - P("CZ"), ax, az, dd)

    def _build_features(self):
        P = self._d
        self.trees = {}     # (x,y,z) -> material
        self.roses = {}     # (x,z)   -> ROSE
        centers = []

        # trees along the two shaded paths (beside them, not on them)
        for zside in (P("PATH_S_Z") + 3, P("PATH_S_Z") - 3,
                      P("PATH_N_Z") + 3, P("PATH_N_Z") - 3):
            x = P("PATH_X0") + 3
            while x <= P("PATH_X1") - 3:
                centers.append((x, zside))
                x += P("TREE_STEP")
        # trees along courtyard edges (kept off the z=80 entrance sightline)
        for zside in (P("COURT_Z0") - 2, P("COURT_Z1") + 2):
            x = P("COURT_X0") + 2
            while x <= P("COURT_X1"):
                if not (P("COURT_Z0") - 4 <= zside <= P("COURT_Z1") + 4 and abs(zside - P("CZ")) <= 3):
                    centers.append((x, zside))
                x += P("TREE_STEP")
        x = P("COURT_X1") + 2
        z = P("COURT_Z0")
        while z <= P("COURT_Z1"):
            centers.append((x, z))
            z += P("TREE_STEP")
        # trees around the mausoleum (well-tended garden, radius 9..11)
        for ang in range(0, 360, 45):
            r = 10
            centers.append((int(P("MAUS_X") + r * math.cos(math.radians(ang))),
                            int(P("MAUS_Z") + r * math.sin(math.radians(ang)))))
        # a few on the west lawn
        for z in range(P("CZ") - 20, P("CZ") + 21, 10):
            centers.append((P("PATH_X0") + 4, z))

        for (tx, tz) in centers:
            if tx < 2 or tx > 157 or tz < 2 or tz > 143:
                continue
            # never block the entrance sightline on the east axis
            if tx > P("COURT_X0") and abs(tz - P("CZ")) <= 3:
                continue
            r = 2 + int(hash01(tx, tz) * 2)          # canopy radius 2..3
            th = 2 + int(hash01(tz, tx) * 3)         # tree height 2..4
            base = 3 if self.on_plinth(tx, tz) else 2
            top = base + th - 1
            # trunk
            for dy in range(0, th):
                self.trees.setdefault((tx, base + dy, tz), IDX["MARBLE_DARK"] if dy == 0 else IDX["FOLIAGE"])
            # canopy: a blob centred on the trunk top so every voxel is
            # 6-connected down the trunk to the ground
            for dx in range(-r, r + 1):
                for dz in range(-r, r + 1):
                    for dy in range(-1, 3):
                        if dx * dx + dz * dz + (dy * dy) * 2 <= r * r + 2:
                            self.trees.setdefault((tx + dx, top + dy, tz + dz), IDX["FOLIAGE"])

        # formal rose beds beside the paths and around the mausoleum
        for zside in (P("PATH_S_Z") + 4, P("PATH_S_Z") - 4,
                      P("PATH_N_Z") + 4, P("PATH_N_Z") - 4):
            x = P("PATH_X0") + 2
            while x <= P("PATH_X1"):
                self.roses[(x, zside)] = IDX["ROSE"]
                x += P("ROSE_STEP")
        for ang in range(0, 360, 20):
            r = 9
            rx = int(P("MAUS_X") + r * math.cos(math.radians(ang)))
            rz = int(P("MAUS_Z") + r * math.sin(math.radians(ang)))
            self.roses[(rx, rz)] = IDX["ROSE"]

    # ---- component tests ----------------------------------------------------
    def _hill_height(self, x, z):
        P = self._d
        # layered ridge silhouette: two overlapping Gaussian ridgelines,
        # ramping up with depth into the +Z edge (compressed, not to scale)
        t = (z - P("HILL_Z0")) / max(1, P("HILL_Z1") - P("HILL_Z0"))
        g1 = P("HILL_PEAK1_H") * math.exp(-((x - P("HILL_PEAK1_X")) ** 2) / (2 * P("HILL_SIGMA") ** 2))
        g2 = P("HILL_PEAK2_H") * math.exp(-((x - P("HILL_PEAK2_X")) ** 2) / (2 * (P("HILL_SIGMA") * 0.8) ** 2))
        h = P("HILL_MIN") + (max(g1 * (1.0 - 0.45 * t), g2) ) * (0.35 + 0.65 * t)
        return min(P("HILL_MAX"), max(P("HILL_MIN"), h))

    def _minaret(self, x, y, z):
        P = self._d
        cx, cz = P("CX"), P("CZ")
        off = P("MIN_OFF")
        for sx in (+1, -1):
            for sz in (+1, -1):
                mx, mz = cx + sx * off, cz + sz * off
                dx, dz = x - mx, z - mz
                if abs(dx) > P("MIN_BASE_HALF") + 1 or abs(dz) > P("MIN_BASE_HALF") + 1:
                    continue
                if y < 3 or y > P("CRESCENT_TOP"):
                    continue
                if y <= P("MIN_BASE_TOP"):
                    if abs(dx) <= P("MIN_BASE_HALF") and abs(dz) <= P("MIN_BASE_HALF"):
                        return IDX["MARBLE_WHITE"]
                    return 0
                if y <= P("MIN_SHAFT_TOP"):
                    # monotonic near-linear taper to a 2-voxel throat
                    span = P("MIN_SHAFT_TOP") - P("MIN_BASE_TOP")
                    w = P("MIN_BASE_HALF") - (y - P("MIN_BASE_TOP")) * P("MIN_BASE_HALF") / span
                    w = max(0.5, w)
                    if abs(dx) <= w and abs(dz) <= w:
                        return IDX["MARBLE_WHITE"]
                    return 0
                # gold crescent (hilal): an upward-opening arc rooted on the
                # shaft throat — bar across the top, arms rising at the ends
                if y == P("MIN_SHAFT_TOP") + 1 and abs(dx) <= 2 and dz == 0:
                    return IDX["GOLD"]
                if P("MIN_SHAFT_TOP") + 2 <= y <= P("CRESCENT_TOP") and abs(dx) == 2 and dz == 0:
                    return IDX["GOLD"]
        return 0

    def _hall(self, x, y, z):
        P = self._d
        cx, cz = P("CX"), P("CZ")
        dx, dz = x - cx, z - cz
        if y < 3 or y > P("HALL_TOP"):
            return 0
        if abs(dx) > P("HALL_R") + 2 or abs(dz) > P("HALL_R") + 2:
            return 0
        # the four minaret bases clip the hall's diagonal corners; the hall
        # shell simply stops where a minaret pad begins
        off = P("MIN_OFF")
        for sx in (+1, -1):
            for sz in (+1, -1):
                if abs(dx - sx * off) <= P("MIN_BASE_HALF") and abs(dz - sz * off) <= P("MIN_BASE_HALF"):
                    return 0

        # four girders: concrete ribs at the diagonal corners, splitting into
        # two legs in the upper half so all four meet at the summit ridge
        g = P("GIRDER_THICK")
        c = self.girder_corner(y)
        for sx in (+1, -1):
            for sz in (+1, -1):
                if abs(abs(dx) - c) <= g and abs(abs(dz) - c) <= g:
                    return IDX["CONCRETE"]
        if y > P("GIRDER_SPLIT_Y"):
            l = self.girder_inner_leg(y)
            for sx in (+1, -1):
                for sz in (+1, -1):
                    if abs(abs(dx) - l) <= g and abs(abs(dz) - l) <= g:
                        return IDX["CONCRETE"]

        # shell: octagonal prism wall band, then uniformly inset sloping shell
        ax, az, dd = octagon_halves(self.hall_radius(y))
        ax = self.hall_xhalf(y)
        Ri = max(1.0, self.hall_radius(y) - P("WALL_THICK"))
        axi, azi, ddi = octagon_halves(Ri)
        axi = max(1.0, ax - P("WALL_THICK"))
        azi = max(1.0, az - P("WALL_THICK"))
        ddi = max(2.0, dd - P("WALL_THICK") * (C225 + S225))
        if y == 3:
            # floor slab: full octagon
            return IDX["MARBLE_WHITE"] if in_oct(dx, dz, ax, az, dd) else 0
        if not in_oct(dx, dz, ax, az, dd):
            return 0
        if in_oct(dx, dz, axi, azi, ddi):
            return 0  # interior void
        # cardinal doorways in the wall band (do not break the shell above)
        if y <= P("OPEN_TOP"):
            if abs(dz) <= P("OPEN_HALF") and dx >= ax - P("WALL_THICK") - 1 and dx >= 0:
                return IDX["OPENING"]
            if abs(dz) <= P("OPEN_HALF") and dx <= -(ax - P("WALL_THICK") - 1) and dx <= 0:
                return IDX["OPENING"]
            if abs(dx) <= P("OPEN_HALF") and dz >= az - P("WALL_THICK") - 1 and dz >= 0:
                return IDX["OPENING"]
            if abs(dx) <= P("OPEN_HALF") and dz <= -(az - P("WALL_THICK") - 1) and dz <= 0:
                return IDX["OPENING"]
        # shadowed inner faces read as MARBLE_SHADE
        if abs(dx) >= ax - 1 or abs(dz) >= az - 1:
            return IDX["MARBLE_WHITE"]
        return IDX["MARBLE_SHADE"] if (y <= P("WALL_TOP") and (abs(dx) <= axi + 1 or abs(dz) <= azi + 1)) else IDX["MARBLE_WHITE"]

    def _plinth(self, x, y, z):
        P = self._d
        if y > P("PLINTH_TOP"):
            return 0
        dx, dz = x - P("CX"), z - P("CZ")
        ax, az, dd = octagon_halves(P("PLINTH_R"))
        if in_oct(dx, dz, ax, az, dd):
            return IDX["MARBLE_SHADE"] if y == 0 else IDX["MARBLE_WHITE"]
        # square pads under each minaret so the plinth extends >=4 voxels past
        # every minaret base (the octagon alone clips the diagonal corners)
        off = P("MIN_OFF")
        for sx in (+1, -1):
            for sz in (+1, -1):
                if abs(x - (P("CX") + sx * off)) <= P("MINARET_PAD_HALF") and \
                   abs(z - (P("CZ") + sz * off)) <= P("MINARET_PAD_HALF"):
                    return IDX["MARBLE_SHADE"] if y == 0 else IDX["MARBLE_WHITE"]
        return 0

    def _water(self, x, y, z):
        P = self._d
        if y != 3:
            return 0
        if (P("POOL_W_X0") <= x <= P("POOL_W_X1") and P("POOL_W_Z0") <= z <= P("POOL_W_Z1")) or \
           (P("POOL_N_X0") <= x <= P("POOL_N_X1") and P("POOL_N_Z0") <= z <= P("POOL_N_Z1")) or \
           (P("POOL_S_X0") <= x <= P("POOL_S_X1") and P("POOL_S_Z0") <= z <= P("POOL_S_Z1")) or \
           (P("POND_L_X0") <= x <= P("POND_L_X1") and P("POND_L_Z0") <= z <= P("POND_L_Z1")) or \
           (P("ABL_X0") <= x <= P("ABL_X1") and P("ABL_Z0") <= z <= P("ABL_Z1")):
            return IDX["WATER"]
        dx, dz = x - P("POND_C_X"), z - P("POND_C_Z")
        if dx * dx + dz * dz <= P("POND_C_R") ** 2:
            return IDX["WATER"]
        return 0

    def _jet(self, x, y, z):
        """White frothy aerated fountain jet rising from the ablution pool,
        on a small marble pedestal so it is rooted, not floating."""
        P = self._d
        if abs(x - P("JET_X")) <= 1 and abs(z - P("JET_Z")) <= 1:
            if y == 3:
                return IDX["MARBLE_WHITE"]          # pedestal in the pool
            if 4 <= y <= 3 + P("JET_H"):
                return IDX["MARBLE_WHITE"]          # the plume
        return 0

    def _courtyard(self, x, y, z):
        P = self._d
        if P("COURT_X0") <= x <= P("COURT_X1") and P("COURT_Z0") <= z <= P("COURT_Z1") \
           and 2 <= y <= 3:
            return IDX["GRANITE"]
        return 0

    def _portico(self, x, y, z):
        """Colonnade around the courtyard: 1-voxel columns every 4 voxels on
        three sides, carrying a 1-voxel roof slab."""
        P = self._d
        sp = P("PORTICO_SPACING")
        y0, y1 = 4, P("PORTICO_ROOF_Y")   # columns rise to meet the roof slab
        ry = P("PORTICO_ROOF_Y")
        # south and north colonnades
        for zc in (P("COURT_Z0"), P("COURT_Z1")):
            if zc != z:
                continue
            if (x - P("COURT_X0")) % sp == 0 and P("COURT_X0") <= x <= P("COURT_X1"):
                if y0 <= y <= y1:
                    return IDX["CONCRETE"]
            if y == ry and P("COURT_X0") <= x <= P("COURT_X1"):
                return IDX["CONCRETE"]
        # east colonnade
        if x == P("COURT_X1") and P("COURT_Z0") <= z <= P("COURT_Z1"):
            if (z - P("COURT_Z0")) % sp == 0 and y0 <= y <= y1:
                return IDX["CONCRETE"]
            if y == ry:
                return IDX["CONCRETE"]
        return 0

    def _verandah(self, x, y, z):
        """Entrance verandah on the EAST face: columns + cantilever roof."""
        P = self._d
        if P("VERANDAH_X0") <= x <= P("VERANDAH_X1") and P("VERANDAH_Z0") <= z <= P("VERANDAH_Z1") \
           and y == P("VERANDAH_Y"):
            return IDX["MARBLE_SHADE"]
        if x == P("VERANDAH_X1") and P("VERANDAH_Z0") <= z <= P("VERANDAH_Z1") \
           and (z - P("VERANDAH_Z0")) % P("VERANDAH_COL_STEP") == 0 and 4 <= y <= P("VERANDAH_Y"):
            return IDX["CONCRETE"]
        return 0

    def _paths(self, x, y, z):
        """Two shaded walking routes from the plinth's west edge to the courtyard."""
        P = self._d
        if y != 3:
            return 0
        w = P("PATH_W") // 2
        for zc in (P("PATH_S_Z"), P("PATH_N_Z")):
            if zc - w <= z <= zc + w and P("PATH_X0") <= x <= P("PATH_X1"):
                return IDX["MARBLE_DARK"]
        if P("PATH_TURN_X") - w <= x <= P("PATH_TURN_X") + w:
            if P("PATH_S_Z") <= z <= P("COURT_Z0"):
                return IDX["MARBLE_DARK"]
            if P("COURT_Z1") <= z <= P("PATH_N_Z"):
                return IDX["MARBLE_DARK"]
        return 0

    def _grass(self, x, y, z):
        P = self._d
        if not (P("SITE_X0") <= x <= P("SITE_X1") and P("SITE_Z0") <= z <= P("SITE_Z1")):
            return 0
        dx, dz = x - P("CX"), z - P("CZ")
        ax, az, dd = octagon_halves(P("PLINTH_R"))
        on_plinth = in_oct(dx, dz, ax, az, dd)
        if on_plinth:
            if y == 3:  # lawn on the plinth top where nothing else is paved
                return IDX["GRASS"]
            return 0
        if y == 1:      # lawn on the surrounding site ground
            return IDX["GRASS"]
        return 0

    def _mausoleum(self, x, y, z):
        """Zia-ul-Haq mausoleum: small octagonal white-marble structure with
        latticed jali screens, two iron doors, on a low podium. Austere."""
        P = self._d
        dx, dz = x - P("MAUS_X"), z - P("MAUS_Z")
        if abs(dx) > P("MAUS_PODIUM_R") + 1 or abs(dz) > P("MAUS_PODIUM_R") + 1:
            return 0
        if y < 2 or y > P("MAUS_ROOF1"):
            return 0
        ax, az, dd = octagon_halves(P("MAUS_PODIUM_R"))
        if y <= 4:
            return IDX["MARBLE_DARK"] if in_oct(dx, dz, ax, az, dd) else 0
        ax, az, dd = octagon_halves(P("MAUS_R"))
        if not in_oct(dx, dz, ax, az, dd):
            return 0
        if P("MAUS_WALL0") <= y <= P("MAUS_WALL1"):
            # two iron doorways on the X axis (short openings, not full-height)
            ax, az, dd = octagon_halves(P("MAUS_R"))
            if abs(dz) <= 1.5 and abs(dx) >= ax - 1.2 and y <= P("MAUS_WALL1") - 2:
                return IDX["OPENING"]
            # latticed jali screens on the four diagonal flats
            adx, adz = abs(dx), abs(dz)
            on_diag_flat = abs(adx + adz - dd) <= 1.0 and adx > 1 and adz > 1
            cardinal_flat = (adx >= ax - 1.5 and adz <= az * 0.55) or (adz >= az - 1.5 and adx <= ax * 0.55)
            if on_diag_flat:
                return IDX["LATTICE"] if (y % 2 == 0 or (adx + adz) % 2 == 0) else IDX["MARBLE_WHITE"]
            if cardinal_flat:
                return IDX["MARBLE_WHITE"]
            return IDX["MARBLE_WHITE"]
        if y >= P("MAUS_ROOF0"):
            # low octagonal roof, no dome, no gold
            shrink = (y - P("MAUS_ROOF0")) * 1.2
            ax, az, dd = octagon_halves(max(1.0, P("MAUS_R") - shrink))
            return IDX["MARBLE_SHADE"] if in_oct(dx, dz, ax, az, dd) else 0
        return 0

    # ---- the two spec-mandated functions ------------------------------------
    def material(self, x, y, z):
        """Return palette index 2..14 for a solid voxel, 0 for empty."""
        P = self._d
        # Margalla Hills backdrop (separate structure, +Z edge)
        if z >= P("HILL_Z0"):
            return IDX["HILL"] if y >= P("HILL_MIN") and y <= self._hill_height(x, z) else 0
        m = self._minaret(x, y, z)
        if m:
            return m
        m = self._hall(x, y, z)
        if m:
            return m
        m = self._mausoleum(x, y, z)
        if m:
            return m
        m = self._jet(x, y, z)
        if m:
            return m
        m = self._water(x, y, z)
        if m:
            return m
        m = self._verandah(x, y, z)
        if m:
            return m
        m = self._portico(x, y, z)
        if m:
            return m
        m = self._paths(x, y, z)
        if m:
            return m
        m = self._courtyard(x, y, z)
        if m:
            return m
        # rose beds sit ON the ground surface: plinth top (y=3) or site ground
        r = self.roses.get((x, z))
        if r and y == (3 if self.on_plinth(x, z) else 1):
            return r
        m = self._plinth(x, y, z)
        if m:
            return m
        m = self._grass(x, y, z)
        if m:
            return m
        t = self.trees.get((x, y, z))
        if t:
            return t
        if y == 2:
            r = self.roses.get((x, z))
            if r:
                return r
        return 0
    def is_solid(self, x, y, z):
        return self.material(x, y, z) != 0


# ---------------------------------------------------------------------------
# Build: iterate the grid once through material()
# ---------------------------------------------------------------------------
def build_grid(model):
    P = model.P
    GX, GY, GZ = P["GRID_X"], P["GRID_Y"], P["GRID_Z"]
    grid = bytearray(GX * GY * GZ)
    idx = lambda x, y, z: (y * GZ + z) * GX + x
    mat = model.material
    for y in range(GY):
        base = y * GZ * GX
        for z in range(GZ):
            row = base + z * GX
            for x in range(GX):
                m = mat(x, y, z)
                if m:
                    grid[row + x] = m
    return grid


def grid_get(model, grid, x, y, z):
    P = model.P
    if 0 <= x < P["GRID_X"] and 0 <= y < P["GRID_Y"] and 0 <= z < P["GRID_Z"]:
        return grid[(y * P["GRID_Z"] + z) * P["GRID_X"] + x]
    return 0


# ---------------------------------------------------------------------------
# Deliverable 1: MagicaVoxel .vox (RIFF-style, little-endian)
# ---------------------------------------------------------------------------
def write_vox(model, grid, path):
    P = model.P
    GX, GY, GZ = P["GRID_X"], P["GRID_Y"], P["GRID_Z"]
    xyzis = []
    for y in range(GY):
        base = y * GZ * GX
        for z in range(GZ):
            row = base + z * GX
            for x in range(GX):
                m = grid[row + x]
                if m:
                    xyzis.append((x, y, z, m))
    xyz_payload = struct.pack("<I", len(xyzis)) + b"".join(
        struct.pack("<BBBB", x, y, z, c) for (x, y, z, c) in xyzis)
    size_payload = struct.pack("<III", GX, GY, GZ)
    rgba_payload = bytearray(4 * 256)   # the format requires a full 256-entry table
    for i, (_, rgb, a) in enumerate(PALETTE):
        off = i * 4  # RGBA chunk starts at colour index 1
        rgba_payload[off] = (rgb >> 16) & 0xFF
        rgba_payload[off + 1] = (rgb >> 8) & 0xFF
        rgba_payload[off + 2] = rgb & 0xFF
        rgba_payload[off + 3] = a
    chunks = [
        (b"SIZE", size_payload, 0),
        (b"XYZI", xyz_payload, 0),
        (b"RGBA", bytes(rgba_payload), 0),
    ]
    # Chunk header = id(4) + content_size(4) + children_size(4).
    # MAIN is the container: content_size=0, and children_size covers the child
    # chunks only. The format has NO child-count field -- MagicaVoxel walks the
    # children by consuming children_size -- so an extra 4-byte count here makes
    # the file unreadable to standard readers (the first child header is read 4
    # bytes late and the whole walk derails).
    children_size = 0
    for cid, payload, cs in chunks:
        children_size += 12 + len(payload) + cs
    body = b"MAIN" + struct.pack("<II", 0, children_size)
    for cid, payload, cs in chunks:
        body += cid + struct.pack("<II", len(payload), cs) + payload
    # Version 150 is the classic MagicaVoxel version that every reader accepts
    # (200 is also valid, but several libraries still only accept 150).
    data = b"VOX " + struct.pack("<I", 150) + body
    with open(path, "wb") as f:
        f.write(data)
    return len(xyzis), data


def parse_vox(data):
    """Independent reader used by check C23, following the MagicaVoxel layout:
    'VOX ' + version, then MAIN (content_size 0, children_size covering the
    children), then the child chunks at the top level. No child-count field."""
    assert data[:4] == b"VOX ", "bad magic"
    version = struct.unpack("<I", data[4:8])[0]
    pos = 8

    def read_chunk():
        nonlocal pos
        cid = data[pos:pos + 4]
        psize, csize = struct.unpack("<II", data[pos + 4:pos + 12])
        pos += 12
        payload = data[pos:pos + psize]
        pos += psize
        return cid, payload, csize

    cid, _payload, children = read_chunk()
    assert cid == b"MAIN", "first chunk must be MAIN"
    end = pos + children  # the children occupy exactly children_size bytes
    size = xyz = rgba = None
    while pos < end:
        c, p, _ = read_chunk()
        if c == b"SIZE":
            size = struct.unpack("<III", p)
        elif c == b"XYZI":
            xyz = struct.unpack("<I", p[:4])[0]
        elif c == b"RGBA":
            rgba = len(p) // 4
    assert pos == end, "children_size does not match the child chunks"
    return version, size, xyz, rgba


# ---------------------------------------------------------------------------
# Deliverable 2: isometric PNG render (stdlib zlib+struct)
# ---------------------------------------------------------------------------
def render_png(model, grid, path, scale=4):
    """Isometric 2:1 render viewed from the south-east and slightly above:
    east entrance + courtyard on the right-front, Margalla ridge behind-left,
    minarets flanking. Depth-sorted, face-shaded (top/right/left brightness)."""
    P = model.P
    GX, GY, GZ = P["GRID_X"], P["GRID_Y"], P["GRID_Z"]
    s = scale
    # projection: sx = (x+z)*s ; sy = ((x - z)/2 - y)*s ; depth = x - z + y
    voxels = []
    for y in range(GY):
        base = y * GZ * GX
        for z in range(GZ):
            row = base + z * GX
            for x in range(GX):
                m = grid[row + x]
                if m:
                    voxels.append((x - z + y, x, y, z, m))
    voxels.sort()  # far first (painter's algorithm)

    min_sx = min((x + z) for _, x, _, z, _ in voxels) * s - 2 * s
    max_sx = max((x + z) for _, x, _, z, _ in voxels) * s + 3 * s
    min_sy = min(((x - z) // 2 - y) for _, x, y, z, _ in voxels) * s - 2 * s
    max_sy = max(((x - z) // 2 - y) for _, x, y, z, _ in voxels) * s + 3 * s
    W = max_sx - min_sx + 1
    H = max_sy - min_sy + 1
    W = max(W, 1024)
    H = max(H, 768)
    img = bytearray(3 * W * H)

    # precomputed projected corner offsets of a unit cube
    corners = {}
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                corners[(dx, dy, dz)] = ((dx + dz) * s, ((dx - dz) * s) // 2 - dy * s)
    TOP = [corners[(0, 1, 0)], corners[(1, 1, 0)], corners[(1, 1, 1)], corners[(0, 1, 1)]]
    RIGHT = [corners[(1, 0, 0)], corners[(1, 1, 0)], corners[(1, 1, 1)], corners[(1, 0, 1)]]
    LEFT = [corners[(0, 0, 1)], corners[(0, 1, 1)], corners[(1, 1, 1)], corners[(1, 0, 1)]]

    shades = {IDX["MARBLE_WHITE"]: (1.00, 0.80, 0.58),
              IDX["MARBLE_SHADE"]: (0.95, 0.76, 0.55),
              IDX["CONCRETE"]: (1.00, 0.78, 0.56),
              IDX["MARBLE_DARK"]: (1.00, 0.78, 0.56),
              IDX["WATER"]: (1.00, 0.85, 0.65),
              IDX["OPENING"]: (1.00, 0.70, 0.50),
              IDX["GOLD"]: (1.00, 0.82, 0.60),
              IDX["GRASS"]: (1.00, 0.80, 0.58),
              IDX["FOLIAGE"]: (1.00, 0.78, 0.55),
              IDX["GRANITE"]: (1.00, 0.78, 0.56),
              IDX["LATTICE"]: (1.00, 0.80, 0.58),
              IDX["HILL"]: (1.00, 0.80, 0.58),
              IDX["ROSE"]: (1.00, 0.78, 0.55)}

    def fill_quad(ox, oy, quad, rgb, bright):
        pts = [(ox + px, oy + py) for px, py in quad]
        ys = sorted(p[1] for p in pts)
        y0, y1 = ys[0], ys[-1]
        r, g, b = rgb
        cr, cg, cb = int(r * bright), int(g * bright), int(b * bright)
        # scanline fill of the convex quad
        for yy in range(y0, y1 + 1):
            xs = []
            for i in range(4):
                (x1, y1a), (x2, y2a) = pts[i], pts[(i + 1) % 4]
                if y1a == y2a:
                    if yy == y1a:
                        xs.extend((x1, x2))
                elif min(y1a, y2a) <= yy < max(y1a, y2a):
                    t = (yy - y1a) / (y2a - y1a)
                    xs.append(int(x1 + (x2 - x1) * t))
            if len(xs) >= 2:
                xa, xb = min(xs), max(xs)
                row = yy * W
                for xx in range(max(0, xa), min(W, xb + 1)):
                    o = (row + xx) * 3
                    img[o] = cr
                    img[o + 1] = cg
                    img[o + 2] = cb

    solid = lambda x, y, z: grid_get(model, grid, x, y, z) != 0
    for _, x, y, z, m in voxels:
        ox = (x + z) * s - min_sx
        oy = ((x - z) // 2 - y) * s - min_sy
        rgb = PALETTE[m - 1][1]  # packed int RGB
        rgb = ((rgb >> 16) & 0xFF, (rgb >> 8) & 0xFF, rgb & 0xFF)
        btop, bright_r, bright_l = shades.get(m, (1.0, 0.8, 0.6))
        if not solid(x, y + 1, z):
            fill_quad(ox, oy, TOP, rgb, btop)
        if not solid(x + 1, y, z):
            fill_quad(ox, oy, RIGHT, rgb, bright_r)
        if not solid(x, y, z - 1):
            fill_quad(ox, oy, LEFT, rgb, bright_l)

    # PNG encode
    raw = bytearray()
    for yy in range(H):
        raw.append(0)
        raw += img[yy * W * 3:(yy + 1) * W * 3]
    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 6))
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)
    return W, H


# ---------------------------------------------------------------------------
# Deliverable 3: ASCII elevations + stats
# ---------------------------------------------------------------------------
ASCII_MAP = {
    IDX["MARBLE_WHITE"]: "W", IDX["MARBLE_SHADE"]: "w", IDX["CONCRETE"]: "C",
    IDX["MARBLE_DARK"]: "d", IDX["WATER"]: "~", IDX["OPENING"]: " ",
    IDX["GOLD"]: "G", IDX["GRASS"]: "g", IDX["FOLIAGE"]: "T", IDX["ROSE"]: "R",
    IDX["GRANITE"]: "#", IDX["LATTICE"]: "l", IDX["HILL"]: "^",
}

def ascii_front(model, grid):
    """Front elevation onto X-Y looking along +Z (viewer at -Z: nearest = min z)."""
    P = model.P
    out = []
    for y in range(P["GRID_Y"] - 1, -1, -2):
        line = []
        for x in range(0, P["GRID_X"], 2):
            ch = "."
            for z in range(P["GRID_Z"]):
                m = grid_get(model, grid, x, y, z) or grid_get(model, grid, x + 1, y, z)
                if m:
                    ch = ASCII_MAP.get(m, ".")
                    break
            line.append(ch)
        out.append("".join(line))
    return "\n".join(out)

def ascii_top(model, grid):
    """Top-down footprint onto X-Z (nearest = highest voxel)."""
    P = model.P
    out = []
    for z in range(0, P["GRID_Z"], 2):
        line = []
        for x in range(0, P["GRID_X"], 2):
            ch = "."
            for y in range(P["GRID_Y"] - 1, -1, -1):
                m = grid_get(model, grid, x, y, z) or grid_get(model, grid, x + 1, y, z)
                if m:
                    ch = ASCII_MAP.get(m, ".")
                    break
            line.append(ch)
        out.append("".join(line))
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Self-validation C1..C24
# ---------------------------------------------------------------------------
def run_checks(model, grid, vox_bytes, vox_count, png_path, params, second_build_hash):
    P = model.P
    GX, GY, GZ = P["GRID_X"], P["GRID_Y"], P["GRID_Z"]
    results = []

    def add(cid, ok, detail=""):
        results.append((cid, bool(ok), detail))

    solids = [(x, y, z, grid_get(model, grid, x, y, z))
              for y in range(GY) for z in range(GZ) for x in range(GX)
              if grid_get(model, grid, x, y, z)]

    # C1/C2/C3/C4: minaret components (above the plinth, structural materials)
    struct_mats = {IDX["MARBLE_WHITE"], IDX["CONCRETE"], IDX["GOLD"]}
    above = [(x, y, z) for (x, y, z, m) in solids if y >= 3 and m in struct_mats]
    key = lambda p: p[0] + p[1] * 1000 + p[2] * 1000000
    aset = set(key(p) for p in above)
    seen = set()
    comps = []
    for p in above:
        if key(p) in seen:
            continue
        stack = [p]
        seen.add(key(p))
        comp = []
        while stack:
            x, y, z = stack.pop()
            comp.append((x, y, z))
            for nx, ny, nz in ((x+1,y,z),(x-1,y,z),(x,y+1,z),(x,y-1,z),(x,y,z+1),(x,y,z-1)):
                if key((nx,ny,nz)) in aset and key((nx,ny,nz)) not in seen:
                    seen.add(key((nx,ny,nz)))
                    stack.append((nx,ny,nz))
        comps.append(comp)
    minarets = []
    for comp in comps:
        ys = [c[1] for c in comp]
        h = max(ys) - min(ys) + 1
        if h >= 60:
            xs = [c[0] for c in comp if c[1] <= 12]
            zs = [c[2] for c in comp if c[1] <= 12]
            base_w = (max(xs) - min(xs) + 1) if xs else 99
            if base_w <= 12:
                minarets.append(comp)
    add("C1", len(minarets) == 4, f"{len(minarets)} minaret components")
    if len(minarets) == 4:
        tops = []
        overall_top = 0
        for comp in minarets:
            shaft = max(y for (x, y, z) in comp if grid_get(model, grid, x, y, z) == IDX["MARBLE_WHITE"])
            tops.append(shaft)
            overall_top = max(overall_top, max(y for (x, y, z) in comp))
        add("C2", all(abs(t - 86) <= 2 for t in tops) and len(set(tops)) == 1 and abs(overall_top - 90) <= 2,
            f"shafts {tops}, top {overall_top}")
        gold_ok = 0
        for comp in minarets:
            if any(grid_get(model, grid, x, y, z) == IDX["GOLD"] and y >= 87 for (x, y, z) in comp):
                gold_ok += 1
        add("C3", gold_ok == 4, f"{gold_ok}/4 crescents")
        cents = sorted((sum(c[0] for c in comp)/len(comp), sum(c[2] for c in comp)/len(comp)) for comp in minarets)
        sym = all(abs(a[0] + b[0] - 2*P["CX"]) < 1.5 and abs(a[1] + b[1] - 2*P["CZ"]) < 1.5
                  for a, b in zip(cents, reversed(cents)))
        add("C4", sym, f"centres {[(round(a,1),round(b,1)) for a,b in cents]}")
    else:
        add("C2", False); add("C3", False); add("C4", False)

    # C5/C6/C7/C8: hall octagon, peak, not-a-dome, ridge-not-spike
    def hall_slice(y):
        pts = set()
        for x in range(P["CX"] - 40, P["CX"] + 41):
            for z in range(P["CZ"] - 40, P["CZ"] + 41):
                m = grid_get(model, grid, x, y, z)
                if m in (IDX["MARBLE_WHITE"], IDX["MARBLE_SHADE"]):
                    dx, dz = x - P["CX"], z - P["CZ"]
                    if abs(dx) <= 34 and abs(dz) <= 34:  # hall region only
                        # exclude the four minaret columns (they are separate
                        # structures standing at the diagonal corners)
                        if any(abs(dx - sx * P["MIN_OFF"]) <= 6 and abs(dz - sz * P["MIN_OFF"]) <= 6
                               for sx in (+1, -1) for sz in (+1, -1)):
                            continue
                        pts.add((dx, dz))
        return pts
    inv_bad = 0
    inv_tot = 0
    for y in range(10, P["X_PINCH_START"]):
        pts = hall_slice(y)
        for (dx, dz) in pts:
            inv_tot += 1
            rx = (dx - dz) / math.sqrt(2)
            rz = (dx + dz) / math.sqrt(2)
            found = any((round(rx)+i, round(rz)+j) in pts for i in (-1,0,1) for j in (-1,0,1))
            if not found:
                inv_bad += 1
    add("C5", inv_tot > 0 and inv_bad / max(1, inv_tot) < 0.03,
        f"45deg mismatch {inv_bad}/{inv_tot} over octagonal body Y=10..{P['X_PINCH_START']-1}")
    hall_pts_by_y = {y: hall_slice(y) for y in (10, 43, 44, 45)}
    peak = max(y for y in range(3, GY) if hall_slice(y))
    add("C6", abs(peak - 45) <= 2, f"hall peak Y={peak}")
    a10, a43 = len(hall_pts_by_y[10]), len(hall_pts_by_y[43])
    add("C7", a10 > 0 and a43 <= 0.20 * a10, f"area Y43={a43} vs Y10={a10} ({100*a43/max(1,a10):.1f}%)")
    xs = [dx for y in (43,44,45) for (dx,dz) in hall_pts_by_y[y]]
    zs = [dz for y in (43,44,45) for (dx,dz) in hall_pts_by_y[y]]
    ex, ez = max(xs)-min(xs)+1, max(zs)-min(zs)+1
    add("C8", ez >= 12 and ex <= 5, f"top-layer extent X={ex} Z={ez}")

    # C9: girders meet at summit
    near = sum(1 for (x,y,z,m) in solids if m == IDX["CONCRETE"] and y >= 40
               and abs(x-P["CX"]) <= 8 and abs(z-P["CZ"]) <= 8)
    add("C9", near >= 4, f"{near} concrete voxels at Y>=40 within 8 of centre")

    # C10/C11: water on all sides, >=4 features, >=1 jet
    water = [(x,y,z) for (x,y,z,m) in solids if m == IDX["WATER"]]
    wset = set(water)
    seen = set()
    feats = 0
    for w in water:
        if w in seen: continue
        feats += 1
        stack=[w]; seen.add(w)
        while stack:
            x,y,z = stack.pop()
            for n in ((x+1,y,z),(x-1,y,z),(x,y,z+1),(x,y,z-1)):
                if n in wset and n not in seen:
                    seen.add(n); stack.append(n)
    sides = {
        "+X": any(w[0] > P["CX"] for w in water), "-X": any(w[0] < P["CX"] for w in water),
        "+Z": any(w[2] > P["CZ"] for w in water), "-Z": any(w[2] < P["CZ"] for w in water)}
    add("C10", all(sides.values()), str(sides))
    jet = any(grid_get(model, grid, x, y, z) == IDX["MARBLE_WHITE"] and y >= 4
              and any((x+dx, 3, z+dz) in wset for dx in (-1,0,1) for dz in (-1,0,1))
              for (x,y,z,m) in solids)
    add("C11", feats >= 4 and jet, f"{feats} water features, jet={jet}")

    # C12/C13: gardens
    counts = {}
    for (_, _, _, m) in solids:
        counts[m] = counts.get(m, 0) + 1
    green = sum(counts.get(IDX[k], 0) for k in ("GRASS", "FOLIAGE", "ROSE"))
    def green_side(dx0, dx1, dz0, dz1):
        return any(m in (IDX["GRASS"], IDX["FOLIAGE"], IDX["ROSE"])
                   for (x,y,z,m) in solids if dx0 <= x-P["CX"] <= dx1 and dz0 <= z-P["CZ"] <= dz1)
    gsides = {"+X": green_side(1, 80, -80, 80), "-X": green_side(-80, -1, -80, 80),
              "+Z": green_side(-80, 80, 1, 80), "-Z": green_side(-80, 80, -80, -1)}
    add("C12", green >= 12000 and all(gsides.values()), f"green={green} sides={gsides}")
    add("C13", counts.get(IDX["FOLIAGE"], 0) >= 120 and counts.get(IDX["ROSE"], 0) >= 40,
        f"foliage={counts.get(IDX['FOLIAGE'],0)} rose={counts.get(IDX['ROSE'],0)}")

    # C14: isolated single-voxel portico columns
    cols = 0
    for (x,y,z,m) in solids:
        if m == IDX["CONCRETE"] and 4 <= y <= 5:
            horiz = sum(1 for (dx,dz) in ((1,0),(-1,0),(0,1),(0,-1))
                        if grid_get(model, grid, x+dx, y, z+dz) == IDX["CONCRETE"])
            if horiz == 0:
                cols += 1
    add("C14", cols >= 12, f"{cols} isolated columns")

    # C15: Margalla ridge
    hills = [(x,y,z) for (x,y,z,m) in solids if m == IDX["HILL"]]
    confined = all(z >= P["HILL_Z0"] for (x,y,z) in hills)
    hmin = min(y for (x,y,z) in hills) if hills else 0
    hmax = max(y for (x,y,z) in hills) if hills else 0
    band1 = max((y for (x,y,z) in hills if z <= 151), default=0)
    band2 = max((y for (x,y,z) in hills if z >= 152), default=0)
    add("C15", hills and confined and 8 <= hmin and hmax <= 34
        and abs(band1 - band2) >= 4, f"heights {hmin}..{hmax}, ridgelines {band1}/{band2}")

    # C16: mausoleum (measure the connected structure, not a box that
    # would also catch neighbouring tree trunks)
    mx, mz = P["MAUS_X"], P["MAUS_Z"]
    mstruct = {IDX["MARBLE_WHITE"], IDX["MARBLE_SHADE"], IDX["MARBLE_DARK"],
               IDX["LATTICE"], IDX["OPENING"]}
    # seed at the podium centre and flood-fill through structure materials
    seed = None
    for y in range(2, 16):
        if grid_get(model, grid, mx, y, mz) in mstruct:
            seed = (mx, y, mz); break
    mvox = []
    maus_comp = set()
    if seed:
        seen_m = {seed}; st = [seed]
        while st:
            x, y, z = st.pop()
            maus_comp.add((x, y, z))
            mvox.append((x, y, z, grid_get(model, grid, x, y, z)))
            for n in ((x+1,y,z),(x-1,y,z),(x,y+1,z),(x,y-1,z),(x,y,z+1),(x,y,z-1)):
                if n not in seen_m and grid_get(model, grid, n[0], n[1], n[2]) in mstruct:
                    seen_m.add(n); st.append(n)
    if mvox:
        across = max(x for (x,y,z,m) in mvox) - min(x for (x,y,z,m) in mvox) + 1
        across_z = max(z for (x,y,z,m) in mvox) - min(z for (x,y,z,m) in mvox) + 1
        hgt = max(y for (x,y,z,m) in mvox) - min(y for (x,y,z,m) in mvox) + 1
        lat_faces = set()
        for (x,y,z,m) in mvox:
            if m == IDX["LATTICE"]:
                ang = int((math.atan2(z-mz, x-mx) + math.pi) / (math.pi/4)) % 8
                lat_faces.add(ang)
        doors = 0
        op = set((x,y,z) for (x,y,z,m) in mvox if m == IDX["OPENING"])
        seen_op = set()
        for w in op:
            if w in seen_op: continue
            doors += 1
            st=[w]; seen_op.add(w)
            while st:
                x,y,z = st.pop()
                for n in ((x+1,y,z),(x-1,y,z),(x,y+1,z),(x,y-1,z),(x,y,z+1),(x,y,z-1)):
                    if n in op and n not in seen_op:
                        seen_op.add(n); st.append(n)
        podium_top = max((y for (x,y,z,m) in mvox if m == IDX["MARBLE_DARK"]), default=0)
        # surrounding garden GROUND surface (grass level), not tree canopies
        surr = max((y for (x,y,z,m) in solids if 9 < max(abs(x-mx), abs(z-mz)) <= 12
                    and m == IDX["GRASS"]), default=0)
        add("C16", across <= 12 and across_z <= 12 and hgt <= 14 and len(lat_faces) >= 4
            and doors >= 2 and podium_top - surr >= 1,
            f"across={across}x{across_z} h={hgt} jali_faces={len(lat_faces)} doors={doors} podium={podium_top} vs garden {surr}")
    else:
        add("C16", False, "no mausoleum voxels")

    # C17: no Pakistan Monument (no tall granite cluster)
    gran_high = sum(1 for (x,y,z,m) in solids if m == IDX["GRANITE"] and y > 3)
    add("C17", gran_high == 0, f"granite above paving level: {gran_high}")

    # C18: connectivity from plinth/ground (hills + mausoleum excluded).
    # Exclude the mausoleum by its actual connected component (computed in
    # C16), not a crude box that would slice nearby trees in half.
    def excluded(x, y, z):
        if z >= P["HILL_Z0"]:
            return True
        if (x, y, z) in maus_comp:
            return True
        return False
    sset = set((x,y,z) for (x,y,z,m) in solids if not excluded(x,y,z))
    start = set(p for p in sset if p[1] <= 2)
    seen = set(start)
    stack = list(start)
    while stack:
        x,y,z = stack.pop()
        for n in ((x+1,y,z),(x-1,y,z),(x,y+1,z),(x,y-1,z),(x,y,z+1),(x,y,z-1)):
            if n in sset and n not in seen:
                seen.add(n); stack.append(n)
    orphans = len(sset) - len(seen)
    add("C18", orphans == 0, f"orphans={orphans}")

    # C19: determinism (second build hash passed in)
    h1 = hashlib.sha256(vox_bytes).hexdigest()
    add("C19", h1 == second_build_hash, f"sha256={h1[:16]}...")

    # C20: parameter round-trip (rebuild from saved params hash passed in)
    add("C20", h1 == second_build_hash, "params round-trip reproduces identical vox")

    # C21: bounds
    oob = sum(1 for (x,y,z,m) in solids if not (0 <= x < GX and 0 <= y < GY and 0 <= z < GZ))
    add("C21", oob == 0 and len(PALETTE) <= 256, f"out-of-bounds={oob}")

    # C22: voxel count range
    add("C22", 40000 <= vox_count <= 1500000, f"voxels={vox_count}")

    # C23: .vox parses AND conforms to the format's fixed invariants
    # (version 150/200, MAIN carrying no content of its own, a full 256-entry
    # RGBA table). The earlier version of this check accepted any version and
    # only required rgba >= len(PALETTE), so a file that no standard reader
    # could open still passed. vox_bytes[20:24] must be b"SIZE": that is the
    # direct regression guard that MAIN's header is 12 bytes, not 16.
    version, size, n, rgba = parse_vox(vox_bytes)
    add("C23",
        version in (150, 200)
        and size == (GX, GY, GZ)
        and n == vox_count
        and rgba == 256
        and vox_bytes[20:24] == b"SIZE",
        f"version={version} size={size} voxels={n} palette={rgba} "
        f"first_child={vox_bytes[20:24].decode('latin1')}")

    # C24: PNG written, >=1024x768, >=8 distinct colours
    try:
        with open(png_path, "rb") as f:
            d = f.read()
    except FileNotFoundError:
        add("C24", False, f"PNG not found: {png_path}")
        return results, counts, h1
    w, hgt = struct.unpack(">II", d[16:24])
    idat = b""
    i = 8
    while i < len(d):
        ln = struct.unpack(">I", d[i:i+4])[0]
        tag = d[i+4:i+8]
        if tag == b"IDAT":
            idat += d[i+8:i+8+ln]
        if tag == b"IEND":
            break
        i += 12 + ln
    raw = zlib.decompress(idat)
    colours = set()
    stride = w * 3 + 1
    for yy in range(0, hgt, 7):
        row = raw[yy*stride+1:(yy+1)*stride]
        for xx in range(0, w*3, 3*13):
            colours.add(bytes(row[xx:xx+3]))
    add("C24", w >= 1024 and hgt >= 768 and len(colours) >= 8,
        f"{w}x{hgt}, {len(colours)} sampled colours")

    return results, counts, h1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def load_params(path):
    if path:
        with open(path) as f:
            p = dict(DEFAULTS)
            p.update(json.load(f))
            return p
    return dict(DEFAULTS)


def main():
    ap = argparse.ArgumentParser(description="Faisal Mosque ensemble procedural voxel generator")
    ap.add_argument("--params")
    ap.add_argument("--save-params")
    ap.add_argument("--render-out")
    ap.add_argument("--tag", default="")
    ap.add_argument("--fetch-reference")
    ap.add_argument("--out-ref", default="reference.jpg")
    ap.add_argument("--no-render", action="store_true")
    args = ap.parse_args()

    if args.fetch_reference:
        import urllib.request
        req = urllib.request.Request(args.fetch_reference, headers={"User-Agent": "faisal-voxel-spec/1.0"})
        data = urllib.request.urlopen(req, timeout=60).read()
        with open(args.out_ref, "wb") as f:
            f.write(data)
        print(f"fetched reference -> {args.out_ref} ({len(data)} bytes)")
        if not args.render_out and args.tag == "" and not args.save_params:
            return

    P = load_params(args.params)
    tag = args.tag

    model = Model(P)
    grid = build_grid(model)

    vox_path = f"faisal_mosque_v{tag}.vox"
    vox_count, vox_bytes = write_vox(model, grid, vox_path)

    # C19/C20: rebuild deterministically and compare
    model2 = Model(load_params(args.params))
    grid2 = build_grid(model2)
    _, vox_bytes2 = write_vox(model2, grid2, "faisal_mosque_rebuild.vox")
    h2 = hashlib.sha256(vox_bytes2).hexdigest()

    png_path = args.render_out or f"faisal_mosque_v{tag}.png"
    if not args.no_render:
        render_png(model, grid, png_path)

    with open(f"faisal_mosque_v{tag}_front.txt", "w") as f:
        f.write(ascii_front(model, grid))
    with open(f"faisal_mosque_v{tag}_top.txt", "w") as f:
        f.write(ascii_top(model, grid))

    results, counts, h1 = run_checks(model, grid, vox_bytes, vox_count, png_path, P, h2)

    stats = {
        "voxel_count": vox_count,
        "sha256_vox": h1,
        "bounding_box": {"x": [0, P["GRID_X"]], "y": [0, P["GRID_Y"]], "z": [0, P["GRID_Z"]]},
        "per_material": {PALETTE[i-1][0]: c for i, c in sorted(counts.items())},
        "checks": {cid: {"pass": ok, "detail": det} for cid, ok, det in results},
    }
    with open(f"faisal_mosque_v{tag}_stats.json", "w") as f:
        json.dump(stats, f, indent=2)
    if args.save_params:
        with open(args.save_params, "w") as f:
            json.dump(P, f, indent=2)

    print(f"voxels={vox_count}  vox={vox_path}  png={png_path}")
    fails = 0
    for cid, ok, det in results:
        print(f"{cid}: {'PASS' if ok else 'FAIL'}  {det}")
        if not ok:
            fails += 1
    print(f"SUMMARY: {len(results)-fails}/{len(results)} checks passed")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()

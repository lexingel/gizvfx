# SPDX-License-Identifier: AGPL-3.0-or-later
"""gizvfx.ramps - colour ramps (dark to bright, hard steps) used by the effects. Any option `palette` takes a name from RAMPS or a list of hex colours."""
from .core import hex2rgb

_R = {
    "fire":     ["#2a0d0d", "#7a1d0f", "#d4401a", "#f7861f", "#ffc94a", "#fff1b8"],
    "ember":    ["#1d0a0a", "#5c1208", "#a8260f", "#e25a14", "#ff9b2e"],
    "lava":     ["#240808", "#6b1408", "#c2310e", "#ff6a1a", "#ffb43c", "#ffe9a0"],
    "smoke":    ["#15151b", "#2c2d37", "#474956", "#6a6d7c", "#969aa8", "#c3c6d0"],
    "dust":     ["#3a2d22", "#5c4a38", "#85705a", "#aa947a", "#cfbb9e"],
    "ice":      ["#10203a", "#1f4673", "#3a82b8", "#74c3e6", "#bdeefa", "#f2fcff"],
    "water":    ["#0b1d3d", "#14407a", "#2273b8", "#4fa6e0", "#9bd6f5", "#e6f7ff"],
    "electric": ["#1a1450", "#3a3ad0", "#5f8dff", "#9fd2ff", "#e5f6ff", "#ffffff"],
    "volt":     ["#2a2a06", "#6e7010", "#b8bd1c", "#eef24a", "#fdffa6", "#ffffff"],
    "poison":   ["#10260d", "#26561a", "#4c9a24", "#8bd13a", "#cdf56a", "#f1ffc2"],
    "holy":     ["#5a4a18", "#a8862a", "#e8c24a", "#fbe58c", "#fff6cf", "#ffffff"],
    "heal":     ["#0e3a2a", "#1c7a52", "#38c07a", "#8ae8ac", "#d4fbe3", "#ffffff"],
    "arcane":   ["#1d0f3d", "#47218a", "#7a3fd0", "#b07af0", "#dcb8ff", "#f6eaff"],
    "shadow":   ["#08060e", "#1a1228", "#2f2148", "#4d3873", "#7a5fa8"],
    "blood":    ["#1c0606", "#4d0c0c", "#8c1414", "#c92222", "#f05a4a"],
    "earth":    ["#241a12", "#4a3624", "#755a3a", "#a08458", "#cdb685"],
    "stone":    ["#1b1c21", "#35373f", "#555863", "#7b7f8c", "#a7abb7", "#d2d5dd"],
    "gold":     ["#3d2a08", "#855a12", "#c98f1e", "#f2c43a", "#ffe58a", "#fff8d6"],
    "leaf":     ["#0f2a14", "#1f5a24", "#3a9a34", "#6ccf48", "#b4f27a"],
    "metal":    ["#1c2026", "#3a414c", "#5d6877", "#8a96a8", "#bcc6d6", "#eef2f8"],
    "bone":     ["#3a342c", "#6b6256", "#a39a88", "#d2c9b4", "#f0e8d6"],
    "neon":     ["#2a0a3a", "#6a1ab0", "#c02ae0", "#ff5adc", "#ffa0ee", "#ffe6fa"],
}
RAMPS = {k: [hex2rgb(c) for c in v] for k, v in _R.items()}


def resolve(p, default="fire"):
    """a palette option -> a list of RGB tuples. Accepts a ramp name, or a list of hex strings / RGB tuples (dark to bright)"""
    if p is None: p = default
    if isinstance(p, str):
        if p in RAMPS: return RAMPS[p]
        if "," in p: p = [x.strip() for x in p.split(",")]
        else: raise ValueError(f"unknown palette '{p}'. Names: {', '.join(sorted(RAMPS))}, or hex colours dark to bright: '#102,#215,#43a'")
    out = []
    for c in p:
        out.append(hex2rgb(c if len(c.lstrip('#')) == 6 else ''.join(ch * 2 for ch in c.lstrip('#'))) if isinstance(c, str) else tuple(int(v) for v in c))
    if len(out) < 2: raise ValueError("a palette needs at least 2 colours")
    return out

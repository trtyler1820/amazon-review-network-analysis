"""
Design tokens for the Streamlit dashboard.

This module defines colors, radii, and chart palettes shared across Python code
(Plotly / matplotlib) and generated CSS (see web/styles.py). Keeping these in
one place makes it cheap to re-tune the system.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Palette — dark editorial with a single warm accent
# ---------------------------------------------------------------------------

PALETTE = {
    # Surfaces
    "bg":              "#0a0a0c",
    "bg_elev":         "#13131a",
    "surface":         "rgba(255, 255, 255, 0.038)",
    "surface_hover":   "rgba(255, 255, 255, 0.068)",
    "surface_strong":  "rgba(255, 255, 255, 0.085)",

    # Borders / dividers
    "border":          "rgba(255, 255, 255, 0.08)",
    "border_strong":   "rgba(255, 255, 255, 0.16)",

    # Text
    "text":            "#eef0f6",
    "text_muted":      "rgba(238, 240, 246, 0.65)",
    "text_dim":        "rgba(238, 240, 246, 0.42)",

    # Accent (warm amber — echo of the Amazon brand without the literal logo)
    "accent":          "#f5b849",
    "accent_bright":   "#ffd37a",
    "accent_soft":     "rgba(245, 184, 73, 0.14)",
    "accent_line":     "rgba(245, 184, 73, 0.35)",

    # Semantic
    "success":         "#7adbb0",
    "danger":          "#ff7a7a",
    "info":            "#8ab4f8",

    # Background-paths line color (matches `text` for a monochrome weave)
    "paths":           "#eef0f6",
}

# ---------------------------------------------------------------------------
# Chart palettes
# ---------------------------------------------------------------------------

# Categorical — used by Plotly colorway, ordered for visual separation.
CHART_PALETTE = [
    "#f5b849",  # accent amber
    "#8ab4f8",  # cool blue
    "#c59cff",  # lilac
    "#7adbb0",  # mint
    "#ff9c73",  # coral
    "#e68ed4",  # pink
]

# Binary: high-retention vs standard
COLOR_HIGH_RET = "#f5b849"
COLOR_STANDARD = "#6b8fd4"

# Sequential scale for transition heatmaps (dark → amber)
COLORSCALE_AMBER = [
    [0.00, "#13131a"],
    [0.25, "#2f2416"],
    [0.55, "#6b4a17"],
    [0.80, "#c38a2d"],
    [1.00, "#f5b849"],
]

# Diverging scale for expansion-difference heatmaps (red / neutral / green)
COLORSCALE_DIVERGING = [
    [0.00, "#d24d4d"],
    [0.45, "#2a2a33"],
    [0.55, "#2a2a33"],
    [1.00, "#7adbb0"],
]

# ---------------------------------------------------------------------------
# Geometry / typography
# ---------------------------------------------------------------------------

RADIUS_LG = "18px"
RADIUS    = "14px"
RADIUS_SM = "10px"
RADIUS_XS = "8px"

FONT_STACK = (
    "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', "
    "Helvetica, Arial, sans-serif"
)
FONT_STACK_DISPLAY = (
    "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', "
    "sans-serif"
)

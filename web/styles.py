"""
Global CSS for the Streamlit dashboard.

Injected once at app boot via `inject_global_styles()`. Uses [data-testid=...]
selectors which are stable across Streamlit 1.3x–1.5x and let us restyle
native widgets (metrics, buttons, sidebar, dataframes) without re-implementing
them.

Aesthetic: dark editorial surface, warm amber accent, flowing background paths
(see web/ui.py for the SVG + keyframe helpers).
"""

from __future__ import annotations

from web.theme import FONT_STACK, FONT_STACK_DISPLAY, PALETTE, RADIUS, RADIUS_LG, RADIUS_SM


def _css() -> str:
    p = PALETTE
    return f"""
/* ========================================================================
   1. Root + typography
   ========================================================================*/
:root {{
  --ar-bg: {p['bg']};
  --ar-bg-elev: {p['bg_elev']};
  --ar-surface: {p['surface']};
  --ar-surface-hover: {p['surface_hover']};
  --ar-border: {p['border']};
  --ar-border-strong: {p['border_strong']};
  --ar-text: {p['text']};
  --ar-text-muted: {p['text_muted']};
  --ar-text-dim: {p['text_dim']};
  --ar-accent: {p['accent']};
  --ar-accent-soft: {p['accent_soft']};
  --ar-accent-line: {p['accent_line']};
  --ar-radius: {RADIUS};
  --ar-radius-lg: {RADIUS_LG};
  --ar-radius-sm: {RADIUS_SM};
  --ar-font: {FONT_STACK};
  --ar-font-display: {FONT_STACK_DISPLAY};
}}

html, body, [data-testid="stAppViewContainer"] {{
  background: var(--ar-bg) !important;
  color: var(--ar-text);
  font-family: var(--ar-font);
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}}

/* Main content wrapper: roomier padding + a tighter max-width for editorial feel */
[data-testid="stAppViewContainer"] .main .block-container {{
  padding-top: 2.2rem;
  padding-bottom: 5rem;
  max-width: 1280px;
}}

/* Typography */
h1, h2, h3, h4, h5 {{
  font-family: var(--ar-font-display);
  color: var(--ar-text);
  letter-spacing: -0.015em;
  font-weight: 650;
}}
h1 {{ font-weight: 700; letter-spacing: -0.028em; }}
h2 {{ font-size: 1.55rem; margin-top: 2rem; }}
h3 {{ font-size: 1.2rem; margin-top: 1.5rem; }}

p, li {{
  color: var(--ar-text);
  line-height: 1.65;
}}

a {{
  color: var(--ar-accent);
  text-decoration: none;
  border-bottom: 1px dotted rgba(245, 184, 73, 0.5);
  transition: color 0.15s, border-color 0.15s;
}}
a:hover {{
  color: {p['accent_bright']};
  border-color: {p['accent_bright']};
}}

/* Tighten Streamlit's default block margins */
[data-testid="stVerticalBlock"] {{ gap: 0.75rem; }}

/* ========================================================================
   2. Hide / tame Streamlit chrome
   ========================================================================*/
#MainMenu {{ visibility: hidden; }}
footer {{ visibility: hidden; }}
header[data-testid="stHeader"] {{
  background: transparent;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}}

/* Decoration bar (top rainbow) — suppress */
[data-testid="stDecoration"] {{ display: none; }}

/* ========================================================================
   3. Sidebar
   ========================================================================*/
[data-testid="stSidebar"] {{
  background: linear-gradient(180deg, #0a0a0c 0%, #0e0e14 100%);
  border-right: 1px solid var(--ar-border);
}}
[data-testid="stSidebar"] [data-testid="stSidebarNavSeparator"] {{ display: none; }}

[data-testid="stSidebar"] .block-container {{
  padding-top: 2rem;
  padding-left: 1.1rem;
  padding-right: 1.1rem;
}}

/* Sidebar brand (image wordmark) — centered */
.ar-sidebar-brand {{
  margin: 0.1rem 0 1.2rem;
  padding: 0 0.05rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 0.45rem;
}}
.ar-sidebar-brand img {{
  display: block;
  width: 100%;
  max-width: 220px;
  height: auto;
  object-fit: contain;
  margin: 0 auto;
  filter: drop-shadow(0 4px 18px rgba(245, 184, 73, 0.18));
}}
.ar-sidebar-brand-kicker {{
  font-size: 10.5px;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: rgba(238, 240, 246, 0.5);
  text-align: center;
}}
.ar-sidebar-brand-fallback .ar-sidebar-brand-title {{
  font-family: var(--ar-font-display);
  font-weight: 650;
  font-size: 16px;
  letter-spacing: -0.015em;
  color: var(--ar-text);
  text-align: center;
}}

/* Sidebar title — we'll replace it via HTML anyway, but tame it */
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2 {{
  font-family: var(--ar-font-display);
  letter-spacing: -0.02em;
  font-weight: 650;
  margin-bottom: 0.5rem;
}}

/* Nav buttons */
[data-testid="stSidebar"] .stButton > button {{
  background: transparent;
  color: var(--ar-text-muted);
  border: 1px solid transparent;
  border-radius: var(--ar-radius-sm);
  padding: 0.55rem 0.85rem;
  font-weight: 450;
  text-align: left;
  justify-content: flex-start;
  transition: background 0.16s, border-color 0.16s, color 0.16s, transform 0.16s;
  position: relative;
  overflow: hidden;
}}
[data-testid="stSidebar"] .stButton > button:hover {{
  background: var(--ar-surface);
  border-color: var(--ar-border);
  color: var(--ar-text);
  transform: translateX(2px);
}}

/* Active page: the nav button's label is wrapped in **bold**, which renders
   as <strong>. We use :has(strong) to promote it visually. */
[data-testid="stSidebar"] .stButton > button:has(strong) {{
  background: var(--ar-accent-soft);
  border-color: rgba(245, 184, 73, 0.35);
  color: {p['accent_bright']};
}}
[data-testid="stSidebar"] .stButton > button:has(strong) strong {{
  font-weight: 600;
  color: {p['accent_bright']};
}}
[data-testid="stSidebar"] .stButton > button:has(strong)::before {{
  content: "";
  position: absolute;
  left: 0; top: 22%; bottom: 22%;
  width: 2px;
  background: var(--ar-accent);
  border-radius: 0 2px 2px 0;
}}

/* Sidebar section labels (multiselect, slider) */
[data-testid="stSidebar"] label p {{
  color: var(--ar-text-muted);
  font-size: 12px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  font-weight: 500;
}}

/* Sidebar inputs — subtle dark backgrounds */
[data-testid="stSidebar"] [data-baseweb="select"] > div,
[data-testid="stSidebar"] [data-baseweb="input"] > div {{
  background: var(--ar-surface) !important;
  border-radius: var(--ar-radius-sm) !important;
}}

/* ========================================================================
   4. Primary buttons (Search, Run Segmentation)
   ========================================================================*/
.main .stButton > button {{
  font-family: var(--ar-font);
  font-weight: 550;
  letter-spacing: 0.015em;
  border-radius: var(--ar-radius);
  border: 1px solid var(--ar-border);
  background: var(--ar-surface);
  color: var(--ar-text);
  padding: 0.55rem 1.1rem;
  transition: background 0.18s, border-color 0.18s, transform 0.18s, box-shadow 0.18s;
}}
.main .stButton > button:hover {{
  background: var(--ar-surface-hover);
  border-color: var(--ar-border-strong);
  transform: translateY(-1px);
}}

/* type="primary" button → amber filled CTA */
.main .stButton > button[kind="primary"] {{
  background: linear-gradient(180deg, #ffc96a 0%, #f5b849 100%);
  border: 1px solid rgba(0, 0, 0, 0.12);
  color: #1a1306;
  font-weight: 600;
  box-shadow:
    0 1px 0 rgba(255, 255, 255, 0.35) inset,
    0 6px 16px rgba(245, 184, 73, 0.22);
}}
.main .stButton > button[kind="primary"]:hover {{
  filter: brightness(1.05);
  transform: translateY(-1px);
  box-shadow:
    0 1px 0 rgba(255, 255, 255, 0.4) inset,
    0 10px 26px rgba(245, 184, 73, 0.32);
}}

/* ========================================================================
   5. Metric cards (glassy restyle of st.metric)
   ========================================================================*/
[data-testid="stMetric"] {{
  background: var(--ar-surface);
  border: 1px solid var(--ar-border);
  border-radius: var(--ar-radius);
  padding: 1rem 1.1rem 0.9rem;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  transition: background 0.2s, border-color 0.2s;
  position: relative;
  overflow: hidden;
}}
[data-testid="stMetric"]::before {{
  content: "";
  position: absolute;
  left: 0; top: 0; right: 0;
  height: 1px;
  background: linear-gradient(90deg,
    transparent 0%,
    rgba(245, 184, 73, 0.4) 50%,
    transparent 100%);
  opacity: 0.6;
}}
[data-testid="stMetric"]:hover {{
  background: var(--ar-surface-hover);
  border-color: var(--ar-border-strong);
}}
[data-testid="stMetricLabel"] p {{
  color: var(--ar-text-muted) !important;
  font-size: 11px !important;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-weight: 550;
  margin-bottom: 0.35rem;
}}
[data-testid="stMetricValue"] {{
  color: var(--ar-text) !important;
  font-family: var(--ar-font-display);
  font-size: 1.9rem !important;
  font-weight: 600 !important;
  letter-spacing: -0.025em;
  line-height: 1.1;
}}
[data-testid="stMetricDelta"] {{
  font-size: 0.8rem !important;
  color: var(--ar-text-muted) !important;
}}

/* ========================================================================
   6. Info / warning / error / success callouts
   ========================================================================*/
[data-testid="stAlert"] {{
  background: var(--ar-surface);
  border: 1px solid var(--ar-border);
  border-left-width: 3px;
  border-radius: var(--ar-radius-sm);
  color: var(--ar-text);
}}
[data-testid="stAlert"] p,
[data-testid="stAlert"] li {{ color: var(--ar-text) !important; }}

/* Info */
[data-testid="stAlert"]:has([data-testid="stAlertContainer-info"]),
[data-testid="stAlertContainer-info"] {{ border-left-color: {p['info']} !important; }}

/* Success */
[data-testid="stAlert"]:has([data-testid="stAlertContainer-success"]),
[data-testid="stAlertContainer-success"] {{ border-left-color: {p['success']} !important; }}

/* Warning */
[data-testid="stAlert"]:has([data-testid="stAlertContainer-warning"]),
[data-testid="stAlertContainer-warning"] {{ border-left-color: {p['accent']} !important; }}

/* Error */
[data-testid="stAlert"]:has([data-testid="stAlertContainer-error"]),
[data-testid="stAlertContainer-error"] {{ border-left-color: {p['danger']} !important; }}

/* Captions — restrained editorial tone */
.main [data-testid="stCaptionContainer"] p,
.main .stCaption p,
.main small {{
  color: var(--ar-text-muted) !important;
  font-size: 13px !important;
  line-height: 1.55 !important;
}}

/* ========================================================================
   7. Dataframe
   ========================================================================*/
[data-testid="stDataFrame"] {{
  border: 1px solid var(--ar-border);
  border-radius: var(--ar-radius-sm);
  overflow: hidden;
  background: var(--ar-surface);
}}

/* ========================================================================
   8. Plotly chart container (frame it like a glass card)
   ========================================================================*/
[data-testid="stPlotlyChart"],
.main [data-testid="stVegaLiteChart"] {{
  background: var(--ar-surface);
  border: 1px solid var(--ar-border);
  border-radius: var(--ar-radius);
  padding: 0.75rem 0.75rem 0.5rem;
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
}}
[data-testid="stPlotlyChart"] + [data-testid="stPlotlyChart"] {{ margin-top: 0.8rem; }}

/* Plotly modebar buttons — calmer */
.modebar-container .modebar-btn path {{ fill: var(--ar-text-muted) !important; }}
.modebar-container .modebar-btn:hover path {{ fill: var(--ar-accent) !important; }}

/* Matplotlib figure (used on the Network Graph + cluster diagnostics) */
[data-testid="stImage"] {{
  background: var(--ar-surface);
  border: 1px solid var(--ar-border);
  border-radius: var(--ar-radius);
  padding: 0.5rem;
}}

/* ========================================================================
   9. Inputs (text_input, selectbox, slider, radio, multiselect)
   ========================================================================*/
[data-baseweb="input"] > div,
[data-baseweb="textarea"] > div,
[data-baseweb="select"] > div {{
  background: var(--ar-surface) !important;
  border-color: var(--ar-border) !important;
  border-radius: var(--ar-radius-sm) !important;
}}
[data-baseweb="input"] > div:focus-within,
[data-baseweb="select"] > div:focus-within {{
  border-color: var(--ar-accent-line) !important;
  box-shadow: 0 0 0 2px rgba(245, 184, 73, 0.12) !important;
}}

/* Radio group — pill-style */
[role="radiogroup"] label {{
  color: var(--ar-text-muted);
}}

/* -----------------------------------------------------------------
   Selected sidebar filters on orange/accent backgrounds — force
   black text so the contrast works. Scoped to the sidebar so we
   never flip body text.
   ----------------------------------------------------------------- */
/* Multiselect "chip" / selected category tag */
[data-testid="stSidebar"] [data-baseweb="tag"],
[data-testid="stSidebar"] [data-baseweb="tag"] *,
[data-testid="stSidebar"] [data-baseweb="tag"] span {{
  color: #1a1306 !important;
}}
[data-testid="stSidebar"] [data-baseweb="tag"] {{
  background: {p['accent']} !important;
  border-color: rgba(0, 0, 0, 0.2) !important;
}}
/* The "x" remove icon on each chip */
[data-testid="stSidebar"] [data-baseweb="tag"] [role="presentation"] svg,
[data-testid="stSidebar"] [data-baseweb="tag"] svg {{
  fill: #1a1306 !important;
  color: #1a1306 !important;
}}

/* Radio — selected option pill. Streamlit renders the selected state with an
   amber-tinted background via the base ring + accent fill; force the label
   text to dark on that fill for contrast. */
[data-testid="stSidebar"] [role="radiogroup"] label[data-baseweb="radio"]:has(input:checked) p,
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) p {{
  color: #1a1306 !important;
  font-weight: 600;
}}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {{
  background: {p['accent']};
  border-radius: var(--ar-radius-sm);
  padding: 0.25rem 0.55rem;
}}

/* Slider — when the user drags, the selected number label overlays the
   amber thumb; make it dark for readability. */
[data-testid="stSidebar"] [data-baseweb="slider"] [role="slider"] {{
  color: #1a1306 !important;
}}
[data-testid="stSidebar"] [data-baseweb="slider"] div[data-testid="stTickBarMin"],
[data-testid="stSidebar"] [data-baseweb="slider"] div[data-testid="stTickBarMax"] {{
  color: var(--ar-text-muted) !important;
}}

/* Expander — default */
[data-testid="stExpander"] details {{
  background: var(--ar-surface);
  border: 1px solid var(--ar-border);
  border-radius: var(--ar-radius-sm);
}}
[data-testid="stExpander"] summary {{
  color: var(--ar-text);
  font-weight: 500;
}}
[data-testid="stExpander"] summary:hover {{
  color: {p['accent_bright']};
}}

/* Limitations page — opt-in prominent expander headers. The Limitations
   route emits an `.ar-limitations-page` sentinel <div>; we scope the styles
   via :has() on <body>, which is stable across Chrome 105+ / Safari 15.4+ /
   Firefox 121+ (i.e. every browser built in the last 18 months). */
body:has(.ar-limitations-page) [data-testid="stExpander"] details {{
  border: 1px solid var(--ar-border);
  background: var(--ar-surface);
  transition: background 0.18s, border-color 0.18s;
  margin-bottom: 0.55rem;
}}
body:has(.ar-limitations-page) [data-testid="stExpander"] details[open] {{
  background: var(--ar-surface-hover);
  border-color: var(--ar-border-strong);
}}
body:has(.ar-limitations-page) [data-testid="stExpander"] summary {{
  padding: 0.75rem 0.9rem;
  font-size: 15.5px;
  font-weight: 600;
  letter-spacing: -0.005em;
  cursor: pointer;
}}
body:has(.ar-limitations-page) [data-testid="stExpander"] summary:hover {{
  color: {p['accent_bright']};
}}
body:has(.ar-limitations-page) [data-testid="stExpander"] details[open] summary {{
  border-bottom: 1px solid var(--ar-border);
  color: {p['accent_bright']};
}}

/* ------------------------------------------------------------------
   Overview: "Where to go next" clickable cards.
   Rendered as pure-HTML <a class="ar-nextgo-card"> anchors (not st.button)
   so the card DOM and text-align are fully under our control. Clicks are
   routed via `?goto=<page>` and handled at the top of web/app.py.
   ------------------------------------------------------------------ */
.ar-nextgo-grid {{
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1rem;
  margin-top: 0.5rem;
}}
.ar-nextgo-card {{
  display: block;
  position: relative;
  padding: 1.15rem 2.2rem 1.15rem 1.2rem;
  min-height: 152px;
  background: var(--ar-surface);
  border: 1px solid var(--ar-border);
  border-radius: var(--ar-radius);
  text-align: left;
  text-decoration: none !important;
  color: var(--ar-text) !important;
  transition: background 0.2s, border-color 0.2s, transform 0.2s, box-shadow 0.2s;
}}
.ar-nextgo-card:hover {{
  background: var(--ar-surface-hover);
  border-color: var(--ar-accent-line);
  transform: translateY(-2px);
  box-shadow: 0 14px 30px rgba(245, 184, 73, 0.12);
}}
.ar-nextgo-card-title {{
  color: {p['accent_bright']};
  font-family: var(--ar-font-display);
  font-size: 15.5px;
  font-weight: 650;
  letter-spacing: -0.005em;
  margin-bottom: 0.5rem;
  text-align: left;
}}
.ar-nextgo-card-body {{
  color: var(--ar-text-muted);
  font-size: 13px;
  line-height: 1.55;
  text-align: left;
}}
.ar-nextgo-card-arrow {{
  position: absolute;
  right: 1rem;
  top: 1.05rem;
  font-size: 16px;
  color: var(--ar-text-dim);
  transition: color 0.2s, transform 0.2s;
}}
.ar-nextgo-card:hover .ar-nextgo-card-arrow {{
  color: {p['accent_bright']};
  transform: translateX(3px);
}}
@media (max-width: 860px) {{
  .ar-nextgo-grid {{ grid-template-columns: 1fr; }}
}}

/* ========================================================================
   10. HERO — the cinematic landing for Overview
   ========================================================================*/
.ar-hero {{
  position: relative;
  width: 100%;
  min-height: 520px;
  overflow: hidden;
  isolation: isolate;
  border-radius: var(--ar-radius-lg);
  border: 1px solid var(--ar-border);
  background:
    radial-gradient(ellipse 60% 50% at 50% 38%,
      rgba(245, 184, 73, 0.10) 0%,
      rgba(245, 184, 73, 0.03) 35%,
      transparent 70%),
    linear-gradient(180deg, #0a0a0c 0%, #0e0e12 100%);
  padding: 5.2rem 2rem 4rem;
  margin: 0 0 1.6rem;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
}}

.ar-hero-paths {{
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  color: var(--ar-text);
  pointer-events: none;
  z-index: 0;
  /* Soften the weave overall so the hero text & stat panel read cleanly. */
  opacity: 0.55;
}}

/* A radial darkening pass behind the hero content — concentrated on the
   lower half (where the stat row sits) so the stats always read against
   a dim, stable backdrop. */
.ar-hero::after {{
  content: "";
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse 68% 54% at 50% 72%,
      rgba(10, 10, 14, 0.72) 0%,
      rgba(10, 10, 14, 0.35) 55%,
      transparent 85%);
  pointer-events: none;
  z-index: 1;
}}

.ar-hero-paths path {{
  fill: none;
  stroke: currentColor;
  stroke-linecap: round;
  stroke-dasharray: 320 2200;
  animation:
    ar-path-flow var(--dur, 22s) linear infinite,
    ar-path-opacity var(--dur, 22s) ease-in-out infinite;
  animation-delay: var(--d, 0s), var(--d, 0s);
  will-change: stroke-dashoffset, opacity;
}}

@keyframes ar-path-flow {{
  from {{ stroke-dashoffset: 0; }}
  to   {{ stroke-dashoffset: -2520; }}
}}
@keyframes ar-path-opacity {{
  0%, 100% {{ opacity: calc(var(--op, 0.2) * 0.6); }}
  50%      {{ opacity: calc(var(--op, 0.2) * 1.15); }}
}}

.ar-hero-content {{
  position: relative;
  z-index: 2;
  max-width: 880px;
}}

.ar-eyebrow {{
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 11.5px;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.22em;
  color: {p['accent_bright']};
  margin-bottom: 1.6rem;
  padding: 0.4rem 0.9rem;
  border: 1px solid rgba(245, 184, 73, 0.28);
  background: rgba(245, 184, 73, 0.06);
  border-radius: 999px;
  backdrop-filter: blur(8px);
  opacity: 0;
  transform: translateY(-6px);
  animation: ar-fade-in 1.4s cubic-bezier(0.2, 0.8, 0.2, 1) 0.15s forwards;
}}
.ar-eyebrow::before {{
  content: "";
  width: 6px; height: 6px;
  border-radius: 50%;
  background: var(--ar-accent);
  box-shadow: 0 0 8px rgba(245, 184, 73, 0.7);
}}

.ar-hero-title {{
  font-family: var(--ar-font-display);
  font-size: clamp(2.6rem, 6vw, 4.6rem);
  font-weight: 700;
  letter-spacing: -0.035em;
  line-height: 1.02;
  margin: 0 0 1.8rem;
  color: var(--ar-text);
}}

.ar-word {{
  display: inline-block;
  margin-right: 0.32em;
  white-space: nowrap;
}}
.ar-word:last-child {{ margin-right: 0; }}

.ar-letter {{
  display: inline-block;
  opacity: 0;
  transform: translateY(72px);
  animation: ar-letter-rise 1.1s cubic-bezier(0.2, 0.85, 0.2, 1.0) both;
  animation-delay: var(--delay, 0s);
  background: linear-gradient(180deg,
    #ffffff 0%,
    rgba(255, 255, 255, 0.7) 100%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  -webkit-text-fill-color: transparent;
  padding: 0 0.005em;  /* prevent descender clipping */
}}

@keyframes ar-letter-rise {{
  to {{ opacity: 1; transform: translateY(0); }}
}}

.ar-hero-subtitle {{
  font-size: clamp(15px, 1.2vw, 17px);
  line-height: 1.6;
  color: var(--ar-text-muted);
  max-width: 640px;
  margin: 0 auto 2.2rem;
  opacity: 0;
  transform: translateY(10px);
  animation: ar-fade-in 1.6s cubic-bezier(0.2, 0.8, 0.2, 1) 1.6s forwards;
}}

/* Outer panel — an opaque, blurred surface that sits *on top* of the
   animated paths so the numbers don't fight with the weave. */
.ar-hero-stats-panel {{
  position: relative;
  display: inline-block;
  margin: 0 auto;
  padding: 1rem 1.4rem;
  border-radius: 999px;
  background:
    linear-gradient(180deg,
      rgba(12, 12, 16, 0.78) 0%,
      rgba(12, 12, 16, 0.6) 100%);
  border: 1px solid rgba(255, 255, 255, 0.10);
  box-shadow:
    0 1px 0 rgba(255, 255, 255, 0.05) inset,
    0 18px 42px rgba(0, 0, 0, 0.45);
  backdrop-filter: blur(14px) saturate(140%);
  -webkit-backdrop-filter: blur(14px) saturate(140%);
  opacity: 0;
  transform: translateY(14px);
  animation: ar-fade-in 1.6s cubic-bezier(0.2, 0.8, 0.2, 1) 1.85s forwards;
}}

.ar-hero-stats {{
  display: flex;
  gap: 0.55rem;
  justify-content: center;
  flex-wrap: wrap;
}}

/* Each stat is a fully-opaque mini-card so the number sits on a readable
   surface even when a bright path animates behind it. */
.ar-hero-stat {{
  position: relative;
  text-align: center;
  padding: 0.55rem 1rem;
  border-radius: 999px;
  background: rgba(20, 20, 27, 0.86);
  border: 1px solid rgba(255, 255, 255, 0.07);
  min-width: 118px;
}}
.ar-hero-stat-value {{
  display: block;
  font-family: var(--ar-font-display);
  font-size: 1.4rem;
  font-weight: 600;
  letter-spacing: -0.02em;
  color: {p['accent_bright']};
  line-height: 1.1;
}}
.ar-hero-stat-label {{
  display: block;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.18em;
  color: var(--ar-text-muted);
  margin-top: 0.3rem;
}}

@keyframes ar-fade-in {{
  to {{ opacity: 1; transform: translateY(0); }}
}}

/* ========================================================================
   11. Page header (non-Overview pages)
   ========================================================================*/
.ar-page-header {{
  position: relative;
  width: 100%;
  overflow: hidden;
  border-radius: var(--ar-radius);
  border: 1px solid var(--ar-border);
  background:
    radial-gradient(ellipse 40% 100% at 12% 50%,
      rgba(245, 184, 73, 0.08) 0%, transparent 60%),
    linear-gradient(180deg, #0b0b0f 0%, #0e0e14 100%);
  padding: 1.8rem 1.8rem 1.6rem;
  margin: 0 0 1.4rem;
  isolation: isolate;
}}

.ar-page-header-paths {{
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  color: var(--ar-text);
  pointer-events: none;
  z-index: 0;
  opacity: 0.55;
}}
.ar-page-header-paths path {{
  fill: none;
  stroke: currentColor;
  stroke-linecap: round;
  stroke-dasharray: 200 1800;
  animation: ar-path-flow var(--dur, 28s) linear infinite,
             ar-path-opacity var(--dur, 28s) ease-in-out infinite;
  animation-delay: var(--d, 0s);
}}

.ar-page-header-content {{
  position: relative;
  z-index: 2;
}}

.ar-page-eyebrow {{
  font-size: 11px;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.22em;
  color: {p['accent_bright']};
  margin-bottom: 0.5rem;
  opacity: 0.9;
}}

.ar-page-title {{
  font-family: var(--ar-font-display);
  font-size: 2.1rem;
  font-weight: 680;
  letter-spacing: -0.028em;
  line-height: 1.1;
  margin: 0 0 0.4rem;
  background: linear-gradient(180deg, #ffffff 0%, rgba(255, 255, 255, 0.72) 100%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  -webkit-text-fill-color: transparent;
}}

.ar-page-subtitle {{
  font-size: 14.5px;
  line-height: 1.55;
  color: var(--ar-text-muted);
  max-width: 780px;
  margin: 0;
}}

/* ========================================================================
   11b. Explainer card (explanation-first; tooltip holds the live value)
   ========================================================================*/
.ar-explainer-card {{
  position: relative;
  background: var(--ar-surface);
  border: 1px solid var(--ar-border);
  border-radius: var(--ar-radius);
  padding: 1rem 2.4rem 0.95rem 1.1rem;   /* extra right padding for "?" */
  min-height: 128px;
  transition: background 0.18s, border-color 0.18s;
  /* NOTE: no `overflow: hidden` — we need the tooltip to escape the card */
}}
.ar-explainer-card::before {{
  content: "";
  position: absolute;
  left: 0; top: 0; right: 0;
  height: 1px;
  background: linear-gradient(90deg,
    transparent 0%,
    rgba(245, 184, 73, 0.4) 50%,
    transparent 100%);
  opacity: 0.55;
  pointer-events: none;
}}
.ar-explainer-card:hover {{
  background: var(--ar-surface-hover);
  border-color: var(--ar-border-strong);
}}
.ar-explainer-label {{
  color: var(--ar-text-muted);
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-weight: 550;
  margin-bottom: 0.5rem;
}}
.ar-explainer-body {{
  color: var(--ar-text);
  font-size: 13.5px;
  line-height: 1.55;
}}

/* "?" help icon + CSS tooltip — mirrors st.metric's help-icon affordance */
.ar-explainer-help {{
  position: absolute;
  top: 0.7rem;
  right: 0.75rem;
  width: 18px; height: 18px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.07);
  color: var(--ar-text-muted);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  line-height: 1;
  cursor: help;
  user-select: none;
  transition: background 0.15s, color 0.15s;
}}
.ar-explainer-help:hover {{
  background: var(--ar-accent-soft);
  color: {p['accent_bright']};
}}
.ar-explainer-help::after {{
  content: attr(data-tooltip);
  position: absolute;
  right: -0.25rem;
  top: calc(100% + 0.5rem);
  min-width: 240px;
  max-width: 320px;
  padding: 0.7rem 0.85rem;
  background: var(--ar-bg-elev);
  border: 1px solid var(--ar-border-strong);
  border-radius: var(--ar-radius-sm);
  color: var(--ar-text);
  font-family: var(--ar-font);
  font-size: 12.5px;
  font-weight: 400;
  line-height: 1.5;
  letter-spacing: 0;
  text-align: left;
  text-transform: none;
  white-space: pre-line;
  z-index: 1000;
  opacity: 0;
  transform: translateY(-3px);
  pointer-events: none;
  transition: opacity 0.14s ease, transform 0.14s ease;
  box-shadow: 0 14px 34px rgba(0, 0, 0, 0.55);
}}
.ar-explainer-help:hover::after,
.ar-explainer-help:focus::after {{
  opacity: 1;
  transform: translateY(0);
}}

/* ========================================================================
   12. Glass card / panel
   ========================================================================*/
.ar-card {{
  background: var(--ar-surface);
  border: 1px solid var(--ar-border);
  border-radius: var(--ar-radius);
  padding: 1.2rem 1.3rem;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}}

.ar-card-title {{
  font-size: 11px;
  font-weight: 550;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--ar-text-dim);
  margin-bottom: 0.4rem;
}}

.ar-card-body {{
  color: var(--ar-text);
  line-height: 1.55;
}}

/* Section divider */
.ar-divider {{
  height: 1px;
  background: linear-gradient(90deg,
    transparent 0%,
    var(--ar-border) 15%,
    var(--ar-border) 85%,
    transparent 100%);
  border: 0;
  margin: 1.8rem 0 1.4rem;
}}

/* ========================================================================
   13. Reduced motion
   ========================================================================*/
@media (prefers-reduced-motion: reduce) {{
  .ar-hero-paths path,
  .ar-page-header-paths path,
  .ar-letter,
  .ar-eyebrow,
  .ar-hero-subtitle,
  .ar-hero-stats {{
    animation: none !important;
    opacity: 1 !important;
    transform: none !important;
  }}
}}

/* ========================================================================
   14. Responsive
   ========================================================================*/
@media (max-width: 860px) {{
  .ar-hero {{ padding: 3.5rem 1.2rem 2.8rem; min-height: 420px; }}
  .ar-hero-stats {{ gap: 1.4rem; }}
  .ar-page-header {{ padding: 1.4rem 1.2rem 1.2rem; }}
  .ar-page-title {{ font-size: 1.7rem; }}
}}
"""


def inject_global_styles() -> None:
    """Inject the global CSS stylesheet once. Call after st.set_page_config()."""
    import streamlit as st
    st.markdown(f"<style>{_css()}</style>", unsafe_allow_html=True)
